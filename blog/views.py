import logging
import re
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, ListView

# REST API
from rest_framework.generics import RetrieveAPIView

from .forms import CommentForm
from .models import Category, Comment, Post, ReplyComment, ShortLink
from .permissions import IsN8nRequest
from .serializers import PostDetailN8nSerializer

logger = logging.getLogger(__name__)

# =========================
# Constants
# =========================
POSTS_PER_PAGE = 10
POPULAR_POSTS_COUNT = 3
LATEST_POSTS_COUNT = 3
RELATED_POSTS_COUNT = 3
SEARCH_MIN_LENGTH = 3
SEARCH_MAX_RESULTS = 10
COMMENT_RATE_LIMIT_SECONDS = getattr(settings, "COMMENT_RATE_LIMIT_SECONDS", 30)


# =========================
# Simple Rate Limiter
# =========================
def rate_limit_by_ip(key_prefix, period_seconds):
    """Rate limiter بر اساس IP و cache"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip = _get_client_ip(request)
            cache_key = f"ratelimit:{key_prefix}:{ip}"

            if cache.get(cache_key):
                return JsonResponse(
                    {"error": "لطفاً کمی صبر کنید."},
                    status=429,
                ) if request.headers.get("X-Requested-With") == "XMLHttpRequest" else redirect(
                    request.META.get("HTTP_REFERER", "/")
                )

            cache.set(cache_key, True, period_seconds)
            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def _get_client_ip(request):
    """استخراج IP واقعی کاربر"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


# =========================
# Helper: Cached Random Posts (جایگزین order_by('?'))
# =========================
def _get_random_published_posts(count, exclude_id=None):
    """پست‌های تصادفی با annotate تعداد کامنت"""
    cache_key = f"random_posts:{exclude_id}:{count}"
    posts = cache.get(cache_key)

    if posts is None:
        qs = (
            Post.published
            .only("title", "slug", "image", "created")
            .annotate(
                comment_count=Count(
                    "comments",
                    filter=Q(comments__active=True)
                )
            )
        )
        if exclude_id:
            qs = qs.exclude(id=exclude_id)

        # به جای order_by('?') از روش بهینه‌تر استفاده کنید
        all_ids = list(qs.values_list("id", flat=True))
        if len(all_ids) > count:
            import random
            selected_ids = random.sample(all_ids, count)
            posts = list(qs.filter(id__in=selected_ids))
        else:
            posts = list(qs)

        cache.set(cache_key, posts, 300)

    return posts



# =========================
# Category List (Function View)
# =========================
def category_list(request, slug):
    category = get_object_or_404(Category, slug=slug)

    posts = (
        Post.published
        .filter(category=category)
        .select_related("author")
        .prefetch_related("tags")
        .only(
            "title", "slug", "description", "image",
            "created", "read_time",
            "author__full_name", "author__id",
        )
    )

    # Cache categories (تغییر کمی دارند)
    categories = cache.get_or_set(
        "all_categories",
        Category.objects.all(),
        timeout=600,
    )

    return render(request, "blog/category_list.html", {
        "category": category,
        "posts": posts,
        "categories": categories,
    })


# =========================
# Post List View
# =========================
class PostListView(ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = "posts"
    paginate_by = POSTS_PER_PAGE

    def get_queryset(self):
        queryset = (
            Post.published
            .select_related("category", "author")
            .prefetch_related("tags")
            .only(
                "title", "slug", "description", "image",
                "created", "read_time", "status",
                "category__name", "category__slug",
                "author__full_name",
            )
        )

        category_slug = self.kwargs.get("category_slug")
        tag_slug = self.kwargs.get("tag_slug")

        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        elif tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        category_slug = self.kwargs.get("category_slug")
        tag_slug = self.kwargs.get("tag_slug")

        # Cache categories
        context["categories"] = cache.get_or_set(
            "all_categories",
            Category.objects.all(),
            timeout=600,
        )

        context["active_category"] = None
        context["tag"] = None

        if category_slug:
            context["active_category"] = get_object_or_404(
                Category, slug=category_slug
            )
            context["canonical_url"] = self.request.build_absolute_uri(
                reverse("blog:post_list_by_category", args=[category_slug])
            )
        elif tag_slug:
            from taggit.models import Tag
            context["tag"] = get_object_or_404(Tag, slug=tag_slug)
            context["canonical_url"] = self.request.build_absolute_uri(
                reverse("blog:post_list_by_tag", args=[tag_slug])
            )
        else:
            context["canonical_url"] = self.request.build_absolute_uri(
                reverse("blog:post_list")
            )

        return context


# =========================
# Post Detail View
# =========================
class PostDetailView(DetailView):
    model = Post
    template_name = "blog/post_detail.html"
    context_object_name = "post"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_object(self, queryset=None):
        return get_object_or_404(
            Post.published
            .select_related("category", "author")
            .prefetch_related("tags")
            # ✅ تعداد کامنت‌های فعال خود این پست هم از قبل محاسبه بشه
            .annotate(
                comment_count=Count(
                    "comments",
                    filter=Q(comments__active=True)
                )
            ),
            slug=self.kwargs["slug"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object

        # ✅ اضافه کردن سوالات متداول فعال مربوط به همین پست
        context["faqs"] = post.faqs.filter(active=True)

        # ✅ پست‌های محبوب
        context["popular_posts"] = _get_random_published_posts(
            POPULAR_POSTS_COUNT, exclude_id=post.id
        )

        # آدرس پست را بدون پارامترهای اضافه (مثل کوئری استرینگ) به دست می‌آوریم
        context["canonical_url"] = self.request.build_absolute_uri(self.object.get_absolute_url())

        # ✅ آخرین پست‌ها
        cache_key = f"latest_posts:exclude:{post.id}"
        latest = cache.get(cache_key)
        if latest is None:
            latest = list(
            Post.published
            .exclude(id=post.id)
            .select_related("category")
            .only("title", "slug", "image", "created", "category__name", "category__slug")
            .annotate(
                comment_count=Count(
                    "comments",
                    filter=Q(comments__active=True)
                )
            )
            .order_by("-created")[:LATEST_POSTS_COUNT]
        )
        cache.set(cache_key, latest, 300)
        context["latest_posts"] = latest

        # ✅ کامنت‌ها و ریپلای‌های فعال
        context["comments"] = (
            post.comments
            .filter(active=True)
            .prefetch_related(
                Prefetch(
                    "replies",
                    queryset=ReplyComment.objects.filter(active=True),
                    to_attr="active_replies",
                )
            )
        )

        # ✅ پست‌های مرتبط
        tag_ids = post.tags.values_list("id", flat=True)
        if tag_ids:
            context["post_related_posts"] = (
                Post.published
                .filter(tags__id__in=tag_ids)
                .exclude(id=post.id)
                .distinct()
                .only("title", "slug", "image")
                .annotate(
                    comment_count=Count(
                        "comments",
                        filter=Q(comments__active=True)
                    )
                )
                [:RELATED_POSTS_COUNT]
            )
        else:
            context["post_related_posts"] = Post.objects.none()

        context["form"] = CommentForm()
        return context
    
    def post(self, request, *args, **kwargs):
        """ارسال کامنت یا ریپلای"""
        self.object = self.get_object()
        post = self.object

        # ✅ Rate limit by IP
        ip = _get_client_ip(request)
        rate_key = f"comment_rate:{ip}"
        if cache.get(rate_key):
            from django.contrib import messages
            messages.warning(request, "لطفاً کمی صبر کنید قبل از ارسال نظر بعدی.")
            return redirect(post.get_absolute_url())

        form = CommentForm(request.POST)

        if form.is_valid():
            parent_id = request.POST.get("parent_id")

            if parent_id:
                # Validate parent_id is numeric
                if not str(parent_id).isdigit():
                    return redirect(post.get_absolute_url())

                parent_comment = get_object_or_404(
                    Comment,
                    id=int(parent_id),
                    active=True,
                    post=post,  # ✅ اطمینان از تعلق کامنت به همین پست
                )
                ReplyComment.objects.create(
                    comment=parent_comment,
                    name=form.cleaned_data["name"],
                    body=form.cleaned_data["body"],
                    active=False,
                )
            else:
                comment = form.save(commit=False)
                comment.post = post
                comment.active = False
                comment.save()

            # Set rate limit
            cache.set(rate_key, True, COMMENT_RATE_LIMIT_SECONDS)
            return redirect(post.get_absolute_url())

        # Invalid form
        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)


# =========================
# Comment Form (standalone endpoint)
# =========================
@require_POST
@rate_limit_by_ip("comment_submit", COMMENT_RATE_LIMIT_SECONDS)
def comment_form(request, post_id):
    post = get_object_or_404(
        Post.published.only("id", "slug", "title"),
        id=post_id,
    )
    parent_id = request.POST.get("parent_id")

    form = CommentForm(request.POST)
    if form.is_valid():
        if parent_id:
            if not str(parent_id).isdigit():
                return redirect(post.get_absolute_url())

            parent_comment = get_object_or_404(
                Comment,
                id=int(parent_id),
                active=True,
                post=post,
            )
            ReplyComment.objects.create(
                comment=parent_comment,
                name=form.cleaned_data["name"],
                body=form.cleaned_data["body"],
                active=False,
            )
        else:
            comment = form.save(commit=False)
            comment.post = post
            comment.active = False
            comment.save()

    return redirect(post.get_absolute_url())


# =========================
# Short Link Redirect
# =========================
def short_link_redirect(request, short_code):
    link = get_object_or_404(
        ShortLink.objects.select_related("original_url"),
        short_code=short_code,
    )
    return redirect(link.get_redirect_url(), permanent=True)


# =========================
# N8N API View
# =========================
class PostDetailN8nAPIView(RetrieveAPIView):
    serializer_class = PostDetailN8nSerializer
    permission_classes = [IsN8nRequest]
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Post.published
            .select_related("category", "author")
            .prefetch_related("tags")
        )


# =========================
# Live Search View
# =========================
@require_GET
@cache_page(30)
def live_search_posts(request):
    query = request.GET.get("q", "").strip()

    # ✅ Sanitize input
    query = re.sub(r"[<>\"';(){}]", "", query)

    if len(query) < SEARCH_MIN_LENGTH:
        return JsonResponse({
            "success": True,
            "results": [],
            "count": 0,
            "message": f"حداقل {SEARCH_MIN_LENGTH} کاراکتر وارد کنید.",
        })

    if len(query) > 100:
        return JsonResponse({
            "success": False,
            "results": [],
            "count": 0,
            "message": "عبارت جستجو بیش از حد طولانی است.",
        })

    results = (
        Post.published
        .filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(tags__name__icontains=query)
        )
        .select_related("category")
        .only("title", "slug", "image", "category__name")
        .distinct()[:SEARCH_MAX_RESULTS]
    )

    data = [
        {
            "title": post.title,
            "url": post.get_absolute_url(),
            "image_url": post.get_image_url(),
            "category": post.category.name if post.category else "",
        }
        for post in results
    ]

    return JsonResponse({
        "success": True,
        "results": data,
        "count": len(data),
        "query": query,
    })

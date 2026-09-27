from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Comment, Post, ReplyComment, ShortLink, FAQ


# =========================
# FAQ Inline
# =========================
class FAQInline(admin.TabularInline):
    model = FAQ
    extra = 1
    fields = ['question', 'answer', 'order', 'active']


# =========================
# Category Admin
# =========================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "post_count")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    list_per_page = 25

    def post_count(self, obj):
        return obj.posts.count()

    post_count.short_description = "تعداد پست"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("posts")
        )


# =========================
# Reply Comment Inline
# =========================
class ReplyCommentInline(admin.TabularInline):
    model = ReplyComment
    extra = 0
    readonly_fields = ("created",)
    fields = ("name", "body", "active", "created")
    can_delete = True


# =========================
# Comment Inline (for Post)
# =========================
class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ("created",)
    fields = ("name", "body", "active", "created")
    show_change_link = True


# =========================
# Post Admin
# =========================
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "category",
        "status",
        "created",
        "read_time",
        "comment_count_display",
    )

    list_filter = (
        "status",
        "category",
        "created",
    )

    search_fields = (
        "title",
        "description",
    )

    prepopulated_fields = {"slug": ("title",)}

    ordering = ("-created",)
    list_per_page = 15
    list_select_related = ("author", "category")
    date_hierarchy = "created"

    inlines = [CommentInline,FAQInline]

    fieldsets = (
        (
            "اطلاعات اصلی",
            {"fields": ("title", "slug", "author", "category", "status")},
        ),
        (
            "محتوا",
            {"fields": ("description", "text", "image", "voice")},
        ),
        (
            "تنظیمات مقاله",
            {"fields": ("read_time", "tags")},
        ),
        (
            "زمان‌ها",
            {
                "fields": ("created", "update_date"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created", "update_date")

    actions = ["make_published", "make_draft"]

    def comment_count_display(self, obj):
        return getattr(obj, "_comment_count", 0)

    comment_count_display.short_description = "تعداد نظرات"
    comment_count_display.admin_order_field = "_comment_count"

    def get_queryset(self, request):
        from django.db.models import Count

        return (
            super()
            .get_queryset(request)
            .select_related("author", "category")
            .annotate(_comment_count=Count("comments"))
        )

    @admin.action(description="انتشار پست‌های انتخاب شده")
    def make_published(self, request, queryset):
        updated = queryset.update(status=Post.STATUS.PUBLISHED)
        self.message_user(request, f"{updated} پست منتشر شد.")

    @admin.action(description="پیش‌نویس کردن پست‌های انتخاب شده")
    def make_draft(self, request, queryset):
        updated = queryset.update(status=Post.STATUS.DRAFT)
        self.message_user(request, f"{updated} پست پیش‌نویس شد.")


# =========================
# Comment Admin
# =========================
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("name", "post", "active", "created", "reply_count")
    list_filter = ("active", "created")
    search_fields = ("name", "body")
    ordering = ("-created",)
    list_per_page = 20
    list_select_related = ("post",)

    inlines = (ReplyCommentInline,)

    actions = ["approve_comments", "reject_comments"]

    def reply_count(self, obj):
        return obj.replies.count()

    reply_count.short_description = "تعداد پاسخ"

    @admin.action(description="تایید نظرات انتخاب شده")
    def approve_comments(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f"{updated} نظر تایید شد.")

    @admin.action(description="رد نظرات انتخاب شده")
    def reject_comments(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f"{updated} نظر رد شد.")


# =========================
# Reply Comment Admin
# =========================
@admin.register(ReplyComment)
class ReplyCommentAdmin(admin.ModelAdmin):
    list_display = ("name", "comment", "active", "created")
    list_filter = ("active", "created")
    search_fields = ("name", "body")
    ordering = ("-created",)
    list_per_page = 20
    list_select_related = ("comment", "comment__post")

    actions = ["approve_replies", "reject_replies"]

    @admin.action(description="تایید پاسخ‌های انتخاب شده")
    def approve_replies(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f"{updated} پاسخ تایید شد.")

    @admin.action(description="رد پاسخ‌های انتخاب شده")
    def reject_replies(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f"{updated} پاسخ رد شد.")


# =========================
# ShortLink Admin
# =========================
@admin.register(ShortLink)
class ShortLinkAdmin(admin.ModelAdmin):
    list_display = ("short_code", "original_url")
    search_fields = ("short_code", "original_url__title")
    list_select_related = ("original_url",)
    list_per_page = 25


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'post', 'order', 'active']
    list_filter = ['active', 'post']
    search_fields = ['question', 'answer']

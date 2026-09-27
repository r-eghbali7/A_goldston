# home/views.py

import logging

from django.shortcuts import redirect, render
from django.views.generic import ListView, TemplateView
from django.views.decorators.http import require_http_methods, require_GET
from django.utils import timezone
from django.contrib import messages

from rest_framework.views import APIView
from rest_framework.response import Response

from .forms import EmailSubscribeForm, SimpleUserLandingForm
from .models import ParsianCoin
from .services import update_and_get_gold_data,format_number_fa
from .serializers import ParsianCoinPriceSerializer
from .permissions import IsN8nRequest
from blog.models import Post



logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────
#  ۱. صفحه اصلی
# ──────────────────────────────────────────────────

@require_GET
def home_view(request):
    """صفحه اصلی سایت"""

    # ✅ 3 پست آخر (منتشر شده) — 1 کوئری بهینه
    latest_posts = (
        Post.published
        .select_related('category', 'author')
        .only(
            'id', 'title', 'slug', 'description', 'image',
            'created', 'category__name', 'category__slug',
            'author__full_name', 'read_time'
        )[:3]
    )

    # ✅ پست‌های محبوب — بدون order_by('?')
    popular_post_ids = list(
        Post.published
        .order_by('?')
        .values_list('id', flat=True)[:10]
    )

    popular_posts = []
    if popular_post_ids:
        import random
        selected_ids = random.sample(
            popular_post_ids,
            min(3, len(popular_post_ids)),
        )
        popular_posts = (
            Post.published
            .filter(id__in=selected_ids)
            .select_related('category')
            .only(
                'id', 'title', 'slug', 'description', 'image',
                'created', 'category__name', 'category__slug',
            )
        )

    # ✅ پست‌هایی که ویس (پادکست) دارند — آخرین ۱۰ تا
    podcast_posts = (
        Post.published
        .exclude(voice='')
        .exclude(voice__isnull=True)
        .select_related('category')
        .only(
            'id', 'title', 'slug', 'image', 'voice',
            'read_time', 'created', 'category__name',
        )
        .order_by('-created')[:10]
    )

    # ✅ تعداد پست‌های منتشرشده (نه همه)
    post_count = Post.published.count()

    context = {
        'latest_posts': latest_posts,
        'popular_posts': popular_posts,
        'podcast_posts': podcast_posts,
        'post_count': post_count,
    }
    return render(request, 'home/index.html', context)

# ──────────────────────────────────────────────────
#  ۲. لیست قیمت سکه‌های پارسیان
# ──────────────────────────────────────────────────

# views.py

class ParsianCoinListView(ListView):
    model = ParsianCoin
    template_name = 'home/gold_list_price.html'
    context_object_name = 'coins'

    def get_queryset(self):
        """فقط سکه‌های موجود — بدون only() تا deferred field نداشته باشیم"""
        return ParsianCoin.objects.in_stock_ordered()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        gold_data = data = update_and_get_gold_data()
        gold_price = gold_data['gold_18k_price']

        # ✅ queryset را به لیست تبدیل کنید تا دوباره evaluate نشود
        coins = list(context['coins'])
        for coin in coins:
            price = coin.calc_price(gold_price)
            coin.display_price = f"{price:,}" if price > 0 else "۰"
        context['coins'] = coins

        change_info = gold_data['changes'].get('gold_18k_price', {})
        change_percent = '۰٪'
        change_class = 'text-[#92a4c9]'

        direction = change_info.get('direction', 'unchanged')
        if direction == 'up':
            change_percent = f"+{change_info['percent']}%"
            change_class = 'text-[#0bda5e]'
        elif direction == 'down':
            change_percent = f"-{change_info['percent']}%"
            change_class = 'text-[#fa6238]'

        context.update({
            'gold_price_per_gram': format_number_fa(gold_price) if gold_price else '۰',
            'last_update': gold_data.get('last_update_str', 'نامشخص'),
            'change_percent': change_percent,
            'change_class': change_class,
        })
        return context

# ──────────────────────────────────────────────────
#  ۳. صفحات ایستا
# ──────────────────────────────────────────────────

class TaraheSiteView(TemplateView):
    template_name = 'home/tarahe_site.html'


class AkasSiteView(TemplateView):
    template_name = 'home/akase.html'


# ──────────────────────────────────────────────────
#  ۴. API برای n8n
# ──────────────────────────────────────────────────

class ParsianCoinPriceN8nAPIView(APIView):
    permission_classes = [IsN8nRequest]

    def get(self, request):
        # ✅ از سرویس مرکزی استفاده کن (بدون تکرار)
        gold_data = data = update_and_get_gold_data()
        gold_price = gold_data['gold_18k_price']

        coins = ParsianCoin.objects.in_stock_ordered()
        serializer = ParsianCoinPriceSerializer(
            coins,
            many=True,
            context={'gold_price': gold_price},
        )

        today = timezone.now().date()
        return Response({
            'date': today.strftime('%Y/%m/%d'),
            'last_update_time': gold_data.get('last_update_str', 'نامشخص'),
            'gold_price_per_gram_18k': format_number_fa(gold_price),
            'coins': serializer.data,
        })


# ──────────────────────────────────────────────────
#  ۵. لندینگ سکه (فرم ثبت درخواست)
# ──────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def landing_coin_view(request):
    """فرم ساده ثبت درخواست در لندینگ"""

    if request.method == 'POST':
        form = SimpleUserLandingForm(request.POST)
        if form.is_valid():
            form.save()  # is_call=False به صورت پیش‌فرض
            messages.success(request, 'درخواست شما با موفقیت ثبت شد.')
            return redirect('home:parsian')
        # ❌ باگ قبلی: فرم جدید خالی ساخته می‌شد
        # ✅ الان فرم با خطاها برگردانده می‌شود
    else:
        form = SimpleUserLandingForm()

    return render(request, 'home/landig_coine.html', {'form': form})


# ──────────────────────────────────────────────────
#  ۶. ماشین‌حساب طلا
# ──────────────────────────────────────────────────

@require_GET
def calculator_view(request):
    """ویوی ماشین‌حساب با نمایش نرخ‌های لحظه‌ای بازار در ترتیب مشخص."""
    gold_data = update_and_get_gold_data()
    formatted_prices = gold_data.get('formatted', {})
    price_changes = gold_data.get('changes', {})

    # پیکربندی ترتیب نمایش، نام‌ها و آیکون‌ها
    items_config = [
        ('gold_18k_price', 'طلا ۱۸ عیار', 'workspace_premium'),
        ('gold_price_irr', 'انس جهانی', 'language'),
        ('sikka_imami', 'سکه امامی', 'stars'),
        ('sikka_tamam', 'سکه تمام بهار آزادی', 'monetization_on'),
        ('sikka_nim', 'سکه نیم', 'adjust'),
        ('sikka_rub', 'سکه ربع', 'data_usage'),
    ]

    market_rates = []
    for key, label, icon in items_config:
        change_info = price_changes.get(key, {})
        
        # قالب‌بندی درصد تغییرات
        percent = change_info.get('percent', 0)
        direction = change_info.get('direction', 'unchanged')
        change_display = f"{percent}٪" if direction != 'unchanged' else "-"

        market_rates.append({
            'label': label,
            'price': formatted_prices.get(key, '۰'),
            'unit': 'تومان',
            'icon': icon,
            'icon_bg': change_info.get('bg_color', 'bg-gray-500/10'),
            'icon_color': change_info.get('color', 'text-[#92a4c9]'),
            'change_class': change_info.get('color', 'text-[#92a4c9]'),
            'change_display': change_display,
            'trend_icon': change_info.get('icon', 'remove'),
        })

    context = {
        'market_rates': market_rates
    }
    return render(request, 'home/calculator.html', context)

# ──────────────────────────────────────────────────
#  7. گرفتن ایمیل از کاربر در فوتر
# ──────────────────────────────────────────────────
def email_subscribe(request):
    if request.method == 'POST':
        form = EmailSubscribeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'ایمیل شما با موفقیت ثبت شد!')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)

    return redirect(request.META.get('HTTP_REFERER', '/'))
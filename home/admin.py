# home/admin.py

from django.contrib import admin
from django.utils import timezone
from django.utils.timesince import timesince
from django.http import HttpResponse

from .models import (
    ParsianCoin, GoldDailyPrice, GoldPriceCache, UserLandingCoine,
)

import json
import csv


# ──────────────────────────────────────────────────
#  ۱. سکه پارسیان
# ──────────────────────────────────────────────────

@admin.register(ParsianCoin)
class ParsianCoinAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'weight_gram',
        'display_order', 'is_in_stock', 'is_featured',
    ]
    list_display_links = ['name']
    list_editable = ['display_order']
    list_filter = ['is_featured', 'is_in_stock']
    search_fields = ['name']
    ordering = ['display_order', 'weight_gram']
    list_per_page = 25
    actions = ['make_featured', 'remove_featured', 'mark_in_stock', 'mark_out_of_stock']

    fieldsets = (
        ('اطلاعات سکه', {
            'fields': ('name', 'weight_gram', 'display_order'),
        }),
        ('وضعیت', {
            'fields': ('is_featured', 'is_in_stock'),
            'classes': ('collapse',),
        }),
    )

    @admin.action(description='تبدیل به پیشنهادی')
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} سکه به عنوان پیشنهادی علامت‌گذاری شد.')

    @admin.action(description='حذف از پیشنهادی')
    def remove_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} سکه از پیشنهادی حذف شد.')

    @admin.action(description='موجود کردن')
    def mark_in_stock(self, request, queryset):
        updated = queryset.update(is_in_stock=True)
        self.message_user(request, f'{updated} سکه موجود شد.')

    @admin.action(description='ناموجود کردن')
    def mark_out_of_stock(self, request, queryset):
        updated = queryset.update(is_in_stock=False)
        self.message_user(request, f'{updated} سکه ناموجود شد.')


# ──────────────────────────────────────────────────
#  ۲. قیمت روزانه طلا
# ──────────────────────────────────────────────────

@admin.register(GoldDailyPrice)
class GoldDailyPriceAdmin(admin.ModelAdmin):
    list_display = [
        'date',
        'gold_price_irr', 'gold_18k_price',
        'sikka_imami', 'sikka_tamam',
        'sikka_nim', 'sikka_rub',
        'fetched_at',
    ]
    list_filter = ['date']
    search_fields = ['date']
    ordering = ['-date']
    list_per_page = 30
    date_hierarchy = 'date'
    readonly_fields = [
        'date', 'gold_price_irr', 'gold_18k_price',
        'sikka_imami', 'sikka_tamam', 'sikka_rub', 'sikka_nim',
        'fetched_at',
    ]

    fieldsets = (
        ('تاریخ', {'fields': ('date', 'fetched_at')}),
        ('قیمت طلا', {'fields': ('gold_price_irr', 'gold_18k_price')}),
        ('قیمت سکه‌ها', {
            'fields': ('sikka_imami', 'sikka_tamam', 'sikka_nim', 'sikka_rub'),
            'classes': ('wide',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ──────────────────────────────────────────────────
#  ۳. کش قیمت طلا
# ──────────────────────────────────────────────────

@admin.register(GoldPriceCache)
class GoldPriceCacheAdmin(admin.ModelAdmin):
    list_display = ['id', 'cache_status', 'last_updated']
    readonly_fields = ['pretty_formatted_data', 'pretty_raw_data', 'last_updated']
    exclude = ['data', 'raw_data']
    list_per_page = 1

    @admin.display(description='وضعیت')
    def cache_status(self, obj):
        if not obj.last_updated:
            return 'بدون داده'
        seconds = (timezone.now() - obj.last_updated).total_seconds()
        if seconds < 120:
            return 'فعال'
        elif seconds < 600:
            return 'نیمه‌فعال'
        return 'منقضی'

    @admin.display(description='داده‌های فرمت‌شده')
    def pretty_formatted_data(self, obj):
        return self._render_json(obj.data)

    @admin.display(description='داده‌های خام')
    def pretty_raw_data(self, obj):
        return self._render_json(getattr(obj, 'raw_data', None))

    def _render_json(self, data):
        if not data:
            return 'داده‌ای موجود نیست'
        try:
            return json.dumps(data, indent=4, ensure_ascii=False)
        except Exception:
            return str(data)[:300]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return True if obj is None else obj.id == 1

    def get_queryset(self, request):
        return super().get_queryset(request).filter(id=1)


# ──────────────────────────────────────────────────
#  ۴. درخواست کاربران
# ──────────────────────────────────────────────────

@admin.register(UserLandingCoine)
class UserLandingCoineAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'phone_number', 'post_code',
        'birthday', 'is_call', 'create_date',
    ]
    list_display_links = ['full_name']
    list_filter = ['is_call']
    search_fields = ['full_name', 'phone_number', 'post_code', 'address']
    ordering = ['-create_date']
    list_per_page = 25
    actions = ['mark_as_called', 'mark_as_not_called', 'export_selected']

    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('full_name', 'phone_number', 'birthday'),
        }),
        ('آدرس و کد پستی', {
            'fields': ('address', 'post_code'),
            'classes': ('wide',),
        }),
        ('وضعیت پیگیری', {
            'fields': ('is_call',),
        }),
        ('اطلاعات سیستمی', {
            'fields': ('create_date',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['create_date']

    @admin.action(description='تماس گرفته شد')
    def mark_as_called(self, request, queryset):
        updated = queryset.update(is_call=True)
        self.message_user(request, f'{updated} درخواست علامت‌گذاری شد.')

    @admin.action(description='در انتظار تماس')
    def mark_as_not_called(self, request, queryset):
        updated = queryset.update(is_call=False)
        self.message_user(request, f'{updated} درخواست علامت‌گذاری شد.')

    @admin.action(description='خروجی CSV')
    def export_selected(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="user_requests.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([
            'نام و نام خانوادگی', 'شماره تماس', 'آدرس',
            'کد پستی', 'تاریخ تولد', 'تماس گرفته شد', 'تاریخ ثبت',
        ])

        for obj in queryset.iterator():
            writer.writerow([
                obj.full_name,
                obj.phone_number,
                obj.address or '',
                obj.post_code or '',
                str(obj.birthday) if obj.birthday else '',
                'بله' if obj.is_call else 'خیر',
                str(obj.create_date) if obj.create_date else '',
            ])

        return response

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        qs = self.get_queryset(request)
        total = qs.count()
        not_called = qs.filter(is_call=False).count()
        extra_context['title'] = (
            f'درخواست‌های کاربران — '
            f'کل: {total} | '
            f'تماس نگرفته: {not_called} | '
            f'تماس گرفته: {total - not_called}'
        )
        return super().changelist_view(request, extra_context=extra_context)

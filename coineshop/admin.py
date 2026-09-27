# coineshop/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, F, Value, DecimalField
from decimal import Decimal

from .models import UserGoldAsset, OrderStatus


@admin.register(UserGoldAsset)
class UserGoldAssetAdmin(admin.ModelAdmin):
    list_display = (
        'user_info_display',
        'title',
        "gold_price_buy",
        'weight',
        'buy_price_display',
        'current_price_display',
        'profit_display',
        'profit_percent_display',
        'status_display',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'user__phone')
    list_select_related = ('user',)
    list_per_page = 30
    date_hierarchy = 'created_at'
    list_editable = ('status',) if False else ()  # در صورت نیاز فعال کنید

    actions = ['approve_selected', 'reject_selected']

    fieldsets = (
        ('اطلاعات کاربر', {
            'fields': ('user',),
        }),
        ('اطلاعات محصول', {
            'fields': ('title', 'image','weight', 'buy_price', "gold_price_buy"),
        }),
        ('وضعیت', {
            'fields': ('status',),
        }),
    )

    def get_queryset(self, request):
        """
        یک بار قیمت طلا را واکشی کن و روی request ذخیره کن.
        از N+1 Query جلوگیری می‌شود.
        """
        qs = super().get_queryset(request).select_related('user')
        # ذخیره قیمت طلا روی request برای استفاده در display methodها
        request._gold_price = UserGoldAsset.get_gold_price_today()
        self._gold_price = request._gold_price
        return qs

    # ===== نمایش فرمت‌شده =====

    @admin.display(description='قیمت خرید', ordering='buy_price')
    def buy_price_display(self, obj):
        return f"{obj.buy_price:,} تومان"

    @admin.display(description='قیمت فعلی')
    def current_price_display(self, obj):
        price = obj.calc_current_price(self._gold_price)
        return f"{int(price):,} تومان"

    @admin.display(description='سود / ضرر')
    def profit_display(self, obj):
        profit = obj.calc_profit_amount(self._gold_price)
        profit_int = int(profit)

        if profit_int >= 0:
            color = '#28a745'  # سبز
            sign = '+'
        else:
            color = '#dc3545'  # قرمز
            sign = '-'
        
        # ابتدا عدد را با کاما فرمت می‌کنیم
        formatted_profit = f"{abs(profit_int):,}"
        
        # حالا آن را به صورت یک متغیر عادی به format_html می‌دهیم
        return format_html(
            '<span style="color:{}; font-weight:bold;">{} {} تومان</span>',
            color, sign, formatted_profit
        )

    
    @admin.display(description='کاربر', ordering='user__phone')
    def user_info_display(self, obj):
        # دریافت نام کامل در صورت وجود
        full_name = obj.user.full_name
        full_name = full_name.strip()
        
        # دریافت شماره تماس (با فرض اینکه فیلد شماره در مدل یوزر phone نام دارد)
        phone = getattr(obj.user, 'phone', obj.user.phone_number) 
        
        if full_name:
            return f"{full_name} - ({phone})"
        return phone


    @admin.display(description='درصد سود')
    def profit_percent_display(self, obj):
        percent = obj.calc_profit_percent(self._gold_price)
        rounded = round(percent, 2)

        if rounded >= 0:
            color = '#28a745'
            icon = '📈'
        else:
            color = '#dc3545'
            icon = '📉'

        return format_html(
            '<span style="color:{};">{} {}٪</span>',
            color, icon, rounded
        )

    @admin.display(description='وضعیت')
    def status_display(self, obj):
        colors = {
            OrderStatus.PENDING: '#ffc107',
            OrderStatus.APPROVED: '#28a745',
            OrderStatus.REJECTED: '#dc3545',
            OrderStatus.CANCELLED: '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:#fff; padding:3px 10px; '
            'border-radius:12px; font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )

    # ===== اکشن‌های گروهی =====

    @admin.action(description='✅ تأیید موارد انتخاب‌شده')
    def approve_selected(self, request, queryset):
        updated = queryset.filter(status=OrderStatus.PENDING).update(
            status=OrderStatus.APPROVED
        )
        self.message_user(request, f'{updated} مورد تأیید شد.')

    @admin.action(description='❌ رد موارد انتخاب‌شده')
    def reject_selected(self, request, queryset):
        updated = queryset.filter(status=OrderStatus.PENDING).update(
            status=OrderStatus.REJECTED
        )
        self.message_user(request, f'{updated} مورد رد شد.')

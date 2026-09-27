# coineshop/models.py

from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.core.validators import MinValueValidator
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# ===== ثابت‌ها =====
CACHE_GOLD_PRICE_KEY = 'gold_price_18k_today'
CACHE_GOLD_PRICE_TTL = 300  # 5 دقیقه


class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'در انتظار تایید'
    APPROVED = 'approved', 'تایید شده'
    REJECTED = 'rejected', 'رد شده'
    CANCELLED = 'cancelled', 'لغو شده'


class UserGoldAssetManager(models.Manager):
    """منیجر سفارشی برای دارایی‌های طلای کاربر"""

    def approved(self):
        """فقط دارایی‌های تأیید شده"""
        return self.filter(status=OrderStatus.APPROVED)

    def for_user(self, user):
        """دارایی‌های یک کاربر خاص"""
        return self.filter(user=user)

    def approved_for_user(self, user):
        """دارایی‌های تأیید شده یک کاربر خاص - بهینه"""
        return (
            self.filter(user=user, status=OrderStatus.APPROVED)
            .select_related('user')
            .only(
                'id', 'title', 'image', 'weight',
                'buy_price', 'status', 'created_at',
                'user__id', 'user__phone_number',
            )
        )


class UserGoldAsset(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gold_assets',
        verbose_name='کاربر',
    )

    title = models.CharField(
        max_length=255,
        verbose_name='عنوان محصول',
    )

    image = models.ImageField(
        upload_to='products/%Y/%m/',
        blank=True,
        verbose_name='تصویر',
    )

    weight = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name='وزن (گرم)',
    )

    gold_price_buy = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='قیمت روز طلا خریداری شده)',
    )

    buy_price = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='قیمت خرید (تومان)',
    )

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        verbose_name='وضعیت',
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='آخرین بروزرسانی',
    )

    objects = UserGoldAssetManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'دارایی طلای کاربر'
        verbose_name_plural = 'دارایی‌های طلای کاربران'
        indexes = [
            models.Index(
                fields=['user', 'status'],
                name='idx_user_status',
            ),
            models.Index(
                fields=['status', '-created_at'],
                name='idx_status_created',
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.title} ({self.get_status_display()})"

    # ===== کش قیمت طلا (یک بار واکشی، همه جا استفاده) =====
    @staticmethod
    def get_gold_price_today() -> Decimal:
        """
        قیمت روز طلای ۱۸ عیار با کش ۵ دقیقه‌ای.
        از N+1 Query جلوگیری می‌کند.
        """
        price = cache.get(CACHE_GOLD_PRICE_KEY)
        if price is not None:
            return price

        try:
            # ⚠️ حتماً order_by داشته باشد تا آخرین قیمت برگردد
            from home.models import GoldDailyPrice
            price_obj = (
                GoldDailyPrice.objects
                .order_by('-date')
                .values_list('gold_18k_price', flat=True)  # ✅ نام صحیح فیلد
                .first()
            )
            price = Decimal(str(price_obj)) if price_obj else Decimal('0')
        except Exception as e:
            logger.error(f"خطا در واکشی قیمت طلا: {e}")
            price = Decimal('0')

        cache.set(CACHE_GOLD_PRICE_KEY, price, CACHE_GOLD_PRICE_TTL)
        return price

    # ===== محاسبات (بدون کوئری اضافه) =====
    # ===== محاسبات (بدون کوئری اضافه) =====
    def calc_current_price(self, gold_price: Decimal = None) -> Decimal:
        """
        محاسبه ارزش فعلی دارایی
        فرمول: وزن * قیمت روز طلای ۱۸ عیار
        """
        if gold_price is None:
            gold_price = self.get_gold_price_today()
            
        # تبدیل وزن به Decimal برای اطمینان و ضرب در قیمت روز
        return Decimal(str(self.weight)) * gold_price

    def calc_profit_amount(self, gold_price: Decimal = None) -> Decimal:
        """
        محاسبه مقدار سود یا زیان به تومان
        فرمول: ارزش فعلی - قیمت تمام شده خرید
        """
        current_value = self.calc_current_price(gold_price)
        # buy_price را به Decimal تبدیل می‌کنیم تا با current_value قابل تفریق باشد
        return current_value - Decimal(str(self.buy_price))

    def calc_profit_percent(self, gold_price: Decimal = None) -> Decimal:
        """
        محاسبه درصد سود یا زیان
        فرمول: (مقدار سود / قیمت تمام شده خرید) * 100
        """
        if self.buy_price == 0:
            return Decimal('0')
            
        profit = self.calc_profit_amount(gold_price)
        return (profit / Decimal(str(self.buy_price))) * Decimal('100')


    # ===== Property ها (برای سازگاری با تمپلیت) =====
    @property
    def current_price(self) -> Decimal:
        return self.calc_current_price()

    @property
    def profit_amount(self) -> Decimal:
        return self.calc_profit_amount()

    @property
    def profit_percent(self) -> Decimal:
        return self.calc_profit_percent()

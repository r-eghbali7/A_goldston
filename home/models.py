# home/models.py

import math

from django.db import models
from django.core.validators import RegexValidator, MinLengthValidator
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone
from django_jalali.db import models as jmodels
from jdatetime import date as jdate
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# ===== ثابت‌ها =====
CACHE_GOLD_PRICE_KEY = 'gold_daily_price_latest'
CACHE_GOLD_PRICE_TTL = 300  # 5 دقیقه


# ──────────────────────────────────────────────────
#  ۱. سکه پارسیان
# ──────────────────────────────────────────────────

class ParsianCoinManager(models.Manager):
    """منیجر سفارشی با کوئری‌های رایج"""

    def in_stock(self):
        return self.filter(is_in_stock=True)

    def featured(self):
        return self.filter(is_featured=True, is_in_stock=True)

    def in_stock_ordered(self):
        """
        سکه‌های موجود، مرتب‌شده.
        همه فیلدها لود می‌شوند تا کوئری deferred نداشته باشیم.
        """
        return (
            self.filter(is_in_stock=True)
            .order_by('display_order', 'weight_gram')
        )


class ParsianCoin(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name='نام سکه',
    )
    weight_gram = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        verbose_name='وزن (گرم)',
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name='پیشنهادی',
        db_index=True,
    )
    is_in_stock = models.BooleanField(
        default=True,
        verbose_name='موجود در انبار',
        db_index=True,
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name='ترتیب نمایش',
    )

    objects = ParsianCoinManager()

    class Meta:
        ordering = ['display_order', 'weight_gram']
        verbose_name = 'سکه پارسیان'
        verbose_name_plural = 'سکه‌های پارسیان'

    def __str__(self):
        return self.name


    def calc_price(self, gold_price_per_gram: float) -> int:
        """محاسبه قیمت سکه بر اساس وزن، سود ۷٪ و مبلغ ثابت و رند کردن به ۱۰۰ هزار تومان"""
        if gold_price_per_gram <= 0:
            return 0
    
        weight = float(self.weight_gram)
    
        # ۱. تعیین مقدار ثابت بر اساس وزن:
        # - زیر ۳۰۰ سوت (< 0.300): ۴۰۰,۰۰۰ تومان
        # - ۳۰۰ تا زیر ۶۰۰ سوت (شامل ۳۰۰، ۴۰۰ و ۵۰۰ سوت): ۳۰۰,۰۰۰ تومان
        # - ۶۰۰ سوت و بالاتر (>= 0.600): ۰ تومان (فقط همان ۷ درصد اعمال می‌شود)
        if weight < 0.300:
            fixed_amount = 300_000
        elif weight < 0.600:
            fixed_amount = 200_000
        else:
            fixed_amount = 0
    
        # ۲. محاسبه قیمت پایه طلا
        base_gold_price = gold_price_per_gram * weight
    
        # ۳. محاسبه مبلغ خام: (قیمت پایه * ۱.۰۷) + مقدار ثابت
        raw_price = (base_gold_price * 1.07) + fixed_amount
    
        # ۴. رند کردن رو به بالا به نزدیک‌ترین ۱۰۰,۰۰۰ تومان
        final_price = math.ceil(raw_price / 100_000) * 100_000

        return int(final_price)

# ──────────────────────────────────────────────────
#  ۲. کش قیمت طلا (DB-backed)
# ──────────────────────────────────────────────────

class GoldPriceCache(models.Model):
    """
    کش قیمت طلا در دیتابیس.
    فقط یک رکورد (id=1) وجود دارد.
    """
    data = models.JSONField(
        default=dict,
        verbose_name='داده‌های فرمت‌شده',
    )
    raw_data = models.JSONField(
        default=dict,
        verbose_name='داده‌های خام (عددی)',
    )
    last_updated = models.DateTimeField(
        default=timezone.now,
        verbose_name='آخرین بروزرسانی',
    )

    class Meta:
        verbose_name = 'کش قیمت طلا'
        verbose_name_plural = 'کش قیمت‌های طلا'

    def __str__(self):
        return f"کش قیمت طلا — آخرین بروزرسانی: {self.last_updated}"

    @classmethod
    def get_instance(cls):
        """
        دریافت تک‌نمونه کش با Django Cache Layer.
        از کوئری در هر request جلوگیری می‌کند.
        """
        cache_key = 'gold_price_cache_instance'
        instance = cache.get(cache_key)
        if instance is None:
            instance, _ = cls.objects.get_or_create(
                id=1,
                defaults={'data': {}, 'raw_data': {}},
            )
            cache.set(cache_key, instance, 30)  # 30 ثانیه
        return instance

    def save(self, *args, **kwargs):
        """پس از ذخیره، کش Django را هم بروز کن"""
        super().save(*args, **kwargs)
        cache.set('gold_price_cache_instance', self, 30)


# ──────────────────────────────────────────────────
#  ۳. قیمت روزانه طلا
# ──────────────────────────────────────────────────

class GoldDailyPriceManager(models.Manager):
    """منیجر سفارشی برای قیمت روزانه"""

    def latest_price(self):
        """آخرین قیمت ثبت‌شده با کش"""
        cached = cache.get(CACHE_GOLD_PRICE_KEY)
        if cached is not None:
            return cached

        obj = (
            self.order_by('-date')
            .only('date', 'gold_18k_price', 'fetched_at')
            .first()
        )
        if obj:
            cache.set(CACHE_GOLD_PRICE_KEY, obj, CACHE_GOLD_PRICE_TTL)
        return obj

    def get_yesterday(self):
        """قیمت‌های آخرین روز قبل از امروز"""
        today = timezone.now().date()
        return (
            self.filter(date__lt=today)
            .order_by('-date')
            .only(
                'date', 'gold_price_irr', 'gold_18k_price',
                'sikka_imami', 'sikka_tamam', 'sikka_rub', 'sikka_nim',
            )
            .first()
        )

    def save_today_snapshot(self, raw_data: dict):
        """
        ذخیره یا بروزرسانی اسنپ‌شات امروز.
        فقط یک رکورد در روز.
        """
        today = timezone.now().date()
        obj, created = self.update_or_create(
            date=today,
            defaults={
                'gold_price_irr': int(float(raw_data.get('gold_price_irr', 0))),
                'gold_18k_price': int(float(raw_data.get('gold_18k_price', 0))),
                'sikka_imami': int(float(raw_data.get('sikka_imami', 0))),
                'sikka_tamam': int(float(raw_data.get('sikka_tamam', 0))),
                'sikka_rub': int(float(raw_data.get('sikka_rub', 0))),
                'sikka_nim': int(float(raw_data.get('sikka_nim', 0))),
            },
        )
        # کش را بی‌اعتبار کن
        cache.delete(CACHE_GOLD_PRICE_KEY)
        return obj, created


class GoldDailyPrice(models.Model):
    date = models.DateField(
        unique=True,
        verbose_name='تاریخ',
        db_index=True,
    )
    gold_price_irr = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='انس جهانی طلا',
    )
    gold_18k_price = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='طلای ۱۸ عیار',
    )
    sikka_imami = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='سکه امامی',
    )
    sikka_tamam = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='سکه تمام بهار آزادی',
    )
    sikka_rub = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='ربع سکه',
    )
    sikka_nim = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='نیم سکه',
    )
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='زمان دریافت داده',
    )

    objects = GoldDailyPriceManager()

    class Meta:
        ordering = ['-date']
        verbose_name = 'قیمت روزانه طلا'
        verbose_name_plural = 'قیمت‌های روزانه طلا'
        indexes = [
            models.Index(fields=['-date', 'gold_18k_price'], name='idx_date_18k'),
        ]

    def __str__(self):
        return f"{self.date}: طلای ۱۸ عیار {self.gold_18k_price:,} تومان"

    def to_raw_dict(self) -> dict:
        """تبدیل به دیکشنری عددی"""
        return {
            'gold_price_irr': float(self.gold_price_irr),
            'gold_18k_price': float(self.gold_18k_price),
            'sikka_imami': float(self.sikka_imami),
            'sikka_tamam': float(self.sikka_tamam),
            'sikka_rub': float(self.sikka_rub),
            'sikka_nim': float(self.sikka_nim),
        }


# ──────────────────────────────────────────────────
#  ۴. اعتبارسنجی تاریخ جلالی
# ──────────────────────────────────────────────────

def validate_not_future_jdate(value):
    """تاریخ تولد نباید در آینده باشد"""
    if value and value > jdate.today():
        raise ValidationError(
            'تاریخ تولد نمی‌تواند در آینده باشد.',
            code='future_birthday',
        )


# ──────────────────────────────────────────────────
#  ۵. درخواست کاربران لندینگ
# ──────────────────────────────────────────────────

class UserLandingCoine(models.Model):
    full_name = models.CharField(
        max_length=100,
        verbose_name='نام و نام خانوادگی',
        validators=[
            MinLengthValidator(5, message='نام باید حداقل ۵ کاراکتر باشد'),
        ],
    )

    phone_number = models.CharField(
        max_length=14,
        unique=True,
        verbose_name='شماره تماس',
        validators=[
            RegexValidator(
                regex=r'^(?:\+98|0|0098)?9\d{9}$',
                message='شماره موبایل نامعتبر است. مثال: 09123456789',
                code='invalid_phone',
            ),
        ],
        db_index=True,
    )

    # ⚠️ اصلاح: blank=True, default='' برای فرم لندینگ ساده
    address = models.TextField(
        verbose_name='آدرس',
        blank=True,
        default='',
        validators=[
            MinLengthValidator(10, message='آدرس خیلی کوتاه است (حداقل ۱۰ کاراکتر)'),
        ],
    )

    post_code = models.CharField(
        max_length=10,
        verbose_name='کد پستی',
        blank=True,
        default='',
        validators=[
            RegexValidator(
                regex=r'^[1-9]\d{9}$',
                message='کد پستی باید دقیقاً ۱۰ رقم باشد و با ۰ شروع نشود.',
                code='invalid_postcode',
            ),
        ],
    )

    birthday = jmodels.jDateField(
        verbose_name='تاریخ تولد',
        null=True,
        blank=True,
        validators=[validate_not_future_jdate],
    )

    create_date = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ثبت درخواست',
        editable=False,
    )

    is_call = models.BooleanField(
        default=False,
        verbose_name='تماس گرفته شد؟',
        db_index=True,
    )

    class Meta:
        verbose_name = 'درخواست کاربر'
        verbose_name_plural = 'درخواست‌های کاربران'
        ordering = ['-create_date']
        indexes = [
            models.Index(fields=['is_call', '-create_date'], name='idx_call_created'),
        ]

    def __str__(self):
        return f"{self.full_name} — {self.phone_number}"

    def clean(self):
        """اعتبارسنجی سطح مدل"""
        super().clean()
        # اگر آدرس پر شده، validator اعمال می‌شود
        # اگر خالی است، چون blank=True مشکلی نیست
        if self.address and len(self.address.strip()) < 10:
            raise ValidationError({
                'address': 'آدرس خیلی کوتاه است (حداقل ۱۰ کاراکتر).',
            })
        
# ARZ 
class MarketPriceHistory(models.Model):
    """ذخیره قیمت روزانه برای مقایسه با روز قبل."""
    symbol = models.CharField(max_length=20, db_index=True)
    date = models.DateField(db_index=True)
    sell_price = models.DecimalField(max_digits=20, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('symbol', 'date')
        ordering = ['-date']
        verbose_name = "تاریخچه قیمت بازار"
        verbose_name_plural = "تاریخچه قیمت‌های بازار"

    def __str__(self):
        return f"{self.symbol} - {self.date} - {self.sell_price}"



# Get Email User
class Email(models.Model):
    email = models.EmailField(
        max_length=100,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9][a-zA-Z0-9._]*[a-zA-Z0-9]@gmail\.com$',
                message='فقط ایمیل‌های Gmail معتبر هستند.'
            )
        ],
        verbose_name="ایمیل",
        unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")

    class Meta:
        verbose_name = "ایمیل"
        verbose_name_plural = "ایمیل‌ها"

    def __str__(self):
        return self.email
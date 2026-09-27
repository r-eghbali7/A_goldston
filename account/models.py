from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.core.validators import RegexValidator
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import secrets


# =========================
# Constants
# =========================
LOCKOUT_DURATION = getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 5)
MAX_FAILED_ATTEMPTS = getattr(settings, "ACCOUNT_MAX_FAILED_ATTEMPTS", 5)
OTP_EXPIRY_SECONDS = getattr(settings, "OTP_EXPIRY_SECONDS", 90)
OTP_MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 3)


# =========================
# User Manager
# =========================
class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, full_name, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("شماره موبایل الزامی است")
        if not full_name:
            raise ValueError("نام و نام خانوادگی الزامی است")

        extra_fields.setdefault("is_active", False)
        user = self.model(
            phone_number=phone_number,
            full_name=full_name,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, full_name, password, **extra_fields):
        extra_fields.update(
            {"is_staff": True, "is_superuser": True, "is_active": True}
        )
        return self.create_user(phone_number, full_name, password, **extra_fields)


# =========================
# Custom User Model
# =========================
class CustomUserModel(AbstractBaseUser, PermissionsMixin):
    phone_regex = RegexValidator(
        regex=r"^09\d{9}$",
        message="شماره موبایل باید با 09 شروع شود و 11 رقم باشد.",
    )

    full_name = models.CharField(
        max_length=255,
        verbose_name="نام و نام خانوادگی",
    )
    phone_number = models.CharField(
        max_length=11,
        unique=True,
        validators=[phone_regex],
        verbose_name="شماره موبایل",
        db_index=True,
    )
    image_author = models.ImageField(
        upload_to="images/author/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="تصویر نویسنده",
    )
    address = models.TextField(
        blank=True,
        default="",
        verbose_name="آدرس",
    )

    is_active = models.BooleanField(default=False, verbose_name="فعال شده")
    is_staff = models.BooleanField(default=False, verbose_name="دسترسی ادمین")
    date_joined = models.DateTimeField(default=timezone.now, verbose_name="تاریخ عضویت")

    # Security fields
    failed_login_attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="تلاش‌های ناموفق",
    )
    last_login_attempt = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="آخرین تلاش ورود",
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"
        indexes = [
            models.Index(fields=["is_active", "phone_number"]),
        ]

    def __str__(self):
        return self.phone_number

    # ---------- Security ----------
    def is_locked_out(self):
        if (
            self.failed_login_attempts >= MAX_FAILED_ATTEMPTS
            and self.last_login_attempt
        ):
            lockout_until = self.last_login_attempt + timedelta(
                minutes=LOCKOUT_DURATION
            )
            if timezone.now() < lockout_until:
                return True
            # اگر مدت قفل تمام شده، خودکار ریست کن
            self.reset_failed_attempts()
        return False

    def register_failed_attempt(self):
        self.failed_login_attempts += 1
        self.last_login_attempt = timezone.now()
        self.save(update_fields=["failed_login_attempts", "last_login_attempt"])

    def reset_failed_attempts(self):
        if self.failed_login_attempts != 0:
            self.failed_login_attempts = 0
            self.last_login_attempt = None
            self.save(
                update_fields=["failed_login_attempts", "last_login_attempt"]
            )


# =========================
# OTP Model
# =========================
class OTP(models.Model):
    user = models.ForeignKey(
        CustomUserModel,
        on_delete=models.CASCADE,
        related_name="otp_codes",
        verbose_name="کاربر",
    )
    code = models.CharField(
        max_length=6,
        verbose_name="کد تایید",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد",
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="تعداد تلاش",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "کد تایید"
        verbose_name_plural = "کدهای تایید"

    def __str__(self):
        return f"OTP - {self.user.phone_number}"

    # ---------- OTP Logic ----------
    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(
            seconds=OTP_EXPIRY_SECONDS
        )

    def increase_attempts(self):
        self.attempts = models.F("attempts") + 1
        self.save(update_fields=["attempts"])
        self.refresh_from_db(fields=["attempts"])

    def max_attempts_reached(self):
        return self.attempts >= OTP_MAX_ATTEMPTS

    @staticmethod
    def generate_code():
        return f"{secrets.randbelow(10**6):06d}"

    @classmethod
    def cleanup_expired(cls):
        """حذف OTPهای منقضی شده - مناسب برای Celery beat"""
        cutoff = timezone.now() - timedelta(seconds=OTP_EXPIRY_SECONDS)
        deleted_count, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return deleted_count

    @classmethod
    def create_for_user(cls, user):
        """ایجاد OTP جدید و حذف قدیمی‌ها در یک عملیات"""
        cls.objects.filter(user=user).delete()
        code = cls.generate_code()
        return cls.objects.create(user=user, code=code), code

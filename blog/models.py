from django.conf import settings
from django.db import models
from django.urls import reverse
from django.core.validators import (
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
)
from django.utils.functional import cached_property
import jdatetime
from taggit.managers import TaggableManager
from ckeditor.fields import RichTextField
from django_jalali.db import models as jmodels


# -----------------------------
# Custom manager for published posts
# -----------------------------
class PublishedManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status=Post.STATUS.PUBLISHED)
        )


# -----------------------------
# Category
# -----------------------------
class Category(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name="نام دسته‌بندی",
        db_index=True,
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name="اسلاگ",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "دسته بندی"
        verbose_name_plural = "دسته بندی ها"
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("blog:post_list_by_category", args=[self.slug])


# -----------------------------
# Post
# -----------------------------
class Post(models.Model):
    class STATUS(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PUBLISHED = "published", "منتشر شده"

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name="دسته بندی",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts",
        verbose_name="نویسنده",
    )
    title = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="عنوان",
    )
    text = RichTextField(verbose_name="متن")
    description = models.TextField(
        max_length=500,
        verbose_name="توضیحات",
    )
    image = models.ImageField(
        upload_to="images/post/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="تصویر",
    )
    voice = models.FileField(
        upload_to="voice/%Y/%m/",
        verbose_name="ویس مقاله",
        blank=True,
        null=True,
    )
    read_time = models.PositiveSmallIntegerField(
        verbose_name="مدت زمان مطالعه (دقیقه)",
        validators=[MinValueValidator(1)],
    )
    created = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
    )
    update_date = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ بروزرسانی",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS.choices,
        default=STATUS.DRAFT,
        verbose_name="وضعیت انتشار",
        db_index=True,
    )
    slug = models.SlugField(
        max_length=250,
        unique=True,
        verbose_name="آدرس",
    )
    tags = TaggableManager(blank=True, verbose_name="تگ")

    # ---- Managers ----
    objects = models.Manager()
    published = PublishedManager()

    class Meta:
        ordering = ["-created"]
        verbose_name = "پست"
        verbose_name_plural = "پست ها"
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["status", "-created"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:post_detail", args=[self.slug])

    def get_image_url(self):
        """Return image URL or empty string"""
        if self.image:
            return self.image.url
        return ""

    def save(self, *args, **kwargs):
        self.updated = jdatetime.datetime.now()
        if not self.pk:
            self.created = jdatetime.datetime.now()
        super().save(*args, **kwargs)

    def get_iso_datetime(self):
        """
        تبدیل تاریخ شمسی به فرمت ISO 8601 برای JSON-LD
        خروجی: '2025-10-22T08:12:47+00:00'
        """
        if not self.created:
            return None
        
        # تبدیل jdatetime به datetime میلادی
        gregorian_datetime = self.created.togregorian()
        
        # اضافه کردن timezone (تهران - UTC+3:30)
        # یا اگر می‌خواهید UTC باشد:
        return gregorian_datetime.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    
    def get_iso_update_date(self):
        if not self.update_date:
            return None
        
        gregorian_datetime = self.update_date.togregorian()
        return gregorian_datetime.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    
    class Meta:
        ordering = ['-created']

# -----------------------------
# Abstract Comment Base
# -----------------------------
class BaseCommentFields(models.Model):
    NAME_VALIDATORS = [
        MinLengthValidator(2, "نام باید حداقل ۲ کاراکتر باشد."),
        RegexValidator(
            regex=r"^[a-zA-Z\s\u0600-\u06FF\u0750-\u077F]+$",
            message="نام فقط می‌تواند شامل حروف و فاصله باشد.",
        ),
    ]
    BODY_VALIDATORS = [
        MinLengthValidator(5, "نظر باید حداقل ۵ کاراکتر باشد."),
        RegexValidator(
            regex=r"^[a-zA-Z0-9\s\u0600-\u06FF\u0750-\u077F.,!?()؟؛،\-]+$",
            message="نظر شامل کاراکترهای غیرمجاز است.",
        ),
    ]

    name = models.CharField(
        max_length=80,
        validators=NAME_VALIDATORS,
        verbose_name="نام",
    )
    body = models.TextField(
        max_length=2000,
        validators=BODY_VALIDATORS,
        verbose_name="متن نظر",
    )
    created = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
    )
    updated = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name="تاریخ بروزرسانی",
    )
    active = models.BooleanField(
        default=False,
        verbose_name="فعال",
        db_index=True,
    )

    class Meta:
        abstract = True


# -----------------------------
# Comment
# -----------------------------
class Comment(BaseCommentFields):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="پست",
    )

    class Meta:
        ordering = ["-created"]
        verbose_name = "کامنت"
        verbose_name_plural = "کامنت ها"
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["post", "active", "-created"]),
        ]

    def __str__(self):
        return f"{self.name}: {self.body[:30]}"


# -----------------------------
# Reply Comment
# -----------------------------
class ReplyComment(BaseCommentFields):
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="replies",
        verbose_name="کامنت",
    )

    class Meta:
        ordering = ["-created"]
        verbose_name = "پاسخ کامنت"
        verbose_name_plural = "پاسخ کامنت ها"
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["comment", "active"]),
        ]

    def __str__(self):
        return f"پاسخ {self.name} به {self.comment.name}"


# -----------------------------
# Short Link
# -----------------------------
class ShortLink(models.Model):
    original_url = models.ForeignKey(
        Post,
        related_name="short_links",
        on_delete=models.CASCADE,
        verbose_name="پست",
    )
    short_code = models.SlugField(
        unique=True,
        max_length=50,
        db_index=True,
        verbose_name="کد کوتاه",
    )

    class Meta:
        verbose_name = "لینک کوتاه"
        verbose_name_plural = "لینک کوتاه ها"

    def __str__(self):
        return f"{self.short_code} → {self.original_url.title}"

    def get_redirect_url(self):
        return self.original_url.get_absolute_url()


# -----------------------------
# FAQ (Frequently Asked Questions)
# -----------------------------
class FAQ(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="faqs",
        verbose_name="پست مربوطه",
        blank=True,
        null=True,
        help_text="اگر این سوال مربوط به پست خاصی است، آن را انتخاب کنید. در غیر این صورت خالی بگذارید تا به عنوان سوال عمومی در نظر گرفته شود."
    )
    question = models.CharField(
        max_length=500,
        verbose_name="پرسش",
    )
    answer = models.TextField(
        verbose_name="پاسخ",
    )
    # اگر می‌خواهید پاسخ‌ها قابلیت استایل‌دهی داشته باشند، می‌توانید به جای TextField از RichTextField استفاده کنید:
    # answer = RichTextField(verbose_name="پاسخ")
    
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="ترتیب نمایش",
        help_text="برای مرتب‌سازی سوالات. عدد کوچکتر بالاتر نمایش داده می‌شود.",
    )
    active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        db_index=True,
    )
    created = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
    )
    updated = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name="تاریخ بروزرسانی",
    )

    class Meta:
        ordering = ["order", "-created"]
        verbose_name = "سوال متداول"
        verbose_name_plural = "سوالات متداول"
        indexes = [
            models.Index(fields=["active", "order"]),
            models.Index(fields=["post", "active"]),
        ]

    def __str__(self):
        return self.question

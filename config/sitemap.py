from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from blog.models import Post, Category

class StaticViewSitemap(Sitemap):
    """
    سایت‌مپ برای صفحات ثابت سایت (مانند صفحه اصلی، درباره ما، تماس با ما)
    """
    priority = 1.0
    changefreq = 'daily'

    def items(self):
        # نام‌های URL مربوط به صفحات اصلی خود را اینجا قرار دهید
        # به عنوان مثال:
        return ('home:index',)

    def location(self, item):
        return reverse(item)


class PostSitemap(Sitemap):
    """
    سایت‌مپ برای مقالات وبلاگ
    """
    changefreq = "hourly"
    priority = 0.8

    def items(self):
        # استفاده از Custom Manager برای دریافت فقط مقالات منتشر شده
        return Post.published.all()

    def lastmod(self, obj):
        # موتورهای جستجو تاریخ میلادی (ISO 8601) را می‌پذیرند.
        # چون از django-jalali استفاده کرده‌اید، باید آن را به میلادی تبدیل کنیم.
        if hasattr(obj.update_date, 'togregorian'):
            return obj.update_date.togregorian()
        return obj.update_date

    # متد location نیاز نیست، زیرا جنگو به طور خودکار از get_absolute_url مدل استفاده می‌کند.


class CategorySitemap(Sitemap):
    """
    سایت‌مپ برای دسته‌بندی‌های وبلاگ
    """
    changefreq = "hourly"
    priority = 0.6

    def items(self):
        # در صورت نیاز می‌توانید فقط دسته‌بندی‌هایی که دارای پست هستند را فیلتر کنید
        return Category.objects.all()

    # متد location در اینجا هم نیاز نیست (از get_absolute_url مدل استفاده می‌شود)

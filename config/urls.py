from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from debug_toolbar.toolbar import debug_toolbar_urls
from django.contrib.sitemaps.views import sitemap
from config.sitemap import PostSitemap, CategorySitemap, StaticViewSitemap
from django.views.generic import TemplateView


# دیکشنری سایت‌مپ‌ها
sitemaps = {
    'static': StaticViewSitemap,
    'posts': PostSitemap,
    'categories': CategorySitemap,
}


urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("home.urls")),
    path("account/", include("account.urls")),
    path("coineshop/", include("coineshop.urls")),
    path("blog/", include("blog.urls")),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += debug_toolbar_urls()
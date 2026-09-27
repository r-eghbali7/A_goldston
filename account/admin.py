from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUserModel, OTP


# =========================
# Custom User Admin
# =========================
@admin.register(CustomUserModel)
class CustomUserAdmin(UserAdmin):
    model = CustomUserModel

    list_display = (
        "phone_number",
        "full_name",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )

    search_fields = (
        "phone_number",
        "full_name",
    )

    ordering = ("-date_joined",)
    list_per_page = 25

    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        (
            _("اطلاعات شخصی"),
            {"fields": ("full_name", "image_author", "address")},
        ),
        (
            _("دسترسی‌ها"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("امنیت"),
            {
                "fields": ("failed_login_attempts", "last_login_attempt"),
                "classes": ("collapse",),
            },
        ),
        (_("تاریخ‌ها"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone_number",
                    "full_name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    readonly_fields = (
        "failed_login_attempts",
        "last_login_attempt",
        "last_login",
        "date_joined",
    )

    filter_horizontal = (
        "groups",
        "user_permissions",
    )


# =========================
# OTP Admin
# =========================
@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "code",
        "created_at",
        "attempts",
        "is_expired_display",
    )

    list_filter = ("created_at",)

    search_fields = (
        "user__phone_number",
        "user__full_name",
    )

    readonly_fields = (
        "code",
        "created_at",
        "attempts",
    )

    list_select_related = ("user",)
    list_per_page = 30

    # ⬇ جلوگیری از ویرایش/ایجاد OTP از ادمین
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(boolean=True, description="منقضی شده؟")
    def is_expired_display(self, obj):
        return obj.is_expired()

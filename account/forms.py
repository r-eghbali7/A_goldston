import re

from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator

from .models import CustomUserModel


# =========================
# Reusable Validators
# =========================
PHONE_REGEX = re.compile(r"^09\d{9}$")

PASSWORD_VALIDATORS = [
    MinLengthValidator(8, "رمز عبور باید حداقل ۸ کاراکتر باشد."),
    RegexValidator(
        regex=r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&]).+$",
        message="رمز عبور باید شامل حرف، عدد و کاراکتر خاص باشد.",
    ),
]


def clean_phone(value):
    """Shared phone validation logic."""
    phone = value.strip()
    if not PHONE_REGEX.match(phone):
        raise ValidationError("شماره موبایل معتبر نیست.")
    return phone


# =========================
# Honeypot Mixin (Anti-Bot)
# =========================
class HoneypotMixin(forms.Form):
    """
    فیلد مخفی ضد ربات.
    اگر ربات این فیلد را پر کند، فرم رد می‌شود.
    """
    website_url = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    def clean_website_url(self):
        value = self.cleaned_data.get("website_url", "")
        if value:
            raise ValidationError("درخواست نامعتبر.")
        return value


# =========================
# SIGN UP FORM
# =========================
class SignUpForm(HoneypotMixin, forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "رمز عبور", "autocomplete": "new-password"}
        ),
        validators=PASSWORD_VALIDATORS,
    )

    class Meta:
        model = CustomUserModel
        fields = ["full_name", "phone_number", "password"]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"placeholder": "نام و نام خانوادگی", "autocomplete": "name"}
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "placeholder": "شماره موبایل",
                    "inputmode": "numeric",
                    "autocomplete": "tel",
                    "maxlength": "11",
                }
            ),
        }

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()
        if len(full_name) > 255:
            raise ValidationError("نام بیش از حد طولانی است.")
        if len(full_name.split()) < 2:
            raise ValidationError("نام و نام خانوادگی را کامل وارد کنید.")
        # جلوگیری از کاراکترهای خاص در نام
        if re.search(r"[<>\"';(){}]", full_name):
            raise ValidationError("نام شامل کاراکترهای غیرمجاز است.")
        return full_name

    def clean_phone_number(self):
        phone = clean_phone(self.cleaned_data["phone_number"])

        # استفاده از exists() به جای first() — فقط یک COUNT کوئری
        if CustomUserModel.objects.filter(
            phone_number=phone, is_active=True
        ).exists():
            raise ValidationError("این شماره قبلاً ثبت شده است.")

        return phone


# =========================
# LOGIN FORM
# =========================
class CustomLoginForm(HoneypotMixin, forms.Form):
    phone_number = forms.CharField(
        label="شماره موبایل",
        max_length=11,
        widget=forms.TextInput(
            attrs={
                "placeholder": "شماره موبایل",
                "inputmode": "numeric",
                "autocomplete": "tel",
            }
        ),
    )

    password = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput(
            attrs={"placeholder": "رمز عبور", "autocomplete": "current-password"}
        ),
    )

    def clean_phone_number(self):
        return clean_phone(self.cleaned_data.get("phone_number", ""))


# =========================
# OTP FORM
# =========================
class OTPForm(forms.Form):
    otp_code = forms.CharField(
        label="کد تایید",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "placeholder": "کد تایید ۶ رقمی",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": r"\d{6}",
                "maxlength": "6",
            }
        ),
        validators=[RegexValidator(r"^\d{6}$", "کد تایید باید ۶ رقم باشد.")],
    )

    def clean_otp_code(self):
        code = self.cleaned_data.get("otp_code", "").strip()
        if not code.isdigit() or len(code) != 6:
            raise ValidationError("کد تایید فقط باید ۶ رقم عددی باشد.")
        return code


# =========================
# Phone Number Form (Password Reset)
# =========================
class PhoneNumberForm(forms.Form):
    phone_number = forms.CharField(
        label="شماره موبایل",
        max_length=11,
        widget=forms.TextInput(
            attrs={
                "placeholder": "شماره موبایل",
                "inputmode": "numeric",
                "autocomplete": "tel",
            }
        ),
    )

    def clean_phone_number(self):
        return clean_phone(self.cleaned_data.get("phone_number", ""))


# =========================
# USER PROFILE FORM
# =========================
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUserModel
        fields = ["full_name", "phone_number", "address"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "readonly": "readonly"}
            ),
            "address": forms.Textarea(
                attrs={"rows": 2, "class": "form-control"}
            ),
        }

    def clean_phone_number(self):
        # شماره موبایل قابل تغییر نیست
        return self.instance.phone_number


# =========================
# CHANGE PASSWORD FORM
# =========================
class ChangePasswordForm(PasswordChangeForm):
    pass


# =========================
# RESET PASSWORD CONFIRM FORM
# =========================
class ResetPasswordConfirmForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="رمز عبور جدید",
        validators=PASSWORD_VALIDATORS,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "رمز عبور جدید",
                "autocomplete": "new-password",
                "class": "form-input",
            }
        ),
    )

    new_password2 = forms.CharField(
        label="تکرار رمز عبور جدید",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "تکرار رمز عبور جدید",
                "autocomplete": "new-password",
                "class": "form-input",
            }
        ),
    )

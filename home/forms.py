# home/forms.py  ← ✅ نه froms.py!

from django import forms
from django.utils.html import strip_tags
from django.core.validators import RegexValidator
from .models import Email, UserLandingCoine


class SimpleUserLandingForm(forms.ModelForm):
    """فرم ساده لندینگ — فقط نام و شماره موبایل"""

    # Honeypot field ضد ربات
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label='',
    )

    class Meta:
        model = UserLandingCoine
        fields = ['full_name', 'phone_number']

        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام و نام خانوادگی',
                'autocomplete': 'name',
                'dir': 'rtl',
                'maxlength': '100',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control ltr-input',
                'placeholder': '09123456789',
                'autocomplete': 'tel',
                'dir': 'ltr',
                'inputmode': 'tel',
                'maxlength': '14',
            }),
        }

        labels = {
            'full_name': 'نام و نام خانوادگی',
            'phone_number': 'شماره موبایل',
        }

    def clean_website(self):
        """Honeypot: اگر پر شده باشد، ربات است"""
        value = self.cleaned_data.get('website', '')
        if value:
            raise forms.ValidationError('ربات شناسایی شد.')
        return value

    def clean_full_name(self):
        """سانتیزه و اعتبارسنجی نام"""
        name = self.cleaned_data.get('full_name', '').strip()
        name = strip_tags(name)

        if len(name) < 5:
            raise forms.ValidationError('نام باید حداقل ۵ کاراکتر باشد.')

        # فقط حروف فارسی، عربی، انگلیسی و فاصله
        import re
        if not re.match(r'^[\u0600-\u06FF\u0750-\u077Fa-zA-Z\s]+$', name):
            raise forms.ValidationError(
                'نام فقط می‌تواند شامل حروف فارسی، عربی یا انگلیسی باشد.'
            )

        return name

    def clean_phone_number(self):
        """تمیز کردن و استانداردسازی شماره موبایل"""
        phone = self.cleaned_data.get('phone_number', '').strip()

        # حذف کاراکترهای غیرمجاز
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')

        # تبدیل به فرمت استاندارد 09xxxxxxxxx
        if phone.startswith('+98'):
            phone = '0' + phone[3:]
        elif phone.startswith('0098'):
            phone = '0' + phone[4:]

        if not phone.startswith('09') or len(phone) != 11:
            raise forms.ValidationError(
                'شماره موبایل باید ۱۱ رقمی باشد و با ۰۹ شروع شود.'
            )

        # بررسی تکراری بودن
        if UserLandingCoine.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError(
                'این شماره قبلاً ثبت شده است.'
            )

        return phone


# Form Get Email
class EmailSubscribeForm(forms.ModelForm):
    class Meta:
        model = Email
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': 'example@gmail.com',
                'dir': 'ltr',
            })
        }
        error_messages = {
            'email': {
                'unique': 'این ایمیل قبلاً ثبت شده است.',
            }
        }


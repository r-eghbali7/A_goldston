import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

from .models import Comment, ReplyComment


class HoneypotMixin(forms.Form):
    """فیلد مخفی ضد ربات - اگر پر شود، فرم رد می‌شود."""
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError("درخواست نامعتبر.")
        return ""


class CommentForm(HoneypotMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["name", "body"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "نام شما",
                    "maxlength": "80",
                    "class": "form-control",
                    "autocomplete": "name",
                }
            ),
            "body": forms.Textarea(
                attrs={
                    "placeholder": "نظر شما...",
                    "rows": 4,
                    "maxlength": "2000",
                    "class": "form-control",
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        # حذف تگ‌های HTML
        name = strip_tags(name)
        if len(name) < 2:
            raise ValidationError("نام باید حداقل ۲ کاراکتر باشد.")
        if len(name) > 80:
            raise ValidationError("نام بیش از حد طولانی است.")
        return name

    def clean_body(self):
        body = self.cleaned_data.get("body", "").strip()
        # حذف تگ‌های HTML
        body = strip_tags(body)
        if len(body) < 5:
            raise ValidationError("نظر باید حداقل ۵ کاراکتر باشد.")
        if len(body) > 2000:
            raise ValidationError("نظر بیش از حد طولانی است.")
        # بررسی لینک‌های مشکوک
        url_pattern = re.compile(r"https?://|www\.", re.IGNORECASE)
        if url_pattern.search(body):
            raise ValidationError("درج لینک در نظرات مجاز نیست.")
        return body


class ReplyCommentForm(HoneypotMixin, forms.ModelForm):
    """فرم جداگانه برای پاسخ - برای استفاده آینده"""
    class Meta:
        model = ReplyComment
        fields = ["name", "body"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "نام شما",
                    "maxlength": "80",
                    "class": "form-control",
                }
            ),
            "body": forms.Textarea(
                attrs={
                    "placeholder": "پاسخ شما...",
                    "rows": 3,
                    "maxlength": "2000",
                    "class": "form-control",
                }
            ),
        }

    def clean_name(self):
        name = strip_tags(self.cleaned_data.get("name", "").strip())
        if len(name) < 2:
            raise ValidationError("نام باید حداقل ۲ کاراکتر باشد.")
        return name

    def clean_body(self):
        body = strip_tags(self.cleaned_data.get("body", "").strip())
        if len(body) < 5:
            raise ValidationError("پاسخ باید حداقل ۵ کاراکتر باشد.")
        url_pattern = re.compile(r"https?://|www\.", re.IGNORECASE)
        if url_pattern.search(body):
            raise ValidationError("درج لینک در پاسخ‌ها مجاز نیست.")
        return body

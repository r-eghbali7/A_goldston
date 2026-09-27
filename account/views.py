import hmac
import logging
import secrets
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import (
    CustomLoginForm,
    OTPForm,
    PhoneNumberForm,
    ResetPasswordConfirmForm,
    SignUpForm,
)
from .models import OTP, CustomUserModel

logger = logging.getLogger(__name__)

OTP_EXPIRY_SECONDS = getattr(settings, "OTP_EXPIRY_SECONDS", 90)
OTP_RESEND_COOLDOWN = getattr(settings, "OTP_RESEND_COOLDOWN", 60)


# =========================
# Rate Limiting Decorator
# =========================
def session_ratelimit(key, max_attempts, period_seconds, error_message=None):
    """
    ساده‌ترین شکل rate limit بر پایه session.
    برای پروداکشن از django-ratelimit یا redis استفاده کنید.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            now = timezone.now()
            attempts_key = f"rl_{key}_attempts"
            window_key = f"rl_{key}_window"

            window_start = request.session.get(window_key)
            attempts = request.session.get(attempts_key, 0)

            if window_start:
                window_start = timezone.datetime.fromisoformat(window_start)
                if now - window_start > timedelta(seconds=period_seconds):
                    # Reset window
                    request.session[attempts_key] = 0
                    request.session[window_key] = now.isoformat()
                    attempts = 0

            if attempts >= max_attempts:
                msg = error_message or "تعداد درخواست‌ها بیش از حد مجاز. لطفاً کمی صبر کنید."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"error": msg}, status=429)
                messages.error(request, msg)
                return redirect(request.path)

            # Increment
            request.session[attempts_key] = attempts + 1
            if not window_start:
                request.session[window_key] = now.isoformat()

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# =========================
# Helper Functions
# =========================
def _mask_phone(phone):
    """نمایش شماره به صورت 0912***4567"""
    if phone and len(phone) == 11:
        return f"{phone[:4]}***{phone[-4:]}"
    return "***"


def _generate_otp():
    """تولید OTP ۶ رقمی امن"""
    return f"{secrets.randbelow(10 ** 6):06d}"


def _send_otp(phone_number, code):
    """ارسال OTP با مدیریت خطا"""
    from utils import send_otp_to_phone

    try:
        send_otp_to_phone(phone_number, code)
        return True
    except Exception:
        logger.exception("OTP send failed for phone: %s***", phone_number[:4])
        return False


def _clear_otp_session(request, keys=None):
    """پاک کردن کلیدهای OTP از session"""
    default_keys = [
        "temp_user_data",
        "otp_code",
        "otp_time",
        "otp_attempts",
    ]
    for k in keys or default_keys:
        request.session.pop(k, None)


def _secure_compare(a, b):
    """مقایسه امن OTP (ضد timing attack)"""
    return hmac.compare_digest(str(a), str(b))


# =========================
# LOGIN
# =========================
@never_cache
@require_http_methods(["GET", "POST"])
@session_ratelimit("login", max_attempts=10, period_seconds=300)
def custom_login(request):
    if request.user.is_authenticated:
        return redirect("home:index")

    if request.method == "POST":
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone_number"]
            password = form.cleaned_data["password"]

            # authenticate handles failed attempts internally
            user = authenticate(
                request, phone_number=phone, password=password
            )

            if user is None:
                messages.error(request, "شماره موبایل یا رمز عبور نادرست است.")
                return render(
                    request, "registration/login.html", {"form": form}
                )

            login(request, user)
            # Redirect to 'next' if provided, else home
            next_url = request.GET.get("next", "home:index")
            return redirect(next_url)
    else:
        form = CustomLoginForm()

    return render(request, "registration/login.html", {"form": form})


# ==================================
# Register View
# ==================================
@never_cache
@require_http_methods(["GET", "POST"])
@session_ratelimit("register", max_attempts=5, period_seconds=600)
def register(request):
    if request.user.is_authenticated:
        return redirect("home:index")

    form = SignUpForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        full_name = form.cleaned_data["full_name"]
        phone_number = form.cleaned_data["phone_number"]
        password = form.cleaned_data["password"]

        # ذخیره موقت اطلاعات کاربر در session
        request.session["temp_user_data"] = {
            "full_name": full_name,
            "phone_number": phone_number,
            "password": password,
        }

        otp_code = _generate_otp()
        request.session["otp_code"] = otp_code
        request.session["otp_time"] = timezone.now().isoformat()
        request.session["otp_attempts"] = 0

        if _send_otp(phone_number, otp_code):
            messages.success(request, "کد تایید ارسال شد.")
            return redirect("accounts:otp_verify")
        else:
            messages.error(request, "خطا در ارسال کد تایید. لطفاً دوباره تلاش کنید.")

    return render(request, "registration/register.html", {"form": form})


# ==================================
# OTP Verification View
# ==================================
@never_cache
@require_http_methods(["GET", "POST"])
def otp_verification(request):
    required_keys = ["temp_user_data", "otp_code", "otp_time"]

    # Validate session
    if not all(k in request.session for k in required_keys):
        messages.error(request, "لطفاً ابتدا ثبت‌نام کنید.")
        return redirect("accounts:register")

    # Check OTP expiration
    try:
        otp_time = timezone.datetime.fromisoformat(request.session["otp_time"])
    except (ValueError, TypeError):
        _clear_otp_session(request)
        return redirect("accounts:register")

    if timezone.now() > otp_time + timedelta(seconds=OTP_EXPIRY_SECONDS):
        messages.error(request, "کد تایید منقضی شده است. دوباره ثبت‌نام کنید.")
        _clear_otp_session(request)
        return redirect("accounts:register")

    phone = request.session["temp_user_data"].get("phone_number", "")
    phone_masked = _mask_phone(phone)

    if request.method == "POST":
        form = OTPForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data["otp_code"]
            stored_otp = request.session["otp_code"]
            attempts = request.session.get("otp_attempts", 0)

            if attempts >= 3:
                messages.error(
                    request,
                    "تعداد تلاش‌ها بیش از حد مجاز. دوباره ثبت‌نام کنید.",
                )
                _clear_otp_session(request)
                return redirect("accounts:register")

            if not _secure_compare(entered_otp, stored_otp):
                request.session["otp_attempts"] = attempts + 1
                remaining = 3 - (attempts + 1)
                messages.error(
                    request,
                    f"کد تایید اشتباه است. {remaining} تلاش باقی‌مانده.",
                )
                return render(
                    request,
                    "registration/otp_verification.html",
                    {"form": form, "phone_masked": phone_masked},
                )

            # ✅ OTP correct → Create user atomically
            user_data = request.session["temp_user_data"]

            with transaction.atomic():
                # حذف کاربر غیرفعال قبلی اگر وجود دارد
                CustomUserModel.objects.filter(
                    phone_number=user_data["phone_number"],
                    is_active=False,
                ).delete()

                user = CustomUserModel(
                    full_name=user_data["full_name"],
                    phone_number=user_data["phone_number"],
                    is_active=True,
                )
                user.set_password(user_data["password"])
                user.save()

            # Clear session
            _clear_otp_session(request)

            # Auto-login
            login(
                request,
                user,
                backend="accounts.authentication.PhoneNumberBackend",
            )
            messages.success(request, "ثبت‌نام با موفقیت انجام شد.")
            return redirect("home:index")
    else:
        form = OTPForm()

    return render(
        request,
        "registration/otp_verification.html",
        {"form": form, "phone_masked": phone_masked},
    )


# =============================
# OTP Resend (AJAX)
# =============================
@require_POST
@session_ratelimit("otp_resend", max_attempts=3, period_seconds=300)
def otp_resend(request):
    """ارسال مجدد OTP با cooldown"""
    if "temp_user_data" not in request.session:
        return JsonResponse({"error": "ابتدا ثبت‌نام کنید."}, status=400)

    # Cooldown check
    last_otp_time = request.session.get("otp_time")
    if last_otp_time:
        try:
            last_time = timezone.datetime.fromisoformat(last_otp_time)
            elapsed = (timezone.now() - last_time).total_seconds()
            if elapsed < OTP_RESEND_COOLDOWN:
                remaining = int(OTP_RESEND_COOLDOWN - elapsed)
                return JsonResponse(
                    {"error": f"لطفاً {remaining} ثانیه صبر کنید."},
                    status=429,
                )
        except (ValueError, TypeError):
            pass

    # Generate new OTP
    otp_code = _generate_otp()
    request.session["otp_code"] = otp_code
    request.session["otp_time"] = timezone.now().isoformat()
    request.session["otp_attempts"] = 0

    phone_number = request.session["temp_user_data"]["phone_number"]

    if _send_otp(phone_number, otp_code):
        return JsonResponse({"message": "کد تایید جدید ارسال شد."})
    else:
        return JsonResponse({"error": "خطا در ارسال کد."}, status=500)


# =========================
# LOGOUT
# =========================
# @require_POST
def logout_view(request):
    """خروج فقط با POST (امنیت CSRF)"""
    logout(request)
    messages.success(request, "با موفقیت خارج شدید.")
    return redirect("home:index")


# =========================
# Password Reset - Step 1: Phone
# =========================
@never_cache
@require_http_methods(["GET", "POST"])
@session_ratelimit("pw_reset", max_attempts=5, period_seconds=600)
def password_reset_phone(request):
    form = PhoneNumberForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone_number"]

        user = CustomUserModel.objects.filter(
            phone_number=phone, is_active=True
        ).first()

        if not user:
            # ⬇ پیام عمومی برای جلوگیری از user enumeration
            messages.info(
                request,
                "اگر حسابی با این شماره وجود داشته باشد، کد تایید ارسال می‌شود.",
            )
            return redirect("accounts:password_reset_phone")

        # ایجاد OTP با حذف قبلی‌ها
        _otp, code = OTP.create_for_user(user)

        if _send_otp(user.phone_number, code):
            request.session["reset_user_id"] = user.id
            return redirect("accounts:password_reset_otp")
        else:
            messages.error(request, "خطا در ارسال کد. دوباره تلاش کنید.")

    return render(request, "registration/password_reset_phone.html", {"form": form})


# =========================
# Password Reset - Step 2: OTP Verify
# =========================
@never_cache
@require_http_methods(["GET", "POST"])
def password_reset_otp(request):
    user_id = request.session.get("reset_user_id")
    if not user_id:
        return redirect("accounts:password_reset_phone")

    try:
        user = CustomUserModel.objects.get(id=user_id, is_active=True)
    except CustomUserModel.DoesNotExist:
        request.session.pop("reset_user_id", None)
        return redirect("accounts:password_reset_phone")

    otp = OTP.objects.filter(user=user).order_by("-created_at").first()

    if not otp or otp.is_expired():
        messages.error(request, "کد منقضی شده است. لطفاً دوباره درخواست دهید.")
        otp and otp.delete()
        request.session.pop("reset_user_id", None)
        return redirect("accounts:password_reset_phone")

    form = OTPForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["otp_code"]

        if otp.max_attempts_reached():
            otp.delete()
            request.session.pop("reset_user_id", None)
            messages.error(request, "تعداد تلاش بیش از حد مجاز.")
            return redirect("accounts:password_reset_phone")

        if not _secure_compare(otp.code, code):
            otp.increase_attempts()
            remaining = 3 - otp.attempts
            messages.error(
                request,
                f"کد وارد شده نادرست است. {remaining} تلاش باقی‌مانده.",
            )
            return render(
                request,
                "registration/password_rest_otp.html",
                {"form": form},
            )

        # ✅ Verified
        otp.delete()
        request.session["reset_verified"] = True
        return redirect("accounts:password_reset_confirm")

    return render(
        request, "registration/password_rest_otp.html", {"form": form}
    )


# =========================
# Password Reset - Step 3: New Password
# =========================
@never_cache
@require_http_methods(["GET", "POST"])
def password_reset_confirm(request):
    if not request.session.get("reset_verified"):
        messages.error(request, "دسترسی غیرمجاز.")
        return redirect("accounts:password_reset_phone")

    user_id = request.session.get("reset_user_id")
    if not user_id:
        return redirect("accounts:password_reset_phone")

    user = get_object_or_404(CustomUserModel, id=user_id, is_active=True)

    form = ResetPasswordConfirmForm(user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            # Reset failed login attempts
            user.reset_failed_attempts()

        # Clear all reset session data
        for key in ["reset_user_id", "reset_verified"]:
            request.session.pop(key, None)

        messages.success(
            request,
            "رمز عبور شما با موفقیت تغییر کرد. لطفاً دوباره وارد شوید.",
        )
        return redirect("accounts:login")

    return render(
        request,
        "registration/password_reset_confirm.html",
        {"form": form},
    )

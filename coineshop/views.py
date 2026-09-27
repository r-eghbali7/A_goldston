# coineshop/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from decimal import Decimal

from account.forms import UserProfileForm, ChangePasswordForm
from .models import UserGoldAsset


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    """
    داشبورد پروفایل کاربر + نمایش دارایی‌های طلا.

    بهینه‌سازی‌ها:
    - قیمت طلا فقط ۱ بار واکشی می‌شود (از کش)
    - کوئری دارایی‌ها با select_related و only
    - محاسبات با یک حلقه و یک قیمت ثابت
    """

    # ===== پردازش فرم (POST) =====
    if request.method == 'POST':
        return _handle_profile_post(request)

    # ===== نمایش داشبورد (GET) =====
    user_form = UserProfileForm(instance=request.user)
    password_form = ChangePasswordForm(user=request.user)

    # واکشی دارایی‌ها (۱ کوئری بهینه)
    user_assets = UserGoldAsset.objects.approved_for_user(request.user)

    # قیمت طلا (از کش - ۰ کوئری اضافه)
    gold_price = UserGoldAsset.get_gold_price_today()

    # محاسبات مجموع با یک حلقه
    summary = _calculate_portfolio_summary(user_assets, gold_price)

    context = {
        'user_form': user_form,
        'password_form': password_form,
        'user_assets': summary['assets_with_calc'],
        'gold_price_18k': int(gold_price),
        'total_assets_value': summary['total_current_value'],
        'total_buy_value': summary['total_buy_value'],
        'total_profit_amount': summary['total_profit_amount'],
        'total_profit_percent': summary['total_profit_percent'],
        'assets_count': summary['count'],
    }

    return render(request, 'registration/dashboard.html', context)


def _handle_profile_post(request):
    """
    پردازش فرم‌های پروفایل و تغییر رمز عبور.
    هر فرم مستقل بررسی می‌شود.
    """
    action = request.POST.get('action', '')

    if action == 'update_profile':
        user_form = UserProfileForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'اطلاعات کاربری با موفقیت بروزرسانی شد.')
        else:
            for field, errors in user_form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')

    elif action == 'change_password':
        password_form = ChangePasswordForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'رمز عبور با موفقیت تغییر کرد.')
        else:
            for field, errors in password_form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        messages.error(request, 'درخواست نامعتبر.')

    return redirect('accounts:profile')


def _calculate_portfolio_summary(assets, gold_price: Decimal) -> dict:
    """
    محاسبه خلاصه پورتفولیو با یک حلقه.
    قیمت طلا یک بار پاس داده می‌شود → ۰ کوئری اضافه.
    """
    total_current = Decimal('0')
    total_buy = Decimal('0')
    total_profit = Decimal('0')
    count = 0

    assets_list = []

    for asset in assets:
        current_price = asset.calc_current_price(gold_price)
        profit_amount = asset.calc_profit_amount(gold_price)
        profit_percent = asset.calc_profit_percent(gold_price)

        # Annotate روی آبجکت (برای تمپلیت)
        asset.current_price_calc = int(current_price)
        asset.profit_amount_calc = int(profit_amount)
        asset.profit_percent_calc = round(profit_percent, 2)
        asset.is_profitable = profit_amount >= 0

        total_current += current_price
        total_buy += Decimal(str(asset.buy_price))
        total_profit += profit_amount
        count += 1

        assets_list.append(asset)

    # درصد سود کل
    total_percent = Decimal('0')
    if total_buy > 0:
        total_percent = (total_profit / total_buy) * 100

    return {
        'assets_with_calc': assets_list,
        'total_current_value': int(total_current),
        'total_buy_value': int(total_buy),
        'total_profit_amount': int(total_profit),
        'total_profit_percent': round(total_percent, 2),
        'count': count,
    }

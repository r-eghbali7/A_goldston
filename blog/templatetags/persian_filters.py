from django import template

register = template.Library()

PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'


def to_persian_numeral(value):
    """تبدیل اعداد انگلیسی به فارسی"""
    result = str(value)
    for i, digit in enumerate('0123456789'):
        result = result.replace(digit, PERSIAN_DIGITS[i])
    return result


@register.filter(name='persian_price')
def persian_price(value):
    """
    تبدیل قیمت به فرمت فارسی با کاما
    مثال: 1500000 → ۱,۵۰۰,۰۰۰
    """
    if value is None or value == '':
        return '۰'

    try:
        # حذف کاراکترهای اضافی و تبدیل به عدد
        num = int(str(value).replace(',', '').replace('٬', '').replace('،', '').strip())
        # فرمت با کاما
        formatted = f"{num:,}"
        # تبدیل به فارسی
        return to_persian_numeral(formatted)
    except (ValueError, TypeError):
        return to_persian_numeral(str(value))


@register.filter(name='to_persian')
def to_persian(value):
    """
    فقط تبدیل اعداد به فارسی (بدون کاما)
    مثال: 125 → ۱۲۵
    """
    if value is None:
        return ''
    return to_persian_numeral(str(value))


@register.filter(name='persian_price_toman')
def persian_price_toman(value):
    """
    تبدیل قیمت به فارسی با کاما + کلمه تومان
    مثال: 1500000 → ۱,۵۰۰,۰۰۰ تومان
    """
    if value is None or value == '' or value == 0:
        return 'رایگان'

    try:
        num = int(str(value).replace(',', '').replace('٬', '').replace('،', '').strip())
        formatted = f"{num:,}"
        persian = to_persian_numeral(formatted)
        return f"{persian}"
    except (ValueError, TypeError):
        return to_persian_numeral(str(value))


@register.filter(name='persian_discount_price')
def persian_discount_price(value):
    """
    نمایش قیمت با تخفیف
    """
    if value is None or value == '' or value == 0:
        return ''

    try:
        num = int(str(value).replace(',', '').replace('٬', '').replace('،', '').strip())
        formatted = f"{num:,}"
        return to_persian_numeral(formatted)
    except (ValueError, TypeError):
        return to_persian_numeral(str(value))

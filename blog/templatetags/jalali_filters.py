from django import template
import jdatetime

register = template.Library()

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

PERSIAN_NUMBERS = "۰۱۲۳۴۵۶۷۸۹"

def to_persian_number(number_str):
    return "".join(PERSIAN_NUMBERS[int(c)] if c.isdigit() else c for c in number_str)

@register.filter
def jalali_date_verbose(value):
    if not value:
        return ""
    
    try:
        # اگر value از نوع jdatetime باشد، مستقیم استفاده می‌کنیم
        if isinstance(value, jdatetime.datetime) or isinstance(value, jdatetime.date):
            jalali = value
        else:
            # اگر datetime میلادی بود، تبدیل کنیم
            jalali = jdatetime.datetime.fromgregorian(datetime=value)

        day = to_persian_number(str(jalali.day))       # روز به فارسی
        month = PERSIAN_MONTHS[jalali.month - 1]       # ماه به فارسی
        year = to_persian_number(str(jalali.year))     # سال به فارسی

        return f"{day} {month} {year}"

    except Exception as e:
        return str(value)

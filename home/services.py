import requests
import re
from bs4 import BeautifulSoup
from django.core.cache import cache
from django.utils import timezone
from .models import GoldPriceCache, GoldDailyPrice

# ---------------------------------------------------------
# ثابت‌های کش
# ---------------------------------------------------------
CACHE_API_KEY = 'gold_api_data_full'
CACHE_API_TTL = 60  # ۶۰ ثانیه کش در لایه جنگو
TIMEOUT_SECONDS = 10

# ---------------------------------------------------------
# توابع کمکی
# ---------------------------------------------------------
def format_number_fa(number_str):
    """جدا کردن ارقام سه‌تایی و استفاده از ویرگول"""
    if not number_str:
        return ""
    try:
        if isinstance(number_str, (int, float)):
            number_str = str(int(number_str))
        number_str = str(number_str).replace(',', '').replace('،', '').strip()
        parts = []
        while len(number_str) > 3:
            parts.insert(0, number_str[-3:])
            number_str = number_str[:-3]
        if number_str:
            parts.insert(0, number_str)
        return "،".join(parts)
    except Exception:
        return number_str

def parse_persian_int(text):
    """تبدیل رشته به عدد صحیح"""
    if not text:
        return 0
    persian_to_english = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    }
    cleaned_text = ''.join(persian_to_english.get(char, char) for char in text)
    cleaned_text = re.sub(r'[^\d]', '', cleaned_text)
    try:
        return int(cleaned_text) if cleaned_text else 0
    except ValueError:
        return 0

# ---------------------------------------------------------
# تابع اسکرپر
# ---------------------------------------------------------
def fetch_gold_prices_from_scraper() -> dict:
    """دریافت قیمت‌ها از سایت و تبدیل به تومان"""
    url = "https://estjt.ir/tv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        raw_data = {
            'gold_price_irr': 0,
            'gold_18k_price': 0,
            'sikka_imami': 0,
            'sikka_tamam': 0,
            'sikka_nim': 0,
            'sikka_rub': 0,
        }

        price_table = soup.select_one(".price-table")
        if price_table:
            rows = price_table.find_all("div", recursive=False)
            for row in rows:
                label_span = row.select_one(".label")
                amount_span = row.select_one(".amount")
                if label_span and amount_span:
                    label = label_span.text.strip()
                    amount_clean = amount_span.text.strip().replace(',', '')
                    
                    if "مظنه تهران" in label:
                        continue
                    if "۱۸" in label or "18" in label:
                        raw_data['gold_18k_price'] = parse_persian_int(amount_clean) #// 10
                    elif "اُنس" in label or "انس" in label:
                        # قیمت انس معمولا دلاری است، اگر در سایت ریالی است این را هم // 10 کنید
                        raw_data['gold_price_irr'] = parse_persian_int(amount_clean.replace('$', '').strip())
                    elif "طرح جدید" in label or "امامی" in label:
                        raw_data['sikka_imami'] = parse_persian_int(amount_clean) #// 10
                    elif "طرح قدیم" in label or "بهار" in label:
                        raw_data['sikka_tamam'] = parse_persian_int(amount_clean) #// 10
                    elif "نیم سکه" in label:
                        raw_data['sikka_nim'] = parse_persian_int(amount_clean) #// 10
                    elif "ربع سکه" in label:
                        raw_data['sikka_rub'] = parse_persian_int(amount_clean) #// 10

        return {'success': True, 'raw': raw_data}

    except Exception as e:
        return {'success': False, 'error': str(e)}

# ---------------------------------------------------------
# تابع اصلی مدیریت آپدیت و دیتابیس (فقط همین یک تابع باید باشد)
# ---------------------------------------------------------
def update_and_get_gold_data() -> dict:
    """بررسی کش، فراخوانی اسکرپر و محاسبه درصد تغییرات"""
    cached_result = cache.get(CACHE_API_KEY)
    if cached_result:
        return cached_result

    db_cache, created = GoldPriceCache.objects.get_or_create(id=1)
    needs_update = created or not db_cache.last_updated or \
                   (timezone.now() - db_cache.last_updated).total_seconds() > CACHE_API_TTL

    if needs_update:
        scraper_response = fetch_gold_prices_from_scraper()
        if scraper_response.get('success'):
            raw = scraper_response['raw']
            
            # ایجاد فرمت‌شده‌ها
            formatted_data = {k: format_number_fa(v) for k, v in raw.items()}
            
            db_cache.data = formatted_data
            db_cache.raw_data = raw
            db_cache.last_updated = timezone.now()
            db_cache.save()
            
            # ذخیره اسنپ‌شات امروز در مدل GoldDailyPrice
            today = timezone.now().date()
            GoldDailyPrice.objects.update_or_create(
                date=today,
                defaults={
                    'gold_price_irr': raw['gold_price_irr'],
                    'gold_18k_price': raw['gold_18k_price'],
                    'sikka_imami': raw['sikka_imami'],
                    'sikka_tamam': raw['sikka_tamam'],
                    'sikka_nim': raw['sikka_nim'],
                    'sikka_rub': raw['sikka_rub'],
                }
            )

    current_raw = db_cache.raw_data or {}
    current_formatted = db_cache.data or {}
    
    # محاسبه تغییرات نسبت به روز قبل
    today = timezone.now().date()
    yesterday_data = GoldDailyPrice.objects.exclude(date=today).order_by('-date').first()
    changes = {}
    
    if yesterday_data:
        def calc_change(current_val, yesterday_val):
            try:
                curr = float(current_val)
                yest = float(yesterday_val)
                if yest == 0: return {'direction': 'unchanged', 'percent': 0, 'diff': 0, 'color': 'text-[#92a4c9]', 'icon': 'remove'}
                
                diff = curr - yest
                percent = (diff / yest) * 100
                
                # اضافه کردن رنگ و آیکون برای راحت‌تر شدن کار در HTML
                direction = 'up' if diff > 0 else 'down' if diff < 0 else 'unchanged'
                color = 'text-[#0bda5e]' if direction == 'up' else 'text-[#fa6238]' if direction == 'down' else 'text-[#92a4c9]'
                bg_color = 'bg-[#0bda5e]/10' if direction == 'up' else 'bg-[#fa6238]/10' if direction == 'down' else 'bg-gray-500/10'
                icon = 'trending_up' if direction == 'up' else 'trending_down' if direction == 'down' else 'remove'

                return {
                    'direction': direction,
                    'percent': round(abs(percent), 2),
                    'diff': abs(diff),
                    'color': color,
                    'bg_color': bg_color,
                    'icon': icon
                }
            except (ValueError, TypeError):
                return {'direction': 'unchanged', 'percent': 0, 'diff': 0, 'color': 'text-[#92a4c9]', 'bg_color': 'bg-gray-500/10', 'icon': 'remove'}

        # 👈 محاسبه تغییرات برای همه آیتم‌ها
        changes['gold_18k_price'] = calc_change(current_raw.get('gold_18k_price', 0), yesterday_data.gold_18k_price)
        changes['sikka_imami'] = calc_change(current_raw.get('sikka_imami', 0), yesterday_data.sikka_imami)
        changes['gold_price_irr'] = calc_change(current_raw.get('gold_price_irr', 0), yesterday_data.gold_price_irr)
        changes['sikka_tamam'] = calc_change(current_raw.get('sikka_tamam', 0), yesterday_data.sikka_tamam)
        changes['sikka_nim'] = calc_change(current_raw.get('sikka_nim', 0), yesterday_data.sikka_nim)
        changes['sikka_rub'] = calc_change(current_raw.get('sikka_rub', 0), yesterday_data.sikka_rub)


    result = {
        'formatted': current_formatted,
        'raw': current_raw,
        'changes': changes,
        'gold_18k_price': float(current_raw.get('gold_18k_price', 0)),
        'last_update_str': timezone.localtime(db_cache.last_updated).strftime('%H:%M:%S') if db_cache.last_updated else '',
        'last_updated': timezone.localtime(db_cache.last_updated).strftime('%H:%M:%S') if db_cache.last_updated else '', # این خط را اضافه کنید
        'last_updated_datetime': db_cache.last_updated,
    }


    cache.set(CACHE_API_KEY, result, CACHE_API_TTL)
    return result

# home/context_processors.py
from home.services import update_and_get_gold_data
from .forms import EmailSubscribeForm

def gold_prices(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {}

    path = request.path
    if path.startswith('/admin/') or path.startswith('/api/'):
        return {}

    gold_data = update_and_get_gold_data() 
    
    # 👈 استخراج دیتای خام برای خواندن قیمت‌ها
    raw_prices = gold_data.get('raw', {})

    return {
            'gold_18k_price': raw_prices.get('gold_18k_price'),
            'gold_price_irr': raw_prices.get('gold_price_irr'),
            'sikka_imami': raw_prices.get('sikka_imami'),
            'sikka_tamam': raw_prices.get('sikka_tamam'),
            'sikka_nim': raw_prices.get('sikka_nim'),
            'sikka_rub': raw_prices.get('sikka_rub'),
            
            # 👈 اضافه کردن متغیر تغییرات به کانتکست
            'gold_changes': gold_data.get('changes', {}),
            
            'gold_last_update_str': gold_data.get('last_update_str'),
            'gold_last_updated_datetime': gold_data.get('last_updated_datetime'),
    }

def email_form(request):
    return {
        'email_subscribe_form': EmailSubscribeForm()
    }

from django.core.management.base import BaseCommand
from home.services import update_and_get_gold_data
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'دریافت قیمت طلا از اسکرپر و ذخیره در دیتابیس'

    def handle(self, *args, **options):
        self.stdout.write("شروع دریافت داده‌ها...")
        result = update_and_get_gold_data()
        if result and result.get('raw'):
            self.stdout.write(self.style.SUCCESS('داده‌ها با موفقیت به‌روزرسانی و در دیتابیس ذخیره شدند.'))
        else:
            self.stdout.write(self.style.ERROR('خطا در دریافت داده‌ها.'))

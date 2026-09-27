# home/serializers.py

from rest_framework import serializers
from .models import ParsianCoin


class ParsianCoinPriceSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    price_raw = serializers.SerializerMethodField()

    class Meta:
        model = ParsianCoin
        fields = ('name', 'weight_gram', 'price', 'price_raw')

    def get_price(self, obj) -> str:
        """قیمت فرمت‌شده"""
        gold_price = self.context.get('gold_price', 0)
        if gold_price:
            raw = obj.calc_price(gold_price)
            return f"{raw:,}"
        return "۰"

    def get_price_raw(self, obj) -> int:
        """قیمت عددی (برای مرتب‌سازی و محاسبات)"""
        gold_price = self.context.get('gold_price', 0)
        return obj.calc_price(gold_price) if gold_price else 0

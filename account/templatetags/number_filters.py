from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def smart_number(value):
    """
    123456.000 → 123,456
    123456.50  → 123,456.5
    """
    if value is None:
        return ""

    value = Decimal(value)

    if value == value.to_integral():
        return f"{int(value):,}"

    return f"{value.normalize():,}"
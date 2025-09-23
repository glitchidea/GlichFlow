from django import template

register = template.Library()

@register.filter
def divisibleby(value, arg):
    """
    Returns the percentage of value compared to arg
    Example: {{ 5|divisibleby:10 }} returns 50.0
    """
    try:
        value = float(value)
        arg = float(arg)
        if arg:
            return value / arg * 100
        return 0
    except (ValueError, TypeError):
        return 0 
from django import template

register = template.Library()

@register.filter
def format_price(value):
    try:
        if value is None or value == "":
            return "0.--"
        price = float(value)
        rounded = round(price, 2)
        
        # Se dopo l'arrotondamento è intero
        if rounded % 1 == 0:
            formatted = f"{int(rounded):,}".replace(",", "'")
            return f"{formatted}.--"
        
        # Se ha decimali
        formatted = f"{rounded:,.2f}".replace(",", "'").replace(".", "__dot__").replace("'", "'").replace("__dot__", ".")
        return formatted
    except (ValueError, TypeError):
        return "0.--"

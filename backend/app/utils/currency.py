SUPPORTED_CURRENCIES = ("inr", "usd", "eur", "gbp", "aud", "cad", "sgd")
DEFAULT_CURRENCY = "usd"

CURRENCY_SYMBOLS = {
    "inr": "₹",
    "usd": "$",
    "eur": "€",
    "gbp": "£",
    "aud": "A$",
    "cad": "C$",
    "sgd": "S$",
}


def normalize_currency(value):
    currency = (value or DEFAULT_CURRENCY).strip().lower()
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError("Unsupported currency")
    return currency


def currency_symbol(value):
    currency = (value or DEFAULT_CURRENCY).strip().lower()
    return CURRENCY_SYMBOLS.get(currency, currency.upper() + " ")


def money_label(amount, currency=None):
    return f"{currency_symbol(currency)}{float(amount or 0):.2f}"


def bucket_add(bucket, currency, amount):
    code = normalize_currency(currency)
    bucket[code] = round(float(bucket.get(code, 0) or 0) + float(amount or 0), 2)
    return bucket

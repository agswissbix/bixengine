import logging
from datetime import datetime
from typing import Dict, List, Optional, Union

import requests
from django.conf import settings
from django.core.cache import cache

LOGGER = logging.getLogger(__name__)

FRANKFURTER_URL = getattr(settings, "FRANKFURTER_URL", "https://api.frankfurter.app")
FX_CACHE_TTL_LATEST = getattr(settings, "FX_CACHE_TTL_LATEST", 3600)


def normalize_currency(code: Optional[str]) -> Optional[str]:
    """Normalizza un codice valuta (None-safe) a ISO upper-case.

    Restituisce None se `code` è falsy.
    """
    if not code:
        return None
    return code.strip().upper()


def _cache_key(base: str, to_list: List[str], date: Optional[str]) -> str:
    to_key = ",".join(sorted(to_list)) if to_list else ""
    date_key = date if date else "latest"
    return f"fx:{date_key}:{base}:{to_key}"


def get_frankfurter_rates(
    base: Union[str, None],
    to_list: Optional[List[str]] = None,
    date: Optional[Union[str, datetime]] = None,
    ttl: Optional[int] = None,
) -> Dict[str, float]:
    """Recupera i tassi da Frankfurter.

    - `base`: codice ISO della valuta di base (es. 'CHF').
    - `to_list`: lista di valute da richiedere (es. ['USD','EUR']).
    - `date`: None per latest oppure stringa 'YYYY-MM-DD' o datetime per storico.
    - Restituisce un dict con chiavi in upper-case e valori float.

    Usa la cache Django. Per i tassi `latest` la cache TTL usa `FX_CACHE_TTL_LATEST`.
    I tassi storici (quando `date` è fornita) vengono memorizzati senza scadenza.
    """
    if base is None:
        return {}

    base = normalize_currency(base)
    to_list = [normalize_currency(t) for t in (to_list or []) if t]
    to_list = [t for t in to_list if t]

    if isinstance(date, datetime):
        date = date.strftime("%Y-%m-%d")

    to_list = sorted(set(to_list))
    key = _cache_key(base, to_list, date)
    
    include_base_rate = False
    if base in to_list:
        include_base_rate = True
        to_list = [t for t in to_list if t != base]
    cached = cache.get(key)
    if cached:
        return cached

    if not to_list:
        rates = {base: 1.0} if include_base_rate else {}
        cache.set(key, rates, None if date else (ttl if ttl is not None else FX_CACHE_TTL_LATEST))
        return rates

    if date:
        url = f"{FRANKFURTER_URL}/{date}"
    else:
        url = f"{FRANKFURTER_URL}/latest"

    params = {"from": base}
    params["to"] = ",".join(to_list)

    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        raw_rates = data.get("rates", {})
        rates: Dict[str, float] = {k.upper(): float(v) for k, v in raw_rates.items()}

        if include_base_rate:
            rates[base] = 1.0

        if date:
            cache.set(key, rates, None)
        else:
            cache.set(key, rates, ttl if ttl is not None else FX_CACHE_TTL_LATEST)

        return rates

    except Exception:
        LOGGER.exception("Frankfurter request failed for base=%s to=%s date=%s", base, to_list, date)
        if include_base_rate:
            out = cached or {}
            out.setdefault(base, 1.0)
            return out
        return cached or {}


def convert_amount(
    amount: Union[float, int, str, None],
    source_currency: Optional[str],
    target_currency: Optional[str],
    rates: Dict[str, float],
) -> Optional[float]:
    """Converti `amount` da `source_currency` a `target_currency` usando `rates`.

    Assunzione: `rates` è stato richiesto con `from=target_currency` (base = target).
    Quindi `rates[source_currency]` indica quanti unità di SOURCE corrispondono a 1 TARGET.

    Formula: amount_in_target = amount_in_source / rates[source]

    Restituisce None se la conversione non è possibile (es. rate mancante).
    """
    if amount is None:
        return None

    src = normalize_currency(source_currency)
    tgt = normalize_currency(target_currency)

    try:
        amount_f = float(amount)
    except Exception:
        return None

    if not src or not tgt:
        return None
    if src == tgt:
        return amount_f

    rate = rates.get(src)
    if not rate:
        return None

    try:
        if float(rate) == 0:
            return None
        return amount_f / float(rate)
    except Exception:
        return None

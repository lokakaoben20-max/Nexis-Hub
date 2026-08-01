import json
import os
import time
from pathlib import Path

import httpx

CACHE_PATH = Path(__file__).with_name("exchange_rate_cache.json")
CACHE_TTL_SECONDS = 6 * 60 * 60  # the underlying API only refreshes once a day anyway

# Ratio implied by the fee amounts hardcoded before this module existed
# (1.50 USD ~= 4000 CDF). Used only if no cached rate exists and the API
# is unreachable, so a first-ever call never breaks payments.
FALLBACK_USD_CDF_RATE = 2666.67


def _free_api_url() -> str:
    api_key = os.getenv("EXCHANGERATE_API_KEY")
    if api_key:
        return f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
    return "https://open.er-api.com/v6/latest/USD"


def _read_cache() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(rate: float) -> None:
    try:
        CACHE_PATH.write_text(
            json.dumps({"usd_cdf_rate": rate, "fetched_at": time.time()}),
            encoding="utf-8",
        )
    except OSError:
        pass


def _fetch_rate_from_api() -> float | None:
    try:
        response = httpx.get(_free_api_url(), timeout=5.0)
        response.raise_for_status()
        data = response.json()
        rates = data.get("conversion_rates") or data.get("rates") or {}
        rate = rates.get("CDF")
        return float(rate) if rate else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


def get_usd_to_cdf_rate(force_refresh: bool = False) -> float:
    cache = _read_cache()
    is_fresh = cache is not None and (time.time() - cache.get("fetched_at", 0)) < CACHE_TTL_SECONDS

    if is_fresh and not force_refresh:
        return cache["usd_cdf_rate"]

    fetched_rate = _fetch_rate_from_api()
    if fetched_rate is not None:
        _write_cache(fetched_rate)
        return fetched_rate

    if cache is not None:
        return cache["usd_cdf_rate"]

    return FALLBACK_USD_CDF_RATE

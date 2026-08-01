import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import exchange_rates


def test_fetches_and_caches_rate_when_no_cache_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(exchange_rates, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(exchange_rates, "_fetch_rate_from_api", lambda: 2500.0)

    rate = exchange_rates.get_usd_to_cdf_rate()

    assert rate == 2500.0
    cached = json.loads(exchange_rates.CACHE_PATH.read_text(encoding="utf-8"))
    assert cached["usd_cdf_rate"] == 2500.0


def test_fresh_cache_is_used_without_hitting_the_api(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({"usd_cdf_rate": 2200.0, "fetched_at": time.time()}), encoding="utf-8")
    monkeypatch.setattr(exchange_rates, "CACHE_PATH", cache_path)

    def _fail_if_called():
        raise AssertionError("should not hit the API when cache is fresh")

    monkeypatch.setattr(exchange_rates, "_fetch_rate_from_api", _fail_if_called)

    rate = exchange_rates.get_usd_to_cdf_rate()
    assert rate == 2200.0


def test_stale_cache_triggers_a_refresh(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    old_timestamp = time.time() - exchange_rates.CACHE_TTL_SECONDS - 1
    cache_path.write_text(json.dumps({"usd_cdf_rate": 2200.0, "fetched_at": old_timestamp}), encoding="utf-8")
    monkeypatch.setattr(exchange_rates, "CACHE_PATH", cache_path)
    monkeypatch.setattr(exchange_rates, "_fetch_rate_from_api", lambda: 2600.0)

    rate = exchange_rates.get_usd_to_cdf_rate()
    assert rate == 2600.0


def test_falls_back_to_stale_cache_when_api_is_unreachable(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    old_timestamp = time.time() - exchange_rates.CACHE_TTL_SECONDS - 1
    cache_path.write_text(json.dumps({"usd_cdf_rate": 2200.0, "fetched_at": old_timestamp}), encoding="utf-8")
    monkeypatch.setattr(exchange_rates, "CACHE_PATH", cache_path)
    monkeypatch.setattr(exchange_rates, "_fetch_rate_from_api", lambda: None)

    rate = exchange_rates.get_usd_to_cdf_rate()
    assert rate == 2200.0


def test_falls_back_to_hardcoded_default_when_no_cache_and_api_unreachable(tmp_path, monkeypatch):
    monkeypatch.setattr(exchange_rates, "CACHE_PATH", tmp_path / "missing_cache.json")
    monkeypatch.setattr(exchange_rates, "_fetch_rate_from_api", lambda: None)

    rate = exchange_rates.get_usd_to_cdf_rate()
    assert rate == exchange_rates.FALLBACK_USD_CDF_RATE


def test_force_refresh_bypasses_fresh_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({"usd_cdf_rate": 2200.0, "fetched_at": time.time()}), encoding="utf-8")
    monkeypatch.setattr(exchange_rates, "CACHE_PATH", cache_path)
    monkeypatch.setattr(exchange_rates, "_fetch_rate_from_api", lambda: 2999.0)

    rate = exchange_rates.get_usd_to_cdf_rate(force_refresh=True)
    assert rate == 2999.0

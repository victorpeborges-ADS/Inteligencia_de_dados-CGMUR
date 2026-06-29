from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.data_connectors.cache import cache_get_json, cache_set_json

_last_request_at = 0.0
RATE_LIMIT_SECONDS = 0.5  # 2 req/s


def _respect_rate_limit() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    _last_request_at = time.monotonic()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def fetch_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    cache_key: Optional[str] = None,
    cache_ttl: int = 3600,
    timeout: int = 20,
) -> Any:
    if cache_key:
        cached = cache_get_json(cache_key)
        if cached is not None:
            return cached

    _respect_rate_limit()
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={"User-Agent": "Sinidu+Clima/1.0 (MCID integracao publica)"},
    )
    response.raise_for_status()
    if response.status_code == 204 or not response.text.strip():
        data = None
    else:
        data = response.json()

    if cache_key and data is not None:
        cache_set_json(cache_key, data, cache_ttl)
    return data

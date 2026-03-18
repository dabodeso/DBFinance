from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests


class FMPError(RuntimeError):
    pass


BASE_URL = "https://financialmodelingprep.com/stable"


def get_api_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.getenv("FMP_API_KEY") or ""
    if not key:
        raise FMPError(
            "Falta la API key de FMP. Configura FMP_API_KEY como variable de entorno o en Streamlit Secrets."
        )
    return key


def _request_json(path: str, params: Dict[str, Any], api_key: str) -> Any:
    url = f"{BASE_URL}{path}"
    p = dict(params)
    p["apikey"] = api_key
    r = requests.get(url, params=p, timeout=20)
    if r.status_code == 429:
        raise FMPError("Too Many Requests (429) en FMP. Rate limit excedido.")
    if r.status_code == 403:
        raise FMPError("API key inválida o sin permisos (403) en FMP.")
    if r.status_code >= 400:
        raise FMPError(f"Error FMP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()
    except Exception as e:
        raise FMPError(f"Respuesta no JSON desde FMP: {e}") from e


def get_json_with_retry(
    path: str,
    params: Dict[str, Any],
    api_key: str,
    retries: int = 3,
    backoff_s: float = 1.5,
) -> Any:
    last_err: Optional[Exception] = None
    for i in range(retries):
        try:
            return _request_json(path, params=params, api_key=api_key)
        except FMPError as e:
            last_err = e
            # retry solo para 429
            if "429" not in str(e):
                break
            time.sleep(backoff_s * (2**i))
    if last_err:
        raise last_err
    raise FMPError("Error desconocido en FMP.")


def quote(symbol: str, api_key: str) -> Dict[str, Any]:
    data = get_json_with_retry("/quote", {"symbol": symbol}, api_key=api_key)
    if isinstance(data, list) and data:
        return dict(data[0])
    if isinstance(data, dict):
        return data
    return {}


def profile(symbol: str, api_key: str) -> Dict[str, Any]:
    data = get_json_with_retry("/profile", {"symbol": symbol}, api_key=api_key)
    if isinstance(data, list) and data:
        return dict(data[0])
    if isinstance(data, dict):
        return data
    return {}


def income_statement(symbol: str, api_key: str, limit: int = 5, period: str = "annual") -> List[Dict[str, Any]]:
    data = get_json_with_retry(
        "/income-statement",
        {"symbol": symbol, "limit": limit, "period": period},
        api_key=api_key,
    )
    return list(data) if isinstance(data, list) else []


def balance_sheet(symbol: str, api_key: str, limit: int = 5, period: str = "annual") -> List[Dict[str, Any]]:
    data = get_json_with_retry(
        "/balance-sheet-statement",
        {"symbol": symbol, "limit": limit, "period": period},
        api_key=api_key,
    )
    return list(data) if isinstance(data, list) else []


def cash_flow(symbol: str, api_key: str, limit: int = 5, period: str = "annual") -> List[Dict[str, Any]]:
    # En docs aparece como cash-flow-statement en el playground; mantenemos ese path.
    data = get_json_with_retry(
        "/cash-flow-statement",
        {"symbol": symbol, "limit": limit, "period": period},
        api_key=api_key,
    )
    return list(data) if isinstance(data, list) else []


def dividends(symbol: str, api_key: str) -> List[Dict[str, Any]]:
    data = get_json_with_retry("/dividends", {"symbol": symbol}, api_key=api_key)
    return list(data) if isinstance(data, list) else []


def historical_price_eod_full(symbol: str, api_key: str) -> Any:
    # Nota: la doc que encontramos menciona índices, pero suele funcionar también para acciones.
    return get_json_with_retry("/historical-price-eod/full", {"symbol": symbol}, api_key=api_key)


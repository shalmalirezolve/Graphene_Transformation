"""
Price extraction and normalization.

Handles three common source formats:
  A) [{currency: "USD", value: 21.5}, ...]   ← Fashion_merged.json style
  B) {"USD": 21.5, "GBP": 18.0}             ← flat dict style
  C) 21.5                                    ← scalar (assumes first currency in config)
"""
from typing import Any, Dict, List, Optional


def build_prices(record: Dict, currencies: List[str]) -> Dict:
    """
    Returns:
      {
        "USD": {"price": 21.5, "rrp": 43.0, "was": 43.0},
        "GBP": {"price": 17.0},
        ...
      }

    `rrp` = original / compare-at price.
    `was` = added alongside rrp only when price < rrp (i.e. item is on sale).
    """
    out: Dict[str, Dict] = {}

    for currency in currencies:
        price = _extract(record.get("price"),          currency)
        rrp   = _extract(record.get("original_price"), currency)

        if price is None and rrp is None:
            continue

        entry: Dict[str, float] = {}
        if price is not None:
            entry["price"] = price
        if rrp is not None:
            entry["rrp"] = rrp
            if price is not None and price < rrp:
                entry["was"] = rrp

        out[currency] = entry

    return out


# ── private ───────────────────────────────────────────────────────────────────

def _extract(raw: Any, currency: str) -> Optional[float]:
    """Pull a numeric value for `currency` from any of the three source formats."""
    if raw is None:
        return None

    # Format A: [{currency, value}]
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                item_currency = str(item.get("currency") or "").upper()
                if item_currency == currency.upper():
                    v = item.get("value") or item.get("price") or item.get("amount")
                    return _to_float(v)
        return None

    # Format B: {"USD": 21.5} or {"USD": {"price": 21.5}}
    if isinstance(raw, dict):
        match = raw.get(currency) or raw.get(currency.lower())
        if match is None:
            return None
        if isinstance(match, dict):
            v = match.get("price") or match.get("value") or match.get("amount")
            return _to_float(v)
        return _to_float(match)

    # Format C: scalar — assume it applies to the first currency only
    return _to_float(raw)


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

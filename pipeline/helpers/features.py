"""
Features array builder.

Schema rules (devdocs):
  - hierarchy option values must be lowercase URL-safe slugs
  - attribute_id values are lowercase strings
"""
from typing import Any, Dict, List, Optional

from .cleaners import top_category_parts, material_label
from .slugify import slugify


def build_features(record: Dict) -> List[Dict]:
    features: List[Dict] = []

    # ── Taxonomy hierarchies (option values must be lowercase slugs) ──────────
    _append_hierarchy(features, "vendor",  record.get("brand"))
    _append_hierarchy(features, "gender",  record.get("gender"))

    mat_text = material_label(record.get("material"))
    if mat_text:
        _append_hierarchy(features, "material", mat_text)

    # color and size are carried by variants[].hierarchy — not duplicated here

    for cat in _clean_list(record.get("category")):
        _append_hierarchy(features, "category", cat)

    for part in top_category_parts(record.get("top_category")):
        _append_hierarchy(features, "department", part)

    for field, dim in (("mid_category", "subcategory"), ("base_category", "subcategory")):
        val = _clean_str(record.get(field))
        if val:
            _append_hierarchy(features, dim, val)

    stock = _clean_str(record.get("stock_status"))
    if stock:
        _append_attribute(features, "stock_status", stock)

    # ── Numeric attributes ────────────────────────────────────────────────────
    _append_attribute(features, "rating",               record.get("rating"))
    _append_attribute(features, "review_count",         record.get("review_count"))

    from .cleaners import material_percentage
    mat_pct = material_percentage(record.get("material"))
    if mat_pct is not None:
        _append_attribute(features, "material_percentage", mat_pct)

    return features


# ── private ───────────────────────────────────────────────────────────────────

def _append_hierarchy(features: List[Dict], dimension: str, value: Any) -> None:
    s = _clean_str(value)
    if s:
        # Both dimension id and option id must be lowercase URL-safe slugs
        features.append({"hierarchy": [dimension.lower(), slugify(s)]})


def _append_attribute(features: List[Dict], attribute_id: str, value: Any) -> None:
    if value is None:
        return
    try:
        typed: Any = float(value)
    except (TypeError, ValueError):
        typed = str(value).strip()
        if not typed:
            return
    features.append({
        "attribute_id": attribute_id.lower(),
        "data": {"value": typed},
    })


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _clean_list(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    return [str(v).strip() for v in raw if v and str(v).strip()]

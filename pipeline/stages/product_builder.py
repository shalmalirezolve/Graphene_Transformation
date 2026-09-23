"""
Product builder — Stage 3a.

Takes a normalized record and returns a fully-formed product object
matching the GrapheneHC target schema. No source field is discarded:
  - Every mapped field has a designated target location
  - Unmapped/extra fields land in properties.extra so nothing is lost
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..config import PipelineConfig
from ..ditmap import build_ditmap
from ..helpers.cleaners import (
    material_label,
    material_percentage,
    primary_product_type,
    strip_html,
    top_category_parts,
)
from ..helpers.features import build_features
from ..helpers.prices import build_prices
from ..helpers.slugify import slugify
from ..helpers.variants import build_variants, build_warehousing


def build_product(record: Dict, config: PipelineConfig) -> Dict:
    locale  = config.locale
    title   = str(record.get("title") or "")
    top_raw = record.get("top_category")
    now     = datetime.now(timezone.utc).isoformat()

    # ── DITMAP (6 shared fields) ──────────────────────────────────────────────
    ditmap = build_ditmap(record, locale)

    # ── Prices ────────────────────────────────────────────────────────────────
    prices = build_prices(record, config.currencies)

    # ── Variants ──────────────────────────────────────────────────────────────
    variants = build_variants(record, locale, prices=prices or None)

    # ── Enabled / stock ───────────────────────────────────────────────────────
    enabled = _is_enabled(record.get("stock_status"), config.in_stock_values)

    # ── Resolve product type from cleaned top_level_category ──────────────────
    product_type_id = config.product_type_map.get(
        primary_product_type(top_raw),
        primary_product_type(top_raw),
    ) or "general"

    # ── URL / slug (use cleaned single category, not raw numpy string) ────────
    top_slug = slugify(primary_product_type(top_raw)) if top_raw else "products"
    slugs    = {locale: slugify(title)}
    urls     = {locale: f"/{top_slug}/{slugify(title)}"}

    product: Dict = {
        # ── DITMAP ───────────────────────────────────────────────────────────
        **ditmap,

        # ── Identity ─────────────────────────────────────────────────────────
        "sku":               str(record.get("id") or ""),
        "enabled":           enabled,
        "include_in_search": True,
        "stock":             1 if enabled else 0,
        "product_type_id":   product_type_id,

        # ── Commerce ─────────────────────────────────────────────────────────
        "prices": prices,

        # ── URL / SEO ─────────────────────────────────────────────────────────
        "slugs": slugs,
        "urls":  urls,
        "meta":  _build_meta(record, locale),

        # ── Discoverability ───────────────────────────────────────────────────
        "tags":     _build_tags(record),
        "features": build_features(record),

        # ── Variants & stock ──────────────────────────────────────────────────
        "variants":    variants,
        "warehousing": build_warehousing(str(record.get("id") or ""), variants),

        # ── Timestamps & publishing ───────────────────────────────────────────
        "published": now,
        "created":   now,
        "modified":  now,
    }

    # ── Merge extra data into properties (nothing lost) ───────────────────────
    _merge_extra_into_properties(product, record)

    return product


# ── private ───────────────────────────────────────────────────────────────────

def _is_enabled(stock_status: Any, in_stock_values: List[str]) -> bool:
    if stock_status is None:
        return True
    return str(stock_status).lower().strip() in {v.lower() for v in in_stock_values}


def _build_meta(record: Dict, locale: str) -> Dict:
    title     = strip_html(str(record.get("title") or "")) or ""
    desc      = strip_html(str(record.get("description") or "")) or ""
    meta_desc = desc.split(".")[0].strip() if desc else ""
    entry: Dict[str, str] = {"title": title}
    if meta_desc:
        entry["description"] = meta_desc
    return {locale: entry}


def _build_tags(record: Dict) -> List[str]:
    seen: set = set()
    tags: List[str] = []

    def _add(value: Any) -> None:
        if not value:
            return
        v = str(value).strip().lower()
        if v and v not in seen:
            seen.add(v)
            tags.append(v)

    # Top category — use cleaned parts, not the raw numpy string
    for part in top_category_parts(record.get("top_category")):
        _add(part)

    for field in ("mid_category", "base_category", "brand", "gender", "stock_status"):
        _add(record.get(field))

    for item in _clean_list(record.get("category")):
        _add(item)

    for color in _clean_list(record.get("colors")):
        _add(color)

    mat_text = material_label(record.get("material"))
    if mat_text:
        _add(mat_text)

    return tags


def _merge_extra_into_properties(product: Dict, record: Dict) -> None:
    """
    Merge any source data not captured elsewhere into product["properties"].extra
    so that no information is silently dropped.

    Currently captures:
      - material_percentage (numeric material value)
      - stock_status (raw string, useful alongside enabled flag)
    """
    props: Dict = product.get("properties") or {}

    # Material as percentage (numeric value in source)
    mat_pct = material_percentage(record.get("material"))
    if mat_pct is not None:
        props["material_percentage"] = mat_pct

    # Raw stock status string (enabled=bool is already set, but the label is useful)
    stock = _clean_str(record.get("stock_status"))
    if stock:
        props["stock_status"] = stock

    # Rating and review_count are in features[] but also useful directly in properties
    if record.get("rating") is not None:
        props.setdefault("rating", record["rating"])
    if record.get("review_count") is not None:
        props.setdefault("review_count", record["review_count"])

    # Colors and sizes as simple lists in properties (already in variants/features,
    # but having them here makes product-level queries simpler)
    colors = _clean_list(record.get("colors"))
    if colors:
        props.setdefault("colors", colors)

    sizes = _clean_list(record.get("sizes"))
    if sizes:
        props.setdefault("sizes", sizes)

    fitment_attributes = record.get("fitment_attributes") or []
    if fitment_attributes:
        props["fitment_attributes"] = fitment_attributes

    product["properties"] = props


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

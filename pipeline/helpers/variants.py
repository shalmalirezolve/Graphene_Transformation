"""
Variant generation from colors × sizes (or either alone).

Key schema rules (from devdocs):
  - hierarchy option values must be lowercase URL-safe slugs
  - each variant needs a `stock` field (deprecated but still expected)
  - warehousing must include a product-level entry (variant_id="*") FIRST,
    followed by one entry per variant
"""
from typing import Dict, List, Optional, Tuple

from .slugify import slugify


def build_variants(record: Dict, locale: str, prices: Optional[Dict] = None) -> List[Dict]:
    """
    Generate all variants for a normalized product record.

    Returns [] for single-SKU products (no colors, no sizes).
    Hierarchy values are lowercased slugs as required by the schema.
    """
    product_id = str(record.get("id") or "")
    title      = str(record.get("title") or "")
    colors     = _clean_list(record.get("colors"))
    sizes      = _clean_list(record.get("sizes"))

    combos: List[Tuple] = _make_combos(colors, sizes)
    if not combos:
        return []

    variants = []
    for combo in combos:
        # combo e.g. ("color", "Beige") or ("color", "Blue", "size", "M")
        # hierarchy: dimension ids and option ids must be lowercase slugs
        hierarchy = []
        attr_vals = []
        for i in range(0, len(combo), 2):
            dim   = combo[i].lower()          # already lowercase dimension
            label = combo[i + 1]              # human-readable value
            opt   = slugify(label)            # slugified option id
            hierarchy += [dim, opt]
            attr_vals.append(label)

        label      = " / ".join(attr_vals)
        variant_id = _make_id(product_id, [slugify(v) for v in attr_vals])

        v: Dict = {
            "id":        variant_id,
            "sku":       variant_id,
            "stock":     0,              # deprecated but schema includes it
            "hierarchy": hierarchy,
        }

        if locale and title:
            v["titles"] = {locale: {"default": f"{title} - {label}"}}

        if prices:
            v["prices"] = prices

        variants.append(v)

    return variants


def build_warehousing(product_id: str, variants: List[Dict]) -> List[Dict]:
    """
    Build the warehousing array.

    Schema requires:
      1. A product-level entry  (variant_id = "*")  — covers the whole product
      2. One entry per variant  (variant_id = <variant id>)
    """
    # Product-level entry (always present, even for single-SKU products)
    product_level = {
        "warehouse_id":    "*",
        "variant_id":      "*",
        "stock":           0,
        "stock_threshold": 0,
        "allow_backorder": False,
        "un_metered":      None,
    }

    if not variants:
        return [product_level]

    variant_entries = [
        {
            "warehouse_id":    "*",
            "variant_id":      v["id"],
            "stock":           0,
            "stock_threshold": 0,
            "allow_backorder": False,
            "un_metered":      None,
        }
        for v in variants
    ]

    return [product_level] + variant_entries


# ── private ───────────────────────────────────────────────────────────────────

def _clean_list(raw) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    return [str(v).strip() for v in raw if v and str(v).strip()]


def _make_combos(colors: List[str], sizes: List[str]) -> List[Tuple]:
    if colors and sizes:
        return [
            ("color", color, "size", size)
            for color in colors
            for size in sizes
        ]
    if colors:
        return [("color", color) for color in colors]
    if sizes:
        return [("size", size) for size in sizes]
    return []


def _make_id(product_id: str, slug_vals: List[str]) -> str:
    slug = "-".join(slug_vals)
    return f"{product_id}-{slug}"

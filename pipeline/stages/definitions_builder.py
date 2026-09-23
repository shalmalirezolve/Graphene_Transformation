"""
Definitions builder — generates definitions.json.

definitions.json is the master attribute registry for GrapheneHC. It contains:

  product_types  — one entry per unique product type (top_level_category)
  attributes     — one entry per attribute dimension used in features[] or
                   variants[]. Each attribute has an `options` list of all
                   observed values (i.e. every unique color, gender, brand, …)

All records are DITMAP structures so they are consistent with products/categories.

The builder does a single pass over all normalized records to collect unique
values, then emits the definitions file.
"""
from collections import defaultdict, OrderedDict
from typing import Any, Dict, List, Optional, Set

from ..config import PipelineConfig
from ..helpers.cleaners import top_category_parts, primary_product_type, material_label
from ..helpers.slugify import slugify


# ── public entry point ────────────────────────────────────────────────────────

def build_definitions(normalized_records: List[Dict], config: PipelineConfig) -> Dict:
    """
    Scan all normalized records and return the full definitions dict:
      {
        "data": {
          "product_types": [...],
          "attributes":    [...]
        }
      }
    """
    locale = config.locale
    collector = _Collector()

    for record in normalized_records:
        collector.ingest(record)

    product_types = _build_product_types(collector.product_types, locale)
    attributes    = _build_attributes(collector, locale)

    return {
        "data": {
            "product_types": product_types,
            "attributes":    attributes,
        }
    }


# ── collector ─────────────────────────────────────────────────────────────────

class _Collector:
    """Single-pass collector that accumulates unique values per attribute."""

    def __init__(self):
        # product types: id → display name (last seen)
        self.product_types: Dict[str, str] = OrderedDict()

        # attribute options: dimension → {option_id → display label}
        self.options: Dict[str, Dict[str, str]] = defaultdict(OrderedDict)

    def ingest(self, record: Dict) -> None:
        # ── Product type ──────────────────────────────────────────────────────
        raw_top = record.get("top_category")
        if raw_top:
            pt_id = slugify(primary_product_type(raw_top))
            if pt_id and pt_id not in self.product_types:
                parts = top_category_parts(raw_top)
                label = parts[-1] if parts else pt_id
                self.product_types[pt_id] = label

            # All category breadcrumb parts become options of "department"
            for part in top_category_parts(raw_top):
                self._add_option("department", part)

        for field in ("mid_category", "base_category"):
            val = record.get(field)
            if val and str(val).strip():
                self._add_option("subcategory", str(val).strip())

        # ── Colors ───────────────────────────────────────────────────────────
        for color in _clean_list(record.get("colors")):
            self._add_option("color", color)

        # ── Sizes ────────────────────────────────────────────────────────────
        for size in _clean_list(record.get("sizes")):
            self._add_option("size", size)

        # ── Gender ───────────────────────────────────────────────────────────
        gender = _clean_str(record.get("gender"))
        if gender:
            self._add_option("gender", gender)

        # ── Brand / vendor ───────────────────────────────────────────────────
        brand = _clean_str(record.get("brand"))
        if brand:
            self._add_option("vendor", brand)

        # ── Material (text only — numeric goes to properties) ─────────────────
        mat = material_label(record.get("material"))
        if mat:
            self._add_option("material", mat)

        # ── Named category list ───────────────────────────────────────────────
        for cat in _clean_list(record.get("category")):
            self._add_option("category", cat)

        # ── Stock status ──────────────────────────────────────────────────────
        stock = _clean_str(record.get("stock_status"))
        if stock:
            self._add_option("stock_status", stock)

    def _add_option(self, dimension: str, label: str) -> None:
        opt_id = slugify(label)
        if opt_id and opt_id not in self.options[dimension]:
            self.options[dimension][opt_id] = label


# ── builders ──────────────────────────────────────────────────────────────────

def _build_product_types(pt_map: Dict[str, str], locale: str) -> List[Dict]:
    result = []
    for pt_id, label in pt_map.items():
        result.append({
            "id":          pt_id,
            "enabled":     True,
            "titles":      {locale: {"default": _title_case(label)}},
            "media":       None,
            "abstracts":   None,
            "properties":  None,
        })
    return result


def _build_attributes(collector: "_Collector", locale: str) -> List[Dict]:
    """
    Emit one attribute entry per dimension, ordered by importance.
    Numeric-only attributes (rating, review_count) have no options list.
    """
    result = []

    # ── Variant attributes (user-selectable) ──────────────────────────────────
    for dim in ("color", "size"):
        opts = collector.options.get(dim)
        if opts:
            result.append(_attribute_with_options(dim, _title_case(dim), opts, locale))

    # ── Feature attributes (not user-selectable) ──────────────────────────────
    for dim in ("gender", "vendor", "material", "department", "subcategory", "category", "stock_status"):
        opts = collector.options.get(dim)
        if opts:
            label = {
                "vendor":       "Brand / Vendor",
                "department":   "Department",
                "subcategory":  "Subcategory",
                "stock_status": "Stock Status",
            }.get(dim, _title_case(dim))
            result.append(_attribute_with_options(dim, label, opts, locale))

    # ── Numeric attributes (no options — just definitions) ────────────────────
    result.append(_numeric_attribute("rating",              "Rating",                  locale))
    result.append(_numeric_attribute("review_count",        "Review Count",            locale))
    result.append(_numeric_attribute("material_percentage", "Material Composition %",  locale))

    return result


def _attribute_with_options(attr_id: str, label: str, opts: Dict[str, str], locale: str) -> Dict:
    options = []
    for opt_id, opt_label in opts.items():
        options.append({
            "id":         opt_id,
            "enabled":    True,
            "titles":     {locale: {"default": opt_label}},
            "media":      None,
            "abstracts":  None,
            "properties": None,
        })
    return {
        "id":         attr_id,
        "enabled":    True,
        "titles":     {locale: {"default": label}},
        "media":      None,
        "abstracts":  None,
        "properties": None,
        "options":    options,
    }


def _numeric_attribute(attr_id: str, label: str, locale: str) -> Dict:
    return {
        "id":         attr_id,
        "enabled":    True,
        "titles":     {locale: {"default": label}},
        "media":      None,
        "abstracts":  None,
        "properties": {"type": "numeric"},
        "options":    [],
    }


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _title_case(s: str) -> str:
    return s.replace("_", " ").replace("-", " ").title()

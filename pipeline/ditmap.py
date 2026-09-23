"""
DITMAP field builders.

These 6 functions produce the shared fields that every target schema
(Products, Categories, Pages) references as /* See DITMAP */.

All builders accept a *normalized* record — a dict with canonical field names
produced by stages/normalizer.py — so they are source-schema-agnostic.

HTML handling: the GrapheneHC schema notes that descriptions/abstracts
"will typically contain HTML". However, we store plain text (HTML stripped)
so that source data HTML tags never appear in output — the platform renders
plain text fine, and it's easier to inspect / search.
"""
from typing import Any, Dict, List, Optional

from .helpers.cleaners import strip_html


# ── descriptions ─────────────────────────────────────────────────────────────

def build_descriptions(record: Dict, locale: str) -> Dict:
    """
    {
      "en-us": {
        "default": "Product description as plain text.",
        "washing_instructions": "..."   # only if care_instructions present
      }
    }
    """
    parts: Dict[str, str] = {}

    desc = strip_html(record.get("description"))
    if desc:
        parts["default"] = desc

    care = strip_html(record.get("care_instructions"))
    if care:
        parts["washing_instructions"] = care

    return {locale: parts} if parts else {}


# ── id ───────────────────────────────────────────────────────────────────────

def build_id(record: Dict) -> str:
    return str(record.get("id") or "")


# ── titles ───────────────────────────────────────────────────────────────────

def build_titles(record: Dict, locale: str) -> Dict:
    """
    {
      "en-us": {
        "default": "Product Name",
        "alt_title": "Brand — Product Name"   # only when brand is present
      }
    }
    """
    title = strip_html(str(record.get("title") or ""))
    if not title:
        return {}

    entry: Dict[str, str] = {"default": title}

    brand = strip_html(str(record.get("brand") or ""))
    if brand:
        entry["alt_title"] = f"{brand} — {title}"

    return {locale: entry}


# ── media ─────────────────────────────────────────────────────────────────────

def build_media(record: Dict) -> Dict:
    """
    {
      "default": {"src": "...", "width": null, "height": null},
      "alt1":    {"src": "...", "width": null, "height": null},
      ...
    }
    Width/height are None when the source does not provide dimensions.
    """
    out: Dict[str, Dict] = {}

    main = record.get("main_image")
    if main:
        out["default"] = _media_entry(main)

    for i, url in enumerate(_iter_nonempty(record.get("additional_images")), start=1):
        out[f"alt{i}"] = _media_entry(url)

    return out


# ── abstracts ─────────────────────────────────────────────────────────────────

def build_abstracts(record: Dict, locale: str) -> Dict:
    """
    {
      "en-us": {
        "default": "First sentence of description, as plain text.",
        "occasion": "For Women"    # derived from gender when available
      }
    }
    """
    desc = strip_html(str(record.get("description") or ""))
    if not desc:
        return {}

    # First sentence as the abstract
    raw = desc.split(".")[0].strip()
    if not raw:
        return {}

    parts: Dict[str, str] = {"default": raw}

    gender = strip_html(str(record.get("gender") or ""))
    if gender:
        parts["occasion"] = f"For {gender}"

    return {locale: parts}


# ── properties ────────────────────────────────────────────────────────────────

def build_properties(record: Dict) -> Dict:
    """
    Structured key-value attributes that don't fit elsewhere.
    Only includes keys where the source has a non-None, non-empty value.
    """
    props: Dict[str, Any] = {}

    _set_if(props, "rating",       record.get("rating"))
    _set_if(props, "review_count", record.get("review_count"))
    _set_if(props, "gender",       _clean_str(record.get("gender")))
    mat = record.get("material")
    if mat is not None and isinstance(mat, str):
        _set_if(props, "material", _clean_str(mat))

    colors = [c for c in (record.get("colors") or []) if c]
    if colors:
        props["colors"] = colors

    sizes = [s for s in (record.get("sizes") or []) if s]
    if sizes:
        props["sizes"] = sizes

    return props


# ── composite builder ────────────────────────────────────────────────────────

def build_ditmap(record: Dict, locale: str) -> Dict:
    """
    Returns all 6 DITMAP fields merged into one dict, ready to be spread
    into a product, category, or page object.
    """
    return {
        "descriptions": build_descriptions(record, locale),
        "id":           build_id(record),
        "titles":       build_titles(record, locale),
        "media":        build_media(record),
        "abstracts":    build_abstracts(record, locale),
        "properties":   build_properties(record),
    }


# ── private helpers ───────────────────────────────────────────────────────────

def _media_entry(src: str) -> Dict:
    return {"src": src, "width": None, "height": None}


def _iter_nonempty(value: Any) -> List:
    if isinstance(value, list):
        return [v for v in value if v]
    if value:
        return [value]
    return []


def _set_if(d: dict, key: str, value: Any) -> None:
    if value is not None and value != "":
        d[key] = value


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None

"""
Data cleaning utilities for messy source values.

The Fashion_merged.json dataset has two data quality issues that need fixing
before values reach the transformation stages:

1. top_level_category is sometimes a numpy array string representation:
     "['Women' 'fashion tops' 'blouses']"
   These must be parsed into a clean list of individual category parts.

2. material is always an integer (0-50), not a string.
   It represents a material composition percentage, not a text label.
"""
import re
from typing import List, Optional


def parse_category_string(raw) -> List[str]:
    """
    Parse a category value into a list of clean string parts.

    Handles:
      - Plain string:              "jumpsuits"      → ["jumpsuits"]
      - Numpy array string:        "['Men' 'tops']" → ["Men", "tops"]
      - Already a list:            ["Jumpsuits"]    → ["Jumpsuits"]
      - Multiline numpy:           "[...\n  ...]"   → cleaned parts
    """
    if not raw:
        return []

    # Already a Python list
    if isinstance(raw, list):
        return [str(v).strip() for v in raw if v and str(v).strip()]

    s = str(raw).strip()

    # Numpy-style array string: "['Men' 'tops']" or "[ 'Men'\n 'tops' ]"
    if s.startswith("["):
        parts = re.findall(r"'([^']*)'", s)
        if parts:
            return [p.strip() for p in parts if p.strip()]
        # Bracket but no quoted strings — fall through to plain treatment
        s = s.strip("[]").strip()

    return [s] if s else []


def top_category_parts(raw) -> List[str]:
    """
    Return all meaningful category parts from a top_level_category value.
    Strips empty strings and deduplicates while preserving order.
    """
    parts = parse_category_string(raw)
    seen = set()
    clean = []
    for p in parts:
        key = p.lower().strip()
        if key and key not in seen:
            seen.add(key)
            clean.append(p.strip())
    return clean


def primary_product_type(raw) -> str:
    """
    Return the single most-specific product type string for product_type_id.
    For numpy arrays, this is the last (most specific) part.
    For plain strings, returns the string itself.
    """
    parts = top_category_parts(raw)
    if not parts:
        return "general"
    # Last part = most specific (e.g. "casual shorts" from ['Women','tops','casual shorts'])
    return parts[-1].lower().strip()


def material_label(value) -> Optional[str]:
    """
    Returns a display label for the material field if it is a meaningful string.
    Returns None if it is numeric (percentage) — those go to properties instead.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None   # numeric — handled as material_percentage in properties
    s = str(value).strip()
    return s if s else None


def material_percentage(value) -> Optional[int]:
    """
    Returns the integer percentage if material is numeric, else None.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def strip_html(text) -> Optional[str]:
    """
    Strip all HTML tags from a string and collapse whitespace.
    Returns None for empty/None inputs.
    Used so source data HTML and our pipeline never double-wrap content.
    """
    if not text:
        return None
    s = str(text).strip()
    if not s:
        return None
    # Remove all HTML tags
    s = re.sub(r"<[^>]+>", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else None

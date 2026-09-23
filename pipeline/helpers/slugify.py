"""
URL slug generator — no external dependencies.

"Off Shoulder Linen Jumpsuit" → "off-shoulder-linen-jumpsuit"
"""
import re
import unicodedata
from typing import Optional


def slugify(text: Optional[str]) -> str:
    if not text:
        return ""
    # Normalize unicode (e.g. é → e)
    normalized = unicodedata.normalize("NFKD", str(text))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered    = ascii_text.lower().strip()
    # Keep only word chars and hyphens
    cleaned    = re.sub(r"[^\w\s-]", "", lowered)
    # Collapse whitespace and underscores to hyphens
    hyphenated = re.sub(r"[\s_]+", "-", cleaned)
    # Collapse repeated hyphens
    collapsed  = re.sub(r"-+", "-", hyphenated)
    return collapsed.strip("-")


def build_slugs(title: str, locale: str) -> dict:
    """Return {"en-us": "some-slug"} for use in the product `slugs` field."""
    return {locale: slugify(title)}


def build_url(title: str, category: Optional[str], locale: str) -> dict:
    """Return {"en-us": "/category/some-slug"} for use in the `urls` field."""
    category_slug = slugify(category) if category else "products"
    return {locale: f"/{category_slug}/{slugify(title)}"}

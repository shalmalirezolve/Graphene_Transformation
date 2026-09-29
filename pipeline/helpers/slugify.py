"""
URL slug generator — no external dependencies.

"Off Shoulder Linen Jumpsuit" → "off-shoulder-linen-jumpsuit"
"""
import re
import hashlib
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


def bounded_slugify(text: Optional[str], max_length: int = 100) -> str:
    """Create a stable slug that fits GrapheneHC identifier limits."""
    slug = slugify(text)
    if len(slug) <= max_length:
        return slug

    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
    prefix_length = max_length - len(digest) - 1
    return f"{slug[:prefix_length].rstrip('-')}-{digest}"


def build_slugs(title: str, locale: str) -> dict:
    """Return {"en-us": "some-slug"} for use in the product `slugs` field."""
    return {locale: slugify(title)}


def build_url(title: str, category: Optional[str], locale: str) -> dict:
    """Return {"en-us": "/category/some-slug"} for use in the `urls` field."""
    category_slug = slugify(category) if category else "products"
    return {locale: f"/{category_slug}/{slugify(title)}"}

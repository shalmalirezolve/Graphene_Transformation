"""
Pipeline configuration.

PipelineConfig is the single source of truth that makes this pipeline generic:
swap out `fields` to support any source schema without touching transformation logic.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _image_url(value: Any) -> Any:
    image = _first(value)
    return image.get("uri") if isinstance(image, dict) else image


def _image_urls(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [image["uri"] for image in value if isinstance(image, dict) and image.get("uri")]


def _price(value: Any) -> Any:
    return value.get("price") if isinstance(value, dict) else value


def _category_parts(value: Any) -> List[str]:
    if not isinstance(value, list) or not value:
        return []
    return [part.strip() for part in str(value[0]).split(">") if part.strip()]


def _category_level(level: int) -> Callable[[Any], Any]:
    def extract(value: Any) -> Any:
        parts = _category_parts(value)
        return parts[level] if len(parts) > level else None
    return extract


def _category_leaves(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    leaves = []
    for path in value:
        parts = [part.strip() for part in str(path).split(">") if part.strip()]
        if parts and parts[-1] not in leaves:
            leaves.append(parts[-1])
    return leaves


@dataclass
class FieldDef:
    """
    Maps a canonical field name to one or more source field names.

    source  — source field name, or list tried left-to-right until a non-empty value is found
    transform — optional callable applied to the extracted value
    default — value used when all source fields are absent / empty
    """
    source: Union[str, List[str]]
    transform: Optional[Callable[[Any], Any]] = None
    default: Any = None


@dataclass
class PipelineConfig:
    # ── Output settings ─────────────────────────────────────────────────────
    locale: str = "en-us"
    currencies: List[str] = field(default_factory=lambda: ["USD"])
    output_format: str = "json"          # "json" (array) | "ndjson" (one line per record)

    # ── Field mappings ───────────────────────────────────────────────────────
    # Canonical name → how to read it from the source record
    fields: Dict[str, FieldDef] = field(default_factory=dict)

    # ── Category / product-type resolution ───────────────────────────────────
    # Maps raw source category strings → target category_id slugs
    category_map: Dict[str, str] = field(default_factory=dict)
    # Maps top-level category → product_type_id
    product_type_map: Dict[str, str] = field(default_factory=dict)

    # ── Stock logic ──────────────────────────────────────────────────────────
    # Any of these values (case-insensitive) means the product is enabled
    in_stock_values: List[str] = field(default_factory=lambda: [
        "in stock", "instock", "in_stock", "low stock", "low_stock",
        "available", "true", "1", "yes",
    ])

    # ── Runtime ──────────────────────────────────────────────────────────────
    batch_size: int = 1000   # how often to print progress
    skip_invalid: bool = True


# ── Built-in source configuration: Fashion_merged.json ───────────────────────

FASHION_MERGED_CONFIG = PipelineConfig(
    locale="en-us",
    currencies=["USD"],
    fields={
        # Identity
        "id":                FieldDef(source="product_id"),
        # Core content
        "title":             FieldDef(source="title"),
        "description":       FieldDef(source="description"),
        "care_instructions": FieldDef(source="care_instructions"),
        # Media
        "main_image":        FieldDef(source="main_image_url"),
        "additional_images": FieldDef(source="additional_image_url", default=[]),
        # Pricing  (source: [{currency, value}] lists)
        "price":             FieldDef(source="price"),
        "original_price":    FieldDef(source="original_price"),
        # Variants
        "colors":            FieldDef(source="colors",  default=[]),
        "sizes":             FieldDef(source="sizes",   default=[]),
        # Attributes
        "brand":             FieldDef(source="brand"),
        "gender":            FieldDef(source="gender"),
        "material":          FieldDef(source="material"),
        # Stock
        "stock_status":      FieldDef(source="stock_status"),
        # Ratings
        "rating":            FieldDef(source="rating"),
        "review_count":      FieldDef(source="review_count"),
        # Taxonomy
        "top_category":      FieldDef(source="top_level_category"),
        "mid_category":      FieldDef(source="mid_level_category"),
        "base_category":     FieldDef(source="base_level_category"),
        "category":          FieldDef(source="category", default=[]),
    },
)


# ── Template for a custom source config ──────────────────────────────────────
# Copy this and adapt `source` values to match your source field names.

CUSTOM_SOURCE_TEMPLATE = PipelineConfig(
    locale="en-us",
    currencies=["USD", "GBP", "EUR"],
    fields={
        "id":                FieldDef(source="id"),
        "title":             FieldDef(source="name"),
        "description":       FieldDef(source="body_html"),
        "care_instructions": FieldDef(source="care_label"),
        "main_image":        FieldDef(source="image_url"),
        "additional_images": FieldDef(source="images", default=[]),
        "price":             FieldDef(source="price"),
        "original_price":    FieldDef(source="compare_at_price"),
        "colors":            FieldDef(source=["colors", "colour", "color"], default=[]),
        "sizes":             FieldDef(source=["sizes", "size_options"],   default=[]),
        "brand":             FieldDef(source=["brand", "vendor"]),
        "gender":            FieldDef(source="gender"),
        "material":          FieldDef(source=["material", "fabric"]),
        "stock_status":      FieldDef(source=["stock_status", "availability"]),
        "rating":            FieldDef(source=["rating", "average_rating"]),
        "review_count":      FieldDef(source=["review_count", "reviews_count"]),
        "top_category":      FieldDef(source=["product_type", "department"]),
        "mid_category":      FieldDef(source="subcategory"),
        "base_category":     FieldDef(source="sub_subcategory"),
        "category":          FieldDef(source=["tags", "categories"], default=[]),
    },
    category_map={},       # e.g. {"Dresses": "dresses", "T-Shirts": "t-shirts"}
    product_type_map={},   # e.g. {"tops": "tops", "bottoms": "bottoms"}
)


# ── Built-in source configuration: automotive fitment NDJSON ────────────────

AUTOPARTS_FITMENT_CONFIG = PipelineConfig(
    locale="en-us",
    currencies=["USD"],
    fields={
        "id":                FieldDef(source="id"),
        "title":             FieldDef(source="title"),
        "description":       FieldDef(source="description"),
        "care_instructions": FieldDef(source="care_instructions"),
        "main_image":        FieldDef(source="images", transform=_image_url),
        "additional_images": FieldDef(source="images", transform=_image_urls, default=[]),
        "price":             FieldDef(source="priceInfo", transform=_price),
        "original_price":    FieldDef(source="original_price"),
        "colors":            FieldDef(source="colors", default=[]),
        "sizes":             FieldDef(source="sizes", default=[]),
        "brand":             FieldDef(source="brands", transform=_first),
        "gender":            FieldDef(source="gender"),
        "material":          FieldDef(source="material"),
        "stock_status":      FieldDef(source="availability"),
        "rating":            FieldDef(source="rating"),
        "review_count":      FieldDef(source="review_count"),
        "top_category":      FieldDef(source="categories", transform=_category_parts),
        "mid_category":      FieldDef(source="categories", transform=_category_level(1)),
        "base_category":     FieldDef(source="categories", transform=_category_level(2)),
        "category":          FieldDef(source="categories", transform=_category_leaves, default=[]),
        "fitment_attributes": FieldDef(source="attributes", default=[]),
    },
)

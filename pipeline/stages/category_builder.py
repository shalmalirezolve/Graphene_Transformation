"""
Category builder — Stage 3b.

GrapheneHC category tree structure (from devdocs schema):
  - Categories use `children.categories` (parent lists its children by id)
  - There is NO parent_id field — the tree is top-down, not bottom-up
  - A root node with id="$" is REQUIRED and must list all top-level children
  - Leaf categories have children.categories = []

Tree we build from the source data:
  $  (root — always required)
  ├── women               ← top_category_parts()[0]
  │   ├── fashion-tops    ← top_category_parts()[1]
  │   │   └── blouses     ← top_category_parts()[2]  or mid_category
  │   └── dresses
  ├── men
  └── ...  (category[] items are direct children of $ as well)
"""
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ..config import PipelineConfig
from ..ditmap import build_ditmap
from ..helpers.cleaners import top_category_parts
from ..helpers.slugify import slugify


def extract_and_build_categories(
    normalized_records: List[Dict],
    config: PipelineConfig,
) -> List[Dict]:
    """
    Build a complete category tree from product records.

    Returns a flat list starting with the "$" root, followed by all other
    category nodes, each containing `children.categories` and `children.products`.
    Products are assigned to their leaf (most-specific) category in the hierarchy.
    """
    names: Dict[str, str] = {}
    children: Dict[str, List[str]] = defaultdict(list)
    cat_products: Dict[str, List[str]] = defaultdict(list)

    def _add(cat_id: str, name: str, parent_id: str) -> None:
        if not cat_id:
            return
        if cat_id not in names:
            names[cat_id] = name
        if cat_id not in children[parent_id]:
            children[parent_id].append(cat_id)
        if cat_id not in children:
            children[cat_id] = []

    for record in normalized_records:
        product_id = str(record.get("id") or "")
        assigned: set = set()

        top_parts = top_category_parts(record.get("top_category"))
        parent = "$"
        last_top = "$"
        for part in top_parts:
            cid = config.category_map.get(part, slugify(part))
            _add(cid, part, parent)
            parent = cid
            last_top = cid

        mid_raw = record.get("mid_category")
        last_mid = last_top
        if mid_raw and str(mid_raw).strip():
            mid_name = str(mid_raw).strip()
            mid_id   = config.category_map.get(mid_name, slugify(mid_name))
            _add(mid_id, mid_name, last_top)
            last_mid = mid_id

        base_raw = record.get("base_category")
        leaf_cat = last_mid
        if base_raw and str(base_raw).strip():
            base_name = str(base_raw).strip()
            base_id   = config.category_map.get(base_name, slugify(base_name))
            _add(base_id, base_name, last_mid)
            leaf_cat = base_id

        # Assign product to its deepest hierarchy category
        if product_id and leaf_cat and leaf_cat != "$":
            cat_products[leaf_cat].append(product_id)
            assigned.add(leaf_cat)

        # category[] → direct children of $; also assign product there
        for cat in _clean_list(record.get("category")):
            cid = config.category_map.get(cat, slugify(cat))
            _add(cid, cat, "$")
            if product_id and cid not in assigned:
                cat_products[cid].append(product_id)
                assigned.add(cid)

    now = datetime.now(timezone.utc).isoformat()

    root = _build_root(children.get("$", []), config, now)

    result = [root]
    for cat_id, name in names.items():
        cat_children = children.get(cat_id, [])
        result.append(
            _build_category(cat_id, name, cat_children, cat_products.get(cat_id, []), config, now)
        )

    return result


# ── builders ──────────────────────────────────────────────────────────────────

def _build_root(top_level_ids: List[str], config: PipelineConfig, now: str) -> Dict:
    """Root category — id='$', not searchable, lists all top-level children."""
    locale = config.locale
    return {
        "id":                "$",
        "descriptions":      {},
        "titles":            {locale: {"default": "All Categories"}},
        "media":             {},
        "abstracts":         {},
        "properties":        {},
        "enabled":           True,
        "include_in_search": False,
        "type":              "manual",
        "slugs":             {locale: "all"},
        "urls":              {locale: "/"},
        "meta":              {locale: {"title": "All Categories"}},
        "tags":              [],
        "created":           now,
        "modified":          now,
        "children": {
            "categories": [
                {"id": cid, "sequence": i + 1}
                for i, cid in enumerate(top_level_ids)
            ],
            "products": [],
            "pages":    [],
        },
    }


def _build_category(
    cat_id: str,
    title: str,
    child_ids: List[str],
    product_ids: List[str],
    config: PipelineConfig,
    now: str,
) -> Dict:
    """Build a single category node with its children list."""
    locale = config.locale

    pseudo_record = {
        "id":                cat_id,
        "title":             title,
        "description":       f"Browse our {title} collection.",
        "care_instructions": None,
        "main_image":        None,
        "additional_images": [],
        "rating":            None,
        "review_count":      None,
        "gender":            None,
        "material":          None,
        "colors":            [],
        "sizes":             [],
        "brand":             None,
    }

    ditmap = build_ditmap(pseudo_record, locale)

    return {
        **ditmap,
        "enabled":           True,
        "include_in_search": True,
        "type":              "manual",
        "slugs":             {locale: cat_id},
        "urls":              {locale: f"/{cat_id}"},
        "meta":              {locale: {"title": title}},
        "tags":              [cat_id],
        "created":           now,
        "modified":          now,
        "children": {
            "categories": [
                {"id": cid, "sequence": i + 1}
                for i, cid in enumerate(child_ids)
            ],
            "products": [
                {"id": pid, "sequence": i + 1}
                for i, pid in enumerate(product_ids)
            ],
            "pages":    [],
        },
    }


# ── private ───────────────────────────────────────────────────────────────────

def _clean_list(raw) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    return [str(v).strip() for v in raw if v and str(v).strip()]

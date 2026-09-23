# Fashion Data Pipeline — GrapheneHC (Advanced Commerce)

Transforms source JSON or NDJSON product data into a
GrapheneHC-compliant batch feed (4-file ZIP) ready for upload via the
Advanced Commerce Batch API.

---

## Folder Structure

```
graphene_pipeline/
├── run_pipeline.py          # Entry point — runs all stages
├── validate_feed.py         # Pre-upload validation against definitions
├── sample_feed.py           # Creates N% sample feed for test uploads
├── upload.py                # Packages output and uploads via Batch API
└── pipeline/
    ├── config.py            # Locale, currencies, in-stock values
    ├── ditmap.py            # DITMAP shared field builders
    ├── stages/
    │   ├── normalizer.py          # Stage 1: raw JSON → canonical fields
    │   ├── definitions_builder.py # Stage 2: attribute registry
    │   ├── product_builder.py     # Stage 3a: products.json
    │   └── category_builder.py   # Stage 3b: categories.json
    └── helpers/
        ├── features.py     # features[] + variants[] per product
        ├── cleaners.py     # Field cleaning utilities
        ├── slugify.py      # URL-safe slug generator
        ├── prices.py       # Price builder
        └── variants.py     # Variant + warehousing builder
```

---

## End-to-End Flow

```
Fashion_merged.json
        │
        ▼
[1] normalizer.py          — maps raw source fields to canonical names
        │
        ▼
[2] definitions_builder.py — scans all records, emits definitions.json
        │                    (product_types + attribute registry with options)
        ▼
[3a] product_builder.py    — builds products.json
        │                    (DITMAP + prices + features + variants + stock)
[3b] category_builder.py   — builds categories.json
        │                    (tree with children.products populated)
        ▼
     output/
       ├── products.json
       ├── categories.json
       ├── definitions.json
       └── pages.json
        │
        ▼
[4] validate_feed.py       — checks every hierarchy dimension & attribute_id
                             matches definitions exactly (run before upload)
        │
        ▼
[5] upload.py              — ZIPs the 4 files → POST /batch/file/full
                             → PUT /batch/process/{receipt_id}
```

---

## Quick Start

### 1. Run the full pipeline
```bash
python run_pipeline.py migratedImages_gbi_partNumber_CTNAPAsani_fitment_sample_10000.ndjson --output-dir sample_output
```

The automotive NDJSON mapping reads `id`, `title`, `description`, `brands`,
`images`, `priceInfo`, `availability`, and hierarchical `categories` fields.
The original input file is not modified.

### 2. Validate output
```bash
python validate_feed.py --dir output --verbose
```

### 3. Validate the generated sample
```bash
python validate_feed.py --dir sample_output
```

### 4. Upload later, when ready
```bash
python upload.py --output-dir sample_output
```

---

## GrapheneHC Schema Notes

| Concept | Rule |
|---------|------|
| `published` | Must be ISO datetime string (`2026-08-14T09:19:15+00:00`), not boolean |
| `stock` | Top-level integer: `1` = in stock, `0` = out of stock |
| Category ↔ Product | Relationships on the **category** side via `children.products[].id` |
| `features[]` hierarchy | `[dimension_id, option_id]` — both must match entries in `definitions.json` |
| `variants[]` hierarchy | `[color_id, color_value, size_id, size_value]` flat list |
| Attribute IDs | Always underscored: `stock_status`, `review_count`, `material_percentage` |
| Color / Size | Live in `variants[].hierarchy` only — **not** duplicated in `features[]` |
| Root category `$` | Required first entry; lists all top-level category IDs as children |

---

## Batch API

| Step | Method | Endpoint |
|------|--------|----------|
| Upload ZIP | `POST` | `/batch/file/full` |
| Trigger processing | `PUT` | `/batch/process/{receipt_id}` |

Auth: `Basic base64(api_key:api_secret)`

---

## Requirements

```
Python 3.9+
```

No third-party dependencies — standard library only.

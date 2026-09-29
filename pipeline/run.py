"""Command-line runner for the feed transformation stages."""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterator, List

from .config import AUTOPARTS_FITMENT_CONFIG, FASHION_MERGED_CONFIG, SHOPIFY_CONFIG, PipelineConfig
from .stages.category_builder import extract_and_build_categories
from .stages.definitions_builder import build_definitions
from .stages.normalizer import normalize_batch
from .stages.product_builder import build_product


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_price(value: object) -> float:
    text = _clean(value).replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _load_records(path: Path) -> List[Dict]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raise ValueError("Input JSON must be an array or an object containing a data array")


def _load_shopify_records(path: Path) -> List[Dict]:
    csv_paths = sorted(path.glob("*.csv")) if path.is_dir() else [path]
    if not csv_paths:
        raise ValueError(f"No Shopify CSV files found in: {path}")

    products: Dict[str, Dict] = {}
    for csv_path in csv_paths:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                handle = _clean(row.get("Handle"))
                if not handle:
                    continue

                product = products.setdefault(
                    handle,
                    {
                        "id": handle,
                        "title": "",
                        "description": "",
                        "brand": "",
                        "colors": [],
                        "sizes": [],
                        "images": [],
                        "categories": [],
                        "price": 0.0,
                        "compare_at_price": 0.0,
                        "availability": "in stock",
                        "gender": "",
                        "material": "",
                        "rating": 0,
                        "review_count": 0,
                    },
                )

                title = _clean(row.get("Title"))
                if title and not product["title"]:
                    product["title"] = title

                description = _clean(row.get("Body (HTML)"))
                if description and not product["description"]:
                    product["description"] = description

                vendor = _clean(row.get("Vendor"))
                if vendor and not product["brand"]:
                    product["brand"] = vendor

                product_category = _clean(row.get("Product Category"))
                if product_category and product_category not in product["categories"]:
                    product["categories"].append(product_category)

                product_type = _clean(row.get("Type"))
                if product_type and product_type not in product["categories"]:
                    product["categories"].append(product_type)

                for tag in [item.strip() for item in (_clean(row.get("Tags")).split(",")) if item.strip()]:
                    if tag and tag not in product["categories"]:
                        product["categories"].append(tag)

                image_url = _clean(row.get("Image Src"))
                if image_url and image_url not in product["images"]:
                    product["images"].append(image_url)

                price = _parse_price(row.get("Variant Price"))
                if price and (not product["price"] or product["price"] == 0.0):
                    product["price"] = price

                compare_at = _parse_price(row.get("Variant Compare At Price"))
                if compare_at and (not product["compare_at_price"] or product["compare_at_price"] == 0.0):
                    product["compare_at_price"] = compare_at

                inventory_qty = _clean(row.get("Variant Inventory Qty"))
                if inventory_qty:
                    try:
                        qty = int(float(inventory_qty))
                    except ValueError:
                        qty = 0
                    if qty > 0:
                        product["availability"] = "in stock"

                status = _clean(row.get("Status")).lower()
                if status and status == "active":
                    product["availability"] = "in stock"
                elif status and status in {"draft", "archived"}:
                    product["availability"] = "out of stock"

    records: List[Dict] = []
    for product in products.values():
        category_path = product["categories"][:3]
        records.append({
            "id": product["id"],
            "title": product["title"] or product["id"],
            "description": product["description"] or product["title"],
            "brand": product["brand"],
            "images": product["images"],
            "categories": category_path,
            "price": product["price"],
            "compare_at_price": product["compare_at_price"],
            "availability": product["availability"],
            "colors": [],
            "sizes": [],
            "gender": "",
            "material": "",
            "rating": 0,
            "review_count": 0,
        })
    return records


def _iter_normalized(path: Path, config: PipelineConfig) -> Iterator[Dict]:
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            record = normalize_batch([json.loads(line)], config)[0]
            if record.get("id") and record.get("title"):
                yield record


def _write_products_streaming(path: Path, records: Iterator[Dict], config: PipelineConfig, chunk_size: int) -> int:
    count = 0
    first = True
    with path.open("w", encoding="utf-8") as file:
        file.write('{"data":[')
        batch = []
        for record in records:
            batch.append(record)
            if len(batch) < chunk_size:
                continue
            for normalized in batch:
                if not first:
                    file.write(",")
                json.dump(build_product(normalized, config), file, ensure_ascii=False, separators=(",", ":"))
                first = False
                count += 1
            batch.clear()
            print(f"Built {count:,} products...", flush=True)
        for normalized in batch:
            if not first:
                file.write(",")
            json.dump(build_product(normalized, config), file, ensure_ascii=False, separators=(",", ":"))
            first = False
            count += 1
        file.write("]}")
    return count


def _config_for(input_path: Path) -> PipelineConfig:
    if input_path.is_dir() or input_path.suffix.lower() == ".csv":
        return SHOPIFY_CONFIG
    if input_path.suffix.lower() in {".ndjson", ".jsonl"}:
        return AUTOPARTS_FITMENT_CONFIG
    return FASHION_MERGED_CONFIG


def _write_json(path: Path, payload: Dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform source data into a GrapheneHC feed")
    parser.add_argument("input", type=Path, help="Input JSON, NDJSON, CSV, or Shopify export folder")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--format", choices=["json", "ndjson"], default="json")
    parser.add_argument("--chunk-size", type=int, default=10_000, help="Products built per memory-bounded batch")
    parser.add_argument("--locale", help="Override output locale")
    parser.add_argument("--currencies", help="Comma-separated currencies, for example USD,GBP")
    args = parser.parse_args()

    if not (args.input.is_file() or args.input.is_dir()):
        parser.error(f"Input not found: {args.input}")

    config = _config_for(args.input)
    if args.locale:
        config.locale = args.locale
    if args.currencies:
        config.currencies = [currency.strip().upper() for currency in args.currencies.split(",") if currency.strip()]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input.is_dir() or args.input.suffix.lower() == ".csv":
        raw_records = _load_shopify_records(args.input)
        normalized = [record for record in normalize_batch(raw_records, config) if record.get("id") and record.get("title")]
        products = [build_product(record, config) for record in normalized]
        categories = extract_and_build_categories(normalized, config)
        definitions = build_definitions(normalized, config)
        _write_json(output_dir / "products.json", {"data": products})
        _write_json(output_dir / "categories.json", {"data": categories})
        _write_json(output_dir / "definitions.json", definitions)
        product_count = len(products)
    elif args.input.suffix.lower() in {".ndjson", ".jsonl"}:
        print("Building categories (streaming pass)...", flush=True)
        categories = extract_and_build_categories(_iter_normalized(args.input, config), config)
        print(f"Built {len(categories):,} categories.", flush=True)
        print("Building definitions (streaming pass)...", flush=True)
        definitions = build_definitions(_iter_normalized(args.input, config), config)
        print("Writing products (streaming pass)...", flush=True)
        product_count = _write_products_streaming(
            output_dir / "products.json",
            _iter_normalized(args.input, config),
            config,
            args.chunk_size,
        )
        _write_json(output_dir / "categories.json", {"data": categories})
        _write_json(output_dir / "definitions.json", definitions)
    else:
        raw_records = _load_records(args.input)
        normalized = [record for record in normalize_batch(raw_records, config) if record.get("id") and record.get("title")]
        products = [build_product(record, config) for record in normalized]
        categories = extract_and_build_categories(normalized, config)
        definitions = build_definitions(normalized, config)
        _write_json(output_dir / "products.json", {"data": products})
        _write_json(output_dir / "categories.json", {"data": categories})
        _write_json(output_dir / "definitions.json", definitions)
        product_count = len(products)

    _write_json(output_dir / "pages.json", {"data": []})

    print(f"Processed {product_count:,} products")
    print(f"Wrote output to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
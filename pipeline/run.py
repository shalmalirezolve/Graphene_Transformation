"""Command-line runner for the feed transformation stages."""

import argparse
import json
from pathlib import Path
from typing import Dict, Iterator, List

from .config import AUTOPARTS_FITMENT_CONFIG, FASHION_MERGED_CONFIG, PipelineConfig
from .stages.category_builder import extract_and_build_categories
from .stages.definitions_builder import build_definitions
from .stages.normalizer import normalize_batch
from .stages.product_builder import build_product


def _load_records(path: Path) -> List[Dict]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raise ValueError("Input JSON must be an array or an object containing a data array")


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
    if input_path.suffix.lower() in {".ndjson", ".jsonl"}:
        return AUTOPARTS_FITMENT_CONFIG
    return FASHION_MERGED_CONFIG


def _write_json(path: Path, payload: Dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform source data into a GrapheneHC feed")
    parser.add_argument("input", type=Path, help="Input JSON or NDJSON file")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--format", choices=["json", "ndjson"], default="json")
    parser.add_argument("--chunk-size", type=int, default=10_000, help="Products built per memory-bounded batch")
    parser.add_argument("--locale", help="Override output locale")
    parser.add_argument("--currencies", help="Comma-separated currencies, for example USD,GBP")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"Input file not found: {args.input}")

    config = _config_for(args.input)
    if args.locale:
        config.locale = args.locale
    if args.currencies:
        config.currencies = [currency.strip().upper() for currency in args.currencies.split(",") if currency.strip()]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input.suffix.lower() in {".ndjson", ".jsonl"}:
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
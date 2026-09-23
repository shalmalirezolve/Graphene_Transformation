"""Find products by nested fitment attributes in an NDJSON feed.

Examples:
    python find_fitment.py input.ndjson --key ymm_1 --value all_all_all
    python find_fitment.py input.ndjson --key ymm_1 --value 1_38_5_2012 --full
    python find_fitment.py input.ndjson --key ymm_1 --value ymm2 --output matches.ndjson
"""

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


def values_from_attribute(attribute: dict) -> Iterable[str]:
    """Yield text values from an attribute's nested value object."""
    value = attribute.get("value", {})
    text = value.get("text", []) if isinstance(value, dict) else value
    if isinstance(text, list):
        yield from (str(item) for item in text)
    elif text is not None:
        yield str(text)


def matches(record: dict, key: str, wanted: str) -> bool:
    for attribute in record.get("attributes", []):
        if attribute.get("key") == key:
            wanted_normalized = wanted.casefold()
            return any(value.casefold() == wanted_normalized for value in values_from_attribute(attribute))
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Find products by fitment attribute")
    parser.add_argument("source", type=Path, help="Input NDJSON file")
    parser.add_argument("--key", required=True, help="Attribute key, for example ymm_1")
    parser.add_argument("--value", required=True, help="Exact attribute value, for example all_all_all")
    parser.add_argument("--full", action="store_true", help="Print complete matching records")
    parser.add_argument("--output", type=Path, help="Optional NDJSON output file")
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error(f"Input file not found: {args.source}")

    matches_found = 0
    output_file = args.output.open("w", encoding="utf-8") if args.output else None
    try:
        with args.source.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                record = json.loads(line)
                if not matches(record, args.key, args.value):
                    continue

                matches_found += 1
                if output_file:
                    output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                elif args.full:
                    print(json.dumps(record, indent=2, ensure_ascii=False))
                else:
                    print(record.get("id", ""))
    finally:
        if output_file:
            output_file.close()

    destination = f" in {args.output}" if args.output else ""
    print(f"Matches: {matches_found:,}{destination}")


if __name__ == "__main__":
    main()

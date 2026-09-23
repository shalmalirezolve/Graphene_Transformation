"""
Pre-upload validation: checks that every hierarchy dimension, attribute_id,
and option value in products.json exactly matches the attribute IDs and
option IDs registered in definitions.json.

Rule (from GrapheneHC schema):
  attribute_id  == hierarchy[0]       (dimension name must match attribute ID)
  option_id     == hierarchy[1]       (option value must match option ID)

Run this BEFORE upload.py to catch mismatches early.

Usage:
    python validate_feed.py                    # validates output/
    python validate_feed.py --dir sample_output
    python validate_feed.py --dir output --verbose
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def iter_products(path: Path):
    """Stream product objects from the top-level {"data": [...]} payload."""
    decoder = json.JSONDecoder()
    with path.open(encoding="utf-8") as file:
        buffer = ""
        started = False
        finished = False

        while not finished:
            chunk = file.read(1024 * 1024)
            if chunk:
                buffer += chunk
            elif not buffer:
                break

            while True:
                buffer = buffer.lstrip()
                if not started:
                    data_start = buffer.find("\"data\"")
                    if data_start < 0:
                        if chunk:
                            break
                        raise ValueError(f"Missing data array in {path}")
                    array_start = buffer.find("[", data_start)
                    if array_start < 0:
                        break
                    buffer = buffer[array_start + 1:]
                    started = True

                buffer = buffer.lstrip()
                if buffer.startswith("]"):
                    return
                if buffer.startswith(","):
                    buffer = buffer[1:].lstrip()
                if not buffer:
                    break

                try:
                    product, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    break
                yield product
                buffer = buffer[end:]

            if not chunk:
                raise ValueError(f"Unexpected end of products array in {path}")


def main():
    parser = argparse.ArgumentParser(description="Validate feed against definitions")
    parser.add_argument("--dir",     default="output", help="Feed directory (default: output)")
    parser.add_argument("--verbose", action="store_true", help="Print every failing product ID")
    args = parser.parse_args()

    d = Path(args.dir)

    # ── Load definitions ──────────────────────────────────────────────────────
    def_path = d / "definitions.json"
    if not def_path.exists():
        print(f"ERROR: {def_path} not found")
        sys.exit(1)

    attrs = load(def_path)["data"]["attributes"]
    valid_attr_ids = {a["id"] for a in attrs}
    attr_options: dict = {}
    for a in attrs:
        opts = a.get("options") or []
        if opts:
            attr_options[a["id"]] = {o["id"] for o in opts}

    print(f"Definitions loaded: {len(valid_attr_ids)} attributes")
    print(f"  IDs: {sorted(valid_attr_ids)}")
    print()

    # ── Load products ─────────────────────────────────────────────────────────
    prod_path = d / "products.json"
    if not prod_path.exists():
        print(f"ERROR: {prod_path} not found")
        sys.exit(1)

    products = iter_products(prod_path)
    print()

    # ── Validate ──────────────────────────────────────────────────────────────
    # issues[description] = [product_id, ...]
    issues: dict = defaultdict(list)

    product_count = 0
    started_at = time.monotonic()
    for product in products:
        product_count += 1
        if product_count % 10_000 == 0:
            elapsed = time.monotonic() - started_at
            rate = product_count / elapsed if elapsed else 0
            print(
                f"Validated {product_count:,} products "
                f"({rate:,.0f}/sec)...",
                flush=True,
            )
        pid = str(product.get("id", "?"))

        # -- Features --
        for feat in product.get("features", []):

            if "hierarchy" in feat:
                h = feat["hierarchy"]
                if not isinstance(h, list) or len(h) < 2:
                    issues[f"hierarchy wrong format (not a 2-element list)"].append(pid)
                    continue
                dim, opt = h[0], h[1]

                if dim not in valid_attr_ids:
                    issues[f"unknown hierarchy dimension '{dim}'"].append(pid)
                elif dim in attr_options and opt not in attr_options[dim]:
                    issues[f"unknown option '{opt}' for dimension '{dim}'"].append(pid)

            elif "attribute_id" in feat:
                aid = feat["attribute_id"]
                if aid not in valid_attr_ids:
                    issues[f"unknown attribute_id '{aid}'"].append(pid)

            else:
                issues["feature entry has neither 'hierarchy' nor 'attribute_id'"].append(pid)

        # -- Variants --
        for variant in product.get("variants", []):
            h = variant.get("hierarchy", [])
            if not isinstance(h, list):
                issues[f"variant hierarchy not a list"].append(pid)
                continue
            for i in range(0, len(h) - 1, 2):
                dim, opt = h[i], h[i + 1]
                if dim not in valid_attr_ids:
                    issues[f"unknown variant dimension '{dim}'"].append(pid)
                elif dim in attr_options and opt not in attr_options[dim]:
                    issues[f"unknown variant option '{opt}' for dimension '{dim}'"].append(pid)

    # ── Report ────────────────────────────────────────────────────────────────
    if not issues:
        print("=" * 55)
        print("VALID — no mismatches found")
        print(f"  {product_count:,} products passed")
        print("=" * 55)
        sys.exit(0)

    print("=" * 55)
    print(f"ISSUES FOUND — {sum(len(v) for v in issues.values())} total across {len(issues)} rule(s)")
    print("=" * 55)
    for desc, pids in sorted(issues.items(), key=lambda x: -len(x[1])):
        unique = len(set(pids))
        print(f"\n  [{unique:,} products]  {desc}")
        if args.verbose:
            for pid in sorted(set(pids))[:10]:
                print(f"    - {pid}")
            if unique > 10:
                print(f"    ... and {unique - 10} more")

    print()
    print("Fix the pipeline code, re-run, then validate again before uploading.")
    sys.exit(1)


if __name__ == "__main__":
    main()

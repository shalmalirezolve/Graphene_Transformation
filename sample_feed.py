"""
Create a reduced sample feed for validation testing.

Reads from output/ (full pipeline output), takes a random N% of products,
filters each category's children.products to only the sampled IDs, then
writes the result to sample_output/. definitions.json and pages.json are
copied in full — they are always required in a full sync.

Usage:
    python sample_feed.py                              # 5% sample → sample_output/
    python sample_feed.py --pct 10                     # 10% sample
    python sample_feed.py --src output --dst sample_output --pct 5 --seed 42

Then upload the sample:
    python upload.py --output-dir sample_output
"""

import argparse
import json
import random
import shutil
from pathlib import Path


def sample_feed(src_dir: str, dst_dir: str, pct: float, seed: int) -> None:
    src = Path(src_dir)
    dst = Path(dst_dir)
    dst.mkdir(exist_ok=True)

    # ── Products ──────────────────────────────────────────────────────────────
    print(f"Reading {src / 'products.json'} ...")
    with open(src / "products.json", encoding="utf-8") as f:
        products_payload = json.load(f)

    all_products = products_payload["data"]
    n_sample = max(1, int(len(all_products) * pct / 100))
    rng = random.Random(seed)
    sampled = rng.sample(all_products, n_sample)
    sampled_ids = {str(p["id"]) for p in sampled}

    print(f"  {len(all_products):,} total  →  {n_sample:,} sampled ({pct}%)")

    with open(dst / "products.json", "w", encoding="utf-8") as f:
        json.dump({"data": sampled}, f, ensure_ascii=False)
    size_kb = (dst / "products.json").stat().st_size / 1024
    print(f"  Written products.json  ({size_kb:,.0f} KB)")

    # ── Categories ────────────────────────────────────────────────────────────
    print(f"Reading {src / 'categories.json'} ...")
    with open(src / "categories.json", encoding="utf-8") as f:
        categories_payload = json.load(f)

    filtered_cats = []
    for cat in categories_payload["data"]:
        cat = dict(cat)
        children = dict(cat.get("children", {}))
        # Keep only the sampled products in each category's children.products
        children["products"] = [
            p for p in children.get("products", [])
            if str(p["id"]) in sampled_ids
        ]
        cat["children"] = children
        filtered_cats.append(cat)

    with open(dst / "categories.json", "w", encoding="utf-8") as f:
        json.dump({"data": filtered_cats}, f, ensure_ascii=False)
    size_kb = (dst / "categories.json").stat().st_size / 1024
    print(f"  Written categories.json  ({size_kb:,.0f} KB, {len(filtered_cats):,} categories)")

    # ── Definitions and pages — always full copy ───────────────────────────────
    for name in ("definitions.json", "pages.json"):
        src_file = src / name
        if src_file.exists():
            shutil.copy2(src_file, dst / name)
            size_kb = (dst / name).stat().st_size / 1024
            print(f"  Copied {name}  ({size_kb:,.0f} KB)")
        else:
            print(f"  WARN: {name} not found in {src_dir}, skipping")

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print(f"Sample feed ready in:  {dst.resolve()}")
    print(f"  Products   : {n_sample:,}  ({pct}% of {len(all_products):,})")
    print(f"  Categories : {len(filtered_cats):,}  (full tree, children filtered to sample)")
    print()
    print("To upload:")
    print(f"  python upload.py --output-dir {dst_dir}")
    print("=" * 55)


def main():
    parser = argparse.ArgumentParser(
        description="Create a % sample of the pipeline output for test uploads"
    )
    parser.add_argument("--pct",  type=float, default=5.0,         help="Percentage of products to sample (default 5)")
    parser.add_argument("--seed", type=int,   default=42,          help="Random seed for reproducibility (default 42)")
    parser.add_argument("--src",  default="output",                 help="Source directory (default: output)")
    parser.add_argument("--dst",  default="sample_output",          help="Destination directory (default: sample_output)")
    args = parser.parse_args()
    sample_feed(args.src, args.dst, args.pct, args.seed)


if __name__ == "__main__":
    main()

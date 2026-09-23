"""
Take a random sample from an NDJSON file without loading the full file.

Usage:
    python sample_ndjson.py migratedImages_gbi_partNumber_CTNAPAsani_fitment.ndjson
    python sample_ndjson.py input.ndjson --count 10000 --seed 42 --output sample.ndjson
"""

import argparse
import random
from pathlib import Path


def reservoir_sample(source: Path, count: int, seed: int) -> list[str]:
    """Return a uniform random sample of non-empty NDJSON lines."""
    rng = random.Random(seed)
    sample: list[str] = []
    records_seen = 0

    with source.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            records_seen += 1
            if len(sample) < count:
                sample.append(line.rstrip("\r\n"))
            else:
                replacement_index = rng.randrange(records_seen)
                if replacement_index < count:
                    sample[replacement_index] = line.rstrip("\r\n")

    if records_seen < count:
        raise ValueError(
            f"The input contains only {records_seen:,} records; "
            f"cannot sample {count:,}."
        )

    return sample


def main() -> None:
    parser = argparse.ArgumentParser(description="Randomly sample records from an NDJSON file")
    parser.add_argument("source", type=Path, help="Input NDJSON file")
    parser.add_argument("--count", type=int, default=10_000, help="Number of records (default: 10000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--output", type=Path, help="Output file (default: <source>_sample_<count>.ndjson)")
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1")
    if not args.source.is_file():
        parser.error(f"Input file not found: {args.source}")

    output = args.output or args.source.with_name(
        f"{args.source.stem}_sample_{args.count}.ndjson"
    )
    records = reservoir_sample(args.source, args.count, args.seed)
    output.write_text("\n".join(records) + "\n", encoding="utf-8")

    print(f"Wrote {len(records):,} records to {output}")
    print(f"Seed: {args.seed}")


if __name__ == "__main__":
    main()

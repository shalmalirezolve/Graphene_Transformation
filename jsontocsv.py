import json
import csv
import os

# ============================================================
# CONFIG
# ============================================================

JSON_FILE = r"C:\Users\HP\Downloads\top10_v3.json"
CSV_FILE = r"C:\Users\HP\Downloads\top10_v3.csv"


# ============================================================
# CHECK INPUT FILE
# ============================================================

print("=" * 60)
print("JSON → CSV CONVERTER")
print("=" * 60)

print(f"Input : {JSON_FILE}")
print(f"Output: {CSV_FILE}")
print()


if not os.path.exists(JSON_FILE):
    print("ERROR: JSON file does not exist.")
    print(f"Check this path:\n{JSON_FILE}")
    exit(1)


file_size = os.path.getsize(JSON_FILE)

print(f"Input file size: {file_size:,} bytes")

if file_size == 0:
    print()
    print("ERROR: The JSON file is EMPTY.")
    print("There is nothing to convert.")
    exit(1)


# ============================================================
# READ FILE
# ============================================================

with open(JSON_FILE, "r", encoding="utf-8-sig") as f:
    content = f.read()


# Remove BOM / whitespace
content = content.strip()


if not content:
    print()
    print("ERROR: The JSON file contains no data.")
    exit(1)


# ============================================================
# TRY NORMAL JSON FIRST
# ============================================================

data = None

try:
    data = json.loads(content)

    print("Detected format: Normal JSON")

except json.JSONDecodeError as normal_json_error:

    print("Normal JSON parsing failed.")
    print("Trying JSONL / NDJSON format...")

    # ========================================================
    # TRY JSONL / NDJSON
    # ========================================================

    jsonl_data = []
    invalid_lines = []

    lines = content.splitlines()

    for line_number, line in enumerate(lines, start=1):

        line = line.strip()

        if not line:
            continue

        try:
            item = json.loads(line)
            jsonl_data.append(item)

        except json.JSONDecodeError:
            invalid_lines.append(line_number)

    if jsonl_data:
        data = jsonl_data

        print("Detected format: JSONL / NDJSON")

        if invalid_lines:
            print(
                f"WARNING: {len(invalid_lines)} invalid "
                f"line(s) were skipped."
            )

            print(
                "Invalid line numbers:",
                invalid_lines[:20]
            )

            if len(invalid_lines) > 20:
                print("...and more")

    else:

        print()
        print("=" * 60)
        print("ERROR: FILE IS NOT VALID JSON")
        print("=" * 60)

        print()
        print("Original JSON error:")
        print(normal_json_error)

        print()
        print("First 500 characters of the file:")
        print("-" * 60)
        print(repr(content[:500]))
        print("-" * 60)

        print()
        print(
            "Possible reasons:"
        )
        print("1. The file is empty.")
        print("2. The file contains plain text.")
        print("3. The file is incomplete/corrupted.")
        print("4. The file is JSONL but contains invalid lines.")
        print("5. The file contains an error message instead of JSON.")

        exit(1)


# ============================================================
# NORMALIZE DATA
# ============================================================

if isinstance(data, dict):

    # Single JSON object
    data = [data]

elif isinstance(data, list):

    # Already a list
    pass

else:

    print()
    print("ERROR: Unsupported JSON structure.")
    print(
        "Expected a JSON object or JSON array, "
        f"but got: {type(data).__name__}"
    )
    exit(1)


# ============================================================
# REMOVE NON-DICT ITEMS
# ============================================================

valid_data = []
skipped_items = 0

for item in data:

    if isinstance(item, dict):
        valid_data.append(item)

    else:
        skipped_items += 1


data = valid_data


if not data:

    print()
    print("ERROR: No JSON objects were found.")
    exit(1)


# ============================================================
# GET ALL COLUMNS
# ============================================================

columns = []

seen_columns = set()

for item in data:

    for key in item.keys():

        if key not in seen_columns:

            seen_columns.add(key)
            columns.append(key)


# ============================================================
# CONVERT NESTED VALUES TO CSV-SAFE TEXT
# ============================================================

def make_csv_safe(value):

    if value is None:
        return ""

    if isinstance(value, (dict, list)):

        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":")
        )

    # Handle other unusual Python values
    if isinstance(value, bool):
        return str(value).lower()

    return value


# ============================================================
# CREATE OUTPUT DIRECTORY IF REQUIRED
# ============================================================

output_directory = os.path.dirname(CSV_FILE)

if output_directory:
    os.makedirs(output_directory, exist_ok=True)


# ============================================================
# WRITE CSV
# ============================================================

with open(
    CSV_FILE,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=columns,
        extrasaction="ignore"
    )

    writer.writeheader()

    for item in data:

        clean_item = {
            key: make_csv_safe(item.get(key, ""))
            for key in columns
        }

        writer.writerow(clean_item)


# ============================================================
# VERIFY OUTPUT
# ============================================================

output_size = os.path.getsize(CSV_FILE)


# ============================================================
# DONE
# ============================================================

print()
print("=" * 60)
print("JSON → CSV COMPLETED SUCCESSFULLY")
print("=" * 60)

print(f"Input file       : {JSON_FILE}")
print(f"Output file      : {CSV_FILE}")
print(f"Input size       : {file_size:,} bytes")
print(f"Output size      : {output_size:,} bytes")
print(f"Rows             : {len(data):,}")
print(f"Columns          : {len(columns):,}")

if skipped_items:
    print(f"Skipped items    : {skipped_items:,}")

if invalid_lines:
    print(f"Invalid JSONL    : {len(invalid_lines):,} lines")

print()
print("Columns:")
for i, column in enumerate(columns, start=1):
    print(f"  {i}. {column}")

print()
print("CSV created successfully.")
print("=" * 60)
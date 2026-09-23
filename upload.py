"""
GrapheneHC Batch Upload
Reads the 4 output files produced by the pipeline, zips them,
and uploads to the GrapheneHC Batch API.

Usage:
    python upload.py
    python upload.py --output-dir output --type full
    python upload.py --type delta

Steps:
    [1/4] Load output files
    [2/4] Preview counts
    [3/4] Build ZIP and POST to /batch/upload/{type}
    [4/4] Trigger processing  PUT  /batch/process/{receipt_id}

Auth:
    Get API_KEY and API_SECRET from:
    Console → Settings → API Access → Admin API
"""

import argparse
import base64
import io
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import requests  # pip install requests


# ── CONFIG — fill these in before running ─────────────────────────────────────
API_KEY    = "cb4e25115c734f84b0376945e3f2a609"
API_SECRET = "b/dFAgrUv22jLwARU7ilwFpTbWGbcvCGsFzj1BDEMk2LElwlqdfAeT+so5WhZGm2"
API_BASE   = "https://rezolvedemo4.api.advancedcommerce.services"
# ─────────────────────────────────────────────────────────────────────────────


FILES_TO_ZIP = [
    "products.json",
    "categories.json",
    "definitions.json",
    "pages.json",
]


# ── Auth ──────────────────────────────────────────────────────────────────────

def _auth_header(api_key: str, api_secret: str) -> dict:
    """Basic Auth: base64(api_key:api_secret) — GrapheneHC format confirmed by probe."""
    token = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ── Step 1: Load output files ─────────────────────────────────────────────────

def load_output_files(output_dir: Path) -> dict:
    """
    Read the 4 JSON files from output_dir.
    Returns {filename: raw_bytes} — the exact bytes that go into the ZIP.
    """
    loaded = {}
    for name in FILES_TO_ZIP:
        path = output_dir / name
        if not path.exists():
            raise FileNotFoundError(
                f"Missing output file: {path}\n"
                f"Run the pipeline first:  python run_pipeline.py Fashion_merged.json"
            )
        loaded[name] = path.read_bytes()
        kb = len(loaded[name]) / 1024
        print(f"  {name:<22}  {kb:,.0f} KB")
    return loaded


# ── Step 2: Preview ───────────────────────────────────────────────────────────

def preview_counts(file_bytes: dict) -> dict:
    """Parse each file and return record counts."""
    counts = {}
    for name, raw in file_bytes.items():
        try:
            doc = json.loads(raw)
            data = doc.get("data", doc)
            if isinstance(data, list):
                counts[name] = len(data)
            elif isinstance(data, dict):
                # definitions.json
                counts[name] = {
                    k: len(v) for k, v in data.items() if isinstance(v, list)
                }
            else:
                counts[name] = 1
        except Exception:
            counts[name] = "?"
    return counts


# ── Step 3: Build ZIP and upload ──────────────────────────────────────────────

def build_zip(file_bytes: dict) -> bytes:
    """Pack all 4 files into an in-memory ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, raw in file_bytes.items():
            zf.writestr(name, raw)
    return buf.getvalue()


def upload_zip(zip_bytes: bytes, upload_type: str, headers: dict) -> str:
    """
    POST /batch/upload/{upload_type}
    Returns the receipt_id from the response.
    """
    url = f"{API_BASE}/batch/upload/{upload_type}"
    print(f"  URL:  {url}")
    print(f"  Size: {len(zip_bytes)/1024:,.0f} KB")

    response = None
    for attempt in range(1, 4):
        try:
            response = requests.post(
                url,
                headers=headers,
                files={"": ("batch.zip", zip_bytes, "application/zip")},
                timeout=(30, 1800),
            )
            break
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.SSLError,
        ) as error:
            if attempt == 3:
                raise RuntimeError(
                    "Upload failed after 3 attempts. "
                    "The API connection was interrupted while sending the ZIP."
                ) from error
            delay = attempt * 10
            print(f"  Upload interrupted ({type(error).__name__}); retrying in {delay}s...", flush=True)
            time.sleep(delay)

    assert response is not None

    print(f"  HTTP: {response.status_code}")
    print(f"  Body ({len(response.text)} chars): {response.text[:300] or '(empty)'}")
    print(f"  Headers: { {k:v for k,v in response.headers.items() if k.lower() in ('content-type','location','x-receipt-id','x-request-id')} }")

    if not response.ok:
        raise RuntimeError(
            f"Upload failed {response.status_code}: {response.text[:500]}"
        )

    # Parse body if non-empty, otherwise check headers for receipt
    body = {}
    if response.text.strip():
        try:
            body = response.json()
        except Exception:
            print(f"  WARN: response is not JSON: {response.text[:200]}")

    receipt_id = (
        (body.get("data") or {}).get("receipt")
        or body.get("receipt_id")
        or body.get("receiptId")
        or body.get("receipt")
        or body.get("id")
        or response.headers.get("X-Receipt-ID")
        or response.headers.get("Location", "").rstrip("/").split("/")[-1] or None
    )
    if not receipt_id:
        raise RuntimeError(
            f"No receipt_id found.\n"
            f"  Status: {response.status_code}\n"
            f"  Body:   {response.text[:300] or '(empty)'}\n"
            f"  Headers: {dict(response.headers)}"
        )

    return str(receipt_id)


def upload_zip_file(zip_path: Path, upload_type: str, headers: dict) -> str:
    """Stream an existing ZIP with curl to avoid a long in-memory multipart write."""
    url = f"{API_BASE}/batch/upload/{upload_type}"
    print(f"  URL:  {url}")
    print(f"  Size: {zip_path.stat().st_size / 1024:,.0f} KB")

    basic_auth = headers["Authorization"].removeprefix("Basic ")
    with tempfile.TemporaryDirectory() as temp_dir:
        body_path = Path(temp_dir) / "response.body"
        header_path = Path(temp_dir) / "response.headers"
        result = subprocess.run(
            [
                "curl.exe", "--fail-with-body", "--silent", "--show-error",
                "--connect-timeout", "30", "--max-time", "7200",
                "-H", f"Authorization: Basic {basic_auth}",
                "-F", f"=@{zip_path}",
                "-D", str(header_path), "-o", str(body_path),
                "-w", "%{http_code}", url,
            ],
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip()[-3:] if result.stdout.strip() else "???"
        body_text = body_path.read_text(encoding="utf-8", errors="replace") if body_path.exists() else ""
        if result.returncode:
            detail = result.stderr.strip() or body_text[:500]
            raise RuntimeError(f"Upload failed (curl exit {result.returncode}, HTTP {status}): {detail}")

    print(f"  HTTP: {status}")
    print(f"  Body ({len(body_text)} chars): {body_text[:300] or '(empty)'}")
    if int(status) >= 400:
        raise RuntimeError(f"Upload failed {status}: {body_text[:500]}")

    try:
        body = json.loads(body_text) if body_text.strip() else {}
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Upload returned non-JSON response: {body_text[:500]}") from error

    receipt_id = (
        (body.get("data") or {}).get("receipt")
        or body.get("receipt_id")
        or body.get("receiptId")
        or body.get("receipt")
        or body.get("id")
    )
    if not receipt_id:
        raise RuntimeError(f"No receipt_id found in response: {body_text[:500]}")
    return str(receipt_id)


# ── Step 4: Trigger processing ────────────────────────────────────────────────

def trigger_processing(receipt_id: str, headers: dict) -> dict:
    """
    PUT /batch/process/{receipt_id}
    Returns the full response body.
    """
    url = f"{API_BASE}/batch/process/{receipt_id}"
    print(f"  URL:  {url}")

    response = requests.put(url, headers=headers, timeout=60)
    print(f"  HTTP: {response.status_code}")

    if not response.ok:
        raise RuntimeError(
            f"Process trigger failed {response.status_code}: {response.text[:500]}"
        )

    return response.json()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Upload pipeline output to GrapheneHC")
    parser.add_argument("--output-dir", default="output", help="Directory with 4 JSON files")
    parser.add_argument("--type", default="full", choices=["full", "delta"],
                        help="full = replace everything  |  delta = update only")
    parser.add_argument("--api-key",    default=API_KEY)
    parser.add_argument("--api-secret", default=API_SECRET)
    parser.add_argument("--zip-file", metavar="FILE",
                        help="Upload an existing ZIP instead of rebuilding it from --output-dir")
    parser.add_argument("--build-zip",  metavar="FILE",
                        help="Build the ZIP and save to FILE, then stop (for manual console upload)")
    args = parser.parse_args()

    output_dir  = Path(args.output_dir)
    upload_type = args.type

    print("=" * 60)
    print(f"GrapheneHC Batch  [{upload_type.upper()}]")
    print("=" * 60)
    print(f"Output dir : {output_dir.resolve()}")
    print()

    if args.zip_file:
        zip_path = Path(args.zip_file)
        if not zip_path.exists():
            parser.error(f"ZIP file not found: {zip_path}")
        print(f"ZIP file    : {zip_path.resolve()}")
        print("[1/4] Loading existing ZIP...")
        zip_bytes = zip_path.read_bytes()
        print(f"  ZIP size: {len(zip_bytes)/1024:,.0f} KB")
    else:
        # Step 1
        print("[1/4] Loading output files...")
        file_bytes = load_output_files(output_dir)

        # Step 2
        print()
        print("[2/4] Preview:")
        counts = preview_counts(file_bytes)
        for name, c in counts.items():
            print(f"  {name:<22}  {c}")

        # Step 3 — build ZIP
        print()
        print("[3/4] Building ZIP...")
        zip_bytes = build_zip(file_bytes)
        print(f"  ZIP size: {len(zip_bytes)/1024:,.0f} KB")

    # If --build-zip: save to disk and stop (manual console upload)
    if args.build_zip:
        out_path = Path(args.build_zip)
        out_path.write_bytes(zip_bytes)
        print()
        print("=" * 60)
        print(f"ZIP saved to:  {out_path.resolve()}")
        print()
        print("Upload manually via the console:")
        print("  1. Open the console in your browser")
        print("  2. Go to Data > Batch Upload (or similar)")
        print(f"  3. Upload the file: {out_path.resolve()}")
        print("=" * 60)
        sys.exit(0)

    # Auto-upload via API
    if "YOUR_API" in args.api_key or "YOUR_API" in args.api_secret:
        print("ERROR: Set API_KEY and API_SECRET at the top of upload.py")
        sys.exit(1)

    headers   = _auth_header(args.api_key, args.api_secret)
    print(f"  API base: {API_BASE}")
    if args.zip_file:
        receipt_id = upload_zip_file(zip_path, upload_type, headers)
    else:
        receipt_id = upload_zip(zip_bytes, upload_type, headers)
    print(f"  Receipt:  {receipt_id}")

    # Step 4
    print()
    print("[4/4] Triggering processing...")
    result = trigger_processing(receipt_id, headers)

    print()
    print("=" * 60)
    print("DONE")
    print(f"  Status  : {result.get('status', result)}")
    print(f"  Receipt : {receipt_id}")
    if result.get("message"):
        print(f"  Message : {result['message']}")
    if result.get("stats"):
        print(f"  Stats   : {result['stats']}")
    print("=" * 60)


if __name__ == "__main__":
    main()

"""Download ~60 varied v2 PDFs from Drive via gws for Phase-1 OCR calibration.

Spreads across regions; uses Drive file size to pre-filter v1 (~2MB) vs v2 (~6.5MB)
BEFORE downloading. Confirms v2 by page_count==7 after download.
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import fitz

GWS = "/home/linuxbrew/.linuxbrew/bin/gws"
PDF_FILES_FOLDER = "1cBfpqWk98lQQkjOjAaZMYaFnJrp_xOZ-"
DEST = Path(__file__).resolve().parents[1] / "work_pdfs"
DEST.mkdir(parents=True, exist_ok=True)
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 60
PER_REGION = 5  # candidates listed per region


def gws_json(args, timeout=120):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {}


def region_folders():
    r = gws_json([GWS, "drive", "files", "list", "--params", json.dumps(
        {"pageSize": 50, "fields": "files(id,name)",
         "q": f"'{PDF_FILES_FOLDER}' in parents and mimeType='application/vnd.google-apps.folder'"})])
    return {f["name"]: f["id"] for f in r.get("files", [])}


def list_pdfs(folder_id, n):
    # request size so we can pre-filter v1 vs v2
    r = gws_json([GWS, "drive", "files", "list", "--params", json.dumps(
        {"pageSize": n, "fields": "files(id,name,size)",
         "q": f"'{folder_id}' in parents and name contains '.pdf'"})])
    return r.get("files", [])


def download(file_id, out):
    subprocess.run([GWS, "drive", "files", "get", "--params",
                    json.dumps({"fileId": file_id, "alt": "media"}),
                    "--output", str(out)], capture_output=True, text=True, timeout=240)


def main():
    regions = region_folders()
    order = sorted(regions, key=lambda x: int(x))
    print(f"regions: {order}")
    cands = []
    for name in order:
        for f in list_pdfs(regions[name], PER_REGION):
            size = int(f.get("size", 0))
            # pre-filter: keep likely-v2 (>4MB); skip likely-v1 (~2MB)
            if size and size < 4_000_000:
                continue
            cands.append((name, f["id"], f["name"]))
    random.seed(7)
    random.shuffle(cands)
    print(f"candidate v2-by-size: {len(cands)}")
    ok = 0
    for name, fid, fname in cands:
        if ok >= TARGET:
            break
        out = DEST / f"R{name}__{fname}"
        if out.exists() and out.stat().st_size > 1000:
            ok += 1
            continue
        download(fid, out)
        if not (out.exists() and out.stat().st_size > 1000):
            continue
        # confirm v2 by page count
        try:
            d = fitz.open(out); n = d.page_count; d.close()
        except Exception:
            out.unlink(missing_ok=True); continue
        if n != 7:
            out.unlink(missing_ok=True); continue
        ok += 1
        if ok % 10 == 0:
            print(f"  downloaded v2: {ok}/{TARGET}")
    print(f"DONE: {ok} v2 PDFs in {DEST}")


if __name__ == "__main__":
    main()

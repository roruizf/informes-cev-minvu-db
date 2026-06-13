"""Detect CEV report version. v2 = 7 pages, v1 = 4 pages (Phase-0 verified).

File size is a cheap secondary signal (v1 ~2MB, v2 ~6.5MB) usable on Drive
metadata before download, but page_count is authoritative.
"""
import fitz


def detect_version(pdf_path) -> int:
    """Return 2 for v2 (7p), 1 for v1 (4p), 0 if unrecognized/unreadable."""
    try:
        doc = fitz.open(pdf_path)
        n = doc.page_count
        doc.close()
    except Exception:
        return 0
    if n == 7:
        return 2
    if n == 4:
        return 1
    return 0


def likely_v1_by_size(size_bytes: int) -> bool:
    """Pre-download heuristic: v1 PDFs are ~2MB, v2 ~6.5MB."""
    return 0 < size_bytes < 4_000_000

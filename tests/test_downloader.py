"""Unit tests for downloader._extract_pdf (the MINVU content-type/trailing-junk fix)."""
from informes_cev_minvu_db.pdf.downloader import _extract_pdf


def test_trims_trailing_html_after_eof():
    raw = b"%PDF-1.4\nbody bytes\n%%EOF\r\n<html>error fragment</html>"
    out = _extract_pdf(raw)
    assert out == b"%PDF-1.4\nbody bytes\n%%EOF"
    assert out.startswith(b"%PDF")
    assert out.endswith(b"%%EOF")


def test_no_pdf_returns_none():
    assert _extract_pdf(b"<html>portal error, no pdf here</html>") is None
    assert _extract_pdf(b"") is None


def test_no_eof_marker_best_effort():
    raw = b"junk%PDF-1.4 content without eof"
    out = _extract_pdf(raw)
    assert out == b"%PDF-1.4 content without eof"


def test_strips_leading_bytes_before_pdf():
    raw = b"\r\n\r\n%PDF-1.7 x %%EOF"
    assert _extract_pdf(raw) == b"%PDF-1.7 x %%EOF"


def test_keeps_last_eof_when_multiple():
    raw = b"%PDF-1.4 a %%EOF b %%EOF trailing"
    assert _extract_pdf(raw) == b"%PDF-1.4 a %%EOF b %%EOF"

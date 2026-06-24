"""Unit tests for downloader._extract_pdf (the MINVU content-type/trailing-junk fix)."""
from pathlib import Path
from types import SimpleNamespace

import informes_cev_minvu_db.pdf.downloader as DL
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


# ── Viewstate reuse: download_comuna_pdfs does 1 search + N postbacks ─────────

class _FakeClient:
    """Records the postback sequence; serves a valid PDF body each time."""
    def __init__(self):
        self.events = []
        self._vs = "vs"
        self._vsg = "vsg"

    # context manager (PortalClient.__enter__ calls load())
    def __enter__(self):
        self.events.append("load")
        return self

    def __exit__(self, *a):
        self.events.append("close")

    def _base_fields(self):
        return {}

    def select_region(self, region_id):
        self.events.append(("select_region", region_id))

    def search(self, region_id, comuna_id, tipo):
        self.events.append(("search", comuna_id))

    def _request(self, method, **kw):
        target = kw["data"]["__EVENTTARGET"]
        self.events.append(("post", target))
        return SimpleNamespace(status_code=200,
                               content=b"%PDF-1.4 " + b"x" * 2000 + b" %%EOF<html>junk")


def test_download_comuna_pdfs_reuses_one_search(monkeypatch, tmp_path):
    fake = _FakeClient()
    monkeypatch.setattr(DL, "PortalClient", lambda *a, **k: fake)

    rows = [SimpleNamespace(eval_id="a", codigo_informe="ctlA"),
            SimpleNamespace(eval_id="b", codigo_informe="ctlB"),
            SimpleNamespace(eval_id="c", codigo_informe=None)]  # no codigo → skipped

    res = DL.download_comuna_pdfs(rows, lambda eid: tmp_path / f"{eid}.pdf",
                                  region_id=10, comuna_id=100, tipo=2)

    assert res == {"a": True, "b": True, "c": False}
    # exactly ONE search for the whole comuna, then one postback per valid row
    assert sum(1 for e in fake.events if e[0] == "search") == 1
    posts = [e for e in fake.events if e[0] == "post"]
    assert [p[1] for p in posts] == ["ctlA", "ctlB"]
    assert (tmp_path / "a.pdf").exists()


def test_download_from_minvu_reuses_passed_client(monkeypatch, tmp_path):
    """When a pre-warmed client is passed, no load/select_region/search happens."""
    fake = _FakeClient()
    row = SimpleNamespace(codigo_informe="ctlX")
    ok = DL.download_from_minvu(row, tmp_path / "x.pdf", 10, 100, 2, client=fake)
    assert ok is True
    assert not any(e == "load" or (isinstance(e, tuple) and e[0] == "search")
                   for e in fake.events)
    assert ("post", "ctlX") in fake.events

"""Fase 13 resilience: DB connect retry, discovery early-stop/resume, admin gate."""
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

import informes_cev_minvu_db.db.session as S
import informes_cev_minvu_db.discovery.run as R
from informes_cev_minvu_db.config import settings


# ── DB connect retry/backoff ────────────────────────────────────────────────

def _op_error(msg="the database system is in recovery mode"):
    return OperationalError("SELECT 1", {}, Exception(msg))


def test_connect_retries_then_succeeds(monkeypatch):
    """A couple of transient connect failures should be retried, not fatal."""
    monkeypatch.setattr(S.settings, "db_connect_retries", 5)
    monkeypatch.setattr(S.settings, "db_connect_backoff", 0.0)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)

    attempts = {"n": 0}

    class FakeSession:
        def __init__(self, engine):
            pass

        def connection(self):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _op_error()
            return object()

        def close(self):
            pass

    monkeypatch.setattr(S, "Session", FakeSession)
    with S.get_session() as s:
        assert s is not None
    assert attempts["n"] == 3


def test_connect_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(S.settings, "db_connect_retries", 3)
    monkeypatch.setattr(S.settings, "db_connect_backoff", 0.0)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)

    class AlwaysFail:
        def __init__(self, engine):
            pass

        def connection(self):
            raise _op_error()

        def close(self):
            pass

    monkeypatch.setattr(S, "Session", AlwaysFail)
    with pytest.raises(RuntimeError, match="DB connect failed after 3 retries"):
        with S.get_session():
            pass


# ── Discovery early-stop (incremental) + checkpoint writes ──────────────────

class _StubClient:
    """Stand-in PortalClient: pages return fixed HTML markers; we drive parsing."""
    def __init__(self, pages):
        self._pages = pages  # dict page_no -> "html"

    def search(self, *a):
        return self._pages[1]

    def goto_page(self, region, comuna, tipo, page):
        return self._pages[page]


def test_discover_comuna_early_stops_on_zero_new(monkeypatch):
    """Incremental: stop paginating once a full page yields 0 new rows."""
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R.hp, "parse_total_count", lambda html, tipo: 50)  # 5 pages
    monkeypatch.setattr(R.hp, "total_pages", lambda n: 5)
    # page 1 -> 10 rows, page 2 -> 10 rows; parse_rows returns a marker per page
    monkeypatch.setattr(R.hp, "parse_rows",
                        lambda html, r, c, t: [{"eval_id": f"{html}-{i}"} for i in range(10)])
    saved = []
    monkeypatch.setattr(R, "_save_progress", lambda *a, **k: saved.append(k))

    # page 1 all new (10), page 2 all known (0 new) -> early stop after page 2
    new_by_page = iter([10, 0])
    monkeypatch.setattr(R, "_upsert_rows", lambda rows: next(new_by_page))

    pages = {1: "p1", 2: "p2", 3: "p3", 4: "p4", 5: "p5"}
    res = R.discover_comuna(_StubClient(pages), 10, 100, 1, incremental=True,
                            early_stop_grace=1)
    assert res["early_stopped"] is True
    assert res["pages"] == 5  # total reported
    assert res["rows_new"] == 10
    # final save marks the unit done
    assert saved[-1]["status"] == "done"


def test_discover_comuna_grace_tolerates_isolated_zero_page(monkeypatch):
    """With grace=2, a single all-known page interleaved with new ones must NOT stop."""
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R.hp, "parse_total_count", lambda html, tipo: 40)
    monkeypatch.setattr(R.hp, "total_pages", lambda n: 4)
    monkeypatch.setattr(R.hp, "parse_rows",
                        lambda html, r, c, t: [{"eval_id": f"{html}-{i}"} for i in range(10)])
    monkeypatch.setattr(R, "_save_progress", lambda *a, **k: None)
    # pages: new, 0-new (isolated), new, 0-new -> never 2 consecutive zeros until end
    new_by_page = iter([5, 0, 3, 0])
    monkeypatch.setattr(R, "_upsert_rows", lambda rows: next(new_by_page))

    res = R.discover_comuna(_StubClient({1: "p1", 2: "p2", 3: "p3", 4: "p4"}),
                            10, 100, 1, incremental=True, early_stop_grace=2)
    # only the last page is the 2nd consecutive zero, and it's also the last page,
    # so all 4 pages get scraped; no premature stop.
    assert res["rows_seen"] == 40
    assert res["rows_new"] == 8


def test_discover_comuna_no_early_stop_when_not_incremental(monkeypatch):
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R.hp, "parse_total_count", lambda html, tipo: 20)
    monkeypatch.setattr(R.hp, "total_pages", lambda n: 2)
    monkeypatch.setattr(R.hp, "parse_rows", lambda html, r, c, t: [{"eval_id": "x"}])
    monkeypatch.setattr(R, "_save_progress", lambda *a, **k: None)
    monkeypatch.setattr(R, "_upsert_rows", lambda rows: 0)  # always 0 new

    res = R.discover_comuna(_StubClient({1: "p1", 2: "p2"}), 10, 100, 1, incremental=False)
    assert res["early_stopped"] is False
    assert res["pages"] == 2


def test_discover_comuna_resume_skips_done_pages(monkeypatch):
    """resume_from_page must skip already-scraped pages (no re-search of them)."""
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R.hp, "parse_total_count", lambda html, tipo: 30)
    monkeypatch.setattr(R.hp, "total_pages", lambda n: 3)
    monkeypatch.setattr(R.hp, "parse_rows", lambda html, r, c, t: [{"eval_id": "x"}])
    monkeypatch.setattr(R, "_save_progress", lambda *a, **k: None)
    upserted = []
    monkeypatch.setattr(R, "_upsert_rows", lambda rows: upserted.append(1) or 1)

    visited = []

    class Tracking(_StubClient):
        def goto_page(self, region, comuna, tipo, page):
            visited.append(page)
            return self._pages[page]

    res = R.discover_comuna(Tracking({1: "p1", 2: "p2", 3: "p3"}), 10, 100, 1,
                            resume_from_page=3)
    # only page 3 processed; pages 1-2 skipped
    assert visited == [3]
    assert len(upserted) == 1
    assert res["rows_seen"] == 1


# ── Admin token gate ────────────────────────────────────────────────────────

def test_require_admin_passes_when_no_token_configured(monkeypatch):
    from informes_cev_minvu_db.app import _require_admin
    monkeypatch.setattr(settings, "admin_token", "")
    _require_admin(None)  # open when unset → no raise


def test_require_admin_rejects_bad_token(monkeypatch):
    from informes_cev_minvu_db.app import _require_admin
    monkeypatch.setattr(settings, "admin_token", "secret")
    with pytest.raises(HTTPException) as ei:
        _require_admin("wrong")
    assert ei.value.status_code == 401


def test_require_admin_accepts_good_token(monkeypatch):
    from informes_cev_minvu_db.app import _require_admin
    monkeypatch.setattr(settings, "admin_token", "secret")
    _require_admin("secret")  # no raise

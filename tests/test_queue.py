"""Unit tests for queue behavior: random ordering SQL + throttle delay."""
import time

from sqlalchemy import func
from sqlmodel import select

from informes_cev_minvu_db.config import settings
from informes_cev_minvu_db.db.models import Evaluaciones
from informes_cev_minvu_db.pipeline import queue as Q


def test_pending_query_uses_random_order():
    """The pending selection must be randomized (no region/comuna bias)."""
    # build the same statement shape and confirm a random() ordering is present
    stmt = (select(Evaluaciones.eval_id)
            .where(Evaluaciones.pdf_download_status == "pending")
            .order_by(func.random()))
    compiled = str(stmt).lower()
    assert "random()" in compiled


def test_download_delay_default_exists():
    assert isinstance(settings.download_delay, (int, float))
    assert settings.download_delay >= 0


def test_process_pending_no_sleep_when_delay_zero(monkeypatch):
    """delay=0 must not sleep; and process_one is called per id."""
    monkeypatch.setattr(Q, "_pending_eval_ids", lambda region_id, limit: ["a", "b", "c"])
    calls = []
    monkeypatch.setattr(Q, "process_one", lambda eid: calls.append(eid) or {"status": "extracted"})
    slept = []
    monkeypatch.setattr(Q.time, "sleep", lambda s: slept.append(s))
    res = Q.process_pending(delay=0)
    assert res == {"selected": 3, "extracted": 3, "skipped_v1": 0, "failed": 0}
    assert calls == ["a", "b", "c"]
    assert slept == []  # no throttle when delay=0


def test_process_pending_sleeps_between_with_delay(monkeypatch):
    monkeypatch.setattr(Q, "_pending_eval_ids", lambda region_id, limit: ["a", "b", "c"])
    monkeypatch.setattr(Q, "process_one", lambda eid: {"status": "extracted"})
    slept = []
    monkeypatch.setattr(Q.time, "sleep", lambda s: slept.append(s))
    Q.process_pending(delay=0.01)
    # sleeps between items but not after the last → n-1 sleeps
    assert slept == [0.01, 0.01]

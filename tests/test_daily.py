"""Daily job: discovery now runs before draining the pending queue (Problem 1 fix)."""
from informes_cev_minvu_db.pipeline import daily as D


def test_run_daily_discovers_then_processes(monkeypatch):
    """run_daily must call discovery across all 16 regions BEFORE process_pending,
    so newly published evals enter the queue and get drained the same tick."""
    calls = []

    monkeypatch.setattr(D, "count_pending", lambda: 0)
    monkeypatch.setattr(D, "run_sync", lambda **k: calls.append("sync") or {})
    monkeypatch.setattr(D, "cleanup_orphans", lambda: calls.append("cleanup") or {})

    def fake_discover(region_id, **k):
        calls.append(("discover", region_id, k.get("incremental"), k.get("resume")))
        return [{"rows_new": 1}]

    monkeypatch.setattr(D, "discover", fake_discover)
    # process_pending is imported lazily inside run_daily
    import informes_cev_minvu_db.pipeline.queue as Q
    monkeypatch.setattr(Q, "process_pending",
                        lambda **k: calls.append("process") or {"extracted": 0})

    summary = D.run_daily()

    # all 16 regions discovered incrementally with resume, before any processing
    discover_calls = [c for c in calls if isinstance(c, tuple) and c[0] == "discover"]
    assert [c[1] for c in discover_calls] == list(range(1, 17))
    assert all(c[2] is True and c[3] is True for c in discover_calls)  # incremental+resume
    assert calls.index("process") > calls.index(discover_calls[-1])
    assert summary["discovery"]["new_total"] == 16  # 1 new per region


def test_run_daily_discover_false_skips_discovery(monkeypatch):
    calls = []
    monkeypatch.setattr(D, "count_pending", lambda: 0)
    monkeypatch.setattr(D, "run_sync", lambda **k: {})
    monkeypatch.setattr(D, "cleanup_orphans", lambda: {})
    monkeypatch.setattr(D, "discover", lambda *a, **k: calls.append("discover") or [])
    import informes_cev_minvu_db.pipeline.queue as Q
    monkeypatch.setattr(Q, "process_pending", lambda **k: {})

    summary = D.run_daily(discover=False)
    assert "discovery" not in summary
    assert calls == []


def test_run_discovery_isolates_region_failure(monkeypatch):
    """A failing region is recorded but does not abort the other 15."""
    def flaky(region_id, **k):
        if region_id == 7:
            raise RuntimeError("portal down")
        return [{"rows_new": 2}]

    monkeypatch.setattr(D, "discover", flaky)
    out = D.run_discovery()
    assert out["regions"][7]["error"].startswith("portal down")
    assert out["regions"][1]["new"] == 2
    assert out["new_total"] == 2 * 15  # 15 good regions

"""Diagnostic: structure (DB-gated) + endpoint admin gate / error handling (DB-less)."""
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from informes_cev_minvu_db.db.session import engine


def _db_available() -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ── DB-gated: the real query set runs and returns the documented shape ───────

@pytest.mark.skipif(not _db_available(), reason="no reachable PostgreSQL")
def test_diagnostic_returns_stable_shape():
    from informes_cev_minvu_db.db.session import create_all
    from informes_cev_minvu_db.diagnostic import diagnostic
    create_all()
    out = diagnostic()

    assert out["ok"] is True
    assert "ts" in out
    ev = out["evaluaciones"]
    assert set(ev) == {"total", "by_status", "by_report_version", "unsynced"}
    assert isinstance(ev["total"], int)
    assert isinstance(ev["by_status"], dict)
    # all 8 detail tables present and counted
    assert set(out["detail_tables"]) == {
        "informe_v2_pagina1", "informe_v2_pagina2", "informe_v2_pagina3_consumos",
        "informe_v2_pagina3_envolvente", "informe_v2_pagina4", "informe_v2_pagina5",
        "informe_v2_pagina6", "informe_v2_pagina7",
    }
    assert all(isinstance(v, int) for v in out["detail_tables"].values())
    assert set(out["discovery_progress"]) == {"by_status", "by_early_stopped"}
    assert set(out["pagina1_nulls"]) == {
        "superficie_interior_util_m2", "emitida_el", "demanda_calefaccion_kwh_m2_ano"}
    # never leak credentials
    import json
    assert "password" not in json.dumps(out).lower()
    assert "postgresql" not in json.dumps(out).lower()


# ── DB-less: endpoint gate + error handling (monkeypatch the query function) ──

def test_endpoint_requires_token_when_set(monkeypatch):
    from informes_cev_minvu_db import app as A
    monkeypatch.setattr(A.settings, "admin_token", "secret")
    with pytest.raises(HTTPException) as ei:
        A.admin_db_diagnostic(x_admin_token="wrong")
    assert ei.value.status_code == 401


def test_endpoint_returns_diagnostic_when_authorized(monkeypatch):
    from informes_cev_minvu_db import app as A
    monkeypatch.setattr(A.settings, "admin_token", "secret")
    monkeypatch.setattr(A, "diagnostic", lambda: {"ok": True, "stub": 1})
    out = A.admin_db_diagnostic(x_admin_token="secret")
    assert out == {"ok": True, "stub": 1}


def test_endpoint_open_when_no_token(monkeypatch):
    from informes_cev_minvu_db import app as A
    monkeypatch.setattr(A.settings, "admin_token", "")
    monkeypatch.setattr(A, "diagnostic", lambda: {"ok": True})
    assert A.admin_db_diagnostic(x_admin_token=None) == {"ok": True}


def test_endpoint_db_error_returns_503(monkeypatch):
    from informes_cev_minvu_db import app as A
    monkeypatch.setattr(A.settings, "admin_token", "")

    def boom():
        raise RuntimeError("db unreachable: recovery mode")

    monkeypatch.setattr(A, "diagnostic", boom)
    resp = A.admin_db_diagnostic(x_admin_token=None)
    assert resp.status_code == 503
    import json
    body = json.loads(resp.body)
    assert body["ok"] is False
    assert "recovery mode" in body["error"]

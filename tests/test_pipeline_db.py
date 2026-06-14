"""Integration test: process Ancud PDF → 8 detail tables with new schema names.

Requires a reachable PostgreSQL (DATABASE_URL). Skips if unavailable so the
suite still runs in DB-less environments.
"""
import pytest
from sqlalchemy import text

from informes_cev_minvu_db.db.session import create_all, engine, get_session


def _db_available() -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="no database reachable")

EVAL_ID = "test-ancud-pytest"


@pytest.fixture(scope="module", autouse=True)
def _setup():
    from informes_cev_minvu_db.db.seed import seed
    from informes_cev_minvu_db.pipeline.process import _ensure_eval
    create_all()
    seed()
    with get_session() as s:
        _ensure_eval(s, EVAL_ID)
    yield
    # cleanup: remove the test eval's rows
    from informes_cev_minvu_db.db import models as M
    from sqlmodel import delete
    with get_session() as s:
        for model in (M.InformeV2Pagina1, M.InformeV2Pagina2, M.InformeV2Pagina3Consumos,
                      M.InformeV2Pagina3Envolvente, M.InformeV2Pagina4, M.InformeV2Pagina5,
                      M.InformeV2Pagina6, M.InformeV2Pagina7):
            s.exec(delete(model).where(model.eval_id == EVAL_ID))
        s.exec(delete(M.Evaluaciones).where(M.Evaluaciones.eval_id == EVAL_ID))
        s.commit()


def test_process_populates_8_tables(ancud_pdf):
    from informes_cev_minvu_db.pipeline.process import process_pdf
    res = process_pdf(EVAL_ID, ancud_pdf)
    assert res["status"] == "extracted"
    assert res["rows"] == {"pagina1": 1, "pagina2": 1, "pagina3_consumos": 1, "pagina7": 1,
                           "pagina3_envolvente": 10, "pagina4": 12, "pagina5": 2, "pagina6": 96}


def test_new_schema_names_and_values():
    with get_session() as s:
        row = s.exec(text(
            "SELECT codigo_evaluacion_energetica, tipo_evaluacion_nombre, "
            "tipo_vivienda_nombre, porcentaje_ahorro, emitida_el "
            f"FROM informe_v2_pagina1 WHERE eval_id='{EVAL_ID}'")).one()
        assert row[0] == "ba26352019"
        assert "ENERG" in (row[1] or "").upper()
        assert row[2] and "Casa" in row[2]           # raw free text
        assert abs(float(row[3]) - (-12)) < 0.001     # float
        assert str(row[4]) == "2019-01-15"            # date

        zona = s.exec(text(
            f"SELECT zona_termica_nombre FROM informe_v2_pagina2 WHERE eval_id='{EVAL_ID}'")).one()
        assert zona[0] == "G"                          # raw text, no FK

        qsol = s.exec(text(
            "SELECT q_sol_kwh FROM informe_v2_pagina5 p JOIN meses m ON p.mes_id=m.mes_id "
            f"WHERE p.eval_id='{EVAL_ID}' AND m.mes_nombre='Enero'")).one()
        assert abs(float(qsol[0]) - 12.9) < 0.05

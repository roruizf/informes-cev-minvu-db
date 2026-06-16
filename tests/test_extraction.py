"""Extraction tests against the Ancud sample (no DB). Known values from the PDF."""
from informes_cev_minvu_db.pdf.extract_all import extract_report
from informes_cev_minvu_db.pdf.version_detect import detect_version


def test_version_v2(ancud_pdf):
    assert detect_version(ancud_pdf) == 2


def test_full_report_shapes(ancud_pdf):
    r = extract_report(ancud_pdf)
    assert r["_validation"]["ok"] is True
    assert len(r["pagina3_envolvente"]) == 10
    assert len(r["pagina4"]) == 12
    assert len(r["pagina5"]) == 2
    assert len(r["pagina6"]) == 96  # 4 months x 24h


def test_pagina1_known_values(ancud_pdf):
    p1 = extract_report(ancud_pdf)["pagina1"]
    assert p1["codigo_evaluacion"] == "ba26352019"
    assert p1["porcentaje_ahorro"] == -12
    assert p1["letra_eficiencia_energetica_dem"] == "F"
    assert abs(p1["demanda_total_kwh_m2_ano"] - 140.7) < 0.05
    assert p1["region"].startswith("X Región")


def test_pagina5_q_sol_known(ancud_pdf):
    p5 = extract_report(ancud_pdf)["pagina5"]
    by_mes = {row["mes"]: row for row in p5}
    assert abs(by_mes["Enero"]["q_sol_kwh"] - 12.9) < 0.05
    assert abs(by_mes["Julio"]["q_sol_kwh"] - 2.9) < 0.05
    assert by_mes["Enero"]["q_recuperado_kwh"] == 0.0


def test_codigo_present_on_detail_rows(ancud_pdf):
    r = extract_report(ancud_pdf)
    # controlled redundancy: every detail row carries codigo_evaluacion
    assert r["pagina5"][0]["codigo_evaluacion"] == "ba26352019"
    assert r["pagina6"][0]["codigo_evaluacion"] == "ba26352019"
    assert r["pagina3_envolvente"][0]["codigo_evaluacion"] == "ba26352019"

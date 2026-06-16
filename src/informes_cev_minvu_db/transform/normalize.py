"""Translate extractor output (legacy field names) to the new schema columns
and normalize types (dates, mes_id).

The coordinate/OCR extractors are kept verbatim (they match the PDF layout);
this layer maps their keys to the renamed columns. Layer-1 raw capture: free-text
dimensions (tipo_vivienda, zona_termica, orientacion) are stored as `_nombre`
strings directly — NO FK reference tables, NO get-or-create.
"""
import re
from datetime import date

# ── value normalizers ───────────────────────────────────────────────────────

_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
          "noviembre": 11, "diciembre": 12}


def parse_chilean_date(value):
    if value is None or isinstance(value, date):
        return value
    s = str(value).strip().lower()
    if not s:
        return None
    m = re.match(r"(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{4})", s)
    if m:
        d, mo, y = (int(g) for g in m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    m = re.match(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", s)
    if m and m.group(2) in _MESES:
        try:
            return date(int(m.group(3)), _MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    return None


def mes_id(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 12 else None
    return _MESES.get(str(value).strip().lower())


# ── key renames per page (legacy extractor key -> new column) ───────────────
# Layer-1: tipo_vivienda / zona_termica / orientacion map straight to *_nombre.

PAGINA1_RENAME = {
    "codigo_evaluacion": "codigo_evaluacion_energetica",
    "tipo_evaluacion": "tipo_evaluacion_nombre",
    "region": "region_nombre",
    "comuna": "comuna_nombre",
    "tipo_vivienda": "tipo_vivienda_nombre",
}
PAGINA2_RENAME = {
    "codigo_evaluacion": "codigo_evaluacion_energetica",
    "region": "region_nombre",
    "comuna": "comuna_nombre",
    "tipo_vivienda": "tipo_vivienda_nombre",
    "zona_termica": "zona_termica_nombre",
}
# page 3 consumos: per->porcentaje, proy->proyectado, ref->referencia, ep->energia_primaria,
# generacion_ep->generacion_energia_primaria, total_consumo_ep->...energia_primaria...
PAGINA3C_RENAME = {
    "codigo_evaluacion": "codigo_evaluacion_energetica",
    "agua_caliente_sanitaria_per": "agua_caliente_sanitaria_porcentaje",
    "iluminacion_per": "iluminacion_porcentaje",
    "calefaccion_kwh_per": "calefaccion_porcentaje",
    "energia_renovable_no_convencional_per": "energia_renovable_no_convencional_porcentaje",
    "consumo_ep_calefaccion_kwh": "consumo_energia_primaria_calefaccion_kwh",
    "consumo_ep_agua_caliente_sanitaria_kwh": "consumo_energia_primaria_agua_caliente_sanitaria_kwh",
    "consumo_ep_iluminacion_kwh": "consumo_energia_primaria_iluminacion_kwh",
    "consumo_ep_ventiladores_kwh": "consumo_energia_primaria_ventiladores_kwh",
    "generacion_ep_fotovoltaicos_kwh": "generacion_energia_primaria_fotovoltaicos_kwh",
    "total_consumo_ep_antes_fotovoltaica_kwh": "total_consumo_energia_primaria_antes_fotovoltaica_kwh",
    "consumo_total_ep_obj_kwh": "consumo_total_energia_primaria_objeto_kwh",
    "consumo_total_ep_ref_kwh": "consumo_total_energia_primaria_referencia_kwh",
}


def _rename_proy_ref(key: str) -> str:
    # _proy_ -> _proyectado_, _ref_ -> _referencia_ (only the consumo/equipo blocks)
    key = re.sub(r"_proy_", "_proyectado_", key)
    key = re.sub(r"_ref_", "_referencia_", key)
    return key


def rename_pagina3_consumos(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        nk = PAGINA3C_RENAME.get(k, _rename_proy_ref(k))
        out[nk] = v
    return out


# codigo_evaluacion -> codigo_evaluacion_energetica on every page
CODIGO_RENAME = {"codigo_evaluacion": "codigo_evaluacion_energetica"}

PAGINA4_RENAME = {
    **CODIGO_RENAME,
    "demanda_calef_viv_eval_kwh": "demanda_calefaccion_viv_eval_kwh",
    "demanda_calef_viv_ref_kwh": "demanda_calefaccion_viv_ref_kwh",
    "demanda_enfri_viv_eval_kwh": "demanda_enfriamiento_viv_eval_kwh",
    "demanda_enfri_viv_ref_kwh": "demanda_enfriamiento_viv_ref_kwh",
}
PAGINA3E_RENAME = {**CODIGO_RENAME, "ua_phil": "ua_mas_phi_l", "orientacion": "orientacion_nombre"}
PAGINA5_RENAME = {**CODIGO_RENAME}
PAGINA6_RENAME = {**CODIGO_RENAME, "temp_exterior": "temperatura_exterior",
                  "temp_interior": "temperatura_interior"}
PAGINA7_RENAME = {**CODIGO_RENAME}

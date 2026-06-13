"""Translate extractor output (legacy field names) to the new schema columns,
resolve string dimensions to FK ids, and normalize types (dates).

The coordinate/OCR extractors are kept verbatim (they match the PDF layout);
this layer maps their keys to the renamed columns and reference FKs.
"""
import re
from datetime import date

from sqlmodel import Session, select

from informes_cev_minvu_db.db import models as M

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


# ── FK resolution (get-or-create for open dimensions) ───────────────────────


def _get_or_create(session: Session, model, name_attr, pk_attr, value):
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    obj = session.exec(select(model).where(getattr(model, name_attr) == value)).first()
    if obj:
        return getattr(obj, pk_attr)
    obj = model(**{name_attr: value})
    session.add(obj)
    session.flush()
    return getattr(obj, pk_attr)


def tipo_vivienda_id(session, value):
    return _get_or_create(session, M.TiposVivienda, "tipo_vivienda_nombre", "tipo_vivienda_id", value)


def zona_termica_id(session, value):
    return _get_or_create(session, M.ZonasTermicas, "zona_termica_nombre", "zona_termica_id", value)


def orientacion_id(session, value):
    return _get_or_create(session, M.Orientaciones, "orientacion_nombre", "orientacion_id", value)


# ── key renames per page (legacy extractor key -> new column) ───────────────

PAGINA1_RENAME = {
    "tipo_evaluacion": "tipo_evaluacion_nombre",
    "region": "region_nombre",
    "comuna": "comuna_nombre",
    # tipo_vivienda handled separately (-> tipo_vivienda_id)
}
PAGINA2_RENAME = {
    "region": "region_nombre",
    "comuna": "comuna_nombre",
}
# page 3 consumos: per->porcentaje, proy->proyectado, ref->referencia, ep->energia_primaria,
# generacion_ep->generacion_energia_primaria, total_consumo_ep->...energia_primaria...
PAGINA3C_RENAME = {
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


PAGINA4_RENAME = {
    "demanda_calef_viv_eval_kwh": "demanda_calefaccion_viv_eval_kwh",
    "demanda_calef_viv_ref_kwh": "demanda_calefaccion_viv_ref_kwh",
    "demanda_enfri_viv_eval_kwh": "demanda_enfriamiento_viv_eval_kwh",
    "demanda_enfri_viv_ref_kwh": "demanda_enfriamiento_viv_ref_kwh",
}
PAGINA3E_RENAME = {"ua_phil": "ua_mas_phi_l"}
PAGINA6_RENAME = {"temp_exterior": "temperatura_exterior", "temp_interior": "temperatura_interior"}

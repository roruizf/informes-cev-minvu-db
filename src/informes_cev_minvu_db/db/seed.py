"""Seed reference tables (Layer-1 structural dims only).

regiones (16, portal names), tipos_evaluacion (2), meses (12). The free-text /
fixed dimensions tipo_vivienda, zona_termica and orientacion are NOT tables —
they are stored as raw `_nombre` strings in the page tables.
"""
from sqlmodel import select

from informes_cev_minvu_db.db.models import Meses, Regiones, TiposEvaluacion
from informes_cev_minvu_db.db.session import get_session

REGIONES = [
    (1, "Región de Tarapacá"), (2, "Región de Antofagasta"), (3, "Región de Atacama"),
    (4, "Región de Coquimbo"), (5, "Región de Valparaíso"),
    (6, "Región del Libertador Gral. Bernardo O'Higgins"), (7, "Región del Maule"),
    (8, "Región del Biobío"), (9, "Región de la Araucanía"), (10, "Región de Los Lagos"),
    (11, "Región Aysén del Gral. Carlos Ibáñez del Campo"),
    (12, "Región de Magallanes y de la Antártica Chilena"),
    (13, "Región Metropolitana de Santiago"), (14, "Región de Los Ríos"),
    (15, "Región de Arica y Parinacota"), (16, "Región de Ñuble"),
]
TIPOS_EVALUACION = [(1, "Precalificación Energética"), (2, "Calificación Energética")]
MESES = [(1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"), (5, "Mayo"), (6, "Junio"),
         (7, "Julio"), (8, "Agosto"), (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"),
         (12, "Diciembre")]


def _seed_simple(s, model, pk_attr, name_attr, rows):
    for pk, name in rows:
        if s.get(model, pk) is None:
            s.add(model(**{pk_attr: pk, name_attr: name}))


def seed() -> dict:
    with get_session() as s:
        _seed_simple(s, Regiones, "region_id", "region_nombre", REGIONES)
        _seed_simple(s, TiposEvaluacion, "tipo_evaluacion_id", "tipo_evaluacion_nombre", TIPOS_EVALUACION)
        _seed_simple(s, Meses, "mes_id", "mes_nombre", MESES)
        s.commit()
        counts = {
            "regiones": len(s.exec(select(Regiones)).all()),
            "tipos_evaluacion": len(s.exec(select(TiposEvaluacion)).all()),
            "meses": len(s.exec(select(Meses)).all()),
        }
    return counts


if __name__ == "__main__":
    print(seed())

"""Seed reference tables.

regiones (16, portal names), tipos_evaluacion (2), meses (12), orientaciones (9),
zonas_termicas (CEV letter zones A-I + B2 — the value the PDF page 2 actually shows;
the manual's OGUC 1-7 is internal-only). tipos_vivienda is populated on extract.
"""
from sqlmodel import select

from informes_cev_minvu_db.db.models import (
    Meses, Orientaciones, Regiones, TiposEvaluacion, ZonasTermicas,
)
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
# Envelope orientations as they appear in page-3 (datacev order)
ORIENTACIONES = [(1, "Horiz"), (2, "N"), (3, "NE"), (4, "E"), (5, "SE"), (6, "S"),
                 (7, "SO"), (8, "O"), (9, "NO"), (10, "Pisos")]
# CEV thermal zones (Estándares de Construcción Sustentable letters) — what page 2 shows
ZONAS_TERMICAS = [(1, "A"), (2, "B"), (3, "B2"), (4, "C"), (5, "D"), (6, "E"),
                  (7, "F"), (8, "G"), (9, "H"), (10, "I")]


def _seed_simple(s, model, pk_attr, name_attr, rows):
    for pk, name in rows:
        obj = s.get(model, pk)
        if obj is None:
            s.add(model(**{pk_attr: pk, name_attr: name}))


def seed() -> dict:
    with get_session() as s:
        _seed_simple(s, Regiones, "region_id", "region_nombre", REGIONES)
        _seed_simple(s, TiposEvaluacion, "tipo_evaluacion_id", "tipo_evaluacion_nombre", TIPOS_EVALUACION)
        _seed_simple(s, Meses, "mes_id", "mes_nombre", MESES)
        _seed_simple(s, Orientaciones, "orientacion_id", "orientacion_nombre", ORIENTACIONES)
        _seed_simple(s, ZonasTermicas, "zona_termica_id", "zona_termica_nombre", ZONAS_TERMICAS)
        s.commit()
        counts = {
            "regiones": len(s.exec(select(Regiones)).all()),
            "tipos_evaluacion": len(s.exec(select(TiposEvaluacion)).all()),
            "meses": len(s.exec(select(Meses)).all()),
            "orientaciones": len(s.exec(select(Orientaciones)).all()),
            "zonas_termicas": len(s.exec(select(ZonasTermicas)).all()),
        }
    return counts


if __name__ == "__main__":
    print(seed())

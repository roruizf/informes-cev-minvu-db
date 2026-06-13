"""Seed reference tables: 16 regiones + 2 tipos de evaluación.

Region names are the canonical labels from the MINVU portal dropdown.
Comunas (348) are populated during discovery (Phase 3), since they require
per-region portal queries.
"""
from sqlmodel import select

from informes_cev_minvu_db.db.models import Regiones, TiposEvaluacion
from informes_cev_minvu_db.db.session import get_session

REGIONES = [
    (1, "Región de Tarapacá"),
    (2, "Región de Antofagasta"),
    (3, "Región de Atacama"),
    (4, "Región de Coquimbo"),
    (5, "Región de Valparaíso"),
    (6, "Región del Libertador Gral. Bernardo O'Higgins"),
    (7, "Región del Maule"),
    (8, "Región del Biobío"),
    (9, "Región de la Araucanía"),
    (10, "Región de Los Lagos"),
    (11, "Región Aysén del Gral. Carlos Ibáñez del Campo"),
    (12, "Región de Magallanes y de la Antártica Chilena"),
    (13, "Región Metropolitana de Santiago"),
    (14, "Región de Los Ríos"),
    (15, "Región de Arica y Parinacota"),
    (16, "Región de Ñuble"),
]

TIPOS_EVALUACION = [
    (1, "Precalificación Energética"),
    (2, "Calificación Energética"),
]


def seed() -> dict:
    """Idempotent upsert of reference data. Returns counts."""
    with get_session() as s:
        for rid, name in REGIONES:
            if not s.get(Regiones, rid):
                s.add(Regiones(region_id=rid, region_name=name))
        for tid, name in TIPOS_EVALUACION:
            if not s.get(TiposEvaluacion, tid):
                s.add(TiposEvaluacion(tipo_evaluacion_id=tid, tipo_evaluacion_nombre=name))
        s.commit()
        n_reg = len(s.exec(select(Regiones)).all())
        n_tip = len(s.exec(select(TiposEvaluacion)).all())
    return {"regiones": n_reg, "tipos_evaluacion": n_tip}


if __name__ == "__main__":
    print(seed())

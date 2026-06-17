"""SQLModel schema for informes-cev-minvu-db.

Conventions (Roberto): names end `_nombre`; no abbreviations
(calefaccion/enfriamiento/proyectado/referencia/energia_primaria/porcentaje/
temperatura). LAYER 1 = capture raw PDF values faithfully; do NOT over-normalize.
Free-text / fixed dimensions (tipo_vivienda, zona_termica, orientacion,
tipo_evaluacion) are stored as `_nombre: str` directly, NOT as FK reference tables
(cleaning/normalization is a future Layer 2 concern). Only truly structural dims
remain as tables: regiones, comunas, meses, tipos_evaluacion. Controlled redundancy
is intentional: page tables keep codigo_evaluacion_energetica/region_nombre/
comuna_nombre/direccion so each is self-contained for API/agents.

Pages 1-5,7 extracted by coordinates; page 6 (temps) by template-matching OCR.
"""
from datetime import date, datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

# ── Reference tables ────────────────────────────────────────────────────────


class Regiones(SQLModel, table=True):
    region_id: int = Field(primary_key=True)
    region_nombre: str = Field(unique=True)

    comunas: List["Comunas"] = Relationship(back_populates="region")


class Comunas(SQLModel, table=True):
    comuna_id: int = Field(primary_key=True)
    comuna_nombre: str
    region_id: int = Field(foreign_key="regiones.region_id", index=True)

    region: Regiones = Relationship(back_populates="comunas")
    evaluaciones: List["Evaluaciones"] = Relationship(back_populates="comuna")


class TiposEvaluacion(SQLModel, table=True):
    __tablename__ = "tipos_evaluacion"
    tipo_evaluacion_id: int = Field(primary_key=True)
    tipo_evaluacion_nombre: str = Field(unique=True, index=True)


class Meses(SQLModel, table=True):
    mes_id: int = Field(primary_key=True)
    mes_nombre: str = Field(unique=True)

# NOTE: orientaciones, tipos_vivienda, zonas_termicas were removed (Layer-1 raw
# capture): those values are stored as `_nombre: str` directly in the page tables.


# ── Discovery / scraping mechanics (NOT mirrored) ───────────────────────────


class Busquedas(SQLModel, table=True):
    search_id: str = Field(primary_key=True)
    search_date: date = Field(index=True)


class PaginasHTML(SQLModel, table=True):
    __tablename__ = "paginas_html"
    id: Optional[int] = Field(default=None, primary_key=True)
    search_id: str = Field(foreign_key="busquedas.search_id", index=True)
    comuna_id: int = Field(foreign_key="comunas.comuna_id")
    tipo_evaluacion_id: int = Field(foreign_key="tipos_evaluacion.tipo_evaluacion_id")
    pagina: int
    status: str = Field(default="pending", index=True)
    viewstate: Optional[str] = None


# ── Master directory table ──────────────────────────────────────────────────


class Evaluaciones(SQLModel, table=True):
    """Report directory: universe of available reports + processing state.

    eval_id = uuid5(NAMESPACE_DNS, f"{comuna_id}_{region_id}_{tipo_evaluacion_id}_{identificacion}")
    """
    eval_id: str = Field(primary_key=True)
    comuna_id: int = Field(foreign_key="comunas.comuna_id", index=True)
    tipo_evaluacion_id: int = Field(foreign_key="tipos_evaluacion.tipo_evaluacion_id")

    identificacion_vivienda: str
    tipologia: Optional[str] = None
    proyecto: Optional[str] = None
    calificacion_energetica_letra: Optional[str] = None
    calificacion_equipos_letra: Optional[str] = None
    codigo_informe: Optional[str] = None
    codigo_etiqueta: Optional[str] = None
    viewstate: Optional[str] = None

    pdf_download_status: str = Field(default="pending", index=True)
    report_version: Optional[int] = None
    retry_count: int = Field(default=0)
    last_error: Optional[str] = None
    last_processed_at: Optional[datetime] = None
    synced_to_mirror_at: Optional[datetime] = Field(default=None, index=True)
    # set on every discovery upsert; lets us detect reports that stop appearing
    # in the portal (no policy applied yet — just observability).
    last_seen_at: Optional[datetime] = Field(default=None, index=True)

    comuna: Comunas = Relationship(back_populates="evaluaciones")
    pagina1: Optional["InformeV2Pagina1"] = Relationship(back_populates="evaluacion")
    pagina2: Optional["InformeV2Pagina2"] = Relationship(back_populates="evaluacion")
    pagina3_consumos: Optional["InformeV2Pagina3Consumos"] = Relationship(back_populates="evaluacion")
    pagina3_envolvente: List["InformeV2Pagina3Envolvente"] = Relationship(back_populates="evaluacion")
    pagina4: List["InformeV2Pagina4"] = Relationship(back_populates="evaluacion")
    pagina5: List["InformeV2Pagina5"] = Relationship(back_populates="evaluacion")
    pagina6: List["InformeV2Pagina6"] = Relationship(back_populates="evaluacion")
    pagina7: Optional["InformeV2Pagina7"] = Relationship(back_populates="evaluacion")


# ── Extracted-data tables (normalized types; controlled redundancy kept) ────


class InformeV2Pagina1(SQLModel, table=True):
    __tablename__ = "informe_v2_pagina1"
    eval_id: str = Field(foreign_key="evaluaciones.eval_id", primary_key=True)
    codigo_evaluacion_energetica: Optional[str] = None
    tipo_evaluacion_nombre: Optional[str] = None
    region_nombre: Optional[str] = None
    comuna_nombre: Optional[str] = None
    direccion: Optional[str] = None
    rol_vivienda_proyecto: Optional[str] = None
    tipo_vivienda_nombre: Optional[str] = None
    superficie_interior_util_m2: Optional[float] = None
    porcentaje_ahorro: Optional[float] = None
    letra_eficiencia_energetica_dem: Optional[str] = None
    demanda_calefaccion_kwh_m2_ano: Optional[float] = None
    demanda_enfriamiento_kwh_m2_ano: Optional[float] = None
    demanda_total_kwh_m2_ano: Optional[float] = None
    emitida_el: Optional[date] = None

    evaluacion: Evaluaciones = Relationship(back_populates="pagina1")


class InformeV2Pagina2(SQLModel, table=True):
    __tablename__ = "informe_v2_pagina2"
    eval_id: str = Field(foreign_key="evaluaciones.eval_id", primary_key=True)
    codigo_evaluacion_energetica: Optional[str] = None
    region_nombre: Optional[str] = None
    comuna_nombre: Optional[str] = None
    direccion: Optional[str] = None
    rol_vivienda: Optional[str] = None
    tipo_vivienda_nombre: Optional[str] = None
    zona_termica_nombre: Optional[str] = None
    superficie_interior_util_m2: Optional[float] = None
    solicitado_por: Optional[str] = None
    evaluado_por: Optional[str] = None
    demanda_calefaccion_kwh_m2_ano: Optional[float] = None
    demanda_enfriamiento_kwh_m2_ano: Optional[float] = None
    demanda_total_kwh_m2_ano: Optional[float] = None
    demanda_total_bis_kwh_m2_ano: Optional[float] = None
    demanda_total_referencia_kwh_m2_ano: Optional[float] = None
    porcentaje_ahorro: Optional[float] = None
    muro_principal_descripcion: Optional[str] = None
    muro_principal_exigencia_w_m2_k: Optional[float] = None
    muro_secundario_descripcion: Optional[str] = None
    muro_secundario_exigencia_w_m2_k: Optional[float] = None
    piso_principal_descripcion: Optional[str] = None
    piso_principal_exigencia_w_m2_k: Optional[float] = None
    puerta_principal_descripcion: Optional[str] = None
    puerta_principal_exigencia_w_m2_k: Optional[str] = None
    techo_principal_descripcion: Optional[str] = None
    techo_principal_exigencia_w_m2_k: Optional[float] = None
    techo_secundario_descripcion: Optional[str] = None
    techo_secundario_exigencia_w_m2_k: Optional[float] = None
    superficie_vidriada_principal_descripcion: Optional[str] = None
    superficie_vidriada_principal_exigencia: Optional[str] = None
    superficie_vidriada_secundaria_descripcion: Optional[str] = None
    superficie_vidriada_secundaria_exigencia: Optional[str] = None
    ventilacion_rah_descripcion: Optional[str] = None
    ventilacion_rah_exigencia: Optional[str] = None
    infiltraciones_rah_descripcion: Optional[str] = None
    infiltraciones_rah_exigencia: Optional[str] = None

    evaluacion: Evaluaciones = Relationship(back_populates="pagina2")


class InformeV2Pagina3Consumos(SQLModel, table=True):
    __tablename__ = "informe_v2_pagina3_consumos"
    eval_id: str = Field(foreign_key="evaluaciones.eval_id", primary_key=True)
    codigo_evaluacion_energetica: Optional[str] = None
    agua_caliente_sanitaria_kwh_m2: Optional[float] = None
    agua_caliente_sanitaria_porcentaje: Optional[float] = None
    iluminacion_kwh_m2: Optional[float] = None
    iluminacion_porcentaje: Optional[float] = None
    calefaccion_kwh_m2: Optional[float] = None
    calefaccion_porcentaje: Optional[float] = None
    energia_renovable_no_convencional_kwh_m2: Optional[float] = None
    energia_renovable_no_convencional_porcentaje: Optional[float] = None
    consumo_total_kwh_m2: Optional[float] = None
    emisiones_kgco2_m2_ano: Optional[float] = None
    calefaccion_descripcion_proyectado: Optional[str] = None
    calefaccion_consumo_proyectado_kwh: Optional[float] = None
    calefaccion_consumo_proyectado_porcentaje: Optional[float] = None
    iluminacion_descripcion_proyectado: Optional[str] = None
    iluminacion_consumo_proyectado_kwh: Optional[float] = None
    iluminacion_consumo_proyectado_porcentaje: Optional[float] = None
    agua_caliente_sanitaria_descripcion_proyectado: Optional[str] = None
    agua_caliente_sanitaria_consumo_proyectado_kwh: Optional[float] = None
    agua_caliente_sanitaria_consumo_proyectado_porcentaje: Optional[float] = None
    energia_renovable_no_convencional_descripcion_proyectado: Optional[str] = None
    energia_renovable_no_convencional_consumo_proyectado_kwh: Optional[float] = None
    energia_renovable_no_convencional_consumo_proyectado_porcentaje: Optional[float] = None
    consumo_total_requerido_proyectado_kwh: Optional[float] = None
    calefaccion_descripcion_referencia: Optional[str] = None
    calefaccion_consumo_referencia_kwh: Optional[float] = None
    calefaccion_consumo_referencia_porcentaje: Optional[float] = None
    iluminacion_descripcion_referencia: Optional[str] = None
    iluminacion_consumo_referencia_kwh: Optional[float] = None
    iluminacion_consumo_referencia_porcentaje: Optional[float] = None
    agua_caliente_sanitaria_descripcion_referencia: Optional[str] = None
    agua_caliente_sanitaria_consumo_referencia_kwh: Optional[float] = None
    agua_caliente_sanitaria_consumo_referencia_porcentaje: Optional[float] = None
    energia_renovable_no_convencional_descripcion_referencia: Optional[str] = None
    energia_renovable_no_convencional_consumo_referencia_kwh: Optional[float] = None
    energia_renovable_no_convencional_consumo_referencia_porcentaje: Optional[float] = None
    consumo_total_requerido_referencia_kwh: Optional[float] = None
    consumo_energia_primaria_calefaccion_kwh: Optional[float] = None
    consumo_energia_primaria_agua_caliente_sanitaria_kwh: Optional[float] = None
    consumo_energia_primaria_iluminacion_kwh: Optional[float] = None
    consumo_energia_primaria_ventiladores_kwh: Optional[float] = None
    generacion_energia_primaria_fotovoltaicos_kwh: Optional[float] = None
    aporte_fotovoltaicos_consumos_basicos_kwh: Optional[float] = None
    diferencia_fotovoltaica_para_consumo_kwh: Optional[float] = None
    aporte_solar_termica_calefaccion_kwh: Optional[float] = None
    aporte_solar_termica_agua_caliente_sanitaria_kwh: Optional[float] = None
    total_consumo_energia_primaria_antes_fotovoltaica_kwh: Optional[float] = None
    aporte_fotovoltaicos_consumos_basicos_kwh_bis: Optional[float] = None
    consumos_basicos_a_suplir_kwh: Optional[float] = None
    consumo_total_energia_primaria_objeto_kwh: Optional[float] = None
    consumo_total_energia_primaria_referencia_kwh: Optional[float] = None
    coeficiente_energetico_c: Optional[float] = None

    evaluacion: Evaluaciones = Relationship(back_populates="pagina3_consumos")


class InformeV2Pagina3Envolvente(SQLModel, table=True):
    __tablename__ = "informe_v2_pagina3_envolvente"
    id: Optional[int] = Field(default=None, primary_key=True)
    eval_id: str = Field(foreign_key="evaluaciones.eval_id", index=True)
    codigo_evaluacion_energetica: Optional[str] = None
    orientacion_nombre: Optional[str] = None
    elementos_opacos_area_m2: Optional[float] = None
    elementos_opacos_u_w_m2_k: Optional[float] = None
    elementos_traslucidos_area_m2: Optional[float] = None
    elementos_traslucidos_u_w_m2_k: Optional[float] = None
    p01_w_k: Optional[float] = None
    p02_w_k: Optional[float] = None
    p03_w_k: Optional[float] = None
    p04_w_k: Optional[float] = None
    p05_w_k: Optional[float] = None
    ua_mas_phi_l: Optional[float] = None

    evaluacion: Evaluaciones = Relationship(back_populates="pagina3_envolvente")
    __table_args__ = (UniqueConstraint("eval_id", "orientacion_nombre", name="uq_eval_orient_p3e"),)


class InformeV2Pagina4(SQLModel, table=True):
    __tablename__ = "informe_v2_pagina4"
    id: Optional[int] = Field(default=None, primary_key=True)
    eval_id: str = Field(foreign_key="evaluaciones.eval_id", index=True)
    codigo_evaluacion_energetica: Optional[str] = None
    mes_id: Optional[int] = Field(default=None, foreign_key="meses.mes_id")
    demanda_calefaccion_viv_eval_kwh: Optional[float] = None
    demanda_calefaccion_viv_ref_kwh: Optional[float] = None
    demanda_enfriamiento_viv_eval_kwh: Optional[float] = None
    demanda_enfriamiento_viv_ref_kwh: Optional[float] = None
    sobrecalentamiento_viv_eval_hr: Optional[float] = None
    sobrecalentamiento_viv_ref_hr: Optional[float] = None
    sobreenfriamiento_viv_eval_hr: Optional[float] = None
    sobreenfriamiento_viv_ref_hr: Optional[float] = None

    evaluacion: Evaluaciones = Relationship(back_populates="pagina4")
    __table_args__ = (UniqueConstraint("eval_id", "mes_id", name="uq_eval_mes_p4"),)


class InformeV2Pagina5(SQLModel, table=True):
    __tablename__ = "informe_v2_pagina5"
    id: Optional[int] = Field(default=None, primary_key=True)
    eval_id: str = Field(foreign_key="evaluaciones.eval_id", index=True)
    codigo_evaluacion_energetica: Optional[str] = None
    mes_id: Optional[int] = Field(default=None, foreign_key="meses.mes_id")
    q_recuperado_kwh: Optional[float] = None
    q_puentes_termicos_kwh: Optional[float] = None
    q_contra_terreno_kwh: Optional[float] = None
    q_piso_ventilado_kwh: Optional[float] = None
    q_ventanas_kwh: Optional[float] = None
    q_muros_kwh: Optional[float] = None
    q_techo_kwh: Optional[float] = None
    q_infiltraciones_kwh: Optional[float] = None
    q_ventilacion_kwh: Optional[float] = None
    q_sol_kwh: Optional[float] = None

    evaluacion: Evaluaciones = Relationship(back_populates="pagina5")
    __table_args__ = (UniqueConstraint("eval_id", "mes_id", name="uq_eval_mes_p5"),)


class InformeV2Pagina6(SQLModel, table=True):
    __tablename__ = "informe_v2_pagina6"
    id: Optional[int] = Field(default=None, primary_key=True)
    eval_id: str = Field(foreign_key="evaluaciones.eval_id", index=True)
    codigo_evaluacion_energetica: Optional[str] = None
    mes_id: Optional[int] = Field(default=None, foreign_key="meses.mes_id")
    hora: Optional[int] = None
    temperatura_exterior: Optional[float] = None
    temperatura_interior: Optional[float] = None
    ocr_low_confidence: bool = Field(default=False)

    evaluacion: Evaluaciones = Relationship(back_populates="pagina6")
    __table_args__ = (UniqueConstraint("eval_id", "mes_id", "hora", name="uq_eval_mes_hora_p6"),)


class InformeV2Pagina7(SQLModel, table=True):
    __tablename__ = "informe_v2_pagina7"
    eval_id: str = Field(foreign_key="evaluaciones.eval_id", primary_key=True)
    codigo_evaluacion_energetica: Optional[str] = None
    mandante_nombre: Optional[str] = None
    mandante_rut: Optional[str] = None
    evaluador_nombre: Optional[str] = None
    evaluador_rut: Optional[str] = None
    evaluador_rol_minvu: Optional[str] = None

    evaluacion: Evaluaciones = Relationship(back_populates="pagina7")

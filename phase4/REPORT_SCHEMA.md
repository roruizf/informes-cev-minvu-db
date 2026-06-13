# Fase 4b — Refactor de Schema · Reporte

**Fecha:** 2026-06-13 · **Veredicto:** ✅ CERRADA (correcciones aplicadas y verificadas)

Aplica las correcciones de schema solicitadas por Roberto antes de Fase 5.

## Tareas completadas

**A — Renombres:** `region/comuna/tipo_evaluacion/tipo_vivienda` → `*_nombre`;
`demanda_calef/enfri` → `demanda_calefaccion/enfriamiento`; `*_per` → `*_porcentaje`
(incl. `calefaccion_kwh_per`→`calefaccion_porcentaje`); `*_proy/*_ref` →
`*_proyectado/*_referencia`; `consumo_ep_*`→`consumo_energia_primaria_*`;
`ua_phil`→`ua_mas_phi_l`; `temp_exterior/interior`→`temperatura_*`.

**B — Tipos:** `pagina1.porcentaje_ahorro` int→float; `busquedas.search_date` str→date.

**C — Tablas referencia + FK:** nuevas `meses`(12), `orientaciones`(10, incl. "Pisos"),
`tipos_vivienda`(poblada al extraer), `zonas_termicas`(letras A-I+B2 — lo que muestra
el PDF, no OGUC 1-7). FKs: pagina5/6.mes_id, pagina3_envolvente.orientacion_id,
pagina1/2.tipo_vivienda_id, pagina2.zona_termica_id.

**D — Redundancia controlada:** codigo_evaluacion/region_nombre/comuna_nombre/direccion/
tipo_vivienda_id se mantienen en cada tabla de página (autocontenidas para API/agentes).

**E — Pipeline:** capa `transform/normalize.py` (renames + resolución FK get-or-create +
fecha chilena) en lugar de tocar los extractores (que coinciden con coordenadas).
`pipeline/persist.py` reescrito para aplicarla. `discovery/run.py` actualizado a comuna_nombre.

**F — Migración:** drop+recreate vía `docker compose down -v` + `cev init` (sin datos reales).

## Evidencia (PDF Ancud, codigo=ba26352019)

- `process-pdf` → `status: extracted`, 8 tablas (p1=1,p2=1,p3c=1,p3e=10,p4=12,p5=2,p6=96,p7=1).
- **Nombres nuevos en SELECT:** region_nombre='X Región de Los Lagos', calefaccion_porcentaje=0.9,
  calefaccion_consumo_proyectado_kwh=17944.8, consumo_energia_primaria_calefaccion_kwh OK.
- **Tipos:** emitida_el=`2019-01-15` (date), porcentaje_ahorro=-12 (double precision).
- **FK por JOIN:** pagina6→meses (Enero), envolvente→orientaciones (Horiz/N/NE/E),
  pagina2→zonas_termicas (G) + tipos_vivienda (auto-creado), pagina4 demanda_calefaccion_* + mes FK.

## Notas
- Hallazgo: la envolvente tiene 10 orientaciones (incl. "Pisos"), no 9 — añadido al seed.
- zonas_termicas usa letras (A,D,F,G observadas en PDFs reales), no enteros OGUC.
- Decisiones registradas en memoria `schema-conventions`.

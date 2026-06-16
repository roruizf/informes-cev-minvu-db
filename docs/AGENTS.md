# Guía para Agentes de IA

Referencia técnica para agentes (Claude Code, Codex, OpenCode) que trabajen en el
código o consuman los datos vía NoCodeBackend.

## Estructura del proyecto

```text
src/informes_cev_minvu_db/
├── config.py            # Settings (pydantic-settings, lee .env)
├── app.py               # FastAPI + health checks + scheduler lifespan
├── scheduler.py         # APScheduler embebido (job diario 03:00 UTC)
├── cli.py               # cev init|discover|process-pdf|sync-mirror|daily|cleanup
├── db/
│   ├── models.py        # 15 tablas SQLModel
│   ├── session.py       # engine + get_session()
│   └── seed.py          # regiones, tipos_evaluacion, meses
├── discovery/
│   ├── portal_client.py # cliente ASP.NET (httpx + VIEWSTATE)
│   ├── html_parser.py   # XPaths + eval_id determinista
│   └── run.py           # orquestador discover()
├── pdf/
│   ├── coordinates.py   # get_page_coordinates(n) en mm (215.9×330.0)
│   ├── extractor.py     # págs 1-5,7 por coordenadas
│   ├── ocr_page6.py     # pág 6 por template matching + digit_templates.pkl
│   ├── version_detect.py# v1=4p / v2=7p
│   ├── extract_all.py   # extracción unificada + validación
│   └── downloader.py    # MINVU (postback) + Drive (gws)
├── transform/normalize.py # renames legacy→schema, resolución FK, fecha chilena
├── pipeline/
│   ├── persist.py       # escribe las 8 tablas de detalle (idempotente)
│   ├── process.py       # process_pdf: detect→extract→validate→persist→status
│   ├── queue.py         # process_pending [B1] + retry_failed (reactiva failed<max_retries)
│   ├── backfill.py      # backfill: discover región(es) + drena cola [B3]
│   ├── daily.py         # job diario (drena pendientes + mirror + cleanup)
│   └── cleanup.py       # PDFs huérfanos >N días
└── mirror/
    ├── nocode.py        # NocodeMirror (MCP DDL + REST CRUD, upsert incremental)
    └── sync.py          # orquestador run_sync()
```

## Schema de BD (15 tablas)

**Filosofía Capa 1:** capturar el valor crudo del PDF. Las dimensiones de texto
libre / fijas (tipo_vivienda, zona_termica, orientacion, tipo_evaluacion en pág1)
se guardan como `_nombre: str` directo — NO como tablas de referencia FK (la
limpieza/normalización es una Capa 2 futura).

**Referencia (dimensionales, solo estructurales):** `regiones`, `comunas`,
`tipos_evaluacion`, `meses`.
**Mecánica de scraping (NO se espejan):** `busquedas`, `paginas_html`.
**Directorio + datos:** `evaluaciones` + `informe_v2_pagina1..7`.

(Tipos: VARCHAR=texto, FLOAT=real, INTEGER=entero, DATE/DATETIME, BOOLEAN.)

### evaluaciones (directorio: universo total + estado del pipeline)
eval_id:VARCHAR PK, comuna_id FK, tipo_evaluacion_id FK, identificacion_vivienda,
tipologia, proyecto, calificacion_energetica_letra, calificacion_equipos_letra,
codigo_informe, codigo_etiqueta, pdf_download_status, report_version, retry_count,
last_error, last_processed_at, synced_to_mirror_at.

### informe_v2_pagina1 (etiqueta)
eval_id PK FK, codigo_evaluacion_energetica, tipo_evaluacion_nombre, region_nombre, comuna_nombre,
direccion, rol_vivienda_proyecto, tipo_vivienda_nombre (texto crudo), superficie_interior_util_m2,
porcentaje_ahorro:FLOAT, letra_eficiencia_energetica_dem,
demanda_calefaccion_kwh_m2_ano, demanda_enfriamiento_kwh_m2_ano, demanda_total_kwh_m2_ano,
emitida_el:DATE.

### informe_v2_pagina2 (envolvente descriptiva)
eval_id PK FK, + region_nombre, comuna_nombre, direccion, rol_vivienda, tipo_vivienda_nombre,
zona_termica_nombre (texto crudo, ej "G"), superficie_interior_util_m2, solicitado_por, evaluado_por,
demandas (calefaccion/enfriamiento/total/total_bis/total_referencia), porcentaje_ahorro,
y por elemento {muro_principal, muro_secundario, piso_principal, puerta_principal,
techo_principal, techo_secundario, superficie_vidriada_principal/secundaria,
ventilacion_rah, infiltraciones_rah} con _descripcion y _exigencia.

### informe_v2_pagina3_consumos (consumos + balance EP)
eval_id PK FK + ~52 columnas: consumos por uso (agua_caliente_sanitaria, iluminacion,
calefaccion, energia_renovable_no_convencional) en _kwh_m2 y _porcentaje; equipos
_proyectado_/_referencia_ (descripcion/kwh/porcentaje); consumo_energia_primaria_*;
fotovoltaica/solar_termica; coeficiente_energetico_c.

### informe_v2_pagina3_envolvente (10 filas/eval, una por orientación)
id PK, eval_id FK, orientacion_nombre (texto crudo: Horiz/N/NE/.../Pisos), elementos_opacos_area_m2, elementos_opacos_u_w_m2_k,
elementos_traslucidos_area_m2, elementos_traslucidos_u_w_m2_k, p01_w_k..p05_w_k, ua_mas_phi_l.

### informe_v2_pagina4 (12 filas/eval, demanda mensual)
id PK, eval_id FK, mes_id FK, demanda_calefaccion/enfriamiento_viv_eval/ref_kwh,
sobrecalentamiento/sobreenfriamiento_viv_eval/ref_hr.

### informe_v2_pagina5 (2 filas/eval: Enero, Julio — flujos Q)
id PK, eval_id FK, mes_id FK, q_recuperado/q_puentes_termicos/q_contra_terreno/
q_piso_ventilado/q_ventanas/q_muros/q_techo/q_infiltraciones/q_ventilacion/q_sol _kwh.

### informe_v2_pagina6 (96 filas/eval: 4 meses × 24h — temperaturas)
id PK, eval_id FK, mes_id FK, hora:INTEGER(0-23), temperatura_exterior,
temperatura_interior, ocr_low_confidence:BOOLEAN.

### informe_v2_pagina7 (antecedentes)
eval_id PK FK, mandante_nombre, mandante_rut, evaluador_nombre, evaluador_rut,
evaluador_rol_minvu.

## Reglas de negocio

- **eval_id determinista**: `uuid5(NAMESPACE_DNS, f"{comuna_id}_{region_id}_{tipo_evaluacion_id}_{identificacion}")`.
  Orden comuna_region_tipo. Re-descubrir/re-procesar es idempotente (upsert, sin duplicados).
- **Versiones**: solo v2 (7 páginas). v1 (4 páginas) → `pdf_download_status='skipped_v1'`.
- **Qué se espeja a NoCodeBackend**: `evaluaciones` (directorio = universo total) +
  `informe_v2_pagina1..7` + dimensionales. **NO** se espejan `busquedas` ni `paginas_html`.
  Invariante: directorio = todo lo disponible; tablas de detalle = lo ya procesado.
- **Mirror incremental**: upsert por clave de negocio (`eval_id`; multi-fila por `mirror_key`
  compuesto). Nunca full-replace (sería fatal a 156K).
- **Redundancia controlada (intencional)**: cada `informe_v2_paginaN` repite
  codigo_evaluacion_energetica/region_nombre/comuna_nombre/direccion/tipo_vivienda_nombre para ser
  autocontenida — los agentes consultan sin JOINs. No "normalizar" esto.
- **Página 6 = 2 filas tabulares siempre** (temperatura_exterior, temperatura_interior).
  El "3er perfil" visible (Temperatura media de confort) es solo una línea del gráfico,
  sin fila numérica. No existe variante de 3 filas que extraer.

## Convenciones de código

- **SQLModel** para modelos; tipos **normalizados** (FLOAT/INTEGER/DATE), no strings crudos.
  La normalización vive en `transform/normalize.py`, no en los extractores.
- **Coordenadas en mm** sobre página de referencia 215.9×330.0; `normalize_coordinates`
  escala a píxeles de la página real.
- **Nombres**: sin abreviaturas (`calefaccion`, `enfriamiento`, `proyectado`, `referencia`,
  `energia_primaria`, `porcentaje`, `temperatura`); columnas de nombre terminan en `_nombre`.
- **Página 5**: extracción por **tamaño de fuente** (los valores mostrados son tamaño ~12,
  los crudos ~5.8) — robusto a cambios de espaciado. **Página 3 envolvente**: por bloques de
  coordenadas (verificado correcto; no refactorizar sin necesidad). **Página 6**: template
  matching de glifos (`digit_templates.pkl`), no OCR de texto libre.

## Pipeline end-to-end

```text
discover (portal) → evaluaciones[pending]
  → downloader (Drive gws / MINVU)
  → version_detect (v1 skip / v2)
  → extract_all (extractor coords págs 1-5,7 + ocr_page6 pág 6)
  → transform/normalize (tipos, FK)
  → persist (8 tablas) → evaluaciones[extracted]
  → mirror/sync (incremental) → NoCodeBackend → evaluaciones.synced_to_mirror_at
  → delete PDF local
```

## Deuda técnica conocida

- **Descarga MINVU: RESUELTA (Fase 9).** El postback devuelve el PDF en el cuerpo
  (`%PDF...`, `Content-Disposition: attachment`) pero mal-etiquetado `text/html` y con
  HTML basura tras `%%EOF`. `_extract_pdf` lo detecta por magic bytes y recorta al
  `%%EOF`. Verificado end-to-end (descarga en vivo → v2 → 8 tablas). Algunos informes
  fallan portal-side (legítimo) → `failed`, reintenta con `cev retry-failed`.
- Reutilización de PDFs de Google Drive (I2): diferida; NO necesaria (MINVU funciona).
- I1 (optimización de viewstate): diferida.
- `evaluaciones.last_seen_at`: seteada en cada discovery; sin política de "stale" aún.
- OCR pág 6: confusiones ocasionales de 1 dígito (5↔6) y un caso de grid atípico (R12);
  las celdas dudosas se marcan `ocr_low_confidence=true`.

# Fase 3 — Discovery · Reporte

**Fecha:** 2026-06-13 · **Veredicto:** ✅ CERRADA (criterio cumplido con evidencia)

## Criterio de cierre (exigido)

> Comando ejecutado contra 1 comuna real + tabla `evaluaciones` con filas visibles.

## Evidencia

**Comando:** `cev discover --region 15 --comuna 12 --tipo 2 --max-pages 2` (Arica, Calificación).
Salida: `{region:15, comuna:12, tipo:2, total_reported:4079, pages:2, rows_seen:20, rows_new:20}`.

**`SELECT count(*) FROM evaluaciones` → 20**, con datos parseados:
```
 eval_id (uuid5) | comuna | tipo | identificacion              | ce | status
 342a6e43-...    |   12   |  2   | 50182-Mz A Lt 58 Psj Arq... | E  | pending
 ... (20 filas)
```

**`comunas` región 15 → 4** (Arica, Camarones, General Lagos, Putre) — poblada desde el dropdown.

**Idempotencia confirmada:** re-ejecutar el mismo discovery da `rows_new: 0`
(eval_id determinista → upsert, sin duplicados). Crítico para el backfill de ~156K.

## Qué se construyó

- `discovery/portal_client.py`: cliente del portal ASP.NET (httpx + VIEWSTATE). Métodos:
  `load`, `select_region` (postback que repuebla comunas), `search` (botón Consultar),
  `goto_page` (pager `__doPostBack(grid,'Page$N')`).
- `discovery/html_parser.py`: `parse_comunas`, `parse_total_count`, `parse_rows` (XPaths para
  ambas grillas Pre/Cal), `eval_id` = uuid5(`comuna_region_tipo_identificacion`).
- `discovery/run.py`: orquestador `discover(region, comuna?, tipos)` → sync comunas + upsert
  evaluaciones paginando.
- CLI `cev discover --region --comuna --tipo --max-pages`.

## Hallazgos del portal (verificados en vivo)

- HTTPS (el http:// legacy da 404). Requiere el set completo de campos legacy incl.
  `ToolkitScriptManager2_HiddenField`; sin él, el postback de región da HTTP 500.
- Resultados: 10/página; total reportado en `ResultadoGrilla{Cal,Pre}`; pager
  `__doPostBack('ctl00$ContentPlaceHolder1$grdViviendas{Cal,Pre}','Page$N')`.
- Grillas separadas por tipo: `grdViviendasPre` (1) / `grdViviendasCal` (2).
- Región 15 / comuna 12 / tipo 2 = 4.079 viviendas (no descargadas; solo directorio).

## Notas para Fase 4
- `--max-pages` se usó solo para la prueba; el backfill real omite el cap.
- Respeto al servidor: `delay` de 1s entre páginas (configurable).

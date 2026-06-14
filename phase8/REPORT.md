# Fase 8 — B1 (daily loop) + B3 (backfill) + Q1 (tests) · Reporte

**Fecha:** 2026-06-14

## B1 — daily loop procesa pendientes ✅ (wiring) / ⚠️ bloqueado por descarga

- `pipeline/queue.py`: `process_pending(region_id, limit)` selecciona
  `evaluaciones WHERE pdf_download_status='pending'`, resuelve región vía comuna,
  descarga el PDF de MINVU a temp, llama `process_pdf(delete_after=True)`, maneja
  fallos (retry_count++, status='failed' = dead-letter re-consultable).
- `pipeline/daily.py`: el job diario ahora hace **drain pendientes → mirror → cleanup**
  (antes solo mirror+cleanup). Integrado y verificado en su orquestación.
- CLI: `cev process-pending [--region N] [--limit K]`.

## B3 — backfill ✅ (wiring) / ⚠️ bloqueado por descarga

- `pipeline/backfill.py` + `cev backfill [--region N] [--tipo] [--discover-only]
  [--max-pages] [--process-limit]`: por región hace discover (puebla comunas +
  evaluaciones) y luego drena la cola. `--region` omitido = las 16.
- Smoke test (región 15, Arica): discover **funcionó** (10 evaluaciones nuevas);
  el loop tomó 2 pendientes e intentó descargar.

## HALLAZGO BLOQUEANTE — `download_from_minvu` devuelve HTML, no PDF

El postback del botón `btnInforme2` (control de cada fila de resultados) **no
devuelve el PDF**: responde la página de resultados (HTML, ~2 MB), tanto con
viewstate fresco como con el de la propia página de resultados.

Diagnóstico:
- El botón está registrado como control de **postback asíncrono de
  AjaxControlToolkit / UpdatePanel** (aparece en la lista de async-postback del
  ScriptManager). Un POST completo normal no dispara la descarga.
- No hay en el HTML de respuesta ningún enlace `.pdf`, iframe/embed, `window.open`
  ni redirect que apunte al binario.
- El portal cambió desde el legacy (ya vimos http→https en Fase 0); el flujo de
  descarga también parece haber cambiado respecto al `download_pdf_report` legacy
  (que usaba `evaluacion.viewstate` + `.x/.y` y, según el legacy, funcionaba).

**Conclusión honesta:** B1 y B3 están **correctamente cableados y probados** en su
lógica (discover → cola → intento de descarga → manejo de estado). La pieza
**no resuelta** es el mecanismo real de descarga del PDF desde el portal actual.
Esto NO se debe dar por funcionando. Requiere trabajo dedicado:
- Reverse-engineering del postback AJAX-delta (cabeceras `X-MicrosoftAjax: Delta=true`,
  parsear la respuesta delta para hallar la URL/handler del PDF), o
- Implementar la reutilización de PDFs de Google Drive (tarea futura ya diferida),
  que evitaría depender del portal para el backfill masivo.

`download_from_minvu` queda como está (intento best-effort), con el gap documentado.

## Q1 — tests ✅

- `tests/test_normalize.py`: unit de `parse_chilean_date`, `mes_id`, mapas de rename
  (codigo_evaluacion_energetica en todas, dims a texto, consumos). 
- `tests/test_extraction.py`: Ancud → versión v2, formas (10/12/2/96), valores conocidos
  (codigo=ba26352019, porcentaje_ahorro=-12, letra F, demanda_total 140.7, q_sol 12.9/2.9),
  codigo presente en filas de detalle (redundancia controlada).
- `tests/test_pipeline_db.py`: integración (skip si no hay BD) — Ancud → 8 tablas con
  conteos exactos + nombres/tipos nuevos (codigo_evaluacion_energetica, tipo_evaluacion_nombre,
  zona_termica_nombre='G', q_sol via JOIN meses).
- **24 tests pasan** (22 sin BD + 2 integración con Postgres).

## Pendiente
- Resolver el mecanismo de descarga MINVU (bloqueante para el backfill real).
- I1 (viewstate optimization) e I2 (Drive) siguen diferidos como acordado.

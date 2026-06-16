# Fase 9 — Fix descarga MINVU + retry + last_seen_at · Reporte

**Fecha:** 2026-06-14 · **Veredicto:** ✅ El "gap bloqueante" de Fase 8 estaba MAL
diagnosticado; la descarga FUNCIONA. Pipeline de extracción completo end-to-end.

## Corrección del diagnóstico de Fase 8

El postback `btnInforme2` **sí devuelve el PDF**. La respuesta:
- empieza con `%PDF-1.4`, cabecera `Content-Disposition: attachment; filename=E.pdf`;
- PERO el servidor la mal-etiqueta `Content-Type: text/html` y **añade HTML basura
  después del `%%EOF`**.

`download_from_minvu` la rechazaba por chequear el content-type. Fase-8 concluyó
erróneamente "gap bloqueante". (Lección repetida: validar contra los bytes reales,
no la señal superficial.)

## A — fix descarga ✅

`pdf/downloader.py::_extract_pdf`: detecta el PDF por magic bytes (`%PDF`), recorta
al último `%%EOF`, descarta basura HTML. Si no hay `%PDF` en el cuerpo → `None` →
descarga falla (caso legítimo: algunos informes fallan en el propio portal, lo
confirmó Roberto manualmente en el navegador con `{readyState:0,status:0}`).

**Verificado end-to-end (descarga en vivo del portal):** región 10 / comuna 6 / tipo 2 →
descarga → detecta v2 → extrae → **8 tablas pobladas** (p1=1,p2=1,p3c=1,p3env=10,
p4=12,p5=2,p6=96,p7=1), datos reales (codigo e7c99c2022, Región de Los Lagos, Ancud,
letra E, demanda 310). `failed: 0`. Los reportes v1 (4p) se marcan `skipped_v1` OK.

## B — estrategia de reintentos ✅

- Fallo de descarga → `failed`, `retry_count++`, `last_error` (dead-letter).
- `process_pending` solo toma `pending` (salta `failed`).
- `cev retry-failed [--region N] [--max-retries 3] [--limit K]`: reactiva los
  `failed` con `retry_count < max_retries` → `pending` y drena. Los que superan
  el tope quedan `failed` definitivo (sin bucle infinito). Verificado: corre limpio.

## last_seen_at ✅

Columna `evaluaciones.last_seen_at` (timestamp) seteada en cada upsert de discovery.
Permite detectar informes que dejan de aparecer en el portal (observabilidad; sin
política de borrado/stale por ahora). Verificado: poblada en los 21 evals descubiertos.

## Tests ✅
- `tests/test_downloader.py` (5): `_extract_pdf` (trim %%EOF, None sin PDF, múltiples EOF, bytes previos).
- Suite total: **27 tests pasan**.

## Pendiente / diferido
- Google Drive como 2º origen (I2): diferido a fase aparte (no necesario — la descarga MINVU funciona).
- I1 (viewstate): diferido.
- Política para informes "desaparecidos" (usar `last_seen_at`): observabilidad lista, política futura.
- OCR pág 6: deuda 5↔6 / R12 (celdas dudosas marcadas `ocr_low_confidence`).

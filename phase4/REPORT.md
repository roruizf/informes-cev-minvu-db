# Fase 4 — PDF Pipeline · Reporte

**Fecha:** 2026-06-13 · **Veredicto:** ✅ CERRADA (criterio cumplido con evidencia)

## Criterio de cierre (exigido)

> Un PDF procesado de principio a fin + datos en todas las tablas de detalle.

## Evidencia

`cev process-pdf --eval-id test-eval-10-6-2profile --path /test_pdfs/EX_2profile_10_6_1.pdf`
→ `status: extracted, version: 2, validation ok: True`.

**Filas escritas en las 8 tablas de detalle** (verificado por SQL):
```
pagina1=1  pagina2=1  pagina3_consumos=1  pagina3_envolvente=10
pagina4=12 pagina5=2  pagina6=96          pagina7=1
```

**Datos reales consultables (pagina1):**
`codigo=ba26352019, region=X Región de Los Lagos, comuna=Ancud, letra=F,
demanda_total=140.7, emitida_el=2019-01-15` (fecha normalizada de `15-01-2019`).

**pagina6 (temps horarias):** 96 filas (4 meses × 24h); 2 celdas low-confidence en enero
marcadas con NULL (deuda 5↔6 diferida). `evaluaciones.pdf_download_status=extracted, version=2`.

## Auditoría de schema (tarea 1)

- **Discrepancia resuelta con el Manual CEV 2019:** el mapa del Manual ubica temps en pág.7
  y metodología en pág.6, pero los PDF v2 REALES (verificado en múltiples) ponen
  **temps horarias en pág.6, flujos Q en pág.5, antecedentes en pág.7**. Se confía en el PDF
  (fuente de verdad del scraping). Schema correcto sin cambios. Ver memoria `page-layout-truth`.
- **Cobertura de campos:** auditado modelo vs claves de los extractores legacy refinados
  (págs 1,2,3-consumos,7) → el modelo cubre todos los campos. Sin correcciones necesarias.

## Qué se construyó

- `pdf/coordinates.py` (de Fase 0), `pdf/extractor.py` (págs 1-5,7 por coordenadas, del legacy
  refinado), `pdf/ocr_page6.py` + `digit_templates.pkl` (template matching de Fase 1),
  `pdf/version_detect.py` (v1=4p / v2=7p), `pdf/extract_all.py` (extracción unificada + validación).
- `pdf/downloader.py`: descarga MINVU (postback codigo_informe) + Drive (gws) — híbrida.
- `pipeline/persist.py`: persistencia idempotente en las 8 tablas + normalización de fecha chilena.
- `pipeline/process.py`: orquestador acquire→detect→extract→validate→persist→status; v1→skipped_v1.
- CLI: `cev process-pdf --eval-id --path [--ensure-eval]`.

## Pendiente para integración masiva (Fase 4-completion / backfill)
- Reconciliación Drive↔eval por `codigo_evaluacion` (find_on_drive es stub).
- Política de borrado Drive sólo tras validar+persistir (red de seguridad acordada).
- Deuda OCR diferida: confusiones 5↔6, outlier R12.

# Fase 5 — Mirror NoCodeBackend · Reporte

**Fecha:** 2026-06-13 · **Veredicto:** ✅ CERRADA (criterio cumplido con evidencia live)

## Criterio de cierre (exigido)

> Registro visible en NoCodeBackend vía REST API.

## Evidencia (instancia CEV dedicada, credenciales en .env gitignored)

**Sync live** (`cev sync-mirror --limit 1`) tras procesar el PDF de Ancud:
- Tablas auto-creadas vía MCP `execute_sql` (DDL), filas vía REST.
- Dimensionales: regiones=16, comunas=1, tipos_evaluacion=2, meses=12, orientaciones=10,
  tipos_vivienda=2, zonas_termicas=10.
- Directorio + detalle: evaluaciones=1, pagina1=1, pagina2=1, pagina3_consumos=1, pagina7=1,
  pagina3_envolvente=10, pagina4=12, pagina5=2, pagina6=96.

**Lectura de vuelta vía REST (closure):**
```
search('evaluaciones', {eval_id:'test-ancud-ba26352019'}) → 1 fila
  comuna_id=12, pdf_download_status=extracted, report_version=2
search('informe_v2_pagina1', ...) → region_nombre='X Región de Los Lagos', letra='F'
```

**Incremental upsert (requisito de diseño crítico):** re-sync `--full` → TODO `updated`,
0 `created`. Sin duplicados: evaluaciones=1 (no 2), pagina6=96 (no 192). Esto hace seguro
el backfill de ~156K, a diferencia del full-replace de sgip.

## Qué se construyó

- `mirror/nocode.py`: `NocodeMirror` (patrón sgip: MCP para DDL, REST para CRUD) con
  **upsert incremental por clave de negocio** (`search`→`update`|`create`), NO full-replace.
- `mirror/sync.py`: orquestador. Sincroniza dimensionales (upsert por PK) + directorio
  `evaluaciones` (por eval_id) + 8 tablas de detalle. Multi-fila usa `mirror_key` compuesto
  (eval_id+discriminador) para upsert exacto. Marca `synced_to_mirror_at`. EXCLUYE
  busquedas/paginas_html. Serializa fechas a ISO.
- CLI `cev sync-mirror [--limit N] [--full]`.

## Limitación conocida (no bloquea)
- En re-syncs, `ensure_table` (CREATE TABLE IF NOT EXISTS vía MCP) emite un warning
  "Could not determine user email for limit check" — es best-effort sobre tablas que ya
  existen (no-op) y NO afecta el path REST de datos. El access token tiene scope de perfil
  limitado. Si se quisiera silenciar, ensure_table puede cachear qué tablas ya existen.

## Limpieza post-test
- Las 125 filas de prueba del eval test se borraron del mirror; las dimensionales quedan
  (datos de referencia legítimos).

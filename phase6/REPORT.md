# Fase 6 — Deploy + Scheduler · Reporte

**Fecha:** 2026-06-13 · **Veredicto:** ✅ CERRADA localmente (criterio cumplido);
deploy real a Zeabur pendiente de la cuenta de Roberto.

## Criterio de cierre (exigido)

> Endpoint `/health` respondiendo 200 desde Zeabur.

## Evidencia (simulación de deploy fresco = config idéntica a Zeabur)

`docker compose up -d --build` sobre volumen limpio:
- **Entrypoint auto-inicializa la BD:** `seeded: {regiones:16, tipos_evaluacion:2, meses:12,
  orientaciones:10, zonas_termicas:10}` — sin paso manual.
- **Scheduler embebido arranca:** `scheduler started: daily job at 03:00 UTC`.
- **`GET /health` → 200** `{"status":"ok","ts":...}`.
- `GET /health/db` → 200; `GET /health/last-scrape` → 200; `POST /admin/run-daily` → 200
  (background, no bloquea).
- DB con 16 regiones tras arranque en volumen nuevo.
- Job diario (CLI `cev daily`) ejecuta mirror incremental + cleanup correctamente
  (dimensionales `updated`, evals ya sincronizados = "nothing to sync").

## Qué se construyó

- `scheduler.py`: APScheduler embebido (BackgroundScheduler), job cron diario a
  `DAILY_SCRAPE_HOUR`:00 UTC, arranca/para vía lifespan de FastAPI. Estado del último
  run en memoria para `/health/last-scrape`.
- `pipeline/daily.py`: job diario (mirror incremental + cleanup); el backfill masivo es
  one-shot aparte.
- `pipeline/cleanup.py`: borrado de PDFs huérfanos >`PDF_CLEANUP_DAYS` días (preventivo;
  el sistema NUNCA toca Drive).
- `app.py`: lifespan que arranca el scheduler (desactivable con `CEV_ENABLE_SCHEDULER=0`);
  `/admin/run-daily` en background.
- `docker-entrypoint.sh` + Dockerfile CMD: `cev init` (idempotente) → uvicorn. Una imagen
  fresca en Zeabur se auto-inicializa.
- `mirror/nocode.py`: cache `_ensured` — silencia el warning MCP en re-syncs (skip DDL si
  la tabla ya tiene datos).
- CLI: `cev cleanup`, `cev daily`.
- `DEPLOY.md`: pasos para Zeabur (Postgres add-on, env vars, health check, backfill vs diario).

## Pendiente (requiere a Roberto)
- **Deploy real:** conectar el repo a Zeabur + Postgres add-on + setear env vars
  (DATABASE_URL con `+psycopg`, credenciales NoCodeBackend). Ver DEPLOY.md.
- **Backfill ~156K:** ejecutar `cev discover` por región + drenar la cola (one-shot).
- Reconciliación Drive (`find_on_drive` stub) si se reutilizan PDFs de Drive.
- Deuda OCR diferida: confusiones 5↔6, outlier R12.

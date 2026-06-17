# Deploy en Zeabur

El sistema es **un solo servicio Docker** (FastAPI + APScheduler embebido) + un
add-on **PostgreSQL** gestionado por Zeabur. Sin cron externo: el scheduler corre
dentro del contenedor.

## Pasos

1. **Crear proyecto en Zeabur** y conectar este repo (rama `main`).
2. **Añadir servicio PostgreSQL** (add-on de un clic). Zeabur expone su URL de conexión.
3. **Servicio app** (se construye desde el `Dockerfile` de la raíz):
   - Variables de entorno (Settings → Environment):
     - `DATABASE_URL` = la URL del Postgres de Zeabur, en formato
       `postgresql+psycopg://USER:PASS@HOST:PORT/DB`
       (Zeabur suele dar `postgresql://...`; añade `+psycopg`).
     - `NOCODEBACKEND_INSTANCE`, `NOCODEBACKEND_SECRET_KEY`, `NOCODEBACKEND_ACCESS_TOKEN`
     - **`CEV_ADMIN_TOKEN`** (recomendado en prod): protege los endpoints `/admin/*`
       con un token compartido. Ver "Token de admin" abajo. Si se omite, los endpoints
       quedan abiertos (la URL de Zeabur es pública).
     - (opcional) `MINVU_BASE_URL`, `DOWNLOAD_CONCURRENCY`, `DOWNLOAD_DELAY` (seg entre
       descargas, default 1.5), `MAX_RETRIES` (default 3), `PDF_DIR`, `PDF_CLEANUP_DAYS`,
       `DAILY_SCRAPE_HOUR` (UTC, default 3).
     - (opcional, Fase 13) `DISCOVERY_CONCURRENCY` (unidades comuna/tipo en paralelo,
       default 8), `DB_CONNECT_RETRIES` (default 6), `DB_CONNECT_BACKOFF` (seg, default 2.0).
   - Puerto: 8000 (el `Dockerfile` lo expone; Zeabur lo detecta).
4. **Health check:** Zeabur puede sondear `GET /health` (200). El `Dockerfile` ya
   incluye un `HEALTHCHECK` equivalente.
5. **Inicialización de la BD:** el contenedor corre `cev init` (crea tablas + seed)
   al arrancar, vía el `command` del compose. En Zeabur, si se usa solo el Dockerfile
   (cuyo `CMD` es uvicorn), ejecutar una vez `cev init` desde la consola del servicio,
   o añadir un pre-deploy hook. **Alternativa simple:** dejar el `CMD` como
   `sh -c "cev init && uvicorn ..."` (ver Dockerfile.zeabur abajo si se prefiere).

## Operación

### Backfill SIN terminal — `POST /admin/run-backfill` (Fase 13, recomendado)

El backfill ya **no depende de tener la consola de Zeabur abierta con `nohup`**. Corre
como tarea de background dentro del propio proceso FastAPI: dispáralo con un `POST` y
ciérra el navegador; sigue corriendo. Si el Postgres de Zeabur se reinicia (recovery
mode), la conexión se reintenta con backoff (`DB_CONNECT_RETRIES`) en vez de morir.

```bash
# Primera corrida COMPLETA (las 16 regiones) — discovery completo, sin early-stop:
curl -X POST "https://TU-APP.zeabur.app/admin/run-backfill" \
  -H "X-Admin-Token: $CEV_ADMIN_TOKEN"

# Una región piloto (recomendado: medir antes de escalar):
curl -X POST "https://TU-APP.zeabur.app/admin/run-backfill?region=13" \
  -H "X-Admin-Token: $CEV_ADMIN_TOKEN"
```

Parámetros (query string): `region` (1-16; omite para las 16), `tipo` (1|2; omite ambos),
`discover_only` (true = solo descubrir, no drenar), `max_pages` (cap por comuna, pruebas),
`process_limit` (cap de PDFs extraídos por región), `incremental` (early-stop por comuna),
`resume` (retomar unidades ya completadas). Responde de inmediato (`202`-style JSON);
un segundo `POST` mientras hay uno corriendo devuelve `409`.

### Monitorear progreso — `GET /admin/backfill-status`

```bash
curl "https://TU-APP.zeabur.app/admin/backfill-status" -H "X-Admin-Token: $CEV_ADMIN_TOKEN"
```
Devuelve el estado vivo del run (`running`, `started_at`, `finished_at`, `summary`,
`error`) **más** métricas de BD: `pending_downloads`, `failed_downloads`,
`evaluaciones_total`, y del checkpoint de discovery `discovery_units_total` /
`_done` / `_early_stopped`.

### Token de admin (`CEV_ADMIN_TOKEN`)

Si `CEV_ADMIN_TOKEN` está seteado, **todos** los `/admin/*` (incl. `run-daily`) exigen
el header `X-Admin-Token: <valor>`; un token incorrecto/ausente da `401`. Si la variable
está vacía, los endpoints quedan abiertos (compatibilidad). En Zeabur: Settings →
Environment → `CEV_ADMIN_TOKEN` = (un secreto largo). Genera uno con
`python -c "import secrets; print(secrets.token_urlsafe(32))"`.

### Retomar una región a medio procesar (ej. región 12)

Si una corrida cayó a mitad (la región 12 quedó incompleta), **no re-paginar todo**:
usa `resume=true`. El checkpoint `discovery_progress` salta las unidades (comuna, tipo)
ya marcadas `done` y retoma las parciales desde su última página. La descarga ya es
idempotente por `pdf_download_status` (no re-descarga lo ya `extracted`).

```bash
# Retoma la región 12 sin re-procesar lo ya hecho (discovery + drena cola):
curl -X POST "https://TU-APP.zeabur.app/admin/run-backfill?region=12&resume=true" \
  -H "X-Admin-Token: $CEV_ADMIN_TOKEN"
# equivalente por CLI:  cev backfill --region 12 --resume
```

### Backfill por CLI (alternativa, requiere consola)

`cev backfill` (las 16) o `cev backfill --region N`. Descubre (en paralelo,
`DISCOVERY_CONCURRENCY` unidades a la vez) y drena la cola (descarga + extracción).
NO es el job diario. La descarga MINVU funciona (ver `phase9/REPORT.md`); las descargas
usan orden aleatorio y un delay de `DOWNLOAD_DELAY` segundos entre PDFs. Flags Fase 13:
`--resume` (retomar) y `--incremental` (early-stop, solo para deltas — ver MANUAL §3).

- **Reintentos:** los informes que fallan en el portal quedan `failed`; reintenta los
  transitorios con `cev retry-failed` (respeta `MAX_RETRIES`).
- **Mirror NoCodeBackend — IMPORTANTE (una vez por instance):** crear las tablas con
  `cev mirror-init` **desde una máquina donde el MCP funcione (ej. local)**. El MCP
  (DDL/CREATE TABLE) falla desde Zeabur con "Could not determine user email for limit
  check" (chequeo atado al contexto del datacenter), pero el REST (insertar datos)
  funciona desde cualquier lado. Por eso `mirror-init` se corre una vez localmente y
  luego `cev sync-mirror` en Zeabur solo usa REST (nunca MCP). Si una tabla falta, el
  sync reporta error por-tabla y NO marca los evals como sincronizados.
- **Fase estable:** el scheduler embebido corre el job diario a `DAILY_SCRAPE_HOUR`:00 UTC
  (drena pendientes + mirror incremental + cleanup). Disparo manual: `POST /admin/run-daily`.

## Endpoints
- `GET /health` — proceso vivo.
- `GET /health/db` — `SELECT 1` contra Postgres.
- `GET /health/last-scrape` — último run del scheduler + pendientes.
- `POST /admin/run-daily` — dispara el job diario en background.
- `POST /admin/run-backfill` — dispara el backfill (o una región) en background (Fase 13).
- `GET /admin/backfill-status` — estado vivo del backfill + métricas de progreso (Fase 13).

> Los `/admin/*` exigen header `X-Admin-Token` si `CEV_ADMIN_TOKEN` está seteado.

## Notas
- El cleanup de Google Drive es MANUAL (Roberto); el sistema nunca toca Drive.
- El cleanup local de PDFs huérfanos (>`PDF_CLEANUP_DAYS` días) corre en el job diario.
- Secretos solo por variables de entorno; nunca en el repo (`.env` está gitignored).

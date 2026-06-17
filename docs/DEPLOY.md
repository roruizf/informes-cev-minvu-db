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
     - (opcional) `MINVU_BASE_URL`, `DOWNLOAD_CONCURRENCY`, `DOWNLOAD_DELAY` (seg entre
       descargas, default 1.5), `MAX_RETRIES` (default 3), `PDF_DIR`, `PDF_CLEANUP_DAYS`,
       `DAILY_SCRAPE_HOUR` (UTC, default 3).
   - Puerto: 8000 (el `Dockerfile` lo expone; Zeabur lo detecta).
4. **Health check:** Zeabur puede sondear `GET /health` (200). El `Dockerfile` ya
   incluye un `HEALTHCHECK` equivalente.
5. **Inicialización de la BD:** el contenedor corre `cev init` (crea tablas + seed)
   al arrancar, vía el `command` del compose. En Zeabur, si se usa solo el Dockerfile
   (cuyo `CMD` es uvicorn), ejecutar una vez `cev init` desde la consola del servicio,
   o añadir un pre-deploy hook. **Alternativa simple:** dejar el `CMD` como
   `sh -c "cev init && uvicorn ..."` (ver Dockerfile.zeabur abajo si se prefiere).

## Operación

- **Fase inicial (backfill ~156K):** comando one-shot desde la consola del servicio:
  `cev backfill` (las 16 regiones) o `cev backfill --region N`. Descubre y drena la cola
  (descarga + extracción). NO es el job diario. La descarga MINVU funciona (ver
  `phase9/REPORT.md`); las descargas usan orden aleatorio y un delay de `DOWNLOAD_DELAY`
  segundos entre PDFs para no saturar el portal. **Recomendado:** correr 1 región piloto
  primero (`cev backfill --region 13`), medir, y luego escalar a las 16.
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
- `POST /admin/run-daily` — dispara el job en background.

## Notas
- El cleanup de Google Drive es MANUAL (Roberto); el sistema nunca toca Drive.
- El cleanup local de PDFs huérfanos (>`PDF_CLEANUP_DAYS` días) corre en el job diario.
- Secretos solo por variables de entorno; nunca en el repo (`.env` está gitignored).

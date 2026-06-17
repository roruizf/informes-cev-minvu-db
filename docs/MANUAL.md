# Manual del Operador

Guía práctica para operar el sistema. No requiere conocimientos de programación.

## 1. Configuración (`.env`)

Copia `.env.example` a `.env` y completa los valores. Variables:

| Variable | Para qué | Ejemplo / default |
|----------|----------|-------------------|
| `DATABASE_URL` | Conexión a PostgreSQL | `postgresql+psycopg://cev:cev@db:5432/cev` |
| `NOCODEBACKEND_INSTANCE` | ID de la base en NoCodeBackend | (lo da NoCodeBackend) |
| `NOCODEBACKEND_SECRET_KEY` | API REST de datos | (secreto) |
| `NOCODEBACKEND_ACCESS_TOKEN` | Crear tablas (MCP) | (secreto) |
| `MINVU_BASE_URL` | Portal MINVU | `https://calificacionenergeticaweb.minvu.cl` |
| `DOWNLOAD_CONCURRENCY` | Descargas paralelas | `8` |
| `DOWNLOAD_DELAY` | Segundos entre descargas de PDF (cortesía con el portal) | `1.5` |
| `DISCOVERY_CONCURRENCY` | Unidades (comuna, tipo) descubiertas en paralelo | `8` |
| `DB_CONNECT_RETRIES` | Reintentos al conectar a la BD (outage transitorio) | `6` |
| `DB_CONNECT_BACKOFF` | Espera inicial entre reintentos de BD (seg, se duplica) | `2.0` |
| `CEV_ADMIN_TOKEN` | Token para proteger los endpoints `/admin/*` | (secreto; vacío = abierto) |
| `PDF_DIR` | Carpeta temporal de PDFs | `/tmp/cev_pdfs` |
| `PDF_CLEANUP_DAYS` | Días antes de borrar huérfanos | `7` |
| `DAILY_SCRAPE_HOUR` | Hora del job diario (UTC) | `3` |

**Los secretos nunca se suben al repo** (`.env` está en `.gitignore`).

## 2. Comandos CLI (`cev`)

Se ejecutan dentro del contenedor: `docker compose exec app cev <comando>`.

| Comando | Qué hace |
|---------|----------|
| `cev init` | Crea las tablas + carga datos de referencia (regiones, meses, etc.) |
| `cev discover --region N [--comuna C] [--tipo 1\|2] [--max-pages K] [--incremental] [--resume]` | Descubre informes del portal → tabla `evaluaciones` (en paralelo) |
| `cev process-pdf --eval-id X --path archivo.pdf [--ensure-eval]` | Procesa un PDF concreto → 8 tablas de detalle |
| `cev mirror-init` | Crea las tablas en NoCodeBackend (una vez por instance, **desde local** — el MCP falla en Zeabur) |
| `cev sync-mirror [--limit N] [--full]` | Empuja datos a NoCodeBackend (incremental, solo REST) |
| `cev process-pending [--region N] [--limit K]` | Drena la cola: descarga + extrae los `pending` |
| `cev retry-failed [--region N] [--max-retries 3] [--limit K]` | Reactiva los `failed` con reintentos disponibles y los drena |
| `cev backfill [--region N] [--discover-only] [--max-pages K] [--process-limit K] [--incremental] [--resume]` | Descubre una región (o las 16) y drena la cola |
| `cev daily` | Job diario: drena pendientes + mirror + cleanup |
| `cev cleanup` | Borra PDFs locales huérfanos (>N días) |

`--max-pages` limita páginas de resultados (10 informes/página); útil para pruebas.
El `--full` re-sincroniza todo aunque ya esté marcado como sincronizado.
`--resume` retoma sin re-procesar (checkpoint); `--incremental` se detiene apenas una
comuna deja de dar informes nuevos (ver §3).

## 3. Flujo de trabajo típico

### Carga inicial — PRIMERA corrida completa (una vez, ~156K informes)

La primera vez hay que recorrer **todas las páginas de todas las comunas**, así que se
corre **SIN `--incremental`**. El discovery es paralelo (`DISCOVERY_CONCURRENCY`); la
descarga de PDFs sigue siendo serial y educada (`DOWNLOAD_DELAY`).

```bash
# por CLI (requiere consola):
docker compose exec app cev backfill                 # las 16 regiones
docker compose exec app cev backfill --region 13     # una región piloto
docker compose exec app cev sync-mirror              # empuja al espejo
```
En Zeabur, sin terminal, usa el endpoint (ver §3.bis y DEPLOY.md):
`POST /admin/run-backfill` (todas) o `?region=13` (una).

### `--incremental` vs primera corrida — CUÁNDO usar cada uno

| Modo | Cuándo | Qué hace |
|------|--------|----------|
| **Sin flag** (completo) | **Primera carga** o re-verificación total | Pagina TODAS las páginas de cada comuna. Lento pero exhaustivo. |
| **`--incremental`** | **Job diario / buscar solo lo nuevo** | El portal lista lo más nuevo primero; apenas una comuna entrega 2 páginas seguidas **sin informes nuevos**, deja de paginar esa comuna. Evita re-paginar ~90% de páginas viejas. |

> ⚠️ `--incremental` asume que el portal ordena **del más nuevo al más viejo**. Es lo
> observado, pero si alguna vez el orden cambia, corre **sin** el flag (siempre correcto,
> solo más lento). Para la **primera** corrida usa siempre el modo completo.

### Retomar tras una caída — `--resume` (ej. región 12 a medio procesar)

Si una corrida se cortó (la región 12 quedó incompleta), **no empieces de cero**:

```bash
docker compose exec app cev backfill --region 12 --resume
# o en Zeabur sin terminal:
#   POST /admin/run-backfill?region=12&resume=true   (header X-Admin-Token)
```
`--resume` lee el checkpoint `discovery_progress`: salta las unidades (comuna, tipo) ya
`done` y retoma las parciales desde su última página. La descarga ya es idempotente
(`pdf_download_status`), así que no re-descarga lo ya `extracted`. Combinable con
`--incremental` si solo buscas deltas.

### 3.bis Operar desde Zeabur SIN terminal (endpoints admin, Fase 13)

```bash
# Lanzar backfill (no necesita nohup ni consola abierta):
curl -X POST "https://TU-APP.zeabur.app/admin/run-backfill?region=12&resume=true" \
  -H "X-Admin-Token: $CEV_ADMIN_TOKEN"

# Monitorear progreso (pendientes, unidades de discovery done/total, etc.):
curl "https://TU-APP.zeabur.app/admin/backfill-status" -H "X-Admin-Token: $CEV_ADMIN_TOKEN"
```
El token sale de `CEV_ADMIN_TOKEN` (ver §1). Si no lo seteas, los `/admin/*` quedan
abiertos. Detalle completo de parámetros y respuestas: `docs/DEPLOY.md`.

> **Descarga MINVU:** funciona. El servidor mal-etiqueta el PDF como `text/html` y le
> añade HTML tras el `%%EOF`; el sistema lo detecta por magic bytes (`%PDF`) y lo recorta.
> Algunos informes fallan en el propio portal (error AJAX) → quedan en `failed`; usa
> `cev retry-failed` para reintentar los transitorios. Los reportes v1 (4 páginas) se
> marcan `skipped_v1` (fuera de alcance). Reutilizar PDFs de Drive es mejora futura.

**Operación estable (automática):** el scheduler corre el job diario a las
`DAILY_SCRAPE_HOUR`:00 UTC: drena pendientes, sincroniza lo nuevo al espejo y limpia
PDFs huérfanos. Para dispararlo a mano: `POST /admin/run-daily` o `cev daily`. Para
buscar informes nuevos de forma rápida: `cev discover --region N --incremental`.

## 4. Dónde ver resultados

- **Health checks** (navegador o curl):
  - `GET /health` — el servicio está vivo.
  - `GET /health/db` — la base de datos responde.
  - `GET /health/last-scrape` — último job + cuántos informes quedan pendientes.
  - `GET /admin/backfill-status` — progreso del backfill en vivo (requiere `X-Admin-Token`
    si `CEV_ADMIN_TOKEN` está seteado).
- **Base de datos (PostgreSQL):** la fuente de verdad. Ej:
  `docker compose exec db psql -U cev -d cev -c "SELECT count(*) FROM evaluaciones;"`
- **NoCodeBackend:** el espejo de lectura, accesible vía su panel web y REST API.
  Lo consultan los agentes de IA.

## 5. Política de almacenamiento

- **PDFs locales (VPS):** se borran automáticamente tras extraer y guardar los datos.
  Un job diario barre cualquier huérfano de más de `PDF_CLEANUP_DAYS` días.
- **Google Drive:** el sistema **nunca** toca tu Drive. Tú borras los PDF de Drive
  manualmente cuando quieras (tras confirmar que se procesaron).
- **Datos:** viven en PostgreSQL (completo) y se espejan a NoCodeBackend (para agentes).

## 6. Versiones de informe

- Solo se procesan informes **v2 (7 páginas)**. Los **v1 (4 páginas)** se detectan
  y se marcan `skipped_v1` (fuera de alcance).

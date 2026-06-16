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
| `PDF_DIR` | Carpeta temporal de PDFs | `/tmp/cev_pdfs` |
| `PDF_CLEANUP_DAYS` | Días antes de borrar huérfanos | `7` |
| `DAILY_SCRAPE_HOUR` | Hora del job diario (UTC) | `3` |

**Los secretos nunca se suben al repo** (`.env` está en `.gitignore`).

## 2. Comandos CLI (`cev`)

Se ejecutan dentro del contenedor: `docker compose exec app cev <comando>`.

| Comando | Qué hace |
|---------|----------|
| `cev init` | Crea las tablas + carga datos de referencia (regiones, meses, etc.) |
| `cev discover --region N [--comuna C] [--tipo 1\|2] [--max-pages K]` | Descubre informes del portal → tabla `evaluaciones` |
| `cev process-pdf --eval-id X --path archivo.pdf [--ensure-eval]` | Procesa un PDF concreto → 8 tablas de detalle |
| `cev sync-mirror [--limit N] [--full]` | Empuja datos a NoCodeBackend (incremental) |
| `cev process-pending [--region N] [--limit K]` | Drena la cola: descarga + extrae los `pending` |
| `cev retry-failed [--region N] [--max-retries 3] [--limit K]` | Reactiva los `failed` con reintentos disponibles y los drena |
| `cev backfill [--region N] [--discover-only] [--max-pages K] [--process-limit K]` | Descubre una región (o las 16) y drena la cola |
| `cev daily` | Job diario: drena pendientes + mirror + cleanup |
| `cev cleanup` | Borra PDFs locales huérfanos (>N días) |

`--max-pages` limita páginas de resultados (10 informes/página); útil para pruebas.
El `--full` re-sincroniza todo aunque ya esté marcado como sincronizado.

## 3. Flujo de trabajo típico

**Carga inicial (una vez, ~156K informes):**
```bash
# descubre + procesa todas las regiones (o una): discover -> drena pendientes
docker compose exec app cev backfill                 # las 16 regiones
docker compose exec app cev backfill --region 13     # una región
docker compose exec app cev sync-mirror              # empuja al espejo
```

> **Descarga MINVU:** funciona. El servidor mal-etiqueta el PDF como `text/html` y le
> añade HTML tras el `%%EOF`; el sistema lo detecta por magic bytes (`%PDF`) y lo recorta.
> Algunos informes fallan en el propio portal (error AJAX) → quedan en `failed`; usa
> `cev retry-failed` para reintentar los transitorios. Los reportes v1 (4 páginas) se
> marcan `skipped_v1` (fuera de alcance). Reutilizar PDFs de Drive es mejora futura.

**Operación estable (automática):** el scheduler corre el job diario a las
`DAILY_SCRAPE_HOUR`:00 UTC: sincroniza lo nuevo al espejo y limpia PDFs huérfanos.
Para dispararlo a mano: `POST /admin/run-daily` o `cev daily`.

## 4. Dónde ver resultados

- **Health checks** (navegador o curl):
  - `GET /health` — el servicio está vivo.
  - `GET /health/db` — la base de datos responde.
  - `GET /health/last-scrape` — último job + cuántos informes quedan pendientes.
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

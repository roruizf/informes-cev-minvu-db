# informes-cev-minvu-db

Sistema **ELT** para los Informes de Calificación Energética de Viviendas (CEV v2)
del MINVU de Chile. Scrapea el directorio público del portal, descarga los PDF
de 7 páginas, extrae y normaliza los datos (coordenadas + OCR), los almacena en
PostgreSQL y los espeja (una vía) en NoCodeBackend para consumo por agentes de IA.

## Qué hace

- **Descubre** el universo de informes disponibles por región/comuna/tipo (portal ASP.NET).
- **Descarga** los PDF (híbrido: Google Drive existente vía gws + portal MINVU).
- **Extrae** las 7 páginas: 1-5 y 7 por coordenadas (PyMuPDF), página 6 (temperaturas
  horarias) por **template matching** de dígitos (la fuente es constante → ~95% precisión).
- **Normaliza** tipos (decimales chilenos, fechas DD-MM-YYYY, FK a tablas de referencia).
- **Persiste** en PostgreSQL (18 tablas) y **espeja incremental** a NoCodeBackend.
- **Opera 24/7**: scheduler embebido (job diario), health checks, cleanup de PDFs.

## Arquitectura (conceptual)

```text
                    ┌──────────────── Contenedor Docker (Zeabur) ────────────────┐
                    │                                                             │
  Portal MINVU ◀────┤  discovery/   → evaluaciones (directorio: universo total)   │
  (ASP.NET)         │  portal_client + html_parser                                │
                    │       │                                                      │
  Google Drive ◀────┤  pdf/ downloader (Drive gws / MINVU)                         │
  (gws, PDFs)       │       │                                                      │
                    │       ▼                                                      │
                    │  pdf/ version_detect (v1=4p skip / v2=7p)                    │
                    │  pdf/ extractor (págs 1-5,7 coords) + ocr_page6 (pág 6)      │
                    │       │                                                      │
                    │  transform/normalize (tipos, FK)                             │
                    │       ▼                                                      │
                    │  pipeline/persist → PostgreSQL 16 (18 tablas)  ◀── verdad    │
                    │       │                                                      │
                    │  mirror/sync (incremental, upsert por eval_id)               │
                    │  FastAPI: /health · /health/db · /health/last-scrape         │
                    │  APScheduler: job diario 03:00 UTC                           │
                    └──────────────────────────┬──────────────────────────────────┘
                                               │ (una vía, incremental)
                                               ▼
                                     NoCodeBackend  ◀── agentes IA leen vía REST/MCP
```

PostgreSQL es la **fuente de verdad**; NoCodeBackend es un espejo de lectura.

## Stack

Python 3.12 · FastAPI · SQLModel · **PostgreSQL 16** · httpx · lxml · PyMuPDF ·
OpenCV + template matching (página 6) · APScheduler · Docker · deploy en Zeabur.

## Fases

| Fase | Logro |
|------|-------|
| 0 — Factibilidad | Portal HTTPS, gws en Docker, reconciliación por codigo_evaluacion |
| 1 — OCR página 6 | Template matching de dígitos (94.8% vs verdad-base); supera Tesseract/EasyOCR |
| 2 — Scaffolding | Paquete + Docker + Postgres + 14 tablas + health checks |
| 3 — Discovery | Scraping del directorio MINVU → evaluaciones (idempotente) |
| 4 — PDF pipeline | Extracción 7 págs → 8 tablas de detalle, normalización |
| 4b — Schema | Renames, tipos, 4 tablas de referencia + FK (18 tablas) |
| 5 — Mirror | Sync incremental unidireccional a NoCodeBackend |
| 6 — Deploy | Scheduler embebido + cleanup; deploy-ready Zeabur |
| 7 — Refactor | Página 5 robustecida (font-size); schema Capa 1 (15 tablas, texto crudo) |
| 8 — Operación | daily loop procesa pendientes (B1); `cev backfill` (B3); tests (Q1) |
| 9 — Descarga + retry | fix descarga MINVU (magic bytes %PDF + trim %%EOF); `cev retry-failed`; `last_seen_at` |

> **Pipeline completo y verificado end-to-end** (descarga en vivo → v2 → 8 tablas).
> La descarga del portal MINVU funciona (el servidor mal-etiqueta el PDF como
> `text/html` y le añade HTML tras el `%%EOF`; se detecta por magic bytes y se recorta).
> Algunos informes fallan legítimamente en el portal → quedan `failed` y se reintentan
> con `cev retry-failed`. Reutilizar PDFs de Google Drive queda como mejora futura.

## Inicio rápido (local)

```bash
cp .env.example .env          # completar credenciales NoCodeBackend
docker compose up -d --build  # app:8000 + postgres:5432 (auto cev init)
curl localhost:8000/health    # {"status":"ok",...}
docker compose exec app cev discover --region 15 --comuna 12 --tipo 2 --max-pages 1
```

## Documentación

- [docs/MANUAL.md](docs/MANUAL.md) — guía del operador (humano).
- [docs/AGENTS.md](docs/AGENTS.md) — guía para agentes de IA (estructura, schema, reglas).
- [docs/DEPLOY.md](docs/DEPLOY.md) — despliegue en Zeabur.

## Ramas

`main` (deploy) ← `develop` (integración) ← `fase-N` (trabajo por fase).

# informes-cev-minvu-db

Sistema ELT que scrapea el portal CEV del MINVU (Chile), descarga los Informes
CEV v2 (PDF de 7 páginas), extrae y normaliza los datos, los almacena en
PostgreSQL y los espeja (una vía) en NoCodeBackend para consumo por agentes.

## Estado por fases

| Fase | Estado | Entregable |
|------|--------|-----------|
| 0 — Factibilidad | ✅ | Pruebas A-E + reporte |
| 1 — OCR página 6 | ✅ | Template matching 94.8% (`phase1/`) |
| 2 — Scaffolding | ✅ | `docker compose up` + 16 regiones |
| 3 — Discovery | ✅ | Scraping del directorio MINVU (`cev discover`) |
| 4 — PDF pipeline | ✅ | Extracción (págs 1-5,7 coords + 6 OCR) → 8 tablas |
| 4b — Schema | ✅ | Renames, tipos, tablas referencia + FK |
| 5 — Mirror | ✅ | Sync incremental a NoCodeBackend (`cev sync-mirror`) |
| 6 — Deploy | ✅ | Scheduler embebido + cleanup; deploy-ready Zeabur (ver DEPLOY.md) |

## Desarrollo local

```bash
docker compose up -d --build          # levanta app (8000) + postgres (5432)
curl localhost:8000/health            # health check
docker compose exec db psql -U cev -d cev -c "SELECT * FROM regiones;"
```

El contenedor `app` corre `cev init` (crea tablas + seed de regiones/tipos) al arrancar.

## CLI

```bash
cev init-db    # crea tablas
cev seed       # seed regiones (16) + tipos (2)
cev init       # ambos
```

## Stack

Python 3.12 · FastAPI · SQLModel · PostgreSQL · httpx · PyMuPDF · Tesseract +
template-matching (página 6) · APScheduler · Docker (deploy en Zeabur).

## Ramas

`main` (deploy) ← `develop` (integración) ← `fase-N` (trabajo por fase).

# Fase 2 — Scaffolding · Reporte

**Fecha:** 2026-06-13 · **Veredicto:** ✅ CERRADA (criterio cumplido con evidencia)

## Criterio de cierre (exigido)

> `docker compose up` funcionando + `SELECT * FROM regiones` devolviendo 16 filas.

## Evidencia

**Contenedores (docker compose ps):** ambos `Up (healthy)`
```
informes-cev-minvu-db-app-1  ...  Up (healthy)  0.0.0.0:8000->8000/tcp
informes-cev-minvu-db-db-1   postgres:16      Up (healthy)  0.0.0.0:5432->5432/tcp
```

**`SELECT count(*) FROM regiones` → 16** (nombres canónicos del portal MINVU):
Tarapacá, Antofagasta, Atacama, Coquimbo, Valparaíso, O'Higgins, Maule, Biobío,
Araucanía, Los Lagos, Aysén, Magallanes, Metropolitana, Los Ríos, Arica y Parinacota, Ñuble.

**`tipos_evaluacion` → 2:** Precalificación / Calificación Energética.

**14 tablas creadas** (regiones, comunas, tipos_evaluacion, busquedas, paginas_html,
evaluaciones, informe_v2_pagina1..7).

**Health endpoints (todos 200):**
- `/health` → `{"status":"ok","ts":...}`
- `/health/db` → `{"status":"ok","db":"reachable"}`
- `/health/last-scrape` → `{"status":"ok","last_processed_at":null,"pending":0}`

## Qué se construyó

- Paquete `src/informes_cev_minvu_db/`: `config.py` (pydantic-settings), `app.py` (FastAPI + health),
  `cli.py` (`cev init|init-db|seed`), `db/{models,session,seed}.py`, y carpetas vacías para
  discovery/pdf/transform/pipeline/mirror (Fases 3-6).
- `db/models.py`: 14 tablas SQLModel (esquema datacev) con **tipos normalizados** (float/int/date),
  + control de pipeline en `evaluaciones` (status, retry_count, synced_to_mirror_at) y
  `ocr_low_confidence` en pagina6.
- `pyproject.toml` (uv/hatchling, script `cev`), `Dockerfile` (python:3.12-slim + tesseract-spa +
  libs OCR + HEALTHCHECK), `docker-compose.yml` (app + postgres:16 con healthcheck).
- Seed de 16 regiones (nombres del portal en vivo) + 2 tipos. Comunas → Fase 3 (discovery).

## Notas para fases siguientes
- `evaluaciones` no tiene `region_id` directo (vía FK comuna→region), como el legacy.
- `init` corre en el arranque del contenedor (idempotente).

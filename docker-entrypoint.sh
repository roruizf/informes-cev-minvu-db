#!/bin/sh
# Zeabur/Docker entrypoint: init DB (idempotent) then run the API with the
# embedded scheduler. `cev init` creates tables + seeds reference data; safe to
# run on every boot.
set -e
echo "[entrypoint] cev init (create tables + seed)..."
cev init || echo "[entrypoint] cev init failed (continuing; may already be initialized)"
echo "[entrypoint] starting uvicorn..."
exec uvicorn informes_cev_minvu_db.app:app --host 0.0.0.0 --port 8000

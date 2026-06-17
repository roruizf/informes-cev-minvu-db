# Fase 12 — limpieza + resiliencia de red · Reporte

**Fecha:** 2026-06-15

## Contexto: primer run real en Zeabur (región 12, 20 PDFs)

`cev process-pending --region 12 --limit 20` → `extracted: 3, skipped_v1: 17, failed: 0`
en ~4-5 min (≈13-15 s/PDF). El pipeline funciona; la mayoría de región 12 son v1.

## Hecho

- **Eliminada `evaluaciones.search_id_descubrimiento`**: columna heredada del legacy,
  siempre NULL, nunca usada (Capa 1: no arrastrar campos no capturados).
- **Retry/backoff de red en `PortalClient._request`**: los GET/POST al portal reintentan
  (4 intentos, backoff 3/6/9/12s) ante errores transitorios (SSL EOF, drops,
  rate-limit blips, timeouts). `downloader` usa el mismo helper. Tests unitarios con
  cliente HTTP mockeado.

## Diferido (con razón)

- **Optimización viewstate por comuna (I1):** procesar pendientes agrupados por
  (comuna,tipo) y reusar un solo search/viewstate para varios PDFs (en vez de 4
  requests por PDF). Reduciría requests ~4x y el tiempo a ~3-5 s/PDF. **NO implementada
  aún** porque mi IP de pruebas quedó bloqueada por el portal (demasiados requests hoy)
  y NO se debe shippear lógica de portal sin verificar en vivo. Se implementa+verifica
  desde Zeabur (su IP no está bloqueada) o cuando la IP de pruebas se libere.

## Hallazgo: rate-limiting REAL del portal

Tras cientos de requests de prueba en el día, el portal **dejó de responder a mi IP**
(SSL EOF sostenido incluso en un GET simple). Confirma que el rate-limiting es real.
Mitigaciones ya en su sitio: `DOWNLOAD_DELAY` (1.5s), orden aleatorio, y ahora
retry/backoff. La optimización viewstate (menos requests/PDF) reduciría el riesgo.
**El bloqueo es a la IP de pruebas, NO a la de Zeabur** (datacenter distinto).

## Nota operativa (Zeabur)

La tabla `evaluaciones` en producción aún tiene la columna `search_id_descubrimiento`
(el `create_all` del entrypoint no dropea columnas). Es inocua (siempre NULL). Para
limpiarla, opcional, una vez:
`ALTER TABLE evaluaciones DROP COLUMN search_id_descubrimiento;`

## Tests
31 pasan (29 sin DB + 2 integración). Nuevos: `test_portal_client.py` (retry/backoff).

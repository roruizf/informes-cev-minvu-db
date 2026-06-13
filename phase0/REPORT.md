# Fase 0 — Reporte de Factibilidad

**Fecha:** 2026-06-13 · **Veredicto:** ✅ SEGUIR (con un cambio mayor de estrategia en página 6)

Muestra: 11 PDFs (2 ejemplos canónicos + 9 regiones). Entorno: `venv` con PyMuPDF 1.27.2, OpenCV, pytesseract; Tesseract 4.1.1 en host. Scripts en `phase0/scripts/`, salidas en `phase0/outputs/`.

---

## Resumen ejecutivo

| Test | Resultado | Evidencia |
|------|-----------|-----------|
| **A — Coordenadas** | ✅ Válidas para v2 | 7/11 son v2 (7p) y extraen región/código limpio; PDFs con rectángulos en `outputs/*_rects.pdf` para tu revisión visual |
| **B — Portal MINVU** | ✅ Vivo (cambió a HTTPS) | `https://...BusquedaVivienda.aspx` → 200; VIEWSTATE ok; VIEWSTATEGENERATOR=`2B422A52` (idéntico al legacy); 16 regiones |
| **C — OCR pág. 6** | ✅ **OCR INNECESARIO** | Los datos están en la **capa de texto**; 192/192 valores extraídos por PDF, 0 OCR |
| **D — gws en Docker** | ✅ Factible (auth ok) | gws lista Drive con refresh token válido; para Docker usar `KEYRING_BACKEND=file` + montar config |
| **E — SQLite legacy + reconciliación** | ✅ | Esquema = SQLModel (14 tablas); reconciliación por `codigo_evaluacion` (consistente en págs 1/3/7) |

---

## HALLAZGO CRÍTICO (Test C) — La página 6 NO requiere OCR

La premisa del PROMPT ("números diminutos en gráficos de Excel → OCR; 2 vs 3 perfiles cambian coordenadas") **es incorrecta**, verificado empíricamente:

- La página 6 tiene, por mes, un **gráfico (imagen raster)** + una **TABLA de datos en CAPA DE TEXTO**.
- La tabla siempre tiene **2 filas numéricas**: `T° exterior` y `T Interior`, cada una con 24 valores horarios (columnas 0..23).
- El "3er perfil" visible (`Temperatura media de confort`) es **solo una línea del gráfico** — NO tiene fila tabular. Por eso "2 vs 3 perfiles" no cambia nada en los datos extraíbles.
- `extract_page6.py` agrupa palabras numéricas por coordenada (y=fila, x=hora) y produce **24/24 exterior + 24/24 interior en los 4 meses**, todos en rango físico [-20,50]°C, en los 7 PDFs v2. **Tasa: 4/4 bandas válidas en 7/7 PDFs = 100%.**

**Implicación:** desaparece el problema de rendimiento (no hay ~45M llamadas Tesseract), el problema de detección 2-vs-3, y el riesgo principal del proyecto. OCR queda como **fallback** solo para PDFs sin capa de texto (escaneados), si existen — a confirmar sobre una muestra mayor en Fase 1.

## Test A — Coordenadas
- Coordenadas legacy de `get_page_coordinates()` siguen válidas para v2 (extraen región, código, etc.).
- **Detección v1/v2 confirmada y trivial:** los v1 tienen **4 páginas**, los v2 **7**. Los 4 PDFs v1 de la muestra devolvieron basura en coords v2 → `page_count==7` es el discriminador.
- Entregables para tu visto bueno: `phase0/outputs/<nombre>_rects.pdf` (rectángulos dibujados) y `<nombre>_p6.png` (render pág. 6).

## Test B — Portal MINVU
- Único cambio: `http://` → `https://`. La URL exacta del PROMPT da 404 en http, 200 en https.
- VIEWSTATE/VIEWSTATEGENERATOR/dropdown de regiones intactos → form-data builders del legacy funcionan con el cambio de esquema.
- No se ejecutó postback completo (respeto al servidor); connectividad + VIEWSTATE + dropdown bastan como evidencia de viabilidad.

## Test D — gws-cli en Docker
- gws en host: OAuth2 con refresh token válido, lista Drive vía REST correctamente.
- Para container headless: `GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file` + montar `~/.config/gws` (client_secret.json + credentials.enc). Pendiente: build real del container (verificado por diseño).
- Acceso a PDFs: por `fileId` / query de carpeta (`q="'FOLDER_ID' in parents"`), NO por ruta. Sin FUSE.

## Test E — SQLite legacy + reconciliación
- Esquema legacy = 14 tablas, idéntico al SQLModel de datacev. `informe_v2_pagina6` = (eval_id, codigo_evaluacion, mes, hora, temp_exterior, temp_interior) → **solo 2 perfiles**, refuerza Test C.
- `evaluaciones` no tiene `region_id` (región vía FK comuna→region).
- **Reconciliación Drive↔directorio:** el UUID del nombre de archivo NO es el eval_id. La llave real es `codigo_evaluacion` leído del PDF (consistente en págs 1/3/7), que se cruza con el directorio. Tarea de Fase 4.

---

## Decisiones que habilita esta fase
1. **Pág. 6 por capa de texto (primario), OCR solo fallback.** Reescribe el plan de Fase 1.
2. v1/v2 por `page_count`.
3. Portal con https; reusar form-data legacy.
4. gws headless con backend `file`; reconciliar por `codigo_evaluacion`.
5. Importar esquema legacy como baseline (los datos de 2.3GB se re-extraen, no se migran).

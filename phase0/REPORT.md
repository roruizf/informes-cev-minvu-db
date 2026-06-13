# Fase 0 — Reporte de Factibilidad

**Fecha:** 2026-06-13 · **Veredicto:** ✅ SEGUIR · **Página 6 requiere OCR (plan original confirmado)**

> **CORRECCIÓN (importante):** Una versión previa de este reporte concluyó erróneamente
> que la página 6 no necesitaba OCR porque las temperaturas estaban en la capa de texto.
> **Esa conclusión era un falso positivo.** Roberto exigió comparar la capa de texto contra
> los valores realmente impresos. Resultado: en la MISMA posición (fila enero exterior),
> la capa de texto dice `15,8 14,9 13,8 12,7...` mientras la TABLA IMPRESA (rasterizada)
> dice `11,9 10,9 10,4 10,0...`. **Son números distintos.** La capa de texto es un decoy
> (datos obsoletos/de otra capa); los valores correctos que ve un humano están en la imagen.
> **OCR es necesario.** Evidencia visual: `phase0/outputs/PROOF_enero_table_vs_textlayer.png`.
> Lección: validar estructura (24/24, en rango) NO basta; hay que validar CORRECTITUD contra lo impreso.

Muestra: 11 PDFs (2 ejemplos canónicos + 9 regiones). Entorno: `venv` con PyMuPDF 1.27.2, OpenCV, pytesseract; Tesseract 4.1.1 en host. Scripts en `phase0/scripts/`, salidas en `phase0/outputs/`.

---

## Resumen ejecutivo

| Test | Resultado | Evidencia |
|------|-----------|-----------|
| **A — Coordenadas** | ✅ Válidas para v2 | 7/11 son v2 (7p) y extraen región/código limpio; PDFs con rectángulos en `outputs/*_rects.pdf` para tu revisión visual |
| **B — Portal MINVU** | ✅ Vivo (cambió a HTTPS) | `https://...BusquedaVivienda.aspx` → 200; VIEWSTATE ok; VIEWSTATEGENERATOR=`2B422A52` (idéntico al legacy); 16 regiones |
| **C — OCR pág. 6** | ⚠️ **OCR NECESARIO** | La capa de texto es un DECOY (no coincide con la tabla impresa). Plan original de OCR confirmado. Ver corrección arriba. |
| **D — gws en Docker** | ✅ Factible (auth ok) | gws lista Drive con refresh token válido; para Docker usar `KEYRING_BACKEND=file` + montar config |
| **E — SQLite legacy + reconciliación** | ✅ | Esquema = SQLModel (14 tablas); reconciliación por `codigo_evaluacion` (consistente en págs 1/3/7) |

---

## Test C — Página 6: OCR ES NECESARIO (capa de texto descartada)

Hipótesis examinada: "los valores horarios están en la capa de texto → no hace falta OCR".
**Falsada** con la prueba de correctitud que exigió Roberto:

- La página 6 SÍ tiene una capa de texto con números plausibles (24 valores, rango físico,
  curva suave) en la posición de la tabla. Por eso una validación solo-estructural daba 100%.
- PERO al comparar contra la **tabla impresa** (rasterizada, lo que ve el humano), en la
  MISMA posición (enero, fila exterior):
  - capa de texto: `15,8 14,9 13,8 12,7 12,1 11,8 ...`
  - tabla impresa: `11,9 10,9 10,4 10,0 10,0 11,0 ...`
  - **No coinciden.** La capa de texto es un decoy (datos obsoletos o de otra capa de render).
- El OCR del método legacy sobre esa tabla produce ruido (`104,0`, `25,124`, `322,922`),
  confirmando por qué los intentos previos fallaron: la tabla es difícil de OCR-ear.

**Implicación:** se mantiene el PLAN ORIGINAL — OCR para la página 6 es obligatorio y sigue
siendo el reto mayor del proyecto. La Fase 1 (harness de calibración OCR con criterio ≥95%
24/24) procede tal como estaba previsto. NO se debe confiar en la capa de texto de la pág. 6.
Evidencia: `phase0/outputs/PROOF_enero_table_vs_textlayer.png` (render de la tabla impresa).

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
- Esquema legacy = 14 tablas, idéntico al SQLModel de datacev. `informe_v2_pagina6` = (eval_id, codigo_evaluacion, mes, hora, temp_exterior, temp_interior) → **solo 2 perfiles** (exterior/interior).
- `evaluaciones` no tiene `region_id` (región vía FK comuna→region).
- **Reconciliación Drive↔directorio:** el UUID del nombre de archivo NO es el eval_id. La llave real es `codigo_evaluacion` leído del PDF (consistente en págs 1/3/7), que se cruza con el directorio. Tarea de Fase 4.

---

## Decisiones que habilita esta fase
1. **Pág. 6 requiere OCR (plan original).** NO confiar en la capa de texto — es un decoy. Fase 1 = harness de calibración OCR con criterio ≥95% 24/24.
2. v1/v2 por `page_count`.
3. Portal con https; reusar form-data legacy.
4. gws headless con backend `file`; reconciliar por `codigo_evaluacion`.
5. Importar esquema legacy como baseline (los datos de 2.3GB se re-extraen, no se migran).

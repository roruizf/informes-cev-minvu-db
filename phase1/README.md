# Fase 1 — Harness de calibración OCR (página 6)

**Objetivo:** extraer las temperaturas horarias de la página 6 (4 meses × 2 filas × 24 horas)
por OCR, con **≥95% de valores coincidiendo con lo impreso** (no solo 24/24 en rango).

**Por qué OCR:** la capa de texto de la página 6 es un decoy (Fase 0). Los valores correctos
están en la tabla rasterizada → OCR obligatorio.

**Branch:** `fase-1` (nace de `develop`, que nace de `main`).

---

## Metodología de verdad-base (muestreo estratificado)

- 60 PDF v2 variados desde Drive (margen sobre 50), procesados y borrados; se conservan solo
  los renders de evidencia de casos flagged.
- El harness auto-marca celdas sospechosas: fuera de rango físico, salto brusco vs vecinas,
  o baja confianza de Tesseract.
- Roberto verifica a ojo solo: TODAS las flagged + ~20 celdas aleatorias por PDF.
- Precisión = % de acierto sobre lo verificado.

## Estimación
- Cómputo: ~4-6 s OCR por página 6 (medido). ~30-60 s/PDF con varias variantes → 60 PDF ≈ 30-60 min.
- <1 GB RAM, sin GPU. Cuellos de botella: descarga Drive + tiempo de verificación humana.

---

## Layout de la tabla de página 6 (medido en Fase 0)

- 4 bandas de mes (Enero, Abril, Julio, Octubre), de arriba a abajo.
- Cada banda: gráfico (imagen) arriba + tabla abajo con fila de horas (0..23) + `T° exterior` + `T Interior`.
- Coordenadas legacy de la franja de cada mes (mm sobre página 215.9×330.0):
  enero (64.5,97.7,173.2,103.1) · abril (64.6,152.5,173.8,157.8) · julio (66.4,211.8,174.0,217.5) · octubre (65.8,271.0,174.5,276.4)

---

## LOG DE VARIANTES OCR

Cada variante: parámetros Tesseract, DPI, preprocesamiento, y resultado en precisión.

| # | DPI | Preprocesamiento | Tesseract cfg | Segmentación | Precisión (vs impreso) | Notas |
|---|-----|------------------|---------------|--------------|------------------------|-------|
| _baseline (legacy)_ | 300 | Otsu + medianBlur | `--oem 3 --psm 6` franja completa | franja de fila entera | ~ruido (`104,0`,`25,124`) | método legacy; falla por dígitos pegados |
| 1 | 600 | adaptiveThreshold + morfología | `--psm 8` whitelist `0-9,.` | celda (vlines + filas en tercios) | ~0% (basura) | vlines bien detectadas (~107px), pero: (a) boundaries desfasadas 1 col, (b) filas por tercios cortan los dígitos → fila interior toda None, (c) ruido de vlines en etiqueta y margen. Segmentación a corregir. |
| 2 | 600 | adaptiveThreshold | `--psm 8` whitelist | columnas por pitch mediano + filas por bandas de tinta (con bordes) | ~0% (todo None) | columnas reconstruidas bien (pitch 108px, 25 bounds), pero las "filas" detectaban las LÍNEAS del grid (49,118,187), no el texto → celdas vacías. |
| 3 | 600 | resize×2 + Otsu + borde | `--psm 8` whitelist `0-9,.` | columnas por pitch + filas por proyección de tinta en región de datos | ~parcial (valores reconocibles con dígito extra) | ¡filas correctas! Lee `12.6`,`22.3` exactos. Error sistemático: dígito de más a la izq (`111.9`→`11.9`, `114.6`→`14.6`): la celda sangra al vecino izq / grid. Falta inset de celda + ajuste de anclaje. |
| 4 | 600 | resize×2 + Otsu + borde | `--psm 8` whitelist `0-9,.` | columnas por pitch + inset celda 16%/4% | enero ext **16/24**, int **12/24** | Gran salto: muchas celdas exactas. Inset fijo no robusto. |
| 5 | 600 | componentes conexas + resize×3 | `--psm 8` whitelist | columnas + crop a blobs de dígito | ext 14/24, int 5/24 | crop funde dígitos vecinos; no mejora. |
| 6 | 600 | + borrado de líneas de grid (morfología) | `--psm 8` | celda | **0/24** | borrado de líneas demasiado agresivo, come trazos de dígitos. REVERTIDO. |
| 7 | EasyOCR (torch CPU) | resize×3 fila completa | allowlist `0-9.,-` | fila entera, bin por x-center | ext **11/24** int 3/24 | EasyOCR RECONOCE excelente pero agrupa celdas vecinas (`21.8122312251223`). |
| 8 | EasyOCR | celda aislada resize×4 | allowlist | por celda | 4/24 | EasyOCR pierde contexto en celda diminuta aislada. |
| 9 | EasyOCR | fila + separadores blancos en bordes de columna | allowlist | fila con gaps + bin x | ext 13/24 int 8/24 | grilla CONFIRMADA correcta (separadores caen en los gaps), pero EasyOCR aún puentea bordes y a veces recorta último dígito. |
| (Tess psm7/8/13 sobre celda limpia) | 600 | crop+blur+Otsu | psm 7/8/13 whitelist | celda | ~12/24 | error sistemático: `1` fantasma a la izq (`111.6`←`11.9`) aun con celda perfectamente recortada. Límite del motor. |

**Variantes 1-9 (Tesseract/EasyOCR):** techo ~65%. Fallo residual por fusión de celdas
(EasyOCR) o dígito fantasma (Tesseract). Grilla de columnas bien detectada.

| 10 | template matching | 600 | segmentación de GLIFOS + plantillas por dígito | clasificación por correlación (TM_CCOEFF_NORMED) | **enero 45/48 (94%), julio 46/48 (96%, datos no vistos)** | ¡FUNCIONA! La fuente es constante → plantillas de dígito generalizan. Filtra remanente de línea de grid (el "1 fantasma") por altura. Misses son confusiones de 1 dígito (5↔6) mejorables con más muestras. |

**CONCLUSIÓN:** el enfoque ganador es **template matching de dígitos** (no OCR de texto libre).
Rompe el techo de 65% → ~94-96% validado en datos no vistos. Causa raíz resuelta: la fuente
del informe es única, así que clasificar glifos individuales contra plantillas vence a los
motores OCR genéricos. Siguiente: ampliar plantillas (más muestras/dígito) y escalar a 5→60 PDF.

---

## Hallazgo doc2md (importante)

- doc2md sobre el **PDF** de pág.6 → `ocr_applied: false`, lee la CAPA DE TEXTO DECOY
  (`15,8 14,9...`) = valores INCORRECTOS. Confirma de nuevo que la capa de texto engaña.
- doc2md sobre la **imagen rasterizada** de pág.6 (forzando OCR) → lee `11.9 10.9 10.4`
  (exterior) y `23.0 22.3 21.5` (interior) = **CORRECTOS** en las primeras celdas. Pero su
  OCR de página completa funde celdas (`230/|223/215`, `1015.0`) y no entrega 24 valores
  separados (encontró 34 números donde debían ser 24).
- **Conclusión:** la receta ganadora = RASTERIZAR (evita el decoy) + SEGMENTAR por celda
  (fuerza 24 valores) + OCR de celda única. doc2md prueba que los valores correctos SÍ son
  OCR-ables; el reto es la disciplina de segmentación, no el motor.

## Resultados
_(en progreso — iterando segmentación por celda hasta ≥90% en 3-5 PDF)_

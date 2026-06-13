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
| 4 | 600 | resize×2 + Otsu + borde | `--psm 8` whitelist `0-9,.` | columnas por pitch + inset celda 16%/4% | enero ext **16/24**, int **12/24** | Gran salto: muchas celdas exactas (`10.4 10.0 11.0 12.6 14.6 16.6 18.3`). Inset fijo no es robusto a la posición variable del dígito (`218.0`,`270.9` aún sangran; `7.0` pierde dígito). Siguiente: recorte por componentes conexas (blobs de dígito) dentro de celda + filtrar fragmentos de grid. |

---

## Resultados
_(pendiente)_

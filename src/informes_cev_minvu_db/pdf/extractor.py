"""Coordinate-based extractors for pages 1-5,7 (page 6 uses ocr_page6).

Ported verbatim from the refined Informe-CEV-v2-pdf-scraper/scraping_functions.py.
get_page_coordinates lives in coordinates.py.
"""
from bisect import bisect_left
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import fitz

from informes_cev_minvu_db.pdf.coordinates import get_page_coordinates



def normalize_coordinates(
    x: float,
    y: float,
    report_width: float,
    report_height: float,
    page_width: float,
    page_height: float
) -> Tuple[float, float]:
    """Normalize coordinates with caching for repeated calculations."""
    try:
        rx = (x / report_width) * page_width
        ry = (y / report_height) * page_height
        return rx, ry
    except ZeroDivisionError:
        logging.error(
            "Report width or height cannot be zero for normalization.")
        return 0.0, 0.0



def extract_text_from_area(page: fitz.Page, area: Tuple[float, float, float, float]) -> str:
    """
    Extract text from a specific area of a PDF page. Robust error handling.
    """
    if not isinstance(page, fitz.Page):
        logging.error(
            "Invalid page object provided to extract_text_from_area.")
        return ""

    if not isinstance(area, tuple) or len(area) != 4:
        logging.error(
            f"Invalid area format provided: {area}. Must be a tuple of 4 coordinates.")
        return ""

    REPORT_WIDTH = 215.9  # mm
    REPORT_HEIGHT = 330.0  # mm

    try:
        page_rect = page.rect
        if page_rect is None:
            logging.error("Could not get page rectangle.")
            return ""
        width = page_rect.width
        height = page_rect.height

        if width <= 0 or height <= 0:
            logging.error(
                f"Invalid page dimensions in extract_text_from_area: width={width}, height={height}")
            return ""

        x1, y1, x2, y2 = area
        if not all(isinstance(coord, (int, float)) for coord in area):
            logging.error(
                f"Coordinates must be numeric in extract_text_from_area: {area}")
            return ""

        if x1 >= x2 or y1 >= y2:
            logging.warning(
                f"Invalid coordinates provided: {area}. Ensure x1 < x2 and y1 < y2.")
            return ""

        # Normalize coordinates
        rx1, ry1 = normalize_coordinates(
            x1, y1, REPORT_WIDTH, REPORT_HEIGHT, width, height)
        rx2, ry2 = normalize_coordinates(
            x2, y2, REPORT_WIDTH, REPORT_HEIGHT, width, height)

        # Ensure normalized coordinates create a valid rectangle
        if rx1 >= rx2 or ry1 >= ry2:
            logging.warning(
                f"Normalized coordinates resulted in invalid rectangle: ({rx1}, {ry1}, {rx2}, {ry2}) from area {area}")
            return ""

        rect = fitz.Rect(rx1, ry1, rx2, ry2)
        extracted_text = page.get_textbox(rect)
        return extracted_text.strip() if extracted_text else ""

    except ZeroDivisionError:
        logging.error(
            "Division by zero error during coordinate normalization in extract_text_from_area.")
        return ""
    except Exception as e:
        logging.error(
            f"Unexpected error extracting text from area {area}: {e}", exc_info=True)
        return ""



def safe_float_convert(text: Optional[str], default: Any = None) -> Union[float, None]:
    """
    Safely converts a string to a float, handling different locale conventions.
    
    Supports:
    - Spanish/European format: 1.234,56
    - US/Standard format: 1,234.56
    - Mixed multi-line OCR output (tries to find a valid number line by line).
    
    Args:
        text: The string to convert.
        default: Value to return if conversion fails.
        
    Returns:
        Converted float or the default value.
    """
    if text is None or text == '':
        return default

    # Handle multi-line text by splitting and processing each line
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return default

    for line in lines:
        try:
            # Basic cleaning
            cleaned = line.strip()
            
            # If both , and . exist (e.g. 1.234,56 or 1,234.56)
            if ',' in cleaned and '.' in cleaned:
                if cleaned.find('.') < cleaned.find(','): # 1.234,56
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else: # 1,234.56
                    cleaned = cleaned.replace(',', '')
            # If only comma exists (e.g. 1234,56)
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '.')
            # If only dot exists (e.g. 1.234 or 1234.56)
            elif '.' in cleaned:
                parts = cleaned.split('.')
                # If there's exactly one dot and it's not followed by exactly 3 digits (e.g. 75.5)
                # it's likely a decimal dot.
                if len(parts) == 2 and len(parts[1]) != 3:
                    pass # Keep the dot as decimal separator
                # If there are multiple dots OR one dot followed by 3 digits (e.g. 1.000 or 1.000.000)
                # verify that all parts after the first have length 3 (thousand separator pattern)
                elif all(len(p) == 3 for p in parts[1:]):
                    cleaned = cleaned.replace('.', '') # Treat as thousands separator
                else:
                    # Invalid or ambiguous dot usage
                    raise ValueError(f"Ambiguous or invalid numeric format: {cleaned}")

            return float(cleaned)
        except (ValueError, TypeError):
            continue

    logging.warning(f"Could not convert '{text}' to float.")
    return default



def _from_procentaje_ahorro_to_letra(porcentaje_ahorro_decimal: Optional[float]) -> Optional[str]:
    """
    Convert a savings percentage (as a float, e.g., 0.75 for 75%) to a corresponding letter grade.
    Handles None input gracefully.
    """
    if porcentaje_ahorro_decimal is None:
        return None
    boundaries = [-0.35, -0.1, 0.2, 0.4, 0.55, 0.7, 0.85, 100.0]
    grades = ['G', 'F', 'E', 'D', 'C', 'B', 'A', 'A+']

    try:
        idx = bisect_left(boundaries, porcentaje_ahorro_decimal)
        if 0 <= idx < len(grades):
            return grades[idx]
        else:
            logging.warning(
                f"Percentage {porcentaje_ahorro_decimal*100}% resulted in out-of-bounds grade index {idx}.")
            if idx >= len(grades):
                return grades[-1]
            else:
                return grades[0]

    except TypeError:
        logging.error(
            f"Invalid type for percentage: {porcentaje_ahorro_decimal}. Cannot determine grade.")
        return None



def get_informe_cev_v2_pagina1_as_dict(pdf_report: fitz.Document) -> Dict[str, Any]:
    """
    Extract data from page 1 of an informe_CEV_v2 PDF report and return it as a dictionary.
    Uses safe float conversion and get_page_coordinates for consistency.
    """
    result: Dict[str, Any] = {}
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")
        if len(pdf_report) < 1:
            raise ValueError("PDF has no pages.")
        page = pdf_report[0]

        # Usar get_page_coordinates para obtener las coordenadas
        COORDINATES = get_page_coordinates(0)

        fields: Dict[str, str] = {k: extract_text_from_area(
            page, v) for k, v in COORDINATES.items()}

        # Post-processing with safe conversion
        porcentaje_ahorro_str = next((line for line in fields.get(
            'porcentaje_ahorro_raw', '').splitlines() if line.replace('-', '').isdigit()), None)
        porcentaje_ahorro_int = int(
            porcentaje_ahorro_str) if porcentaje_ahorro_str is not None else None
        porcentaje_ahorro_decimal = float(
            porcentaje_ahorro_int / 100.0) if porcentaje_ahorro_int is not None else None

        demanda_cal_str = fields.get(
            'demanda_calefaccion_kwh_m2_ano_raw', '').splitlines()
        demanda_enf_str = fields.get(
            'demanda_enfriamiento_kwh_m2_ano_raw', '').splitlines()
        demanda_tot_str = fields.get(
            'demanda_total_kwh_m2_ano_raw', '').splitlines()
        emitida_str = fields.get('emitida_el_raw', '').splitlines()

        result = {
            'tipo_evaluacion': fields.get('tipo_evaluacion', '').strip(),
            'codigo_evaluacion': fields.get('codigo_evaluacion', '').strip(),
            'region': fields.get('region', '').strip(),
            'comuna': fields.get('comuna', '').strip(),
            'direccion': fields.get('direccion', '').strip(),
            'rol_vivienda_proyecto': fields.get('rol_vivienda_proyecto', '').strip(),
            'tipo_vivienda': fields.get('tipo_vivienda', '').strip(),
            'superficie_interior_util_m2': safe_float_convert(fields.get('superficie_interior_util_m2')),
            'porcentaje_ahorro': porcentaje_ahorro_int,
            'letra_eficiencia_energetica_dem': _from_procentaje_ahorro_to_letra(porcentaje_ahorro_decimal),
            'demanda_calefaccion_kwh_m2_ano': safe_float_convert(demanda_cal_str[-1] if demanda_cal_str else None),
            'demanda_enfriamiento_kwh_m2_ano': safe_float_convert(demanda_enf_str[-1] if demanda_enf_str else None),
            'demanda_total_kwh_m2_ano': safe_float_convert(demanda_tot_str[-1] if demanda_tot_str else None),
            'emitida_el': emitida_str[-1].strip() if emitida_str else None
        }
        return result

    except (IndexError, ValueError, TypeError) as e:
        logging.error(
            f"Error processing Page 1 dictionary: {e}", exc_info=True)
        return {}



def get_informe_cev_v2_pagina2_as_dict(pdf_report: fitz.Document) -> Dict[str, Any]:
    """
    Extract data from page 2 of an informe_CEV_v2 PDF report and return it as a dictionary.
    Uses safe float conversion and get_page_coordinates for consistency.
    """
    result: Dict[str, Any] = {}
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")
        if len(pdf_report) < 2:
            raise ValueError("PDF has less than 2 pages.")
        page = pdf_report[1]

        # Usar get_page_coordinates para obtener las coordenadas
        COORDINATES = get_page_coordinates(1)

        fields: Dict[str, str] = {k: extract_text_from_area(
            page, v) for k, v in COORDINATES.items()}

        # Helper lambdas for cleaner processing
        def get_last_line(key): return fields.get(
            key, '').splitlines()[-1].strip() if fields.get(key) else None

        def get_last_line_float(
            key): return safe_float_convert(get_last_line(key))

        def clean_desc(key): return fields.get(
            key, '').replace('\n', ' ').strip()

        def clean_exigencia_float(key: str) -> Optional[float]:
            """
            Convierte valores de exigencia técnica (rango 0-5, un dígito antes del decimal).
            Maneja tanto punto como coma decimal automáticamente.
            """
            try:
                raw_text = fields.get(key, '').replace('[W/m2K]', '').strip()
                if not raw_text:
                    return None

                # Simplemente reemplazar coma por punto y convertir
                # Como sabemos que son valores pequeños (0-5), no hay separadores de miles
                cleaned_text = raw_text.replace(',', '.')
                return float(cleaned_text)

            except (ValueError, TypeError):
                logging.warning(
                    f"Could not convert exigencia value '{raw_text}' to float for key '{key}'.")
                return None

        result = {
            'region': clean_desc('region'),
            'comuna': clean_desc('comuna'),
            'direccion': clean_desc('direccion'),
            'rol_vivienda': clean_desc('rol_vivienda'),
            'tipo_vivienda': clean_desc('tipo_vivienda'),
            'zona_termica': clean_desc('zona_termica'),
            'superficie_interior_util_m2': safe_float_convert(fields.get('superficie_interior_util_m2_raw')),
            'solicitado_por': clean_desc('solicitado_por'),
            'evaluado_por': clean_desc('evaluado_por'),
            'codigo_evaluacion': clean_desc('codigo_evaluacion'),
            'demanda_calefaccion_kwh_m2_ano': get_last_line_float('demanda_calefaccion_kwh_m2_ano_raw'),
            'demanda_enfriamiento_kwh_m2_ano': get_last_line_float('demanda_enfriamiento_kwh_m2_ano_raw'),
            'demanda_total_kwh_m2_ano': get_last_line_float('demanda_total_kwh_m2_ano_raw'),
            'demanda_total_bis_kwh_m2_ano': get_last_line_float('demanda_total_bis_kwh_m2_ano_raw'),
            'demanda_total_referencia_kwh_m2_ano': get_last_line_float('demanda_total_referencia_kwh_m2_ano_raw'),
            'porcentaje_ahorro': get_last_line_float('porcentaje_ahorro_raw'),
            'muro_principal_descripcion': clean_desc('muro_principal_descripcion'),
            'muro_principal_exigencia_w_m2_k': clean_exigencia_float('muro_principal_exigencia_raw'),
            'muro_secundario_descripcion': clean_desc('muro_secundario_descripcion'),
            'muro_secundario_exigencia_w_m2_k': clean_exigencia_float('muro_secundario_exigencia_raw'),
            'piso_principal_descripcion': clean_desc('piso_principal_descripcion'),
            'piso_principal_exigencia_w_m2_k': clean_exigencia_float('piso_principal_exigencia_raw'),
            'puerta_principal_descripcion': clean_desc('puerta_principal_descripcion'),
            'puerta_principal_exigencia_w_m2_k': clean_desc('puerta_principal_exigencia_raw'),
            'techo_principal_descripcion': clean_desc('techo_principal_descripcion'),
            'techo_principal_exigencia_w_m2_k': clean_exigencia_float('techo_principal_exigencia_raw'),
            'techo_secundario_descripcion': clean_desc('techo_secundario_descripcion'),
            'techo_secundario_exigencia_w_m2_k': clean_exigencia_float('techo_secundario_exigencia_raw'),
            'superficie_vidriada_principal_descripcion': clean_desc('superficie_vidriada_principal_descripcion'),
            'superficie_vidriada_principal_exigencia': clean_desc('superficie_vidriada_principal_exigencia'),
            'superficie_vidriada_secundaria_descripcion': clean_desc('superficie_vidriada_secundaria_descripcion'),
            'superficie_vidriada_secundaria_exigencia': clean_desc('superficie_vidriada_secundaria_exigencia'),
            'ventilacion_rah_descripcion': clean_desc('ventilacion_rah_descripcion'),
            'ventilacion_rah_exigencia': clean_desc('ventilacion_rah_exigencia'),
            'infiltraciones_rah_descripcion': clean_desc('infiltraciones_rah_descripcion'),
            'infiltraciones_rah_exigencia': clean_desc('infiltraciones_rah_exigencia')
        }
        return result

    except (IndexError, ValueError, TypeError) as e:
        logging.error(
            f"Error processing Page 2 dictionary: {e}", exc_info=True)
        return {}



def get_informe_cev_v2_pagina3_consumos_as_dict(pdf_report: fitz.Document) -> Dict[str, Any]:
    """
    Extract data from page 3 (consumos) of an informe_CEV_v2 PDF report and return it as a dictionary.
    Uses safe float conversion and get_page_coordinates for consistency.
    """
    result: Dict[str, Any] = {}
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")
        if len(pdf_report) < 3:
            raise ValueError("PDF has less than 3 pages.")
        page = pdf_report[2]

        # Usar get_page_coordinates para obtener las coordenadas
        COORDINATES = get_page_coordinates(2)

        fields: Dict[str, str] = {k: extract_text_from_area(
            page, v) for k, v in COORDINATES.items()}

        def get_float(key): return safe_float_convert(fields.get(key))

        def get_last_line_float(key): return safe_float_convert(
            fields.get(key, '').splitlines()[-1] if fields.get(key) else None)
        def clean_desc(key): return fields.get(
            key, '').replace('\n', ' ').strip()

        result = {
            'codigo_evaluacion': clean_desc('codigo_evaluacion'),
            'agua_caliente_sanitaria_kwh_m2': get_float('agua_caliente_sanitaria_kwh_m2_raw'),
            'agua_caliente_sanitaria_per': get_float('agua_caliente_sanitaria_per_raw'),
            'iluminacion_kwh_m2': get_float('iluminacion_kwh_m2_raw'),
            'iluminacion_per': get_float('iluminacion_per_raw'),
            'calefaccion_kwh_m2': get_float('calefaccion_kwh_m2_raw'),
            'calefaccion_kwh_per': get_float('calefaccion_kwh_per_raw'),
            'energia_renovable_no_convencional_kwh_m2': get_float('energia_renovable_no_convencional_kwh_m2_raw'),
            'energia_renovable_no_convencional_per': get_float('energia_renovable_no_convencional_per_raw'),
            'consumo_total_kwh_m2': get_float('consumo_total_kwh_m2_raw'),
            'emisiones_kgco2_m2_ano': get_float('emisiones_kgco2_m2_ano_raw'),
            'calefaccion_descripcion_proy': clean_desc('calefaccion_descripcion_proy'),
            'calefaccion_consumo_proy_kwh': get_last_line_float('calefaccion_consumo_proy_kwh_raw'),
            'calefaccion_consumo_proy_per': get_last_line_float('calefaccion_consumo_proy_per_raw'),
            'iluminacion_descripcion_proy': clean_desc('iluminacion_descripcion_proy'),
            'iluminacion_consumo_proy_kwh': get_last_line_float('iluminacion_consumo_proy_kwh_raw'),
            'iluminacion_consumo_proy_per': get_last_line_float('iluminacion_consumo_proy_per_raw'),
            'agua_caliente_sanitaria_descripcion_proy': clean_desc('agua_caliente_sanitaria_descripcion_proy'),
            'agua_caliente_sanitaria_consumo_proy_kwh': get_last_line_float('agua_caliente_sanitaria_consumo_proy_kwh_raw'),
            'agua_caliente_sanitaria_consumo_proy_per': get_last_line_float('agua_caliente_sanitaria_consumo_proy_per_raw'),
            'energia_renovable_no_convencional_descripcion_proy': clean_desc('energia_renovable_no_convencional_descripcion_proy'),
            'energia_renovable_no_convencional_consumo_proy_kwh': get_last_line_float('energia_renovable_no_convencional_consumo_proy_kwh_raw'),
            'energia_renovable_no_convencional_consumo_proy_per': get_last_line_float('energia_renovable_no_convencional_consumo_proy_per_raw'),
            'consumo_total_requerido_proy_kwh': get_last_line_float('consumo_total_requerido_proy_kwh_raw'),
            'calefaccion_descripcion_ref': clean_desc('calefaccion_descripcion_ref'),
            'calefaccion_consumo_ref_kwh': get_last_line_float('calefaccion_consumo_ref_kwh_raw'),
            'calefaccion_consumo_ref_per': get_last_line_float('calefaccion_consumo_ref_per_raw'),
            'iluminacion_descripcion_ref': clean_desc('iluminacion_descripcion_ref'),
            'iluminacion_consumo_ref_kwh': get_last_line_float('iluminacion_consumo_ref_kwh_raw'),
            'iluminacion_consumo_ref_per': get_last_line_float('iluminacion_consumo_ref_per_raw'),
            'agua_caliente_sanitaria_descripcion_ref': clean_desc('agua_caliente_sanitaria_descripcion_ref'),
            'agua_caliente_sanitaria_consumo_ref_kwh': get_last_line_float('agua_caliente_sanitaria_consumo_ref_kwh_raw'),
            'agua_caliente_sanitaria_consumo_ref_per': get_last_line_float('agua_caliente_sanitaria_consumo_ref_per_raw'),
            'energia_renovable_no_convencional_descripcion_ref': clean_desc('energia_renovable_no_convencional_descripcion_ref'),
            'energia_renovable_no_convencional_consumo_ref_kwh': get_last_line_float('energia_renovable_no_convencional_consumo_ref_kwh_raw'),
            'energia_renovable_no_convencional_consumo_ref_per': get_last_line_float('energia_renovable_no_convencional_consumo_ref_per_raw'),
            'consumo_total_requerido_ref_kwh': get_last_line_float('consumo_total_requerido_ref_kwh_raw'),
            # CONSUMOS SIN INCLUIR ERNC
            'consumo_ep_calefaccion_kwh': get_float('consumo_ep_calefaccion_kwh_raw'),
            'consumo_ep_agua_caliente_sanitaria_kwh': get_float('consumo_ep_agua_caliente_sanitaria_kwh_raw'),
            'consumo_ep_iluminacion_kwh': get_float('consumo_ep_iluminacion_kwh_raw'),
            'consumo_ep_ventiladores_kwh': get_float('consumo_ep_ventiladores_kwh_raw'),
            # GENERACIÓN FOTOVOLTAICA EN LA VIVIENDA
            'generacion_ep_fotovoltaicos_kwh': get_float('generacion_ep_fotovoltaicos_kwh_raw'),
            'aporte_fotovoltaicos_consumos_basicos_kwh': get_float('aporte_fotovoltaicos_consumos_basicos_kwh_raw'),
            'diferencia_fotovoltaica_para_consumo_kwh': get_float('diferencia_fotovoltaica_para_consumo_kwh_raw'),
            # DISTRIBUCIÓN DEL APORTE DE SOLAR TÉRMICA
            'aporte_solar_termica_calefaccion_kwh': get_float('aporte_solar_termica_calefaccion_kwh_raw'),
            'aporte_solar_termica_agua_caliente_sanitaria_kwh': get_float('aporte_solar_termica_agua_caliente_sanitaria_kwh_raw'),
            # BALANCE GENERAL DE ENERGÍA
            'total_consumo_ep_antes_fotovoltaica_kwh': get_float('total_consumo_ep_antes_fotovoltaica_kwh_raw'),
            'aporte_fotovoltaicos_consumos_basicos_kwh_bis': get_float('aporte_fotovoltaicos_consumos_basicos_kwh_bis_raw'),
            'consumos_basicos_a_suplir_kwh': get_float('consumos_basicos_a_suplir_kwh_raw'),
            # RESUMEN DE CONSUMOS FINALES DE REFERENCIA Y OBJETO
            'consumo_total_ep_obj_kwh': get_float('consumo_total_ep_obj_kwh_raw'),
            'consumo_total_ep_ref_kwh': get_float('consumo_total_ep_ref_kwh_raw'),
            'coeficiente_energetico_c': get_float('coeficiente_energetico_c_raw')
        }
        return result

    except (IndexError, ValueError, TypeError) as e:
        logging.error(
            f"Error processing Page 3 (Consumos) dictionary: {e}", exc_info=True)
        return {}



def get_informe_cev_v2_pagina3_envolvente_as_dict(pdf_report: fitz.Document) -> Dict[str, Any]:
    """
    Extracts envelope data from page 3 into a dictionary (10 orientation rows).

    Coordinate-block based (opacos area/U, traslucidos area/U, puentes P01-P05,
    UA+phiL). VERIFIED correct against the rendered table for all blocks (Fase 7,
    PDF Ancud). Intentionally NOT refactored: the multi-block row alignment
    (incl. the UA+phiL index handling) is delicate and currently exact; a rewrite
    would add risk without correctness gain. Page 5 (simpler) was refactored to a
    font-size approach; page 3 stays coordinate-based.
    """
    data_list: Dict[str, List[Any]] = {}
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")
        if len(pdf_report) < 3:
            raise ValueError("PDF has less than 3 pages.")
        page = pdf_report[2]

        dy = 4.2
        num_orientations = 10
        num_puentes_termicos = 8
        puente_termico_start_y = 250.0
        orientations = ['Horiz', 'N', 'NE', 'E',
                        'SE', 'S', 'SO', 'O', 'NO', 'Pisos']

        # Usar get_page_coordinates para obtener las coordenadas base
        COORDINATES = get_page_coordinates(2)

        # Extraer coordenadas específicas de envolvente
        COORDINATES_BLOCKS = {
            'codigo_eval_coords': COORDINATES.get('codigo_evaluacion', (62.3, 30.7, 88.1, 36.0)),
            'opacos_area_coords': COORDINATES.get('opacos_area_coords', (19.8, 245.6, 47.6, 287.3)),
            'opacos_u_coords': COORDINATES.get('opacos_u_coords', (48.7, 245.6, 60.8, 287.3)),
            'traslucidos_area_coords': COORDINATES.get('traslucidos_area_coords', (68.4, 245.6, 89.7, 283.0)),
            'traslucidos_u_coords': COORDINATES.get('traslucidos_u_coords', (90.8, 245.6, 103.1, 283.0)),
            'ua_phil_coords': COORDINATES.get('ua_phil_coords', (189.5, 245.6, 201.9, 287.3))
        }

        PT_COORDS_BASE: Dict[str, Tuple[float, float]] = {
            'p01_w_k': (115.5, 124.5), 'p02_w_k': (126.2, 136.9), 'p03_w_k': (139.0, 148.2),
            'p04_w_k': (149.0, 160.0), 'p05_w_k': (161.3, 171.2)
        }

        # --- Extract Single Value ---
        codigo_evaluacion = extract_text_from_area(
            page, COORDINATES_BLOCKS['codigo_eval_coords']).strip()

        # --- Extract Columnar Data Blocks ---
        opacos_area_text = extract_text_from_area(
            page, COORDINATES_BLOCKS['opacos_area_coords'])
        opacos_U_text = extract_text_from_area(
            page, COORDINATES_BLOCKS['opacos_u_coords'])
        traslucidos_area_text = extract_text_from_area(
            page, COORDINATES_BLOCKS['traslucidos_area_coords'])
        traslucidos_U_text = extract_text_from_area(
            page, COORDINATES_BLOCKS['traslucidos_u_coords'])

        # --- Extract Puente Termico Data ---
        puentes_termicos_text: Dict[str, List[str]] = {
            key: [] for key in PT_COORDS_BASE}
        for key, (x1, x2) in PT_COORDS_BASE.items():
            for i in range(num_puentes_termicos):
                y1 = puente_termico_start_y + i * dy
                y2 = y1 + 3.5
                pt_coord = (x1, y1, x2, y2)
                text_lines = extract_text_from_area(
                    page, pt_coord).splitlines()
                puentes_termicos_text[key].append(
                    text_lines[-1] if text_lines else '')

        # --- Extract UA_phiL usando extracción individual por fila ---
        ua_phiL_values = []
        dy_ua = 3.5  # dy específico para UA_phiL (diferente del dy general)
        for n in range(0, 12):
            area_coordinates = (189.2, 245.5 + n * dy_ua,
                                201.9, 249.0 + n * dy_ua)
            extracted_text = extract_text_from_area(page, area_coordinates)
            if extracted_text:
                ua_phiL_line = extracted_text.splitlines()[-1]
                try:
                    ua_phiL_value = float(ua_phiL_line.replace(',', '.'))
                    ua_phiL_values.append(ua_phiL_value)
                except (ValueError, TypeError):
                    ua_phiL_values.append(None)
            else:
                ua_phiL_values.append(None)

        # Eliminar elementos en posiciones 4 y 9
        if len(ua_phiL_values) > 4:
            ua_phiL_values.pop(4)  # Luego el menor
        if len(ua_phiL_values) > 9:
            ua_phiL_values.pop(9)  # Eliminar primero el índice mayor

        # Asegurar que tenemos exactamente 10 valores
        while len(ua_phiL_values) < num_orientations:
            ua_phiL_values.append(None)
        # Truncar si hay más de 10
        ua_phiL_values = ua_phiL_values[:num_orientations]

        # --- Process and Structure Data ---
        data_list['codigo_evaluacion'] = [codigo_evaluacion] * num_orientations
        data_list['orientacion'] = orientations

        opacos_area_lines = opacos_area_text.splitlines()[-num_orientations:]
        opacos_U_lines = opacos_U_text.splitlines()[-num_orientations:]
        data_list['elementos_opacos_area_m2'] = [
            safe_float_convert(line) for line in opacos_area_lines]
        data_list['elementos_opacos_u_w_m2_k'] = [
            safe_float_convert(line) for line in opacos_U_lines]

        traslucidos_area_lines = traslucidos_area_text.splitlines(
        )[-(num_orientations-1):]
        traslucidos_U_lines = traslucidos_U_text.splitlines(
        )[-(num_orientations-1):]
        data_list['elementos_traslucidos_area_m2'] = [
            safe_float_convert(line) for line in traslucidos_area_lines] + [None]
        data_list['elementos_traslucidos_u_w_m2_k'] = [
            safe_float_convert(line) for line in traslucidos_U_lines] + [None]

        for key, lines in puentes_termicos_text.items():
            float_values = [safe_float_convert(line) for line in lines]
            data_list[key] = [None] + float_values + \
                [None]  # Pad first and last

        data_list['ua_phil'] = ua_phiL_values

        # Validate list lengths
        for key, lst in data_list.items():
            if len(lst) != num_orientations:
                logging.warning(
                    f"Length mismatch for {key} (Envolvente): expected {num_orientations}, got {len(lst)}. Padding.")
                data_list[key].extend([None] * (num_orientations - len(lst)))

        return data_list

    except (IndexError, ValueError, TypeError) as e:
        logging.error(
            f"Error processing Page 3 (Envolvente) dictionary: {e}", exc_info=True)
        return {}



def get_informe_cev_v2_pagina4_as_dict(pdf_report: fitz.Document) -> Dict[str, Any]:
    """
    Extracts monthly data from page 4 into a dictionary (structured for DataFrame).
    Uses safe float conversion and get_page_coordinates for consistency.
    """
    data_list: Dict[str, List[Any]] = {}
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")
        if len(pdf_report) < 4:
            raise ValueError("PDF has less than 4 pages.")
        page = pdf_report[3]
        num_months = 12
        months = list(range(1, num_months + 1))

        # Usar get_page_coordinates para obtener las coordenadas
        COORDINATES = get_page_coordinates(3)

        codigo_evaluacion = extract_text_from_area(
            page, COORDINATES['codigo_evaluacion']).strip()
        data_list['codigo_evaluacion'] = [codigo_evaluacion] * num_months
        data_list['mes_id'] = months

        # Extraer datos mensuales usando las coordenadas generadas
        monthly_fields = [key for key in COORDINATES.keys()
                          if key.endswith('_mes_1')]
        base_fields = [key.replace('_mes_1', '') for key in monthly_fields]

        for base_field in base_fields:
            monthly_values = []
            for month in range(1, 13):
                field_key = f'{base_field}_mes_{month}'
                if field_key in COORDINATES:
                    text = extract_text_from_area(page, COORDINATES[field_key])
                    monthly_values.append(safe_float_convert(text))
                else:
                    monthly_values.append(None)
            data_list[base_field] = monthly_values

        # Validate list lengths
        for key, lst in data_list.items():
            if len(lst) != num_months:
                logging.warning(
                    f"Length mismatch for {key} (Page 4): expected {num_months}, got {len(lst)}. Padding.")
                data_list[key].extend([None] * (num_months - len(lst)))

        return data_list

    except (IndexError, ValueError, TypeError) as e:
        logging.error(
            f"Error processing Page 4 dictionary: {e}", exc_info=True)
        return {}



def get_informe_cev_v2_pagina5_as_dict(pdf_report: fitz.Document) -> Dict[str, Any]:
    """
    Extract page 5 (energy flows Q) using 20 INDIVIDUAL coordinate boxes
    (10 parameters x Enero/Julio). Robust to line-spacing changes; no swap hack.
    Returns the same {col: [enero, julio]} structure for two rows.
    """
    data_list: Dict[str, List[Any]] = {}
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")
        if len(pdf_report) < 5:
            raise ValueError("PDF has less than 5 pages.")

        page = pdf_report[4]
        COORDINATES = get_page_coordinates(4)
        if not COORDINATES:
            logging.warning("No coordinates defined for page 5")
            return {}

        codigo_evaluacion = extract_text_from_area(page, COORDINATES['codigo_evaluacion']).strip()

        # The table has, per cell, a DISPLAYED value (font size ~12) and a smaller
        # RAW value (~5.8) beneath it. We extract only the displayed (size-12) numeric
        # spans in the table region — robust to row-pitch changes (no fixed boxes,
        # no swap hack). Split into Enero (left, x<70mm) / Julio (right) by x, order by y.
        REPORT_W, REPORT_H = 215.9, 330.0
        pr = page.rect
        x_split_mm, y_lo, y_hi = 70.0, 187.0, 246.0
        num_re = re.compile(r'^-?\d+(?:,\d+)?$|^-$')

        enero, julio = [], []
        for blk in page.get_text("dict").get("blocks", []):
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    txt = span["text"].strip()
                    if not num_re.match(txt) or span["size"] < 9.0:  # displayed only
                        continue
                    mx = span["bbox"][0] / pr.width * REPORT_W
                    my = span["bbox"][1] / pr.height * REPORT_H
                    if not (y_lo < my < y_hi and 44 < mx < 95):
                        continue
                    val = 0.0 if txt == '-' else safe_float_convert(txt)
                    (enero if mx < x_split_mm else julio).append((my, val))

        enero = [v for _, v in sorted(enero)]
        julio = [v for _, v in sorted(julio)]
        # pad/truncate to 10
        enero = (enero + [None] * 10)[:10]
        julio = (julio + [None] * 10)[:10]

        params = ['q_recuperado', 'q_puentes_termicos', 'q_contra_terreno', 'q_piso_ventilado',
                  'q_ventanas', 'q_muros', 'q_techo', 'q_infiltraciones', 'q_ventilacion', 'q_sol']

        data_list['codigo_evaluacion'] = [codigo_evaluacion, codigo_evaluacion]
        data_list['mes'] = ['Enero', 'Julio']
        for i, p in enumerate(params):
            data_list[f'{p}_kwh'] = [enero[i], julio[i]]

        return data_list

    except Exception as e:
        logging.error(f"Error accessing Page 5 dictionary: {e}", exc_info=True)
        return {}



def get_informe_cev_v2_pagina7_as_dict(pdf_report: fitz.Document) -> Dict[str, Any]:
    """
    Extract data from page 7 of an informe_CEV_v2 PDF report and return it as a dictionary.

    Args:
        pdf_report (fitz.Document): The PyMuPDF document object.

    Returns:
        Dict[str, Any]: A dictionary containing field names as keys and extracted text/data as values.
    """
    result: Dict[str, Any] = {}
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")
        if len(pdf_report) < 7:
            raise ValueError("PDF has less than 7 pages.")

        page = pdf_report[6]

        # Usar get_page_coordinates para obtener las coordenadas
        COORDINATES = get_page_coordinates(6)

        fields: Dict[str, str] = {k: extract_text_from_area(
            page, v) for k, v in COORDINATES.items()}

        result = {
            'codigo_evaluacion': fields.get('codigo_evaluacion', '').strip(),
            'mandante_nombre': fields.get('mandante_nombre', '').strip(),
            'mandante_rut': fields.get('mandante_rut', '').strip(),
            'evaluador_nombre': fields.get('evaluador_nombre', '').strip(),
            'evaluador_rut': fields.get('evaluador_rut', '').strip(),
            'evaluador_rol_minvu': fields.get('evaluador_rol_minvu', '').strip()
        }
        return result

    except (IndexError, ValueError, TypeError) as e:
        logging.error(
            f"Error processing Page 7 dictionary: {e}", exc_info=True)
        return {}


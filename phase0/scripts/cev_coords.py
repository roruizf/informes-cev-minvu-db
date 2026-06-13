# Ported verbatim from Informe-CEV-v2-pdf-scraper/scraping_functions.py for Phase 0 Test A

import logging
from functools import lru_cache
from typing import Dict, Tuple
import fitz


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



def get_page_coordinates(page_num: int) -> Dict[str, Tuple[float, float, float, float]]:
    """
    Get coordinates for each page based on the page number.

    Args:
        page_num: Page number (0-indexed)

    Returns:
        Dictionary with coordinates for the specified page
    """

    # Página 1 (índice 0)
    if page_num == 0:
        return {
            'tipo_evaluacion': (8.3, 9.0, 165.6, 18.8),
            'codigo_evaluacion': (73.1, 20.0, 97.1, 25.1),
            'region': (28.0, 26.6, 165.3, 31.8),
            'comuna': (29.2, 33.0, 165.3, 38.2),
            'direccion': (31.3, 39.1, 165.3, 44.3),
            'rol_vivienda_proyecto': (55.5, 45.6, 165.3, 50.8),
            'tipo_vivienda': (45.9, 51.7, 165.3, 56.9),
            'superficie_interior_util_m2': (53.0, 58.3, 70.0, 63.5),
            'porcentaje_ahorro_raw': (5.6, 78.6, 165.8, 191.3),
            'demanda_calefaccion_kwh_m2_ano_raw': (15.6, 220.0, 73.0, 230.0),
            'demanda_enfriamiento_kwh_m2_ano_raw': (90.0, 220.0, 151.5, 230.0),
            'demanda_total_kwh_m2_ano_raw': (167.0, 225.0, 209.0, 245.0),
            'emitida_el_raw': (34.5, 247.0, 57.5, 252.8)
        }

    # Página 2 (índice 1)
    elif page_num == 1:
        return {
            'region': (40.4, 47.4, 95.0, 51.7),
            'comuna': (40.4, 53.2, 95.0, 57.4),
            'direccion': (40.4, 58.9, 95.0, 63.1),
            'rol_vivienda': (40.4, 64.6, 95.0, 68.9),
            'tipo_vivienda': (40.4, 70.2, 95.0, 74.4),
            'zona_termica': (143.1, 47.5, 151.0, 51.7),
            'superficie_interior_util_m2_raw': (143.1, 53.3, 151.0, 57.5),
            'solicitado_por': (143.1, 58.9, 210.5, 63.1),
            'evaluado_por': (143.1, 64.7, 210.5, 68.9),
            'codigo_evaluacion': (143.1, 70.2, 163.0, 74.5),
            'demanda_calefaccion_kwh_m2_ano_raw': (98.7, 98.7, 109.5, 105.2),
            'demanda_enfriamiento_kwh_m2_ano_raw': (98.7, 120.9, 109.5, 126.5),
            'demanda_total_kwh_m2_ano_raw': (98.6, 137.0, 136.0, 149.5),
            'demanda_total_bis_kwh_m2_ano_raw': (39.2, 159.8, 122.8, 166.0),
            'demanda_total_referencia_kwh_m2_ano_raw': (16.9, 168.3, 146.2, 173.2),
            'porcentaje_ahorro_raw': (151.0, 162.6, 201.5, 168.7),
            'muro_principal_descripcion': (46.2, 202.5, 184.5, 209.2),
            'muro_principal_exigencia_raw': (185.5, 202.5, 209.5, 209.2),
            'muro_secundario_descripcion': (46.2, 209.5, 184.5, 216.2),
            'muro_secundario_exigencia_raw': (185.5, 209.5, 209.5, 216.2),
            'piso_principal_descripcion': (46.2, 216.5, 184.5, 223.2),
            'piso_principal_exigencia_raw': (185.5, 216.5, 209.5, 223.2),
            'puerta_principal_descripcion': (46.2, 223.5, 184.5, 230.2),
            'puerta_principal_exigencia_raw': (185.5, 223.5, 209.5, 230.2),
            'techo_principal_descripcion': (46.2, 230.5, 184.5, 237.0),
            'techo_principal_exigencia_raw': (185.5, 230.5, 209.5, 237.0),
            'techo_secundario_descripcion': (46.2, 237.6, 184.5, 244.1),
            'techo_secundario_exigencia_raw': (185.5, 237.6, 209.5, 244.1),
            'superficie_vidriada_principal_descripcion': (46.2, 244.6, 184.5, 251.2),
            'superficie_vidriada_principal_exigencia': (185.5, 244.6, 209.5, 251.2),
            'superficie_vidriada_secundaria_descripcion': (46.2, 251.6, 184.5, 258.2),
            'superficie_vidriada_secundaria_exigencia': (185.5, 251.6, 209.5, 258.2),
            'ventilacion_rah_descripcion': (46.2, 258.6, 184.5, 265.2),
            'ventilacion_rah_exigencia': (185.5, 258.6, 209.5, 265.2),
            'infiltraciones_rah_descripcion': (46.2, 265.6, 184.5, 272.2),
            'infiltraciones_rah_exigencia': (185.5, 265.6, 209.5, 272.2)
        }

    # Página 3 (índice 2) - Consumos
    elif page_num == 2:
        return {
            'codigo_evaluacion': (62.3, 30.7, 88.1, 36.0),
            'agua_caliente_sanitaria_kwh_m2_raw': (79.2, 73.4, 98.3, 77.0),
            'agua_caliente_sanitaria_per_raw': (99.4, 73.4, 117.3, 77.0),
            'iluminacion_kwh_m2_raw': (79.2, 77.7, 98.3, 81.9),
            'iluminacion_per_raw': (98.7, 77.7, 117.3, 81.9),
            'calefaccion_kwh_m2_raw': (79.2, 82.3, 98.3, 86.5),
            'calefaccion_kwh_per_raw': (98.7, 82.3, 117.3, 86.5),
            'energia_renovable_no_convencional_kwh_m2_raw': (79.2, 87.0, 98.3, 91.2),
            'energia_renovable_no_convencional_per_raw': (98.7, 87.0, 117.3, 91.2),
            'consumo_total_kwh_m2_raw': (118.0, 74.0, 149.3, 86.0),
            'emisiones_kgco2_m2_ano_raw': (171.5, 69.0, 184.3, 74.2),
            'calefaccion_descripcion_proy': (76.6, 101.4, 155.5, 105.3),
            'calefaccion_consumo_proy_kwh_raw': (157.0, 101.4, 196.0, 105.3),
            'calefaccion_consumo_proy_per_raw': (198.0, 101.4, 209.0, 105.3),
            'iluminacion_descripcion_proy': (76.6, 106.2, 155.5, 110.0),
            'iluminacion_consumo_proy_kwh_raw': (157.0, 106.2, 196.0, 110.0),
            'iluminacion_consumo_proy_per_raw': (198.0, 106.2, 209.0, 110.0),
            'agua_caliente_sanitaria_descripcion_proy': (76.6, 111.2, 155.5, 115.0),
            'agua_caliente_sanitaria_consumo_proy_kwh_raw': (157.0, 111.2, 196.0, 115.0),
            'agua_caliente_sanitaria_consumo_proy_per_raw': (198.0, 111.2, 209.0, 115.0),
            'energia_renovable_no_convencional_descripcion_proy': (76.6, 115.8, 155.5, 120.0),
            'energia_renovable_no_convencional_consumo_proy_kwh_raw': (157.0, 115.8, 196.0, 120.0),
            'energia_renovable_no_convencional_consumo_proy_per_raw': (198.0, 115.8, 209.0, 120.0),
            'consumo_total_requerido_proy_kwh_raw': (157.0, 121.0, 196.0, 125.0),
            'calefaccion_descripcion_ref': (76.6, 136.1, 155.5, 140.1),
            'calefaccion_consumo_ref_kwh_raw': (157.0, 136.1, 196.0, 140.1),
            'calefaccion_consumo_ref_per_raw': (198.0, 136.1, 209.0, 140.1),
            'iluminacion_descripcion_ref': (76.6, 140.7, 155.5, 144.7),
            'iluminacion_consumo_ref_kwh_raw': (157.0, 140.7, 196.0, 144.7),
            'iluminacion_consumo_ref_per_raw': (198.0, 140.7, 209.0, 144.7),
            'agua_caliente_sanitaria_descripcion_ref': (76.6, 145.5, 155.5, 149.9),
            'agua_caliente_sanitaria_consumo_ref_kwh_raw': (157.0, 145.5, 196.0, 149.9),
            'agua_caliente_sanitaria_consumo_ref_per_raw': (198.0, 145.5, 209.0, 149.9),
            'energia_renovable_no_convencional_descripcion_ref': (76.6, 150.3, 155.5, 155.1),
            'energia_renovable_no_convencional_consumo_ref_kwh_raw': (157.0, 150.3, 196.0, 155.1),
            'energia_renovable_no_convencional_consumo_ref_per_raw': (198.0, 150.3, 209.0, 155.1),
            'consumo_total_requerido_ref_kwh_raw': (157.0, 155.5, 196.0, 161.0),
            # CONSUMOS SIN INCLUIR ERNC
            'consumo_ep_calefaccion_kwh_raw': (87.0, 176.0, 104.0, 179.5),
            'consumo_ep_agua_caliente_sanitaria_kwh_raw': (87.0, 180.0, 104.0, 183.5),
            'consumo_ep_iluminacion_kwh_raw': (87.0, 184.0, 104.0, 187.5),
            'consumo_ep_ventiladores_kwh_raw': (87.0, 188.0, 104.0, 191.5),
            # GENERACIÓN FOTOVOLTAICA EN LA VIVIENDA
            'generacion_ep_fotovoltaicos_kwh_raw': (87.0, 199.0, 104.0, 202.3),
            'aporte_fotovoltaicos_consumos_basicos_kwh_raw': (87.0, 202.8, 104.0, 206.4),
            'diferencia_fotovoltaica_para_consumo_kwh_raw': (87.0, 206.9, 104.0, 210.2),
            # DISTRIBUCIÓN DEL APORTE DE SOLAR TÉRMICA
            'aporte_solar_termica_calefaccion_kwh_raw': (87.0, 218.5, 104.0, 222.0),
            'aporte_solar_termica_agua_caliente_sanitaria_kwh_raw': (87.0, 222.5, 104.0, 225.8),
            # BALANCE GENERAL DE ENERGÍA
            'total_consumo_ep_antes_fotovoltaica_kwh_raw': (192.0, 176.0, 208.0, 179.5),
            'aporte_fotovoltaicos_consumos_basicos_kwh_bis_raw': (192.0, 180.0, 208.0, 183.5),
            'consumos_basicos_a_suplir_kwh_raw': (192.0, 183.9, 208.0, 187.3),
            # RESUMEN DE CONSUMOS FINALES DE REFERENCIA Y OBJETO
            'consumo_total_ep_obj_kwh_raw': (192.0, 199.0, 208.0, 202.5),
            'consumo_total_ep_ref_kwh_raw': (192.0, 202.8, 208.0, 206.5),
            'coeficiente_energetico_c_raw': (192.0, 207.0, 208.0, 210.5),
            # Coordenadas de envolvente también están en página 3
            'opacos_area_coords': (19.8, 245.6, 47.6, 287.3),
            'opacos_u_coords': (48.7, 245.6, 60.8, 287.3),
            'traslucidos_area_coords': (68.4, 245.6, 89.7, 283.0),
            'traslucidos_u_coords': (90.8, 245.6, 103.1, 283.0),
            'puentes_termicos_coords': (115.2, 249.8, 171.8, 283.1),
            'ua_phil_coords': (189.5, 245.6, 201.9, 287.3)
        }

    # Página 4 (índice 3) - Datos mensuales
    elif page_num == 3:
        coordinates = {'codigo_evaluacion': (62.3, 30.7, 88.1, 36.0)}

        # Coordenadas mensuales (12 columnas)
        dx = 13.5
        base_x = 42.0
        col_width = 12.0
        Y_COORDS = {
            'demanda_calef_viv_eval_kwh': (139.5, 143.5),
            'demanda_calef_viv_ref_kwh': (144.0, 148.0),
            'demanda_enfri_viv_eval_kwh': (161.4, 165.5),
            'demanda_enfri_viv_ref_kwh': (166.0, 170.2),
            'sobrecalentamiento_viv_eval_hr': (254.8, 258.8),
            'sobrecalentamiento_viv_ref_hr': (259.5, 263.4),
            'sobreenfriamiento_viv_eval_hr': (274.8, 278.8),
            'sobreenfriamiento_viv_ref_hr': (279.2, 283.3)
        }

        for key, (y1, y2) in Y_COORDS.items():
            for i in range(12):  # 12 meses
                x1 = base_x + i * dx
                x2 = x1 + col_width
                coordinates[f'{key}_mes_{i+1}'] = (x1, y1, x2, y2)

        return coordinates

    elif page_num == 4:
        coordinates = {
            'codigo_evaluacion': (62.3, 30.7, 88.1, 36.0),
            # Coordenadas para columna completa de Enero (ajustar según PDF real)
            # x1, y1, x2, y2 - columna completa
            'columna_enero': (46.5, 189.7, 62.0, 243.2),
            # Coordenadas para columna completa de Julio (ajustar según PDF real)
            # x1, y1, x2, y2 - columna completa
            'columna_julio': (76.5, 189.7, 92.0, 243.2)
        }
        return coordinates

    # Página 6 (índice 5)
    elif page_num == 5:
        return {
            'codigo_evaluacion': (62.3, 30.7, 88.1, 36.0),
            'enero': (64.5, 97.7, 173.2, 103.1),
            'abril': (64.6, 152.5, 173.8, 157.8),
            'julio': (66.4, 211.8, 174.0, 217.5),
            'octubre': (65.8, 271.0, 174.5, 276.4),
        }

    # Página 7 (índice 6)
    elif page_num == 6:
        return {
            'codigo_evaluacion': (62.3, 30.7, 88.1, 36.0),
            'mandante_nombre': (27.5, 90.6, 96.0, 94.5),
            'mandante_rut': (27.5, 95.2, 96.0, 99.0),
            'evaluador_nombre': (131.1, 90.6, 209.3, 94.5),
            'evaluador_rut': (131.1, 95.2, 209.3, 99.0),
            'evaluador_rol_minvu': (150.0, 99.9, 171.0, 103.7)
        }

    else:
        return {}



def draw_extraction_rectangles(pdf_report: fitz.Document, page_num: int, coordinates: Dict[str, Tuple[float, float, float, float]] = None, output_path: str = None) -> fitz.Document:
    """
    Draw rectangles on a specific page of the PDF to visualize the extraction areas.
    Uses normalized coordinates to match the scale used in extract_text_from_area.

    Args:
        pdf_report: fitz.Document object
        page_num: Page number (0-indexed)
        coordinates: Dictionary with field names and their coordinates. If None, uses get_page_coordinates()
        output_path: Optional path to save the modified PDF

    Returns:
        fitz.Document: The modified document with rectangles drawn
    """
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")
        if len(pdf_report) <= page_num:
            raise ValueError(f"PDF has less than {page_num + 1} pages.")

        # Usar get_page_coordinates si no se proporcionan coordenadas
        if coordinates is None:
            coordinates = get_page_coordinates(page_num)

        if not coordinates:
            logging.warning(f"No coordinates found for page {page_num + 1}")
            return pdf_report

        # Constantes de normalización
        REPORT_WIDTH = 215.9  # mm
        REPORT_HEIGHT = 330.0  # mm

        # Color único para todo el informe (azul por defecto)
        DEFAULT_COLOR = (0, 0, 1)

        # Obtener la página especificada
        page = pdf_report[page_num]

        # Obtener dimensiones de la página
        page_rect = page.rect
        if page_rect is None:
            raise ValueError("Could not get page rectangle.")

        page_width = page_rect.width
        page_height = page_rect.height

        if page_width <= 0 or page_height <= 0:
            raise ValueError(
                f"Invalid page dimensions: width={page_width}, height={page_height}")

        # Dibujar rectángulos para cada coordenada
        rectangles_drawn = 0
        for field_name, coords in coordinates.items():
            try:
                x1, y1, x2, y2 = coords

                # Validar coordenadas originales
                if not all(isinstance(coord, (int, float)) for coord in coords):
                    logging.warning(
                        f"Invalid coordinates for {field_name}: {coords}")
                    continue

                if x1 >= x2 or y1 >= y2:
                    logging.warning(
                        f"Invalid rectangle for {field_name}: {coords}")
                    continue

                # Normalizar coordenadas
                rx1, ry1 = normalize_coordinates(
                    x1, y1, REPORT_WIDTH, REPORT_HEIGHT, page_width, page_height)
                rx2, ry2 = normalize_coordinates(
                    x2, y2, REPORT_WIDTH, REPORT_HEIGHT, page_width, page_height)

                # Verificar coordenadas normalizadas
                if rx1 >= rx2 or ry1 >= ry2:
                    logging.warning(
                        f"Normalized coordinates invalid for {field_name}: ({rx1}, {ry1}, {rx2}, {ry2}) from original {coords}")
                    continue

                # Crear rectángulo normalizado
                rect = fitz.Rect(rx1, ry1, rx2, ry2)

                # Dibujar rectángulo con línea fina (0.75) y color único
                page.draw_rect(rect, color=DEFAULT_COLOR, width=0.75)
                rectangles_drawn += 1

            except Exception as e:
                logging.error(f"Error drawing rectangle for {field_name}: {e}")
                continue

        logging.info(f"Page {page_num + 1}: Successfully drew {rectangles_drawn} rectangles out of {len(coordinates)} defined coordinates.")

        # Guardar si se especifica una ruta
        if output_path:
            pdf_report.save(output_path)
            logging.info(f"PDF con rectángulos guardado en: {output_path}")

        return pdf_report

    except Exception as e:
        logging.error(f"Error drawing rectangles on page {page_num + 1}: {e}")
        logging.error(f"Error drawing rectangles on page {page_num + 1}: {e}")
        return pdf_report



def draw_all_pages_rectangles(pdf_report: fitz.Document, output_path: str = None) -> fitz.Document:
    """
    Draw rectangles on all pages of the PDF report using coordinates defined by get_page_coordinates().

    Args:
        pdf_report: fitz.Document object
        output_path: Optional path to save the modified PDF

    Returns:
        fitz.Document: The modified document with rectangles drawn on all pages
    """
    try:
        if not isinstance(pdf_report, fitz.Document):
            raise TypeError("Input must be a fitz.Document object.")

        total_rectangles = 0

        # Procesar cada página
        for page_num in range(min(7, len(pdf_report))):  # Máximo 7 páginas
            coordinates = get_page_coordinates(page_num)

            if coordinates:
                draw_extraction_rectangles(pdf_report, page_num, coordinates)
                total_rectangles += len(coordinates)
            else:
                logging.warning(f"No coordinates defined for page {page_num + 1}")

        logging.info(f"Total rectangles drawn across all pages: {total_rectangles}")

        # Guardar si se especifica una ruta
        if output_path:
            pdf_report.save(output_path)
            logging.info(f"PDF completo con rectángulos guardado en: {output_path}")

        return pdf_report

    except Exception as e:
        logging.error(f"Error drawing rectangles on all pages: {e}")
        logging.error(f"Error drawing rectangles on all pages: {e}")
        return pdf_report


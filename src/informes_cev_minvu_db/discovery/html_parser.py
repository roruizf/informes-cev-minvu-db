"""Parse the MINVU portal HTML: comuna dropdown, result count, and grid rows.

XPaths adapted from cev-data-lake/utils/html_functs.py, verified live in Phase 3.
Two grids: grdViviendasPre (tipo 1) / grdViviendasCal (tipo 2).
"""
import html as _html
import math
import re
import uuid

from lxml import html as LH

RESULTS_PER_PAGE = 10


def parse_comunas(page_html: str) -> list[tuple[int, str]]:
    m = re.search(r"(dbComuna.*?</select>)", page_html, re.S)
    if not m:
        return []
    opts = re.findall(r'<option[^>]*value="(-?\d+)"[^>]*>([^<]+)</option>', m.group(1))
    return [(int(v), _html.unescape(t.strip())) for v, t in opts if v != "-1"]


def parse_total_count(page_html: str, tipo: int) -> int:
    sid = "ContentPlaceHolder1_ResultadoGrillaCal" if tipo == 2 else "ContentPlaceHolder1_ResultadoGrillaPre"
    doc = LH.fromstring(page_html)
    txt = " ".join(t.strip() for t in doc.xpath(f'//span[@id="{sid}"]//text()') if t.strip())
    m = re.search(r"([\d.]+)\s+Vivienda", txt)
    return int(m.group(1).replace(".", "")) if m else 0


def total_pages(count: int) -> int:
    return max(1, math.ceil(count / RESULTS_PER_PAGE)) if count else 0


def eval_id(comuna_id: int, region_id: int, tipo: int, identificacion: str) -> str:
    """Deterministic eval_id. Order is comuna_region_tipo (datacev convention)."""
    s = f"{comuna_id}_{region_id}_{tipo}_{identificacion}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, s))


def parse_rows(page_html: str, region_id: int, comuna_id: int, tipo: int) -> list[dict]:
    """Extract evaluation rows from the result grid for the given tipo."""
    grid = "ContentPlaceHolder1_grdViviendasCal" if tipo == 2 else "ContentPlaceHolder1_grdViviendasPre"
    doc = LH.fromstring(page_html)
    base = f'//table[@id="{grid}"]/tbody/tr'

    def col(n):
        return doc.xpath(f'{base}/td[not(@class) and not(@style)][{n}]/text()')

    ident = [t.strip() for t in col(1)]
    tipologia = [t.strip() for t in col(2)]
    comuna = [t.strip() for t in col(3)]
    proyecto = [t.strip() for t in col(4)]

    def letras(offset_from_last):
        srcs = doc.xpath(f'{base}/td[position() = (last()-{offset_from_last})]/div/img/@src')
        out = []
        for s in srcs:
            if "Letra" in s:
                v = s.split("Letra")[1].split(".png")[0]
                out.append(None if v == "--" else v)
        return out

    ce = letras(2)
    cee = letras(1)
    cod_informe = doc.xpath(f'{base}/td[position()=last()]/div/div[@class="BtVerEtiqueta"]/div/input/@name')
    cod_etiqueta = doc.xpath(f'{base}/td[position()=last()]/div/div[@class="BtVerMapa"]/div/input/@name')

    rows = []
    for i, idv in enumerate(ident):
        if not idv:
            continue
        rows.append({
            "eval_id": eval_id(comuna_id, region_id, tipo, idv),
            "comuna_id": comuna_id,
            "tipo_evaluacion_id": tipo,
            "identificacion_vivienda": idv,
            "tipologia": tipologia[i] if i < len(tipologia) else None,
            "proyecto": proyecto[i] if i < len(proyecto) else None,
            "calificacion_energetica_letra": ce[i] if i < len(ce) else None,
            "calificacion_equipos_letra": cee[i] if i < len(cee) else None,
            "codigo_informe": cod_informe[i] if i < len(cod_informe) else None,
            "codigo_etiqueta": cod_etiqueta[i] if i < len(cod_etiqueta) else None,
        })
    return rows

"""PDF acquisition from the MINVU portal.

Layer-1: the saved viewstate caducates, so we do a fresh load→select_region→search
to obtain a valid viewstate, then the codigo_informe postback returns the PDF.
Drive reuse is intentionally NOT here (separate future task).
"""
import logging
from pathlib import Path

from informes_cev_minvu_db.discovery.portal_client import PortalClient

logger = logging.getLogger(__name__)


def download_from_minvu(eval_row, dest: Path, region_id: int, comuna_id: int,
                        tipo: int) -> bool:
    """Download a report PDF from the portal via the codigo_informe postback.

    eval_row.codigo_informe is the input control name; the postback returns the PDF.
    A fresh viewstate is obtained each call (the stored one expires).
    """
    if not eval_row.codigo_informe:
        return False
    client = PortalClient()
    try:
        client.load()
        client.select_region(region_id)
        client.search(region_id, comuna_id, tipo)
        target = eval_row.codigo_informe
        f = {**client._base_fields(), "__EVENTTARGET": target, "__VIEWSTATE": client._vs,
             "ctl00$ContentPlaceHolder1$dbRegion": str(region_id),
             "ctl00$ContentPlaceHolder1$dbComuna": str(comuna_id),
             "ctl00$ContentPlaceHolder1$dbCertificacion": str(tipo),
             f"{target}.x": "7", f"{target}.y": "7"}
        r = client._client.post(client.url, data=f)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf"):
            dest.write_bytes(r.content)
            return dest.stat().st_size > 1000
        return False
    except Exception as e:  # noqa: BLE001
        logger.warning("minvu download failed: %s", e)
        return False
    finally:
        client.close()

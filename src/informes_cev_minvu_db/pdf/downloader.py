"""PDF acquisition: MINVU portal download + Google Drive (gws) reuse.

Hybrid strategy (Phase-4): prefer reusing a PDF already on Drive; fall back to
downloading from the MINVU portal. Drive reconciliation is by codigo_evaluacion
(Phase-0 finding: the Drive filename UUID is NOT the eval_id).
"""
import json
import logging
import subprocess
from pathlib import Path

from informes_cev_minvu_db.config import settings
from informes_cev_minvu_db.discovery.portal_client import PortalClient, TOOLKIT

logger = logging.getLogger(__name__)
GWS = "/home/linuxbrew/.linuxbrew/bin/gws"


def download_from_minvu(eval_row, dest: Path, region_id: int, comuna_id: int,
                        tipo: int, viewstate: str) -> bool:
    """Download a report PDF from the portal via the codigo_informe postback.

    eval_row.codigo_informe is the input control name; the postback returns the PDF.
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


def _gws_json(args, timeout=120):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {}


def find_on_drive(codigo_evaluacion: str, region_id: int) -> str | None:
    """Locate a PDF on Drive whose filename matches the eval. Returns fileId or None.

    Drive layout: pdf_files/{region}/{region}_{comuna}_{tipo}_{uuid}.pdf — filename
    does not embed codigo_evaluacion, so matching is best-effort by region folder.
    Full reconciliation (open PDF, read codigo) is done by the pipeline if needed.
    """
    # Placeholder: real reconciliation resolves the region folder id then lists.
    # Kept minimal here; the pipeline currently supports local/MINVU paths.
    return None


def download_from_drive(file_id: str, dest: Path) -> bool:
    try:
        subprocess.run([GWS, "drive", "files", "get", "--params",
                        json.dumps({"fileId": file_id, "alt": "media"}),
                        "--output", str(dest)], capture_output=True, text=True, timeout=240)
        return dest.exists() and dest.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        logger.warning("drive download failed: %s", e)
        return False

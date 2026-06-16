"""PDF acquisition from the MINVU portal.

The btnInforme2 postback returns the PDF in the response BODY (starts with %PDF,
Content-Disposition: attachment) BUT the server mislabels Content-Type as
text/html and appends an HTML error fragment after the PDF. So we detect the PDF
by its magic bytes and trim everything after the last %%EOF — NOT by content-type.

Some informes legitimately fail portal-side (verified manually: the browser shows
{readyState:0,status:0,...} for certain reports); for those the body has no %PDF
and we return False (an expected failure → caller marks 'failed' + retry).

A fresh viewstate is obtained each call (the stored one expires).
"""
import logging
from pathlib import Path

from informes_cev_minvu_db.discovery.portal_client import PortalClient

logger = logging.getLogger(__name__)


def _extract_pdf(raw: bytes) -> bytes | None:
    """Return the PDF bytes from a response body, or None if there is no PDF.

    Trims any leading/trailing non-PDF bytes: keep from the first %PDF to the
    last %%EOF (inclusive). The MINVU response appends HTML after %%EOF.
    """
    start = raw.find(b"%PDF")
    if start < 0:
        return None
    eof = raw.rfind(b"%%EOF")
    if eof > start:
        return raw[start:eof + 5]
    return raw[start:]  # no EOF marker found; best effort


def download_from_minvu(eval_row, dest: Path, region_id: int, comuna_id: int,
                        tipo: int) -> bool:
    """Download a report PDF from the portal via the codigo_informe postback.

    eval_row.codigo_informe is the input control name; the postback returns the PDF
    (mislabeled as text/html). Returns True if a valid PDF was saved.
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
        if r.status_code != 200:
            logger.warning("minvu download: HTTP %s", r.status_code)
            return False
        pdf = _extract_pdf(r.content)
        if pdf is None:
            # Portal returned no PDF (expected for some informes) → caller retries.
            logger.info("minvu download: no PDF in response (portal-side failure)")
            return False
        dest.write_bytes(pdf)
        return dest.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        logger.warning("minvu download failed: %s", e)
        return False
    finally:
        client.close()

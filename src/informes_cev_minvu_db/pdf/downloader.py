"""PDF acquisition from the MINVU portal.

The btnInforme2 postback returns the PDF in the response BODY (starts with %PDF,
Content-Disposition: attachment) BUT the server mislabels Content-Type as
text/html and appends an HTML error fragment after the PDF. So we detect the PDF
by its magic bytes and trim everything after the last %%EOF — NOT by content-type.

Some informes legitimately fail portal-side (verified manually: the browser shows
{readyState:0,status:0,...} for certain reports); for those the body has no %PDF
and we return False (an expected failure → caller marks 'failed' + retry).

By default a fresh PortalClient (load → select_region → search) is built per call,
since process_pending drains in RANDOM order and consecutive downloads rarely share
a comuna. For comuna-grouped drains, pass a pre-warmed `client` (already loaded +
searched on the same region/comuna/tipo) to reuse its VIEWSTATE: one search serves
many downloads (see download_comuna_pdfs).
"""
import logging
from pathlib import Path

from informes_cev_minvu_db.discovery.portal_client import PortalClient

logger = logging.getLogger(__name__)


def _post_informe(client: PortalClient, target: str, region_id: int,
                  comuna_id: int, tipo: int, dest: Path) -> bool:
    """Issue the btnInforme2 postback on an already-searched client; save the PDF."""
    f = {**client._base_fields(), "__EVENTTARGET": target, "__VIEWSTATE": client._vs,
         "ctl00$ContentPlaceHolder1$dbRegion": str(region_id),
         "ctl00$ContentPlaceHolder1$dbComuna": str(comuna_id),
         "ctl00$ContentPlaceHolder1$dbCertificacion": str(tipo),
         f"{target}.x": "7", f"{target}.y": "7"}
    r = client._request("POST", data=f)
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
                        tipo: int, client: PortalClient | None = None) -> bool:
    """Download a report PDF from the portal via the codigo_informe postback.

    eval_row.codigo_informe is the input control name; the postback returns the PDF
    (mislabeled as text/html). Returns True if a valid PDF was saved.

    client: optional pre-warmed PortalClient already searched on this
        (region, comuna, tipo). When given, its VIEWSTATE is reused and it is NOT
        closed (the caller owns it). When None, a throwaway client is built + closed
        here (the default per-call behaviour).
    """
    if not eval_row.codigo_informe:
        return False
    own = client is None
    if own:
        client = PortalClient()
    try:
        if own:
            client.load()
            client.select_region(region_id)
            client.search(region_id, comuna_id, tipo)
        return _post_informe(client, eval_row.codigo_informe, region_id,
                             comuna_id, tipo, dest)
    except Exception as e:  # noqa: BLE001
        logger.warning("minvu download failed: %s", e)
        return False
    finally:
        if own:
            client.close()


def download_comuna_pdfs(eval_rows, dest_for, region_id: int, comuna_id: int,
                         tipo: int) -> dict[str, bool]:
    """Download many PDFs for ONE (region, comuna, tipo) reusing a single search.

    One load → select_region → search primes the VIEWSTATE; each row is then a single
    postback (N+3 requests for N rows instead of 4N). `eval_rows` items must expose
    `eval_id` and `codigo_informe`; `dest_for(eval_id)` returns the destination Path.
    Returns {eval_id: ok}. Note: a VIEWSTATE can expire on long runs; callers should
    keep comuna batches modest or fall back to per-call download on failure.
    """
    out: dict[str, bool] = {}
    with PortalClient() as client:
        client.select_region(region_id)
        client.search(region_id, comuna_id, tipo)
        for row in eval_rows:
            if not row.codigo_informe:
                out[row.eval_id] = False
                continue
            try:
                out[row.eval_id] = _post_informe(
                    client, row.codigo_informe, region_id, comuna_id, tipo,
                    dest_for(row.eval_id))
            except Exception as e:  # noqa: BLE001
                logger.warning("minvu download failed for %s: %s", row.eval_id, e)
                out[row.eval_id] = False
    return out

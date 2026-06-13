"""Client for the MINVU CEV portal (ASP.NET WebForms, VIEWSTATE-driven).

Verified live (Phase 3, 2026-06-13): portal is HTTPS; region selection is a
postback that repopulates the comuna dropdown; the search button is
`BtnConsultarbusq`; results paginate via __doPostBack(grid, 'Page$N') at 10/page.
Two result grids: grdViviendasPre (tipo 1) / grdViviendasCal (tipo 2).
"""
import re

import httpx

from informes_cev_minvu_db.config import settings

PATH = "/Publico/BusquedaVivienda.aspx"
TOOLKIT = (";;AjaxControlToolkit, Version=4.1.60501.0, Culture=neutral, "
           "PublicKeyToken=28f01b0e84b6d53e:es-CL:5c09f731-4796-4c62-944b-da90522e2541:"
           "de1feab2:f2c8e708:720a52bf:f9cec9bc:589eaa30:a67c2700:ab09e3fe:87104b7c:"
           "8613aea7:3202a5a2:be6fb298")


def _hidden(name: str, text: str) -> str:
    m = re.search(rf'id="{name}"\s+value="([^"]*)"', text)
    return m.group(1) if m else ""


class PortalClient:
    def __init__(self, base_url: str | None = None, timeout: float = 40.0):
        self.url = (base_url or settings.minvu_base_url).rstrip("/") + PATH
        self._client = httpx.Client(
            timeout=timeout, verify=False,  # portal cert chain is incomplete
            headers={"User-Agent": "Mozilla/5.0", "Referer": self.url},
        )
        self._vs = ""
        self._vsg = ""

    def close(self):
        self._client.close()

    def __enter__(self):
        self.load()
        return self

    def __exit__(self, *exc):
        self.close()

    def _base_fields(self) -> dict:
        return {
            "ToolkitScriptManager2_HiddenField": TOOLKIT,
            "__EVENTARGUMENT": "", "__VIEWSTATEGENERATOR": self._vsg,
            "__SCROLLPOSITIONX": "0", "__SCROLLPOSITIONY": "0", "__VIEWSTATEENCRYPTED": "",
            "ctl00$ContentPlaceHolder1$look": "0",
            "ctl00$ContentPlaceHolder1$dbTipologia": "-1",
            "ctl00$ContentPlaceHolder1$TxtNombrePry": "",
            "ctl00$ContentPlaceHolder1$txtIdentificacion": "",
            "ctl00$ContentPlaceHolder1$txtCampo": "0",
            "ctl00$ContentPlaceHolder1$txtOrden": "0",
        }

    def load(self) -> str:
        r = self._client.get(self.url)
        r.raise_for_status()
        self._vs = _hidden("__VIEWSTATE", r.text)
        self._vsg = _hidden("__VIEWSTATEGENERATOR", r.text)
        return r.text

    def select_region(self, region_id: int) -> str:
        """Postback on the region dropdown; repopulates comunas. Returns HTML."""
        f = {**self._base_fields(),
             "__EVENTTARGET": "ctl00$ContentPlaceHolder1$dbRegion", "__VIEWSTATE": self._vs,
             "ctl00$ContentPlaceHolder1$dbRegion": str(region_id),
             "ctl00$ContentPlaceHolder1$dbComuna": "-1",
             "ctl00$ContentPlaceHolder1$dbCertificacion": "-1"}
        r = self._client.post(self.url, data=f)
        r.raise_for_status()
        self._vs = _hidden("__VIEWSTATE", r.text)
        return r.text

    def search(self, region_id: int, comuna_id: int, tipo: int) -> str:
        """Click 'Consultar' for region/comuna/tipo. Returns results HTML (page 1)."""
        f = {**self._base_fields(), "__EVENTTARGET": "", "__VIEWSTATE": self._vs,
             "ctl00$ContentPlaceHolder1$dbRegion": str(region_id),
             "ctl00$ContentPlaceHolder1$dbComuna": str(comuna_id),
             "ctl00$ContentPlaceHolder1$dbCertificacion": str(tipo),
             "ctl00$ContentPlaceHolder1$BtnConsultarbusq": "Consultar"}
        r = self._client.post(self.url, data=f)
        r.raise_for_status()
        self._vs = _hidden("__VIEWSTATE", r.text)
        return r.text

    def goto_page(self, region_id: int, comuna_id: int, tipo: int, page: int) -> str:
        """Navigate to result page N via the grid pager postback."""
        grid = "grdViviendasCal" if tipo == 2 else "grdViviendasPre"
        f = {**self._base_fields(),
             "__EVENTTARGET": f"ctl00$ContentPlaceHolder1${grid}",
             "__EVENTARGUMENT": f"Page${page}", "__VIEWSTATE": self._vs,
             "ctl00$ContentPlaceHolder1$dbRegion": str(region_id),
             "ctl00$ContentPlaceHolder1$dbComuna": str(comuna_id),
             "ctl00$ContentPlaceHolder1$dbCertificacion": str(tipo)}
        r = self._client.post(self.url, data=f)
        r.raise_for_status()
        self._vs = _hidden("__VIEWSTATE", r.text)
        return r.text

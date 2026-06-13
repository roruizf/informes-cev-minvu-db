"""One-way read mirror of CEV data in nocodebackend.com.

Follows the sgip-system NocodeMirror pattern (MCP for DDL, REST for CRUD) but is
INCREMENTAL (upsert by a business key), NOT full-replace: sgip's wipe-and-recreate
is fine for tens of rows but fatal at ~156K. We search by key → update or create.

API shape (verified against api.nocodebackend.com):
  {BASE}/{op}/{table}?Instance={instance}
  ops: create (POST) | read (GET) | search (POST, filter dict) |
       update/{id} (PUT) | delete/{id} (DELETE)
  auth: Authorization: Bearer {secret_key}
DDL (CREATE TABLE) is not in the REST data API; it IS in the MCP endpoint
(tool execute_sql, auth via access token).

Mirror scope: the report directory (evaluaciones) + all extracted data
(informe_v2_pagina1..7) + dimensionals. EXCLUDES scraping mechanics
(busquedas, paginas_html). Invariant: directory = full universe; extracted = processed.
"""
import json
import logging

import requests

from informes_cev_minvu_db.config import settings

logger = logging.getLogger(__name__)
_TIMEOUT = 20
_MCP_URL = "https://app.nocodebackend.com/api/mcp/sse"


def _sql_type(value) -> str:
    if isinstance(value, bool):
        return "TINYINT"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE"
    return "TEXT"


def _infer_ddl(table: str, rows: list[dict]) -> str:
    columns: dict[str, str] = {}
    for row in rows:
        for key, value in row.items():
            if key == "id":
                continue  # mirror owns its own `id`
            if key not in columns or (columns[key] == "TEXT" and value is not None):
                if value is not None:
                    columns[key] = _sql_type(value)
                columns.setdefault(key, "TEXT")
    cols_sql = ", ".join(f"`{n}` {t}" for n, t in columns.items())
    return (f"CREATE TABLE IF NOT EXISTS `{table}` "
            f"(`id` INT AUTO_INCREMENT PRIMARY KEY{', ' + cols_sql if cols_sql else ''})")


class NocodeMirror:
    def __init__(self, base_url=None, instance=None, secret_key=None,
                 access_token=None, mcp_url=None, session=None):
        self.base_url = (base_url or settings.nocodebackend_api_url).rstrip("/")
        self.instance = instance or settings.nocodebackend_instance
        self.secret_key = settings.nocodebackend_secret_key if secret_key is None else secret_key
        self.access_token = settings.nocodebackend_access_token if access_token is None else access_token
        self.mcp_url = mcp_url or _MCP_URL
        self._session = session or requests.Session()
        self._ensured: set[str] = set()  # tables we've already CREATE-TABLE'd this run

    @property
    def enabled(self) -> bool:
        return bool(self.secret_key and self.instance)

    # ── MCP: DDL bootstrap ──────────────────────────────────────────────────

    def _mcp_execute_sql(self, sql: str) -> dict:
        resp = self._session.post(
            self.mcp_url,
            headers={"Authorization": f"Bearer {self.access_token}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "execute_sql",
                             "arguments": {"database": self.instance, "sql": sql}}},
            timeout=30)
        if not resp.ok:
            raise RuntimeError(f"MCP execute_sql: HTTP {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"MCP execute_sql: {json.dumps(data['error'])[:200]}")
        return data.get("result", {})

    def ensure_table(self, table: str, rows: list[dict]) -> str:
        if table in self._ensured:
            return "cached"
        if not self.access_token:
            return "skip: no access token"
        if not rows:
            return "skip: no rows"
        # If the table already has data, it exists — skip DDL (avoids the MCP
        # "user email limit check" warning on no-op CREATE TABLE IF NOT EXISTS).
        try:
            if self.search(table, {}):
                self._ensured.add(table)
                return "exists"
        except Exception:  # noqa: BLE001
            pass
        try:
            self._mcp_execute_sql(_infer_ddl(table, rows))
            self._ensured.add(table)
            return "ok"
        except Exception as e:  # noqa: BLE001
            logger.warning("ensure_table %s failed: %s", table, e)
            return f"error: {str(e)[:120]}"

    # ── REST CRUD ───────────────────────────────────────────────────────────

    def _req(self, method: str, path: str, json_body=None):
        return self._session.request(
            method, f"{self.base_url}/{path}", params={"Instance": self.instance},
            headers={"Authorization": f"Bearer {self.secret_key}",
                     "Content-Type": "application/json", "accept": "application/json"},
            json=json_body, timeout=_TIMEOUT)

    def search(self, table: str, filters: dict) -> list[dict]:
        resp = self._req("POST", f"search/{table}", json_body=filters)
        if not resp.ok:
            return []
        data = resp.json()
        if isinstance(data, dict):
            data = data.get("data") or data.get("records") or []
        return data if isinstance(data, list) else []

    def _create(self, table: str, row: dict) -> None:
        resp = self._req("POST", f"create/{table}", json_body=row)
        if not resp.ok:
            raise RuntimeError(f"create/{table}: HTTP {resp.status_code} {resp.text[:200]}")

    def _update(self, table: str, mirror_id, row: dict) -> None:
        resp = self._req("PUT", f"update/{table}/{mirror_id}", json_body=row)
        if not resp.ok:
            raise RuntimeError(f"update/{table}/{mirror_id}: HTTP {resp.status_code} {resp.text[:200]}")

    def upsert(self, table: str, rows: list[dict], key: str) -> dict:
        """Incremental upsert: for each row, search by `key`; update if found, else create.

        `key` is the business key (e.g. eval_id). Rows must include it. The mirror's
        own `id` is never sent on create/update.
        """
        created = updated = 0
        for row in rows:
            payload = {k: v for k, v in row.items() if k != "id"}
            kv = payload.get(key)
            existing = self.search(table, {key: kv}) if kv is not None else []
            if existing and existing[0].get("id") is not None:
                self._update(table, existing[0]["id"], payload)
                updated += 1
            else:
                self._create(table, payload)
                created += 1
        return {"created": created, "updated": updated}

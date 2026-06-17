"""Unit tests for PortalClient network retry/backoff (no real network)."""
import httpx
import pytest

from informes_cev_minvu_db.discovery.portal_client import PortalClient


def _client(monkeypatch):
    c = PortalClient()
    c._net_retries = 3
    monkeypatch.setattr(c, "_client", _FakeHTTP())
    # don't actually sleep
    import informes_cev_minvu_db.discovery.portal_client as pc
    monkeypatch.setattr(pc.time, "sleep", lambda s: None)
    return c


class _FakeResp:
    status_code = 200
    text = "ok"


class _FakeHTTP:
    def __init__(self):
        self.calls = 0
        self.script = []  # list of exceptions or None (success)

    def request(self, method, url, **kw):
        i = self.calls
        self.calls += 1
        if i < len(self.script) and self.script[i] is not None:
            raise self.script[i]
        return _FakeResp()


def test_retries_then_succeeds(monkeypatch):
    c = _client(monkeypatch)
    c._client.script = [httpx.ConnectError("eof"), httpx.ReadError("drop"), None]
    r = c._request("GET")
    assert r.status_code == 200
    assert c._client.calls == 3  # 2 failures + 1 success


def test_raises_after_max_retries(monkeypatch):
    c = _client(monkeypatch)
    c._client.script = [httpx.ConnectError("eof")] * 5  # always fails
    with pytest.raises(RuntimeError, match="failed after 3 retries"):
        c._request("GET")
    assert c._client.calls == 3


def test_succeeds_first_try(monkeypatch):
    c = _client(monkeypatch)
    c._client.script = [None]
    assert c._request("POST", data={}).status_code == 200
    assert c._client.calls == 1

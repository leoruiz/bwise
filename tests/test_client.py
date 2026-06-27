import io
import json
import urllib.error

import pytest

from bwise import client
from bwise.client import AmbiguousItemError, BwError, VaultLockedError


def test_extract_token_prefers_password():
    item = {"login": {"password": "pw"}, "fields": [{"value": "f"}], "notes": "n"}
    assert client.extract_token(item) == "pw"


def test_extract_token_falls_back_to_field_then_notes():
    assert client.extract_token({"fields": [{"value": "f"}]}) == "f"
    assert client.extract_token({"notes": "  n  "}) == "n"


def test_extract_token_raises_when_empty():
    with pytest.raises(BwError):
        client.extract_token({"fields": [{"value": ""}], "notes": "  "})


def test_check_locked_raises_vault_locked_error():
    with pytest.raises(VaultLockedError, match="vault is locked"):
        client.check({"success": False, "message": "Vault is locked."})


def test_vault_locked_error_is_a_bwerror():
    assert issubclass(VaultLockedError, BwError)


def test_check_passes_through_other_messages():
    with pytest.raises(BwError, match="boom") as exc:
        client.check({"success": False, "message": "boom"})
    assert not isinstance(exc.value, VaultLockedError)


def test_get_item_exact_name_match(monkeypatch):
    res = {"success": True, "data": {"data": [{"name": "a"}, {"name": "ab"}]}}
    monkeypatch.setattr(client, "request", lambda *a, **k: res)
    assert client.get_item("a")["name"] == "a"


def test_get_item_not_found(monkeypatch):
    res = {"success": True, "data": {"data": [{"name": "ab"}]}}
    monkeypatch.setattr(client, "request", lambda *a, **k: res)
    with pytest.raises(BwError, match="not found"):
        client.get_item("a")


def test_get_item_by_id(monkeypatch):
    uuid = "3f2a1b4c-5d6e-7f80-9a1b-2c3d4e5f6071"
    item = {"id": uuid, "name": "x"}
    monkeypatch.setattr(
        client, "request", lambda m, p, *a, **k: {"success": True, "data": item}
    )
    assert client.get_item(uuid) == item


def test_get_item_ambiguous_raises(monkeypatch):
    dupes = [{"name": "dup", "id": "1"}, {"name": "dup", "id": "2"}]
    res = {"success": True, "data": {"data": dupes}}
    monkeypatch.setattr(client, "request", lambda *a, **k: res)
    with pytest.raises(AmbiguousItemError) as exc:
        client.get_item("dup")
    assert exc.value.name == "dup"
    assert len(exc.value.candidates) == 2


class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self, *a):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_request_success(monkeypatch):
    monkeypatch.setattr(
        client.urllib.request, "urlopen", lambda *a, **k: _FakeResp({"success": True})
    )
    assert client.request("POST", "/x", {"a": 1}) == {"success": True}


def test_request_http_error_non_json_body(monkeypatch):
    def fake_urlopen(*a, **k):
        raise urllib.error.HTTPError(
            "http://x", 500, "err", {}, io.BytesIO(b"not json")
        )

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(BwError, match="HTTP 500"):
        client.request("GET", "/x")


def test_status_parses_template(monkeypatch):
    payload = {"data": {"template": {"status": "unlocked"}}}
    monkeypatch.setattr(client, "request", lambda *a, **k: payload)
    assert client.status() == "unlocked"


def test_put_item_calls_check(monkeypatch):
    seen = {}
    monkeypatch.setattr(client, "request", lambda *a, **k: {"success": True})
    assert client.put_item({"id": "1"}) == {"success": True}


def test_extract_token_reads_notes(monkeypatch):
    assert client.extract_token({"notes": "  n  "}) == "n"


def _http_error(code, body):
    return urllib.error.HTTPError(
        "http://x", code, "err", {}, io.BytesIO(json.dumps(body).encode())
    )


def test_request_reads_locked_400_body(monkeypatch):
    def fake_urlopen(*a, **k):
        raise _http_error(400, {"success": False, "message": "Vault is locked."})

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    res = client.request("GET", "/whatever")
    assert res == {"success": False, "message": "Vault is locked."}


def test_request_unreachable_raises_bwerror(monkeypatch):
    def fake_urlopen(*a, **k):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(BwError, match="cannot reach bw serve"):
        client.request("GET", "/status")

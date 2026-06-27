import io
import json
import urllib.error

import pytest

from bwise import client
from bwise.client import BwError


def test_extract_token_prefers_password():
    item = {"login": {"password": "pw"}, "fields": [{"value": "f"}], "notes": "n"}
    assert client.extract_token(item) == "pw"


def test_extract_token_falls_back_to_field_then_notes():
    assert client.extract_token({"fields": [{"value": "f"}]}) == "f"
    assert client.extract_token({"notes": "  n  "}) == "n"


def test_extract_token_raises_when_empty():
    with pytest.raises(BwError):
        client.extract_token({"fields": [{"value": ""}], "notes": "  "})


def test_check_locked_message_is_actionable():
    with pytest.raises(BwError, match="run `bwise up`"):
        client.check({"success": False, "message": "Vault is locked."})


def test_check_passes_through_other_messages():
    with pytest.raises(BwError, match="boom"):
        client.check({"success": False, "message": "boom"})


def test_get_item_exact_name_match(monkeypatch):
    res = {"success": True, "data": {"data": [{"name": "a"}, {"name": "ab"}]}}
    monkeypatch.setattr(client, "request", lambda *a, **k: res)
    assert client.get_item("a")["name"] == "a"


def test_get_item_not_found(monkeypatch):
    res = {"success": True, "data": {"data": [{"name": "ab"}]}}
    monkeypatch.setattr(client, "request", lambda *a, **k: res)
    with pytest.raises(BwError, match="not found"):
        client.get_item("a")


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

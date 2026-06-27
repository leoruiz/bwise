import json

import pytest

from bwise import cli
from bwise.client import BwError


@pytest.fixture
def patch_request(monkeypatch):
    calls = []

    def fake(method, path, body=None, **kw):
        calls.append((method, path, body))
        return {"success": True}

    monkeypatch.setattr(cli, "request", fake)
    return calls


def test_unlock_already_unlocked(monkeypatch, patch_request):
    monkeypatch.setattr(cli, "status", lambda: "unlocked")
    cli.up()  # no prompt, no request
    assert patch_request == []


def test_unlock_unauthenticated_raises(monkeypatch):
    monkeypatch.setattr(cli, "status", lambda: "unauthenticated")
    with pytest.raises(BwError, match="not logged in"):
        cli.up()


def test_unlock_happy_path(monkeypatch, patch_request):
    monkeypatch.setattr(cli, "status", lambda: "locked")
    monkeypatch.setattr(cli, "prompt_master_password", lambda: "pw")
    cli._default()
    assert ("POST", "/unlock", {"password": "pw"}) in patch_request
    assert ("POST", "/sync", None) in patch_request


def test_unlock_no_password_raises(monkeypatch):
    monkeypatch.setattr(cli, "status", lambda: "locked")
    monkeypatch.setattr(cli, "prompt_master_password", lambda: None)
    with pytest.raises(BwError, match="no master password"):
        cli.up()


def test_unlock_wrong_password_raises(monkeypatch):
    monkeypatch.setattr(cli, "status", lambda: "locked")
    monkeypatch.setattr(cli, "prompt_master_password", lambda: "bad")
    monkeypatch.setattr(
        cli, "request", lambda *a, **k: {"success": False, "message": "no"}
    )
    with pytest.raises(BwError, match="unlock failed"):
        cli.up()


def test_lock_success(monkeypatch):
    monkeypatch.setattr(cli, "request", lambda *a, **k: {"success": True})
    cli.lock()


def test_lock_failure(monkeypatch):
    monkeypatch.setattr(
        cli, "request", lambda *a, **k: {"success": False, "message": "x"}
    )
    cli.lock()


@pytest.mark.parametrize(
    "state,code",
    [("unlocked", 0), ("locked", 1), ("unauthenticated", 2), ("nope", 3)],
)
def test_status_exit_codes(monkeypatch, capsys, state, code):
    monkeypatch.setattr(cli, "status", lambda: state)
    with pytest.raises(SystemExit) as exc:
        cli.status_cmd()
    assert exc.value.code == code
    assert capsys.readouterr().out.strip() == state


def test_status_unreachable_and_quiet(monkeypatch, capsys):
    def boom():
        raise BwError("down")

    monkeypatch.setattr(cli, "status", boom)
    with pytest.raises(SystemExit) as exc:
        cli.status_cmd(quiet=True)
    assert exc.value.code == 3
    assert capsys.readouterr().out == ""


def test_env_no_fields_warns(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_item", lambda item: {"fields": []})
    cli.env_cmd("x")
    assert capsys.readouterr().out == ""


def test_env_exports_and_writes_file(monkeypatch, capsys, tmp_path):
    item = {
        "fields": [{"name": "TOK", "value": "v"}, {"name": "@file:f", "value": "d"}]
    }
    monkeypatch.setattr(cli, "get_item", lambda i: item)
    written = {}
    monkeypatch.setattr(
        cli.env_mod, "write_secret_file", lambda p, v: written.__setitem__(p, v)
    )
    cli.env_cmd("x")
    assert "export TOK='v'" in capsys.readouterr().out
    assert written == {"f": "d"}


def test_get_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_item", lambda i: {"id": "1", "notes": "n"})
    cli.get("x")
    assert json.loads(capsys.readouterr().out) == {"id": "1", "notes": "n"}


def test_get_notes(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_item", lambda i: {"notes": "secret"})
    cli.get("x", notes=True)
    assert capsys.readouterr().out == "secret"


def test_get_notes_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_item", lambda i: {})
    cli.get("x", notes=True)
    assert capsys.readouterr().out == ""


def test_token(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_item", lambda i: {"login": {"password": "pw"}})
    cli.token("x")
    assert capsys.readouterr().out.strip() == "pw"


def test_set_notes(monkeypatch):
    item = {"id": "1", "notes": "old"}
    monkeypatch.setattr(cli, "get_item", lambda i: item)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("new notes"))
    saved = {}
    monkeypatch.setattr(cli, "put_item", lambda it: saved.update(it))
    cli.set_notes("x")
    assert saved["notes"] == "new notes"


def test_main_success(monkeypatch):
    monkeypatch.setattr(cli, "app", lambda: None)
    cli.main()  # no exit


def test_main_bwerror_exits_2(monkeypatch, capsys):
    def boom():
        raise BwError("locked")

    monkeypatch.setattr(cli, "app", boom)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "bwise: locked" in capsys.readouterr().err


def test_doctor_all_ok(monkeypatch, capsys):
    monkeypatch.setattr(cli.doctor_mod, "run_checks", lambda: [("ok", "fine")])
    cli.doctor()  # no SystemExit
    assert "✓ fine" in capsys.readouterr().out


def test_doctor_with_failure_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(cli.doctor_mod, "run_checks", lambda: [("fail", "broken")])
    with pytest.raises(SystemExit) as exc:
        cli.doctor()
    assert exc.value.code == 1
    assert "✗ broken" in capsys.readouterr().out

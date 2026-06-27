import json

import pytest

from bwise import cli
from bwise.client import AmbiguousItemError, BwError, VaultLockedError


class _FakeStdin:
    def __init__(self, tty: bool):
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


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


def test_lock_failure_raises(monkeypatch):
    monkeypatch.setattr(
        cli, "request", lambda *a, **k: {"success": False, "message": "x"}
    )
    with pytest.raises(BwError, match="lock failed"):
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
    cli.get_notes("x")
    assert capsys.readouterr().out == "secret"


def test_get_notes_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_item", lambda i: {})
    cli.get_notes("x")
    assert capsys.readouterr().out == ""


def test_token(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_item", lambda i: {"login": {"password": "pw"}})
    cli.token("x")
    assert capsys.readouterr().out.strip() == "pw"


def test_describe_uses_username_or_placeholder():
    assert cli._describe({"login": {"username": "alice@x"}}) == "alice@x"
    assert cli._describe({}) == "(no username)"


def test_resolve_item_passthrough(monkeypatch):
    monkeypatch.setattr(cli, "get_item", lambda n: {"id": "1"})
    assert cli._resolve_item("x") == {"id": "1"}


def test_resolve_item_disambiguates_on_tty(monkeypatch, capsys):
    cands = [
        {"id": "id-aaa", "login": {"username": "alice@x"}},
        {"id": "id-bbb", "login": {"username": "bob@y"}},
    ]

    def raise_ambiguous(name):
        raise AmbiguousItemError("dup", cands)

    monkeypatch.setattr(cli, "get_item", raise_ambiguous)
    monkeypatch.setattr(cli.sys, "stdin", _FakeStdin(True))
    monkeypatch.setattr("builtins.input", lambda: "2")
    assert cli._resolve_item("dup") is cands[1]
    menu = capsys.readouterr().err
    assert "alice@x" in menu and "id-aaa" in menu
    assert "bob@y" in menu and "id-bbb" in menu


def test_pick_non_interactive_lists_ids(monkeypatch):
    exc = AmbiguousItemError(
        "dup", [{"id": "aaa", "login": {"username": "a"}}, {"id": "bbb"}]
    )
    monkeypatch.setattr(cli.sys, "stdin", _FakeStdin(False))
    with pytest.raises(BwError, match="re-run with the id") as raised:
        cli._pick(exc)
    assert "aaa" in str(raised.value) and "bbb" in str(raised.value)


def test_prompt_choice_retries_then_accepts(monkeypatch):
    answers = iter(["x", "0", "3", "1"])
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    assert cli._prompt_choice(2) == 1


def test_prompt_choice_eof_raises(monkeypatch):
    def boom():
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    with pytest.raises(BwError, match="no selection"):
        cli._prompt_choice(2)


def test_list_items(monkeypatch, capsys):
    items = [
        {"name": "login1", "type": 1},
        {"name": "note1", "type": 2},
        {"name": "", "type": 2},
        {"name": "note2", "type": 2},
    ]
    res = {"success": True, "data": {"data": items}}
    monkeypatch.setattr(cli, "request", lambda *a, **k: res)
    cli.list_items()
    assert capsys.readouterr().out.split() == ["login1", "note1", "note2"]


def test_list_items_filters_by_type(monkeypatch, capsys):
    items = [{"name": "login1", "type": 1}, {"name": "note1", "type": 2}]
    res = {"success": True, "data": {"data": items}}
    monkeypatch.setattr(cli, "request", lambda *a, **k: res)
    cli.list_items(item_type="note")
    assert capsys.readouterr().out.split() == ["note1"]
    monkeypatch.setattr(cli, "request", lambda *a, **k: res)
    cli.list_items(item_type="login")
    assert capsys.readouterr().out.split() == ["login1"]


def test_completion_prints_fish_script(capsys):
    cli.completion("fish")
    assert "complete -c bwise" in capsys.readouterr().out


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


def test_main_vault_locked_adds_hint(monkeypatch, capsys):
    def boom():
        raise VaultLockedError("vault is locked")

    monkeypatch.setattr(cli, "app", boom)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "run `bwise up`" in capsys.readouterr().err


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

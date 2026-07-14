import subprocess

from bwise import pinentry


def test_unquote_assuan_decodes_percent_escapes():
    assert pinentry._unquote_assuan("a%25b%0Ac") == "a%b\nc"


def test_unquote_assuan_passthrough():
    assert pinentry._unquote_assuan("plain") == "plain"


def test_find_pinentry_uses_override(monkeypatch):
    monkeypatch.setenv("BWISE_PINENTRY", "my-pinentry")
    monkeypatch.setattr(pinentry.shutil, "which", lambda p: "/usr/bin/" + p)
    assert pinentry.find_pinentry() == "my-pinentry"


def test_find_pinentry_override_not_found(monkeypatch):
    monkeypatch.setenv("BWISE_PINENTRY", "missing")
    monkeypatch.setattr(pinentry.shutil, "which", lambda p: None)
    assert pinentry.find_pinentry() is None


def test_find_pinentry_candidate(monkeypatch):
    monkeypatch.delenv("BWISE_PINENTRY", raising=False)
    monkeypatch.setattr(
        pinentry.shutil, "which", lambda p: "/x" if p == "pinentry" else None
    )
    assert pinentry.find_pinentry() == "pinentry"


def test_find_pinentry_none(monkeypatch):
    monkeypatch.delenv("BWISE_PINENTRY", raising=False)
    monkeypatch.setattr(pinentry.shutil, "which", lambda p: None)
    assert pinentry.find_pinentry() is None


def test_find_pinentry_skips_all_over_ssh(monkeypatch):
    monkeypatch.delenv("BWISE_PINENTRY", raising=False)
    monkeypatch.setenv("SSH_CONNECTION", "1.2.3.4 5 6.7.8.9 22")
    monkeypatch.setattr(pinentry.shutil, "which", lambda p: "/usr/bin/" + p)
    # Headless: no pinentry variant is usable, so fall back to getpass.
    assert pinentry.find_pinentry() is None


def test_find_pinentry_ssh_tty_also_headless(monkeypatch):
    monkeypatch.delenv("BWISE_PINENTRY", raising=False)
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.setenv("SSH_TTY", "/dev/ttys001")
    monkeypatch.setattr(pinentry.shutil, "which", lambda p: "/usr/bin/" + p)
    assert pinentry.find_pinentry() is None


def test_find_pinentry_gui_prefers_mac(monkeypatch):
    monkeypatch.delenv("BWISE_PINENTRY", raising=False)
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.delenv("SSH_TTY", raising=False)
    monkeypatch.setattr(pinentry.shutil, "which", lambda p: "/usr/bin/" + p)
    assert pinentry.find_pinentry() == "pinentry-mac"


def test_find_pinentry_override_honored_over_ssh(monkeypatch):
    monkeypatch.setenv("BWISE_PINENTRY", "pinentry-mac")
    monkeypatch.setenv("SSH_CONNECTION", "1.2.3.4 5 6.7.8.9 22")
    monkeypatch.setattr(pinentry.shutil, "which", lambda p: "/usr/bin/" + p)
    assert pinentry.find_pinentry() == "pinentry-mac"


def _fake_proc(stdout):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_pinentry_prompt_returns_data(monkeypatch):
    monkeypatch.setattr(
        pinentry.subprocess, "run", lambda *a, **k: _fake_proc("OK\nD s%25cret\nOK\n")
    )
    assert pinentry._pinentry_prompt("p") == "s%cret"


def test_pinentry_prompt_error(monkeypatch):
    monkeypatch.setattr(
        pinentry.subprocess, "run", lambda *a, **k: _fake_proc("ERR 83886179 cancel\n")
    )
    assert pinentry._pinentry_prompt("p") is None


def test_pinentry_prompt_no_data(monkeypatch):
    monkeypatch.setattr(
        pinentry.subprocess, "run", lambda *a, **k: _fake_proc("OK\nBYE\n")
    )
    assert pinentry._pinentry_prompt("p") is None


def test_prompt_master_password_via_pinentry(monkeypatch):
    monkeypatch.setattr(pinentry, "find_pinentry", lambda: "p")
    monkeypatch.setattr(pinentry, "_pinentry_prompt", lambda prog: "pw")
    assert pinentry.prompt_master_password() == "pw"


def test_prompt_master_password_getpass_fallback(monkeypatch):
    monkeypatch.setattr(pinentry, "find_pinentry", lambda: None)
    monkeypatch.setattr(pinentry.getpass, "getpass", lambda prompt: "typed")
    assert pinentry.prompt_master_password() == "typed"


def test_prompt_master_password_getpass_empty(monkeypatch):
    monkeypatch.setattr(pinentry, "find_pinentry", lambda: None)
    monkeypatch.setattr(pinentry.getpass, "getpass", lambda prompt: "")
    assert pinentry.prompt_master_password() is None

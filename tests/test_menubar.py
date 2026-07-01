import subprocess
import sys
import types

import pytest

from bwise import menubar
from bwise.menubar import RumpsUI, VaultController


class _FakeUI:
    def __init__(self):
        self.title = None

    def set_title(self, text):
        self.title = text


def _controller(codes):
    """Controller whose runner returns queued exit codes and records calls."""
    calls = []
    seq = iter(codes)

    def run(args):
        calls.append(args)
        return next(seq)

    ui = _FakeUI()
    return VaultController(ui, run), ui, calls


def test_refresh_unlocked_sets_open_glyph():
    ctrl, ui, _ = _controller([menubar.UNLOCKED])
    ctrl.refresh()
    assert ui.title == "🔓"


def test_refresh_locked_sets_closed_glyph():
    ctrl, ui, _ = _controller([menubar.LOCKED])
    ctrl.refresh()
    assert ui.title == "🔒"


def test_refresh_unauthenticated_glyph():
    ctrl, ui, _ = _controller([menubar.UNAUTHENTICATED])
    ctrl.refresh()
    assert ui.title == "🔑"


def test_refresh_unreachable_glyph():
    ctrl, ui, _ = _controller([99])
    ctrl.refresh()
    assert ui.title == menubar.UNREACHABLE_GLYPH


def test_unlock_runs_then_refreshes():
    ctrl, ui, calls = _controller([0, menubar.UNLOCKED])
    ctrl.unlock()
    assert calls[0] == ["bwise", "up"]
    assert calls[1] == ["bwise", "status", "--quiet"]
    assert ui.title == "🔓"


def test_lock_runs_then_refreshes():
    ctrl, ui, calls = _controller([0, menubar.LOCKED])
    ctrl.lock()
    assert calls[0] == ["bwise", "lock"]
    assert ui.title == "🔒"


def test_sync_runs_then_refreshes():
    ctrl, ui, calls = _controller([0, menubar.UNLOCKED])
    ctrl.sync()
    assert calls[0] == ["bwise", "sync"]
    assert ui.title == "🔓"


def test_rumps_ui_sets_app_title():
    app = types.SimpleNamespace(title=None)
    RumpsUI(app).set_title("🔓")
    assert app.title == "🔓"


def test_run_bwise_returns_exit_code(monkeypatch):
    monkeypatch.setattr(
        menubar.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 3),
    )
    assert menubar._run_bwise(["bwise", "status"]) == 3


def test_load_rumps_imports_module(monkeypatch):
    fake = types.ModuleType("rumps")
    monkeypatch.setitem(sys.modules, "rumps", fake)
    assert menubar._load_rumps() is fake


class _FakeApp:
    def __init__(self, name, title=None):
        self.name = name
        self.title = title
        self.menu = None
        self.ran = False

    def run(self):
        self.ran = True


class _FakeMenuItem:
    def __init__(self, label, callback=None):
        self.label = label
        self.callback = callback


class _FakeTimer:
    def __init__(self, callback, interval):
        self.callback = callback
        self.interval = interval
        self.started = False

    def start(self):
        self.started = True


def _fake_rumps():
    mod = types.ModuleType("rumps")
    mod.App = _FakeApp
    mod.MenuItem = _FakeMenuItem
    mod.Timer = _FakeTimer
    return mod


def test_main_missing_extra_exits_with_hint(capsys):
    def boom():
        raise ImportError("no rumps")

    with pytest.raises(SystemExit) as exc:
        menubar.main(load=boom)
    assert exc.value.code == 1
    assert "menubar" in capsys.readouterr().err


def test_main_wires_menu_timer_and_runs():
    rumps = _fake_rumps()
    captured = {}

    class _App(_FakeApp):
        def __init__(self, name, title=None):
            super().__init__(name, title)
            captured["app"] = self

    rumps.App = _App
    timers = []
    rumps.Timer = lambda cb, iv: timers.append(_FakeTimer(cb, iv)) or timers[-1]

    calls = []
    menubar.main(
        run=lambda args: calls.append(args) or menubar.UNLOCKED, load=lambda: rumps
    )

    app = captured["app"]
    assert app.ran is True
    assert app.title == "🔓"  # refresh ran before app.run
    labels = [item.label for item in app.menu]
    assert labels == ["Unlock", "Lock", "Sync"]

    # invoke each menu callback + the timer callback to cover the lambdas
    for item in app.menu:
        item.callback(None)
    timers[0].callback(None)
    assert timers[0].started is True
    assert ["bwise", "up"] in calls
    assert ["bwise", "lock"] in calls
    assert ["bwise", "sync"] in calls

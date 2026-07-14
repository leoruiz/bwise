import subprocess
import sys
import types

import pytest

from bwise import menubar
from bwise.menubar import RumpsUI, VaultController


class _FakeUI:
    def __init__(self):
        self.state = None

    def set_state(self, state):
        self.state = state


def _controller(codes):
    """Controller whose runner returns queued exit codes and records calls."""
    calls = []
    seq = iter(codes)

    def run(args):
        calls.append(args)
        return next(seq)

    ui = _FakeUI()
    return VaultController(ui, run), ui, calls


def test_refresh_unlocked_sets_unlocked_state():
    ctrl, ui, _ = _controller([menubar.UNLOCKED])
    ctrl.refresh()
    assert ui.state == menubar.UNLOCKED


def test_refresh_locked_sets_locked_state():
    ctrl, ui, _ = _controller([menubar.LOCKED])
    ctrl.refresh()
    assert ui.state == menubar.LOCKED


def test_refresh_unauthenticated_state():
    ctrl, ui, _ = _controller([menubar.UNAUTHENTICATED])
    ctrl.refresh()
    assert ui.state == menubar.UNAUTHENTICATED


def test_refresh_unknown_code_falls_back_to_unreachable():
    ctrl, ui, _ = _controller([99])
    ctrl.refresh()
    assert ui.state == menubar.UNREACHABLE


def test_unlock_runs_then_refreshes():
    ctrl, ui, calls = _controller([0, menubar.UNLOCKED])
    ctrl.unlock()
    assert calls[0] == ["bwise", "up"]
    assert calls[1] == ["bwise", "status", "--quiet"]
    assert ui.state == menubar.UNLOCKED


def test_lock_runs_then_refreshes():
    ctrl, ui, calls = _controller([0, menubar.LOCKED])
    ctrl.lock()
    assert calls[0] == ["bwise", "lock"]
    assert ui.state == menubar.LOCKED


def test_sync_runs_then_refreshes():
    ctrl, ui, calls = _controller([0, menubar.UNLOCKED])
    ctrl.sync()
    assert calls[0] == ["bwise", "sync"]
    assert ui.state == menubar.UNLOCKED


def test_rumps_ui_sets_icon_and_template():
    app = types.SimpleNamespace(icon=None, template=None)
    icons = {
        menubar.UNLOCKED: ("/icons/unlocked.png", True),
        menubar.UNREACHABLE: ("/icons/error.png", False),
    }
    ui = RumpsUI(app, icons)

    ui.set_state(menubar.UNLOCKED)
    assert app.icon == "/icons/unlocked.png"
    assert app.template is True

    ui.set_state(menubar.UNREACHABLE)
    assert app.icon == "/icons/error.png"
    assert app.template is False


def test_rumps_ui_unknown_state_falls_back_to_unreachable():
    app = types.SimpleNamespace(icon=None, template=None)
    icons = {menubar.UNREACHABLE: ("/icons/error.png", False)}
    RumpsUI(app, icons).set_state(12345)
    assert app.icon == "/icons/error.png"


def _bound_ui():
    app = types.SimpleNamespace(icon=None, template=None)
    icons = {state: (f"/icons/{state}.png", True) for state in menubar.ICONS}
    ui = RumpsUI(app, icons)
    items = {name: _FakeMenuItem(name) for name in ("unlock", "lock", "sync")}
    ui.bind_menu(items)
    return ui, items


def test_menu_unlocked_shows_lock_and_sync_only():
    ui, items = _bound_ui()
    ui.set_state(menubar.UNLOCKED)
    assert items["unlock"].hidden is True
    assert items["lock"].hidden is False
    assert items["sync"].hidden is False


def test_menu_locked_shows_unlock_only():
    ui, items = _bound_ui()
    ui.set_state(menubar.LOCKED)
    assert items["unlock"].hidden is False
    assert items["lock"].hidden is True
    assert items["sync"].hidden is True


def test_menu_unauthenticated_shows_unlock_only():
    ui, items = _bound_ui()
    ui.set_state(menubar.UNAUTHENTICATED)
    assert items["unlock"].hidden is False
    assert items["lock"].hidden is True
    assert items["sync"].hidden is True


def test_menu_unreachable_hides_all_actions():
    ui, items = _bound_ui()
    ui.set_state(menubar.UNREACHABLE)
    assert all(item.hidden for item in items.values())


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
        self.icon = None
        self.template = None
        self.menu = None
        self.ran = False

    def run(self):
        self.ran = True


class _FakeMenuItem:
    def __init__(self, label, callback=None):
        self.label = label
        self.callback = callback
        self.hidden = False


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
    fake_icons = {state: (f"/icons/{state}.png", True) for state in menubar.ICONS}
    menubar.main(
        run=lambda args: calls.append(args) or menubar.UNLOCKED,
        load=lambda: rumps,
        build_icons=lambda: fake_icons,
    )

    app = captured["app"]
    assert app.ran is True
    # refresh ran before app.run, setting the unlocked icon
    assert app.icon == f"/icons/{menubar.UNLOCKED}.png"
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


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit rendering is macOS-only")
def test_build_icons_renders_a_png_per_state():
    pytest.importorskip("AppKit")
    icons = menubar._build_icons()
    assert set(icons) == set(menubar.ICONS)
    for state, (path, template) in icons.items():
        assert path.endswith(".png")
        with open(path, "rb") as handle:
            assert handle.read(8) == b"\x89PNG\r\n\x1a\n"
        assert template is (menubar.ICONS[state][1] is None)

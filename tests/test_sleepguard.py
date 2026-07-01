import subprocess
import sys
import types

import pytest

from bwise import sleepguard


class _FakeCenter:
    def __init__(self):
        self.name = None
        self.block = None

    def addObserverForName_object_queue_usingBlock_(self, name, obj, queue, block):
        self.name = name
        self.block = block


class _FakeRunLoop:
    def __init__(self):
        self.ran = False

    def run(self):
        self.ran = True


def _fake_appkit():
    center = _FakeCenter()
    loop = _FakeRunLoop()
    mod = types.ModuleType("AppKit")
    mod.NSWorkspaceWillSleepNotification = "NSWorkspaceWillSleepNotification"

    class _Workspace:
        @staticmethod
        def sharedWorkspace():
            return _Workspace()

        def notificationCenter(self):
            return center

    class _RunLoop:
        @staticmethod
        def currentRunLoop():
            return loop

    mod.NSWorkspace = _Workspace
    mod.NSRunLoop = _RunLoop
    return mod, center, loop


def test_main_registers_runs_and_locks_on_sleep():
    appkit, center, loop = _fake_appkit()
    locked = []
    sleepguard.main(lock=lambda note: locked.append(note), load=lambda: appkit)
    assert center.name == "NSWorkspaceWillSleepNotification"
    assert loop.ran is True
    center.block("sleep-note")  # simulate the sleep notification
    assert locked == ["sleep-note"]


def test_main_missing_extra_exits_with_hint(capsys):
    def boom():
        raise ImportError("no AppKit")

    with pytest.raises(SystemExit) as exc:
        sleepguard.main(load=boom)
    assert exc.value.code == 1
    assert "sleepguard" in capsys.readouterr().err


def test_load_appkit_imports_module(monkeypatch):
    fake = types.ModuleType("AppKit")
    monkeypatch.setitem(sys.modules, "AppKit", fake)
    assert sleepguard._load_appkit() is fake


def test_lock_runs_bwise_lock(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        sleepguard.subprocess,
        "run",
        lambda a, **k: seen.setdefault("args", a) or subprocess.CompletedProcess(a, 0),
    )
    sleepguard._lock()
    assert seen["args"] == ["bwise", "lock"]

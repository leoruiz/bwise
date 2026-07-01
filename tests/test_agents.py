import plistlib
import subprocess

import pytest

from bwise import agents
from bwise.client import BwError


@pytest.fixture(autouse=True)
def _stub_which(monkeypatch):
    """Resolve program lookups to fake paths so builds don't need real binaries
    (CI has no bw / bwise-menubar on PATH)."""
    monkeypatch.setattr(agents.shutil, "which", lambda name: f"/usr/bin/{name}")


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class _FakeRunner:
    """Records launchctl argv and returns queued (or default-ok) results."""

    def __init__(self, results=None):
        self.calls = []
        self._results = list(results or [])

    def __call__(self, args):
        self.calls.append(args)
        return self._results.pop(0) if self._results else _completed()

    def verbs(self):
        return [c[1] for c in self.calls if len(c) > 1]


# --- Agent / plist ---------------------------------------------------------


def test_plist_serve_has_keepalive_no_interval():
    agent = agents.build("serve")
    p = agent.plist()
    assert p["Label"] == "com.bwise.serve"
    assert p["KeepAlive"] is True
    assert p["RunAtLoad"] is True
    assert "StartInterval" not in p
    assert p["ProgramArguments"][1:] == [
        "serve",
        "--hostname",
        "localhost",
        "--port",
        "8087",
    ]


def test_plist_sync_has_interval_no_keepalive():
    p = agents.build("sync").plist()
    assert p["StartInterval"] == agents.SYNC_INTERVAL_S
    assert "KeepAlive" not in p


def test_plist_menubar_has_path_env():
    p = agents.build("menubar").plist()
    assert "PATH" in p["EnvironmentVariables"]


def test_sleepguard_agent_runs_sleep_guard():
    agent = agents.build("sleepguard")
    assert agent.label == agents.SLEEPLOCK_LABEL
    assert agent.program[1:] == ["sleep-guard"]
    assert agent.keep_alive is True


def test_plist_roundtrips_through_plistlib():
    p = agents.build("serve").plist()
    assert plistlib.loads(plistlib.dumps(p)) == p


def test_serve_port_from_base(monkeypatch):
    monkeypatch.setattr(agents, "BASE", "http://localhost:9999")
    assert "9999" in agents.build("serve").program


def test_build_unknown_raises():
    with pytest.raises(BwError, match="unknown agent"):
        agents.build("nope")


def test_which_missing_raises(monkeypatch):
    monkeypatch.setattr(agents.shutil, "which", lambda _n: None)
    with pytest.raises(BwError, match="not on PATH"):
        agents.build("sync")


def test_plist_path(tmp_path):
    agent = agents.build("sync")
    assert agent.plist_path(tmp_path) == tmp_path / "com.bwise.sync.plist"


# --- install / uninstall / status -----------------------------------------


def test_install_writes_plist_and_loads(tmp_path):
    agent = agents.build("sync")
    run = _FakeRunner([_completed(1), _completed(), _completed(), _completed()])
    assert agents.install(agent, agents_dir=tmp_path, run=run) == "loaded"
    assert agent.plist_path(tmp_path).exists()
    assert "bootstrap" in run.verbs()
    assert "kickstart" in run.verbs()


def test_install_serve_kept_running_when_loaded(tmp_path):
    agent = agents.build("serve")
    run = _FakeRunner([_completed(0)])  # is_loaded -> print returns 0
    assert agents.install(agent, agents_dir=tmp_path, run=run) == "kept running"
    assert run.verbs() == ["print"]  # no bootout/bootstrap/kickstart


def test_install_serve_loads_when_absent(tmp_path):
    agent = agents.build("serve")
    run = _FakeRunner([_completed(1), _completed(), _completed(), _completed()])
    assert agents.install(agent, agents_dir=tmp_path, run=run) == "loaded"
    assert "bootstrap" in run.verbs()


def test_install_bootstrap_failure_raises(tmp_path):
    agent = agents.build("sync")
    run = _FakeRunner([_completed(), _completed(1, stderr="boom")])
    with pytest.raises(BwError, match="boom"):
        agents.install(agent, agents_dir=tmp_path, run=run)


def test_uninstall_removes_plist(tmp_path):
    agent = agents.build("sync")
    agent.plist_path(tmp_path).write_bytes(b"x")
    run = _FakeRunner()
    assert agents.uninstall(agent, agents_dir=tmp_path, run=run) == "removed"
    assert not agent.plist_path(tmp_path).exists()
    assert "bootout" in run.verbs()


def test_uninstall_not_installed(tmp_path):
    agent = agents.build("sync")
    assert (
        agents.uninstall(agent, agents_dir=tmp_path, run=_FakeRunner())
        == "not installed"
    )


def test_is_loaded_true_false():
    assert (
        agents.is_loaded(agents.build("sync"), run=_FakeRunner([_completed(0)])) is True
    )
    assert (
        agents.is_loaded(agents.build("sync"), run=_FakeRunner([_completed(1)]))
        is False
    )


def test_kickstart_starts_label():
    run = _FakeRunner()
    agents.kickstart("com.bwise.serve", run=run)
    expected = f"gui/{agents.os.getuid()}/com.bwise.serve"
    assert run.calls[0] == ["launchctl", "kickstart", expected]


def test_kickstart_kill_adds_flag():
    run = _FakeRunner()
    agents.kickstart(agents.SERVE_LABEL, kill=True, run=run)
    assert run.calls[0][:3] == ["launchctl", "kickstart", "-k"]


def test_default_runner_uses_subprocess(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        agents.subprocess,
        "run",
        lambda a, **k: seen.setdefault("args", a) or _completed(),
    )
    agents._run(["launchctl", "list"])
    assert seen["args"] == ["launchctl", "list"]

import subprocess
import urllib.error

import pytest

from bwise import serve
from bwise.client import BwError


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_probe_healthy(monkeypatch):
    monkeypatch.setattr(serve.urllib.request, "urlopen", lambda *a, **k: _FakeConn())
    assert serve.probe() == serve.HEALTHY


def test_probe_stuck_on_http_error(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.HTTPError("http://x", 500, "err", {}, None)

    monkeypatch.setattr(serve.urllib.request, "urlopen", boom)
    assert serve.probe() == serve.STUCK


def test_probe_stuck_on_timeout(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(serve.urllib.request, "urlopen", boom)
    assert serve.probe() == serve.STUCK


def test_probe_down_on_refused(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr(serve.urllib.request, "urlopen", boom)
    assert serve.probe() == serve.DOWN


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


def test_restart_kickstarts_serve_agent(monkeypatch):
    seen = {}

    def fake_kickstart(label, *, kill=False):
        seen["label"] = label
        seen["kill"] = kill
        return _completed(0)

    monkeypatch.setattr(serve.agents, "kickstart", fake_kickstart)
    serve.restart()
    assert seen["label"] == serve.agents.SERVE_LABEL
    assert seen["kill"] is True


def test_restart_failure_raises(monkeypatch):
    def fake_kickstart(label, *, kill=False):
        return _completed(1, stderr="boom")

    monkeypatch.setattr(serve.agents, "kickstart", fake_kickstart)
    with pytest.raises(BwError, match="boom"):
        serve.restart()


def test_ensure_healthy_noop_when_healthy(monkeypatch):
    monkeypatch.setattr(serve, "probe", lambda: serve.HEALTHY)
    assert serve.ensure_healthy() == serve.HEALTHY


def test_ensure_healthy_restarts_and_recovers(monkeypatch):
    states = iter([serve.STUCK, serve.DOWN, serve.HEALTHY])
    monkeypatch.setattr(serve, "probe", lambda: next(states))
    monkeypatch.setattr(serve, "restart", lambda: None)
    monkeypatch.setattr(serve.time, "sleep", lambda _s: None)
    reported = []
    assert serve.ensure_healthy(reported.append) == serve.HEALTHY
    assert any("restarting" in m for m in reported)
    assert any("recovered" in m for m in reported)


def test_ensure_healthy_gives_up(monkeypatch):
    monkeypatch.setattr(serve, "probe", lambda: serve.DOWN)
    monkeypatch.setattr(serve, "restart", lambda: None)
    monkeypatch.setattr(serve.time, "sleep", lambda _s: None)
    clock = iter([0.0, 10.0, 20.0])
    monkeypatch.setattr(serve.time, "monotonic", lambda: next(clock))
    with pytest.raises(BwError, match="did not recover"):
        serve.ensure_healthy()

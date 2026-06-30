from bwise import doctor, serve


def _levels(results):
    return [level for level, _ in results]


def _patch(monkeypatch, *, bw="/usr/bin/bw", pinentry="pinentry", probe="healthy"):
    monkeypatch.setattr(doctor.shutil, "which", lambda p: bw)
    monkeypatch.setattr(doctor, "find_pinentry", lambda: pinentry)
    monkeypatch.setattr(doctor.serve, "probe", lambda: probe)


def test_all_healthy(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(doctor, "status", lambda: "unlocked")
    results = doctor.run_checks()
    assert _levels(results) == [doctor.OK] * 5


def test_bw_cli_missing(monkeypatch):
    _patch(monkeypatch, bw=None)
    monkeypatch.setattr(doctor, "status", lambda: "unlocked")
    results = doctor.run_checks()
    assert results[1] == (doctor.FAIL, "bw CLI not found — install the Bitwarden CLI")


def test_pinentry_missing_warns(monkeypatch):
    _patch(monkeypatch, pinentry=None)
    monkeypatch.setattr(doctor, "status", lambda: "unlocked")
    results = doctor.run_checks()
    assert results[2][0] == doctor.WARN
    assert "pinentry" in results[2][1]


def test_daemon_down_short_circuits(monkeypatch):
    _patch(monkeypatch, probe=serve.DOWN)
    results = doctor.run_checks()
    assert _levels(results) == [doctor.OK, doctor.OK, doctor.OK, doctor.FAIL]
    assert "unreachable" in results[-1][1]


def test_daemon_stuck_short_circuits(monkeypatch):
    _patch(monkeypatch, probe=serve.STUCK)
    results = doctor.run_checks()
    assert results[-1][0] == doctor.FAIL
    assert "not responding" in results[-1][1]


def test_vault_locked_warns(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(doctor, "status", lambda: "locked")
    results = doctor.run_checks()
    assert results[-1] == (doctor.WARN, "vault locked — run `bwise up`")


def test_vault_unauthenticated_fails(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(doctor, "status", lambda: "unauthenticated")
    results = doctor.run_checks()
    assert results[-1][0] == doctor.FAIL
    assert "bw login" in results[-1][1]

from bwise import doctor
from bwise.client import BwError


def _levels(results):
    return [level for level, _ in results]


def test_all_healthy(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda p: "/usr/bin/bw")
    monkeypatch.setattr(doctor, "status", lambda: "unlocked")
    results = doctor.run_checks()
    assert _levels(results) == [doctor.OK, doctor.OK, doctor.OK, doctor.OK]


def test_bw_cli_missing(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda p: None)
    monkeypatch.setattr(doctor, "status", lambda: "unlocked")
    results = doctor.run_checks()
    assert results[1] == (doctor.FAIL, "bw CLI not found — install the Bitwarden CLI")


def test_daemon_unreachable_short_circuits(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda p: "/usr/bin/bw")

    def boom():
        raise BwError("down")

    monkeypatch.setattr(doctor, "status", boom)
    results = doctor.run_checks()
    assert _levels(results) == [doctor.OK, doctor.OK, doctor.FAIL]
    assert "unreachable" in results[-1][1]


def test_vault_locked_warns(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda p: "/usr/bin/bw")
    monkeypatch.setattr(doctor, "status", lambda: "locked")
    results = doctor.run_checks()
    assert results[-1] == (doctor.WARN, "vault locked — run `bwise up`")


def test_vault_unauthenticated_fails(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda p: "/usr/bin/bw")
    monkeypatch.setattr(doctor, "status", lambda: "unauthenticated")
    results = doctor.run_checks()
    assert results[-1][0] == doctor.FAIL
    assert "bw login" in results[-1][1]

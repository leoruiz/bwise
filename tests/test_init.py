from importlib.metadata import PackageNotFoundError

import bwise


def test_resolve_version_returns_installed():
    assert bwise._resolve_version()  # installed editable -> real version string


def test_resolve_version_falls_back_when_missing(monkeypatch):
    def boom(_name):
        raise PackageNotFoundError

    monkeypatch.setattr(bwise, "version", boom)
    assert bwise._resolve_version() == "0+unknown"

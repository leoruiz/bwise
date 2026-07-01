"""bwise — Bitwarden Wrapper Injecting Secrets Everywhere.

A thin client over the local ``bw serve`` daemon. Import the library for
programmatic access, or use the ``bwise`` CLI.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .client import (
    BASE,
    AmbiguousItemError,
    BwError,
    VaultLockedError,
    check,
    extract_token,
    get_item,
    put_item,
    request,
    status,
)


def _resolve_version() -> str:
    try:
        return version("bwise")
    except PackageNotFoundError:
        return "0+unknown"


__version__ = _resolve_version()

__all__ = [
    "BASE",
    "AmbiguousItemError",
    "BwError",
    "VaultLockedError",
    "check",
    "extract_token",
    "get_item",
    "put_item",
    "request",
    "status",
]

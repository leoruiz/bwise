"""bwise — Bitwarden Wrapper Injecting Secrets Everywhere.

A thin client over the local ``bw serve`` daemon. Import the library for
programmatic access, or use the ``bwise`` CLI.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .client import (
    BASE,
    BwError,
    VaultLockedError,
    check,
    extract_token,
    get_item,
    put_item,
    request,
    status,
)

try:
    __version__ = version("bwise")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0+unknown"

__all__ = [
    "BASE",
    "BwError",
    "VaultLockedError",
    "check",
    "extract_token",
    "get_item",
    "put_item",
    "request",
    "status",
]

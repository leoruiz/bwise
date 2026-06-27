"""bwise — Bitwarden Wrapper Injecting Secrets Everywhere.

A thin client over the local ``bw serve`` daemon. Import the library for
programmatic access, or use the ``bwise`` CLI.
"""

from __future__ import annotations

from .client import (
    BASE,
    BwError,
    check,
    extract_token,
    get_item,
    put_item,
    request,
    status,
)

__all__ = [
    "BASE",
    "BwError",
    "check",
    "extract_token",
    "get_item",
    "put_item",
    "request",
    "status",
]

__version__ = "0.1.0"

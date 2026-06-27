"""Health checks for the bw CLI, the ``bw serve`` daemon, and the vault.

Generic, machine-agnostic checks that belong in the package (as opposed to the
dotfiles ``bw-doctor``, which also checks LaunchAgents, sleepwatcher, and certs).
"""

from __future__ import annotations

import shutil

from . import __version__
from .client import BASE, BwError, status

OK, WARN, FAIL = "ok", "warn", "fail"
GLYPH = {OK: "✓", WARN: "!", FAIL: "✗"}


def run_checks() -> list[tuple[str, str]]:
    """Return ``(level, message)`` health-check lines for the bwise stack."""
    results: list[tuple[str, str]] = [(OK, f"bwise {__version__}")]
    results.append(
        (OK, "bw CLI found on PATH")
        if shutil.which("bw")
        else (FAIL, "bw CLI not found — install the Bitwarden CLI")
    )
    try:
        state = status()
    except BwError:
        results.append((FAIL, f"bw serve unreachable at {BASE} — start the daemon"))
        return results
    results.append((OK, f"bw serve reachable at {BASE}"))
    if state == "unlocked":
        results.append((OK, "vault unlocked"))
    elif state == "locked":
        results.append((WARN, "vault locked — run `bwise up`"))
    else:
        results.append((FAIL, f"vault {state} — run `bw login`"))
    return results

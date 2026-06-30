"""Health checks for the bw CLI, the ``bw serve`` daemon, and the vault.

Generic, machine-agnostic checks that belong in the package (as opposed to the
dotfiles ``bw-doctor``, which also checks LaunchAgents, sleepwatcher, and certs).
"""

from __future__ import annotations

import shutil

from . import __version__, serve
from .client import BASE, status
from .pinentry import find_pinentry

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
    pin_msg = "no pinentry — `bwise up` uses getpass; install pinentry-mac"
    results.append(
        (OK, "pinentry available for secure prompts")
        if find_pinentry()
        else (WARN, pin_msg)
    )
    state = serve.probe()
    if state == serve.DOWN:
        results.append((FAIL, f"bw serve unreachable at {BASE} — start the daemon"))
        return results
    if state == serve.STUCK:
        msg = f"bw serve at {BASE} is not responding — restart it (`bwise up` heals)"
        results.append((FAIL, msg))
        return results
    results.append((OK, f"bw serve reachable at {BASE}"))
    vault = status()
    if vault == "unlocked":
        results.append((OK, "vault unlocked"))
    elif vault == "locked":
        results.append((WARN, "vault locked — run `bwise up`"))
    else:
        results.append((FAIL, f"vault {vault} — run `bw login`"))
    return results

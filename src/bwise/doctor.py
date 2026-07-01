"""Health checks for the bw CLI, the ``bw serve`` daemon, the vault, and the
bwise launchd agents.

Generic, machine-agnostic checks that belong in the package (as opposed to the
dotfiles ``bw-doctor``, which also checks sleepwatcher).
"""

from __future__ import annotations

import shutil
import sys

from . import __version__, agents, serve
from .client import BASE, status
from .pinentry import find_pinentry

OK, WARN, FAIL = "ok", "warn", "fail"
GLYPH = {OK: "✓", WARN: "!", FAIL: "✗"}


def _agent_checks() -> list[tuple[str, str]]:
    """One line per bwise agent (macOS only); unloaded is a warning, not a failure."""
    if sys.platform != "darwin":
        return []
    lines: list[tuple[str, str]] = []
    for name, label in agents.LABELS.items():
        if agents.loaded(label):
            lines.append((OK, f"agent {label} loaded"))
        else:
            hint = f"agent {label} not loaded — `bwise agent install {name}`"
            lines.append((WARN, hint))
    return lines


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
    results.extend(_agent_checks())
    return results

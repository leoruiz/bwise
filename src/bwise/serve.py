"""Health probe and self-heal for the local ``bw serve`` daemon.

When the daemon is dead or wedged, :func:`ensure_healthy` restarts it. bwise owns
the daemon's launchd agent (:data:`bwise.agents.SERVE_LABEL`), so the restart is a
fixed ``launchctl kickstart`` — no shell, no user-supplied command.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable

from . import agents
from .client import BASE, BwError

PROBE_TIMEOUT_S = 2
RECOVER_TIMEOUT_S = 15
RECOVER_POLL_S = 0.5

HEALTHY = "healthy"
STUCK = "stuck"
DOWN = "down"


def probe(timeout: int = PROBE_TIMEOUT_S) -> str:
    """Classify the daemon: ``healthy``, ``stuck`` (errors or hangs), or ``down``."""
    req = urllib.request.Request(BASE + "/status", method="GET")  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout):  # noqa: S310
            return HEALTHY
    except urllib.error.HTTPError:
        return STUCK
    except urllib.error.URLError as exc:
        return STUCK if isinstance(exc.reason, TimeoutError) else DOWN


def restart() -> None:
    """Force-restart the bwise-managed ``bw serve`` agent; raise on failure."""
    result = agents.kickstart(agents.SERVE_LABEL, kill=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "no output"
        raise BwError(
            f"could not restart {agents.SERVE_LABEL} ({detail}); "
            "install it with `bwise agent install serve`"
        )


def ensure_healthy(report: Callable[[str], None] = lambda _message: None) -> str:
    """Probe the daemon; restart and wait for recovery if it is not healthy.

    Returns the final state, or raises :class:`BwError` if it cannot recover.
    """
    state = probe()
    if state == HEALTHY:
        return state
    report(f"bw serve is {state} — restarting")
    restart()
    deadline = time.monotonic() + RECOVER_TIMEOUT_S
    while time.monotonic() < deadline:
        if probe() == HEALTHY:
            report("bw serve recovered")
            return HEALTHY
        time.sleep(RECOVER_POLL_S)
    raise BwError("bw serve did not recover after restart")

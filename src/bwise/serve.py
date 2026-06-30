"""Health probe and self-heal for the local ``bw serve`` daemon.

bwise is a client, not the daemon's supervisor — something else (a launchd or
systemd service) starts ``bw serve``. When the daemon is dead or wedged, bwise
restarts it by running the command in ``$BWISE_SERVE_RESTART``, keeping the
machine-specific mechanism out of this package.
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from .client import BASE, BwError

RESTART_ENV = "BWISE_SERVE_RESTART"
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
    """Run ``$BWISE_SERVE_RESTART`` to restart the daemon; raise if unset or failing."""
    command = os.environ.get(RESTART_ENV)
    if not command:
        raise BwError(
            "bw serve needs a restart but no restart command is configured; "
            f"restart it yourself or set ${RESTART_ENV}"
        )
    result = subprocess.run(  # noqa: S602  (user-configured restart command)
        command, shell=True, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "no output"
        raise BwError(f"${RESTART_ENV} failed (exit {result.returncode}): {detail}")


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

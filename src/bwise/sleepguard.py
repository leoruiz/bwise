"""Lock the vault when the Mac goes to sleep (optional ``sleepguard`` extra).

Registers for the macOS "will sleep" notification and runs ``bwise lock``. Like
the menubar app, pyobjc (``AppKit``) is imported lazily so the module imports
without the extra installed; it runs as a long-lived agent.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from collections.abc import Callable
from typing import Any


def _lock(_note: Any = None) -> None:
    subprocess.run(["bwise", "lock"], check=False)


def _load_appkit() -> Any:
    return importlib.import_module("AppKit")


def main(
    *, lock: Callable[[Any], None] = _lock, load: Callable[[], Any] = _load_appkit
) -> None:
    """Watch for sleep and lock the vault; exits with a hint if the extra is absent."""
    try:
        appkit = load()
    except ImportError:
        print(
            "bwise sleep-guard needs the 'sleepguard' extra: "
            "uv tool install 'bwise[sleepguard]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    center = appkit.NSWorkspace.sharedWorkspace().notificationCenter()
    center.addObserverForName_object_queue_usingBlock_(
        appkit.NSWorkspaceWillSleepNotification, None, None, lock
    )
    appkit.NSRunLoop.currentRunLoop().run()


if __name__ == "__main__":  # pragma: no cover
    main()

"""A menubar vault indicator for bwise (optional ``menubar`` extra).

Shows the ``bw serve`` vault state (🔓/🔒) in the macOS menubar and offers
unlock / lock / sync from a click. The logic lives in :class:`VaultController`,
which is pure and testable; ``rumps`` (macOS-only) is imported lazily and wrapped
by :class:`RumpsUI`, so the module imports fine without the extra installed.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from collections.abc import Callable
from typing import Any, Protocol

TITLE = "bwise"
REFRESH_S = 15
UNLOCKED, LOCKED, UNAUTHENTICATED = 0, 1, 2
GLYPH = {UNLOCKED: "🔓", LOCKED: "🔒", UNAUTHENTICATED: "🔑"}
UNREACHABLE_GLYPH = "❓"

# argv for `bwise <cmd>`; status is quiet so only its exit code matters.
_STATUS = ["bwise", "status", "--quiet"]
_UNLOCK = ["bwise", "up"]
_LOCK = ["bwise", "lock"]
_SYNC = ["bwise", "sync"]

Runner = Callable[[list[str]], int]


class MenuUI(Protocol):
    """The menubar surface the controller drives (implemented by :class:`RumpsUI`)."""

    def set_title(self, text: str) -> None: ...


class VaultController:
    """Vault state/actions, decoupled from any UI toolkit for testability."""

    def __init__(self, ui: MenuUI, run: Runner) -> None:
        self._ui = ui
        self._run = run

    def refresh(self) -> None:
        """Poll the vault status and update the menubar glyph."""
        self._ui.set_title(GLYPH.get(self._run(_STATUS), UNREACHABLE_GLYPH))

    def unlock(self) -> None:
        self._run(_UNLOCK)
        self.refresh()

    def lock(self) -> None:
        self._run(_LOCK)
        self.refresh()

    def sync(self) -> None:
        self._run(_SYNC)
        self.refresh()


class RumpsUI:
    """Adapts a ``rumps.App`` instance to :class:`MenuUI` (app injected, not built)."""

    def __init__(self, app: Any) -> None:
        self._app = app

    def set_title(self, text: str) -> None:
        self._app.title = text


def _run_bwise(args: list[str]) -> int:
    """Run ``bwise`` and return its exit code (status codes drive the glyph)."""
    return subprocess.run(args, check=False).returncode  # noqa: S603


def _load_rumps() -> Any:
    """Import ``rumps`` lazily; only present with the ``menubar`` extra (macOS)."""
    return importlib.import_module("rumps")


def main(*, run: Runner = _run_bwise, load: Callable[[], Any] = _load_rumps) -> None:
    """Launch the menubar app; exits with a hint if the ``menubar`` extra is absent."""
    try:
        rumps = load()
    except ImportError:
        print(
            "bwise-menubar needs the 'menubar' extra: uv tool install 'bwise[menubar]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    app = rumps.App(TITLE, title=UNREACHABLE_GLYPH)
    controller = VaultController(RumpsUI(app), run)
    app.menu = [
        rumps.MenuItem("Unlock", callback=lambda _: controller.unlock()),
        rumps.MenuItem("Lock", callback=lambda _: controller.lock()),
        rumps.MenuItem("Sync", callback=lambda _: controller.sync()),
    ]
    controller.refresh()
    rumps.Timer(lambda _: controller.refresh(), REFRESH_S).start()
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()

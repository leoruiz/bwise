"""A menubar vault indicator for bwise (optional ``menubar`` extra).

Shows the ``bw serve`` vault state in the macOS menubar as a single padlock and
offers unlock / lock / sync from a click. One icon always: the *fill* tells
locked (filled) from unlocked (outline), and both are monochrome *template*
images that adapt to the menubar (white in dark mode, black in light). Only the
unusual states — not logged in, daemon unreachable — get a color so they stand
out.

The logic lives in :class:`VaultController`, which is pure and testable; ``rumps``
and the AppKit icon rendering (both macOS-only) are injected, so the module
imports fine without the extra installed.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

TITLE = "bwise"
REFRESH_S = 15
UNLOCKED, LOCKED, UNAUTHENTICATED, UNREACHABLE = 0, 1, 2, 3

# state -> (filled, tint) for the custom "b" padlock. ``filled`` picks the solid
# (locked) vs outline (unlocked) body; a ``None`` tint means a monochrome
# template icon that adapts to the menubar, while a tint name colors an unusual
# state so it stands out.
ICONS: dict[int, tuple[bool, str | None]] = {
    UNLOCKED: (False, None),
    LOCKED: (True, None),
    UNAUTHENTICATED: (False, "orange"),
    UNREACHABLE: (True, "red"),
}

# state -> the menu actions that make sense in it. Sync needs an unlocked vault
# (bw serve rejects /sync while locked), so it lives with Lock; a locked or
# logged-out vault offers only Unlock, and an unreachable daemon offers nothing.
VISIBLE_ACTIONS: dict[int, frozenset[str]] = {
    UNLOCKED: frozenset({"lock", "sync"}),
    LOCKED: frozenset({"unlock"}),
    UNAUTHENTICATED: frozenset({"unlock"}),
    UNREACHABLE: frozenset(),
}

# argv for `bwise <cmd>`; status is quiet so only its exit code matters.
_STATUS = ["bwise", "status", "--quiet"]
_UNLOCK = ["bwise", "up"]
_LOCK = ["bwise", "lock"]
_SYNC = ["bwise", "sync"]

Runner = Callable[[list[str]], int]
# state -> (icon file path, is_template): the rendered artifacts a UI consumes.
IconMap = dict[int, tuple[str, bool]]


def _state_for(code: int) -> int:
    """Map a ``bwise status`` exit code to a known state (fallback: unreachable)."""
    return code if code in ICONS else UNREACHABLE


class MenuUI(Protocol):
    """The menubar surface the controller drives (implemented by :class:`RumpsUI`)."""

    def set_state(self, state: int) -> None: ...


class VaultController:
    """Vault state/actions, decoupled from any UI toolkit for testability."""

    def __init__(self, ui: MenuUI, run: Runner) -> None:
        self._ui = ui
        self._run = run

    def refresh(self) -> None:
        """Poll the vault status and update the menubar icon."""
        self._ui.set_state(_state_for(self._run(_STATUS)))

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
    """Adapts a ``rumps.App`` to :class:`MenuUI`, swapping its icon per state.

    ``icons`` maps each state to a ``(path, is_template)`` pair; ``template`` must
    be set before ``icon`` so rumps applies the template flag when loading it.
    Once :meth:`bind_menu` registers the action items, :meth:`set_state` also hides
    the actions that don't apply to the current state.
    """

    def __init__(self, app: Any, icons: IconMap) -> None:
        self._app = app
        self._icons = icons
        self._items: dict[str, Any] = {}

    def bind_menu(self, items: dict[str, Any]) -> None:
        """Register the action menu items (keyed ``unlock``/``lock``/``sync``)."""
        self._items = items

    def set_state(self, state: int) -> None:
        path, template = self._icons.get(state) or self._icons[UNREACHABLE]
        self._app.template = template
        self._app.icon = path
        visible = VISIBLE_ACTIONS.get(state, frozenset())
        for action, item in self._items.items():
            item.hidden = action not in visible


def _run_bwise(args: list[str]) -> int:
    """Run ``bwise`` and return its exit code (status codes drive the icon)."""
    return subprocess.run(args, check=False).returncode  # noqa: S603


def _load_rumps() -> Any:
    """Import ``rumps`` lazily; only present with the ``menubar`` extra (macOS)."""
    return importlib.import_module("rumps")


def _draw_padlock(filled: bool) -> Any:  # pragma: no cover  (AppKit; macOS-only)
    """Draw the bwise "b" padlock black-on-transparent and return the NSImage.

    The shackle is always stroked; a filled body knocks the ``b`` out as a hole so
    it reads against the menubar, while an outline body draws the ``b`` solid.
    """
    appkit: Any = importlib.import_module("AppKit")
    foundation: Any = importlib.import_module("Foundation")
    make_point, make_rect = foundation.NSMakePoint, foundation.NSMakeRect

    size = 44.0
    body_w, body_h, body_y, radius = 24.0, 18.0, 5.0, 4.5
    body_x = (size - body_w) / 2
    center_x, body_top = size / 2, body_y + body_h
    shackle_r, leg_h = 6.0, 7.0

    image = appkit.NSImage.alloc().initWithSize_((size, size))
    image.lockFocus()
    appkit.NSGraphicsContext.currentContext().setShouldAntialias_(True)
    appkit.NSColor.blackColor().set()

    shackle = appkit.NSBezierPath.bezierPath()
    shackle.setLineWidth_(3.0)
    shackle.setLineCapStyle_(appkit.NSLineCapStyleRound)
    shackle.moveToPoint_(make_point(center_x - shackle_r, body_top - 1))
    shackle.lineToPoint_(make_point(center_x - shackle_r, body_top + leg_h))
    shackle.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
        make_point(center_x, body_top + leg_h), shackle_r, 180, 0, True
    )
    shackle.lineToPoint_(make_point(center_x + shackle_r, body_top - 1))
    shackle.stroke()

    body = appkit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        make_rect(body_x, body_y, body_w, body_h), radius, radius
    )
    if filled:
        body.fill()
    else:
        body.setLineWidth_(2.3)
        body.stroke()

    attrs = {
        appkit.NSFontAttributeName: appkit.NSFont.boldSystemFontOfSize_(14),
        appkit.NSForegroundColorAttributeName: appkit.NSColor.blackColor(),
    }
    glyph = foundation.NSString.stringWithString_("b")
    text_size = glyph.sizeWithAttributes_(attrs)
    point = make_point(
        body_x + (body_w - text_size.width) / 2,
        body_y + (body_h - text_size.height) / 2,
    )
    context = appkit.NSGraphicsContext.currentContext()
    if filled:
        context.setCompositingOperation_(appkit.NSCompositingOperationDestinationOut)
        glyph.drawAtPoint_withAttributes_(point, attrs)
        context.setCompositingOperation_(appkit.NSCompositingOperationSourceOver)
    else:
        glyph.drawAtPoint_withAttributes_(point, attrs)

    image.unlockFocus()
    return image


def _build_icons() -> IconMap:  # pragma: no cover  (AppKit; macOS-only)
    """Render each state's "b" padlock to a PNG and return a state -> icon map.

    Monochrome states keep the black drawing and are flagged ``template`` so macOS
    tints them to the menubar color; unusual states are recolored with their tint
    and kept non-template so the color shows through.
    """
    appkit: Any = importlib.import_module("AppKit")
    foundation: Any = importlib.import_module("Foundation")
    make_rect = foundation.NSMakeRect

    colors = {
        "orange": appkit.NSColor.systemOrangeColor,
        "red": appkit.NSColor.systemRedColor,
    }
    cache = Path(tempfile.gettempdir()) / "bwise-menubar-icons"
    cache.mkdir(exist_ok=True)
    bodies = {True: _draw_padlock(True), False: _draw_padlock(False)}

    def render(filled: bool, tint: str | None) -> tuple[str, bool]:
        base = bodies[filled]
        size = base.size()
        rect = make_rect(0, 0, size.width, size.height)
        canvas = appkit.NSImage.alloc().initWithSize_(size)
        canvas.lockFocus()
        base.drawInRect_fromRect_operation_fraction_(
            rect, make_rect(0, 0, 0, 0), appkit.NSCompositingOperationSourceOver, 1.0
        )
        if tint is not None:
            colors[tint]().set()
            appkit.NSRectFillUsingOperation(
                rect, appkit.NSCompositingOperationSourceAtop
            )
        canvas.unlockFocus()
        rep = appkit.NSBitmapImageRep.imageRepWithData_(canvas.TIFFRepresentation())
        data = rep.representationUsingType_properties_(
            appkit.NSBitmapImageFileTypePNG, {}
        )
        path = cache / f"{'filled' if filled else 'outline'}-{tint or 'template'}.png"
        data.writeToFile_atomically_(str(path), True)
        return str(path), tint is None

    return {state: render(filled, tint) for state, (filled, tint) in ICONS.items()}


def main(
    *,
    run: Runner = _run_bwise,
    load: Callable[[], Any] = _load_rumps,
    build_icons: Callable[[], IconMap] = _build_icons,
) -> None:
    """Launch the menubar app; exits with a hint if the ``menubar`` extra is absent."""
    try:
        rumps = load()
    except ImportError:
        print(
            "bwise-menubar needs the 'menubar' extra: uv tool install 'bwise[menubar]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    app = rumps.App(TITLE)
    ui = RumpsUI(app, build_icons())
    controller = VaultController(ui, run)
    items = {
        "unlock": rumps.MenuItem("Unlock", callback=lambda _: controller.unlock()),
        "lock": rumps.MenuItem("Lock", callback=lambda _: controller.lock()),
        "sync": rumps.MenuItem("Sync", callback=lambda _: controller.sync()),
    }
    ui.bind_menu(items)
    app.menu = [items["unlock"], items["lock"], items["sync"]]
    controller.refresh()
    rumps.Timer(lambda _: controller.refresh(), REFRESH_S).start()
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()

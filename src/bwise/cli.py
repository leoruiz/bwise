"""``bwise`` — Bitwarden Wrapper Injecting Secrets Everywhere.

A single-entry CLI over the local ``bw serve`` daemon: unlock once, then read
secrets into env vars, files, and other tools from every terminal.
"""

from __future__ import annotations

import json
import sys

import cyclopts
from loguru import logger

from . import doctor as doctor_mod, env as env_mod
from .client import BwError, extract_token, get_item, put_item, request, status
from .pinentry import prompt_master_password

logger.remove()
logger.add(sys.stderr, format="bwise: {message}", level="INFO")

app = cyclopts.App(name="bwise", help=__doc__)

EXIT_STATUS = {"unlocked": 0, "locked": 1, "unauthenticated": 2}


def _unlock() -> None:
    state = status()
    if state == "unauthenticated":
        raise BwError("bw is not logged in — run `bw login` first")
    if state == "unlocked":
        logger.info("already unlocked")
        return
    password = prompt_master_password()
    if not password:
        raise BwError("no master password entered")
    result = request("POST", "/unlock", {"password": password})
    if not result.get("success"):
        raise BwError(f"unlock failed: {result.get('message')}")
    request("POST", "/sync")
    logger.info("vault unlocked")


@app.command
def up() -> None:
    """Unlock the vault (prompts for the master password via pinentry)."""
    _unlock()


@app.default
def _default() -> None:
    _unlock()


@app.command
def lock() -> None:
    """Lock the vault."""
    result = request("POST", "/lock")
    logger.info(
        "vault locked"
        if result.get("success")
        else result.get("message", "lock failed")
    )


@app.command(name="status")
def status_cmd(*, quiet: bool = False) -> None:
    """Print the vault status; exit 0/1/2/3 = unlocked/locked/unauth/unreachable."""
    try:
        state = status()
    except BwError:
        state = "unreachable"
    if not quiet:
        print(state)
    raise SystemExit(EXIT_STATUS.get(state, 3))


@app.command(name="env")
def env_cmd(item: str, /) -> None:
    """Print ITEM's custom fields as `export` lines and write any @file: secrets."""
    fields = get_item(item).get("fields") or []
    if not fields:
        logger.warning(f"item {item!r} has no custom fields")

    def write_file(path: str, value: str) -> None:
        env_mod.write_secret_file(path, value)
        logger.info(f"wrote {path} (600)")

    exports = env_mod.materialize(fields, warn=logger.warning, write_file=write_file)
    if exports:
        print("\n".join(exports))


@app.command
def get(item: str, /, *, notes: bool = False) -> None:
    """Print ITEM as JSON, or just its notes field with --notes."""
    data = get_item(item)
    if notes:
        sys.stdout.write(data.get("notes") or "")
    else:
        print(json.dumps(data, indent=2))


@app.command
def token(item: str, /) -> None:
    """Print ITEM's secret: password, else first custom field, else notes."""
    print(extract_token(get_item(item)))


@app.command
def doctor() -> None:
    """Health-check the bw CLI, the bw serve daemon, and the vault."""
    results = doctor_mod.run_checks()
    for level, msg in results:
        print(f"  {doctor_mod.GLYPH[level]} {msg}")
    if any(level == doctor_mod.FAIL for level, _ in results):
        raise SystemExit(1)


@app.command(name="set-notes")
def set_notes(item: str, /) -> None:
    """Replace ITEM's notes with stdin, preserving its other fields."""
    data = get_item(item)
    data["notes"] = sys.stdin.read()
    put_item(data)


def main() -> None:
    try:
        app()
    except BwError as exc:
        print(f"bwise: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":  # pragma: no cover
    main()

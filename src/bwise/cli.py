"""``bwise`` — Bitwarden Wrapper Injecting Secrets Everywhere.

A single-entry CLI over the local ``bw serve`` daemon: unlock once, then read
secrets into env vars, files, and other tools from every terminal.
"""

from __future__ import annotations

import json
import sys
from typing import Literal

import cyclopts
from loguru import logger

from . import doctor as doctor_mod, env as env_mod
from .client import (
    AmbiguousItemError,
    BwError,
    VaultLockedError,
    check,
    extract_token,
    get_item,
    put_item,
    request,
    status,
)
from .pinentry import prompt_master_password

logger.remove()
logger.add(sys.stderr, format="bwise: {message}", level="INFO")

app = cyclopts.App(name="bwise", help=__doc__)

EXIT_STATUS = {"unlocked": 0, "locked": 1, "unauthenticated": 2}


def _describe(item: dict) -> str:
    """A human label to tell duplicate-named items apart (its login username)."""
    return (item.get("login") or {}).get("username") or "(no username)"


def _prompt_choice(count: int) -> int:
    while True:
        print(f"Pick [1-{count}]: ", end="", file=sys.stderr, flush=True)
        try:
            raw = input()
        except EOFError as exc:
            raise BwError("no selection made") from exc
        if raw.strip().isdigit() and 1 <= int(raw) <= count:
            return int(raw)
        print(f"  enter a number between 1 and {count}", file=sys.stderr)


def _pick(exc: AmbiguousItemError) -> dict:
    """Resolve an ambiguous name: prompt on a TTY, else fail with the ids."""
    candidates = exc.candidates
    if not sys.stdin.isatty():
        listing = "\n".join(f"  {c['id']}  ({_describe(c)})" for c in candidates)
        raise BwError(
            f"{len(candidates)} items named {exc.name!r}; re-run with the id:\n"
            f"{listing}"
        )
    print(f"{exc.name!r} matches {len(candidates)} items:", file=sys.stderr)
    for i, candidate in enumerate(candidates, 1):
        print(f"  {i}) {_describe(candidate)}   {candidate['id']}", file=sys.stderr)
    return candidates[_prompt_choice(len(candidates)) - 1]


def _resolve_item(name: str) -> dict:
    """Like :func:`get_item`, but interactively disambiguates duplicate names."""
    try:
        return get_item(name)
    except AmbiguousItemError as exc:
        return _pick(exc)


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
    if not result.get("success"):
        raise BwError(f"lock failed: {result.get('message')}")
    logger.info("vault locked")


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
    fields = _resolve_item(item).get("fields") or []
    if not fields:
        logger.warning(f"item {item!r} has no custom fields")

    def write_file(path: str, value: str) -> None:
        env_mod.write_secret_file(path, value)
        logger.info(f"wrote {path} (600)")

    exports = env_mod.materialize(fields, warn=logger.warning, write_file=write_file)
    if exports:
        print("\n".join(exports))


@app.command
def get(item: str, /) -> None:
    """Print ITEM as JSON."""
    print(json.dumps(_resolve_item(item), indent=2))


@app.command(name="get-notes")
def get_notes(item: str, /) -> None:
    """Print ITEM's notes field."""
    sys.stdout.write(_resolve_item(item).get("notes") or "")


@app.command
def token(item: str, /) -> None:
    """Print ITEM's secret: password, else first custom field, else notes."""
    print(extract_token(_resolve_item(item)))


@app.command(name="list")
def list_items() -> None:
    """Print the names of all vault items, one per line."""
    res = check(request("GET", "/list/object/items"))
    for item in res["data"]["data"]:
        if name := item.get("name"):
            print(name)


@app.command
def completion(shell: Literal["fish", "bash", "zsh"] = "fish") -> None:
    """Print a shell completion script for bwise (default: fish)."""
    print(app.generate_completion(prog_name="bwise", shell=shell))


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
    data = _resolve_item(item)
    data["notes"] = sys.stdin.read()
    put_item(data)


def main() -> None:
    try:
        app()
    except VaultLockedError:
        print("bwise: vault is locked — run `bwise up`", file=sys.stderr)
        sys.exit(2)
    except BwError as exc:
        print(f"bwise: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":  # pragma: no cover
    main()

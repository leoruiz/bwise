"""HTTP client for the local ``bw serve`` daemon.

Dependency-free (stdlib only) so it stays cheap to import and can be reused by
external scripts. The CLI layer (:mod:`bwise.cli`) builds on top of this.

``bw serve`` returns HTTP 400 with a JSON body when the vault is locked, which
``urllib`` raises as :class:`urllib.error.HTTPError`. :func:`request` reads that
body instead of mis-reporting the daemon as unreachable.

All functions raise :class:`BwError` on failure; callers print it with their own
prefix.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("BW_SERVE_URL", "http://localhost:8087")
TIMEOUT_S = 30


class BwError(RuntimeError):
    """A ``bw serve`` request failed (unreachable, locked, not found, ...)."""


class VaultLockedError(BwError):
    """The vault is locked; unlock before reading or writing."""


def request(
    method: str, path: str, body: dict | None = None, timeout: int = TIMEOUT_S
) -> dict:
    """Call the daemon and return parsed JSON, even on a 4xx (locked) response."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(  # noqa: S310  (BW_SERVE_URL is local http(s) config)
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  (loopback http)
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            return json.load(exc)
        except (json.JSONDecodeError, ValueError):
            raise BwError(f"bw serve returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise BwError(
            f"cannot reach bw serve at {BASE} ({exc}); is the daemon running?"
        ) from exc


def check(res: dict) -> dict:
    """Raise on a failure response; a locked vault raises :class:`VaultLockedError`."""
    if not res.get("success"):
        message = res.get("message", "request failed")
        if "lock" in message.lower():
            raise VaultLockedError("vault is locked")
        raise BwError(message)
    return res


def status() -> str:
    """Return the vault status: ``unlocked`` / ``locked`` / ``unauthenticated``."""
    return request("GET", "/status")["data"]["template"]["status"]


def get_item(name: str) -> dict:
    """Return the vault item whose name exactly matches ``name``."""
    res = check(request("GET", f"/list/object/items?search={urllib.parse.quote(name)}"))
    items = [i for i in res["data"]["data"] if i.get("name") == name]
    if not items:
        raise BwError(f"item {name!r} not found")
    return items[0]


def put_item(item: dict) -> dict:
    """Write ``item`` back to the vault, preserving its other fields."""
    return check(request("PUT", f"/object/item/{item['id']}", item))


def extract_token(item: dict) -> str:
    """Pull a secret: password field, else first custom field, else notes."""
    password = (item.get("login") or {}).get("password")
    if password:
        return password
    for field in item.get("fields") or []:
        if field.get("value"):
            return field["value"]
    notes = item.get("notes")
    if notes and notes.strip():
        return notes.strip()
    raise BwError("no token found in item (checked password, custom fields, notes)")

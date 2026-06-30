"""Secure master-password prompt.

Prefers a ``pinentry`` program (keylogger-resistant, never echoes), falling back
to :func:`getpass.getpass` when none is available. The password is returned to the
caller, which sends it in the request *body* — never argv, env, or disk.
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess

# In preference order; override with $BWISE_PINENTRY.
_CANDIDATES = ("pinentry-mac", "pinentry")
_ASSUAN_PERCENT = 0x25  # '%' introduces a %XX escape


def _unquote_assuan(text: str) -> str:
    """Decode an Assuan ``%XX``-escaped data line from pinentry."""
    raw = text.encode()
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == _ASSUAN_PERCENT and i + 2 < len(raw):
            out.append(int(raw[i + 1 : i + 3], 16))
            i += 3
        else:
            out.append(raw[i])
            i += 1
    return out.decode(errors="replace")


def find_pinentry() -> str | None:
    """Return the pinentry program to use, or ``None`` if none is installed."""
    override = os.environ.get("BWISE_PINENTRY")
    if override:
        return override if shutil.which(override) else None
    for candidate in _CANDIDATES:
        if shutil.which(candidate):
            return candidate
    return None


def _pinentry_prompt(program: str) -> str | None:
    commands = (
        "SETTITLE Bitwarden\n"
        "SETPROMPT Master password:\n"
        "SETDESC Unlock the Bitwarden vault (bw serve).\n"
        "GETPIN\nBYE\n"
    )
    proc = subprocess.run(
        [program],
        input=commands,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("D "):
            return _unquote_assuan(line[2:])
        if line.startswith("ERR"):
            return None
    return None


def prompt_master_password() -> str | None:
    """Prompt for the master password; return ``None`` if cancelled/empty."""
    program = find_pinentry()
    if program:
        return _pinentry_prompt(program)
    return getpass.getpass("Bitwarden master password: ") or None

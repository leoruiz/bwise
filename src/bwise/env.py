"""Materialize a vault item's custom fields as shell exports and/or files.

Each custom field acts on its *name* (the value is always opaque, never parsed):

    NAME            valid env identifier  ->  `export NAME=<value>`
    @file:PATH      file directive        ->  write <value> to PATH, chmod 600
    (anything else)                       ->  warning, skipped

The core :func:`materialize` takes ``warn`` and ``write_file`` callables so it is
pure and testable; the CLI injects real implementations.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable

ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FILE_PREFIX = "@file:"
PLACEHOLDER = "#REPLACEME#"
LINKED_FIELD_TYPE = 3


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def write_secret_file(path: str, value: str) -> None:
    """Write ``value`` to ``path`` with mode 600, refusing to follow a symlink."""
    path = os.path.expanduser(os.path.expandvars(path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(value)
    os.chmod(path, 0o600)


def materialize(
    fields: list[dict],
    *,
    warn: Callable[[str], None],
    write_file: Callable[[str, str], None],
) -> list[str]:
    """Return ``export`` lines for env-name fields; apply ``@file:`` side effects."""
    exports: list[str] = []
    for field in fields:
        name = field.get("name") or ""
        value = field.get("value") or ""

        if value == PLACEHOLDER:
            warn(f"field {name!r} is still a placeholder ({PLACEHOLDER}) — fill it in the vault")

        if field.get("type") == LINKED_FIELD_TYPE:
            warn(f"skipping linked field {name!r} (no literal value)")
        elif name.startswith(FILE_PREFIX):
            path = name[len(FILE_PREFIX):].strip()
            if path:
                write_file(path, value)
            else:
                warn("skipping @file: field with empty path")
        elif ENV_NAME.match(name):
            exports.append(f"export {name}={shell_quote(value)}")
        else:
            warn(f"skipping field with non-identifier name {name!r}")
    return exports

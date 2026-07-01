"""Manage bwise's own launchd agents (macOS): the ``bw serve`` daemon, periodic
sync, and the menubar indicator.

bwise generates each agent's plist from resolved config (the port comes from
``BW_SERVE_URL``; program paths are resolved on ``PATH``), so there is nothing
machine-specific to hand-write. All ``launchctl`` calls go through an injected
runner, keeping the module testable.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .client import BASE, BwError

LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
SYNC_INTERVAL_S = 900
SERVE_LABEL = "com.bwise.serve"

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class Agent:
    """A launchd agent bwise manages, plus how it maps to a plist."""

    name: str
    label: str
    program: list[str]
    keep_alive: bool = False
    start_interval: int | None = None
    environment: dict[str, str] = field(default_factory=dict)
    reload_safe: bool = True

    def plist(self) -> dict:
        data: dict = {
            "Label": self.label,
            "ProgramArguments": list(self.program),
            "RunAtLoad": True,
        }
        if self.keep_alive:
            data["KeepAlive"] = True
        if self.start_interval is not None:
            data["StartInterval"] = self.start_interval
        if self.environment:
            data["EnvironmentVariables"] = dict(self.environment)
        return data

    def plist_path(self, agents_dir: Path = LAUNCH_AGENTS) -> Path:
        return agents_dir / f"{self.label}.plist"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _which(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise BwError(f"{name!r} is not on PATH — install it first")
    return path


def _menubar_path_env() -> str:
    return os.pathsep.join(
        [str(Path.home() / ".local" / "bin"), "/opt/homebrew/bin", "/usr/bin", "/bin"]
    )


def _serve_agent() -> Agent:
    parsed = urlparse(BASE)
    host, port = parsed.hostname or "localhost", parsed.port or 8087
    return Agent(
        "serve",
        SERVE_LABEL,
        [_which("bw"), "serve", "--hostname", host, "--port", str(port)],
        keep_alive=True,
        reload_safe=False,  # restarting bw serve re-locks the vault
    )


def _sync_agent() -> Agent:
    return Agent(
        "sync",
        "com.bwise.sync",
        [_which("bwise"), "sync"],
        start_interval=SYNC_INTERVAL_S,
    )


def _menubar_agent() -> Agent:
    return Agent(
        "menubar",
        "com.bwise.menubar",
        [_which("bwise-menubar")],
        keep_alive=True,
        environment={"PATH": _menubar_path_env()},
    )


BUILDERS: dict[str, Callable[[], Agent]] = {
    "serve": _serve_agent,
    "sync": _sync_agent,
    "menubar": _menubar_agent,
}
NAMES = tuple(BUILDERS)


def build(name: str) -> Agent:
    """Resolve one agent by name, raising on an unknown name."""
    try:
        return BUILDERS[name]()
    except KeyError:
        raise BwError(
            f"unknown agent {name!r}; choose from {', '.join(NAMES)}"
        ) from None


def kickstart(
    label: str, *, kill: bool = False, run: Runner = _run
) -> subprocess.CompletedProcess[str]:
    """Start (or, with ``kill``, force-restart) a launchd label via a fixed argv."""
    args = ["launchctl", "kickstart"]
    if kill:
        args.append("-k")
    args.append(f"{_domain()}/{label}")
    return run(args)


def is_loaded(agent: Agent, *, run: Runner = _run) -> bool:
    return run(["launchctl", "print", f"{_domain()}/{agent.label}"]).returncode == 0


def install(
    agent: Agent, *, agents_dir: Path = LAUNCH_AGENTS, run: Runner = _run
) -> str:
    """Write the agent's plist and (re)load it; return a short status word.

    A non-``reload_safe`` agent (``bw serve``) that is already loaded is left
    running so the vault stays unlocked.
    """
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agent.plist_path(agents_dir)
    path.write_bytes(plistlib.dumps(agent.plist()))
    if not agent.reload_safe and is_loaded(agent, run=run):
        return "kept running"
    run(["launchctl", "bootout", f"{_domain()}/{agent.label}"])
    result = run(["launchctl", "bootstrap", _domain(), str(path)])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "no output"
        raise BwError(f"bootstrap {agent.label} failed: {detail}")
    kickstart(agent.label, run=run)
    return "loaded"


def uninstall(
    agent: Agent, *, agents_dir: Path = LAUNCH_AGENTS, run: Runner = _run
) -> str:
    """Bootout the agent and remove its plist; return a short status word."""
    run(["launchctl", "bootout", f"{_domain()}/{agent.label}"])
    path = agent.plist_path(agents_dir)
    if path.exists():
        path.unlink()
        return "removed"
    return "not installed"

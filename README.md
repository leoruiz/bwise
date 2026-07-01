# bwise

**B**it**w**arden **W**rapper **I**njecting **S**ecrets **E**verywhere.

A thin client over the local [`bw serve`](https://bitwarden.com/help/cli/#serve)
daemon. Unlock your vault **once**, then read secrets into environment variables,
files, and other tools from **every** terminal and project — no master password
re-prompting, no session tokens to juggle.

> **Unofficial.** Not affiliated with or endorsed by Bitwarden. "Bitwarden" is a
> trademark of Bitwarden, Inc. This project just wraps the official `bw` CLI.

## Why

`bw serve` exposes the unlocked vault over a loopback REST API. `bwise` is a small
ergonomic layer on top:

- **Unlock once** — `bwise up` prompts via `pinentry` (keylogger-resistant) and
  hands the password straight to the daemon; nothing is written to disk or argv.
- **Secrets everywhere** — any shell can `bwise env <item>` to export fields, or
  `bwise get <item>` to read raw JSON. Pairs naturally with [direnv](https://direnv.net/).
- **One state** — the daemon holds the unlocked vault, so there are no per-shell
  session tokens to export or expire.

## Install

```sh
brew install leoruiz/bwise/bwise          # once tapped (see below)
# or with uv:
uv tool install git+https://github.com/leoruiz/bwise
# or, for local development:
uv tool install --editable .
```

To install via Homebrew, tap this repo first (it isn't named `homebrew-bwise`,
so pass the URL explicitly):

```sh
brew tap leoruiz/bwise https://github.com/leoruiz/bwise
brew install bwise
```

The Homebrew formula pulls in `pinentry-mac` automatically. With the other
install methods, install a pinentry program yourself (macOS: `brew install
pinentry-mac`) — otherwise `bwise up` falls back to a plain `getpass` prompt.

Requires the official [`bw` CLI](https://bitwarden.com/help/cli/) running in serve
mode (e.g. `bw serve --port 8087`).

## Usage

```sh
bwise up                 # unlock (bare `bwise` also unlocks)
bwise lock
bwise sync               # sync the vault with the Bitwarden server
bwise status [--quiet]   # exit 0/1/2/3 = unlocked/locked/unauthenticated/unreachable
bwise get  <item>        # raw item JSON
bwise get-notes <item>   # just the notes field
bwise token <item>       # the item's secret (password / field / notes)
bwise env  <item>        # `export` lines + @file: secrets
bwise list [TERM] [--type T] [--ids]   # item names; TERM searches, --type filters, --ids shows ids

# Item commands accept --type to assert/guard the item's type, e.g.
bwise get-notes ylab/api --type note   # errors unless ylab/api is a secure note
bwise doctor             # health-check the bw CLI, daemon, vault, and agents
bwise completion [fish]  # print a shell completion script
bwise set-notes <item>   # replace notes from stdin

# macOS: manage bwise's own launchd agents (bw serve, sync, menubar, sleep-lock)
bwise agent install [serve|sync|menubar|sleepguard|all]
bwise agent status [name|all]
bwise agent uninstall [name|all]
```

### Running at login (macOS)

On macOS, bwise can manage its own launchd agents — no hand-written plists. It
generates each from resolved config (the port from `BW_SERVE_URL`, program paths
from `PATH`) and loads them via `launchctl`:

```sh
uv tool install 'bwise[menubar,sleepguard]'   # extras for the GUI/sleep agents
bwise agent install --all
```

| Agent | Role |
|-------|------|
| `com.bwise.serve` | the `bw serve` daemon (kept running when already up) |
| `com.bwise.sync` | `bwise sync` every 15 min |
| `com.bwise.menubar` | the menubar indicator (needs the `menubar` extra) |
| `com.bwise.sleeplock` | `bwise sleep-guard` — lock on sleep (needs the `sleepguard` extra) |

`bwise doctor` reports whether each agent is loaded, and `bwise up` self-heals a
dead or stuck `bw serve` by restarting its agent.

### Menubar indicator (macOS)

An optional menubar app shows the vault state (🔓 unlocked / 🔒 locked) and
offers unlock / lock / sync from a click. It needs the `menubar` extra (macOS
only; pulls in `rumps`/PyObjC):

```sh
uv tool install 'bwise[menubar]'
bwise-menubar                 # runs the status-bar app in the foreground
```

To run it at login, use `bwise agent install menubar` (see [Running at login](#running-at-login-macos)),
or install the [`contrib/com.example.bwise-menubar.plist`](contrib/com.example.bwise-menubar.plist)
example LaunchAgent by hand:

```sh
cp contrib/com.example.bwise-menubar.plist \
  ~/Library/LaunchAgents/com.example.bwise-menubar.plist
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.example.bwise-menubar.plist
```

### `bwise env` field convention

Each custom field acts on its **name** (the value is always opaque):

| Field name        | Effect                                         |
|-------------------|------------------------------------------------|
| `MY_VAR`          | prints `export MY_VAR='<value>'`               |
| `@file:~/path`    | writes `<value>` to the file, `chmod 600`      |
| anything else     | warning on stderr, skipped                     |

```sh
eval "$(bwise env my-project)"      # load secrets into the current shell
```

With direnv:

```sh
# .envrc
eval "$(bwise env my-project)"
```

### Library

```python
import bwise

item = bwise.get_item("my-project")
token = bwise.extract_token(item)
```

## Configuration

| Variable           | Default                  | Purpose                          |
|--------------------|--------------------------|----------------------------------|
| `BW_SERVE_URL`     | `http://localhost:8087`  | daemon base URL                  |
| `BWISE_PINENTRY`   | auto (`pinentry-mac`…)   | pinentry program for `bwise up`  |
| `BWISE_SERVE_RESTART` | _(unset)_             | command to restart a dead/stuck `bw serve` |

When set, `BWISE_SERVE_RESTART` lets `bwise up` self-heal: if the daemon is
unreachable or wedged (e.g. returning HTTP 500), bwise runs this command and
waits for it to come back before unlocking. bwise doesn't own the daemon's
lifecycle, so the restart mechanism is left to you — e.g. a `launchctl kickstart
-k` of your `bw serve` service.

## Security model

- `bw serve` should be bound to **loopback only** with origin protection on.
- It has **no API auth**: while unlocked, *any* local process can read the vault.
  On a single-user machine this is an accepted trade-off — mitigate by locking
  aggressively (e.g. `bwise lock` on sleep/wake).
- The master password is sent only in the request body to `/unlock`; it is never
  placed in argv, environment, or on disk.
- `@file:` writes use `O_NOFOLLOW` to refuse following a pre-planted symlink.

## License

MIT — see [LICENSE](LICENSE).

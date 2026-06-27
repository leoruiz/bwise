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
uv tool install git+https://github.com/leoruiz/bwise
# or, for local development:
uv tool install --editable .
```

Requires the official [`bw` CLI](https://bitwarden.com/help/cli/) running in serve
mode (e.g. `bw serve --port 8087`).

## Usage

```sh
bwise up                 # unlock (bare `bwise` also unlocks)
bwise lock
bwise status [--quiet]   # exit 0/1/2/3 = unlocked/locked/unauthenticated/unreachable
bwise get  <item>        # raw item JSON
bwise get-notes <item>   # just the notes field
bwise token <item>       # the item's secret (password / field / notes)
bwise env  <item>        # `export` lines + @file: secrets
bwise list               # names of all vault items (one per line)
bwise doctor             # health-check the bw CLI, daemon, and vault
bwise completion [fish]  # print a shell completion script
bwise set-notes <item>   # replace notes from stdin
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

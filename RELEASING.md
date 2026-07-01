# Releasing bwise

bwise ships two ways: as a Python package (`uv tool install`) and as a Homebrew
formula in this repo's self-tap. A release is a git tag plus a matching GitHub
release; the Homebrew formula is then pointed at that tag's source tarball.

CI (`.github/workflows/ci.yml`) only runs `poe test` on pushes and PRs — there is
no release automation, so the steps below are manual.

## Cutting a release

1. **Bump the version** in `pyproject.toml`, then refresh the lockfile so
   `uv.lock` records the new version:

   ```sh
   uv lock
   poe test          # lint, typecheck, deptry, audit, 100% coverage gate
   git commit -am "Bump version to X.Y.Z"
   ```

   Use semver: new backward-compatible features are a minor bump, fixes a patch.

2. **Tag and push:**

   ```sh
   git push origin main
   git tag -a vX.Y.Z -m "bwise X.Y.Z"
   git push origin vX.Y.Z
   ```

3. **Create the GitHub release** for the tag (this is what the formula's `url`
   points at — GitHub auto-generates the `.tar.gz` from the tag):

   ```sh
   gh release create vX.Y.Z --title vX.Y.Z --notes "..."
   ```

4. **Update the Homebrew formula** (`HomebrewFormula/bwise.rb`): bump `url` to the
   new tag and set `sha256` to the tarball's checksum:

   ```sh
   curl -sL https://github.com/leoruiz/bwise/archive/refs/tags/vX.Y.Z.tar.gz \
     | shasum -a 256
   ```

   When runtime dependencies change, regenerate the `resource` stanzas with
   `brew update-python-resources ./HomebrewFormula/bwise.rb` (or bump them by
   hand from PyPI). Commit and push.

5. **Verify the tap installs** end to end:

   ```sh
   brew tap leoruiz/bwise https://github.com/leoruiz/bwise
   brew install leoruiz/bwise/bwise
   bwise --help
   ```

## How the Homebrew formula builds (and future options)

bwise uses the `uv_build` backend (`pyproject.toml`). Homebrew's stock
`virtualenv_install_with_resources` builds everything from source with pip, which
can't compile `uv_build` in an isolated environment. The formula therefore builds
bwise's (pure-Python) wheel with `uv` at install time and installs that:

- `depends_on "uv" => :build`
- `uv build --wheel`, then `uv pip install --no-deps --offline` the wheel into the
  virtualenv (Homebrew's pip helper forces `--no-binary`, which rejects wheels).

This is **option A: build from source at install time**. Two alternatives, if the
release process ever outgrows it:

- **B — attach a prebuilt wheel to the GitHub release.** Point the formula at the
  `.whl` instead of the source tarball; no `uv`/build step on the user's machine.
  Cost: build and upload the wheel on every release.
- **C — publish to PyPI.** Cleanest provenance, and also unlocks
  `uv tool install bwise` / `pipx install bwise` from PyPI. The formula can then
  install from the published artifact. Cost: a PyPI publish step per release.

Option A is intentionally self-contained and needs no extra publishing; because
bwise is pure Python the install-time wheel build is effectively instant.

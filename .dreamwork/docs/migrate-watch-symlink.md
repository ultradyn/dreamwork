# Migration — `watch.py` → symlink to `deprecated/watch.py` (#368, first increment)

> **Status: procedure only. The symlink is NOT created here.** #425 built the
> safety net (the deploy recipe and `dev/deploy_state.py` resolve a symlinked
> `watch.py` and prove the snapshot is the server before touching the live
> process). This document is the order of operations and the checks that must
> pass at each step, so the first increment of #368 can flip the link without
> taking his dashboard down.

## Why a symlink, and why this is deferred to #368

His words (2026-07-28): *the files on disk might be updated while agents are
running, so they need to be able to continue running OR be explicitly told they
must reload.* When `watch.py` is eventually split into a package (#368), a
symlink at the old path lets a client that was started against the monolith
keep running until it is deliberately restarted. **#368 has not started** — it
is behind an open question (`#263` Q3) — so flipping the link today buys
nothing (there is no split to be compatible with) and is not done here.

## The measured blocker #425 closed (verify it stays closed)

Once `watch.py` is a symlink, `git show HEAD:watch.py` emits the link's
**target path** as its content — the 19 bytes `deprecated/watch.py` — because
git stores a symlink as a blob whose content is the target. Two things followed
under the old deploy recipe, and both bit:

1. `ast.parse("deprecated/watch.py")` **succeeds** — it parses as
   `deprecated / watch.py` (a division expression). The syntax guard that
   existed to catch a broken snapshot passed the garbage.
2. The recipe killed the working server with `pkill` **before** it noticed, so
   the garbage snapshot started, died on import, and the final `curl` was the
   first thing to notice — by which time his dashboard was already dark.

#425's fix (committed): the deploy recipe and `dev/deploy_state.py` share one
resolver (`resolve_blob`) that follows the link to the real module, and one
guard (`assert_is_server`) that asserts the snapshot **defines the server**
(top-level `def main` and `GENERATION =`) rather than merely that it parses.
The guard runs **before** `pkill`. A path string, an empty file, and a
truncated blob are all rejected by name; the dashboard stays up.

## Order of operations — #368's first increment

Each step has a check that must pass before moving on. Run them on a **scratch
checkout first**, never against the live tree on `:35110` and never binding a
port in `39880–39899` (the guard range). The live dashboard is his; it was down
for two hours on 2026-07-28 already.

1. **Move the monolith, create the link, commit.**
   ```
   mkdir -p deprecated
   git mv watch.py deprecated/watch.py
   ln -s deprecated/watch.py watch.py
   git add watch.py deprecated/watch.py
   git commit -m 'refactor(#368): symlink watch.py -> deprecated/watch.py'
   ```
   *Check.* `git ls-tree HEAD watch.py` shows mode `120000`; `git ls-tree HEAD
   deprecated/watch.py` shows mode `100644`. `git status --porcelain` is clean.

2. **`python3 watch.py` behaves identically through the link.**
   Python follows the symlink at exec time, so the interpreter runs
   `deprecated/watch.py`. *Check.* `python3 watch.py --help` matches the
   pre-move output, and `python3 watch.py --target <scratch> --port <outside
   39880–39899>` serves a health-responding page. Start your own server on a
   port outside the guard range and stop it; do not touch `:35110`.

3. **`__file__`-relative path resolution still resolves.** This is the classic
   symlink trap, and `watch.py` is already on the safe side of it: it computes
   its own source with `os.path.abspath(__file__)` (line ~7524), **not**
   `realpath`. `abspath` keeps the symlink's directory as the directory, so
   `dirname(__file__)` is the repo root (where the dashboard's siblings live),
   while `open(__file__)` follows the link and reads the real module. *Check.*
   `python3 -c "import os; print(os.path.dirname(os.path.abspath('watch.py')))"`
   from the repo root prints the repo root, not `deprecated/`. **Regression
   guard:** if any path is ever switched to `os.path.realpath(__file__)`, the
   trap opens (dirname becomes `deprecated/`) and this check goes red. Keep
   `abspath`.

4. **`--target` and the port file still resolve.** Both are independent of
   `__file__`: `--target` is passed on the command line and the port file is
   `.dreamwork/watch-port` under the target. *Check.* a scratch server started
   through the link serves the scratch target's data, and `/data.json`'s
   `target` field is the scratch path.

5. **`just test` still discovers its guards.** The guards start
   `python3 watch.py` through the link; Python follows it, so they are
   unaffected. *Check.* `just test` green **on a scratch checkout** (the guard
   recipe binds `39890–39899`; never run it while the coordinator's suite holds
   that range). Confirm the `serving` guard in particular still classifies
   correctly — see the known interaction below.

6. **An already-running server survives the swap.** A running process has
   already imported its module; the link flip is a tree commit and does not
   touch the running code or the deployed snapshot file
   (`~/.cache/dreamwork/deployed/<name>-watch.py`). The next tick re-reads the
   **target's** files (the project being watched), not `watch.py` itself.
   *Check.* start a server on a scratch checkout, perform steps 1–2 against a
   *different* clone, and confirm the running server's next tick still answers
   `/` and `/mtime`. The swap is non-disruptive to a running server; the next
   **deploy** (not tick) is where the resolver matters.

7. **`just deploy` resolves the link.** *Check.* `just deploy` on the scratch
   checkout reports `deployed HEAD (<sha>) on :<port>`, the deployed snapshot
   file is the real module (its byte count matches
   `git cat-file blob $(git ls-tree HEAD deprecated/watch.py | awk '{print $3}')`
   — not 19), and `python3 dev/deploy_state.py` reports `current`.

## Known interaction #368 must close (out of scope for #425)

`watch.py`'s own `serving_report` (the `/serving` family, line ~7587) compares
the process's `SELF_SRC` — its own bytes, read at import via
`open(os.path.abspath(__file__))`, which **follows** the symlink to the real
module — against `git show HEAD:watch.py`. After the flip, `HEAD:watch.py` is
the 19-byte link string, so it no longer matches `SELF_SRC`; the walk then
matches an **older** pre-flip revision and `serving_report` reads **BEHIND**
for this skill's own tree, even though the process is running the current real
module. `watch.py` is owned by #368, not #425, so this is not fixed here. The
first #368 increment must either resolve the link in `serving_report` (the same
`resolve_blob` mechanism) or explicitly accept the false-BEHIND for the
self-hosted tree. The check at step 5 surfaces it.

`deployed.py` (root) has the same shape: it compares the snapshot against
`git show HEAD:watch.py` per revision. It will read the snapshot as **BEHIND**
or **UNTRACKED** after the flip for the same reason. Like `serving_report`, it
is outside #425's listed scope; flag it for #368.

## What this increment deliberately did NOT do

- **`watch.py` is not a symlink** and **`deprecated/` does not exist.** #425 is
  the safety net, not the jump. `git status --porcelain` proves it.
- `watch.py`, `test_watch.py`, `lint.py`, `file-formats.md`, and the ledger
  files were not edited. `deployed.py` (root) was not edited either; its
  sibling bug is documented above for #368.

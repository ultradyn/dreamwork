# Brief — #425: make the tooling symlink-safe *before* `watch.py` becomes a symlink

Repo: `ud-dreamwork`. Worktree: **`.worktrees/425`**, branch **`wt/425`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

## What he asked for, and why this increment is *not* the symlink

His words, direct, 2026-07-28 17:38:

> *"when we migrate watch.py to something more maintanable, we should keep a copy of the monolithic
> script in like `deprecated/watch.py` but symlink `watch.py` in the main dir so clients won't break if
> the files on disk are updated before the new skill is rerun and things are properly updated. In
> general this should kind of be a principle of ours: the files on disk might be updated while agents
> are running, so they need to be able to continue running OR be explicitly told ... that they must
> reload."*

**Do not create the symlink in this increment.** Note his opening clause — *"when we migrate"*. The
migration is `#368` and it has not started; it is behind an open question on his desk (`#263` Q3, does
`#368` land before lane E). Flipping `watch.py` to a symlink today buys nothing, because there is no
split to be compatible with — and it costs something real, measured below.

**This increment makes the mechanism safe so that `#368`'s first increment can flip it.** That is the
whole job: tooling that survives `watch.py` being a symlink, proven, plus the procedure written down.

## The measured blocker — verify it yourself first, then fix it

`just deploy` (justfile, recipe `deploy`) does:

```
git show {{rev}}:watch.py > "$snap"
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$snap"
pkill -f "$(basename "$snap")"
nohup python3 "$snap" --target "$PWD" --dev &
... curl health check ...
```

**Git stores a symlink as a blob whose content is the target path.** So once `watch.py` is a symlink,
`git show HEAD:watch.py` emits the 19-byte string `deprecated/watch.py` — and
**`ast.parse("deprecated/watch.py")` succeeds**, because it is a valid expression (`deprecated` divided
by `watch.py`). The syntax check that exists to catch a broken snapshot passes.

The order is what makes it bite: **`pkill` kills the working server first.** Then the garbage snapshot
passes `ast.parse`, starts, dies on import, and only the final `curl` notices. The recipe honestly
reports *"deploy failed"* — with **the human's dashboard already down and staying down.**

**Reproduce both halves before you fix anything** (a scratch `git init` in `/tmp` is enough) and put the
observed outputs in your report. If either half does not reproduce, **stop and say so** — the fix below
is built on them.

## What to build

1. **`deploy` resolves the link.** Snapshot the *real module*, not the link. Decide how: resolving via
   `git ls-files -s` mode `120000` then re-`git show`-ing the target is one way; `git cat-file --follow-symlinks`
   is another and may be cleaner — **check whether it exists in this git version rather than assuming.**
   State which you chose and why.
2. **The `ast.parse` guard asserts the snapshot is the server**, not merely that it parses. A syntax
   check that passes on a path string is measuring the wrong property. Something like: the module
   parses **and** defines the expected top-level entry point (`main`, and whatever the server class /
   `GENERATION` constant is — read `watch.py` and pick markers that cannot be present by accident in a
   path string). Keep it cheap; it runs on every deploy.
3. **`dev/deploy_state.py` must keep working through a symlink.** It reads `HEAD:watch.py` and compares
   to the deployed snapshot; with a symlink in the tree those become different things by construction.
   Fix it the same way as `deploy`, so the two agree.
4. **Write the migration procedure** in `.dreamwork/docs/` (a new short doc, or the right existing one —
   check `doc-map.md` and add a row if you create a file, or `lint` will fail you). It states the order
   of operations for `#368`'s first increment and **the checks that must pass at each step**, from the
   `#425` ledger entry: `python3 watch.py` behaves identically through the link; the port file,
   `--target` and `__file__`-relative path resolution still resolve (a monolith computing paths from
   `__file__` may see the **target's** directory, which is the classic symlink trap); `just test` still
   discovers its guards; and **an already-running server survives the swap** without its next tick
   failing.

## Red-first, and this repo's reds have a documented habit of passing

**A new check is not verification until it has been red.** For each of items 1–3: build a scratch
checkout where `watch.py` **is** a symlink, run the tooling, and watch it fail *before* your fix. Then
fix and watch it pass. **Name in your report the exact production line whose removal makes each test
fail again.** If you cannot name one, there isn't one.

**A green red-run is a finding, never a relief.** If you make `watch.py` a symlink and the unfixed
`deploy` appears to work, do not conclude it is fine — find out why your injection did not reach the
code. That has happened twice in this repo in one day, both times on the single decision the test was
named for.

**The negative direction matters here**: after your fix, a snapshot that is genuinely broken (truncated,
empty, a path string) must **still** be rejected. A guard widened until it accepts everything has
removed a check rather than improved it.

## Done means all of these

1. **Both halves of the blocker reproduced and quoted** (git stores the target as content;
   `ast.parse` accepts it), before the fix.
2. **`just deploy` works with `watch.py` as a symlink**, proven in a scratch checkout — not on this
   repo's real tree, and **not against the live dashboard on :35110, which is his.**
3. **The snapshot guard rejects a path string** and still accepts the real module. Both directions
   tested by name.
4. **`dev/deploy_state.py` agrees with `deploy`** through a symlink, and still reports `current` /
   `STALE SNAPSHOT` / `STALE PROCESS` correctly. Read its docstring first — it answers two separate
   questions and the second one exists because the first version answered only one and was trusted.
5. **The migration procedure documented**, with the per-step checks from item 4 above, and a `doc-map.md`
   row if you added a file.
6. **`watch.py` is NOT a symlink at the end** and `deprecated/` is not created. This increment is the
   safety net, not the jump. `git status --porcelain` proves it.
7. `python3 lint.py` clean. `python3 -m pytest -q -p no:randomly` passes for whatever test files you
   touch. **Do NOT run `just test`** — guard ports 39890–39899 are in use by the coordinator's own
   suite run; bind nothing in 39880–39899, and do not kill a process holding one.
8. **Do not restart, pkill or redeploy the live dashboard.** It is on :35110, it is his, and it was down
   for two hours today already. If you need a server, start your own on a port outside 39880–39899 and
   stop it.

## Files

Yours: `justfile` (the `deploy` recipe only), `dev/deploy_state.py`, a new doc under `.dreamwork/docs/`
plus its `doc-map.md` row, and a test file for the above.

**Not yours:** `watch.py` and `test_watch.py` (do not edit them — read them to pick your guard markers),
`lint.py`, `file-formats.md`, `.dreamwork/tasks.md` / `questions.md` (coordinator is the only writer —
report exact lines instead), and anything under `.dreamwork/review/`.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'fix(#425): …'` — **`--only`, never
  `git add -A`**. Note `--only <directory>` does not pick up untracked files inside it and does not say
  so, so a new file needs the `git add` first.
- **Commit before you finish.** A lane today did 24 turns of correct work and exited without
  committing; `git log` showed nothing and it was recovered by hand from the dirty worktree.
- **Push back with reasons if any of this is wrong.** Many lanes today have refuted something their
  brief asserted and every one was right to. In particular: **if you think `deploy` should stop
  snapshotting a single file entirely** — after `#368` the dashboard is a package and `deploy` will have
  to copy a tree — say so with your reasoning. That may be the better fix and this brief is choosing the
  smaller one deliberately, so argue if you disagree.

## Report

Say: both reproductions with their literal output; which git mechanism you used to resolve the link and
why; the markers your snapshot guard asserts and why a path string cannot satisfy them; the exact
production line whose removal fails each new test; your negative tests by name; confirmation that
`watch.py` is not a symlink and `deprecated/` does not exist at the end; and confirmation you neither
ran `just test` nor touched :35110.

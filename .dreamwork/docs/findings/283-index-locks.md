# #283 — Diagnosis: recurring orphaned Git index locks and dead attribution

**Lane:** diagnosis (worktree `subagent-019fadee-267d-7053-a054-6fc94c659978`)
**Date:** 2026-07-29
**Scope:** mechanism, current state, defenses, recommended remediation. **No code
fix shipped** — the index-lock root cause is environmental (a host shell-prompt
extension + a KIO/FUSE search worker), not repo-owned tooling; the attribution
class is already defended in repo docs. Detail and the "fix only what you can
prove" rationale are below.

---

## 0. Current observed state (2026-07-29 22:53 +1000)

- **No stale `index.lock` exists** in the main checkout, the `~/src/dreamwork`
  symlink, `~/src/amaroo` (the repo named in the #283 body), or any worktree.
  The earlier witnesses (inodes `251560857` etc.) have since cleared.
- **`git-lock-watch.service` is `inactive`.** Its log's last line is
  `2026-07-29 03:18:27` (~19.5 h ago). This is the witness #283's own closing
  condition depends on, and it is dead — see §3. **The quiet window cannot be
  evaluated until it is restarted.**
- Last snapshots still name PID `1246815` (D-state, cwd
  `/run/user/1000/kio-fuse-*/filenamesearch`, `git rev-parse --is-inside-work-tree`).

## 1. Mechanism A — orphaned `.git/index.lock` (environmental, not repo code)

A holderless zero-byte `.git/index.lock` is created when a process opens it then
is **killed before its normal cleanup** (SIGTERM/SIGKILL mid-`git status`), or
when a transient writer is shorter-lived than any sampler can catch. Two
proven/circumstantial creators on this host, **neither in this repo**:

1. **`pi-powerline-footer` shell-prompt extension.** Per the `~/CLAUDE.md` system
   mitigation and the #283 body: it runs `git status --porcelain` with a
   **500 ms `proc.kill`** and **no `--no-optional-locks`**. Under load the kill
   fires mid-index-lock and orphans it. A patch to add `--no-optional-locks` was
   applied to the *installed* extension, but it only takes effect on the **next
   pi restart** — which (per the #283 body) had not happened as of the body's
   last update (pi newest instance started 2026-07-27 04:08, before the patch).
2. **KIO/Dolphin `filenamesearch` worker** (PID `1246815`). The research doc
   `.dreamwork/docs/research/git-index-lock-attribution-283.md` **falsified**
   `1246815` as the creator (it is a stuck D-state process for ~10 days; its
   `git rev-parse` command takes no index lock), leaving it as medium-confidence
   circumstantial only.

**This is not something repo-owned tooling causes or can fix.** Every read-only
`git` call in this repo's tooling already passes `--no-optional-locks`, so it
never contends for the index lock the way the prompt extension does (§4).

## 2. Mechanism B — dead attribution (whole-index commit sweeps a peer's work)

The `12f47e3` class: a plain `git commit` commits **the whole index**, not just
the paths you `git add`-ed, so a concurrently-staged file rides inside your
commit. `12f47e3` (`file(#387)`) landed `test_user_events_digest.py` inside a
ledger commit. Evidence and the corrected mechanism are in
`lessons.md:1613-1630` ("`git commit` commits the index… `git commit --only
mine` gives a one-file commit") and refined at `lessons.md:1907-1930` and
`lessons.md:2069-2074` (a commissioned review found **no instance** of a
same-file hunk sweep; the one real incident was a *plain* `git commit`, i.e.
`--only`'s absence).

**Defended in repo docs, not by a machine check.** `CLAUDE.md:104-114` and
`SKILL.md:273-284` mandate `git commit --only <paths>` (and `git add <file>`
first for new files, because `--only <dir>` silently skips untracked files).
There is no automated guard that *enforces* `--only` at commit time — the
discipline is the guard.

## 3. Mechanism C — the witness itself dies silently (the open gap)

`git-lock-watch.service` uses `Restart=on-failure`. The watcher script
(`~/.llm-general/systems/xsm/git-lock-watch.sh`) is a single `inotifywait | while
read` pipeline with **no `set -o pipefail`**: when `inotifywait` closes the pipe
the loop ends and bash exits **0**, so systemd records success and never
restarts. The research doc (§1) calls this **high confidence**. **This is why the
service is dead right now** (§0) and why #283's closing condition is currently
unmeasurable.

## 4. Existing defenses (audited)

- **`--no-optional-locks` on every read-only git call** in repo tooling:
  `watch.py:10375,10472,10548,11240,11349,12299`; `deployed.py:64`;
  `task_origins.py:93`; `dev/lane_guard.py:515,555`; `lint.py:3383`. Asserted by
  `test_watch.py:2045` (`test_every_git_call_refuses_the_index_lock`) and
  `test_deployed.py:172`. **No repo tooling takes the index lock.**
- **No `git add -A` / `git add .` in tooling** — only in comments/docs as the
  named hazard, and one explicit-path `git add` in the `provenance-evidence`
  justfile recipe (interactive, not the recurring cause).
- **`git commit --only` convention** documented (`CLAUDE.md`, `SKILL.md`).
- **Pre-merge gate** `dev/lane_guard.py:_pre_merge` (lines 567-650): asserts the
  preconditions of `git merge` — refuses on a dirty main index/worktree or on a
  lane contesting a path — and **never moves work** (no stash/reset/checkout).
  This is the structural backstop against the attribution class at merge time.

## 5. Fixes shipped

**None.** No proven gap exists in repo-owned tooling:
- index-lock orphans come from the host prompt extension / KIO worker (§1) — not
  fixable in-repo;
- attribution is already defended by docs + the pre-merge gate (§2, §4);
- the watcher exit-0 (§3) is host infrastructure outside this repo's scope
  (`~/.llm-general/systems/xsm/`), not repo-owned tooling.

Inventing a code fix for a non-code cause is explicitly out of bounds.

## 6. Recommended remediation (not done here — coordinate with the human)

1. **Restart the witness:** `systemctl --user restart git-lock-watch` so #283's
   closing condition becomes measurable again. It is dead as of this report.
2. **Make the witness survive clean exit 0:** change the unit to
   `Restart=always` (and/or `set -o pipefail` + a wrapper loop in the script).
   This closes §3 and is the one durable fix; it lives in the host system-KB,
   not this repo.
3. **Force the pi-powerline-footer patch effective:** a pi restart so the
   `--no-optional-locks` patch is the running extension. Until then, absence of
   orphans proves nothing (the #283 body's stated closing condition).
4. **Keep `git commit --only` discipline** (Mechanism B is not machine-enforced).
5. **Manual lock-clearing is operator judgement**, never automated: a zero-byte
   `index.lock` with no `lsof`/`fuser` holder and no merge/rebase/cherry-pick in
   progress is safe to remove; otherwise leave it.

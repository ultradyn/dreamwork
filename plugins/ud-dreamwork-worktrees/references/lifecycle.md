# Lifecycle — create, validate, merge, cleanup

## Preflight

1. Target is a git repo; `.gitignore` lists `.worktrees/`.
2. Co-agent: claims ledger present (empty ok).
3. Branch name free: `fix/N-slug` (no `#`).

## Create

```bash
git worktree add -b fix/N-slug .worktrees/N-slug master
# attach existing branch only when it already exists:
# git worktree add .worktrees/N-slug fix/N-slug
```

Confirm clean baseline on the expected branch.

## Validate (before merge)

- Evidence receipt present (`evidence.md`; co-agent: inbox + ack).
- Spot-check red/green or cold-read.
- Rebase onto current master inside the worktree; resolve conflicts
  deliberately (never blind `-X theirs`).

## Merge

Coordinator (or Max) on main checkout / project PR flow. Workers: **no push**
unless Max authorized.

## Cleanup (never force-blind)

**Never** first:

- `git worktree remove --force`
- `rm -rf .worktrees/<slug>`

`--force` declines to ask whether anyone is still in the tree. It does
**not** answer that question, and must not be read as answering it. The
#316 incident is what happens when it is trusted to: a live agent was
mid-edit in a worktree whose file state read as disposable, and
`--force` removed it without complaining. (The only thing that surfaced
the mistake was `git branch -d` refusing on an unmerged branch — git's
own safety, and it worked only because that agent had happened to
commit. Do not build a fix that relies on that luck.)

**Do:**

1. **Process check — first, always.** Before reading any file state, run
   the plugin's liveness check against the worktree path:
   ```
   python3 plugins/ud-dreamwork-worktrees/occupied.py .worktrees/N-slug
   ```
   (the script lives at `plugins/ud-dreamwork-worktrees/occupied.py`
   relative to this skill's checkout; resolve it through `plugin_resolver`
   when cleaning a target whose plugin is elsewhere). A worktree whose
   agent is mid-thought is byte-identical to one whose agent has gone,
   so every step below — all of which reads file state — is moot until
   this is clear. **If it names a live process, stop**: an agent is in
   there and will lose uncommitted work if you remove. Exit `0` = clear,
   `1` = process(es) found (live or stranded). It reports pid and command
   line because "something is in there" without a name sends the reader
   on a hunt, and a visible command line is no substitute — a worker's
   process is usually a shell wrapper (`zsh -c …`) whose argv never names
   the tool, which is why a grep over `ps` could not have worked. A cwd
   reading `…/N-slug (deleted)` means the directory is already gone and a
   process is stranded in it; note it, it cannot be saved.
2. `git worktree list`
3. Worktree `git status -sb`
4. Inspect **untracked and ignored** scratch (`git status --ignored`).
5. Classify artifacts:
   - **Obviously disposable** (e.g. `__pycache__`, `.pytest_cache`) → may
     remove with worktree.
   - **Non-obvious** (logs, screenshots, local DBs, half-written notes) →
     **owner/coordinator decision required**, recorded in the evidence
     receipt `cleanup decision` field or claim `notes`. Move valuable
     scratch out **before** remove.
6. If clean / disposable-only, remove worktree then merged branch:
   `git worktree remove .worktrees/N-slug`
   then `git branch -d fix/N-slug` when merged.
7. Clear claim ledger entry / status projection.

If remove refuses (dirty): stop and report — do **not** `--force` without
Max after inspect.

## Failure paths

| Situation | Action |
|-----------|--------|
| Tests red after rebase | fix or abandon with receipt |
| Null result | no merge |
| Orphan worktree | inspect; decision; then clean |
| Path conflict | reject new claim |

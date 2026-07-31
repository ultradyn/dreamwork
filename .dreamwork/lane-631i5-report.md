# Lane report — #631 increment 5: server-derived session catalogue, still dark

**Lane:** glm-631i5 · **Base:** `911b6ab7` (master, unmoved) · **Commit:** `410d5d7`
**Files:** `session_source.py`, `test_session_source.py`
**Verdict:** LANDED — dark, server-only, +21 collected tests (19 → 40).

## What changed and why

Extended `session_source.py` with the switcher catalogue (`catalogue()`,
`CatalogEntry`, `CatalogResult`, and helpers `_slug_for`, `_session_uuid`,
`_confined_to_root`, `_target_slug_dirs`). The catalogue discovers strictly-
named UUID JSONL transcripts under the target's cwd slug(s), including
`.worktrees/*` slugs (the session relocates), classifies them, and returns
mtime/size/liveness metadata. No entry carries a path.

**The confinement decision (lead finding).** Two gates, both load-bearing:

1. **No browser-supplied path.** `CatalogEntry` has no path field — the wire
   shape carries only an opaque `session_id`. A consumer that wants to open a
   source resolves the id back through `resolve()`, which does its own uuid-
   search. No request parameter is ever joined into a filesystem path.

2. **Resolve-before-confine symlink order.** `_confined_to_root` does
   `path.resolve(strict=False).relative_to(real_root)` — links are resolved
   FIRST, then the resolved location is confined. The symlinked projects root
   (§2: `projects` → `~/.claude-shared/projects`) is handled because
   `real_root` is itself resolved, so everything is in real-path space. A
   symlink whose NAME is a clean UUID but whose TARGET leaves the root (e.g.
   points at a secret file outside root) resolves outside and is dropped,
   with a count in the result detail. **The order is the bug**: confining the
   name first (the name is under root) and resolving after admits the escape.

**Adversarial name decisions** (the assertion protecting real session content):

| adversarial name | decision | why |
|---|---|---|
| `550e8400-…-446655440000-evil.jsonl` (uuid prefix + tail) | rejected | `_session_uuid` full-string regex; stem is not a clean uuid |
| `evil-550e8400-….jsonl` (head + uuid) | rejected | same — stem fails the regex |
| `550e8400-….JSONL` (wrong case ext) | rejected | `Path.suffix != '.jsonl'` |
| `not-a-uuid.jsonl` | rejected | regex fails |
| `memory` (chrome dir name) | rejected | no `.jsonl` suffix; also skipped as non-file |
| `..jsonl` (traversal-shaped) | rejected | stem `.` fails regex |
| clean-named symlink → outside root | rejected | resolve-before-confine drops it |

**Active identity.** `active = (active_id is not None and uid == active_id)`.
Newest-mtime is never promoted — the recorded `agent_session` is the only
identity. A catalogue built with two live sessions where the recorded id is the
OLDER one (by mtime) marks the older one active; the test pins this with
`os.utime` so the mtime ordering is genuine and runtime-derived.

**Empty vs unmeasured.** `CatalogResult.status` is `"ok"` (measured root,
possibly empty) or `"unmeasured"` (root missing/unreadable). The detail string
for unmeasured carries "could not be measured"; ok's does not. An empty
catalogue over an empty root and one over a root the resolver failed to measure
render differently (`#136`/`#671`).

**Liveness semantics.** `live` is a scan-time claim: `last_record_at` was
within `stale_after` of `now` when the catalogue was built. Both
`last_record_at` and `age_seconds` are carried so a consumer can re-judge as
`now` advances without rescanning — but the file may have grown since, so
`live` is a reading over a window, not a durable truth (`#765` shape one level
down).

## Red-proof — both directions

### Injection 1 (design-specified): newest-mtime promoted to active

**Sabotage:** appended `newest = max(entries, key=lambda e: e.mtime); for e:
e.active = (e is newest)` after building entries.

**Red:** `test_the_recorded_id_is_marked_active_even_when_older` reds on
`assert by_id[UUID_A].active is True` → `AssertionError: assert False is True`.
The two sessions have genuinely different mtimes (pinned via `os.utime` and
asserted at runtime: `by_id[UUID_B].mtime > by_id[UUID_A].mtime`).

### Injection 2 (design-specified): absolute path in wire catalogue

**Sabotage:** added `path: str` field to `CatalogEntry` and populated it with
`str(cand.resolve())`.

**Red:** `test_no_entry_exposes_a_path_field` reds on
`assert "path" not in names, "CatalogEntry must not carry a path"` →
`AssertionError: CatalogEntry must not carry a path`. The test also checks
`astuple` for any `Path` instance or string starting with `/`, so a path under
any field name is caught.

### Direction 2: confinement order (resolve-after, confine-name-first)

**Sabotage:** changed `_confined_to_root` from
`path.resolve(strict=False).relative_to(real_root)` to
`path.relative_to(real_root)` (no resolve).

**Red:** `test_a_clean_named_symlink_pointing_outside_root_is_dropped` reds on
`assert OTHER_ID not in ids` → the symlink escape was admitted instead of
dropped. This is the order bug the brief names — the symlink's NAME is under
root so name-confinement passes, but its TARGET is outside root so resolve-
then-confine fails.

### Direction 2: slug self-consistency false-green (closed)

Every discovery test named its fixture dir via `_slug(target)` (the production
function), so a wrong slug rule would be self-consistent between test and impl
and the test would still pass. Closed by
`test_the_slug_rule_matches_the_measured_root_independently`, which asserts the
literal measured slug (`/home/x/.llm-general/skills/ud-dreamwork` →
`-home-x--llm-general-skills-ud-dreamwork`) independently of the function.

### `redproof check` output (final)

```
history: examined 1 commit(s) since 911b6ab7a777 (master) against 1 injected
path(s); read 1 blob(s), 0 holding a recorded injection.
check: clean — 3 injection(s) registered, all restored and absent from the
working tree and from this branch's commits
```

## Verification

- **Lint:** `python3 lint.py` → clean at **5 warnings** (same as base; the
  warning set is the gitignored-ledger one that does not travel to worktrees).
- **Tests:** `python3 -m pytest test_session_source.py` → **40 passed**.
  Collected count: **19 before, 40 after** (+21).
- **Dark:** `grep -rn "catalogue\|CatalogEntry\|CatalogResult"` outside the two
  lane files returns nothing. No production import; `SessionService` calls it
  in increment 6.
- **No browser guards, no port binding, no `watch.py` touched.**

## Rebase

Master was unmoved at `911b6ab7` (my base). 0 behind, 1 ahead. No rebase needed.

## Cited issues (relied-on lines)

- **#136/#671** — "distinct nothings must not read the same": the `ok` vs
  `unmeasured` distinction and the `assert res.entries` preconditions.
- **#702** — "three classifier outcomes must stay distinguishable": the
  catalogue's status field keeps `ok`/`unmeasured` distinct, and within `ok`
  the empty case is a valid finding, not a collapse.
- **#765** — "a recorded hold keeps reading as current after its condition
  expired": `live` is documented as a scan-time reading over a window; the age
  is carried for re-judgment.
- **#613 §6** — the server-side registry confinement ruling: "paths are
  derived … the browser only ever names a session id."
- **#698** — the symlink trap: `Path.glob` / `iterdir` follows the symlinked
  base; `_confined_to_root` handles the resolve-before-confine order.

## Out of scope (named, not fixed)

- The slug rule (`/` and `.` → `-`) is measured against the real
  `~/.claude-p/projects/` but is not stated in §2 (which says only `/` → `-`).
  The `.` mapping is real (`-home-x--llm-general-skills-ud-dreamwork` exists),
  so the design underspecifies; reported, not extended.
- `CATALOGUE_CLIENT` is hardcoded to `"claude-code"` — the one measured client.
  A second client's root would need its own catalogue call with a different
  `projects_root`; the closed-set discipline belongs to increment 6 / `#615`.
- Opening or scanning any catalogue entry is increment 6 onward.

---

## DOGFOOD REPORT

**Friction found.**

1. **The offloaded prompt file did not exist.** The system message said "Read
   this file with read_file before responding" and pointed at a path under
   `~/.grok/sessions/…/prompts/prompt_0.txt` that was not on disk (the
   sessions directory had no `prompts/` subdir for this worktree). The full
   brief was in the inline `<user_query>`, so no information was lost, but the
   instruction to read a missing file is a broken redirect that cost a
   diagnostic step. Not blocking — the inline text was complete.

2. **`_target_slug_dirs` includes `.worktrees/*` but skips symlinks.** This is
   deliberate (a symlinked worktree name is unusual), but if a worktree manager
   symlinks its worktree dirs (some do), those sessions would be invisible to
   the catalogue. Worth a note for increment 6's caller — not a bug in this
   increment, which only discovers; the consumer resolves.

3. **The `_slug_for` self-consistency trap is general.** This is the second
   time this loop has hit the "test and impl agree on a wrong value because
   they call the same function" shape (the first was `#655`'s hand-rolled
   status reader). The literal-pin guard I added is cheap and closes it for
   this function, but the pattern — "a helper used by both the test and the
   code under test cannot catch its own wrongness" — is worth a lessons entry.
   I did not write one (out of scope for a lane), but the coordinator should
   consider it.

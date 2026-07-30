# Brief #564 — the dashboard's two questions parts grouped under one "Q & A" section, with a real gap above

Origin: human (his add-idea, journal ord=61, receipt 23050b66, filed #564).

His words: *"the 2 questions parts should be under a 'Q & A' section —
currently there's no gap between the section above them and them."*

## Lane-owns

- `watch.py`, **dashboard questions/answers region only**: `qSection`
  (~3568-3600), the dashboard assembly lines at ~4073-4075 (`qSection(d)`
  and the `questions for the dreamer · N open` dim link), and the CSS
  that spaces this group.
- Tests: extend the dashboard render tests that pin this region; a guard
  only if the rendered STRUCTURE changes in a way the existing dashboard
  guard cannot see (say so either way in the report).

**Explicitly not yours:** `chatList`/`chatRow` and anything chats
(lane-562chat is LIVE in that region — the section directly above
yours); the burndown region (lane-559bdhover live); the status section
(merged, but not yours); the reviews panel; `transitions.md`,
`watch-design.md`, `file-formats.md`, `lint.py`, the justfile,
`questions.md`, the ledger. FLAG wording for coordinator-owned files in
your report; do not edit them.

## The act

On the dashboard (`/`), the two questions parts today are `qSection(d)`
(the collapsible questions block with the `.qseclabel` summary) and the
dim `questions for the dreamer · N open` link line — rendered back to
back at ~4074-4075, directly under the topic-chats list with no
separation from it. Group both under ONE visible "Q & A" section:

1. A section container (the dashboard's existing section/label idiom —
   reuse, never invent) headed **Q & A**, containing both parts.
2. A real visual gap between this group and the section above — the
   container's own top spacing/border per watch-design.md's spacing
   tokens. **Achieve it entirely on the questions side** — do not touch
   `chatList`; the chats panel is another live lane's region and your
   gap must not depend on editing it.
3. The group's own internal rhythm stays as it is — this is grouping and
   separation, not a redesign of the cards.

## Contracts to read first (not optional)

- `transitions.md` — if the section head or gap involves anything
  appearing, disappearing, or changing state (it should not need to —
  this is static structure), it obeys the file; the panel's tick
  re-render is the already-documented settled idiom.
- `watch-design.md` — the section-label idiom, spacing tokens, copy
  voice ("Q & A" is his word — use it verbatim).
- The `#504` comment at ~4020-4027 documents the settled re-render
  idiom this panel already lives under.

## Verification (the repo's discipline, all of it)

- **Born-red:** a failing render test first (the group head exists, both
  parts inside the container, the container present between the chats
  region and the rest), then implement, then green. Tests render through
  the REAL page assembly, never a hand-built fragment.
- **Red-proof:** name the production line each test binds, `cp`-backup,
  sabotage, watch the discriminating tests fail — **a green red-run is
  a finding, never a relief** — `cp`-restore, prove byte-identical with
  `cmp`. Run ALL sabotage/restore inside YOUR worktree; verify `pwd`
  first (a prior lane red-proved against the main checkout — don't).
- If rendered structure changes in a way the existing guards don't pin,
  add the solo guard in `dev/capture/` and run it on a free 3989x port
  that is NOT 39890 (lane-559) or 39892 (lane-562): use 39893.
- Never touch port 35110; never `pkill -f`; never `attn`; never the full
  coordinator suite.
- NEVER read_file an image (text-only lane; the coordinator does visual
  verdicts).

## Handoff (#398)

End with a `## Pending` line appended to the literal path
`.dreamwork/handoffs.md`: task id, bare shas, no parentheticals, no
model claims. `grep -nE '^(<{7}|>{7}|={7}|\|{7})' .dreamwork/handoffs.md`
must be empty before you finish. Commits: `git commit --only <paths>`
(new files `git add`ed first). Report: commits (bare shas), born-red +
red-proof evidence with named production lines, the exact structure
shipped, guard yes/no + why, FLAGs, found-not-fixed.

# Brief #563 — the topic-chats section is always visible, even when empty

Origin: human (his add-idea, journal ord=61, receipt 23050b66, filed #563).
Sequenced behind #562 (same region) — now unblocked: #562 merged
`35a630ee`, deployed, folded.

His words: *"the 'topic chats' section should always be visible even when
there are no chats."*

## Lane-owns

- `watch.py`, **chat-list region only**: `chatList` (~4050-4070 — the
  `if (!d.chats || !d.chats.length) return '';` early return is the
  defect), and if needed the `.chatrow`/list CSS.
- Tests: extend the chat tests in test_watch.py; the `chatsurface` guard
  (dev/capture/chatsurface.mjs) if the empty state changes what it
  should assert (the guard builds its OWN target — the shared fixture
  is chatless, so the guard's target setup may need an empty-chats arm;
  coordinate within your own files).

**Explicitly not yours:** the composer region (lane-570compose live),
the posture widget (lane-565569posture live), the burndown, the Q&A
section, `transitions.md`, `watch-design.md`, `file-formats.md`,
`lint.py`, the justfile, the ledger. FLAG, never edit.

## The act

Today `chatList` returns `''` when `d.chats` is empty — the whole
section, label included, vanishes ("quiet when empty, like reviews",
the #504 comment at ~4020). He wants the section always visible:

1. The `topic chats` label renders whether or not chats exist.
2. The count line follows the #562 shape: `topic chats · 0 total` when
   empty (unread clause absent at 0, per the same rule — only when
   unread > 0).
3. An empty-state line under the label in the page's own quiet voice —
   the dashboard's existing empty-state idiom (see how other sections
   handle "nothing here yet": a single dim line, no new token). Pick
   the idiom that already exists; do not invent one.
4. With chats present, nothing changes from today's #562 rendering.

**Note the deliberate contrast**: the reviews panel stays quiet-when-empty
(he has not asked to change it). Only the chats section gains the
always-visible treatment. If you judge the two should be consistent,
FLAG it — do not change reviews.

## Contracts to read first (not optional)

- `transitions.md` — the section going from absent to present IS a
  transition. The panel re-renders through innerHTML each tick (the
  documented settled re-render idiom at ~4020-4027), and an arriving
  chat was already that settled re-render; a section that is always
  present removes the appear/vanish entirely, which is the smallest
  possible motion story. If the empty state involves anything appearing
  or disappearing beyond that, it obeys the file.
- `watch-design.md` — the empty-state voice and dim-row idiom.
- The #504/#562 chat machinery and comments around `chatList`.

## Verification (the repo's discipline, all of it)

- **Born-red:** a failing render test first (empty `d.chats` → label
  present, `0 total`, empty-state line; non-empty → today's rendering
  unchanged), through the REAL `chatList`, then implement, then green.
- **Red-proof:** name the production line (the early return / the
  empty branch), `cp`-backup, sabotage, watch the discriminating tests
  fail (a GREEN red-run is a finding, never a relief), `cp`-restore,
  `cmp` byte-identical. ALL sabotage/restore inside YOUR worktree;
  verify `pwd` first.
- **Guard:** `chatsurface` builds its own target. If the empty state
  deserves a browser assertion (the label is present on a chatless
  target), extend the guard IN YOUR OWN FILE with an empty-chats arm
  and run it solo on port 39890 (free again — the merged lanes' ports
  are released; 39894/39895 are the live lanes'). Otherwise say why the
  pytest coverage is sufficient.
- Never touch port 35110, never `pkill -f`, never `attn`, never the
  full coordinator suite. NEVER read_file an image.

## Handoff (#398)

`## Pending` line appended to the literal path
`.dreamwork/handoffs.md`: task id, bare shas, no parentheticals, no
model claims. `grep -nE '^(<{7}|>{7}|={7}|\|{7})' .dreamwork/handoffs.md`
empty before finishing. Commits `git commit --only <paths>` (new files
`git add`ed first). Report: commits (bare shas), born-red + red-proof
evidence with named production lines, the empty-state copy as shipped,
guard yes/no + why, FLAGs (incl. the reviews-consistency call),
found-not-fixed.

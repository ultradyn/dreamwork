# Brief #570 — the composer text entry is manually expandable; a drag disables autoexpand until submit

Origin: human (his do-next, journal ord=66, receipt d1a23fcb, filed #570).

His words: *"the text entry box should still be manually expandable by
the user. Right now, it isn't. so once it is fully expanded, i can't
make it bigger even if i wanted to. once the user manually drags it,
disable the autoexpand entirely until the prompt is submitted (then it
returns to normal behavior)."*

## Lane-owns

- `watch.py`, **composer region only**: the compose textarea, its
  autoexpand logic, its resize handle / CSS, and the submit path that
  re-enables autoexpand.
- Tests: extend the composer tests; a guard only if the resize behaviour
  is not pinnable by the existing composer guards (say so either way).

**Explicitly not yours:** the posture widget (lane for #565/#569 not yet
dispatched but the region is reserved), the burndown region, the chat
region, the questions/Q&A region, `transitions.md`, `watch-design.md`,
`file-formats.md`, `lint.py`, the justfile, the ledger. FLAG, never edit.

## The act

1. The compose textarea is **manually resizable** by the user (a CSS
   `resize` handle, or the browser's native textarea resize — reuse the
   page's idiom; do not invent a custom drag unless the native one is
   already suppressed).
2. **Once the user manually drags it**, the autoexpand is **disabled
   entirely** for that composition — the box stays at the user's chosen
   size no matter what is typed or pasted.
3. **On submit**, the autoexpand returns to normal behavior (the next
   composition autoexpands again).
4. The manual size is NOT persisted across submissions — it resets on
   submit (his words: "then it returns to normal behavior"). A future
   user setting (#571) may change that; it is out of scope here.

## Contracts to read first (not optional)

- `transitions.md` — the autoexpand→manual transition (the box stops
  growing on its own) and the submit→autoexpand transition (it resumes)
  are state changes that obey the file. The resize handle's appearance
  is static CSS, not motion.
- `watch-design.md` — the composer's existing shape, tokens, the
  textarea's current styling.

## Verification (the repo's discipline, all of it)

- **Born-red:** a failing test first (through the REAL composer render +
  submit path), then implement, then green. The test must exercise the
  full cycle: autoexpand works → user drags → autoexpand disabled →
  submit → autoexpand re-enabled.
- **Red-proof:** name the production line each test binds (the
  drag-detection, the autoexpand disable, the submit re-enable),
  `cp`-backup, sabotage, watch the discriminating tests fail (a GREEN
  red-run is a finding, never a relief), `cp`-restore, `cmp`
  byte-identical. ALL sabotage/restore inside YOUR worktree; verify
  `pwd` first.
- If the resize behaviour needs a guard (a drag is a pointer gesture the
  existing guards may not drive), add one in `dev/capture/` on port
  39894 (39890-39893 are used by merged lanes; 39894 is free). Otherwise
  say why none is needed.
- Never touch port 35110, never `pkill -f`, never `attn`, never the full
  coordinator suite.
- NEVER read_file an image.

## Handoff (#398)

`## Pending` line appended to the literal path
`.dreamwork/handoffs.md`: task id, bare shas, no parentheticals, no
model claims. `grep -nE '^(<{7}|>{7}|={7}|\|{7})' .dreamwork/handoffs.md`
empty before finishing. Commits `git commit --only <paths>` (new files
`git add`ed first). Report: commits (bare shas), born-red + red-proof
evidence with named production lines, the resize mechanism shipped
(native vs custom), guard yes/no + why, FLAGs, found-not-fixed.

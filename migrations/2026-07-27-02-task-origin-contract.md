# 2026-07-27 — task origin is recorded, forward-only from #216

## What changed

The task ledger gains a provenance contract (#213). Every entry whose
leading `- **#…**` token names any id **>= 216** must carry exactly one
origin marker in its metadata chain: `origin: **human**`,
`origin: **loop**`, or `origin: **unknown**`. Entries whose ids all
predate the cutoff are exempt and unchecked — historical tasks stay
unknown rather than being guessed. `unknown` is a first-class truthful
value, not a failure. `lint.py` errors on a governed entry with a
missing, invalid, wrongly-cased, or duplicated marker.

First-seen parsing of origin from git history (#216) and the dashboard's
honest provenance read (#217) are later increments. This change is the
contract and the linter only.

## How to apply

In the target's `.dreamwork/tasks.md`, add `origin: **unknown**` to the
metadata chain of every `- **#…**` entry — Open or Recently landed —
whose listed ids include one >= 216 and which has no marker. Exception:
where the entry's own text already proves who filed it, record
`origin: **human**` or `origin: **loop**` instead. Do NOT guess, and do
not run git archaeology to decide — first-seen parsing is #216's job.

- Combined entries (`- **#250/#251**`) are governed when ANY listed id
  is >= 216; `- **#138/#156**` needs nothing.
- A `#N` mentioned in an entry's body is a cross-reference, not the
  entry's number — it never triggers the rule.
- Entries with all ids < 216 need nothing; do not mark them.
- The marker may hard-wrap (`origin:` ending a line, value on the next).

Run `python3 <skill-dir>/lint.py --target .` to confirm clean.

Shape: `file-formats.md` (`.dreamwork/tasks.md` — origin, forward-only
from #216). Checked by `lint.py`.

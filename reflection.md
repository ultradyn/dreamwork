# Reflection checklist

Run this after each change and at each mid-task checkpoint. Slowly — the
point is noticing, not box-ticking.

1. Did the change do only what the task said? Anything smuggled in?
2. Re-read the diff cold. Does it match the intent you would state aloud?
3. Run the project's verification (tests/lint, or its stated routine —
   see DREAMWORK.md). Green? And if the increment touched `.dreamwork/`,
   also run `python3 <skill-dir>/lint.py --target .` — the project's own
   tests never check the loop's files, so on every target but the skill's
   own repo this is the only thing standing between a malformed
   `questions.md` and a silently empty dashboard.
4. Did this break a promise made elsewhere — docs, cross-references,
   numbering, callers? In particular: if you taught something a new way
   to *read* a thing, go and check whatever *writes* it still matches.
   A reader and a writer that drift apart fail silently, which is the
   expensive kind.
5. Did anything occur to you that was out of scope? Task list, now.
   If the queue changed at all, the ledger changes in the same commit —
   a session-scoped backend forgets, the ledger doesn't.
   Dreamers: report the queue change instead; the coordinator writes the
   ledger, so ids can't collide.
6. Is the increment committable as-is? If not, what is the smallest step
   that makes it so?

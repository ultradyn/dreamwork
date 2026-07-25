# 2026-07-25 — submissions.log exists, and it must never be committed

## What changed

The dashboard now writes `.dreamwork/submissions.log`: one JSON line per
POST received, persisted as the first act of `do_POST` — before dispatch,
before parse, before validation — so a submission that then fails
400/404/409/413/500 still leaves the human's text on disk. Shape in
`file-formats.md`; checked by `lint.py`; built because an answer that
failed to match its entry was refused with a 409 and recorded nowhere.

It is the only **verbatim** copy of what the human typed. Everything else
that accepts their words stores a rendering (`append_answer` hard-wraps),
which is also why it exists.

## How to apply

Add one line to the **target's** `.gitignore`:

```
.dreamwork/submissions.log
```

That is the whole migration, and it is not optional: the file holds raw
typed text, and without the line it sits untracked — one `git add -A`
away from committing or pushing the human's words. If the target keeps a
frozen capture fixture the way this repo does, ignore the fixture's copy
too.

The file itself appears on its own, at the first submission through a
dashboard running this version. Nothing to create, nothing to backfill.

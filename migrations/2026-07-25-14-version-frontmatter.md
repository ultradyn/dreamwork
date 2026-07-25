# 2026-07-25 — DREAMWORK.md gains a version stamp in YAML frontmatter

## What changed

The skill can now say which dreamwork it is: `bin/ud-dw-githash` prints
its version (`<sha12>`, with a live `+N` when the checkout is dirty, or
`unknown`). For that to mean anything at a target, the target has to
remember which version it last reconciled with — and that stamp lives in
YAML frontmatter at the top of DREAMWORK.md:

```
---
dreamwork-version: 5853e1789929
---
# DREAMWORK.md — <project>
```

Full shape in `file-formats.md` ("DREAMWORK.md frontmatter"); checked by
`lint.py`. Only the first token of the githash output is stored — the
dirty annotation is live state, not identity.

This is the memory half of #194's upgrade design
(`docs/plans/version-and-upgrade.md`): a later init step will compare
stamp against tool on every load and dispatch a cheap discovery pass over
the intervening commits. Nothing performs that comparison yet.

## How to apply

Add the frontmatter block above the first line of the target's
DREAMWORK.md, stamped with the first token of what
`<skill-dir>/bin/ud-dw-githash` prints now. If the tool says `unknown`,
stamp `unknown` — that is a legal, quiet state, and the estimate-from-
mtimes fallback belongs to the init step, not to you.

The rest of the file is the human's prose and must not be otherwise
touched. One stamp, nothing else.

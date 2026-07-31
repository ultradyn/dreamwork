# Plan — #572: GitHub PR/comment etiquette and the `gh` shim

**Status:** design settled except Q2's remaining fork. Not started.
**His asking level for this task:** *"ask me (please treat this task as if your posture says that the asking level is to ask me about design choices etc)"* — so the forks were surfaced as `#572` in `questions.md` and answered via the dashboard on **2026-07-31 03:57**. This file is the durable record of what he settled; `questions.md` keeps only what is still his to decide.

## What it is

A protocol of etiquette for posting to GitHub as Max: every PR body and comment carries an agent-attribution header and a signoff whose `Internal Reference` links back to the dreamwork work that produced it. A stdlib-python-only `gh` shim adds them automatically so it cannot be forgotten.

## Settled by his 2026-07-31 03:57 answer

### Q1 — header text · `rec` accepted

```
*Posted by Max's dreamwork agent*
```

Italic, one line, top of the body. Names whose agent it is without pretending to be him — his own sketch (`*Written by my Agent*`) was anonymous, and `*AI-assisted*` says nothing about agency.

### Q3 — shim mechanism · `rec` accepted, with a preference

`dev/gh_shim.py`: wraps `gh pr create` / `gh issue comment` / `gh pr comment`, reads the body from `--body`, `--body-file` or `$EDITOR`, prepends/appends the header and footer, delegates to the real `gh`. ~100 lines of argparse + subprocess, stdlib only.

**Install surface — his call:** *"the extension is better i feel, so we should recommend that i think but also we can provide the alias as a backup."* So: ship a `gh-dreamwork` extension as the recommended path (discoverable, on PATH, `gh dreamwork ...`), and document the fish alias as a fallback for anyone who does not want an extension installed.

### Q4 — testing phases · `rec` accepted, signature dropped

Three phases, exactly as he specified them:

1. **Pass-through.** The shim inserts nothing and delegates unchanged. Proves the interception works at all before it can corrupt a real post.
2. **HTML-comment probe.** It inserts `<!-- Posted by Max's dreamwork agent · Internal Reference: <id> -->` — invisible in rendered markdown, present in source. We then test whether the marker can be recovered from other posts, or whether GitHub sanitises it.
3. **Release** (his signoff required). The visible header and footer ship.

**No cryptographic signature.** His words: *"no need for a sig at all probably, but the option is there for us if we want."* Recorded as deliberately deferred, not overlooked — it is a second system (key management, a verification endpoint) and the Internal Reference already carries traceability. Revisit only if authenticity becomes a real concern.

### Q5 — docs page · `rec` accepted

The footer links `https://dreamwork.ultradyn.ai/docs/q/what-is-an-internal-reference` from day one, accepting that it 404s until the page exists. Writing that page is a follow-up task on dreamhub's docs surface. The reference works as a lookup key regardless of whether the link resolves.

## Q2 — open, narrowed

His pushback: *"hmm, do we want to leak the sequence id though? also what if there are multiple comments left under one /command dispatch?"*

### The leak concern is answered by the code

`user_events/sqlite.py:708-713`:

```python
receipt_id = str(uuid.uuid5(
    uuid.NAMESPACE_URL,
    f"ud-dreamwork.receipt:{envelope.client_action_id}",
))
```

The receipt id is a **UUIDv5 hash of the client action id**, which is itself a `uuid4`. It is not a counter and contains no ordinal, no timestamp and no host identifier. Publishing one reveals nothing about how many commands he has issued, in what order, or when — the properties a leaked sequence would expose.

His instinct was right that a sequence exists, though: the `receipts` table carries a separate monotonic **`sequence`** column (`user_events/sqlite.py:785`). That column *would* leak volume and ordering. It is simply not what the footer publishes, and it must never become what it publishes. Worth stating explicitly in the shim's own docstring so a later change cannot quietly swap one for the other.

One further property, since it bears on the same worry: because the id is a v5 hash of a random 122-bit uuid4, publishing it does not expose the `client_action_id` it derives from.

### The multiple-comments case is by design, not a defect

Several comments from one dispatch share one reference — because they share one cause. The reference answers *"why does this text exist?"*, and GitHub already answers *"which post is this?"* with a per-comment permalink. Adding a per-post discriminator would build a second identifier to solve a problem the platform has already solved.

### What is still his to decide

Whether the reference is allowed to be one-to-many at all. It changes what the docs page promises a reader who follows it:

- **`rec` — the reference points at the dispatch.** One id, possibly several posts. The page explains "this is the instruction that produced this text", and a reader who follows it may find sibling posts. Simple, no new identifier.
- **Per-post discriminator.** `Internal Reference: <receipt-id>#2`, with the shim keeping a per-receipt counter. The page can then resolve to exactly one post — at the cost of the shim holding durable state it otherwise does not need, and of a counter that *is* an ordinal, reintroducing exactly the leak shape he flagged, scoped to one dispatch.

## Files this will touch when it starts

- `dev/gh_shim.py` — new
- a `gh-dreamwork` extension wrapper, plus the documented fish-alias fallback
- tests for body extraction from `--body` / `--body-file` / `$EDITOR`, and for phase-1 byte-identical pass-through

## Constraints carried from the repo

- **Stdlib python only.** No dependencies (`watch-design.md`'s surviving constraint is the Python-dependency one).
- Phase 3 does not ship without his explicit signoff — he said so, and it is the phase that changes what appears under his name in public.

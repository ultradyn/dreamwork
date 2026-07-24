# 2026-07-25 — notes carry their author

## What changed

Threaded notes in `.dreamwork/questions.md` now record **who wrote
them**, not just when and through which channel:

- human: `- **Note (human, via <channel>, <ts>):** …`
- the loop: `- **Follow-up (loop, <ts>):** …`

Reported by the human, who found his own dashboard notes reading as part
of the loop-written entry above them: "they should be demarcated as
notes in the file … or be obviously user notes, not something written by
a dreamer". The old tag `- **Follow-up (via watch, <ts>):**` recorded the
channel only, so a dreamer's in-session follow-up and a human's note were
indistinguishable once folded into one thread.

## How to apply

New notes use the new tags. Existing entries need no rewrite — read the
old forms as their author implies: `(via watch, …)` was a human at the
dashboard, `(in-session, …)` was the loop. Any tool that parses threads
should accept all four forms.

The rendering half belongs to whatever surface displays questions: where
both voices appear, authorship must be visible — quietly (a dim label or
a hanging marker), not as decoration.

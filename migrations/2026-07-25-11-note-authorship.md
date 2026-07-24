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
old forms as their author implies: any `(via <channel>, …)` was a human
at that channel, and `(in-session, …)` was the loop. A parser accepts
all four:

| tag | author |
|---|---|
| `- **Note (human, via <channel>, <ts>):**` | human (current) |
| `- **Follow-up (loop, <ts>):**` | the loop (current) |
| `- **Follow-up (via <channel>, <ts>):**` | human (legacy) |
| `- **Follow-up (in-session, <ts>):**` | the loop (legacy) |

Anything unrecognised: render it, attribute nothing, never guess.

The rendering half belongs to whatever surface displays questions: where
both voices appear, authorship must be visible — quietly (a dim label or
a hanging marker), not as decoration.

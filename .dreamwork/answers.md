# Questions for the dreamer

## Open

## Answered

- **2026-07-27 — #283 safe Dolphin-window falsification observation**
  → in progress from the dashboard answer at 00:16. Max's exact words were:
  “closed. but not sure that it's dolphin is it? if it is that's good to
  know.” The coordinator does not assume the closed window was Dolphin. It is
  observing this repository's existing `index.lock` events for 60 seconds,
  read-only, then will report whether the former cadence stopped or persisted.
  No privileged tracing or process/KIO/Git mutation was authorized.

- **2026-07-26 — What causes the pause between answer and question movement?**
  → answered (2026-07-26 14:00): it is mostly an intentional **1.6-second
  client-side rerender hold**. After `POST /answer` succeeds, `sendAnswer()`
  immediately restates the existing card as `answered · awaiting fold`, lifts
  the answer text from the textarea, and starts the card/neighbour travel.
  That travel is nominally 850ms, while `holdRerenderUntil = Date.now() +
  1600` prevents the live `/mtime` tick from replacing the DOM until the
  confirmation morph has settled. The visible consequence is roughly 750ms
  of quiet after the first animation.

  The second movement begins on the first eligible live tick that sees the
  changed file. `tick()` recurs every 2 seconds, so the exact pause also
  depends on poll phase: a poll just after the hold regroups promptly; one
  arriving just before it waits another cycle. The later coordinator move
  from `## Open` into `## Answered` is separate and not a fixed part of this
  middle pause. This separation was introduced deliberately so a tick cannot
  replace the card during the answer-submit morph; `morph.mjs` traces the
  first 1400ms inside the hold, while `regroup.mjs` proves the later live-data
  movement.

  **Human:** When submitting an answer to a question, it animates first the
  answer, then pauses for about a second, then animates the question as it
  moves into answered · awaiting fold. What causes the middle pause?


- **2026-07-26 — Can an answer re-block or reopen a question?** → answered
  (2026-07-26 13:45): an answer first leaves the dreamer's question in
  **answered · awaiting fold**. The coordinator reads and acts on it, and
  folds only when it resolves the decision. If it does not, the entry may
  remain open or receive a narrower follow-up. A later amendment on a folded
  question can reopen the same entire entry, preserving its notes and answer;
  a materially different issue becomes a new question that names the prior
  title or task. The existing linear thread is enough for this governance
  channel. #229 topic chats are the deliberate heavier model when a subject
  needs repeated fresh-agent discussion rather than one decision thread.

  **Human:** I might answer a question in such a way that could unblock the
  dreamer, or might not. How is this handled at the moment? Can a question for
  the user that gets answered be changed back to unanswered, or does the agent
  just start a new question? How does it link back to prior questions? Should
  we consider building something more complex?

# Brief — verify draft durability empirically: does typed text survive a server restart?

Repo: `ud-dreamwork`. **Work in the main checkout, READ-ONLY except your one output file.** No worktree.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[draftcheck]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/draftcheck-inbox.md`.

Final report goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which
model you are** at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md` — report the lines you want added.

## Why this exists — the coordinator was wrong and wants to know how wrong

The coordinator told the human a server restart could lose text he had typed into the dashboard, because `#269`
(draft durability) was recorded as *designed and authorised but not implemented*. **The human corrected it:
"drafts are durable btw, ask a grok subagent to check."** He is right that a mechanism exists — `watch.py`
around **line 4649** carries `#269, acute`, keying drafts as `dw:adraft:<target>:<id>` and restoring them after
each render.

So the ledger's picture of `#269` is wrong somewhere, and the question is *which part*. **Your job is to
establish empirically what the shipped mechanism actually guarantees**, so the record matches reality and the
authorised remaining work is the real remainder.

## The questions, in priority order

1. **Does typed text survive a `watch.py` process restart?** Not just a page reload — an actual restart of the
   server, which is what the coordinator was cautious about. Test it.
2. **When is a draft written?** Per keystroke, debounced (how long?), on blur, or on submit? A debounce means a
   restart within that window loses the tail of a sentence — that is the difference between "durable" and
   "durable except the last few seconds", and it is the answer the human's correction hinges on.
3. **Which boxes are covered?** The review-dock answer box is the one `#269` names. Also check the **command
   composer** (the box he types `do-now` / `add-idea` into — those go to `watch-events.log`), the questions-page
   answer boxes, and the comment/follow-up path. **A box that is not covered is the finding.**
4. **Is it survived by a reload, a route change, and a re-render?** The code claims all three; verify rather
   than trusting the comments.
5. **What clears a draft, and is that correct?** Line ~3525 says a landed answer must not leave a draft that
   reappears "as a thought he already sent". Confirm a *rejected* or *failed* send does **not** clear it — his
   standing rule is that a draft clears only on **durable success**.
6. **Storage mechanism:** `localStorage` or IndexedDB? `#269`'s design specified IndexedDB with cross-tab
   handling and 30-day GC (he answered `rec` on both at 01:12). If the shipped version is `localStorage`, say
   so — then the design's remaining value is the *upgrade*, not the feature, and the ledger should say that.

## How to test without disturbing him

- **Do NOT touch :35110.** He is reading it right now. Start **your own** `watch.py` on a port you pick in
  **39895–39899** and drive that. Kill only the pid you started, by exact pid — never `pkill -f`.
- Playwright is available; `dev/capture/*.mjs` shows the house idiom for serving the real target on an ephemeral
  port and driving it (`dev/capture/states.mjs` is a good model). Reuse that scaffolding rather than writing new.
- **Type real text, restart your server, reload, and read the box.** An assertion about `localStorage` contents
  is weaker evidence than the text reappearing in the field.
- Do not touch the heartbeat, the monitors, the loop, or `just deploy`. Do not run the full `just test`.

## Output

**One file: `.dreamwork/docs/draft-durability-status.md`** — what is shipped, what it guarantees, what it does
**not**, per box and per event, with the code lines cited. Plus a **`doc-map.md` row** (contended; on conflict
resolve as a union and verify the row against the directory both ways).

Then, in your report, **the ledger correction**: what `#269`'s open entry should say now, and whether the
authorised implementation is (a) still entirely open, (b) partly shipped, or (c) already satisfied and should be
folded. Quote the evidence for whichever you claim.

## Done means

1. The doc exists with the six answers, each backed by an observation or a cited line — **not by a comment's
   claim about itself**. Where a comment says one thing and the behaviour differs, the behaviour wins and you
   report the discrepancy.
2. `python3 lint.py --target .` clean afterwards.
3. Nothing on :35110 touched; every process you started killed by exact pid; nothing left listening.

## Practical

- `git add .dreamwork/docs/draft-durability-status.md` then
  `git commit --only .dreamwork/docs/draft-durability-status.md .dreamwork/docs/doc-map.md -m 'docs(#269): …'`
  — **`--only`, never `git add -A`**: other agents commit in this tree.
- **Commit before you finish.** **~15–20 minutes**; the restart test is the part worth the time.
- **Report a negative finding as loudly as a positive one.** If drafts turn out to be durable in every case the
  human implied, say so plainly — that is a correction of the coordinator's record and exactly what he asked
  for. If you find a box that loses text, that is a bug and it outranks everything else in your report.

## Report

Say: which model you are; whether typed text survived a real process restart, and in which boxes; the write
trigger and debounce window with the line that sets it; which boxes are **not** covered; what clears a draft and
whether a failed send does; `localStorage` vs IndexedDB; the ledger correction for `#269`; and confirmation you
never touched :35110, killed every process you started by exact pid, and did not run the full `just test`.

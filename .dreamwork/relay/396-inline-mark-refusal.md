# Coordinator → #396 · 2026-07-28 08:59

**One added obligation, and it is explicitly granted. Nothing else changes.**

## When you land a commit, write a hand-off line

Append **one line** to `.dreamwork/handoffs.md` under `## Pending`, per landing:

```
- **#396** · landed `<sha>` · <YYYY-MM-DD HH:MM> · by <your runner> — <one line, what landed>
```

**This file is now in your ownership list** — your brief did not grant it because the
obligation did not exist when you were dispatched. Append only, in a single shell append
(`cat >>`), never by rewriting: other sessions append concurrently and a rewrite loses
their line. `git add .dreamwork/handoffs.md` then `git commit --only .dreamwork/handoffs.md`
if it is untracked-new to you; otherwise `--only` is enough.

**Do NOT touch `## Folded`** — that section is the coordinator's, and do **not** write to
`.dreamwork/tasks.md`. You are using the channel, not the ledger.

## Why, since it looks redundant against your inbox report and is not

They are read by different things at different times. **The inbox carries your judgement,
is prose, and is read by a coordinator once.** The hand-off carries the **id and the sha**,
and is read by `lint.py` and the dashboard **forever** — `lint` WARNs while a landed task
is still under `## Open`, which is the condition that cost an hour twice (`#334`, `#362`).

So an inbox report is durable only while a coordinator is alive to act on it, and the case
the hand-off exists for is precisely the other one.

**`#381` built this channel and both its readers, and I verified them end to end.** What was
missing was anyone telling a producer to use it: `## Pending` sat empty while two lanes
landed. **A channel nobody writes fails the same way as a channel nobody reads, and looks
just as finished.** You are the first lanes asked to write one, so if the format fights you,
say so in your report — that is a finding about the format, not a failure of yours.

# dreamwork

A heartbeat-driven autonomous dev loop for coding agents. Leave an agent
dreaming on a project and come back to steady, safe, well-chosen
progress.

The loop wakes itself every 4.75 minutes, works in small committed
increments with deliberate reflection after each change, captures every
idea as a task, and picks the next one by an explicit algorithm when
idle. It knows what you want because you told it once, in a file it
keeps current.

## What makes it different

- **Small increments are the error-catching mechanism.** Each task is
  capped at 15-20 minutes and ends verifiable and committable, so
  mistakes surface while the agent is still on the path that made them.
- **Nothing durable lives in the conversation.** Goals, open questions,
  lessons, plans, and the task queue itself are files in the repo — the
  loop survives a restart, a compaction, or a fresh agent.
- **It asks, and records the ask.** Anything needing a human decision
  lands in `.dreamwork/questions.md` with enough context to answer cold,
  and can be answered from the dashboard instead of the terminal.
- **It delegates to itself.** Substantial work goes to dreamer
  subagents that share the loop's memory and write back what they
  learned.
- **It watches itself dream.** `watch.py` is a dependency-free local
  dashboard showing live status, questions, review artifacts, and a
  composer for steering the loop — no build step, no npm.
- **It also does errands.** [`ud-dreamtask`](../ud-dreamtask/SKILL.md)
  is the same loop bounded to one task: it establishes what done looks
  like, works it in increments, and stops when the criteria verify.
- **It scales past one project.** `dreamhub.py` is a read-only page over
  every dreaming project on the machine: which loops are moving, which
  have gone quiet, which are waiting on you, and a link through to each
  project's own dashboard (`dreamhub add <path>`, then `dreamhub serve`).

## Install

The skill is consumed in-harness, so installing is a symlink:

```sh
ln -s "$PWD" ~/.claude/skills/ud-dreamwork      # Claude Code
ln -s "$PWD" ~/.agents/skills/ud-dreamwork      # Codex
```

Then start it on a project: say *dreamwork* (or *start dreaming*) to the
agent. On first run it interviews you briefly and writes `DREAMWORK.md`
at the project root — your goals, philosophy, and working preferences.
Everything after that is the loop.

## Where to look

[`SKILL.md`](SKILL.md) is the entry point and the product: philosophy,
the tick flow, the selection algorithm, subagents, durable state,
commands, guardrails. Beside it, [`initialization.md`](initialization.md)
is the per-session startup, [`reflection.md`](reflection.md) the
post-change checklist, [`watch-design.md`](watch-design.md) the dashboard
styleguide, and [`writing-plugins.md`](writing-plugins.md) the contract
for extending the loop.

---

Created by [Max Kaye (XertroV)](https://xk.io) + AI.

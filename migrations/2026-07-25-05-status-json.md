# 2026-07-25 — status.json for the watch dashboard

## What changed

The loop refreshes `.dreamwork/status.json` each tick (best-effort:
current task, queue depth, last tick, last commit) so watch.py can show
live loop state — the native task list isn't on disk otherwise.

## How to apply

Add `.dreamwork/status.json` to the target's .gitignore (it churns every
tick — ephemera, not history). The loop starts writing it on its next
tick; watch.py shows a status section automatically once it exists.

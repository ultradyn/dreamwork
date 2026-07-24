# 2026-07-25 — review artifacts

## What changed

`.dreamwork/review/<slug>.html`: self-contained rich review artifacts
(inline charts/math/styles, offline-clean) for sizeable things needing
the human's eyes, each paired with a questions.md entry for the response.
watch.py lists them on the dashboard and serves them raw (confined to
that directory).

## How to apply

Nothing required until the first artifact; create the directory on first
use. Restart any running watch.py to gain the /review route.

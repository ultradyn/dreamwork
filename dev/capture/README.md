# watch capture/instrumentation scripts

Headless-chromium evidence scripts from the 2026-07-25 watch build-out
(dreamer-beauty). Each targets a RUNNING watch server — adapt the port
(never 35110/35111). Durable patterns: per-frame trace for motion
(optrace), multi-timestamp captures for dissolves, fresh page per frame
to dodge headless screenshot stall. See watch-design.md for the motion
invariants these verify.

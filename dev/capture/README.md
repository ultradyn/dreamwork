# watch capture/instrumentation scripts

Headless-chromium evidence scripts from the 2026-07-25 watch build-out
(dreamer-beauty). Each targets a RUNNING watch server — adapt the port
(never 35110/35111). Durable patterns: per-frame trace for motion
(optrace), multi-timestamp captures for dissolves, fresh page per frame
to dodge headless screenshot stall. See watch-design.md for the motion
invariants these verify.

Added in the #91 composer batch:

- `worldspace.mjs` — the shader field is world-space: the same screen rect
  in windows of different heights must be the same pixels.
- `popbg.mjs` — a popped-out window mounts the shader, and its background
  matches the main page's across the document boundary.
- `indtrace.mjs` — per-frame trace of the composer's selection indicator:
  it must LAND on open and SLIDE on select (and jump under reduced motion).
- `menucap.mjs` — the ⋯ hover menu: row membership, descriptions, reveal,
  and picking an uncommon kind.

Two patterns from that batch worth reusing. **Freeze the clock**
(`context.addInitScript(() => { Date.now = () => T; })`) whenever comparing
a time-varying visual across captures that cannot be simultaneous — it is
what makes a cross-document pixel comparison possible at all. And **prove
the comparison discriminates**: temporarily restore the bug and check the
script reports FAIL, because a pixel test that can only ever pass is worse
than no test.

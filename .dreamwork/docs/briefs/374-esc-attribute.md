# Brief — #374: `esc()` does not escape the double quote; three attributes take a URL parameter

**Task (from the store, #374, P2, security/bug, origin loop — found by the
fileview dreamer, re-verified by reading):** `watch.py`'s JS
`esc = t => { d.textContent = t; return d.innerHTML }` (today ~:1489)
serialises *text* content, so `&`, `<`, `>` are escaped and `"` is NOT (the
HTML serialiser only escapes quotes inside attribute values). Three
attributes interpolate it (~:1527-1528): `aria-label="pop out ${esc(label)}"`,
`data-pipurl="${esc(url)}"`, `data-piplabel="${esc(label)}"`. Reachable:
~:4737 passes `v.param` — the route parameter from `/file?p=…` — as `label`,
so a `"` in the query string closes the attribute early. `<`/`>` stay escaped
so no new tag can be opened, but `onfocus=` on that same focusable button is
enough. `url` is `encodeURIComponent`'d at the call sites and is currently
safe. Exposure today: a crafted link the human opens against his own
dashboard (small); under #233's trusted-LAN mode it becomes any device on the
LAN (not small).

**Fix shape (the filing's recommendation; verify before trusting):** an
`escA()` for attribute position rather than widening `esc()`, so text
position keeps producing readable `"`. Every attribute interpolation of
`esc(...)` output in that builder must move to `escA` — sweep the file for
`="${esc(` and `='${esc(` and name each site you converted (and each you
deliberately did not, with the reason — e.g. a value already
`encodeURIComponent`'d).

**Red-first (required, and the filing names the form):** the proof is a `p`
containing `"` and an assertion about the PARSED DOM's attribute set, not
about the HTML string — the string looks plausible either way. New guard
`dev/capture/escattr.mjs`: drive `/file?p=` with a payload containing a quote
(`x" onfocus="window.__pwned=1` or similar), parse the rendered pip button,
assert (a) the attribute set contains NO injected attribute, (b)
`data-piplabel`/`aria-label` carry the literal payload as ONE value, and (c)
a precondition that the button really rendered (else vacuous). Watch it FAIL
against the unfixed code (born-red — the parsed DOM gains the injected
attribute), then fix and watch it PASS.

**Lane-owns:** `watch.py` (the `esc` helper + the pip-button builder region
ONLY — ~:1480-1540 and the ~:4737 call site), `dev/capture/escattr.mjs`
(new). Nothing else. Do NOT register the guard in the justfile
(coordinator-owned at the merge gate). Do not touch `lint.py`, `justfile`,
`SKILL.md`, `watch-design.md`, `transitions.md`, or `dev/capture/remindbtn.mjs`
(a sibling lane owns that file).

**Verification:** solo guard only —
`DREAMWORK_GUARDS="escattr" DREAMWORK_HUB_GUARDS= just guards 3989X` after
`ss -ltn` shows 39890-39899 free. Never `just test`, never the full suite.
Red-proofs per the repo rule: cp-snapshot → sabotage a NAMED production line
(e.g. `escA` falls back to `esc`) → the targeted check FAILs → cp-restore
byte-identical (cmp-verified, NEVER `git checkout`). A green red-run is a
finding, never a relief. Note in your report which production line each red
binds.

**Obligations (#398):** when done, append ONE Pending line to the literal file
`.dreamwork/handoffs.md` under `## Pending` (append-only; grammar in that
file's head: `- **#374** · landed \`<sha>\` · 2026-07-30 · by lane-374escattr — …`),
commit with `git commit --only <paths>` (a NEW file needs `git add <file>`
first), never `git add -A`, no `attn`, no `pkill -f`. Report: commits, the
born-red run (the parsed-DOM attribute set before/after), red-proof lines,
and the converted/not-converted site list with reasons.

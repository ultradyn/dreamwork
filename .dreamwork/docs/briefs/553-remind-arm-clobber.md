# Brief — #553: the remind cooldown's setTimeout can clobber a live `arming override…`

**Task (from the store, #553, P3, bug, origin loop):** paintRemindSlot's
cooldown-end setTimeout can clobber a live 'arming override…' for one render
cycle (≤2s, self-heals via morphdom) — gate it on pendingPostIsLive (#551
follow-up).

**The defect, as characterised at the #551 gate (coordinator review):** the
remind button's 10s cooldown ends with a `setTimeout` that repaints the slot
back to the button. If the human arms a posture override DURING that window,
the shared armed state (`arming override…`) is live — and when the timer fires
it repaints the slot from stale remind-state, hiding the armed copy until the
next data tick re-renders (≤2s later, morphdom self-heals). Small, but it is
exactly the class `transitions.md` exists for: a state the human created is
visually withdrawn by a timer he did not.

**Fix shape (named in the filing, verify before trusting):** the cooldown-end
repaint must early-return when an arm is live —
`pendingPostIsLive(readPostPending())` is the predicate the armed state itself
uses; reuse it, do not invent a second test of arm-ness. Read the actual code
first (`grep -n 'paintRemindSlot\|remindCooldownUntil\|pendingPostIsLive'
watch.py`): if the slot repaint already flows through a path that respects the
arm, say so and narrow the task to the guard.

**Red-first (required):** extend `dev/capture/remindbtn.mjs` with the
interleaving: press remind (cooldown starts), then arm a posture override
(pick a different stop for one axis — the shared 10s arm), then advance past
the remind cooldown (Playwright `page.clock` install+runFor is the landed
idiom for production setTimeout/setInterval — see bdinput's (d)/(e) checks)
and assert the slot still reads the armed copy, never the resurrected button.
Watch it FAIL against the unfixed code (born-red), then fix and watch it PASS.
The guard runs its own server with `DREAMWORK_REMIND_INBOX_DIR` redirected —
keep that seam intact.

**Lane-owns:** `watch.py` (the paintRemindSlot / sendRemind / posturePicker
region only — the remind+arm machinery, NOT the unrelated posture constants or
Python handlers), `dev/capture/remindbtn.mjs`. Nothing else. Do NOT register
the guard in the justfile (coordinator-owned at the merge gate). Do not touch
`lint.py`, `justfile`, `SKILL.md`, `watch-design.md`, `transitions.md`.

**Verification:** solo guard only —
`DREAMWORK_GUARDS="remindbtn" DREAMWORK_HUB_GUARDS= just guards 3989X` after
`ss -ltn` shows 39890-39899 free. Never `just test`, never the full suite.
Red-proofs per the repo rule: cp-snapshot → sabotage a NAMED production line
(your early-return) → the targeted check FAILs → cp-restore byte-identical
(cmp-verified, NEVER `git checkout`). A green red-run is a finding, never a
relief. pytest: `python3 -m pytest test_watch.py -q -k posture` if you touch
anything a test covers.

**Obligations (#398):** when done, append ONE Pending line to the literal file
`.dreamwork/handoffs.md` under `## Pending` (append-only; grammar in that
file's head: `- **#553** · landed \`<sha>\` · 2026-07-30 · by lane-553armfix — …`),
commit with `git commit --only <paths>` (a NEW file needs `git add <file>`
first), never `git add -A`, no `attn`, no `pkill -f`. Report: commits, the
born-red run, red-proof lines, and whether the fix shape matched the filing.

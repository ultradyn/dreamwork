# Brief — #556: popoutDoc re-opens the #374 attribute injection one hop away

**Task (verbatim from the store, #556, P2, origin loop, filed at the #374 merge
gate):** `popoutDoc` builds `<iframe src="${esc(url)}" title="${esc(label)}">`
(`watch.py:9496`) from the pip button's decoded `data-pipurl`/`data-piplabel`
(`watch.py:9942`). After escA those dataset values carry the WHOLE raw payload
as one value, so clicking the now-safe dashboard pip on a crafted `/file?p=`
page with a quote payload re-interpolates it into the popout window's iframe
tag via `esc` (no `"` escape). popHead (element-body esc only) and popoutShell
(`doc.title` assignment) were verified safe by the coordinator; the fixing lane
should still sweep the popout family and extend `escattr.mjs` (or a sibling)
with a popout-phase assertion. Red-first: drive the pip click on the crafted
URL, parse the popout document's iframe attribute set.

**Context you need:** #374 landed as `9d946d09` — read the `escA` helper and
its provenance comment (`watch.py:2284-2296`), the converted `pipBtn`
(`watch.py:2403-2407`), and the guard `dev/capture/escattr.mjs` (its header
comment is the contract: parsed-DOM attribute-SET assertions, never the HTML
string; absence-first preconditions; the payload `x" onfocus="window.__pwned=1`).
The popout click dispatch is the `pip.dataset` consumer — find every
`dataset.pipurl` / `dataset.piplabel` read and trace what each feeds.

**What to build:**
1. **The fix:** `popoutDoc`'s iframe interpolation uses `escA` for both `src`
   and `title` — reuse the existing helper, author no variant. (`src` holds
   `/file?p=<encodeURIComponent payload>` today, so its quotes arrive as `%22`
   — nearly safe already; `escA` is still correct-by-position. `title` carries
   the RAW decoded label and is the live vector.)
2. **The popout-family sweep:** every builder that interpolates a value derived
   from `dataset.pip*` (or any other DOM-round-tripped string) into a
   `"`-delimited attribute gets the same treatment. Name each site you convert
   and each you leave with its reason (closed-set / server-side constant /
   text position). The 25 sites the #374 lane triaged as internal/closed-set
   are OUT of scope unless one is DOM-round-tripped — say so if you find one.
3. **The guard phase:** extend `dev/capture/escattr.mjs` with a popout phase
   (preferred — one guard, one payload, two hops) or add a sibling
   `escattrpop.mjs`; state the choice and the reason. The phase: on the same
   crafted `/file?p=<payload>` page, CLICK the pip button, capture the popout
   document, and assert on the PARSED iframe: attribute set is exactly what
   `popoutDoc` emits (src, title — no injected `onfocus`), and `title` carries
   the whole payload as one value. Absence-first precondition: the popout
   really opened AND contains an iframe (else the phase is vacuous — name it).
   Popout capture mechanism is yours to discover: `openPopout` may use
   `window.open` (Playwright `context.waitForEvent('page')`) or a
   Document-Picture-in-Picture window (Playwright support is limited — if PiP
   is the default path, driving the window.open fallback or calling the doc
   builder through the page are both acceptable; what is NOT acceptable is
   asserting on the HTML string instead of a parsed document). Record the
   mechanism in the guard's header comment.
4. **Red-first, both hops visible:** before the fix, the popout phase FAILs on
   the parsed iframe (injected attribute present / title truncated) — record
   the born-red parsed-attribute before/after exactly as #374 did. After the
   fix it PASSes. Then red-proof: cp-snapshot → sabotage a NAMED production
   line (your `escA` conversion in `popoutDoc`) → the popout phase FAILs →
   cp-restore byte-identical (cmp-verified, NEVER `git checkout`). A green
   red-run is a finding, never a relief.

**Lane-owns:** `watch.py` (the popout family ONLY — `popoutDoc`, `popHead`,
`popoutShell`, `openPopout`, the `dataset.pip*` dispatch at ~:9942; do NOT
touch the remind/arm region or `remindbtn.mjs` — lane-553armfix owns those;
do NOT touch `pipBtn` itself — landed and guarded), `dev/capture/escattr.mjs`
or ONE new sibling guard file. Nothing else: not `justfile` (registration is
coordinator-owned at the merge gate — if you add a sibling guard, do NOT
register it), not `lint.py`/`test_lint.py` (lane-555sweep), not
`.dreamwork/handoffs.md` except your own Pending line.

**Verification:** solo guard only, after `ss -ltn` shows 39890-39899 free
(`DREAMWORK_GUARDS="escattr" DREAMWORK_HUB_GUARDS= just guards 3989X`);
`python3 -m pytest test_watch.py -q` full is allowed (no browser); NEVER
`just test` or the guard suite — browser lanes are in flight. Commit with
`git commit --only <paths>` (a NEW file needs `git add <file>` first); no
`attn`; no `pkill -f`.

**Obligations (#398):** when done, append ONE Pending line to the literal file
`.dreamwork/handoffs.md` under `## Pending` (append-only; grammar in that
file's head: `- **#556** · landed \`<sha>\` · 2026-07-30 · by lane-556popout — …`
— bare shas, no parentheticals; do not claim a model — the #469 notice: a lane
cannot know its own model). Report back: commits, the born-red popout
before/after, red-proof lines, the sweep table (converted / left-with-reason),
and the popout-capture mechanism you used.

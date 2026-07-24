# Spike #115 — what unifying `qaCard`/`pageHeader` onto the component vocabulary actually costs

Run 2026-07-25 in `.worktrees/spike-components` (branch `spike/components`),
timeboxed to ~1 hour. Three commits: `286cdb2` (vocabulary + fragment
wrapper), `2d429e1` (pageHeader), `f5a093a` (qaCard). 55 tests pass at
every commit.

## Verdict

**Split. `pageHeader` and the prose furniture are cheap and worth doing.
`qaCard` is moderate-to-expensive and not worth doing.** The plan's claim
that "unifying them is a bigger change than it looks" is right about
`qaCard` and wrong about `pageHeader` — and the two are different enough
that lumping them together is the actual mistake in the plan's open
question.

The load-bearing obstacle is real but it is **not** the one the plan
guessed. See "The obstacle" below: it is not that `qaCard` owns behaviour
in the abstract, it is one specific, checkable thing.

## Numbers

| | watch.py | tests/guards | notes |
|---|---|---|---|
| Build the vocabulary + fragment wrapper | +242 / −5 | 0 | 6 components, 2 emitters each |
| `pageHeader` → `heading` | +37 / −21 | **0** | net +16, nothing else touched |
| `qaCard` → vocabulary | +45 / −14 | **+6 / −2** in `dev/capture/qacard.mjs` | 4 of those CSS lines exist only to undo the components |
| **Total vs master** | +328 / −40 across 2 files | | |

Components built: `heading`, `label`, `quiet`, `note`, `chain`, `compare`,
`decision`. `qaCard` could use **three** of them (`heading`'s `.dq` title
element, `label`, `note`). It needed **none** of `chain`, `compare`,
`decision` — the three that are actually the vocabulary's reason to exist.

## What fell out naturally

**`pageHeader` is the vocabulary's `heading`, exactly.** The dashboard's
`<header class="htitlebar">` + `#meta` line and an artifact's `<h1>` +
`.sub` were the same component under two names. The composer's `+` opener
is just a gutter slot the artifact leaves empty:

```js
const pageHeader = (inner, sub) => vHeading(inner, sub, CMD_GUTTER);
```

Four view builders each moved their `<div id="meta">…</div>` into the
`sub` argument it always was, `#meta`'s CSS rule deleted in favour of
`.sub` (kept as an id alias so `#meta .q` and `dev/capture/pip83.mjs`
still resolve). **Zero test changes, zero guard changes, page renders
identically.** This is a rename, not a refactor.

**The prose furniture is the same story.** `.label` and `.quiet` were
already byte-identical strings in `watch.py`'s `STYLE` and in both
hand-written artifacts. Putting them in one `COMPONENT_CSS` spliced into
both the page shell and the artifact shell is pure deletion of a copy.

**The fragment wrapper works and is small.** `wrap_fragment()` is ~15
lines; `/reviewraw` grows a three-line branch on `.part.html`. A fragment
emitted purely from the Python `v_*` functions renders correctly with no
page errors (screenshot taken, chain/compare/decision/note all good).
Stage 1 of #112 is genuinely cheap.

## What fought back

### The obstacle: a card's class names are its addressing scheme, not styling hooks

This is the finding. `sendAnswer()` does:

```js
const anstext = card.querySelector('.anstext');
flipDock(anstext, fromRect, anstext.getBoundingClientRect());
```

`.anstext` is not a style hook there. It is **the address of the FLIP
hero inside a live card**. A vocabulary class is by definition reusable,
and therefore *cannot be unique within a card*. The moment `.anstext`
becomes `.note`, that `querySelector` stops being a guaranteed-correct
address and becomes a first-match guess — and it would break **silently**,
the first time a card contains a second `.note` (which is one markdown
feature away: a question body rendering a callout).

The fix is to keep a private hook alongside the shared class:

```js
const vNote = (inner, cls) => `<div class="note${cls ? ' ' + cls : ''}">${inner}</div>`;
// ...
vNote(mdInline(q.answer), 'anshero')
card.querySelector('.anshero')   // never '.note'
```

So **every vocabulary component the dashboard uses needs an "and also tag
it with this" parameter that exists purely for behaviour and that
artifacts will never pass.** That is the concrete shape of the plan's
suspicion, and it is worse than it sounds: the escape hatch is invisible
in the component's own contract, and forgetting it produces a bug no test
catches.

This *confirms* the plan's instinct but **refutes its stated reason**.
The problem is not "the vocabulary has nothing to say about behaviour" —
a component that emits static markup is perfectly usable inside an
interactive card. The problem is narrower and sharper: **shared class
names destroy uniqueness, and this card's behaviour depends on
uniqueness.** `holdRerenderUntil`, keying by index, and the submit
handlers turned out to be *irrelevant* to the unification — they never
touched the markup vocabulary at all. Only the morph's selector did.

### Every borrowed component needed its context to unsay it

Four CSS rules exist for no reason other than undoing defaults the
components brought with them:

```css
.qa .label { margin:.35rem 0 .15rem; font-size:.65rem; letter-spacing:.07em; }
.qa .note  { border-left:0; padding-left:0; margin:0; opacity:1; white-space:pre-wrap; }
.qa .dq    { margin:0; }
```

`.label` carries `margin: var(--space) 0 .5rem` (1.6rem) because it is a
*section* label on a 72ch reading page. Inside a dense card that is
absurd. `.note` carries an accent rail — but `.qa.awaiting` already has
one, so nesting them double-rails.

**A component that needs its context to unsay it is not shared; it is
forked with extra steps.** The components were sized for artifact
pages, and the card is a different density regime. This is the honest
cost and it is not one-off — it recurs for every future component the
card borrows.

### A visual regression the structural guard cannot see

After the change, the in-card "ANSWERED · AWAITING FOLD" tag and the
*section* label "ANSWERED · AWAITING FOLD (1)" render as the same
component at nearly the same size. A reader can no longer tell "this
labels a group of cards" from "this labels a field inside one card".
Both guards pass. Only the screenshot shows it.

### `just test` is not the net here

The rewired `qaCard` kept **55/55 green** while `dev/capture/qacard.mjs`
— the #105 structural guard, which is the *actual* guard for this
component — failed two assertions (`hasTitle`, `hasAnsTag`). The Python
tests check for token presence in the JS source; they cannot see
structure. Anyone doing this work for real must run the capture scripts,
and they are outside `just test`. Worth its own task.

Note the guard's *cross-surface* assertions all passed throughout: a
consistent rename cannot break "the dashboard renders the identical card
as /questions". Only the two absolute assertions caught it.

### Two emitters, always

The vocabulary has to exist twice — `v_*` in Python (artifacts render
server-side, once) and `vChain`/`vCompare`/`vDecision`/… in JS (the
dashboard re-renders live every ~2s in the client). There is no single
place to put it. I mitigated the worst of the drift by writing
`COMPONENT_CSS` once and splicing it into both documents, and by stamping
the chain's geometry constants from Python into the JS (`/*CHAIN_W*/620`
→ `re.sub`), but **the emitter bodies are genuinely duplicated** and only
a parity test can hold them together. Worse, the JS emitters use `esc()`,
which needs `document` — so they cannot be unit-tested in Python or node
at all. Parity testing requires playwright.

This is a standing cost of *any* dashboard/artifact unification, paid
before you get to `qaCard` at all.

## What this taught me about the artifact vocabulary itself

Three things, all found by looking at the render rather than the markup —
which is the styleguide's own recorded lesson, holding up again.

1. **`compare` is two components wearing one name.** A *decision* row
   labels each cell (`Rec — …` / `Alternative — …`) because the labels
   differ per row. A genuine *comparison table* (`DEPTH` / `LIVES IN`)
   wants its header pair once at the top. My emitter repeats the header
   on every row, which is right for `decision` and visibly wrong for a
   table — you can see `ARTIFACT` / `DASHBOARD` stuttering three times
   down the demo artifact. Split them, or give `compare` a
   `headers: 'once' | 'per-row'` mode.

2. **`compare`'s `point` flag is ambiguous and I implemented it wrong.**
   "This row is the point" should accent the *cell*, not the column
   label; my version lights the label. The markup read fine. Only the
   screenshot showed it. Name the flag for what it accents.

3. **`chain` generalised cleanly and is the strongest component.** Rows
   of `{depth, title, detail, aside}`, deepest row takes the accent,
   height computed from whether a row has a detail line. It reproduced
   the goal-hierarchies diagram's feel without any per-artifact
   coordinates. This is the one that will pay for itself immediately on
   #114.

**And the thing the human should notice:** the components `qaCard` could
*not* use are the three that justify the vocabulary (`chain`, `compare`,
`decision`), and the ones it could use are the three that are trivially
shared anyway (`label`, `note`, a title element). That asymmetry is the
answer. The vocabulary is for *arguing a design in prose and diagrams*;
the dashboard is for *operating a loop*. They overlap only in furniture.

## Recommendation

**Do the cheap half now, inside #112. Leave `qaCard` alone.**

- **Take**: `heading` (absorbs `pageHeader`), `label`, `quiet`, `note`,
  and one `COMPONENT_CSS` block spliced into both shells. ~+50 net lines,
  zero test changes, deletes a real duplicate, and it is already written
  in `2d429e1` if you want it. It also removes a live divergence risk:
  another dreamer is editing `pageHeader` right now.
- **Leave**: `qaCard`. Not because it is impossible — it works, it is
  committed, the page renders and both guards pass — but because the
  ledger is bad. It buys nothing (`qaCard` was already one component
  across four surfaces, which was #105's whole point) and it costs four
  undo-rules, an escape-hatch parameter on every component the card
  touches, a silent-failure mode in the morph's selector, and a flattened
  visual hierarchy.
- **Do not** put `expand`, `preB`/`linkify`, or `mdB` in the vocabulary.
  `mdB` is a markdown renderer, not a layout component, and artifacts
  hand-write their HTML — they have no use for it.
- **Fix `compare` before shipping the vocabulary** (finding 1 above);
  it is the component most likely to be used wrong on the first artifact.
- **File a task**: the capture scripts in `dev/capture/` are the real
  guards for the page's components but sit outside `just test`, so a
  change can be green and broken at once. This spike demonstrated it.

If `pageHeader` is taken, `watch-design.md`'s Components section should
say the heading is one component with a gutter slot, and that a card's
behavioural hooks (`.anshero`, `data-qkey`) are private addresses that
must never be a shared vocabulary class — that rule is the durable lesson
here regardless of what is adopted.

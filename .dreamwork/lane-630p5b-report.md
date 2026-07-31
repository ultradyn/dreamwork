# Lane 630 P5 stage 2 report — one `QaCard` wrapper

## Verdict and measurement first

`QaCard` was ready enough for this increment. The production builder exists at
`client/components.js:820-822`, returns one outer `.qa` card, and is called by
four production builder paths (`qSection`, `buildQuestions`, `buildReview`, and
`buildQuestion`). Its render-time ambient reads reduce to the mutable `data`
and `view` bindings; `rmr` is used by post-mount indicator painting rather than
card construction, and the emitted onclick only names the existing
`submitCard` function for a real dashboard to resolve later.

The real fixture measured 1,741 characters after DOM parse/serialization. The
mounted wrapper measured the same 1,741 characters, and strict equality passed
after both sides went through the same detached-template parser and serializer.
That supports the local wrapper increment. It does **not** answer whether
claude.ai/design presents a useful editable component.

One prerequisite is shakier than the plan records. `ds/index.js` concatenates
all client sources, whose top-level startup expects the dashboard shell. In a
blank document it threw `composer mount main missing #cmdpalette` and
`morphdom is not defined`; injecting it a second time into a running dashboard
initially threw `composer already mounted by main`. The equality guard therefore
mounts the exported wrapper in an isolated root in the real shell, after
clearing the shell's composer ownership marker for the design bundle's one
startup. This proves the wrapper and bundle locally, but it is also the precise
question the external ingestion spike must answer: does the design tool analyse
the export without requiring the dashboard startup environment, or does the
package need a later side-effect isolation increment?

## What changed

- Exported **only** `QaCard` from `dev/build/wrapper-exports.js`. It calls
  `qaCard(q, k)` and supplies/restores the bounded `data`/`view` context. It
  contains no fallback markup and no palette.
- Added `QaCard.d.ts`, `QaCard.prompt.md`, and `QaCard.fixture.json` as authored
  build inputs under `dev/build/ds-src/`; `just build-client` copies them into
  `client/dist/ds/`, and pytest checks each copy byte-for-byte.
- Added and registered `dev/capture/wrappereq.mjs`. Its assertions are:
  builder output non-empty; builder output contains `class="qa"`; mounted
  output clears the runtime-derived 1,740-character floor; strict normalized
  equality; and no browser page errors.
- Rebuilt `client/dist`. The standing manifest remains **14 inputs / 3 hashed
  executable outputs**. The three design-only companion files are copied and
  pytest-guarded rather than added to the deployed-output manifest: adding
  them there would require editing `watch.py`'s AST-literal `DATA_SIBLINGS`
  shipping tuple, which this lane is explicitly forbidden to touch. The
  executable wrapper lives in manifest-guarded `ds/index.js`.
- No other wrapper, route conversion, live-route mount, token value, palette,
  `client/*.js` source, or `watch.py` edit landed.

Commits after rebasing onto local master:

- `7ef03934` — `feat(#630): export one derived QaCard wrapper`
- `baf73d6b` — `fix(#630): register the wrapper equality guard`

## Red-proof, both directions

### Wrapper equality

Direction 1 changed only the wrapper result, replacing the fixture key with an
equal-length wrong key, rebuilt the design bundle, and ran the browser guard.
All three preconditions stayed green at 1,741 / 1,741 characters. The exact
discriminating failure was:

> `FAIL QaCard wrapper serialization strictly equals qaCard builder serialization`

Direction 2 constructed the requested wrong-but-consistent case: a component
can mount a captured copy of today's builder string through
`dangerouslySetInnerHTML`; after the shared parser/serializer, equality still
passes. Equality alone therefore **cannot distinguish derivation from
coincidental identity**. The source purity check catches the ordinary copied
tag-literal form, but an adversarial restatement split across string fragments
or imported from an ungoverned file evades that regex. The honest guarantee is:
equality permanently catches drift between the current builder and the shipped
wrapper over the fixture, while purity makes the normal second-renderer mistake
loud; neither is a semantic call-graph proof.

### Wrapper purity

Direction 1 planted `const FORBIDDEN_COPY = '<span>';` in the governed wrapper
source. The detector first found more than twenty real tag literals in
`client/components.js`, then failed on the intended assertion:

> `dev/build/wrapper-exports.js states markup of its own (['span']). A wrapper must CALL the builder`

Direction 2 is the fragment/import bypass above: a manually maintained string
can avoid a contiguous `<tag` literal. It is a real open false-green, not
claimed closed.

The exact lesson title consulted before injection resolved once:
**A red for the wrong reason is indistinguishable from a red for the right one
in a `-q` summary**.

`python3 dev/redproof.py check` after restoration reported:

> `check: clean — 4 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

## Verification

- Rebased cleanly onto local `master` `3d082c0d`; no hand resolution was
  needed. Post-rebase branch head before this report was `baf73d6b`.
- `just pytest test_client_dist.py` — **30 passed**.
- Focused browser guard `wrappereq` on ephemeral port `49013` — **PASS**;
  preflight load **24.84**, suite-start load **24.85** on 16 cores; runner
  confirmed **1 of 1 registered guards ran and judged**.
- `python3 lint.py` — **clean, 5 warnings**, matching the lane bar.
- `client/dist` — **OK, 14 inputs and 3 outputs**.
- No other existing browser guard asserts wrapper/builder equality. The new
  `wrappereq` guard is the precise coverage for the changed surface.

## External ingestion step still owed to Max

Upload the contents of `client/dist/ds/` to claude.ai/design: `index.js`,
`styles.css`, `QaCard.d.ts`, `QaCard.prompt.md`, and
`QaCard.fixture.json`. Render the fixture and judge both whether the export is
accepted and whether the string-mounted card is usefully editable at component
granularity. Also observe whether preview execution tolerates the concatenated
client startup assumptions described above. That authenticated upload is the
end-to-end signal; this lane did not attempt it and does not claim it passed.

## Issue evidence relied on

- `#630`: **"Stage 2 (wrapper exports, .d.ts, .prompt.md, fixture props) is
  next and §6-R5 still binds it: run ONE wrapper end-to-end through the design
  tool before authoring the rest."** This bounds the increment to `QaCard`.
- `#651`: **"a guard's message must name a mode the guard can actually detect,
  and the way to know is to construct that mode and watch it fail."** This is
  why the report quotes the discriminating failures rather than red counts.
- `#440`: **"a single supported way"** is the relied-on rule; this increment
  keeps one `qaCard(q, k)` render path and one styling source.

## DOGFOOD REPORT

The highest-value finding is the design bundle's startup assumption. The P1
story says concatenating the client sources is harmless for a tool with no
dashboard, but execution on a blank canvas fails before `DreamworkDesign`
becomes available because those sources expect dashboard DOM and morphdom.
The new guard had to expose this before it could judge equality. The external
spike should treat side-effect isolation as a first-class observation, not
only visual editability.

The brief also contains a narrow reporting tension: it supplies an absolute
coordinator `inbox.md` path and says to append there, while the boilerplate
says the lane writes its report and nothing else so the coordinator owns the
hand-off line. I treated `inbox.md` as the explicit delivery channel distinct
from the forbidden shared `.dreamwork/handoffs.md`; I did not touch
`handoffs.md`.

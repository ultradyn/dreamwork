# #630 P5 stage 1 lane report

## Verdict

**Chosen shape: derive from `client/style.css`.** The sole palette remains the
served stylesheet. `client/tokens.css` is a value-free tooling entrypoint that
imports it, `client/conventions.md` tells the design tool and component authors
to extract the imported `:root` custom properties, and the existing
`just build-client` path copies the same source byte-for-byte to
`client/dist/ds/styles.css` under the SHA-256 manifest guard.

I rejected making a new token file the source. The served page embeds
`client/style.css`; consuming an external token source would require either an
external CSS fetch, a second hand-maintained composite, or a change to the
asset loader/build machinery outside this lane's ownership. The first changes
the single-response page, the second creates the two truths this increment is
meant to avoid, and the third exceeds stage 1. The derived shape preserves one
supported answer to “what colour is this?”: read the declaration in
`client/style.css`. `tokens.css` deliberately contains no declaration/value.

**The served page did not change.** Fresh servers on ephemeral ports `:54533`
and `:43199` returned byte-identical `GET /` bodies: 773,674 bytes, SHA-256
`3fd3bb50618f4ca441a820e46ad931c1240497f184555679ecbdf75a02791c82`.
The check asserted its own preconditions before `cmp`: `client/style.css` was
non-empty (126,517 bytes), `<style>` was present, and the page exceeded a floor
computed at runtime from the real client assets (610,380 bytes).

This shape does not make stage-2 wrapper purity harder. It keeps styling
outside wrapper source, so a delegating wrapper can remain a call plus a mount
boundary with no tag literal or copied token value. Stage 2 was not started.

Implementation commit after the final required rebase: `5caacb0ce49f5b5182ffc184d6e29ddf67678874`.

## What changed

- `client/tokens.css`: an import-only claude-design token entrypoint; no token
  values are restated.
- `client/conventions.md`: the compact design-tool contract: styling authority,
  token intent, motion/focus expectations, and the stage-2 delegation rule.
- `client/dist/`: rebuilt with the supported recipe. Its bytes remained current;
  lint reports `OK client/dist matches 14 inputs and 3 outputs`.

The governing task says: **#630** P5 is “Stage 1: tokens + `styles.css` +
`conventions.md`” and stage 2 begins with wrapper exports. The scope ruling in
**#668** says, verbatim, “He did not touch the on-disk master state rule, which
stays exactly as strict as it was.” That is why this increment exposes the
existing palette instead of checking in a parallel value list.

## Red proofs

### Direction 1 — ordinary source/output drift

Before injection I ran `python3 dev/lessons_index.py --act red-proof`, then
armed `client/style.css` with `dev/redproof.py`. I changed `--bg` from
`#0b0f19` to `#0b0f1a` without rebuilding. The discriminating lint result was:

> `ERROR client/dist client/dist was built from different bytes: client/style.css — run just build-client`

`dev/redproof.py restore` restored the lane-private snapshot and verified it;
the dist was rebuilt from the restored original.

### Direction 2 — wrong but internally consistent

I renamed the declaration `--bg` to `--background` and renamed every
`var(--bg)` consumer in the same stylesheet. `client/tokens.css` remained
consistent automatically because it imports that source rather than listing
names or values. Before rebuild, lint correctly reported the same stale-input
ERROR. After `just build-client`, it reported:

> `OK client/dist client/dist matches 14 inputs and 3 outputs`

This is the requested open false-green: once the wrong source and all current
consumers agree and the derived artifact is rebuilt, a present-tree staleness
guard cannot know the historical/original name was right. Closing that would
require an independent semantic oracle, which would itself become another
authority unless the human explicitly pins such a compatibility contract.

Final hand-off gate:

> `check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

## Verification

- `just pytest test_client_dist.py test_client_assets.py` — 38 passed. The
  relevant assertions bind that dist styles byte-equal the served stylesheet,
  both sides contain a runtime-derived custom-property sentinel, the page is a
  non-vacuous real assembly, and committed dist matches its inputs/outputs.
- `python3 lint.py` — before rebase, clean with the required 5 warnings and
  `client/dist` OK. After rebasing to current master, **5 ERRORs / 5 WARNs**:
  every ERROR is the persisted-brief absolute-inbox check, across
  `630-cx-630p5.md`, `631-glm-631i3.md`, `645-cx-645i6.md`,
  `765-cx-765holds.md`, and `769-glm-769echo.md`; `client/dist` remains OK.
  The worktree interpreter against the live main target reports the same five
  ERRORs (and one live-target warning), proving they are upstream/current-master
  state rather than this branch's client change. Historical briefs are outside
  lane ownership and the brief expressly forbids rewriting them.
- Browser guard: none in `dev/capture/` covers an off-page design-tool
  entrypoint or conventions document. I do not claim browser-guard coverage.
  The exact fresh-server `GET /` comparison above directly binds the narrower
  claim that the served page did not change.
- Rebase: local `master` moved from the stated base
  `bc7aab6b8e6f7e48ec74340af98e9c06a17dd995` to
  `24b45a3f6cf357f047a91a301dc3ab17039f9e7a`, then advanced again to
  `4db4a02eafd68f07a94c1c5220246e5234afcbb3`; both rebases completed without
  a content conflict. The persisted brief/receipt blocked the first checkout as untracked
  files, so I preserved them in lane-private scratch and restored them
  byte-for-byte; their receipt matches
  `dc09136402670fe568c8c6d9ee1fa050668a928c43cd428a0bd832226b2de7e6`.

## Issue readings relied on

- **#440** does **not** support the brief's colour-specific parenthetical. Its
  actual line is “a single supported way to fold an entry.” The direct brief
  constraint and #668's one-fact/one-home ruling still govern this work, but
  #440 is a miscitation here.
- **#755** says “Do not silently rewrite his prose”; applied here, conventions
  describe authority without manufacturing a replacement palette.
- **#671** says zero entries must report `DID NOT REVIEW` rather than “nothing
  to review”; the page and stylesheet comparisons therefore assert non-empty,
  runtime-derived preconditions.
- **#136** distinguishes “present-but-unparseable” from genuinely empty; the
  token entrypoint is checked for a real import and no local declarations.
- **#702** describes “two lists with different id grammars, one silently
  fatal”; its relevant general warning is why no second token-name/value list
  was introduced.

## Out of scope

- A semantic oracle that says `--bg` is the historically/rightly named token
  does not exist. The direction-2 construction demonstrates that explicitly.
- Stage 2's `QaCard` wrapper, declarations, prompt, and fixture props remain
  untouched, as required.

## DOGFOOD REPORT

The brief's measured stylesheet size was stale twice over: it says 1,798
lines, the plan records 1,927, and the actual branch point was 1,974. This did
not affect the design because the checks derive sizes at runtime.

More importantly, **#440 is a real citation defect**: the issue is about the
one supported ledger-fold writer, not one supported way to know a colour. The
brief's prose states the desired colour-authority constraint clearly enough to
act, and #668 supplies the applicable doctrine, but a lane following the issue
number finds unrelated evidence.

The rebase rule also collided with the dispatch-persistence mechanism: local
master had gained tracked copies of the same brief/receipt that remained
untracked in the lane, so `git rebase master` refused before detaching HEAD.
The safe recovery was lane-private move → rebase → restore and hash-verify.
That case is not described in the boilerplate, though persisted briefs make it
predictable for any lane whose master advances past the coordinator's
brief-persistence commit.

That same master advance invalidated the brief's promised lint bar: before
rebase the lane met exactly 5 warnings and no ERRORs; afterwards current master
itself has five absolute-inbox brief ERRORs, including this lane's persisted
brief. The boilerplate simultaneously says historical briefs must not be
rewritten, so the lane cannot both repair the bar and obey scope. I left the
upstream defect untouched and named every failing file above.

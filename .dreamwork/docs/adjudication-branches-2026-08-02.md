# Branch-content adjudication — 2026-08-02

## Verdicts

| Branch | Verdict | Recommended disposition |
|---|---|---|
| `cx-691recap` | **Content is on `master` under a different document and sha.** The exact 463-line file is absent, but all eight feature-defining decisions are in the canonical 675-line `main-agent-recap.md`. | Do not land a second design. Retain the ref only until this adjudication is accepted, then discard it under the coordinator's branch policy. |
| `glm-646policy` | **Content is on `master` under different shas.** Three source/test commits are patch-equivalent; the sole `+` is only a generated bundle rebuild, and current `master` contains both the feature and a self-consistent newer bundle. | Discard; landing it would roll generated and source files back. |
| `opus-863jank2` | **Content is on `master` under different shas.** The guard commit is patch-equivalent and all 68 source/guard lines added by the `+` commit occur exactly on `master`. Its committed bundle is stale against two of three changed inputs. | Discard; especially do not trust or land its `dist`. |

No branch is genuinely unlanded at the feature-content level. Therefore there
is no unique work here to preserve or land. The branch refs remain untouched by
this lane.

## Scope, method, and changed premise

I examined exactly **three refs** against local `master`: `cx-691recap`,
`glm-646policy`, and `opus-863jank2`. For each I counted every `git cherry -v`
row, every unique path touched by the divergent commits, and then checked the
feature at the production/document sites. A `+` was treated only as a prompt
for content inspection.

The live ledger contradicted the dispatch premise before analysis began. The
`#911` record still says, quoted, **"THREE ARE NOT"** accounted for, while the
records for the three underlying tasks already say:

- `#691`: **"BRANCH CLASSIFIED — cx-691recap ... is a SUPERSEDED DUPLICATE;
  do NOT merge."**
- `#646`: **"Landed 1c7f015b"** and later **"BRANCH CLASSIFIED —
  glm-646policy ... is a SUPERSEDED DUPLICATE; do NOT merge."**
- `#863`: **"BRANCH ADJUDICATED — opus-863jank2 ... is SUPERSEDED; do NOT
  merge."**

Those notes were leads, not evidence for the verdicts below. Their coexistence
with the stale `#911` premise is itself a correct-when-written state-drift
instance. I did not mutate the single-writer ledger.

## `cx-691recap`

### Verdict

**Already on `master` by content, as a canonical fold-in rather than the same
file or an equivalent patch.** Do not land `recap-design.md` as a second design.

### Evidence and denominators

`git cherry -v master cx-691recap` examined **3 commits**: **3 `+`, 0 `-`**:

> `+ 599e8b7a design(#691): refresh cheap-model recap design`
>
> `+ 633e02cd design(#691): tighten recap invariants`
>
> `+ 918215d8 design(#691): follow canonical store composer`

Those three commits touch **1 unique path**. An explicit existence check
examined that **1/1 path** and reported:

> `MASTER_PATH MISSING .dreamwork/docs/plans/recap-design.md`

That proves the exact file is absent; it does not prove its design is absent.
I therefore compared its **8/8 bullets** under `Decision in one page` with the
canonical plan on `master`:

| Branch decision family | Canonical `master` evidence |
|---|---|
| pulse-driven 40%-offset serial sidecar | `main-agent-recap.md`, scheduling seam: the survivor is **"a `tee` leg on the existing pipeline"**, with `40% of 285 s = 114 s` |
| absent-by-default `model`/`every` gate and fixed ccc argv | feature-gate section: **"Tracked `.dreamwork/recap`"**, `model: glm52`, `every: 1`, and **"There is deliberately no arbitrary `runner:` shell string"** |
| recorded session identity, resolver, no fallback | source section: **"pass it to the existing `session_source.resolve` seam. Accept only its `live` result ... There is no fallback."** |
| existing session-log projection, including compaction markers | digest/compaction sections: **"The projector consumes the existing `session_log` service/scanner"** and drops compact-summary records |
| 24 KiB assembled-prompt cap, head 1/3 + tail 2/3 | cap section: **"Cap: 24 KiB of assembled prompt"** and **"Split 1/3 head, 2/3 tail"** |
| v4 `RecapRepository` in the canonical store composer | DB section: **"Add a `dreamwork_db.recaps.RecapRepository`"** to `dreamwork_store_spec` and **"do not create a rival `recap_store_spec`"** |
| attempt log and honest dashboard failure/freshness states | DB/failure sections specify the same `recap_attempt` shape, committed `running` row, stale/failure states, and repository DTO |
| recap-id-gated cross-dissolve | transition section: **"Gate on `recap.id`, never on the tick"** and reuse the existing content cross-dissolve |

Thus the semantic denominator is **8 decision families examined, 8 present, 0
missing**. The canonical file is also not an accidental look-alike:

- Its opening reconciliation note explicitly says **"This remains the one
  design of record"** and **"The unmerged `cx-691recap` branch is provenance
  for corrections folded below"**.
- `.dreamwork/docs/doc-map.md` names `main-agent-recap` in both the plans
  inventory and its own detail row; searching the doc map for the two candidate
  names examined **2 names**, found `main-agent-recap` at **2 sites**, and found
  `recap-design` at **0**.
- The branch's three commits ended at 14:02. The canonical file then received
  `docs(#804): reconcile recap design with canonical seams` at 14:33. This is a
  later fold-in, not an older document that merely resembles the branch.

### What would be lost and recommendation

Deleting the ref would lose the exact alternate 463-line wording and its
commit-level provenance, but **no authoritative design decision**: the 8/8
decision inventory is in the maintained 675-line plan. Landing the file would
instead create two claimed designs for one feature and contradict the canonical
file's explicit one-design-of-record note. Recommendation: **discard as a
landing candidate; do not merge it.** Preserve the ref only until the
coordinator accepts this evidence.

## `glm-646policy`

### Verdict

**Already on `master` under different shas.** The only non-equivalent commit is
a generated rebuild of source whose feature commits are already equivalent.

### Evidence and denominators

`git cherry -v master glm-646policy` examined **4 commits**: **1 `+`, 3 `-`**.
The three `-` rows are the route/helpers, the textbox UI, and their tests. The
one `+` row is:

> `+ f7ffe079 feat(#646): rebuild client/dist bundle for the new policy control`

That commit changes exactly **3 generated files and 0 source/test files**:

> `25  0  client/dist/ds/index.js`
>
> `29  0  client/dist/ds/styles.css`
>
> `5   5  client/dist/manifest.json`

Across all four divergent commits I enumerated **8 unique touched paths**;
explicit blob lookups found **8 present, 0 missing** on `master`.

The feature itself is present. I examined its **5 historical source/test
paths** on `master`: `watch.py` had 37 matching lines, `client/router.js` 41,
`client/style.css` 14, `client/views.js` **0**, and `test_watch.py` 118. The zero
is deliberate and loud: later client extraction moved the control's markup out
of `views.js`, while the live implementation remains visible at these sites:

> `client/router.js`, `subagentPolicyPicker`: `<textarea ...
> id="spolicy-field" ...>` plus explicit `save` and `reset` buttons.
>
> `client/router.js`, `commitSubagentPolicy`: `fetch('/subagent-policy', ...`
>
> `watch.py`, `delete_subagent_policy`: `os.unlink(path)` with distinct absent
> and failure outcomes.

I also checked the generated surface rather than assuming source implies a
bundle. Across **2 generated files**, current `master` contains 8 policy-control
token hits in `client/dist/ds/index.js` and 5 in
`client/dist/ds/styles.css`. Manifest verification examined **3 relevant
inputs and 2 outputs** on each tree:

- `glm-646policy`: **3/3 input hashes and 2/2 output hashes match**. Its `+`
  commit is a real build, but a build of already-equivalent source.
- `master`: **3/3 input hashes and 2/2 output hashes match**, and it contains
  newer unrelated client work.

### What would be lost and recommendation

Nothing unique would be lost. The source, tests, and generated feature are on
`master`; the branch's only `+` is an older internally-consistent bundle.
Recommendation: **discard; do not land the rebuild**, because doing so would
replace a newer valid bundle with an older one.

## `opus-863jank2`

### Verdict

**Already on `master` under different shas.** The guard is patch-equivalent,
every source/guard addition in the WIP commit is present exactly, and its
warning about `dist` is correct.

### Evidence and denominators

`git cherry -v master opus-863jank2` examined **2 commits**: **1 `+`, 1 `-`**:

> `- 32e591db guard(#863): sample the answer box every frame across a submit`
>
> `+ 0ba86a56 wip(#863): preserve lane A's three-cause fix, UNBUILT — do not trust dist`

Across both commits I enumerated **6 unique touched paths**; explicit blob
lookups found **6 present, 0 missing** on `master`.

For the `+` commit I extracted every added source/guard line from its **4
non-generated paths**, then compared each exact full line with the corresponding
`master` blob using a full-stream equality check:

| Path | Added lines examined | Exact on `master` | Missing |
|---|---:|---:|---:|
| `client/router.js` | 15 | 15 | 0 |
| `client/style.css` | 28 | 28 | 0 |
| `client/views.js` | 22 | 22 | 0 |
| `dev/capture/qjank.mjs` | 3 | 3 | 0 |
| **Total** | **68** | **68** | **0** |

The three production causes are independently visible at **4/4 checked sites**
(three fixes plus the guard's positive control), one match at each:

> `client/router.js`: `el.style.overflow = 'clip';`
>
> `client/style.css`: `.qa { margin:.6rem 0 1rem -.9rem;
> padding-left:.9rem;`
>
> `client/views.js`: `function travelQuestionColumn() {`
>
> `dev/capture/qjank.mjs`: `control: travelCard actually armed its inline
> overflow ...`

The generated warning is also measurable. I compared the WIP manifest with
the actual branch blobs for **3 changed client inputs**: router matched, while
style and views mismatched (**1/3 match, 2/3 mismatch**). Its **2/2 output
hashes** match only that stale generated output. Current `master` is
self-consistent at **3/3 inputs and 2/2 outputs**. Therefore the source fix is
preserved but the WIP bundle cannot represent all of it.

### What would be lost and recommendation

Nothing unique would be lost: the guard commit is patch-equivalent and the WIP
adds 68/68 source/guard lines already present on `master`. Recommendation:
**discard; do not land**, especially not the manifest or bundle whose own input
hashes prove it stale.

## False-green controls (the adapted red-proof)

The brief explicitly replaces production sabotage with content-proofing for
this document-only lane, so I did not run `dev/redproof.py` or inject a defect.

**Direction 1 — the claimed master content is directly observable.** The
evidence above names the canonical recap decision sites (8/8), the policy UI,
route, reset, source/test population and built bundle, and all three jank fixes
plus their guard (68/68 exact additions and 4/4 feature sites). A verdict cannot
pass merely because a sha is reachable or `git cherry` printed `-`.

**Direction 2 — attempted false greens:**

1. Treating `cx-691recap`'s missing path as missing content would pass over the
   canonical differently-named plan. Comparing both candidate plan names and
   all eight decisions closes it.
2. Treating `glm-646policy`'s three `-` rows as the whole answer would ignore
   the `+` bundle. Inspecting its exact 3-file population, the feature sites,
   and both trees' 3-input/2-output manifests closes it.
3. Finding jank strings in `dist` could pass with a stale bundle. The WIP's
   2/3 input-hash mismatch demonstrates that false green; the verdict rests on
   68/68 source/guard lines and `master`'s 3/3 + 2/2 manifest instead.
4. An early exact-line probe used `rg -q` in a `pipefail` pipeline; `rg` exited
   after a match, upstream `git show` received SIGPIPE, and real matches read
   as absent. The contradiction with an explicit site check exposed it. The
   reported 68/68 result comes from a corrected full-stream `awk` comparison.

No open uncertainty remains about the three feature verdicts. The only policy
choice left is when the coordinator considers the retained duplicate refs safe
to remove; this lane deliberately did not make or apply that choice.

## Rebase and verification

This section will be finalized after rebasing the report commit onto the final
local `master` snapshot. All three verdicts will be rechecked because any of
the refs could land while this report is being written.

- **Named tests:** none. This lane changes one Markdown report and no code.
- **Deliberately not done:** no merge, cherry-pick, branch deletion/prune,
  force-update, push, build, browser guard, live-ledger mutation, status write,
  or `attn` call.

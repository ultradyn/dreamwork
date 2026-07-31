# Lane #753b report

## Verdict

Fixed and verified. `open_section_text` keeps the column-0 section anchor while
again tolerating trailing whitespace on `## Open`. The sweep report now carries
the open-id / parsed-body-id pair unconditionally and refuses to issue any
landing verdict when the two projections name different ID sets. The refusal
reports both missing and unexpected IDs by name.

The detector lives in `sweep_text`, not `lint.py`: this is the consumer whose
`nothing to review` verdict becomes unreliable, and it already materializes
both projections. That preserves #440's one-supported-way rule and leaves the
well-pinned pure `sweep(text, commits) -> (n, findings)` contract unchanged.

Commits after the final rebase onto local `master`:

- `5fcbcb9b` — `fix(#753): preserve whitespace-tolerant open headings`
- `3164f693` — `feat(#753): refuse sweep on projection disagreement`
- `d9b8f8e1` — `test(#753): pin sweep body coverage header`

## Changes

- `ledger_parse.open_section_text` now compares
  `ln.rstrip() == "## Open"` inside the existing
  `ln.startswith("## ")` column-0 gate. A trailing space or tab is accepted;
  an indented body heading remains body content.
- `sweep_text` compares `{int(id) for id in watch.parse_ledger(...)[0]}` with
  the exact keys parsed into its body map. Set equality is deliberate: equal
  counts can still conceal different IDs.
- The standing header now prints `N open ids (...) / M parsed body ids` even
  when equal, following #682's examined-vs-understood precedent.
- On any set disagreement it returns before rendering findings or the clean
  sentence, with e.g. `1 open id(s) missing parsed bodies: #7` and/or
  `1 unexpected parsed body id(s): #2`.

## Red-proof

### Trailing-whitespace hardening

Before the fix, the new fixture changed only `## Open` to `## Open ` and failed
with the discriminating message:

> `AssertionError: a trailing space on the column-0 ## Open heading hid the entire Open section`
>
> `assert None == <the normal Open section>`

After the fix, both trailing-space and exact headings return identical section
text. The opposite property also remains pinned by the first-half test: an
indented ` ## What to build` does not terminate Open, and the later `#753`
entry remains present by ID.

### Independent projection detector — Direction 1

With the column-0 section anchor still fixed, the fixture introduces a
different parser disagreement: column-0 prose starves `#1`'s body, followed by
the malformed head `- **stage #2**`. `watch.parse_ledger` sees open IDs `{1}`;
the broader `ledger_entries` grammar produces body IDs `{1, 2}`. This is not
the indented-heading defect.

Deleting only the new refusal made the test fail with:

> `sweep reported a verdict despite disagreeing projections:`
> `... against 1 open ids (markdown) / 2 parsed body ids ...`
> `sweep: nothing to review (this ran — see the examined count above)`

The restored code instead says `DID NOT REVIEW`, names
`1 unexpected parsed body id(s): #2`, and does not contain the clean phrase.

### Direction 2 — the remaining false-green

A duplicate-ID ledger has two `#1` entry heads: the first does not cite
`abc1234`; the second does. Both readers collapse to one ID/key, so the header
honestly says `1 open ids / 1 parsed body ids`; the later body overwrites the
first and sweep still prints `nothing to review`. Thus this detector cannot
prove body completeness or uniqueness when both projections collapse the same
way. That is intentionally not duplicated here: duplicate-ID integrity has a
separate supported guard, while this check owns projection disagreement.

`dev/redproof.py check` after both injections:

> `check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

## Heading symmetry audit

- `open_section_text` now tolerates trailing whitespace on `## Open`.
- Its `ln.startswith("## ")` boundary already tolerates trailing whitespace on
  `## Recently landed ` and any other real column-0 section heading.
- `watch.parse_ledger` tolerates trailing spaces/tabs on both headings too, so
  there is no remaining trailing-whitespace disagreement.
- A separate disagreement remains: watch's heading regexes also tolerate
  *leading* spaces/tabs, while `open_section_text` deliberately requires
  column 0. That is the same ambiguity the first half fixed, is outside this
  lane's off-limits `watch.py`, and should be named as a reader disagreement.

## Verification

- Before changes: requested four-file suite — **649 passed** in 71.92s.
- After changes and final rebase: requested four-file suite — **651 passed**
  in 77.15s.
- Focused ledger/sweep suites — **96 passed**.
- Bare worktree `python3 lint.py` — **clean (6 warnings)**; four warnings are
  explicit worktree/store refusals because the gitignored live store does not
  travel.
- Worktree interpreter against the live checkout:
  `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork` —
  **clean (2 warnings)**, the existing questions-resolution and lessons
  near-duplicate warnings.
- `python3 dev/redproof.py check` — clean, two injections restored and absent
  from all three branch commits.
- Live store sweep, run through this worktree's interpreter:

  ```text
  sweep: examined 274 commits since 5817617c4205 against 171 open ids (store) / 171 parsed body ids (261 id-bearing, 13 skipped, mostly other #N)
    #753 — `2635eb6a` test(#753): pin sweep body coverage header, `07e5e905` feat(#753): refuse sweep on projection disagreement, `cdead2c5` fix(#753): preserve whitespace-tolerant open headings
  sweep: 1 open id(s) git names (verb form) that the entry does not cite
  warnings: 171 open tasks · 5 unanswered questions · 248 untyped
  ```

The live pair is **171/171**, so the refusal did not fire on a healthy ledger.
The quoted shas are from the live run immediately before the final rebase; the
current rebased commit shas are listed at the top of this report.

## Issue evidence read

- #753: “Keep BOTH properties: the column-0 anchor on `ln.startswith("## ")`,
  and whitespace tolerance on the comparison via
  `ln.rstrip() == "## Open"`.”
- `lessons.md:3311`: “The real cause was in neither the check nor the data but
  in the projection between them.” This is the layer the new set comparison
  instruments.
- #671: “Every tick since the store cutover has been getting a confident empty
  answer from the primary landing-discovery route.” The new disagreement path
  cannot emit that clean sentence.
- #702: “Malformed task ids are KEPT and reported loudly rather than reaped as
  dead.” The refusal likewise names every unclassifiable ID rather than only a
  count.
- #682: “examined-count is not matched-count.” The body pair is carried in the
  header for the same reason.
- #440: “a single supported way to fold an entry.” One detector lives at the
  corrupted verdict, not in both sweep and lint.
- #404: “a sweep that finds nothing must be distinguishable from one that did
  not run.” Projection disagreement now differs from both.
- #136: “present-but-unparseable is a fault and must look like one.” The
  refusal and the clean result render differently.
- #607: “The path you invoke is the INTERPRETER; `--target`/`--ledger` is only
  the SUBJECT.” All live after-runs used the worktree interpreter.
- #589: “Blank must be a VALID answer that is STATED, never an omitted
  section.” The dogfood section below is explicit.

## Rebase and scope

Local `master` moved repeatedly during the lane. I rebased onto it three times;
all rebases were clean and required no hand resolution. No live ledger mutation,
merge, push, port bind, or `attn` invocation occurred. No off-limits file was
changed. `BRIEF.md` remains the coordinator-provided untracked input.

## Out of scope

- The leading-whitespace disagreement with `watch.parse_ledger` described
  above remains.
- Column-0 prose can starve an entry body without changing either ID set. The
  new detector cannot see that content-level loss.
- Duplicate IDs can collapse identically in both readers and remain a false
  clean here; the existing uniqueness guard is the supported home for that
  class.

## DOGFOOD REPORT

The task's Direction 1 text implied that the live column-0-prose starvation at
`lessons.md:3311` would itself make the two sweep counts disagree. It does not:
the entry head has already entered the body map before column-0 prose truncates
its content, so both ID sets still agree. To build the requested independent
red-proof without returning to the heading defect, the fixture combines that
real starvation shape with the broader `ledger_entries` head grammar, producing
an unexpected `#2` body ID. The brief should distinguish **ID projection loss**
(which this detector catches) from **body-content starvation** (which it cannot);
calling both “an entry unparseable” obscures the boundary the Direction 2
exercise is specifically meant to expose.

The task also says bare `python3 lint.py` should reproduce the live clean bar.
In a lane it correctly produces `clean (6 warnings)` because the store is
gitignored; the meaningful two-warning bar requires the worktree interpreter
plus explicit live `--target`, exactly as #607 says. The prior #753 report
already identified this wording friction, and it remains present in the second
half's verification text.

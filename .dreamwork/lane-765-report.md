# Lane 765 report

**Measurement first: the frozen live snapshot contains 17 recorded hold claims;
13 name a releaser and 4 are prose.** The distribution is not the reason to add
a new lint check, because 12 of the 13 named claims already have canonical
`depends(task, needs)` rows, while the remaining named claim lives inside an
explicitly opaque `queued_dispatches.note`. A check confined to this lane's
owned files would either duplicate the dependency graph or parse prose.

## Verdict

MEASURED; BUILT NOTHING. This is the complete outcome.

The useful implementation boundary already exists for ledger blockers: use the
`depends` relation, not the words in `blocked_on`. It does not yet exist for
queued-dispatch holds: `ids` names the queued subjects and `note` is opaque;
there is no structural field naming the release task/event. Adding a lint regex
over that note would recreate the false-attribution defect this task forbids.

The future increment, if wanted, is therefore a data-format/writer increment,
not a `lint.py` increment: add one canonical structured releaser field to a
queued dispatch, write it through the supported status writer, document it, and
only then teach lint to compare that field with ledger state. That work is
outside this lane's ownership and should not be smuggled in as a reader-only
change.

## Frozen measurement

I copied the live `tasks.md` shim and `status.json`, and used SQLite's backup
operation for `ledger.sqlite3`, under:

    /home/xertrov/.cache/ud-dreamwork/lane-scratch/ud-dreamwork/cx-765holds/measure

The kernel reports that scratch directory as `btrfs`. Snapshot hashes:

    tasks.md       a9c7ebcb0e11b60efc2c717a083cd1c21bfe8f01ea61c61a4d6f6253840998d1
    status.json    78c535c2ada6ad25f6cccddafa79bed4effaaf5372cca41afc1d8fe55906392e
    ledger.sqlite3 9b74c18a345d3da1f93bbd4e6c2942427fd586e2e2a5b45e0aafd80400ae168a

The snapshot held 165 open tasks and five queued-dispatch entries.

| Surface | Recorded holds | Named releaser | Prose / unclassifiable | What the structure can decide |
|---|---:|---:|---:|---|
| ledger `blocked_on` | 15 | 12 | 3 | all 12 named rows also have matching `depends` edges |
| task titles | 0 | 0 | 0 | no current title asserts that its task is held |
| `queued_dispatches.note` | 2 | 1 | 1 | 0: both facts are inside opaque prose |
| **total** | **17** | **13** | **4** | **12 named facts are structural today** |

The 12 task releasers are six distinct ids. Nine edges point to open tasks;
three (`#240 -> #241`, `#257 -> #241`, `#259 -> #241`) point to landed `#241`.
That does **not** prove the holds expired; it proves only that the named
releaser landed and the three claims now require re-evaluation.

The queued holds were:

- `#631`: “Increment 10 (derived cache) sits BEHIND #645's guard prerequisite.”
  This manually names `#645`, which was open in the frozen snapshot, but no
  status field carries that relation.
- `#736/#628`: “phase 2 - HELD on load (#666).” The release condition is load,
  not task `#666`; this is prose and cannot be decided from task state.

No title was an actual hold claim. A broad title proxy over the brief's words
(`held`, `blocked`, `not parallel`, `waiting on`) named five titles — `#188`,
`#193`, `#465`, `#623`, and `#765` — and all five were descriptions or
metacommentary, not current holds. In queued notes the same proxy found only the
load hold and missed `#631`'s “BEHIND” wording. In `blocked_on` it would fire on
all 15 rows, including nine whose named dependencies remain open and three
human holds it cannot evaluate. The word check is therefore false-positive on
healthy input and false-negative on a real hold in the same snapshot.

## Why no check shipped

There is no precise reader-only check spanning all three surfaces:

1. Ledger named releasers are already structured in `depends`; parsing the
   duplicate `blocked_on` prose would create a second truth.
2. Titles contain no live hold to govern, while the word proxy names five
   healthy titles.
3. `queued_dispatches.note` has no releaser field. Parsing wording would miss
   the measured “BEHIND” form unless the regex widened, which multiplies false
   attribution. Treating every note as unclassifiable would print five rows for
   two holds and train the reader to skip them.

The measurement does show that a structural feature would govern most claims:
13/17 manually name a releaser. But 12/13 are already represented by the
dependency graph. The net new governed surface from a `lint.py`-only change is
therefore 0/2 queued holds, not 13/17 total holds. Ceremony now would buy no
decision.

## Direction 1 and direction 2

No check was added, so there was no direction-1 injection and no red-proof to
claim. `dev/redproof.py check` is still run as the hand-off gate below.

The equivalent direction-2 obligation is the future implementer's likely
mistake: **“named releaser landed” does not entail “real hold expired.”** A
valid fixture is task A structurally held on task B, with B landed, while A's
substantive release condition still awaits deployment, a human ruling, or a
follow-up slice B did not deliver. The correct output is “B landed; re-evaluate
A's hold,” never “A is unblocked” and never an automatic mutation. The three
live edges to landed `#241` demonstrate the observable half of that fixture;
their bodies do not let automation decide the substantive half.

## Line-count impact

No check was added. On the dispatched base and immediately before rebase,
`python3 lint.py` remained `clean (5 warning(s))`: before 5, after 5. No new
healthy-input line was introduced, and the existing “ledger checks examined
nothing” warning still names seven checks rather than pretending a new check
ran against a store that does not travel to the worktree.

After rebasing, the newly tracked brief corpus from `master` moves the branch
to `5 error(s), 5 warning(s)`: five persisted briefs have no absolute inbox
path. That is an upstream gate regression from `24b45a3f`, not a line-count
effect of this report; it is named below rather than rounded into the lane bar.

## Verification

- Branch point and initial local `master` were both
  `bc7aab6b8e6f7e48ec74340af98e9c06a17dd995`; `origin/master` was
  `ad6ee0d0a1be9f3dc6fdde6c977eb33ef93754e3`.
- Local `master` advanced once to
  `24b45a3f6cf357f047a91a301dc3ab17039f9e7a`. Rebase initially refused
  because that commit had begun tracking the two byte-identical dispatch
  receipt files still untracked in this worktree. I moved the redundant copies
  to lane-private scratch, rebased cleanly, and verified both tracked files
  byte-for-byte with `cmp`. Post-rebase report commit:
  `c1939c2beac8808b52abf86da9936ad9d189dad8` before this final report update.
- `python3 lint.py` before the report: no errors, five warnings.
- `just pytest test_lint.py::TestTitleBlockedClaim::test_a_stale_nonempty_blocker_passes_silently`
  exercises the existing named-releaser false-green: `1 passed in 0.94s`.
- `python3 dev/redproof.py check`: `check: calm — no injections registered
  (opt-in discipline; nothing to evaluate).`
- Final post-rebase `python3 lint.py`: exit 1, five errors and five warnings.
  The errors name `630-cx-630p5.md`, `631-glm-631i3.md`,
  `645-cx-645i6.md`, `765-cx-765holds.md`, and `769-glm-769echo.md`; each
  persisted worktree brief lacks the absolute inbox path required by lint.
  None is lane-owned, and this dispatch supplied no inbox path to record.
- No live `status.json`, `questions.md`, or ledger mutation was performed.

## Relied-on ledger evidence

- `#765`: “Whether that is worth the ceremony is exactly what the lane must
  MEASURE before building — building nothing and shipping the lesson is a
  legitimate outcome.”
- `#755`: “The prose around an id is the coordinator judgement status_sync is
  right not to touch”; its landed note also records that the former check
  “fires two warnings on the healthy live file.”
- `#702`: the direction-2 requirement says an entry naming no id “cannot be
  checked and must be reported as unclassifiable rather than counted clean.”
- `#671`: the broken sweep printed a real count while “the ‘nothing to review’
  is false, and the two together read as a positive all-clear.”
- `#136`: “THREE zero-states, not one”; present-but-unparseable and genuinely
  empty must remain distinct.
- `#725`: “measure how many of the 171 open titles trip the check before
  believing it.”
- `#746`: “A check whose remedy re-trips it trains readers to skim that row.”

## DOGFOOD REPORT

The brief's main premise was usefully incomplete: it discussed `blocked_on` as
text but did not mention the store's canonical `depends(task, needs)` relation.
Finding that relation changed the denominator from “13 named holds a new check
could govern” to “12 already structured, one still trapped in opaque status
prose.” Future briefs about ledger blockers should name both representations so
a lane does not design a second parser before discovering the existing edge.

There was also a small measurement trap in the phrase “live holds.” A recorded
hold is exactly what may be stale, so calling all 17 semantically live would
presuppose the answer. This report calls them **recorded hold claims** and
separately reports releaser state; that vocabulary should be used in future
measurement briefs.

The final rebase exposed a benign but costly coordination collision: the
coordinator committed this lane's persisted brief receipts while their
dispatch-time copies remained untracked here, so Git refused to detach HEAD
even though the bytes were identical. The refusal was safe and the recovery
was straightforward, but a dispatch-receipt commit that lands mid-lane should
either account for those worktree copies or document this expected rebase
step.

More importantly, the same `master` commit made the final lint gate red: all
five newly persisted worktree briefs omit the absolute coordinator inbox path,
including this lane's brief. The boilerplate says reports go to the
coordinator, but the task-specific head supplies only the tracked lane-report
path; it gives no inbox destination. Lint's demand is therefore unreachable
from the delivered brief without guessing. The coordinator should either put
the absolute inbox path into future dispatched heads (and repair these five
receipts through the receipt-owning workflow) or reconcile the lint contract
with lane reports. I did not edit historical/persisted briefs.

No out-of-scope code was changed.

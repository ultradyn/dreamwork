# Lane 587 report — ABS_INBOX_PATH_RE tests the basename, not absoluteness

**Verdict: FIXED.** Commit `0dc54ae9` (rebased onto master `8dd4bfbb`).
Lane: `lane-587inbox`, worktree `.worktrees/lane-587inbox`.

## The defect and the fix

`lint.ABS_INBOX_PATH_RE` was `/[\w./-]+/inbox\.md` — it accepted only a path
whose **basename** is literally `inbox.md`. The loop's actual comms convention
(measured on disk at `/home/xertrov/.cache/agent-comms/ud-dreamwork/`) is
`coord-inbox.md` and `<lane-id>-inbox.md`, so a brief citing the **real**
coordinator inbox failed the check while a brief citing a nonexistent
`.../lane-X/inbox.md` passed it.

The old regex, measured against the four paths the brief names:

```
FAIL  '/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md'   -> None
FAIL  '/home/xertrov/.cache/agent-comms/ud-dreamwork/lane-586routes-inbox.md' -> None
PASS  '/home/xertrov/.cache/agent-comms/ud-dreamwork/lane-586routes/inbox.md' -> match  (the fake)
FAIL  '.dreamwork/inbox.md'                                            -> None   (correct: this is #405's defect)
```

The fix anchors on **a leading `/` plus a basename ending in `inbox.md`**, so
the real convention passes:

```python
# was: ABS_INBOX_PATH_RE = re.compile(r"/[\w./-]+/inbox\.md")
ABS_INBOX_PATH_RE = re.compile(r"(?<![\w.~:-])/\S*/[\w-]*inbox\.md(?![\w.-])")
```

The lookbehind `(?<![\w.~:-])` keeps the `/` genuinely leading — it is not
preceded by `~`, `:` (Windows drive), `.`, `-` or a word char — so the
`~`-prefixed, Windows `C:/` and deep-relative forms that merely look absolute
do not slip through. The trailing `(?![\w.-])` makes `inbox.md` the tail of
the token, so `inbox.md.bak` is rejected.

## Red-proof, both directions

### Direction 1 (the real defect fails today, passes after)

**Production sabotage.** `redproof.py begin lint.py` → reverted the regex to
the old value → ran the new positive test:

```
FAILED test_lint.py::TestBriefWorktreeAbsInbox::test_abs_inbox_regex_accepts_the_real_comms_convention
    AssertionError: /home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md
    assert None is not None
```

The discriminating message is the **real convention path returning `None`** —
not a red count. `redproof.py restore lint.py` restored and verified; the full
class passed 11/11 after. The negative test
(`test_abs_inbox_regex_still_rejects_non_absolute_or_non_inbox`) passed under
the old regex too, which confirms the **positive** is the discriminating arm:
the old regex was already correct on the negative and wrong on the positive.

**`redproof.py check` (post-restore, pre-commit):**
```
check: clean — 1 injection(s) registered, all restored and absent from the
working tree and from this branch's commits:
  lint.py (sha 3f15904bfd97, hint: 'ABS_INBOX_PATH_RE = ...')
```

**`redproof.py check` (post-commit history scan):**
```
history: examined 1 commit(s) since 812a819dce73 (master) against 1 injected
path(s); read 1 blob(s), 0 holding a recorded injection.
check: clean
```

### Direction 2 (cases the new regex accepts but the rule is still broken)

The rule (#405) is **absoluteness**. The new regex closes the obvious
false-greens but two remain at the regex's design boundary — both unclosable
without over-fitting, both immaterial to the check's job:

- **`/x/notaninbox.md`** — basename `notaninbox.md` contains the substring
  `-inbox.md`, so `[\w-]*inbox\.md` matches it. A negative lookbehind that
  required the char before `inbox` to be `-` or `/` would reject this, but it
  would also reject the legitimate `coord-inbox.md`... no: `coord-inbox.md`
  has `-inbox.md` too. The substring overlap is structural: the real
  convention *is* `<prefix>-inbox.md`, so any basename of that shape is
  indistinguishable from a contrived one by regex alone. **Immaterial**: no
  brief cites `/x/notaninbox.md`; the check's job is "is there an absolute
  inbox path at all," not "is the basename a real comms file."
- **`/etc/coord-inbox.md`** (or any absolute path outside the comms dir) —
  absolute and correctly shaped, so it passes. The check does not and should
  not encode the comms directory prefix; #405 is about absoluteness, not
  location. Closing this would require hardcoding `~/.cache/agent-comms/`,
  which is exactly the comms-convention refactor the brief forbade.

The cases the new regex **correctly closes** that a looser regex would miss
(verified against a candidate `/\S*/[\w-]*inbox\.md` without the lookbehind):

```
foo/.dreamwork/coord-inbox.md   — relative-but-slash; strict FAILS, loose PASSES
~/.cache/.../coord-inbox.md     — tilde-prefix;          strict FAILS, loose PASSES
C:/Users/x/coord-inbox.md       — Windows drive;         strict FAILS, loose PASSES
```

The full 13-case matrix (7 must-pass, 6 must-fail) is all-correct under the
shipped regex.

## The discriminating assertion is the negative one

The brief is emphatic and the red-proof bears it out: **the relative
`.dreamwork/inbox.md` must STILL fail.** That is #405's entire point — a
worktree lane handed a relative path writes its own copy. A fix that accepts
absoluteness but starts accepting relative paths has inverted the rule. The
new test `test_abs_inbox_regex_still_rejects_non_absolute_or_non_inbox`
asserts this explicitly, and it passes under both the old and new regex
(confirming the negative was never the broken arm).

## Verification

- **`pytest test_lint.py`**: **522 passed** (520 before + 2 new methods), 0
  failed, in 67.57s. Files run: `test_lint.py` (the only file the change
  touches).
- **`python3 lint.py`**: `clean (6 warning(s))` — the 6 store WARNs are the
  expected-in-a-worktree set from #611 (the `ledger checks` row naming all
  six silent-skipping checks, plus `tasks.md` and `lessons.md`). **Zero
  ERRORs.** The worktree-inbox check itself: `OK briefs 96 worktree-naming
  brief(s), 65 in scope after absolute-inbox rule, 31 grandfathered (#405)` —
  unchanged and green.
- **Live tree coverage**: all 65 in-scope briefs pass under the new regex;
  **zero newly-missing**. The check's OK coverage number is identical before
  and after.

## Grandfathering decision: DO NOT mass-edit existing briefs

**Decision: leave the 4 fake-path briefs as-is.** I agree with the brief's
stated view. Reasoning:

1. **They are historical documents.** A brief describes the dispatch as it
   was; the fake path was the lane's actual receive channel name in the
   coordinator's eyes at the time (the coordinator *did* write to a
   `lane-586routes/inbox.md`-shaped target, because that is what the check
   demanded). Rewriting them retroactively rewrites history.
2. **#398/#405 already established the grandfathering posture.** The check
   itself grandfathered 31 pre-rule briefs; the principle that old briefs are
   not edited to satisfy a rule that postdates them is already load-bearing
   here.
3. **The fakes are now harmless.** Under the fixed regex they pass for the
   same reason the real paths do (they ARE absolute and inbox-shaped). The
   check no longer *rewards* the fake shape over the real one, so the
   incentive that created them is gone. A reader who greps for the convention
   will find 91 citations of the bare form, 47 of `coord-inbox.md`, and ~40
   of `<lane>-inbox.md` — the 4 fakes are a rounding error, and they are
   self-identifying (the per-lane *directory* `.../lane-586routes/inbox.md`
   is visibly different from the flat `.../lane-586routes-inbox.md`).
4. **Cost of the alternative.** Mass-editing 4 historical briefs is 4
   commits' worth of conflict surface for every concurrent lane that touches
   `.dreamwork/docs/briefs/`, for zero behavioral gain.

**Out of scope, filed for the coordinator:** the 4 fake paths
(`586-chat-reply-routes.md`, `591-g2-render-authority.md`,
`592-worktree-lint-false-error.md`, `595-597-sideways-scroll.md`) all cite a
per-lane *directory* `.../lane-<id>/inbox.md`. Whether the coordinator ever
wants a one-line note in `briefs/boilerplate.md` (owned by #608) telling
future briefs to prefer the flat `<lane>-inbox.md` form is a documentation
decision, not a lint one — and #608 is live on that file.

## Cited issues, relied-on lines

- **#587** (this task): *"lint.ABS_INBOX_PATH_RE is /[\w./-]+/inbox\.md, so
  it only accepts a path whose BASENAME is literally inbox.md."* — the defect
  statement, verified empirically above.
- **#405** (the rule this check enforces): *".dreamwork/inbox.md is
  UNTRACKED, so it does not exist in a worktree at all — a lane appending its
  report there creates a fresh file in the worktree that the coordinator
  never reads... so the dispatch prompt must give both channels as ABSOLUTE
  paths."* The gap between this (absoluteness) and the old regex (basename)
  IS the bug.
- **#586** (the brief that had to lie): #587's entry cites it — *"#586's
  brief had to invent a per-lane directory .../lane-586routes/inbox.md purely
  to satisfy it."* Confirmed: `586-chat-reply-routes.md` carries exactly that
  fake path.
- **#671** (a check that examines nothing must not read as passing): the
  principle that drove the negative-assertion emphasis — *"a check that can
  only pass on a fiction"* is the same class as *"a check that examines
  zero entries and says so confidently."*
- **#612** (volume): the change is a regex + 2 tests, 59 insertions / 4
  deletions across 2 files.
- **#611** (the 6 store WARNs are expected in a worktree): *"[the 6 silent-
  skipping checks] each record their own skip... the list is DERIVED from the
  code that skipped."* Quoted in the verification section above.

## Rebase outcome

Master moved `812a819d` → `8dd4bfbb` (one commit, `merge(#608)`) during the
work. Rebased cleanly onto `8dd4bfbb`; no conflicts. Final commit sha:
`0dc54ae9`.

## Dogfood report

- **The brief was correct and precise.** Every claim it made — the regex
  shape, the real convention, the #586 fake-path cost, the negative-as-
  discriminating-assertion emphasis — checked out exactly on measurement. The
  one thing it slightly understated: the number of *real-convention* briefs
  already in the tree (47 citing `coord-inbox.md`, ~40 citing
  `<lane>-inbox.md`), which makes the fix high-value rather than theoretical —
  nearly half the in-scope briefs were already citing the real convention and
  the broken check was not catching them either way (because they also
  happened to cite the bare `.dreamwork/inbox.md`, which the old regex DID
  match).
- **`redproof.py` is good and I trust it more than my own discipline.** The
  `begin`/`restore`/`check` protocol plus the post-commit history scan is the
  right design: the history scan is the part that catches the
  commit-while-sabotaged failure mode that a working-tree-only check cannot.
  No friction.
- **One small friction, not worth a dogfood issue:** the brief says "441 tests
  as of the last count in #606's entry" but the live count is 522. Test
  counts rot fast; I treated it as a stale-and-harmless reference rather than
  a target, but a future brief author might trust the literal. Low cost.
- **The "fake path" discovery was the interesting part.** Categorizing the
  briefs by cited path required running the regex over all 96 worktree
  briefs, and the first cut (categorize by single match) was wrong because
  briefs cite multiple paths. The `Counter` over all matches was the right
  tool. Nothing in the tooling misled me here; I'm noting it because the
  "what is the real convention on disk" question is the load-bearing fact and
  it took two passes to count honestly.

# Lane report — #589: make the dogfood report a standing obligation

**Verdict:** DONE. Three parts landed; no lint check built (argued below).
Rebased onto `master` (`8a00df9`); base had not moved.

## What I changed and why

Three commits, each one document:

1. **`SKILL.md`** (`1af6079`) — Subagents section: a lane's inbox report ends
   with a dogfood section, required, beside the hand-off obligation. States
   the design point the entry settles (blank is a valid answer that is
   STATED; an omitted section reads as "no friction"), names the
   coordinator-reads-it half (`#606`'s failure), and cites `#136`/`#671`.
2. **`file-formats.md`** (`1af6079`) — brief shape: a new subsection under
   the briefs section stating the obligation lives in the boilerplate, the
   obligation is on the lane's report (not the brief), and no lint check
   binds it — with the reason.
3. **`briefs/boilerplate.md`** (`a01b173`) — the writer. Strengthened the
   existing `## Deliverable` dogfood paragraph to carry the full obligation:
   required-not-optional, the "beyond the direct task" framing, the
   coordinator-reads-it half, and the blank-is-stated design point.

## Part 3 — argued: no lint check

The brief asked me to consider a lint check and **argue it**, not assume it.
I considered it and **refused** it, on three grounds:

**Ground 1 — direction.** The obligation is on the **lane's report**. A brief
check inspects the **brief**. Those are different documents, and only one
exists at lint time. `check_brief_lane_owns` (the named sibling) works because
the thing it checks (`Lane-owns:`) IS in the brief and IS the obligation. Here
the obligation is discharged in a document (`inbox.md`) that lint never reads
and that does not exist when the brief is written. A check on the brief would
be checking the wrong document.

**Ground 2 — writer-not-description** (`lessons.md:405`, quoted verbatim):
> *"When a format fails silently, the fix is a WRITER, not a second
> description of it."*

The boilerplate IS the writer. `#400` (measured): *"The lessons that reach a
lane are the ones hand-copied into its brief — nothing else does… a lane reads
what is physically in front of it."* The boilerplate is physically in front of
every lane (`#400`'s own measurement), appended verbatim to every dispatch. So
the obligation reaching the lane is a property of the writer, not of a check
on a different document.

**Ground 3 — a token is not a statement** (`#699`, cited in boilerplate's own
header). A string-match check for "dogfood" in a brief would bind a token, not
a statement. A brief could contain the word "dogfood" in prose (this one does)
without carrying the obligation. `check_brief_lane_owns` avoids this because
`Lane-owns:` is a machine-parseable line with a grammar; "ask for a dogfood
report" is prose, and no grammar distinguishes "stated as an obligation" from
"mentioned in passing."

**What I did instead:** strengthened the boilerplate — the one document
physically in front of every lane — to carry the full obligation. This is the
writer `lessons.md:405` names.

## Red-proof

**Direction 1 (demonstration, since I built wording not a check):** proved the
dispatch path carries the obligation to a lane. A dispatch concatenates a
task-specific head with `briefs/boilerplate.md`; I reproduced that
concatenation and grepped for the four obligation phrases. All four are
present in the text a lane receives:

```
$ { echo "# Task head"; cat briefs/boilerplate.md; } | grep -iE "dogfood report|required, not optional|No friction found|coordinator reads it"
Then a **DOGFOOD REPORT** — required, not optional (#589): what about this
coordinator reads it. **"No friction found" is a valid answer that is STATED**;
```

The discriminating assertion is **not a count** (a count of "dogfood" would
match the brief head's title too); it is the presence of the obligation
phrases in the concatenated dispatch text.

**Direction 2 — the open false-green I cannot close:** the failure this design
cannot catch is **a lane that writes the section but fills it with a
restatement of its task** (satisfying the format, saying nothing). The
obligation is "write a dogfood section"; a section that exists but is hollow
passes any check on its existence, and no check can judge whether its content
is genuine. This is the `file-formats.md` "unguarded" category: the inbox is
prose read by a language model, and *"a linter would only ever check the parts
that do not matter."* A second open case the brief named: a lane killed before
writing its report at all — the section cannot exist, and that is
indistinguishable from a lane that declined. Both are structural limits of
wording-as-enforcement, and I report them rather than pretend the wording
closes them.

`dev/redproof.py check` output:
```
check: calm — no injections registered (opt-in discipline; nothing to evaluate).
```

## Cited issues, relied-on lines quoted

- **`#671`** — *"a sweep which found nothing must be distinguishable from one
  that did not run"*; and the repo's oldest form of the design point: a zero
  that examined nothing must not read as passing. Governs the blank-vs-omitted
  distinction.
- **`#400`** — *"The lessons that reach a lane are the ones hand-copied into
  its brief — nothing else does… a lane reads what is physically in front of
  it."* Governs WHERE the obligation belongs (the boilerplate, not lessons.md
  and not a check).
- **`#606`** — the out-of-scope warning that existed and went unread: the
  coordinator half. My SKILL.md wording names this directly.
- **`#612`** — volume. Three small commits, each one document; no doc tripled
  in length.
- **`#136`** — *"THREE zero-states, not one… present-but-unparseable is a
  fault and must look like one."* The ancestor of the blank-stated rule.
- **`lessons.md:405`** — *"When a format fails silently, the fix is a WRITER,
  not a second description of it."* Governs check-vs-wording.
- **`#699`** (via boilerplate header) — *"no string-match check can bind 'a
  rule is stated' (a token is not a statement)."* A check for "dogfood" in a
  brief binds a token.

## Considered and refused

- **Mass-editing historical briefs.** `#398`/`#405` grandfather them; `#587`/
  `#607` upheld that tonight. The boilerplate is the standing half concatenated
  at dispatch time, so historical briefs already receive the obligation via the
  boilerplate without editing. Considered and refused.
- **A lint check.** Argued above; refused on direction, writer-not-description,
  and token-not-statement grounds.

## Rebase outcome

`master` = `8a00df9`; my base = `8a00df9`. Master had not moved; no rebase
needed. Post-rebase sha (== pre-rebase, since nothing moved): `a01b173`.

## Verification

- `python3 lint.py --target .` — **clean** (6 warnings, all the expected
  worktree-lacks-ledger ones; zero ERRORs).
- `python3 dev/redproof.py check` — calm (quoted above).
- Did not touch `lint.py`/`test_lint.py`, so no `pytest test_lint.py` run
  required (the brief gates that on "if you touch it").
- No browser guards (non-UI lane).

---

## Dogfood report

(Required, not optional — and this is the shape I am proposing, so it is also
the cheapest test of my own design.)

**Friction 1 — `file-formats.md` is 2700 lines and the brief-shape section I
needed had no anchor.** I spent a read-budget finding where a "brief format"
row should live. The main table (`## The rest`) has rows for every
`.dreamwork/` file but nothing for `briefs/*.md` as a class; the
`Lane-owns:` subsection is buried at line ~2070 under the briefs heading. A
lane adding a new brief-format concern has no single index to find the
section. Filing not-fixing: the briefs section could carry a one-line pointer
in the main table, or the `## The rest` table could gain a `briefs/*.md` row.

**Friction 2 — the boilerplate already had a dogfood paragraph, and the
brief did not tell me.** The brief's Part 3 asked me to "consider a line in
`briefs/boilerplate.md`" as if it might not exist. It does — the `##
Deliverable` section has closed with a dogfood-report ask for some time. I
nearly added a second one. The right move was to strengthen the existing
paragraph, but the brief's framing cost me a read to discover that. A brief
that names a file to edit could note whether the content already exists
there (one line: "the Deliverable section already asks for one; strengthen
it").

**Friction 3 — `check_title_blocked_claim` is an excellent pattern but its
docstring is 40 lines and the brief pointed at it as "the shape a new check
should follow" without quoting the load-bearing part.** The load-bearing
decision in that check is the discrimination (`#707`: the pattern is "blocked
on" the CLAIM idiom, not bare "blocked"). I had to read the whole docstring
to find the one sentence that governs. A brief that names a check as a
pattern could quote the discriminating sentence rather than pointing at the
function.

**No friction found** on the core task: the three-part structure was clear,
the off-limits list was precise, and the red-proof section's "if you build
only wording, direction 1 is a demonstration" gave me the exact shape to
follow.

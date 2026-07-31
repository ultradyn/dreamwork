# Lane 771 report — shell and CLI shape errors

## Verdict

**False-fire measurement leads the result: a repository-text backtick guard flags 292
healthy non-command lines (282 in the brief/lane corpus and 10 in commit bodies).** A
generic `pipeline &&` scan adds four more healthy prose/example hits. At the narrower
command-string boundary, the exact known-bad spellings flag zero healthy persisted command
examples, but this repository has no universal boundary through which arbitrary agent shell
commands pass. A check in `lint.py` would therefore inspect descriptions, not behaviour; an
optional preflight would be another check the coordinator must remember to run.

I shipped **no syntactic guard and no ledger read-back verb**. I added the measured alternative
to `briefs/boilerplate.md`: after a mutating command or controlling inventory, read the
authoritative resulting state immediately and bind follow-on reporting/writes to the producer's
status rather than a later pipeline element or pre-existing state.

The change is commit `5644146b` (`docs(#771): require resulting-state verification`). A targeted
test exposed a healthy live-corpus false red; commit `1080d830` removes the test's stale
`HISTORICAL ONLY` precondition while retaining its actual assertion that all four checks carry
the same reach qualifier.

## Corpus and measurement

I measured three persisted sources named by the brief:

- all 219 Markdown lane briefs under the live main checkout's
  `.dreamwork/docs/briefs/`;
- all 469 Markdown records under the live main checkout's `.dreamwork/` (briefs, lane reports,
  lessons, hand-offs, and measurements), plus the two tracked `briefs/` files;
- all git commit bodies on this branch's history, 42,288 lines.

The candidate scans and manual classification were:

| Candidate spelling | File hits | Commit-body hits | Healthy false fires | Finding |
|---|---:|---:|---:|---|
| literal `git merge … -F -` | 1 | 0 | 0 | The one hit is the recorded defect, not a healthy command. |
| any double-quoted span containing a backtick | 282 | 10 | 292 | All are healthy repository text at lint scope; most are prose or quoted examples. |
| exact `--note "…backtick…"` shape | 1 | 0 | 0 | The one hit is the lesson describing the defect. The executed shell source was never persisted. |
| generic pipeline followed by `&&` | 4 | 0 | 4 | All four are prose/code/table examples, not the failed worktree removal. |
| exact `git worktree remove … | … &&` | 0 | 0 | 0 | The incident command is absent from the persisted corpus. |
| recursive `grep` plus `--include='*.py'` | 1 | 0 | not mechanically decidable | Whether this is wrong depends on whether extensionless scripts belong to the intended population. |

Thus the exact patterns have a good false-fire rate only after being handed an actual command
string. No owned, mandatory command-string interception point exists. At the repository lint
boundary the only broad candidate with useful recall—the backtick scan—is wrong on 292 healthy
inputs, materially violating #755.

No lint check was added, so lint row counts do not move on either target. Before and after:

- worktree `python3 lint.py`: 5 warnings -> 5 warnings;
- worktree interpreter against main, `python3 lint.py --target
  /home/xertrov/.llm-general/skills/ud-dreamwork`: 1 warning -> 1 warning;
- `lint.py`: 6,083 lines -> 6,083; `test_lint.py`: 8,758 -> 8,757 (the stale
  environmental precondition was deleted); boilerplate: 288 -> 295.

## Decision (IGC)

Context: the agent issues arbitrary shell through its harness; this repo can lint persisted
files and can supply optional tools, but it does not own the shell execution boundary.

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| lint persisted prose for spellings | ✘ | ✘ | ✘ | ✔ | ✔ |
| optional command-string preflight | ✘ | ✔ | ✘ | ✔ | ✘ |
| ledger `note` write/read comparison | ✘ | ✔ | ✘ | ✘ | ✘ |
| resulting-state standing contract | ✔ | ✔ | ✔ | ✔ | ✔ |

- G1: does not fire on healthy input.
- G2: reaches the failure family rather than one spelling.
- G3: names only what it proves.
- G4: fits the owned surface without creating an optional competing route.

Decisive errors: repository lint sees prose and produced 292 false fires. An optional preflight
does not reach commands that bypass it, so it recreates the remembered-check problem #440 rules
against. Ledger read-back happens after shell expansion: the process receives the already-damaged
argv, so `stored == argv` can pass while the user's intended word is missing. It would verify a
different property (storage fidelity) and cannot honestly claim intended-text fidelity. The lane
does not own `dev/ledger.py` in any case.

## Mechanical versus semantic findings

1. `git merge … -F -` is mechanically recognizable as a literal spelling. The consequential
   defect—recording a landing after merge failed—is closed only by exit-status/result binding.
2. An unescaped literal backtick in a directly written double-quoted argument is mechanically
   recognizable. Intended text equality is not: intent is gone before `execve`, and read-back can
   compare only against the post-expansion argv.
3. The exact recorded worktree pipeline is mechanically recognizable. A general rule that
   `pipeline && command` is wrong is semantic: sometimes the author intentionally means the last
   pipeline element's status. Whether `echo` asserts upstream success depends on its meaning.
4. The grep spelling is not itself a defect. The semantic part is whether the intended inventory
   includes extensionless executable scripts (or non-Python files). Syntax alone cannot supply
   that population.

## Both directions for candidate guards

No guard shipped, so there was no production injection and no Direction-1 red-proof registry
entry. The candidate cases were nevertheless evaluated both ways:

- Merge literal: a literal matcher rejects the recorded `git merge … -F -`. False-green:
  `flag=-F; input=-; git merge --no-ff "$branch" "$flag" "$input"` has the same invalid argv but
  no literal `-F -` spelling.
- Note literal: the exact directly written double-quoted form is matched. False-green:
  put the whole command in `cmd` and run `eval "$cmd"`; the executed line contains no backtick
  spelling. More importantly, a read-back verifier sees the post-substitution argv and reports
  equality after the word has already vanished.
- Worktree pipeline: the exact directly written pipeline is matched. False-green: store the
  pipeline in a variable, `eval "$pipeline" && echo "removed $w"`; a direct-source matcher sees
  only `eval` while status still flows through `tail`.
- Grep inventory: a literal matcher can name `--include='*.py'`, but cannot decide it is broken.
  False-green spelling: `suffix='*.py'; grep -rl sqlite3.connect --include="$suffix"` still omits
  extensionless scripts while hiding the literal. False-red: a census intentionally restricted
  to Python-suffixed modules is healthy with the same syntax.

These names are intentionally narrow: “literal spelling in a directly written command”, never
“unsafe merge”, “safe note”, or “complete inventory”. This is the #651 naming limit and #645's
spelling-versus-behaviour limit.

## Relied-on issue and lesson evidence

- #771: “a wrapper that inspects the command string sees a SPELLING, not a behaviour” and the
  legitimate outcome explicitly permits a standing-contract result.
- #755: “a queued entry whose task landed sometimes means the FOLLOW-UP is still wanted” and the
  landed note records two warnings on healthy live data as the known gap. This is the governing
  false-attribution constraint.
- #440: “`lint` cannot police a throwaway script” and “the check that matters is that the tool
  exists and is the only path”. There is no corresponding one-path shell wrapper here.
- #645 increment 5: the guard must account for remaining production sites before being enabled;
  this supports inventory from the actual population rather than a suffix assumption.
- #651: three measured static proxies matched 12, 22, and 52 healthy constructs, and “the defect
  is semantic and no regex decides it”. It also requires names not to outrun proof.
- #702: `_base_id('#696')` and `_base_id('696')` differ mechanically while the free-form sibling
  field uses another grammar; syntax is useful only where the field boundary is authoritative.
- #671: zero entries now says `DID NOT REVIEW`, because a confident empty result must not resemble
  a completed check.
- #136: missing, present-but-unparseable, and genuinely empty are distinct states. This informed
  the refusal to make an optional or unobserved scanner look like coverage.
- Lesson **“Unescaped backticks in a double-quoted zsh argument execute, and the ledger silently
  loses shas.”** resolves to exactly one head. It already says lint cannot recover a legal note's
  missing content and recommends re-reading the write.
- Lesson **“A green reading is evidence only if you know what produced it — three times in one
  evening I credited the wrong mechanism”** resolves to exactly one head. Its merge example says
  follow-on state captured an unrelated HEAD.
- The companion sentence “a lesson that does not become a check is a lesson waiting to be
  re-learned” occurs inside the uniquely resolving lesson **“A conflict resolver that greps for
  three marker forms misses the fourth”**. Here the measured result is that no owned check reaches
  the commands without becoming noisy or optional, so the shipped replacement is the resulting-
  state contract rather than another lesson.

## Verification and rebase

- Baseline lint: worktree 5 warnings; main target 1 warning.
- First targeted run: 561 passed, 1 failed. Discriminating failure:
  `expected.startswith("HISTORICAL ONLY")` rejected the healthy value
  `current through task #771 (0-id gap; 3 unnumbered brief(s) cannot be ordered)`.
- After narrowing that stale test precondition, exact rerun:
  `just pytest test_lint.py::TestBriefCorpusReach::test_all_four_live_checks_carry_the_same_reach_qualifier test_dispatch_lane.py`
  -> 17 passed.
- Full requested targeted pair is rerun after report creation; final result is recorded below.
- No sabotage was injected. `dev/redproof.py check` final output is recorded below.
- Rebase outcome is recorded after the final rebase below.

## DOGFOOD REPORT

The generated live lane brief itself makes the brief corpus current through #771, while
`TestBriefCorpusReach.test_all_four_live_checks_carry_the_same_reach_qualifier` assumed the live
checkout must remain `HISTORICAL ONLY`. That is a #755 false red on every lane whose persisted
brief closes the id gap. The hermetic sibling tests already prove historical/current/unknown
classification; the live test's real purpose is cross-check agreement. I removed only the stale
environmental precondition and retained the exact agreement assertion.

The task head also says to append a hand-off line to the absolute coordinator inbox, while the
standing contract says a lane writes its report and nothing else and requires an override to name
the rule it replaces. The head is emphatic but does not explicitly name an override of the
single-writer rule. I followed the common authorised reading: this report is written; no inbox or
handoffs line is appended.


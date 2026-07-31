# Lane 748 report — boilerplate citation audit

## Verdict

`briefs/boilerplate.md` now carries the volume principle without `#612`. I chose
option (a), dropping the citation: the sentence is its own authority, while filing a
new task solely to serve as retroactive authority would invert the relationship between
a claim and its evidence and would violate this lane's read-only-ledger constraint.

The complete pass found **47 citation occurrences naming 32 unique ids**. At the
unique-id level, 18 are accurate-only, 9 contain at least one thematically-adjacent use,
2 are wrong, 1 is unresolvable, and 2 are unclassifiable-only syntax examples. Mixed-use
ids are called out in the table rather than being forced into a single flattering bucket.
Excluding the already-known `#612`, the audit therefore found **two wrong ids**:

- `#691` did not state the snapshot incident. I repointed it to `#703`, whose body says
  verbatim that a `#691` lane's first snapshot landed in the shared directory.
- `#704` is about a live-worktree test that fails with an empty fleet, not snapshot
  sequencing. I removed the citation and made the already-self-contained sequencing
  claim direct.

No lint check was added. A string check can establish that a token occurs, not that the
ledger entry semantically supports the surrounding claim; adding one would reproduce
the exact false-green shape this audit found.

## Option choice (IGC)

Context: preserve a good standing rule, keep the live ledger read-only, and land the
smallest honest correction.

| Idea | All | G1: principle remains | G2: authority is honest | G3: minimal/read-only |
|---|:---:|:---:|:---:|:---:|
| (a) Drop `#612` | ✔ | ✔ | ✔ | ✔ |
| (b) File a task and cite it | ✘ | ✔ | ✘ | ✘ |

The decisive errors for (b) are that it manufactures an entry to justify prose that
already stands alone, and it requires a forbidden mutation of the live ledger. Option
(a) is the sole survivor.

## Audit method and red-proof substitute

1. Enumerate every exact `#[0-9]+[a-z]?` token in the file: 47 occurrences, 32 unique
   ids.
2. Run `python3 dev/ledger.py get <id> --ledger
   /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md` once for every
   unique token. `#392a` was run exactly as cited and rejected as a non-integer id.
3. Compare every occurrence's surrounding claim with both the returned title and body.
   An id naming the lane that observed a fact is not enough if the ledger entry does not
   record that fact.
4. Classify accurate, thematically-adjacent, wrong, unresolvable, or unclassifiable.
   Syntax examples have no authority claim and are therefore unclassifiable, not green.

**Direction 1:** this uniform pass independently flags `#612`. The boilerplate claims a
scope rule (“fewest lines that carry the meaning”); the ledger title is *“The #381
fold-prompt WARN quotes the ENTIRE hand-off body verbatim, so one 4KB hand-off dominates
the whole lint report”*. That is thematically about volume but does not state the scope
rule.

**Direction 2:** two false-green constructions were tested against the method. First,
resolving each unique id only once can hide mixed uses: `#667` accurately supports the
worktree-ledger command but does not directly support “the coordinator resolving them
blind is how #667 went wrong.” Evaluating all 47 occurrences closes that hole. Second,
a task id can name the lane where an incident happened while its entry says nothing about
the incident (`#691`, `#704`); requiring support in the returned body exposes both. The
remaining open limit is `#392a`: the numeric-only CLI cannot resolve it, so the method
reports it as unresolvable even though neighbouring entries corroborate the history.

## Citation table

Several migrated ledger titles end mid-sentence; the table reproduces the returned title
verbatim rather than silently repairing it.

| Id | What the boilerplate claims | Entry's actual title | Verdict |
|---|---|---|---|
| `#136` | “nothing registered” must differ from a pass; an omitted dogfood section must differ from “none found” | “A questions.md that parses to nothing must say so” | **thematically-adjacent** — the entry establishes three zero states for `questions.md`, not these two surfaces |
| `#349` | never restore a red injection with `git checkout` | “`lessons.md` is 117 entries and 1476 lines, and a lesson in it failed to” | **accurate** — the body quotes that exact failed lesson and the destroyed-work consequence |
| `#392a` | committed work can survive while its report does not | no title; `get` rejects `392a` as an invalid integer | **unresolvable** — `#404`/`#687` corroborate the incident, but the cited id itself cannot be opened |
| `#400` | lane-facing rules reach lanes only when copied into their briefs | “`lessons.md` has outgrown being read, and the briefs that tell lanes to read it are” | **accurate** — the body says the lessons that reach a lane are the ones hand-copied into its brief |
| `#404` | git subjects are the primary landing route; committed deliverables outlive a missing inbox report | “for a same-tree lane, `git log` is a strictly more reliable landing channel than” | **accurate** |
| `#471` | a guard that throws before assertions did not judge | “a single guard cannot be run on its own, and I cannot explain why the full run disagrees” | **accurate** — the body distinguishes assertion verdicts from pre-judgement server failures |
| `#577` | example commit subject `feat(#577)` | “the /chat/<id> page needs a reply composer so he can reply from the UI instead of the CLI. Reuse and extend existing components (the composer's postJSON/DraftStore/confirmation lifecycle, the chat route's existing /chatdata reader). Reply via POST to the existing /command route with kind 'chat' and the chat id, OR a new /chat-reply route — the existing CLI (bin/ud-dw-chat reply) imports watch.apply_chat_turn, the ONE writer; the UI path must go through the same server-side writer, never a second one. Found-not-fixed at #562 gate: 'reply composer on /chat/<id> deliberately out of scope — new ingestion path, not a rendering one'. Max's 04:00 do-next: 'this page needs a way to reply. reuse and extend our existing component(s).' NOTE: watch.py is now refactored (#397) — client JS lives in client/*.js, not watch.py. The composer components are in client/command.js, the chat view in client/views.js, routing in client/router.js.” | **unclassifiable** — this occurrence is syntax, not an authority claim |
| `#589` | every lane report requires a stated dogfood section | “Dogfood report: make it a standing section of every lane's report, in the dispatch prompt not the relay” | **accurate** |
| `#592` | the main-checkout tool is a legitimate pre-fix baseline | “lint.py in a lane worktree emits a FALSE tasks.md ERROR — three hand-offs now teach lanes to ignore it” | **thematically-adjacent** — that lane discovered the interpreter issue, but `#607` is the entry that actually records the baseline technique |
| `#596` | one-direction checks let real false-greens through | “TITLES has no 'research' key so /research's heading reads 'dreamwork watch' — and the diff test covers 3 of 4 tables” | **accurate** — its fold records three constructed false-green vectors |
| `#607` | invoke the main-checkout tool only for the deliberate pre-fix baseline | “Briefs prescribe the skill-dir lint.py as the verification command — a symlink to the MAIN checkout, so a lane editing lint.py verifies against the code it just fixed elsewhere” | **accurate** |
| `#608` | snapshotting the wrong state can restore away the real fix | “The red-proof recipe in every brief backs up the WRONG state — it says snapshot first, but the state you must restore TO is the post-fix one” | **accurate** |
| `#612` | land the fewest lines that carry the meaning | “The #381 fold-prompt WARN quotes the ENTIRE hand-off body verbatim, so one 4KB hand-off dominates the whole lint report” | **thematically-adjacent** — lint-output volume is not a change-scope rule; citation removed |
| `#624` | `git commit --only` still sweeps another lane's edits to the same file | “git commit --only <shared-file> does NOT isolate lanes — it sweeps another lane's uncommitted append to the same path, and the victim's own commit then reports 'nothing to commit'” | **accurate** |
| `#634` | `/tmp` is the wrong substrate for filesystem-sensitive snapshots/probes | “The agent scratchpad is tmpfs, and tmpfs does not update mtime for mmap'd writes — any lane measuring filesystem behaviour there gets a clean-looking WRONG answer” | **accurate** |
| `#652` | red-proof snapshots must be lane-private | “The agent scratchpad is SHARED between concurrent lanes, and that endangers the #349 snapshot protocol” | **accurate** |
| `#655` | a brief's “one commit ahead” count hid that the lane was 32 commits behind; the same review exposed false-green checks | “Status section should show the number of unprocessed batched events waiting to be drained” | **mixed: accurate / thematically-adjacent** — the body records the 32-behind merge failure and false-greens, but `#672` is the entry that quotes the false “one commit ahead” brief claim |
| `#666` | targeted pytest avoids fleet pile-on; browser load is mainly a memory problem and raw load is not CPU attribution | “Lanes cannot see each other's test runs, so they pile on — 8 concurrent pytest suites turned a 4.5-minute verdict into ~50 minutes of wall clock” | **accurate** |
| `#667` | the bare ledger command fails in a worktree; coordinator-side blind conflict resolution went wrong | “`ledger.py get` silently returns 'not found' from a lane worktree — and the brief then routes the lane to the deprecated file, manufacturing a confident wrong citation” | **mixed: accurate / thematically-adjacent** — the command claim is exact; the body records a diff3 merge conflict but not the stronger “blind resolution went wrong” claim |
| `#671` | a check that examined nothing must not read as a pass | “ledger.py sweep never got the #294 store dispatch — it examines zero ledger entries and says so confidently” | **thematically-adjacent** — the principle is exact, but the boilerplate applies it to red-proof and dogfood surfaces |
| `#683` | `dev/redproof.py` owns snapshot/restore and refuses unrestored injections | “A red-proof injection can be committed and merged — nothing checks the tree is clean of injections at hand-off” | **accurate** |
| `#686` | committing before stop is weaker than committing every coherent increment | “A ccc @glm52 lane produced eight files of work and committed none of it — the handoff contract assumes a commit and nothing enforces it” | **accurate** |
| `#687` | lanes report; the coordinator alone writes `handoffs.md` | “SKILL.md and lessons.md disagree about who writes handoffs.md, and I added to the stale side tonight” | **accurate** |
| `#688` | example commit subject `fix(#688)` | “A branch-level reachability check at the fold step — the twin of ledger.py sweep that sweep cannot be” | **unclassifiable** — this occurrence is syntax, not an authority claim |
| `#690` | sibling tokens in the same body must be checked; low-to-mid-20s guard load is viable | “The health guard fails two assertions on merged master: the unreadable panel announces the fault but no longer names the path” | **mixed: accurate / thematically-adjacent** — the entry records both sibling tokens and the 23.72 clean run, but not the exact claim that the lane declined at 21–25 |
| `#691` | a lane's first red-proof snapshot landed in a shared directory containing other lanes' backups | “Cheap-model recap of the main agent actions, shown on the dashboard — DESIGN FIRST, he reviews before implementation” | **wrong** — the entry never records the snapshot incident; changed to `#703` |
| `#699` | a token match cannot prove that a prose rule is stated | “check_doc_map_plans unions every parenthesised group on the row, so a plan can be 'mapped' while the enumeration never names it” | **thematically-adjacent** — it proves occurrence-in-the-wrong-place can false-green, not semantic prose equivalence |
| `#700` | experiments are file-gated; `docs(#700)` is commit syntax; a `#700` lane measured the subject regex | “SKILL.md:913 'Experiments are feature-gated' is a rule with no referent — nothing implements it” | **mixed: accurate / unclassifiable / thematically-adjacent** — the gate claim is exact, the syntax example makes no claim, and `#707` records the regex measurement |
| `#703` | checked-in boilerplate preserves corrections and must mirror lane-facing rules | “Audit SKILL.md's lane rules against briefs/boilerplate.md — rules that exist but never reach a lane” | **accurate** — its body also records the shared-snapshot incident now cited at the red-proof rule |
| `#704` | a lane snapshotted two files too early and restored away later edits | “test_live_worktrees_do_not_collide FAILS when the fleet is empty — the suite's greenness depends on transient machine state” | **wrong** — neither title nor body records snapshot sequencing; citation removed |
| `#707` | `dev/ledger.py sweep` requires the `verb(#NNN)` subject shape | “sweep's SWEEP_SUBJECT misses the repo's dominant commit form, so the primary landing-discovery route is nearly blind” | **accurate** |
| `#710` | `redproof.py check` scans branch history for committed injections | “An injection committed mid-branch survives a tree-only hand-off gate and gets merged with the branch” | **accurate** |

## Recommendations for adjacent and unresolved uses

I did not change these because adjacency is a judgement call under the brief:

- Make cross-surface analogies explicit (`same shape as #136/#671/#699`) so they do not
  read as direct authority for red-proof, dogfood, or prose semantics.
- Drop `#592` from the pre-fix-baseline clause; `#607` states it directly.
- Repoint the “one commit ahead” wording from `#655` to `#672`; `#655` documents the
  downstream failure, while `#672` quotes the bad claim.
- Rephrase the `#667` conflict clause or cite an entry that actually establishes the
  coordinator-blind failure; its current body only records the conflict and its resolution.
- Keep `#690` for the measured 23.72 outcome, but remove or separately source the exact
  “declined at 21–25” provenance.
- Drop `#700` from the subject-regex measurement; `#707` is already the exact authority.
- `#392a` is redundant beside `#404`, which already records its landing. Removing the
  suffix-id reference would make every remaining authority directly resolvable.

## Historical reports considered and left alone

I considered the four inherited lane-report copies named by the task and deliberately did
not edit them. The ledger evidence supports forward-only grandfathering:

- `#398`, actual title *“a brief written after the hand-off obligation landed must carry
  it”*, reports **“3 brief(s) in scope … 27 grandfathered.”**
- `#405`, actual title *“the loop has been managing file contention by hand all session
  when his standing”*, reports **“30 existing worktree briefs grandfathered.”**
- `#587`, actual title *“brief absolute-inbox lint rule tests the filename, not
  absoluteness — no real inbox matches it”*, says **“Grandfathering upheld with an
  argument rather than on my say-so.”**

Those reports are historical evidence of the propagation defect. Rewriting them would
erase the record and widen a forward boilerplate correction into a history rewrite.

## Verification and landing

- `python3 lint.py`: exit 0, **clean (6 warnings)**, zero ERRORs. Three warnings are the
  expected worktree/store refusal rows; the other three are pre-existing questions,
  status, and lesson warnings. This matches `#611`'s actual title, *“In a worktree,
  check_ledger_sections and check_task_origins print NOTHING rather than saying they
  examined nothing.”*
- `python3 -m pytest test_lint.py`: **534 passed in 70.12s**.
- No browser guards were run, per brief.
- Rebased cleanly onto local `master` after it moved 16 commits; no conflicts.
- Source correction commit after rebase: `082720f38ed7249a4fcd53e627a84b17fb183e9c`.

## DOGFOOD REPORT

The boilerplate itself was useful as a document rather than merely a command list: the
uniform audit caught the known `#612` case and two additional wrong authorities. Three
meta-citations in the task-specific brief have the same problem and should be corrected
before this audit pattern is reused:

- `#440` is invoked for “pick one and argue,” but its actual title is *“the coordinator
  hand-rolls a ledger split on every fold, and the unanchored form has now”*. Its body
  argues for one supported ledger path, but does not state a general option-argument rule:
  **thematically-adjacent**.
- `#590` is invoked for “a non-zero count is a question, not a verdict,” but its actual
  title is *“Re-rank the open backlog against his 2026-07-31 focus (watch.py modularity +
  built frontend)”*. Its body calls audit numbers recommendations, but does not establish
  the general reachability-count rule: **thematically-adjacent**.
- `#702` is invoked for “an id you cannot classify must be reported unclassifiable,” but
  its actual title is *“status.json records a dispatch in two places and only one is
  machine-readable, so the fleet can read as empty while lanes run”*. It says a separate
  observation is “not yet a verdict,” not that unclassifiable is a required bucket:
  **wrong**.

The other concrete friction is suffix ids: `dev/ledger.py get 392a` rejects the citation
grammar used by the boilerplate. The audit can remain honest only by exposing that as
unresolvable; silently coercing it to `392` would have audited a different task.

`BRIEF.md` was intentionally left untouched. It is the supplied audit input and an
untracked copy; the scoped source of truth is `briefs/boilerplate.md`.

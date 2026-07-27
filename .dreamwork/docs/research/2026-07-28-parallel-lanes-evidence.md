# #264 (empirical half) — what thirteen parallel lanes in one shared tree actually did

**Date:** 2026-07-28
**Agent:** grok-dreamer (empirical half of #264)
**Scope:** One research document only. Reads the durable record of the 2026-07-28
fan-out (git log, inbox, lessons, dogfood-orchestration.md, status.json) and reports
what it demonstrates about concurrent dreamers. **No code changed, no design chosen.**
The design half landed at `914648c`; this is the evidence it did not have.
**Report path:** this file only.

## How the counts were derived, and where they disagree with the coordinator's prose

Every count below is from `git log`, not from `dogfood-orchestration.md`. The
disagreements are recorded because the brief makes them findings.

| Measure | git-derived value | `dogfood-orchestration.md` says | Agreement |
|---|---|---|---|
| Commits, 2026-07-27 → 2026-07-28 (both days) | **496** | (not stated as a total) | — |
| Commits, 2026-07-28 only | **235** | (not stated) | — |
| Commits, fan-out window 05:10→08:34 (first dispatch → this brief) | **121** | (not stated) | — |
| Distinct task-lanes dispatched (counting #263's sub-lanes A/B/B2/C/D/F separately) | **~17** | "thirteen lanes" (final tally, line ~657) | **Disagree — see below** |
| Distinct task-lanes (counting #263 as one task with phases) | **~12** | "thirteen" | closer, still soft |
| Peak concurrency the record states | **5** ("five lanes live", 06:30) | "thirteen parallel lanes" (brief title) | **Disagree** |
| Files touched >1× in the fan-out window | **30+** (tasks.md 30×, lessons.md 22×, dogfood doc 10×, watch.py 7×, …) | "the binding constraint is file ownership" | agrees in spirit |

**The "thirteen" is a cumulative dispatch tally, not a concurrency figure, and the
doc revises it three times in two hours.** It reads "nine lanes, six refutations"
at 06:56, "ten lanes, seven refutations" at 07:15, and "Thirteen lanes" in the
closing section. The peak number of lanes running *at the same time* the doc itself
records is **five** (06:30). `git log` shows the dispatch commits but **does not
label a "lane"** — lane identity is coordinator-assigned via the briefs, so no
lane count is strictly derivable from git; any number is partly coordinator-sourced.
The honest reading: **~17 lane-instances were dispatched across the session, peaking
at 5 concurrent, and "thirteen" is the coordinator's own running count at the moment
they stopped adding to it.** That the headline figure drifts and is never a measured
concurrency is itself a finding about the record `#264` would cite.

`watch.py` was touched by **four distinct parties** in the window (`#277`, `#300`,
`#385`, `#391`) — but **sequentially**, each merged before the next began. That is
serialisation (question 4), not concurrent damage, and it is the single most
load-bearing fact in this document.

---

## Q1 — Every incident, each with a locator (the spine)

Labelled **[DAMAGE]** (the state was wrong or work corrupted) versus **[NEAR-MISS]**
(would have been damage; caught, or never reached a durable state). The ratio is
`#264`'s answer, so they are not mixed.

### [DAMAGE] 1 — Lane A's A2 test buried in the coordinator's `file(#387)` commit
**Locator:** commit `12f47e3` (`file(#387): the hook from #361…`), acknowledged at
`f4e922a` ("I buried its A2 test in my own commit"); cited in `CLAUDE.md`.
**What touched what:** the coordinator filed `#387` with a plain `git commit` (not
`--only`); the index held lane A's staged `test_user_events_digest.py` (+48 lines,
the A2 increment). `git show 12f47e3 --stat` lists `tasks.md` (+28) **and**
`test_user_events_digest.py` (+48). Lane A's own A1 commit is `aad1d8d` (05:55:41);
A2's test has **no commit of its own** — it lives only inside the `#387` filing commit.
**Damage:** provenance/ownership corruption — a lane's increment is attributed to the
wrong task. The bytes are present, so the tree is functionally intact; the assignment
and the citation chain are not. **Caught by:** the coordinator's own `git show --stat`
after the fact, recorded at `f4e922a`. This is the canonical incident `CLAUDE.md` cites.

### [DAMAGE] 2 — Lane B's full suite was RED before and after its work, from other lanes
**Locator:** `.dreamwork/inbox.md`, lane-b-journal report (#263 B1–B4), the
"Acceptance criteria §3" block.
**What touched what:** lane B's baseline was `1 failed, 887 passed` — the failure was
lane C's in-progress `test_a_second_process_cannot_read_while_the_lock_is_held`. After
lane B's four commits it was `1 failed, 897 passed` — the failure was now
`test_answers_route_and_ask_are_wired`, because **another lane's uncommitted `watch.py`
was dirty in the working tree** ("working-tree dirty `watch.py` from another lane; not
in my commits").
**Damage:** the full `just test` suite was **unusable as a green/red signal** for lane
B; it had to retreat to running only its own file (`pytest test_user_events_sqlite.py`)
to prove "my damage is zero." The shared tree forced per-file verification. **Caught
by:** lane B itself, by isolating to its owned file and reading the failure names.

### [DAMAGE] 3 — Lane C's full-suite run timed out and threw a false failure under load
**Locator:** `.dreamwork/inbox.md`, lane-c report (#263 C1–C3), criteria §3 note:
"an earlier full-suite run hit a 200s timeout + one `F` (`BrokenPipeError` in an HTTP
test) — that was pure load flake under load ~60 with several lanes live."
**What touched what:** several concurrent lanes (one of them `#386` deliberately
generating CPU load) starved lane C's HTTP test of wall-clock.
**Damage:** a false red that lane C had to explain away and re-run with a longer bound.
Same class as #2 — the shared *machine* corrupted the verification signal even though
no file was shared. **Caught by:** lane C, by re-running with a longer timeout.

### [DAMAGE] 4 — `git checkout --` injection-undo ate uncommitted work and faked two reds
**Locator:** commit `5216bf0` (lesson, 2026-07-28 00:54 — **pre-fan-out**, included
because it is the same failure class already on record).
**What touched what:** while red-proving `#348`, each injection was reverted with
`git checkout -- review_artifact.py`. The first revert took the uncommitted `_SQL` spec
with it; injections two and three then ran against a tree with the feature gone and
"read exactly like discriminating reds."
**Damage:** ~20 minutes of work destroyed and two proofs rendered worthless; neither
fact announced itself. **Caught by:** `git status` showing only the test file modified.
**Relevance to #264:** this is the uncommitted-work-destroyed class — the exact hazard
a shared tree multiplies when N agents hold in-flight edits.

### [NEAR-MISS] 5 — A `cd` redirected a write into a RUNNING agent's worktree
**Locator:** commit `677364b` (lesson, 2026-07-27 23:54 — **pre-fan-out**).
**What touched what:** right after `cd .worktrees/339-highlight && ccc …`, an append
meant for the main checkout's `lessons.md` landed in the running agent's worktree copy
—"a file it did not own and had no reason to see modified."
**Would-have-been damage:** a commit carrying another agent's untracked edit.
**Caught by:** `lint.py` reporting `status.json absent` (impossible in the main
checkout, normal in a worktree); reverted with `git -C <worktree> checkout --` before
it reached a commit. **Note:** this one involved a worktree, and is cited again in Q3
as a cost worktrees *add*.

### [NEAR-MISS] 6 — `--only <directory>` silently left three lane briefs uncommitted
**Locator:** commits `d77630e` ("the three from the last dispatch, which `--only`
silently left behind"), `c036540`, `3c58c17`, `a604010`, `94ebea3`.
**What touched what:** lanes were told to commit with `git commit --only <directory>`;
`--only` on a directory silently skips untracked files, so the briefs for `#300`,
`#385`, `#386` never landed.
**Would-have-been damage:** loss of the durable work-instructions for three live lanes
on any clean. **Caught by:** the coordinator's `git status` / `git show --stat`.

### [NEAR-MISS] 7 — A lane edited `justfile` outside its ownership list
**Locator:** commit `3f9cf5a` (lesson) + `6ca28dc` (relay ratification).
**What touched what:** `#367` increment 2a required a new guard, which only "counts"
once registered in `DEFAULT_GUARDS` (`justfile`) — but `justfile` was not in the lane's
ownership list and `lint.py` was held by another lane. The lane appended `markrail`
to `DEFAULT_GUARDS` anyway.
**Would-have-been damage:** a disjointness collision on `justfile`. The lesson states it
plainly: **"Nothing collided only because no other lane needed the `justfile` — that
was luck, not design."** **Caught by:** the coordinator, who ratified it by relay rather
than reverting.

### [NEAR-MISS] 8 — Load made the motion guards deterministically red
**Locator:** `dogfood-orchestration.md` §"The finding that constrains the whole model"
(lines ~219–270): `/proc/loadavg → 125.49 … nproc → 16`; plugcmd run twice back-to-back
"produced byte-identical failure sets"; the same checks passed at 05:05 when run alone.
**What touched what:** `#386`'s brief asked it to characterise a flake "under moderate
load (3 busyloops)"; `#300` was concurrently measuring per-frame motion in the same tree.
Two lanes that could not touch the same byte interfered *through the machine*.
**Would-have-been damage:** real defects mis-attributed to load, or real fixes rejected
as flaky. **It bit for real:** `#391` (prominence regression) was **initially dismissed
as a load flake** and had to be re-filed as genuine (`b5d541a`, "a real regression, not
the load flake it was reported as"). That promotes this from near-miss to **actual
damage to the triage decision** — labelled near-miss on the code, damage on the process.

### [NEAR-MISS] 9 — `#386`'s load generator orphaned its workers and leaked five cores
**Locator:** commit `3d4ad51` (lesson).
**What touched what:** each round's `/tmp/busyloop.py` workers were reparented to
`systemd --user` when their shell exited and kept spinning — load hit **161 on 16
cores**, of which only four processes were live.
**Would-have-been damage:** compounded #8 into sustained, reliable reds. **Caught by:**
the coordinator checking process *parentage* (ppid), not CPU.

### [NEAR-MISS] 10 — Two browser lanes would have silently graded each other's server
**Locator:** `dogfood-orchestration.md` §5 of the orchestrator notes (line ~455):
"every guard defaults to **one port** (39899), so two lanes would have silently graded
each other's server"; corroborated by a lane report, `.dreamwork/inbox.md` line ~892:
"the suite is contended, and the port range is in use by another lane."
**Would-have-been damage:** a guard verdict from the wrong server. **Caught by:** the
justfile pre-flight comment and explicit per-lane port assignment.

**Incident count: 10 with locators. DAMAGE: 4 (one pre-fan-out). NEAR-MISS: 6 (one
pre-fan-out, one of which — #8/#391 — caused real decision damage).** The pre-fan-out
items (4, 5) are dated as such and are the same classes the fan-out then multiplied.

---

## Q2 — The four mechanisms: held vs failed, or "no instance found"

| Mechanism | Held (instance) | Failed (instance) or **no instance found** |
|---|---|---|
| **Stated ownership list per lane** | Lane B's inbox report proves it touched only `user_events/sqlite.py`, `test_user_events_sqlite.py`, `.gitignore`, listing `git show --stat` for `6a865e4 9bea281 2e1e987 37d0066`; dogfood doc: "4/4 stayed inside ownership." | **Failed:** `#367`-inc2a edited `justfile` outside its list (`3f9cf5a`). Held by luck, not design. |
| **`git commit --only <paths>`** | Held hundreds of times on explicit *file* paths — lane B/C reports: "Each of my four commits lists only those paths." | **Failed (edge):** `--only <directory>` silently skipped untracked briefs (`d77630e`). **The brief's specific worry — `--only` sweeping a concurrent lane's uncommitted *hunk in the same file* — NO INSTANCE FOUND.** The one index-sweep that did happen (`12f47e3`) was a *plain* `git commit`, i.e. the absence of `--only`, not its failure. |
| **Single-writer ledger (`tasks.md`)** | **Held for write-safety:** all 30 `tasks.md` commits in the window are by the coordinator; verified `git log -- .dreamwork/tasks.md \| grep -v 'Max Kaye'` → empty. No lane ever committed the ledger. | **No concurrent-write instance found.** The single-writer's *correctness* failed separately (Q5: `status.json` drift), but that is not a concurrency failure. |
| **Append-only inbox** | **Held throughout:** dogfood doc "all four appended once to the inbox, none used attn"; no clobber recorded. | **No failed instance found.** Append-only-by-convention held under 13 writers. |

**Six of eight boxes carry an instance; two are honest "no instance found."** The two
absences are themselves results: the most-feared mechanism (same-file hunk sweep under
`--only`) did not occur, and neither of the two single-writer channels (ledger, inbox)
ever saw a concurrent write. The failures cluster around the mechanisms, not within them.

---

## Q3 — Shared tree vs worktree: costs each way, evidenced from the one worktree lane

The one worktree lane was `#277` (c2c peer in `.worktrees/277-dreamfade`, merged at
`0b3512e`/`955e189`). CLAUDE.md prescribes worktrees when disjointness cannot be
arranged; today used one shared tree for everyone else.

**Incidents a worktree would have PREVENTED (shared-tree cost):**
- **#2** (dirty `watch.py` polluting lane B's suite) — isolated tree ⇒ no foreign dirt.
- **#3** (load-flake false red in lane C's HTTP test) — *not* prevented; load is
  machine-wide, not tree-wide. (Listed to be honest: a worktree fixes the *file*
  pollution, not the *CPU* pollution.)
- **#6** (untracked briefs skipped) — *not* prevented; that is an index/CLI edge,
  present in a worktree too.
- **#1** (`12f47e3` index sweep) — *not* prevented; a worktree has its own index, but
  the sweep was the coordinator's own commit in the main tree, and merges bring the
  same hazard back.

So of the 10 incidents, a worktree would have prevented **exactly one class for sure —
working-tree file pollution (#2 and the file-dirt half of #3)**, i.e. ~2 of 10.

**Costs the worktree ADDED (evidenced from `#277`):**
- **Loss of visibility:** dogfood doc — the peer's "work sat uncommitted for hours where
  I could not see it — I only learned what it was doing by reading its worktree diff."
- **Unreviewed merge:** `955e189` "the peer merged it itself, and the merge is kept" —
  the coordinator accepted a merge it had not reviewed.
- **The `cd`-redirect hazard (incident #5):** the write-into-the-wrong-tree incident was
  *into a worktree*; worktrees introduce a second cwd that a stale `cd` can silently
  target.

**Net finding:** worktrees trade the file-pollution class (~2 incidents) for a
visibility-and-merge-review class (~3 costs). They do **not** touch the load class (#8,
#9), the index/provenance class (#1, #6), or the registry-coupling class (#7) — which
are the majority of today's incidents. A worktree is the right tool for the file-pollution
failure mode specifically; it is not a general answer to what went wrong today.

---

## Q4 — Where serialisation actually bit, and the bottleneck file

`status.json` states it directly, and git confirms: **`watch.py` is the bottleneck.**

- **`watch.py`** — touched by 4 parties (`#277`, `#300`, `#385`, `#391`), each merged
  before the next began. `status.json` `coordinator_next`: *"Approved and unstarted, all
  needing watch.py and therefore BLOCKED while dreamer-284-252 holds it: #295, #351,
  #337, #331, #322, #352 (parser dedup)."* — **six tasks queued behind one file.**
- **`#354` increment 1 was deliberately NOT dispatched** because of it: `a6c0732`
  "queue(#354 inc1): brief written and deliberately NOT dispatched — watch.py is
  contended." A correct, ready brief sat idle for no reason except that one 8,647-line
  file admits one writer.
- **Guard ports** — secondary bottleneck. A lane could not verify ("the port range is in
  use by another lane", inbox ~892); every guard defaults to one port, so browser lanes
  must be serialised against each other too.
- **The ledger / coordinator attention** — dogfood doc §3: *"I became the bottleneck on
  shared state, and it is serial. Every lane that finishes generates work only the
  coordinator may do… Three lanes produced five such edits in fifteen minutes. Parallel
  workers, serial ledger."*

**The contended file, named with evidence: `watch.py`, with six tasks waiting and one
correct brief shelved.** The dogfood doc's own conclusion — that the modular split
(`#368`) is "now measurable rather than aesthetic: it is the difference between one
watch.py lane and three" — is the directly-evidenced consequence for `#264`.

---

## Q5 — Broke from parallelism, not from concurrent access (the class #264 does not anticipate)

These are second-order: no two lanes wrote the same record, yet parallelism broke things.

1. **Load destroyed guard verdicts** (#8). The repo's most careful checks assert on
   *intermediate frames of a transition*; a CPU-starved browser cannot deliver frames on
   schedule, so they fail *deterministically*, not flakily. Verification had to be
   serialised against the lanes — removing exactly the throughput parallelism was for.
2. **Load-generator orphans** (#9) compounded #8 into sustained reds and hit load 161.
3. **The full suite became noise** (#2, #3): lanes retreated to per-file `pytest`
   because the shared tree's full-suite signal was red with other lanes' in-flight work.
   The verification regime was *structurally reduced* by parallelism.
4. **A real regression was initially dismissed as load flake** (`#391`, `b5d541a`):
   load noise corrupted triage, not just verification.
5. **Registry/baseline coupling** (#7, and its inverse): a new file in a
   registry-checked directory, or a new guard, reddens *other* lanes' `lint.py`
   baselines until registered — so a lane's deliverable can break a lane it never
   touched. The brief names this one; it is real and it is invisible in the guard output.
6. **The coordinator's single-writer output drifted** under lane throughput
   (dogfood doc §"Nobody reviews the coordinator"): `current_task_ids` named `[263, 385,
   389]` hours after all three closed; `deployed` named a dead pid/rev; both render on
   the dashboard. This is not concurrent access — it is the single writer overwhelmed by
   parallel producers, carrying fields forward across ticks.
7. **The coordinator became the serial ledger-writer** (dogfood §3): throughput at the
   workers did not raise throughput at the ledger.

**The common shape:** every item here is an *environmental* or *coupling* failure —
shared CPU, shared working tree, shared registry, shared single-writer — not a
record-write race. **This is the class `#264`'s option list does not address**, and it is
the majority of today's incidents.

---

## Q6 — What the evidence rules OUT

1. **It rules out that "disjoint file ownership is sufficient for safe parallelism."**
   Disjoint ownership held for writes (Q2: zero concurrent write-write commits). It did
   not prevent 8 of the 10 incidents, because those incidents were not write collisions.
   Any `#264` option that is purely record-level — locks, CAS, leases, SQLite WAL,
   per-record spools — would have prevented **zero of today's actual damage**, because
   today's actual damage was not two writers on one record.
2. **It rules out that the ledger/inbox need a new concurrency mechanism.** The two
   single-writer channels (`tasks.md`, `inbox.md`) had **zero** concurrent-write
   incidents across 13 writers and 121 commits. The single-writer rule held by
   construction. A lease or CAS on the ledger solves a problem that did not occur.
3. **It rules in that the binding problems are environmental, not transactional.** The
   incidents that did occur — load-starved motion guards, working-tree pollution, a
   coordinator index sweep, registry-coupled baselines, a overwhelmed single-writer —
   survive any record-level concurrency control. They are properties of *one shared tree
   on one shared machine with one shared coordinator*, not of the write protocol.
4. **The one record that approximates write-contention — `watch.py` — was safe by
   serialisation, not by a mechanism `#264` would build.** Four parties wanted it; they
   took turns; six tasks waited. The fix that the evidence points at is the one the
   dogfood doc already names — **splitting `watch.py` so more than one lane can hold a
   piece of it** — which is a modularity decision, not a concurrency-primitive decision.

**Bottom line for #264:** the record kills the premise that today's failures are the
concurrency failures `#264` lists. The listed mechanisms address write-write contention
on shared state; the shared state never saw write-write contention. What failed was the
*shared environment*, and the single most useful sentence this corpus supports is:
**record-level concurrency control would have changed none of today's outcomes; the
outcomes were set by shared CPU, a shared working tree, a shared registry, and one
overloaded single-writer.**

---

## What I am not confident about

- **The lane count.** Git does not label lanes; "lane" is coordinator-assigned via
  briefs. My ~17 (sub-lanes separate) / ~12 (#263 as one) / peak-5-concurrent are
  inferences from dispatch commits + the doc's own concurrency statements. The doc's
  "thirteen" is a soft, self-revising tally. None of these is a hard git figure.
- **Whether a same-file `--only` hunk-sweep ever occurred.** I found no record of one.
  The absence is consistent across lessons and inbox, but I cannot prove a negative from
  commit metadata alone; a hunk-sweep leaves no mark `git show --stat` would surface.
  I report it as "no instance found," not "proved impossible."
- **Pre-fan-out incidents (#4, #5).** They are dated 2026-07-27/early-07-28, before the
  05:10 fan-out. I include them because the brief's corpus spans both days and they are
  the exact failure classes the fan-out multiplied — but they are not themselves
  thirteen-lane incidents, and I have labelled them as such.
- **The `#391`-as-load-flake dismissal.** I rely on the coordinator's own re-filing
  (`b5d541a`) for the claim that load noise caused a real regression to be initially
  dismissed; I did not re-derive the prominence regression independently (out of scope —
  no code, and `watch.py` is held).

--- SUMMARY ---

- **Counts (git-derived):** 121 commits in the fan-out window (05:10–08:34), 235 on
  2026-07-28, 496 across both days. ~17 lane-instances dispatched, **peak 5 concurrent**;
  the doc's "thirteen" is a cumulative, self-revising tally, not a concurrency figure.
- **Incidents: 10 with locators — 4 DAMAGE, 6 NEAR-MISS** (one near-miss, `#391`,
  caused real triage damage). Two are pre-fan-out, same class, labelled as such.
- **No concurrent write-write commit on any file occurred.** The ledger and inbox saw
  zero concurrent writes across 13 writers. The single-writer rule held by construction.
- **The four mechanisms:** ownership list held (failed once, by luck); `--only` held on
  files (failed on directories; **same-file hunk-sweep: no instance found**); single-writer
  ledger held for writes; append-only inbox held throughout.
- **Bottleneck: `watch.py`** — 4 sequential parties, 6 tasks queued, one correct brief
  shelved (`a6c0732`). Secondary: guard ports.
- **Worktree trade:** would have prevented ~2/10 (the file-pollution class); added ~3
  costs (visibility loss, unreviewed merge, `cd`-redirect). It does not touch the load,
  index, or registry classes.
- **Q6 — what's ruled out:** record-level concurrency primitives (locks/CAS/leases/
  SQLite/spools) would have prevented **zero** of today's actual damage, because today's
  damage was not write-write contention — it was shared CPU, a shared working tree, a
  shared registry, and one overloaded single-writer. The evidence points at modularity
  (splitting `watch.py`), not at a concurrency mechanism.
- **`python3 lint.py` exits 0**; one file written, nothing else touched.

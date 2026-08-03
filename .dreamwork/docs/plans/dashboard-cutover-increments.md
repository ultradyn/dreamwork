> **Coordinator action required before landing:** add
> `dashboard-cutover-increments` to the plans row in
> `.dreamwork/docs/doc-map.md`. This lane does not own that custodial file.
>
> **Planning only.** No production seam changes here, so no red-proof is owed.

# Dashboard cutover increments

This plan scopes the visible React conversion of `/`. It complements, rather
than repeats, `react-migration-increments.md`: that ratified plan exports
derived wrappers whose markup still comes from incumbent builders; this plan
moves live dashboard surfaces and retires their string authority.

## Verdict

Convert one complete dashboard panel authority at a time inside the incumbent
dashboard shell, then flip the shell and delete `buildDashboard` in one final
commit. The first panel also lands the generic island lifecycle, so no
unreachable infrastructure or component-only preparatory commit is required.

This is legal because `buildDashboard` serves one route. `/tasks` and
`/tasks2` both resolve to `tasks2`, which returns `buildTasks2(...)` before the
dashboard fallthrough. The default route alone reaches `buildDashboard`.
Every intermediate commit must therefore keep `/tasks` on `tasks2`; making it
match `/` would be a routing regression, not compatibility.

The exact deletion claims are:

- **zero prior increments before the first string builder can be deleted:**
  D1 converts topic chats and deletes the private `chatList`/`chatRow` string
  authority in that same commit;
- **eight increments before `buildDashboard` can be deleted:** D1-D8 remove
  every panel and control from its markup authority; D9 atomically moves the
  remaining shell/order and deletes the builder;
- no earlier increment may claim that `buildDashboard` is dead merely because
  some or most of its panels are native.

Implementation sizing starts from these boundaries. This document does not
invent elapsed-time estimates for work whose live event seams have not yet
been implemented.

## Current-tree measurement

The code graph reports 16 ordinary `CALLS` edges out of `buildDashboard`.
That graph count misses the two bare callbacks passed to `Array.map`. The
callback-aware census used by the dashboard assembly guard adds `gitRow` and
`dreamBlock`, so the current result is **18 unique application callees**
(excluding `map`, `join`, and `slice` themselves):

`qHealth`, `goalHandle`, `label`, `servingLine`, `gitRow`, `dreamBlock`,
`expand`, `chatList`, `qSection`, `artifactRow`, `mdB`,
`groupProgressPanel`, `burnPanel`, `statusBlock`, `posturePicker`,
`subagentPolicyPicker`, `tintPicker`, and `drawModePicker`.

One route bounds the eventual authority flip, but 18 callees and the distinct
QA, tick, POST, persistence, focus, and shader lifecycles make a one-commit
rewrite unsafe. The route correction removes a phantom constraint; it does
not remove the work.

## Authority rules in force

- The renderer/second-truth prohibition was **relaxed on 2026-07-31 19:09**.
  A temporary renderer twin is costly, not illegal.
- The cheaper shape remains per-surface single authority. A derived wrapper
  still calls the incumbent builder and is not another markup authority. When
  a native panel becomes live, its incumbent string fragment or private
  builder is removed in the same commit.
- The QaCard-family cut is already decided by
  `1069-qacard-scope.md`: all four QaCard-bearing compositions move as one
  subtree family, while their outer route shells may remain legacy. This plan
  consumes that boundary and does not reopen it.
- The authenticated Claude-design checkpoint is **dissolved as a migration
  gate, not satisfied**, by the 2026-08-03 16:06 ruling “Claude design comes
  AFTER react.” Nothing here waits for it or claims that ingestion occurred.

## IGC decision

**Context.** `/` is the only `buildDashboard` route; mixed native and legacy
routes already ship; no component-island lifecycle exists yet; the complete
QaCard subtree boundary is ratified. “Same `/` + `/tasks`?” and “prior
increments” are factual columns, not goals, and do not participate in `All`.

| Idea | All | G1 | G2 | G3 | G4 | G5 | Same `/` + `/tasks` throughout? | Prior increments before any string deletion |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| One `/` route flag day | ✘ | ✘ | ✔ | ✔ | ✔ | ✘ | No — correct | 0 |
| Flip a derived React shell, prepare all groups off-route, then swap | ✘ | ✔ | ✘ | ✔ | ✔ | ✘ | No — correct | 4 |
| Convert broad data-dependency bands | ✘ | ✘ | ✘ | ✘ | ✔ | ✘ | No — correct | 0 |
| Convert bottom-up by callee depth | ✘ | ✘ | ✘ | ✘ | ✔ | ✘ | No — correct | at least 4 shared-leaf increments |
| **Convert complete panel authorities as live islands; flip shell last** | **✔** | **✔** | **✔** | **✔** | **✔** | **✔** | **No — correct** | **0** |

- **G1:** the first increment is a bounded, deployable vertical slice and no
  increment needs later work to make its own surface correct · **G2:** each
  converted surface has one live markup authority and loses its incumbent
  string output in the ownership commit · **G3:** the complete QaCard-family
  cut is preserved rather than split by route or helper · **G4:** the final
  `buildDashboard` deletion is bounded to `/` and never moves `/tasks` ·
  **G5:** every increment has a non-vacuous proof through the live tick/event
  seam, not an off-route component snapshot promised verification later.

Decisive errors:

1. The route flag day has clean end-state authority, but no bounded first
   commit: all 18 callees and every event lifecycle must be correct before
   anything can land. It fails the purpose of this scoping task.
2. A derived shell is legal and independently deployable, but it leaves
   `buildDashboard` as one opaque string. Off-route components cannot prove
   live reconciliation, and four staging increments must land before any
   string authority is retired.
3. Data bands group fields that update together but split authorities that
   act together: QaCard state spans four compositions, while operational
   controls have distinct POST, focus, persistence, and shader lifecycles.
4. Callee depth is not a surface boundary. Shared leaves such as `label`,
   `expand`, and `artifactRow` still have other consumers, while splitting
   QaCard from its compose/thread satellites creates the rival authority the
   existing QaCard scope rejects.
5. Panel islands survive because the string shell may emit a mount host but
   cannot emit or reconcile the converted subtree. The first simple panel
   pays for and proves the lifecycle; later panels reuse it; the final route
   flip changes composition ownership without changing panel behavior.

## Landing sequence

The identifiers are `D1`-`D9` so they cannot be confused with the ratified
wrapper plan's increments 1-10. Each increment includes `just build-client`,
the full test files it changes, the repo-wide guard set, and lint row-set
comparison in addition to the specific proof named below.

### D1 — Topic-chat panel plus the first live island

**Moves:** add the generic mount/update/unmount contract for a component host;
move the dashboard topic-chat count, empty state, and rows into a native
`DashboardChats`; replace the `chatList(d)` call with that host; delete
`chatList` and its private `chatRow` helper after the final name census.

**Owns:** React owns the entire topic-chat panel. The legacy router still owns
navigation and tick scheduling; `buildDashboard` owns only the host's position.

**Proof:** component fixtures cover zero chats, read chats, unread counts, and
two adjacent rows; the current topic-chat assertions in `test_watch.py` run
against the mounted component; the `chatsurface` guard proves a live `/` tick
updates the same host and links to `/chat/<id>`. A deletion census rejects a
remaining `chatList`/`chatRow` definition or call.

**Why independently landable:** lifecycle and first consumer land together,
the live panel retains all current states, and the prior string builder is
gone. No later panel is required. **This is the first dispatch.**

### D2 — QA population as the already-ratified family cut

**Moves:** implement the complete subtree cut from
`1069-qacard-scope.md` across `/questions`, dashboard Q&A, `/question`, and
the `/review` dock. Dashboard's Q&A label and answers link remain shell-owned
until D9. Delete the reachable `qaCard`, `qaInner`, `qaCompose`,
`followThread`, and `qSection` string authorities and retire their derived
builder claims in the same commit.

**Owns:** one native QaCard/QaCompose/FollowThread family owns card render and
local state; surface adapters own population/grouping; the router remains the
single cross-card/route motion and reduced-motion authority. This consumes
ratified wrapper increments 1 **“QaCard proves the delegating-wrapper path end
to end”**, 5 **“Export `FollowThread`”**, and 6 **“Export `QaCompose`”** as
bridges; it does not recreate them.

**Proof:** all five proof obligations in `1069-qacard-scope.md` are blocking:
four-surface source census, real tick/morph per composition, held answer and
note POST raced with a tick, the full tick-mid-edit inventory, and paired
reduced-motion assertions. Run the full QA/client modules plus the `qacard`,
`qsec`, `qgroup`, `qdual`, `docktarget`, and submit guards.

**Why independently landable:** every QaCard consumer changes in this commit,
so no builder/component pair remains. Outer dashboard, questions, and review
shells remain valid and need no later route flip.

### D3 — Operational readout: group progress and status

**Moves:** native group-progress and status panels replace
`groupProgressPanel` and `statusBlock`; delete those private builders.

**Owns:** React owns readout structure, status complement/folds, pending
handoffs, and queue facts. Existing collection and tick code continue to own
the data; no new status derivation is introduced.

**Proof:** populated, absent, unreadable, queue, and pending-handoff fixtures
run through the mounted production component; the `status` and
`groupprogress` guards prove live-tick updates and non-vacuous rows.

**Why independently landable:** these readouts have no POST or shader
dependency. Their host replaces their old markup and works before every other
operational control moves.

### D4 — Operational control: burndown

**Moves:** replace `burnPanel` with a native burndown component and delete the
builder in the same commit.

**Owns:** React owns burndown DOM and local control state; incumbent ledger
collection, preference storage, and command endpoints remain data/transport
authorities.

**Proof:** the `burndown`, `bdinput`, and `bdhover` guards prove real history,
step/limit behavior, hover details, and focused input survival across a tick;
the full burndown assertions in `test_watch.py` bind the production mount.

**Why independently landable:** it is one interactive panel with its whole
focus/persistence lifecycle. It does not wait for posture, tint, or shell work.

### D5 — Operational control: posture/deploy and subagent policy

**Moves:** native posture/deploy and policy controls replace
`posturePicker` and `subagentPolicyPicker`; delete both string builders.

**Owns:** React owns selection, drafts, countdown presentation, and policy
input state; the existing arm/deploy/policy POST paths remain the sole write
and receipt authority.

**Proof:** full posture/policy tests exercise success, refusal, countdown,
sticky selection, deployment, and a tick during an armed draft; the `posture`
and `posturerecuse` guards bind the live controls and response path.

**Why independently landable:** the two controls share one posture/policy
transaction boundary and move together. No visual-preference or shell state is
needed for their POST lifecycle to finish green.

### D6 — Operational control: tint and shader draw mode

**Moves:** native visual-preference controls replace `tintPicker` and
`drawModePicker`; delete both builders.

**Owns:** React owns the two picker DOM/state presentations. Existing tint
server persistence, draw-mode browser storage, cross-tab adoption, and
`dreambg` shader APIs remain their single effect authorities.

**Proof:** full tint/draw-mode assertions cover default, invalid fallback,
selection, server refusal, storage events, and cross-tab adoption; the
`drawmode` guard proves the rendered modes drive the live shader rather than a
component-only substitute.

**Why independently landable:** both visual controls can mount at the bottom
of the legacy shell and exercise today's effect APIs without any later panel
or route ownership change.

### D7 — Remaining panels I: health and activity

**Moves:** native health, goal handle, commits/serving, and dream/archive
panels replace their dashboard string fragments. `qHealth` moves on every
remaining surface that consumes it so its builder can be deleted; private
`goalHandle` and `servingLine` builders are deleted. Shared leaf builders stay
derived until their own last consumer moves.

**Owns:** React owns dashboard health/activity composition and list/empty
states. Collection, commit ordering, liveness calculation, and archive data
remain incumbent data authorities.

**Proof:** fixtures cover unreadable/healthy questions, absent/present goal,
zero/multiple commits, serving state, active dreams, and non-empty archive;
the `health`, `dashboard`, `serving`, `gitrow`, `dreamfade`, `goalfault`, and
`goalorder` guards prove current route order and live updates.

**Why independently landable:** the increment moves one read-only top-of-page
composition and all last consumers of the only shared helper it deletes. QA
events and lower controls are already separate hosts.

### D8 — Remaining panels II: reviews and files

**Moves:** native dashboard reviews preserve quiet-when-empty, the cap, and
the all-reviews link; native files preserve the three named documents,
Markdown rendering, and disclosure identity. Their inline string fragments
leave `buildDashboard` in this commit.

**Owns:** React owns both artifact panel compositions. Ratified wrapper
increments 2 **“Export `Label`”**, 4 **“Export `Expand`”**, 7 **“Export
`ArtifactRow`”**, and 8 **“Export one route composition: `Reviews`”** remain
derived leaves where still shared; this plan does not restate their markup.

**Proof:** review fixtures cover empty, at-cap, and over-cap populations with
stable order and links; file fixtures cover missing and populated Markdown
plus disclosure persistence. The `reviews5` guard and full wrapper/Markdown
tests prove the live dashboard behavior and derived-leaf contracts.

**Why independently landable:** both panels are read-only compositions over
already-shipping derived leaves. Their old inline markup is removed now; D9 is
not needed to make either visible or correct.

### D9 — Shell cutover and atomic `buildDashboard` deletion

**Moves:** register a native `Dashboard` route that directly composes the D1-D8
components in current order; move the `#sections` wrapper, dashboard Q&A label
and answers link, and any residual empty/ordering chrome; remove dashboard
island hosts that are no longer needed as route children; delete
`buildDashboard` and its router fallthrough call. Retarget or retire wrapper
plan increment 9's future **“Dashboard”** derived export if it exists by then.

**Owns:** React owns the `/` shell and all its panel composition. The router
continues to own navigation, data fetch/tick, cross-route motion, and `/tasks`
as `tasks2`.

**Proof:** a route census asserts `/` has one native registry authority,
`buildDashboard` has no definition/call/export, and `/tasks` plus `/tasks2`
still reach `buildTasks2`. A full dashboard fixture asserts panel order and
all hosts populated after initial load and a tick; the `dashboard` guard runs
the real `/` route rather than a mounted component in isolation.

**Why independently landable:** every child is already live and proven before
this commit. The shell flip changes only composition ownership, deletes the
one-route builder atomically, and leaves no work for a later increment to make
`/` usable.

## Preparation versus deletion

D1-D8 are preparatory **for the outer builder deletion**, but they are not
dead preparation: each makes a live panel native, deletes that panel's prior
string authority, and carries its own proof. D9 is the eventual atomic
builder deletion. This distinction prevents both false claims: “nothing can
move until the whole dashboard moves” is too strict, while “a native panel
means `buildDashboard` can be deleted” is too loose.

If implementation discovers that one proposed group cannot remove its old
surface or prove its live event seam without D9, it is not an increment. Merge
that group into D9 and update the count; do not land an exemption that says it
will be verified later.

## How this plan could be wrong

1. The first island may expose a reconciler constraint that prevents a builder
   shell from hosting a component-owned subtree. D1 must then refuse; it may
   not leave duplicate topic-chat markup or unreachable infrastructure.
2. The QaCard family may be too large for one implementation dispatch. Its
   authority boundary is still atomic; inability to fit is a re-planning
   result, not permission to split a card from compose/thread or by route.
3. A helper census may find a consumer absent from the current code graph.
   The implementation must re-run name-based source and test/capture searches
   before deletion and include every live consumer or leave the shared helper
   derived.
4. Another route may flip before D7-D9. Re-resolve current consumers and
   native registrations; already-native work becomes **ALREADY DONE**, not a
   second implementation.

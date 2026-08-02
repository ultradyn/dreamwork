# Goal 1 membership proposal: React webui migration

## Verdict

`groups add-task` already exists. The help text describes it as “add one canonical task id to a
group”, so the conditional implementation task in the request is not owed. This lane is a
dogfood audit and produces a proposal for the coordinator; it does not mutate the live ledger.

I examined **188 open tasks** and propose **0 new links**. Goal 1 already has five members, and I
would keep all five. I rejected **183 open tasks** as clear non-members. One further task is
borderline and is listed below rather than being silently forced into the goal.

## Membership proposal

The coordinator should preserve these five existing Goal 1 members:

| Task | Title | Why it belongs to the React migration specifically |
| --- | --- | --- |
| #630 | Build the derived component surface + bundle step (the #591 survivor) | It is the migration's core build/runtime seam: it bundles the existing client assets into the React component surface and defines the phased conversion path. |
| #640 | The ratified #591 G2 artifact cites pre-drift line numbers, and implementers will read it as spec | It repairs the durable ruling artifact that directly governs whether and how the React component transition may proceed. |
| #692 | Import the design into Claude Design once the React webui has landed and we have transitioned | It is explicitly gated on the React webui landing and consumes the migrated component system after transition. |
| #823 | command composer: paste files and images as attachments (React-gated) | Its body explicitly says implementation must wait for and use React, so it is migration-gated rather than a current-client feature. |
| #859 | Evaluate popout windows as the first React surface instead of /research | It evaluates the first React migration surface and compares popout isolation against the current conversion sequence. |

No additional task is unambiguously ready for linking from this pass. The proposal is therefore
an intentionally zero-addition extension of the already-applied five-task slice.

## Borderline

- **#631 — Build the live session-log view (the #613 design).** Its body names a “SessionLog
  component” and asks whether it should use the new component system, but also says most of the
  work is independent of the React ruling. The settling question is: **is this task required to
  be implemented as part of the React migration, or may it land as a current-client component
  before/alongside that migration?** Until that is answered, linking it would conflate a future
  component feature with the migration itself.

## Rejections and scope

The 183 clear rejections are mostly dashboard behavior/style/content features, current-client
bugs, general `watch.py` modularity, data/ledger migrations, review/tooling work, and tasks whose
relationship is only that they happen to mention `client/`, `webui`, `router`, or `component`.
The goal wording is narrower: convert the webui to run through the React build and migrate the
watch server over. Unattached tasks are not defective; they remain unclassified for this goal.

I read the **title and body of all 188 open tasks**. Keyword candidates were then checked against
their full bodies. The title-only candidates were deliberately not treated as evidence.

Closed tasks were excluded before membership decisions. A task that genuinely concerned the
migration but is already landed is historical evidence, not open work to attach to Goal 1; adding
it would inflate progress with work that was not gated by this goal. No closed task is proposed.

## False-green constructions

### Title-match trap

I constructed the trap by comparing the keyword candidate list with the body audit: titles such as
“webui”, “component”, “client”, “bundle”, and “watch.py” produced many candidates whose bodies were
dashboard features, general refactors, or unrelated tooling. The mitigation is explicit full-body
reading for all 188 open tasks and a reason tied to the React migration for each retained member.

### Already-landed trap

The audit was restricted to `state='open'` before proposing links. Closed migration history was
not attached, so it cannot improve Goal 1's live progress denominator.

### Unanimous-subtree trap

The proposal is deliberately only the five migration-specific members already present. Dashboard
membership, current-client UI polish, and broad `watch.py` architecture were rejected even when
they could plausibly improve the dashboard. A long list would indicate that the goal's migration
wording had been ignored.

### Empty-population trap

This is not a failed zero-result pass: the denominator is **188 open examined**, the existing
membership is **5 retained**, the proposal adds **0**, and the clear rejection count is **183**,
with **1 borderline** separately named. The honest result is that the prior five-task slice
already captures the unambiguous React migration work currently filed.

## Dogfood friction report

1. **The command under test is unavailable to the dogfooding lane.** `groups add-task` mutates the
   single-writer ledger, so this lane was structurally forbidden from running the command it was
   asked to dogfood. I could inspect its help and the read-only store, and I could produce the
   exact proposal, but I could not learn whether applying one link gives a useful success/error
   message, rejects duplicates clearly, or handles a stale task id. Suggestion: provide a
   coordinator-applied proposal/dry-run mode that exercises validation and prints the exact
   mutation without allowing a lane to write the live store; the coordinator can then apply the
   resulting canonical commands.
2. **The brief's approximate open-task count is stale.** The task record says “~183”, while the
   authoritative read found 188 open tasks. Suggestion: generate the denominator beside the
   dispatch or require the report command to print it, so the lane does not carry a rotting
   headline number.
3. **Keyword discovery is useful but dangerous.** The candidate set was much larger than the
   actual migration set, and titles made false positives look plausible. Suggestion: add a
   read-only `groups suggest-tasks --group 1`/dry-run report that shows title, body excerpt, and
   explicit confidence/borderline status, while leaving the final membership decision human- or
   lane-authored.
4. **The existing set has no visible rationale in the group view.** The five members are
   traceable here, but `groups get` would only show ids/titles; it cannot show why each belongs to
   this goal rather than the dashboard parent. Suggestion: support an append-only proposal or
   membership note artifact, or include a reason field in a future write path without making the
   task body the second source of truth.

## Out of scope

Applying the five retained links or any new link is coordinator work because of the live
single-writer rule. #631 remains unlinked pending the question above. No CLI, ledger schema, task
body, dashboard, or unrelated documentation changes are made here.

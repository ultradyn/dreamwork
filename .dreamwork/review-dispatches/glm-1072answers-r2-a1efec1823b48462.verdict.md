# Review verdict — glm-1072answers round 2 (@cx-reviewer, gpt-5.6-terra)

Reviewed pinned `a5ffb2dce176d14464807fcec3bd480914426bb8`. Recovered by the coordinator from
the launcher's stdout log on 2026-08-04: the reviewer wrote NO inbox heading and NO review
decision, so this verdict existed only in a scratchpad file. Preserved here verbatim.

## Verdict

**ANOTHER ROUND** — reviewed pinned `a5ffb2dce176d14464807fcec3bd480914426bb8`. The lane branch subsequently moved to `2b97e396`; I did not review that new tip.

- **P1 — post-rebase red-proof was not re-armed.** The author registry/reach evidence is timestamped `06:58`, while rebases completed at `08:56` (onto `44397ea6`) and again at `09:02`. `redproof check --require 1 --base 44397ea6` exits 0 and reports `caught 1 of 1`, but that only validates the older recorded injection; it does not satisfy #993’s required fresh re-arm. Re-run the injection/control after the current rebase, then re-run the three gates.

- **P1 — the delegate can render nothing and the relevant suite stays green.** In an isolated clone, I replaced [Answers](/home/xertrov/.llm-general/skills/.worktrees/glm-1072answers-review-r2/dev/build/wrapper-exports.js line 104)’s builder output with `''`, rebuilt, staged only the generated dist needed by the deploy-index test, then ran:

  ```text
  python3 -m pytest test_client_dist.py -q
  42 passed in 32.69s
  ```

  The generic browser loop only requires every export to mount and preserve input; its strict output comparison is hard-coded to `Reviews` at [test_client_dist.py](/home/xertrov/.llm-general/skills/.worktrees/glm-1072answers-review-r2/test_client_dist.py line 524). Thus an empty or wrong `Answers` delegate ships green.

  Cheapest honest closure: add an Answers-only DOM serialization equality test over all five fixtures, comparing mounted `Answers` output with `buildAnswers(props.data)`. It need not alter the Reviews implementation or `#1071` source; generalizing the existing test is optional.

## Standards

- **P1 — the exported type contradicts production data and runtime.** [Answers.d.ts](/home/xertrov/.llm-general/skills/.worktrees/glm-1072answers-review-r2/dev/build/ds-src/Answers.d.ts line 10) permits only `"unreadable"` although the committed fixture uses `"ok"` and `watch.answers_health` can emit `missing`, `empty`, `unreadable`, or `ok`. It also makes `data` optional/null at [line 16](/home/xertrov/.llm-general/skills/.worktrees/glm-1072answers-review-r2/dev/build/ds-src/Answers.d.ts line 16), but [buildAnswers](/home/xertrov/.llm-general/skills/.worktrees/glm-1072answers-review-r2/client/views.js line 1213) dereferences it immediately. Make `data` required and model the complete health union, then rebuild the shipped declaration.

## Spec

The delegate shape itself is correct: it calls `buildAnswers(data)` and introduces no competing markup. I found no reliance on the stale “second truth” rule as a prohibition.

Other checks already completed before the red-proof chronology finding:

- Fresh `just build-client && git diff --exit-code -- client/dist/` passed. The unmodified relevant suite also passed: `42 passed in 32.93s`.
- Runtime is **146,462 / 147,000**, leaving **538 bytes**. The next runtime change does not mathematically have to fail, but any measured increase of **539+ bytes** will.
- All three `Answers` `DATA_SIBLINGS` entries are correct, present in the manifest inputs, and `ship_siblings('HEAD', temp)` actually wrote all three to the deploy snapshot.
- The fixture test sweeps every real record: open, answered, and both askform records. The five states reach the named `buildAnswers` paths; `askform` correctly demonstrates the unconditional composer alongside non-empty open and answered lists.
- The `q1`/`b` issue is an inherent limit of a shape/branch guard. A length threshold would reject it cheaply, but would be arbitrary rather than demonstrate more rendering behavior; the present claim is honest.
- Follow-up worth filing, not implementing:

  **Derive deployed ds-src companions from the revision build inventory**

  Replace the manually enumerated `dev/build/ds-src/*` portion of `DATA_SIBLINGS` with per-revision derivation from the build-input contract (or the revision’s manifest). Keep non-build data siblings explicit, preserve tree filtering, and add a red proof that a newly added/rebuilt companion triad deploys without a `watch.py` edit.
diff --git a//tmp/glm1072answers-delegate.1h305M/dev/build/wrapper-exports.js b//tmp/glm1072answers-delegate.1h305M/dev/build/wrapper-exports.js
index ce1d8427a60075c8e17b7c413ec3669c027f737e..516a4a5ec87475e58736112fe94fd746d11e1a37
--- a//tmp/glm1072answers-delegate.1h305M/dev/build/wrapper-exports.js
+++ b//tmp/glm1072answers-delegate.1h305M/dev/build/wrapper-exports.js
@@ -103,7 +103,7 @@
 
 export const Answers = ({ data }) => React.createElement(HOST, {
   'data-dw-delegate': 'buildAnswers',
-  dangerouslySetInnerHTML: { __html: buildAnswers(data) },
+  dangerouslySetInnerHTML: { __html: '' },
 });
 
 Answers.displayName = 'Answers';

hook: Stop
hook: Stop Completed
tokens used
252,251

**ANOTHER ROUND** — reviewed pinned `a5ffb2dce176d14464807fcec3bd480914426bb8`. The lane branch subsequently moved to `2b97e396`; I did not review that new tip.

- **P1 — post-rebase red-proof was not re-armed.** The author registry/reach evidence is timestamped `06:58`, while rebases completed at `08:56` (onto `44397ea6`) and again at `09:02`. `redproof check --require 1 --base 44397ea6` exits 0 and reports `caught 1 of 1`, but that only validates the older recorded injection; it does not satisfy #993’s required fresh re-arm. Re-run the injection/control after the current rebase, then re-run the three gates.


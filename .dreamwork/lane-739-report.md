# Lane 739 report

## Verdict

PASS. Added the single neighbouring-surface stub `const drawModePicker = () => '';` to the Q&A assembly-order harness in `test_watch.py`. Production code is unchanged. This follows the task entry's diagnosis: “The fix is to add drawModePicker to the stub sentinels, exactly as chatList and burnPanel are stubbed.” Commit after rebasing onto current local `master`: `da097b710050e33f2706b0db8bd95afd6b3ecf3e`.

## Red-proof

Direction 1: with the stub present, I used `python3 dev/redproof.py begin client/views.js`, removed the real `h += label('Q & A');` production line, and ran the exact test. It failed on the discriminating assertion:

> `AssertionError: '<div class="label">Q & A</div>' not found in ...`

The rendered output still contained `topic chats`, `class="qsec"`, `/answers`, and `burndown`, so this was specifically the missing header rather than a harness/evaluation failure. The brief names `client/router.js`, but the current split tree places `buildDashboard` and this production line in `client/views.js`; `router.js` contains `drawModePicker` but not the injectable line. I restored via `redproof.py restore`, then `cmp` reported an exact match to the lane-private snapshot.

Direction 2: with the stub present, I removed `h += drawModePicker();` from `buildDashboard`; the exact Q&A test still passed (`1 passed`). This is a real false-green for picker presence and placement. It is acceptable for this narrowly documented ordering test: the open behavioural-guard task explicitly requires “paused: the canvas contents are IDENTICAL across N animation frames AND non-blank”, plus light and animated behaviour. Fold picker presence/placement into that task's behavioural browser guard rather than widening this Q&A harness; this finding belongs to #736.

Final red-proof gate:

> `check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

It listed both `client/views.js` injections, with shas `4fa675692932` and `5818030cd57d`.

## Verification

- After rebase, `python3 -m pytest test_watch.py -k 'questions_parts or Collector'`: `169 passed, 314 deselected in 5.41s`.
- After rebase, full `python3 -m pytest test_watch.py`: `483 passed in 67.37s`.
- No browser guards were run, per the lane brief.
- Rebase: local `master` had moved five commits; `git rebase master` completed without conflicts. New commit sha is `da097b710050e33f2706b0db8bd95afd6b3ecf3e`.

## Harness recommendation

Do not make every unknown JavaScript identifier silently callable through a broad proxy: that could also hide misspellings in the real functions under test. A worthwhile follow-up is a small harness helper that takes the extracted `buildDashboard` source, discovers its direct callee names, preserves an explicit allowlist of real functions (`label`, `qSummary`, `qSection`) and explicit marker-producing boundaries (`chatList`, `burnPanel`), and supplies a no-output sentinel for every other discovered direct callee. The existing preconditions still ensure the ordering subjects rendered, while a new neighbouring surface no longer reds an unrelated ordering test. This deserves its own reviewed task because the discovery rule must reject dynamic/member calls and syntax it cannot classify rather than guessing.

## DOGFOOD REPORT

Two brief defects cost time. First, the direction-1 path was stale: the named production line is in `client/views.js`, not `client/router.js`; `redproof.py` safely dropped the initially armed, unchanged router snapshot, but the brief should name the split location. Second, the scope parenthetical says `#612` means “land the fewest lines,” while ledger #612 is actually titled “The #381 fold-prompt WARN quotes the ENTIRE hand-off body verbatim...”; that citation is unrelated and should be corrected or removed. Apart from those two concrete inaccuracies, the snapshot/restore/check protocol and verification instructions were clear and effective.

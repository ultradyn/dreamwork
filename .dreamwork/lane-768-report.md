# Lane 768 report — checked prompt delivery

## Result

Built a coordinator-side dispatch wrapper and made `just dispatch-lane` the
documented supported `ccc` route.

The task entry's correction was load-bearing: "SO THE FIX MUST BE OUT-OF-BAND,
and it must run in the coordinator's own process before the runner is exec'd."
`dev/dispatch_lane.py` therefore reads the prompt, requires the exact current
`briefs/boilerplate.md` as its final, non-fenced section, and only then replaces
itself with the runner. The prompt is appended as one argv item; no shell
command substitution is involved.

Changed:

- `dev/dispatch_lane.py` — fail-closed validation and exec boundary.
- `justfile` — `just dispatch-lane prompt.txt @cx-coder -y`.
- `SKILL.md` — names this as the supported route and direct `ccc` dispatch as
  unsupported.
- `test_dispatch_lane.py` — nine integration/contract tests.

Commits before this report: `b6402a88`, `7cac0f18`, `8394aaef`.

## What the assertion establishes

It establishes that the exact string this wrapper passes as the runner's final
argv item contains one byte-exact copy of the current standing contract, as the
final prompt section and outside a Markdown fence. It also establishes that a
healthy wrapper launch adds no stdout or stderr of its own.

It does not establish that a downstream wrapper preserved that argument before
the ultimate process received it. `/proc/<pid>/cmdline` is authoritative for a
live process, but a post-launch scan has a narrow window: an already-exited
runner has no entry. It also needs structural runner identity and explicit
exclusion of the scanner and its ancestors; substring `pgrep`/`ps` scans carry
their own search text and false-attribute themselves. I did not add that larger,
race-prone mechanism to this pre-launch increment.

## Does this escape remember-to-run?

Not completely. It collapses prompt validation and launch into one supported
command, so a coordinator using `just dispatch-lane` cannot forget the separate
check. The documentation and a contract test bind that route. But this repo
cannot prevent a coordinator from bypassing it with the external `ccc` binary;
`ccc` is explicitly out of scope to modify. Therefore this moves the remaining
remember-to-run boundary to "use the supported route"; it does not make bypass
technically impossible.

## Direction 1 red proof

The exact incident input, `$(cat /tmp/lane/p766.txt)`, is refused at exit 2
with:

> standing contract from briefs/boilerplate.md is missing or altered

I then registered `dev/dispatch_lane.py` with `dev/redproof.py`, injected an
early return that skipped the assertion, and ran only
`test_literal_command_substitution_refuses_and_names_missing_contract`. It went
red on the discriminating consequence: expected refusal exit 2, got exit 0 and
empty stderr because the broken prompt reached `true`. Restore verified the
original bytes. The hand-off gate reported:

> history: examined 3 commit(s) since fad560984d2e (master) against 1 injected path(s); read 2 blob(s), 0 holding a recorded injection.
>
> check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits

## Direction 2

- A 120,000-byte prompt with no rules: refused.
- Only `Never merge, never push.`: refused.
- The complete contract inside either a backtick or tilde Markdown fence:
  refused as "inside a fenced quotation, not as lane instructions".
- Unreadable prompt and empty prompt: separately refused as "could not read"
  and "prompt is empty"; neither can look like a valid launch.
- Unclassifiable remainder: prose can quote the exact contract without Markdown
  quotation syntax and place it last. That is byte-for-byte indistinguishable
  from instructions to this mechanical pre-launch check, so it passes. Closing
  that semantic case would require a stronger prompt envelope or delivery
  protocol, not another substring heuristic.

## Verification

- Initial base measured with `git merge-base HEAD master`:
  `fad560984d2e5e9bd67a1fb5943cd68811da5270` (matching the dispatched SHA).
- Before report, `git rebase master`: already up to date.
- Finish-time local `master`: `fad560984d2e5e9bd67a1fb5943cd68811da5270`;
  `git rev-list --count HEAD..master` was `0`.
- `just pytest test_dispatch_lane.py`: `9 passed`.
- `python3 lint.py`: clean with the expected worktree bar of `6 warning(s)`.
- `git diff --check`: clean.
- No browser guard, port binding, live-ledger mutation, push, merge, or `attn`
  invocation occurred.

## DOGFOOD REPORT

Two dispatch defects were present in the task materials:

1. `BRIEF.md` names a worktree but has no machine-readable `Lane-owns:` line,
   despite the standing contract requiring one. I treated the user-granted
   repository scope as authority and report the missing declaration here.
2. The task-specific verification asks for manual `cp`/`cmp` restoration,
   while the standing boilerplate says `dev/redproof.py` owns that protocol.
   The task does not explicitly declare an override or name the replaced rule,
   so I followed the standing contract and used `dev/redproof.py`.

The quoted-example requirement also exposed a real boundary: syntax-level
quotation is classifiable; semantically quoted raw text is not. The report
states that false-green rather than pretending the pre-launch check can decide
instructional intent.

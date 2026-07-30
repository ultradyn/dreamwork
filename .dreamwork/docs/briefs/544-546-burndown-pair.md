# Brief — #544 + #546: burndown pair (bar segment order + datapoints cap)

Lane: lane-544burndown (glm-5.2). Two small add-ideas from Max via the dashboard, both in
the burndown surface of watch.py — land as TWO commits in the one lane.

## Part 1 — #544: the unknown section sits between user and loop (receipt `b4e74e4b`)

> for burndown bar below the chart, put the unknown section between user and loop
> (which I gather is the agent)

The provenance bar below the burndown chart segments task origin (human / loop / unknown —
the #213/#216/#217 provenance work; `bdhover` and `burndownmock` guards are adjacent).
Today the segment order places unknown somewhere other than between the human ("user")
and loop ("the agent", his words) sections. Reorder so the bar reads **user · unknown ·
loop** — unknown as the honest gap between the two knowns. Check both the bar rendering
order and any legend/hover ordering (`bdhover` reads the segments) so they agree; the
tooltip copy must keep calling loop "loop" (his parenthetical is a question, not a rename
request — do NOT relabel anything to "agent").

## Part 2 — #546: cap the datapoints input, and raise the cap to 256 (receipt `f49fc3b9`)

> burndown chart numerical input can go above 128 but looks like the actual number of
> datapoints caps there anyway. the number input should be capped so it doesn't show a
> number that's higher than we allow. Also let's set the cap to 256.

Two halves: (a) the input currently accepts/displays values above the real maximum — find
where the datapoint count actually clamps (the render truncates at some N) and make the
INPUT's max attribute + any stepper logic agree with the real cap, so the control never
shows a number the chart cannot honour (the `bdinput` guard and its #532 hold-repeat work
are adjacent); (b) raise the real cap from 128 to **256** — if the 128 is a data-window
limit rather than a rendering limit, widening it is the actual ask; measure what breaks at
256 (column width? fetch size?) before assuming it is free. If 256 has a real cost, land
(a) with the input capped at the true current max and report the 256 cost instead of
forcing it.

## Constraints

- Lane-owns: watch.py burndown surface (chart, provenance bar, datapoints input/steppers),
  test_watch.py burndown tests, dev/capture/bdhover.mjs / burndownmock.mjs / bdinput.mjs
  ONLY if the change moves what they assert (update in the same commit, naming each).
- `transitions.md` governs any runtime appear/disappear/resize; a segment reorder that
  animates must reuse the existing idiom.
- Red-first: sabotage the production line (e.g. revert the segment order; restore the 128
  clamp) → the bound check FAILs → cp-restore byte-identical (never git checkout). A green
  red-run is a finding — report it.
- Verification: pytest subsets + solo guards via `DREAMWORK_GUARDS="bdhover burndownmock
  bdinput" DREAMWORK_HUB_GUARDS= just guards 3989X` after `ss -ltn` shows the port free.
  Never the full suite. NEVER read_file an image (text-only; the coordinator does the
  visual verdict from your screenshots).
- Commit `git commit --only <paths>` (git add new files first). Append ONE line to
  `.dreamwork/handoffs.md` under `## Pending` before your final commit (#398 obligation).
  No attn, no pkill -f, no servers left running at exit.
- Final message: commit hashes, red-proof evidence, the true pre-change clamp you found
  (and whether 256 was free or costed), and what the merge gate should look at.

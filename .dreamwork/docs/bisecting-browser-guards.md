# Bisecting browser guards without inventing a boundary

Use `dev/bisect_guard.py` for historical browser-guard comparisons. A plain
`git bisect run` treats every nonzero guard exit as “bad”; here that conflates a
behavioural assertion with a timeout, missing repository metadata, stale
server, unavailable dependency, or guard crash.

## The audited failure

The wrong qroll boundary was not produced by `git bisect`. The surviving
transcript shows three separate runs:

1. the then-current checkout failed;
2. a detached worktree at `e195f901` failed for the later real regressions;
3. a detached worktree at `947531af` passed.

Revision `2730557f` was never run. It was named because it was the next commit
and touched the three guard files. A later clean run proved that revision
passes. The leading contamination hypothesis is therefore not the cause of
that particular wrong answer: the historical runs used fresh detached
worktrees, which had `.git`, excluded ignored present-day files, and started
their own identity-checked server. The method failed by interpolation across
an unmeasured commit, then called that interpolation a bisect.

## Required procedure

Run every candidate through the judge, without piping it through `head` or
`tail`:

```sh
python3 dev/bisect_guard.py --guard qroll --port 39890 \
  947531af 2730557f
```

The tool creates a fresh detached worktree per revision and verifies, before
running:

- the revision resolves to a commit and the worktree HEAD is exactly it;
- repository metadata exists and `git show HEAD:watch.py` works;
- the tree has no tracked or untracked changes before the guard;
- the historical guard, fixture, server, lint judgement gate, and just recipe
  all exist;
- the `guards` recipe body (not comments or unrelated file bytes) directly
  invokes the selected guard, checks server identity/port ownership, and wires
  `lint.py guard-execution` into its failure status;
- the selected port is free; and
- the current machine-load preflight travels with that revision's verdict.

If temporary-worktree removal fails, the result is `DID NOT JUDGE`, includes
whether the registry entry survived, and preserves the directory as evidence.
Unlock/remove it explicitly after diagnosis; deleting only the directory turns
the surviving registry entry into a phantom that pruning cannot remove.

The three outcomes are intentionally not Boolean:

- `PASS` (process exit 0): the historical judgement gate confirmed a real
  assertion and all assertions passed;
- `FAIL` (exit 1): a named behavioural assertion failed under an OK preflight;
- `DID NOT JUDGE` (exit 125): any missing precondition, crash-only sentinel,
  timeout, incomplete output, contamination, or red under CAUTION-or-worse.

Exit 125 is suitable for `git bisect skip`, but do not let a run with skipped
commits print “first bad”: skipped candidates can leave a range, not a point.
Prefer listing explicit revisions until every candidate is classified.

## Worked qroll result

The two extraction-boundary revisions must both say PASS. A later revision in
the stale-response window gives the discriminating qroll persistence failure;
that is a judged red, not the crash sentinel. If the preflight is CAUTION or
worse, rerun that red before using it as boundary evidence. A green remains
usable because the measured load failure mode manufactures false reds, not
false greens.

## Honest boundary of the method

The runner closes the observed contamination classes: caller `client/dist/`
and `node_modules` cannot travel into a fresh worktree; an archive without
`.git` is refused; the port must be free and the served target must identify
itself.

It does **not** make external dependencies historical. These guards import an
absolute Playwright installation, and they still use the current kernel,
Chromium, fonts, clock, and machine environment. A compatible-but-behaviourally
different external dependency can make a clean revision fail a real assertion,
and the runner cannot identify that as contamination from output alone. Pin or
archive those dependencies when that distinction matters; otherwise report the
revision as judged in the recorded environment, not intrinsically bad.

Classification also depends on guards naming setup checks as `precondition:`
or using the shared absence-first wording. If a guard gives a hidden setup
assumption a behavioural-looking name, no output parser can recover the
distinction; audit that guard's assertion vocabulary before trusting its red.

The recipe check is structural, not a shell interpreter. It rejects the known
comment-plus-echo false green, but an uncalled function can contain every
required direct line while another line prints `PASS`, and a historical
`lint.py` or guard can itself lie. The IGC choice is therefore deliberately
narrow: raw substring checks fail the judged-verdict goal; replacing the
historical runner fails revision fidelity; recipe-body inspection preserves
fidelity and closes the observed defect, provided accepted revisions are
reported as having an auditable recipe shape rather than being sound against
arbitrary historical shell. Refuse (`125`) whenever that gate cannot be
established, and audit unusual indirection before trusting a boundary.

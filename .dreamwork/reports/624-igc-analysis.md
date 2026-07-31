# #624 — IGC analysis: `--only` does not isolate lanes on a SHARED path

## Context

`git commit --only <path>` commits the path's full current content, so it
sweeps another agent's uncommitted edit to the **same** file. The swept
agent's own `--only` then reports `nothing to commit, working tree clean`,
which a confused agent reads as failure and re-appends — duplicating a row
the coordinator folds twice. Verified in a throwaway repo: two appends to
one file, one `--only` commit sweeps both, victim sees `nothing to commit`,
re-appends, final file has the victim's line **twice** (count = 2).

**Critical fact discovered during analysis:** #687 (merged dc3ac7c3) already
made the coordinator the **single writer** of `handoffs.md` — the file the
#624 entry names as "the one file every lane writes on master." Verified:
every commit touching `handoffs.md` since dc3ac7c3 is authored by the
coordinator (Max Kaye), not by a lane. The boilerplate already carries "DO
NOT append a hand-off line to `.dreamwork/handoffs.md`. That file has a
single writer and it is not you." So the collision site the entry describes
is **already structurally removed** — #687 IS option 3 applied to
handoffs.md.

## Goals (binary)

- **G1** — a confused lane that sees `nothing to commit` after writing to a
  shared file does NOT blindly re-append (prevents the DUPLICATE).
- **G2** — implementable within this lane's scope: `briefs/boilerplate.md`
  and the handoffs protocol only. `dev/ledger.py` (#627), `status_sync.py`
  (#720), `dev/journal_consume.py` (#722), and `watch.py` are off-limits.
- **G3** — proportional to the **remaining** risk. #687 already removed the
  primary collision site, so the residual risk is a lane writing to some
  OTHER shared file and hitting the same `nothing to commit` → re-append
  trap. The fix must not build infrastructure for a collision site that no
  longer exists.

## Matrix

| Idea | All | G1 | G2 | G3 |
|------|:---:|:--:|:--:|:--:|
| 1. Brief instruction in boilerplate.md | **✔** | ✔ | ✔ | ✔ |
| 2. Lock serialising appends | **✘** | ✔ | ✘ | ✘ |
| 3. Per-lane pending files, coordinator concatenates | **✘** | ✔ | ✘ | ✘ |

## Decisive errors

**Option 2 ✘ G2:** a lock needs acquisition/release code in the append path
— that lives in `watch.py` or a `dev/` script, both off-limits. **✘ G3:** a
lock for a collision site #687 already removed is infrastructure without a
job; the file it would serialise (`handoffs.md`) now has one writer.

**Option 3 ✘ G2:** the coordinator's concatenation/fold path lives in
`dev/ledger.py`, explicitly off-limits (#627 is live there). The brief
anticipates this: "if your fix genuinely needs a ledger.py change, stop, do
everything else, and tell me what remains." **✘ G3:** #687 already
implemented option 3's structural fix for the only shared-write site
(`handoffs.md`). There is no remaining shared append-only file lanes write
to (inbox.md is typically untracked; worktree files are disjoint). The cost
— reworking the fold path, a new file format, a `lint.py` row, and
sequencing behind #627 — is not repaid because the collision site it
removes no longer exists.

## Decision: option 1

**What I gave up:** option 1 holds by convention, not by construction. A
lane that doesn't read the boilerplate, or panics at `nothing to commit`
before checking, could still re-append. But #687 already removed the
structural collision site, so the only remaining path is a lane writing to
some other shared file — a much narrower risk than the original
handoffs.md collision. The instruction is the right defense for that
residual risk, and it is the only option implementable within this lane's
scope.

**The change:** add a rule to `briefs/boilerplate.md` (where every lane
reads it) that explains: `nothing to commit` after writing to a shared file
means your write was likely swept by another agent's `--only` commit of the
same path — CHECK whether your content is already on master before
re-appending, because re-appending creates a DUPLICATE the coordinator
folds twice. This directly addresses the discriminating assertion (the
DUPLICATE, not the sweep).

## Direction 2 (false-green analysis)

The brief asks: "two lanes appending identical lines — does 'is my line on
master?' distinguish mine from theirs?"

**Argued:** for byte-identical lines, the check CANNOT distinguish mine from
theirs, but it does not need to. If the lines are identical, one copy on
master is the correct end state regardless of which lane's write produced
it. The check finds the line, concludes "already there," does not re-append,
and the duplicate is prevented. This is a true-green with indistinguishable
provenance, which is semantically correct for identical content.

**The open false-green** (reported, not closed): `--only` commits the full
file content verbatim, so a swept lane's exact line IS on master in its
exact form — the check is sound for this mechanism. The case it misses is
not constructable through `--only` alone: it would require the sweeper to
have MODIFIED the swept content before committing, which `--only` does not
do. So the check is tight against the actual failure mechanism.

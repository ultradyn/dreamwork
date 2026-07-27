# Coordinator → #398 · 2026-07-28 09:30

**A correction to MY instruction, not to your work. You did what the brief said.**

## Do not inject into a brief under `.dreamwork/docs/briefs/` again

I saw `.dreamwork/docs/briefs/397-client-extraction-design.md` briefly carrying
`.dreamwork/NOT_THE_HANDOFF` in place of `.dreamwork/handoffs.md`, and then reverted. That was
your red for criterion 5, you restored it correctly, and **the fault is mine**: the brief told
you to *"remove the `handoffs.md` mention from a brief added after the cutoff"* without granting
you that directory and without my noticing that **both** briefs on the new side of the cutoff
belong to **lanes that are running right now** — `#397` and `#392a`. A lane that re-read its
brief during your injection would have been told to append to a file that does not exist.

**For any remaining red, use a temp target instead:** copy the repo's `.dreamwork/docs/briefs/`
into a scratch directory, point your check's root at it, and injure that. If your check cannot
be pointed at a different root, **that is a finding worth reporting** — it means the check is
not testable without mutating live state, which is a design problem in the check and more
interesting than the red.

If you have already finished all three reds, there is nothing to do here.

## Two things that are genuinely yours to know

- **`lint.py` is still yours** and `file-formats.md` is now **free** — another lane released it.
  You still may not edit it; I have applied a related doc change myself. If your check needs a
  spec line, put the text in your report as the brief says.
- **A gap in `#395`'s fix, found ten minutes ago and relevant to you if you touch that code:**
  the marker pattern is anchored to line-start or a `·` separator so casual prose cannot
  manufacture a phantom marker — but **quoting the marker accurately means quoting its
  separator**, so a ledger entry that cites the marker precisely still manufactures one. My own
  entry about it produced two and a lint ERROR. Do not treat the anchoring as airtight.

**Nothing here changes your acceptance criteria.** Criterion 4 still stands: `python3 lint.py`
must exit 0 on the live tree, 27 grandfathered and 2 in scope.

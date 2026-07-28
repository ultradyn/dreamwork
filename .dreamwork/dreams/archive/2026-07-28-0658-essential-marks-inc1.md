# Essential marks increment 1 — two things worth keeping

2026-07-28 0658 · dreamer-367-inc1 · landed at dbcbcc5

The increment itself is in the inbox report. Two findings beyond it.

## "land on it" means the marked element, not its parent

The contract says a mark on an element with no stable id is refused because
"next/prev must be able to land on it." I read that as the id living somewhere
on or near the marked element, and my first test fixtures put `id` on a parent
`<section>` and `data-mark` on the child `<p>`. The implementation refused
every one of them — correctly. The id has to be on the SAME element that
carries the `data-mark`, because that is the element next/prev scrolls to and
the tab will anchor to. A parent id does not help: the flag points at a height,
and the element at that height is the marked one.

This matters for the later increments that actually render the tab and the
next/prev: both must key off the marked element's own id. When an author
writes `<section id="x"><p data-mark="y">`, the build refuses and the message
should send them to put the id on the `<p>` (or the mark on the section). The
no-id refusal is the cheap place this got decided; the rendering increments
inherit a body whose every mark is individually addressable.

## A byte-identity check under concurrent commits, and why pinning HEAD is wrong

The brief's criterion 3 is the one that produces false greens, and the obvious
implementation — `git show HEAD:review_artifact.py` — is wrong in this tree for
two reasons that both bit within an hour:

1. HEAD moves under you. Between my first and second commands HEAD went
   e84ca0c → 5e908ff (another lane committed), and after MY commit HEAD moved
   again to 8d5ad92. A test that pins `HEAD` compares new-vs-new once the
   feature is committed (HEAD then carries the feature), and a pinned SHA
   breaks on the next `carm` rebase.

2. Recomputing the expected side with the new code is the hollow version the
   brief warns about — both sides move together.

What works, and survived my own commit landing plus a peer's on top:

- **Resolve the pre-change ref by CONTENT, not position.** Walk
  `git log -- review_artifact.py` and take the newest commit whose copy lacks
  the feature's marker constant (`MARKS_WARN_AT`). That is the pre-change
  builder regardless of how history gets rewritten, as long as a pre-change
  copy is reachable.
- **Freeze a digest as the robust fallback.** Captured before editing, it
  asserts even when git can't resolve (no repo, shallow history); and it is
  the thing a rebase cannot touch.
- **Prove the digest honest at test time.** Re-run the pre-change builder from
  the resolved ref and assert it produces the frozen digest — so the constant
  is verified as genuinely pre-change rather than fabricated. Guard the
  resolved module with `assert not hasattr(old, "<feature>")` so the resolver
  can never silently pick a post-change commit and compare new-vs-new.

The shape generalises: any "did my change leave X unchanged" check in a tree
with concurrent commits and no CI should resolve its baseline by content and
cross-check it, not pin a moving ref. The bonus red (appending a placeholder to
the output) confirmed the check is not hollow — the cheapest proof that the
expected side is actually independent of the code under test.

## A small one

`grep -c PATTERN file` exits 1 when the count is zero, which broke an `&&`
chain mid-verification and silently stopped the checks after it. The success
case (zero matches) is the non-zero exit. Append `|| true` when the count
itself is what you wanted, not the match.

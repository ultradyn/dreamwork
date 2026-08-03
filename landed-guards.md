# Landed guards — regression tests landed tasks rely on

Each row names a LANDED task and the test function that guards its fix.
`lint.py` verifies each named function is still defined somewhere in the
test tree; a name that no longer resolves is flagged.

**This can assert a test of this name is DEFINED. It can NEVER assert the
behaviour is still guarded** — a test can be gutted to `pass` and keep its
name (#651). A name that does not resolve could be RENAMED (update the row
to the new name) or DELETED (restore the guard, or reopen the task); those
are different remedies and this check cannot tell them apart, so it names
the task and the missing test for a human to decide (#136).

Add a row when a task lands a regression test whose silent disappearance
would let the defect recur unnoticed. The registry is opt-in: only named
guards are checked, and the population is reported on every run so "checked
0" can never read as "checked everything" (#868).

- #868 test_right_count_over_wrong_set_is_rejected

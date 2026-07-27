# Reds that came back green — two coordination traps in one batch

Lane C, increments 11–13. The plan says a green red-run is a finding, never a
relief, and this batch handed me two of them in sequence. Both were the same
family the repo keeps finding: the test's own scaffolding stood in front of the
code under test, so the named regression never reached it. Writing them down so
the next red that comes back green gets the same suspicion.

## Trap 1 — an eagerly-evaluated message that consumed the contention window

The lock test held a child process's lock and asserted the parent's acquisition
timed out. It failed consistently. The lock was real (a raw `fcntl` probe proved
the child's `flock` excluded the parent). The standalone reproduction passed.
The difference was one line:

```python
self.assertIsNotNone(held, "child never reported HELD: %s" % proc.stderr.read())
```

`proc.stderr.read()` is in the **message**, and Python evaluates function
arguments before the call — so it runs every time, success or failure. It blocks
until the child's stderr reaches EOF, i.e. until the child **exits**. By the
time `assertIsNotNone` ran, the child had died and released the lock, and the
parent's acquire sailed through a lock that was no longer held. The test was
asserting the coordination, not the lock.

Fix: read stderr only in the failure path (`if held is None: self.fail(...)`).
The generalisable rule: **anything that blocks on a child in an assertion
message is eagerly evaluated and will reorder your test's timeline.** Messages
are not lazy.

## Trap 2 — a precondition that depended on the property under test

The lineage red (delete the digest-field exclusion) was supposed to fail on its
**third** assertion (same body → same digest). It failed on the **precondition**
instead. The precondition was `assertTrue(validate(text1))`; `validate` is the
lineage property, and once the exclusion is gone the digest is self-referential
and `validate` is `False` for every file — so the precondition collapsed before
the discriminating assertion ran.

The same coupling then broke a **second** test: the kill test's precondition and
recovery check also called `validate`, so the exclusion red failed two tests,
not one.

Fix: make preconditions **structural** (footer present, digest is a SHA-256,
generation landed) — properties that hold whether or not the thing under test is
present — and let each test own exactly one property. The kill test owns
atomicity; it must not also depend on the digest-exclusion property.

## The rule, restated for this batch

A precondition that asserts the property under test will mask the discriminating
assertion: under the red, the precondition fails first and the test reports the
wrong line. Preconditions must be *orthogonal* to the sabotage they precede —
true in both the green and the red world — or the red lands on the scaffolding,
not the code. And when a red breaks more than its own test, that is coupling to
remove, not a quirk to document.

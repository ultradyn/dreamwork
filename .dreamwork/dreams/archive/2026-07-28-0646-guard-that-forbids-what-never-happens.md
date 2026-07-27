# A guard that forbids what never happens can only be red structurally

F3's red line was "the read-only guard in the command dispatcher": `replay` is
the only command permitted a domain effect, and `list`/`show`/`health` may not
touch a managed file. The natural test snapshots the managed files, runs the
read commands, and asserts byte-identical.

The trap: **read commands do not write**, so deleting a guard that prevents
writes they never perform changes nothing observable about them. A purely
behavioural red is impossible here — "doesn't write" and "is forbidden to
write" produce identical file bytes. The first draft of the red (make the guard
route every command through the write path) broke F1's `list` test too, because
list's success *is* the thing the guard classifies. It was not discriminating.

What made it discriminate: **route the permitted path upstream of the guard.**
`list`/`show`/`health` are dispatched by membership in `READ_COMMANDS` *before*
the dispatcher ever consults `_write_authorized`. So widening the guard
(`return True`) cannot reach them — F1/F2 stay green — and breaks only the F3
classification assertion (`{c for c in COMMANDS if _write_authorized(c)} ==
{"replay","purge"}`).

The general form, and it is worth separating from the existing "assert the
outcome, not the mechanism" lesson: **a property that is a PERMISSION rather
than a behaviour has no behavioural red.** "Only X may do Y" is a fact about the
dispatch table, not about any run. Assert it structurally — iterate the
command set and require the classification — and keep the behavioural snapshot
as the thing that catches the *next* person who accidentally makes a read
command write (e.g. a cache). The two earn different places: the structural
assertion is the discriminating red; the behavioural one is the regression net.

And the routing decision that lets them coexist is itself load-bearing: if the
permitted path consults the guard, then breaking the guard breaks the permitted
path, and the red stops discriminating. Keep the guard on the *forbidden* path
only.

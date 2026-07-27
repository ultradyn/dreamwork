# The arm is silent for ten seconds — so a POST count cannot police hover

Filed while landing #300 (run-mode description popover).

## The finding

#290's run-mode arm deliberately does **not** POST for ten seconds. A
guard that counts `/run-mode` requests, events-log lines, and file bytes
across a hover sweep will pass while `showRunDesc` calls `pickRunMode`
on every pointerover: the arm UI lights up, pending localStorage is
written, the countdown ticks — and nothing reaches the server yet.

That is exactly the interference #300 forbids, and the first red-run of
the "zero side effects" check came back **green** with the bug in place.
A green red-run is a finding, never a relief.

## The fix (one class)

Assert the signals that flip at *selection*, not at *commit*:

- `#runcount` must not contain `arms in` after a hover-only sweep
- `localStorage` keys matching `dw:run-mode-pending:` must be unchanged

Those are the production lines `pickRunMode` / `writeRunPending` touch
immediately. POST/file/events remain necessary but not sufficient.

## Why it generalises

Any deferred-commit control (arm, confirm, debounce-to-write) makes the
end-state write a late signal. A side-effect check aimed at "did the
user gesture change durable state" has to sample the *pending* surface
too, or it only sees the world ten seconds later — which is also when
the damage is already done.

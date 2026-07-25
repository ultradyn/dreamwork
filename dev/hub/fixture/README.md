# dreamhub fixture — five targets, five shapes

Frozen input for `test_dreamhub.py` and `dev/hub/hub.mjs`. Never served
directly: both readers run it through `dev/hub/prep.py`, which copies it and
applies `ages.json`. Do not point anything at this directory itself — a guard
that writes into the repo's fixture eats what the next reader needs.

| Target | Shape | Expected state |
|---|---|---|
| `fresh` | status.json, watch-port | `dreaming` |
| `quiet` | status.json 25m old | `quiet` |
| `stalled` | status.json 3h old, no watch-port | `stalled` |
| `nostatus` | `.dreamwork/` but no status.json | `no status` |
| `torn` | status.json truncated mid-write, fresh mtime | `dreaming`, with a note |

A sixth case has no directory on purpose: the registry the readers build also
names `gone/`, which does not exist, so a deleted target renders as `missing`
rather than vanishing from the list.

`torn` is the one that matters most. `status.json` is rewritten every tick, so
the hub **will** read one mid-write; a target caught mid-write is dreaming
harder than any of the others, and reporting it as "no status" would be a lie
that flickers once a tick.

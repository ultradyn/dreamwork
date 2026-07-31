# Lane 730 report — REAPED printed when only a SIGNAL was sent

**Verdict: FIXED.** `do_kill` now verifies exit after SIGTERM and renders three
outcomes distinctly: REAPED (confirmed gone), SIGNALLED (still alive after a
bounded wait — reported, never auto-SIGKILLed), refused/skipped (unchanged).

Commit `20457fbf` on `lane-730reap`, rebased onto master `236828b5`.

## What changed and why

`do_kill` appended to `killed` the instant `os.kill(pid, 15)` returned. `os.kill`
returning means the signal was **delivered**, not that the process **died**. So
four distinct outcomes — clean exit, still shutting down, ignoring SIGTERM, wedged
in D state — all rendered as `REAPED`. That is #136 ("gone" and "I did not look"
must not render identically) and #671 (a completed action that verified nothing
must not read as done).

**The fix** (bounded, ~30 lines in `dev/reaper.py`):

1. `_wait_for_exit(pid)` — polls `os.kill(pid, 0)` + `/proc/<pid>/stat` state
   until the process is gone (ProcessLookupError) or a zombie ('Z' state —
   terminated, holding no resources) or a bounded 3s timeout.
2. `do_kill` returns four lists: `(killed, signalled, refused, skipped)`. After
   SIGTERM, if `_wait_for_exit` confirms gone → `killed` (REAPED); else →
   `signalled` (SIGNALLED).
3. `main` renders SIGNALLED distinctly: names the pid, says "NOT confirmed gone",
   and offers `kill -9 <pid>` as a **human decision**, not the tool's. No
   auto-escalation to SIGKILL — #288: the design earns trust by being narrow.

**Zombie detection** is load-bearing and discovered during testing: a SIGTERM'd
`sleep` victim becomes a zombie (terminated, parent hasn't called `wait()`), and
`os.kill(pid, 0)` **succeeds** on zombies. In production this is invisible
(orphans are reparented to init, which reaps instantly), but the `/proc` state
check makes the verification robust regardless. A zombie IS gone: terminated,
holding no resources, no listening socket.

## The design question — pid-based vs port-based verification

**Chosen: pid-based, for now.** The caller wants the PORT free, and pid-exit ≠
port-free when a surviving child holds the listening socket. But:

- The reaper can only reach `watch.py` servers (the `is_watch_server` gate in
  `_gather_one`). `watch.py` does **not** fork (grep confirmed: no
  `os.fork`/`SO_REUSEPORT`; only "forked conversation" prose matches).
- So for every process the tool can touch today, pid-exit and port-free coincide.
- A port-based check would couple `do_kill` to a second `ss` call and a port
  that may be `None` (the `--port 0` case), adding infrastructure for a scenario
  the tool cannot reach (#612: volume).

**What would change that:** if the reaper ever reaped *guard* servers (which do
fork), port-based verification becomes necessary. The Direction-2 false-green
below is exactly this scenario, reproduced and reported.

## Red-proof

### Direction 1 — injected bug, discriminating test goes red

Injected the original bug via `dev/redproof.py begin/restore`:
```python
# INJECTED BUG (#730 red-proof): append immediately without verifying
killed.append(rec)
```

The discriminating test `test_signalled_when_sigterm_is_ignored_real_victim`
(spawns a real child with `signal.signal(SIGTERM, SIG_IGN)`, no `os.kill`
monkeypatch) went red on:

```
>           assert signalled == [rec], \
E               AssertionError: a SIGTERM-ignoring process is SIGNALLED, not REAPED
E               assert [] == [{'classifica...: 99999, ...}]
```

`signalled` was empty because the buggy code put the still-alive victim in
`killed`. A happy-path-only test passes against the broken code — today's code
gets the happy path right; this is the one that does not.

`dev/redproof.py check`: **clean** — injection registered, restored, absent from
working tree and commits.

### Direction 2 — the false-green the fix leaves open (reported, not closed)

**Reproduced:** a parent holds a listening socket, forks a child that inherits
the fd and ignores SIGTERM, then the parent is reaped. The fix correctly reports
REAPED for the parent pid (it IS gone, `parent exited: -15`), but:

```
port 40769 in ss before reap: True
killed=1 signalled=0          ← parent correctly REAPED
parent exited: -15            ← parent is genuinely gone
port 40769 STILL HELD after parent REAPED: True   ← port is NOT free
```

The port is held by the surviving child. This is the surviving-child false-green
the design question names, and it is **why pid-based verification is not the
final answer if the reaper ever reaps forking servers**. Out of scope today
(watch.py does not fork; the reaper cannot reach this scenario), but the trigger
is named.

## Cited issues, with relied-on lines

- **#136** — *"present-but-unparseable is a fault and must look like one."* Here:
  REAPED and SIGNALLED must render distinctly; the four conflated cases are #136
  exactly.
- **#671** — *"420 commits WERE examined, the 'nothing to review' is false, and
  the two together read as a positive all-clear."* A confident claim that outruns
  its evidence is the defect; `killed.append` after `os.kill` is that.
- **#288** — *"tooling/authority incident … posture confers no kill authority."*
  The argument against auto-SIGKILL; the design earns trust by being narrow.
- **#702** — *"The pair then bounds nothing from below, which is worse than a
  single honest number because it looks like corroboration."* A SIGNALLED that
  looks like REAPED is worse than an honest "not confirmed."
- **#612** — *"A correct change that triples a doc's length gets reverted by the
  next reader."* The fix is ~30 lines; no restructuring of `classify` or
  `parse_cmdline` (#729 cites them as the exemplar).

## Rebase

Rebased onto local master `236828b5` (was `f054e882` at dispatch; master moved
+5 merges including #641, #728, #725). No conflicts. Post-rebase: 22 passed,
no conflict markers (`grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'` clean).

## Verification

- `python3 -m pytest test_reaper.py` — **22 passed** (was 16 before; +6 new).
- `python3 lint.py` — **0 ERRORs, 6 WARNs** (expected in a worktree, #611).
- `python3 dev/reaper.py` (dry-run, live machine):
  ```
  reaper: dry-run (kills nothing). 3 watch.py server(s)
    [live     -                   ] report   pid=1401005 port=35110 ... note=deployed-dashboard
    [stale    rule1-elapsed-stale ] report   pid=1338823 port=41234 ...
    [stale    rule1-elapsed-stale ] report   pid=3049611 port=35113 ...
  reaper: 0 dead-lane (killable via --kill --pid/--all-dead), 2 stale (report only), 1 live.
  ```
  Both protected dashboards (:35110, :35113) correctly NOT in the killable set.

## Out of scope (not fixed — named for the coordinator)

1. **Port-based verification** — the Direction-2 false-green. Necessary if the
   reaper ever reaps guard servers (which fork). Filed, not built.
2. **`--all-dead` summary line** when one pid confirms (REAPED) and another does
   not (SIGNALLED) — the summary currently reads by the `killed`/`signalled`
   split, which is correct, but an operator skimming for "REAPED" could miss a
   SIGNALLED in a multi-pid sweep. Low stakes (SIGNALLED prints its own block
   with the pid and the kill command), but worth a glance.

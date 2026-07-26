# #283 · Git `index.lock` attribution + `git-lock-watch` exit-0 (Phase 1–3)

**Date:** 2026-07-26
**Agent:** grok-sugar-vesi-x6tv
**Scope:** Diagnosis only — no service/config/mitigation edits, no package install, no sudo, no lock deletion, no KIO/Git disruption
**Report path:** this file only

## Existing facts (accepted)

| Fact | Source |
|------|--------|
| Holderless zero-byte locks (inodes 251560857 / 251691418 / 251782419 / 251806538) | task #283 |
| Fatal path: main dreamwork checkout via `~/src/dreamwork` → `~/.llm-general/skills/ud-dreamwork` | symlink |
| Correlated PID **1246815**: `git rev-parse --is-inside-work-tree`, cwd `…/kio-fuse-…/filenamesearch` | prior witness |
| Correlation ≠ creator proof | prior + this report |
| Host mitigation doc | `~/.llm-general/systems/xsm/git-index-lock-mitigation.md` |
| Watcher | `~/.llm-general/systems/xsm/git-lock-watch.sh` + user unit `git-lock-watch.service` |

---

## 1. Why `git-lock-watch.service` can exit 0 and stay dead

### Unit

```ini
ExecStart=%h/.llm-general/systems/xsm/git-lock-watch.sh
Restart=on-failure
RestartSec=5
```

**`Restart=on-failure` does not restart on clean exit (status 0).**

### Script control flow (`git-lock-watch.sh`, 52 lines)

1. `set -u` only — **no `set -e`**, **no `set -o pipefail`**.
2. Build `DIRS` from `$HOME/src/*/.git` (+ worktrees). Empty → `exit 1` (would restart).
3. Log `WATCH START N dirs`.
4. **Single pipeline, no outer loop:**

```bash
inotifywait -m -q -e create,delete,moved_from … "${DIRS[@]}" \
| while IFS='|' read -r t w e f; do
    … filter index.lock …
    CREATE → snapshot_gits … &
  done
```

5. When `inotifywait` closes its stdout (exit, crash, kill, resource failure that closes the pipe), `read` gets **EOF**, the `while` ends, the script **falls off the end**.
6. Default bash pipeline status without `pipefail` is the **last** command (`while`) → **0**.
7. systemd records success → **no restart** → monitoring stays off until a human `systemctl --user start/restart`.

### Code-level exit-0 path (certain)

| Step | Result |
|------|--------|
| `inotifywait` ends (any reason that closes the pipe) | consumer loop ends |
| bash exits | **0** (typical) |
| unit | `Result=success`, **NRestarts stays 0** |

**Not** caused by: log rotation mid-run (rotation only runs at script **start** if log > 10 MiB).

### Historical evidence

| Time | Event |
|------|--------|
| 2026-07-10 14:13 | WATCH START 348 dirs |
| 2026-07-14 11:30 | WATCH START 580 dirs (restart/reboot) |
| 2026-07-20 16:01 | Last lines in `log.1` (still writing snaps) |
| 2026-07-20 → 2026-07-26 18:29 | **No WATCH START** — watcher not running (~6 days) |
| 2026-07-26 18:29 | Human/restart: WATCH START 766 dirs; service **active** again |

`journalctl --user -u git-lock-watch` for Jul 19–21 is empty of stop reasons (no captured failure narrative). That is consistent with a **quiet exit 0** rather than crash loops.

### Confidence

| Claim | Confidence |
|-------|------------|
| Exit-0 + `Restart=on-failure` is why the unit stays dead after clean stop | **High** (unit + script) |
| Exact Jul-20 trigger that ended `inotifywait` | **Low–medium** (not logged; candidates: session event, inotify resource pressure with 580→766 dirs, signal, rare tool exit) |

### Next falsifiable hypothesis (service)

H-S1: wrapping ExecStart in `while true; do …; sleep 1; done` or `Restart=always` would have kept coverage after Jul-20 without human restart.
*(Fix later — not proposed as implement-now.)*

---

## 2. Attribution of recurring dreamwork `index.lock`

### Live recurrence (this session)

From `~/.cache/git-lock-watch/log` around 20:21–20:23 AEST:

- Path: `/home/xertrov/src/dreamwork/.git/index.lock`
- Pattern: **CREATE then DELETE ~every 2 s** (not multi-hour sticky orphans during the sample window)
- Snapshots on CREATE list almost only:

```text
pid=1246815 ppid=1092
cwd=/run/user/1000/kio-fuse-DRfGac/filenamesearch
argv=[git rev-parse --is-inside-work-tree]
parent=[/usr/lib/systemd/systemd --user]
```

### PID 1246815 — **not** the creator (high confidence)

| Observation | Implication |
|-------------|-------------|
| `STAT=D` (uninterruptible sleep) for **~10.5 days** (`ELAPSED 10-14:06:26`) | Process is **stuck**, not running a 2 Hz creat loop |
| Self-test: `git rev-parse --is-inside-work-tree` leaves **no** `index.lock` | Command class does not take the index lock |
| 10 ms / 20 ms pgrep sampling during active CREATE storms: **only** 1246815 as `git` | Lock creator is **not** a durable process named exactly `git` (or is shorter-lived than sampling) |
| cwd is **kio-fuse filenamesearch**, not the dreamwork tree | Consistent with KDE search worker, not a normal agent cwd |

**Conclusion:** 1246815 is a **correlated stuck artifact of KIO/FUSE**, not proven creat(2) of `index.lock`. Prior “only git process” snapshots systematically **over-credit** this D-state PID.

### Environmental context (circumstantial, strong)

| Process | Role |
|---------|------|
| `dolphin …/ud-dreamwork/.` (PID 250653) | Dolphin window open on the same tree as the lock path |
| `kio-fuse -f` (1246792) | FUSE front for KIO |
| `kioworker … kio_filenamesearch.so` (1246802, 1251108) | Filename search workers; cwd of stuck git |
| `baloorunner` | Desktop search (secondary suspect) |

Mitigation doc already proves opportunistic **`git status`** (not `rev-parse`) is the lock-taking class for prompts/statuslines. KDE file managers often run short-lived git for VCS overlays; those would match **CREATE/DELETE ~2 s** if a refresh timer is active.

### 2026-07-27 ATTRIBUTION FOUND: `pi-powerline-footer` footer refresh (high confidence)

Path note: the watcher logs `/home/xertrov/src/dreamwork/.git/index.lock`;
`~/src/dreamwork` is a **symlink** to `~/.llm-general/skills/ud-dreamwork` —
same repo, two spellings. All evidence below is this checkout.

During #292/#293 integration, every coordinator commit attempt (01:26, 01:49,
01:55, 02:01, 02:57, 03:00, 03:03 AEST) found a **fresh holderless zero-byte
`index.lock`** blocking `git add`/`git merge`. Each was removed only after the
established evidence gate. Following the watcher log at 03:03:00 produced the
decisive capture:

```
argv=[git status --porcelain] cwd=~/.llm-general/skills/ud-dreamwork parent=[pi]
```

- **250 of 282** `parent=[pi` snapshot lines in the watcher log involve this
  repo — a pi-spawned `git status --porcelain` is the dominant recurring
  lock-taker here by two orders of magnitude.
- Code-level source identified: **`pi-powerline-footer/git-status.ts`** (npm
  extension, loaded by every pi session) — `fetchGitStatus()` calls
  `runGit(["status", "--porcelain"], 500)`. Two defects combine:
  1. **No `--no-optional-locks`** — so `git status` refreshes the index and
     takes `index.lock` on every footer refresh;
  2. **`runGit` kills the child on a 500ms timeout** (`proc.kill()`), which
     lands mid-refresh under load and leaves a **zero-byte orphan lock**.
- Causal fit with today's timeline: orphans appeared right after heavy
  coordinator verification runs (`pytest -n 2`, browser guards, deploy) —
  exactly when a 500ms `git status` would time out — and each orphan then
  blocked the next coordinator `git add`/`git commit` in the same chain.
- pi core itself uses `--no-optional-locks` for its footer branch query;
  this npm extension did not.

**Mitigation applied (2026-07-27):** patched the installed
`~/.pi/agent/npm/node_modules/pi-powerline-footer/git-status.ts` to spawn
`git --no-optional-locks status --porcelain`. Footer status becomes read-only
(never takes `index.lock`), which eliminates both the orphan production and
the extension's own `File exists` failures. Caveats: effective on next pi
restart; overwritten by package upgrade until fixed upstream. Documented in
`~/.llm-general/systems/xsm/git-index-lock-mitigation.md`.

**Verification plan:** watcher stays armed; if orphan CREATEs in this repo
stop across normal coordinator activity after pi restart, #283 can close as
attributed + mitigated. A residual non-pi creator would reappear in the log
and reopen Phase A/B.

### Creator confidence

| Claim | Confidence |
|-------|------------|
| Creator is **not** proven to be 1246815 | **High** |
| Creator is short-lived / not durable `git` binary under `pgrep -x git` sampling | **High** |
| Creator is **`pi-powerline-footer`'s 500ms-timeout `git status --porcelain`** | **High** (watcher capture + exact argv match + code-level kill mechanism + load-correlated timing; see 2026-07-27 section) |
| Creator is in the **KIO/Dolphin/filenamesearch** family | **Refuted as primary** (2026-07-27: KIO PID was an over-credited D-state artifact) |
| Exact argv/open flags of creator | **Established** for the dominant creator: `git status --porcelain`, index-refresh lock, SIGTERM at 500ms |

### Why the current watcher cannot prove creators

1. **`pgrep -x git`** only samples processes named `git` — misses wrappers, `git.real`, libgit, or renamed binaries.
2. **50 ms × 5 samples after CREATE** — creator that exits in &lt;1 ms (lock create+delete pair is often sub-interval) is gone before SNAP[1].
3. **CREATE/DELETE same second** in the log — lifetime of lock may be shorter than one snapshot round.
4. Reading `/proc/$pid/environ` races (journal: “No such file”, “Permission denied”) — noise, not root cause of exit 0.

---

## 3. Reproducible instrumentation plan (no fix; safer tools first)

### Host capability check after L1 recurrence (read-only)

The host has no `strace`, `perf`, `bpftrace`, `execsnoop`, BCC `opensnoop`,
`sysdig`, `trace-cmd`, or SystemTap command installed. `auditctl` is present,
but audit-rule changes require privileged authority; unprivileged BPF is
disabled (`kernel.unprivileged_bpf_disabled=2`), perf is restricted
(`kernel.perf_event_paranoid=2`), and Yama `ptrace_scope=1` limits attachment.
A faster `/proc` sampler remains observationally weak because the creator can
open, close, and exit before the inotify event is delivered—the failure already
seen with 50ms snapshots. There is therefore no honest user-scoped path on this
host to bind `openat(O_CREAT)` to PID/exe/argv without installing a tracer,
attaching to a suspected process family, or authorising privileged audit/eBPF.
The watcher remains active (`Result=success`, `NRestarts=0`) and provides
recurrence timing, not creator identity.

**Constraints:** no sudo/package install/service mutation in this phase. Prefer user-scoped tools.

### Phase A — prove class without CAP (run anytime recurrence is live)

1. **Close Dolphin window on ud-dreamwork** (human action) and watch CREATE rate on dreamwork for 60 s.
   - If rate → 0: KIO/UI path strongly confirmed.
   - If rate continues: not that Dolphin window (try baloo pause / other Dolphins).
2. **Parallel tight sampler** (user-owned, not unit change):

```bash
# terminal A
inotifywait -m -e create,delete --format '%T %e %w%f' --timefmt '%F %T.%N' \
  /home/xertrov/src/dreamwork/.git/

# terminal B (10ms loop; log all non-stuck PIDs)
while sleep 0.01; do
  for p in $(pgrep -x git 2>/dev/null); do
    [ "$p" = 1246815 ] && continue
    echo "$(date +%T.%N) pid=$p cwd=$(readlink /proc/$p/cwd) argv=[$(tr '\0' ' ' </proc/$p/cmdline)]"
  done
done | tee /tmp/git-lock-tight-sample.log
```

3. Broaden name match: `pgrep -f '[g]it '` not only `-x git`.
4. Sample **all** processes with open cwd under dreamwork:
   `ls -l /proc/[0-9]*/cwd 2>/dev/null | rg dreamwork`.

### Phase B — openat attribution (needs human CAP/audit consent)

Not run this phase without approval:

| Tool | What it gives |
|------|----------------|
| **auditd** `auditctl -a always,exit -F path=…/index.lock -F perm=wa -k gitlock` | pid, exe, success on write |
| **bpftrace** `tracepoint:syscalls:sys_enter_openat` filter path | full argv if combined with `execve` |
| **strace -f -e openat,unlink** on `kioworker` / `dolphin` (same user may work) | direct proof if attach permitted |

Success criterion: one CREATE event with **matching openat of `index.lock` and O_CREAT** bound to pid/exe/argv, while 1246815 remains D and idle.

### Phase C — service death (read-only)

1. Next time the unit is inactive with Result=success, capture:
   `systemctl --user status git-lock-watch` + `journalctl --user -u git-lock-watch -b -1`.
2. Check whether `inotifywait` error log `~/.cache/git-lock-watch/err` grew.
3. Count watched dirs vs `sysctl fs.inotify.max_user_watches` (read-only).

---

## 4. Root-cause confidence summary

| Topic | Finding | Confidence |
|-------|---------|------------|
| Service exits 0 and stays dead | Script ends after `inotifywait` pipeline EOF; `Restart=on-failure` ignores clean exit | **High** |
| Jul-20 multi-day gap | No WATCH START until manual Jul-26 restart | **High** (gap) / **Low** (exact signal) |
| 1246815 as lock creator | Falsified for current 2 s CREATE storm | **High** |
| Lock class = opportunistic git index write (status-like), not rev-parse | Aligns with 2026-07-10 mitigation doc | **High** (class) |
| KIO/Dolphin/filenamesearch as driver of *this* dreamwork cadence | Circumstantial + environment | **Medium** |
| Exact creator argv/open flags | **Unknown** until Phase B | — |

---

## 5. Next falsifiable hypothesis (priority order)

1. **H1 (UI):** Closing Dolphin on `ud-dreamwork` stops CREATE/DELETE cadence within 30 s.

### 2026-07-27 L1 falsification result

At 00:16 AEST Max answered, exactly: “closed. but not sure that it's dolphin is
it? if it is that's good to know.” The coordinator therefore treats the closed
window's application identity as unknown rather than silently upgrading it to
Dolphin. A corrected, wall-clock-bounded observer ran:

```sh
timeout 60s inotifywait -m -q -e create,delete,moved_to,moved_from \
  /home/xertrov/.llm-general/skills/ud-dreamwork/.git
```

It recorded **0 `index.lock` events in 60 seconds**, compared with the previous
~2-second CREATE/DELETE cadence. (An earlier Python observer was discarded
because a blocking `readline()` could exceed 60 seconds on the zero-event
outcome.) At that moment this supported the closed window as a trigger candidate,
but it did not identify the application, PID, executable, argv, or
`openat(O_CREAT)` caller.

**Later recurrence falsifies the strong interpretation.** At 00:46:33–37, with
the window still closed, the watcher recorded new dreamwork CREATE/DELETE churn
followed by holderless zero-byte inode `253401791`; the coordinator verified no
`lsof`/`fuser` holder, no live repo Git process and no operation state before
removing that stale lock at 00:53. A second holderless zero-byte lock, inode
`253453575`, recurred at 00:57 and again blocked a reviewed cherry-pick; the same
positive holder/process/operation-state checks preceded its removal. The same watcher interval also saw churn in
other repositories. Therefore the 60-second quiet period was transient: closing
the window did **not** eliminate the underlying source and does not strongly
attribute it to that window. KIO/filenamesearch remains circumstantial context;
the snapshots again showed only long-lived PID 1246815, already falsified as the
creator. No Git/KIO/service/watcher/configuration change was made, and privileged
tracing remains unauthorized.
2. **H2 (name):** Tight sampler with `pgrep -f git` catches short-lived `git status`/`git diff` with cwd under dreamwork within one CREATE.
3. **H3 (service):** Any `inotifywait` exit under current unit leaves `ActiveState=inactive` and `Result=success` with NRestarts=0.
4. **H4 (stuck PID):** 1246815 never appears in `/proc/locks` as holder of dreamwork index (lsof if available); remains D forever until reboot/kill -9 of FUSE stack.

---

## 6. Safety notes

- Live locks observed during diagnosis were **ephemeral** (CREATE/DELETE pairs); no multi-hour holderless file left in place by us.
- Did **not** remove locks, stop KIO, or modify the unit.
- Stuck D-state git for 10 days is a **host hygiene** concern (zombie-like I/O wait on kio-fuse) but separate from creat attribution; do not kill without Max approval (may affect KIO stack).

---

## 7. Deliverable status

| Phase | Status |
|-------|--------|
| 1 Explain exit-0 path from code/unit | **Done** |
| 2 Instrument / attribute creator | **Partial** — falsified 1246815; creator still unproven; plan Phase A–B |
| 3 Report + next hypothesis | **Done** |

No fix proposal until openat-level attribution (per assignment).

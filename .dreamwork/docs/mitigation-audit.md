# Mitigation audit — four unchecked records (#416)

**Checked:** 2026-07-28 ~22:01 AEST (host `xsm`)
**By:** mitaudit lane (Grok 4.5 / xAI), READ-ONLY on master
**Scope:** the four mitigations in `~/CLAUDE.md` §"System mitigations in place" that were not re-verified while resolving `#408`. The two that `#408` already covered are out of scope here.

Nothing on the host was changed. No unit was started/stopped/restarted/enabled/disabled. No dotfile or config was edited. Port `:35110`, the heartbeat, monitors, and the loop were not touched. `just test` / `just deploy` were not run.

---

## 1. Brave `--ozone-platform=x11`

**Claim** (`~/CLAUDE.md`): `~/.config/brave-flags.conf` has `--ozone-platform=x11`.

**One-line check:**

```text
$ grep -n -- '--ozone-platform=x11' ~/.config/brave-flags.conf
4:--ozone-platform=x11
```

Full file (for context; comments only, one flag):

```text
# Force XWayland to avoid KWin Wayland pointer-grab desync that wedges the UI
# (cursor stuck as resize arrows, clicks ignored, IPC eventually stalls).
# Remove this line if you want to try Wayland-native again after a KWin upgrade.
--ozone-platform=x11
```

**Verdict: holds.**

Linked diagnosis: `~/.llm-general/systems/xsm/brave-xwayland-mitigation.md` (active; revert = delete/comment the line).

---

## 2. `sccache-server.service` (systemd `--user`)

**Claim:** user unit pre-starts a foreground, never-idle sccache server at login.

**One-line check:**

```text
$ systemctl --user is-active sccache-server.service; systemctl --user is-enabled sccache-server.service
active
enabled
```

Supporting (still read-only):

```text
$ systemctl --user show -p FragmentPath -p ActiveState -p UnitFileState sccache-server.service
ActiveState=active
FragmentPath=/home/xertrov/.config/systemd/user/sccache-server.service
UnitFileState=enabled
```

`systemctl --user status` (trimmed): unit loaded from that path; **Active: active (running)** since Fri 2026-07-24 16:27:59 AEST; Main PID sccache under `~/.cargo/bin/sccache`.

**Verdict: holds.**

Linked diagnosis: `~/.llm-general/systems/xsm/sccache-eperm-mitigation.md`. Recovery (not run): `systemctl --user restart sccache-server`.

---

## 3. amaroo git-wf2 / `pi-powerline-footer` patch (stated expiry)

**Claim** (2026-07-27 note on the git-index-lock bullet): recurring dreamwork `index.lock` orphans attributed to `pi-powerline-footer`'s 500ms-timeout `git status --porcelain`; installed extension patched to `--no-optional-locks`; **re-check after package upgrades**.

Diagnosis path for the patch file:
`~/.pi/agent/npm/node_modules/pi-powerline-footer/git-status.ts`
(full write-up: `~/.llm-general/systems/xsm/git-index-lock-mitigation.md` §2026-07-27).

### 3a. Does the patched file still carry the patch?

**One-line check:**

```text
$ grep -n 'no-optional-locks\|xsm mitigation' ~/.pi/agent/npm/node_modules/pi-powerline-footer/git-status.ts
117:  const output = await runGit(["--no-optional-locks", "status", "--porcelain"], 500); // xsm mitigation: never take index.lock for a footer (#283) — see ~/.llm-general/systems/xsm/git-index-lock-mitigation.md
```

**Verdict on the patch: holds** — the `xsm mitigation` marker and `--no-optional-locks` argument are still on disk.

### 3b. Has the package been upgraded since the patch?

Cheap local evidence only (no registry query, no `npm install` dry-run):

```text
$ stat -c '%y %n' \
    ~/.pi/agent/npm/node_modules/pi-powerline-footer/git-status.ts \
    ~/.pi/agent/npm/node_modules/pi-powerline-footer/package.json \
    ~/.pi/agent/npm/package-lock.json
2026-07-27 03:13:40.770056170 +1000 .../pi-powerline-footer/git-status.ts
2026-07-18 03:48:50.660721653 +1000 .../pi-powerline-footer/package.json
2026-07-24 01:29:58.775094058 +1000 .../package-lock.json
```

```text
$ grep -E '"version"|"name"' ~/.pi/agent/npm/node_modules/pi-powerline-footer/package.json | head -3
  "name": "pi-powerline-footer",
  "version": "0.7.0",
```

`package-lock.json` resolves `pi-powerline-footer-0.7.0.tgz`. Package tree mtime is 2026-07-18 (install of 0.7.0); the patched source is newer (2026-07-27, the mitigation day); the parent npm lock was last written 2026-07-24 — **before** the patch and without bumping this package off 0.7.0.

**Verdict on upgrade history: holds (not upgraded since the patch), on cheap local mtime+lock evidence.** A reinstall of the same version that overwrote `git-status.ts` would have dropped the patch; the patch is still present, so no such overwrite occurred after 2026-07-27. This does **not** prove upstream 0.7.0 never gained `--no-optional-locks` officially, nor whether a newer version exists on the registry — settling that would need an intentional `npm view pi-powerline-footer version` (or browsing the GitHub repo) and is out of the "one-line system state" check. Prefer an upstream PR so the local patch is no longer load-bearing (diagnosis already says this).

**Expiry note:** the diagnosis's "re-check after package upgrades" still has no watcher. This audit is the re-check; nothing automatic will fire on the next `npm update` under `~/.pi/agent/npm/`.

---

## 4. Root `ntp-force-sync.timer`

**Claim:** root timer runs stepped `sntp` every 60min (`Persistent=true`) as belt-and-braces over timesyncd.

**One-line check:**

```text
$ systemctl is-active ntp-force-sync.timer; systemctl is-enabled ntp-force-sync.timer
active
enabled
```

Supporting:

```text
$ systemctl show -p ActiveState -p Result -p ExecMainStatus -p ExecMainStartTimestamp ntp-force-sync.service
ActiveState=inactive
Result=success
ExecMainStartTimestamp=Tue 2026-07-28 21:38:51 AEST
ExecMainStatus=0
```

```text
$ systemctl show -p ActiveState -p LastTriggerUSec ntp-force-sync.timer
ActiveState=active
LastTriggerUSec=Tue 2026-07-28 21:38:51 AEST
```

Unit files present at `/etc/systemd/system/ntp-force-sync.{service,timer}` (root-owned). Last oneshot exited 0/SUCCESS about 21 minutes before this audit; timer was waiting for the next hour trigger. Status journal notes a KoD db open warning (`/run/ntp-kod`); the diagnosis file already documents that path and treats the warning as expected when the file is missing — not a drift of the mitigation.

**Verdict: holds.**

Linked diagnosis: `~/.llm-general/systems/xsm/ntp-force-sync-mitigation.md`.

---

## Summary table

| # | Record | Check | Verdict |
|---|---|---|---|
| 1 | Brave `--ozone-platform=x11` | `grep` on `brave-flags.conf` | **holds** |
| 2 | `sccache-server.service` | `systemctl --user is-active` / `is-enabled` | **holds** |
| 3 | `pi-powerline-footer` patch | `grep` on installed `git-status.ts` + mtimes | **holds** (patch present; package not upgraded since) |
| 4 | `ntp-force-sync.timer` | `systemctl is-active` / `is-enabled` + last oneshot success | **holds** |

No **drifted** / **gone** findings. No repair ledger entries recommended from this pass.

---

## Records that should be reworded (the `#408` failure mode)

`#408`'s failure mode: a paragraph that **reads as one mitigation** but is **several independent claims**, so a partial truth looks like a full pass.

### Primary offender: the **git index.lock churn** bullet

Today's `~/CLAUDE.md` bullet (paraphrased structure, not edited):

- fish pure prompt override (`_pure_prompt_git_dirty.fish` + `--no-optional-locks`)
- Claude Code `GIT_OPTIONAL_LOCKS=0` in `~/.claude/settings.json`
- amaroo PR #893 / git-wf2 `is_dirty()` fix
- `git-lock-watch.service` (attribution logger, not a lock preventer)
- 2026-07-27 addendum: `pi-powerline-footer` local npm patch (with package-upgrade expiry)

Those are **five separately falsifiable claims** with different files, different lifetimes, and different "what broken looks like." Spot-checking any one does not check the others. Spot-checking this audit's #3 only covers the pi footer line.

Spot-checks run while writing this audit (supporting, not the four mandated ones) happened to still hold for the other four pieces on this host — pure override present, `GIT_OPTIONAL_LOCKS=0` in settings, `git-lock-watch` active+enabled — but that is **not** a substitute for splitting the record. amaroo PR #893's presence in the installed amaroo tree was **not** re-verified here (`cannot tell from here` without locating the amaroo install and grepping `statusline_data` / `_default_git`); settling it is a separate one-line check against that tree.

**Suggested rewording** (drop-in replacement for the single bullet; still do not edit `~/CLAUDE.md` from this lane — human or a follow-up lane applies):

```markdown
- **git index.lock churn** (2026-07-10, host `xsm`): background `git status` (prompts, agent hooks, statuslines) took the real `.git/index.lock` (races interactive git; orphans locks when killed). Full diagnosis: [`~/.llm-general/systems/xsm/git-index-lock-mitigation.md`](/home/xertrov/.llm-general/systems/xsm/git-index-lock-mitigation.md). Independent mitigations — check each on its own line:
  - fish pure: `~/.config/fish/functions/_pure_prompt_git_dirty.fish` adds `--no-optional-locks`.
  - Claude Code: `~/.claude/settings.json` `env.GIT_OPTIONAL_LOCKS=0` (hardlinked to `~/.claude-p/settings.json`).
  - amaroo git-wf2: PR #893 — `statusline_data._default_git` injects `GIT_OPTIONAL_LOCKS=0` (verify in the installed amaroo tree; long-running pre-merge sessions need a pull).
  - attribution only: `git-lock-watch.service` (systemd --user) logs lock creators to `~/.cache/git-lock-watch/log`.
  - pi footer (2026-07-27): installed `~/.pi/agent/npm/node_modules/pi-powerline-footer/git-status.ts` patched to `git --no-optional-locks status --porcelain` (`xsm mitigation` comment). **Overwritten by package upgrade — re-check after upgrading `pi-powerline-footer`; prefer upstream PR.**
```

### The other three audited records

| Record | Multi-claim? | Action |
|---|---|---|
| Brave XWayland | No — one file, one flag | Leave as-is |
| sccache-server | No — one unit, one purpose (status + enabled are the same mitigation) | Leave as-is |
| ntp-force-sync | Borderline: timer + service + `sntp` args, but one install | Leave as one bullet; optional: name both unit files in the one-liner so a missing service is not invisible behind an active timer |

### Out of scope of the four, but same shape (for the human)

- **`~/.local/bin/cc` wrapper** bullet already admits a residual: bare `rustc` / non-cargo builds still hit the wrapper. That residual is correctly stated as a **note**, not as "mitigated." No reword required for the `#408` partial-truth shape — it is already two explicit claims.

---

## Commands that were not pure reads

| Command | Why |
|---|---|
| `kill` of a runaway `find /home/xertrov …` started by this audit | Cleaned up the audit's own process after a too-broad search; no host config, unit, or dotfile changed |

Everything else was `cat` / `grep` / `rg` / `ls` / `stat` / `systemctl status|show|is-active|is-enabled` (no start/stop/restart/enable/disable) / `date` / `hostname`.

---

## What this audit deliberately did not do

- Did not edit `~/CLAUDE.md`, any file under `~/.config`, any systemd unit, or any package.
- Did not run `just test`, `just deploy`, or touch `:35110` / heartbeat / monitors / loop.
- Did not verify amaroo PR #893 in an amaroo checkout (separate claim inside the multi-claim bullet).
- Did not query the npm registry for a newer `pi-powerline-footer` than 0.7.0.
- Did not open a repair ledger entry (nothing drifted).

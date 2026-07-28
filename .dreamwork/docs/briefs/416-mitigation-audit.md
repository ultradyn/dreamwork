# Brief — #416: audit the four unchecked mitigation records, and write down what held

Repo: `ud-dreamwork`. **Work READ-ONLY in the main checkout. No worktree, no branch. Change no tracked file
except the two outputs below.** **Never use `attn`.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`.**

## Why

`~/CLAUDE.md`'s *"System mitigations in place"* section has six bullets, each naming a file or a systemd unit —
so each is checkable in **one line**. Three were checked while resolving `#408` and **one of those three was
false**: the paragraph read as a single mitigation and was two-thirds true, which is the shape that defeats
reading it. A mitigation record is a claim about system state and nothing re-checks it.

**The four unchecked:**

1. Brave's `--ozone-platform=x11` in `~/.config/brave-flags.conf`
2. `sccache-server.service` (systemd `--user`)
3. The amaroo git-wf2 / `pi-powerline-footer` patch — **its own note says "re-check after package upgrades",
   so it has a stated expiry nobody is watching**
4. Root's `ntp-force-sync.timer`

## What to produce

**`.dreamwork/docs/mitigation-audit.md`** plus a `doc-map.md` row. For each of the four:

- The **one-line check you ran** and its **verbatim output** (trimmed, but not paraphrased).
- **Verdict: holds / drifted / gone / cannot tell from here**, and `cannot tell` is a legitimate verdict —
  say what would settle it.
- For #3 specifically: whether the patched file still carries the patch, and whether the package has been
  upgraded since. If you cannot establish the upgrade history cheaply, say so rather than guessing.
- A **dated line** at the top: what was checked, when, and by which lane.

Then one closing section: which records should be **reworded** because they read as one claim but are
several — the `#408` failure mode — with the suggested wording. **Do not edit `~/CLAUDE.md`.**

## Hard constraints

- **READ-ONLY on his system.** `systemctl --user status`, `systemctl status` (no sudo), `cat`, `grep`, `ls`,
  `pacman -Qi`. **Do not start, stop, restart, enable or disable any unit. Do not edit any dotfile or config.**
  An audit reports; it asks before it repairs. `#408` changed a settings file **only** because he answered a
  direct ask.
- **Do not touch :35110**, the heartbeat, the monitors, or the loop. Do not run `just test` or `just deploy`.
- Machine-specific docs live under `~/.llm-general/systems/<hostname>/` — `hostname` is `xsm`. Read the linked
  diagnosis files; several state their own recovery procedure and expiry.
- If a mitigation is **drifted**, that is a finding to report, not a thing to fix. Propose the repair as a
  ledger entry and give me the exact text.

## Done means

1. `.dreamwork/docs/mitigation-audit.md` exists with all four audited, each carrying its command, verbatim
   output, and verdict.
2. A `doc-map.md` row for it.
3. **Nothing on his system changed** — say so explicitly, and list every command you ran that was not a read.
4. `python3 lint.py` still clean (you changed nothing it checks; a change means you touched more than you meant).
5. Commit on **master**: `git add .dreamwork/docs/mitigation-audit.md` then
   `git commit --only .dreamwork/docs/mitigation-audit.md .dreamwork/docs/doc-map.md -m 'docs(#416): …'` —
   **`--only`, never `git add -A`**. **Commit before you finish.**

## Report

Say: which model you are; the four verdicts with the commands that produced them; anything you could not
establish and what would settle it; which records need rewording and the suggested text; any repair you are
recommending as a ledger entry (exact text); and confirmation you changed nothing on his system, did not
touch :35110, and did not run `just test`.

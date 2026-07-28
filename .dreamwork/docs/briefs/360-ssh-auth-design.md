# Brief — #360: Dreamhub auth the operator already owns — ssh, not a hosted IdP

Repo: `ud-dreamwork`. Worktree: **`.worktrees/sshauth`**, branch **`wt/sshauth`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

## What he asked for, and why it redirects a landed design

Read `#360` in `.dreamwork/tasks.md`, and read `#275`'s landed design first — **this contradicts it on purpose.**
`#275` put a mature authenticating reverse proxy (Cloudflare Access, Tailscale Funnel) at the boundary and
called that the safe answer. He redirected, 2026-07-28 01:39: *"self-hosted with a tunnel or over a shared mesh
or lan — we should aim for simpler auth methods; ssh tunnel, session key auth'd via ssh (magic-link esq),
user/pw, sqrl if possible."*

**His reasoning is sound and should anchor the design: a self-hosted tool whose auth depends on a third party's
control plane is not self-hosted.** Do not re-argue for the proxy; if you believe it still wins for some case,
say so in one paragraph and move on.

The four he named, in the order they cost least:

1. **ssh tunnel** — no auth code at all; the hub stays loopback-bound and ssh *is* the boundary. **This is
   already possible today, and documenting it is the first deliverable** — a working recipe beats a design.
2. **Session key issued over ssh** — the interesting one. The operator runs one command on the host and gets a
   URL or token; magic-link-shaped but with ssh as the trust root instead of email.
3. **user/pw** — the fallback everyone understands, and the one with the most ways to get wrong.
4. **SQRL** — *"if possible"*, so treat it as a survey item: is it alive, is there a usable implementation, what
   would it cost. **A one-paragraph honest answer, including "no", is the right size.**

## Hard constraint, and it is absolute

**Public/WAN serving of Dreamhub is FORBIDDEN until he approves a reviewed design.** This task is **design and
documentation only.** Do not bind a non-loopback interface, do not open a tunnel, do not start a listener
reachable off-host, do not add a config default that would. `dreamhub.py`'s loopback default and its
trusted-LAN opt-in are load-bearing — describe changes, do not make them. **If your design needs a
demonstration, describe the demonstration; do not run it.**

## Deliverable

`.dreamwork/docs/plans/hub-ssh-auth.md` plus a `doc-map.md` row (note a `hub-public-auth` plan already exists —
**read it, and say how yours relates: supersede, extend, or sit beside**; do not silently duplicate it).

Cover, for each of the four:

- **What the operator does**, concretely, in commands — including the second machine (his phone, per `#275`'s
  own use case). An auth design that is correct and unusable from a phone has missed the point.
- **What the trust root is**, and what an attacker who has *not* got it cannot do.
- **What code the hub needs**, and what it must never store. A session key that is a bearer token in a URL is
  a credential in his shell history and in any log — say how you handle that, or say it disqualifies the option.
- **Revocation and expiry.** *"How do I turn this off after I lose my phone"* is the question that separates a
  design from a wish.
- **What it costs** — implementation, and ongoing operator effort per new device.
- **The failure mode**: what breaks when the tunnel drops, the key expires mid-session, or two devices race.

Then a **recommendation with an order**: what to document now (option 1), what to build first, and what to
leave. **Say plainly what is NOT worth doing** — a design recommending everything is not a design, and "ssh
tunnel plus a documented recipe is enough for now" is a legitimate and possibly the best conclusion.

## Done means

1. The plan exists and answers every bullet for each of the four options.
2. **The ssh-tunnel recipe is written and correct** — the commands, from a laptop and from a phone, with the
   hub still loopback-bound. This is the part that has value tonight.
3. A `doc-map.md` row, and an explicit statement of the relationship to `hub-public-auth`.
4. **A review artifact with an `#ask`**, because the choice among four auth models is unambiguously his:
   `.dreamwork/review/src/360-hub-ssh-auth.html` via `python3 review_artifact.py build` — note that a build now
   **refuses** a page with no `#ask` or a decoy one (`#436`, landed tonight), and exemption is by declaration.
   `#ask` above the derived fold (`node dev/capture/above_fold.mjs …`; it derives the fold now — `#432`).
   **Table trap fixed tonight (`c19107a`)**: the template's `table{min-width:max-content}` sizes tables to
   unwrapped content — he could not read the last one — so set `min-width:0;width:100%;table-layout:fixed` and
   check 390px.
5. Report the exact `questions.md` entry text you want filed. **Do not edit `questions.md`.**
6. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1091 at dispatch). **Do not run the
   full `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop.

## Files

Yours: `.dreamwork/docs/plans/hub-ssh-auth.md`, `.dreamwork/docs/doc-map.md`,
`.dreamwork/review/src/360-hub-ssh-auth.html` and its build output.

**Not yours:** `dreamhub.py`, `watch.py`, `justfile`, `dev/capture/*` (**live lanes hold `watch.py` and
`states.mjs`**), `review-artifact.template.html`, `lint.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`.

## Practical

2 threads. `git add <newfiles>` then `git commit --only <paths>` — **never `git add -A`**. **Commit before you
finish.** **Push back with reasons if any of this is wrong.**

## Report

Which model you are; the four options compared on trust root, operator cost and revocation; the ssh-tunnel
recipe as you verified it *on paper*; the relationship to `hub-public-auth`; what you recommend building first
and what not at all; the artifact's derived fold and `#ask` top; the `questions.md` text; and explicit
confirmation that you bound no non-loopback interface, opened no tunnel, started no off-host listener, and
touched neither `dreamhub.py` nor :35110.

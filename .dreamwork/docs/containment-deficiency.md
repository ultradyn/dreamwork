# Containment deficiency — #450

> **Status:** a boundary statement, not a build plan. No mechanism is wired, and
> the ruling is that none should be — yet. This doc states what protection is
> absent today, where a reader would act on that, and the seams that must stay
> open so a future lane can close the gap without redesigning. It implements
> `#450`, which records the human's answer to `#288`'s contain-vs-detect
> question. The full design and the falsifying prototype live in
> [`plans/subagent-containment.md`](plans/subagent-containment.md); the ruling
> itself is folded into `DREAMWORK.md` ("A known deficiency, noted, beats an
> expensive defence built early").

**The ruling this doc exists to carry, verbatim:**

> *"don't do anything too expensive or time consuming. just plan for it and
> make sure the deficiency is noted. We are just going to be testing with our
> own trusted nodes first, so provided we can implement isolation layers
> later, then we can. Re claude code, we can have that kind of thing where we
> can't do tools or intercepts or whatever, we'll just have a warning next to
> it that it lacks certain protections. but i mean that's fine, if someone
> else is providing the api key then they can probably provide the harness,
> too."* — the human, 2026-07-29 00:50

**The framing that survives into every section below, because it is his and it
is better than the loop's:** *whoever supplies the API key can supply the
harness.* A protection that must live inside someone else's harness is **not
our seam** — it is a boundary, not an apology for unbuilt work. The `#288`
design already proved the namespace wall works (three incident vectors held at
~22 ms per contained process); it stays **prototyped and unwired** by this
ruling, and the positive PID/health invariants remain the live defence.

## 1 — Per-harness capability, derived from what the loop actually dispatches

The loop dispatches **two runners and nothing else** (`DREAMWORK.md`, CURRENT):
`ccc @grok` and `ccc @glm52`, up to four of each, and the coordinator does not
implement. Native subagents were superseded on 2026-07-28 and are not
dispatched. So the table is over those two runners plus the superseded native
path; no harness is invented.

| harness the loop dispatches | tool calls interceptable? | whole-harness containable? | protection absent |
|---|---|---|---|
| `ccc @grok` (grok CLI runner, multimodal) | **no, today** — no wrapper routes a tool call through a wall; whether `ccc`/grok exposes a hook a future wrapper could use is **uninvestigated** (the harness internals are not loop-owned) | **mechanically yes** — `bwrap` held all three incident vectors at ~22 ms; **but self-defeating**: a wall around the whole harness holds the API key too | per-tool-call containment that keeps the key outside the wall while tools run inside |
| `ccc @glm52` (glm5 runner, pi instance) | **no, today** — same; `ccc`'s interception seam is **uninvestigated** | **mechanically yes, self-defeating** for the same reason | same: per-tool-call containment with the key outside |
| native subagents (Claude Code / grok native) | **superseded** — not dispatched since 2026-07-28 23:14; `DREAMWORK.md` rules `ccc @grok`/`ccc @glm52` only | n/a while superseded | n/a; if re-enabled, the harness-owns-both-halves finding below applies |

**Why "no, today" is a fact rather than a guess.** The `#288` design
established the load-bearing property directly: a harness like Claude Code
(and the equivalents the `ccc` runners wrap) makes the LLM API call *and*
executes the tools in one process, so there is no per-tool-call seam to cut
without harness cooperation. The prototype tested the cheap half (can a
namespace wall hold?) and could not test the expensive half (can we get the
harness to route tool calls through it?) — because that half is either a
wrapper that proxies an existing harness's tool calls, requiring
harness-specific interception, or `#358`'s head/body fork. Neither is built,
and neither is this lane's to build.

**Where the unknowns actually live.** "Interceptable?" has a present answer
(no wrapper exists) and an open one (does `ccc` expose a hook?). The open one
is marked **uninvestigated** rather than ✘ because the loop does not own or
introspect `ccc`; an invented ✔ there would be worse than the gap, and the
brief says so. Resolving it is the first act of a future lane that wires the
wall — not of this doc.

**The reframe, applied.** A per-tool-call wall that must live inside `ccc` is
the harness-supplier's seam, because the harness supplier is the API-key
supplier. So "protection absent" is a boundary statement about what the loop
does not (and, per the ruling, should not yet) provide — not a commitment to
build it. The one obligation the ruling *does* create is in §3.

## 2 — The trusted-nodes precondition, stated where someone would act on it

*"We are just going to be testing with our own trusted nodes first"* is a live
operating condition, not background. It is the reason the absence in §1 is
acceptable today, and it must be re-read at the two moments someone could
forget it:

**At dispatch.** The coordinator's dispatch step is where a lane is spawned,
and it is where the precondition bites. Every lane the loop dispatches today
runs on a **trusted node under the same UID the coordinator trusts**, and the
loop's agents are **trusted-but-fallible, not adversarial** (the `#288`
threat model, stated plainly: it bounds itself to same-UID fallibility and
deliberately excludes privilege escalation and kernel escapes). Under that
model the uncontained capabilities — signalling any process the account owns
(the literal `#288` incident), reading any file the account can read (the API
key included), binding any port, exhausting any shared resource — are
tolerable precisely because a trusted node will reach them only by mistake,
and the positive invariants (§3) detect the mistake's outcome.

**In delegation routing.** `DREAMWORK.md`'s delegation rules already route by
stakes; the trusted-nodes line is the silent precondition under them. State
it there when it changes (see below), not only here.

**What specifically changes the day an untrusted node runs a lane.** The
threat model crosses from *fallible* to *adversarial*, and the same-UID
boundary is not an adversarial boundary — a node that means harm is not
stopped by a prompt, a worktree, or supervision, and the positive invariants
only *detect* a kill after it lands, they do not *prevent* one. From that day,
containment stops being defence-in-depth and becomes load-bearing: either the
wall is wired in at the dispatch point (§3), **or the node is refused**.
Trust is a dispatch-time decision, and it is the coordinator's — never a
subagent's — to make or withdraw.

## 3 — The seams that keep later isolation possible

This is the one obligation the ruling creates: *provided we can implement
isolation layers later, then we can.* Three seams must stay open so a future
lane can wire the wall without redesigning. None of them is new work; all
three exist today and the rule is **do not close them**.

1. **The prototype — `dev/containment_falsify.py`.** It is the proof the
   mechanism works on this host: `bwrap` (present at `/usr/bin/bwrap`,
   unprivileged user namespaces enabled) created ephemeral PID + net
   namespaces that held the signal, read, and reach vectors at ~22 ms, with
   every verdict derived from host-side ground truth. It is falsification, not
   a shipped mechanism — it is imported by nothing and run by no recipe. Keep
   it runnable and ungutted so a future lane extends it rather than
   re-proving that a namespace wall holds.

2. **The positive PID/health invariants — the whole immediate win.**
   `dev/deploy_state.py`'s byte-compare of the deploy snapshot against
   `HEAD:watch.py`, plus `GENERATION` (`watch.py:37`) and
   `skill_identity()` (`{commit, skill_version}`), are the detection layer
   that catches the `#288` outcome a prompt cannot prevent: a protected
   service killed or overwritten. The rule, and a future wall depends on it:
   **a positive invariant stays authoritative over a subagent's report.** A
   "PASS no live 35110" that a live `GENERATION` contradicts is downgraded to
   suspect on the spot, and restoration (`just deploy HEAD`) is gated on the
   invariant flipping back — never on the subagent's word. Keep these
   positive (never assert an absence where the bug was the creation of one)
   and keep them sampled after any subagent touches deploy-adjacent state.

3. **The dispatch point.** Lanes spawn in one place, through `ccc @grok` /
   `ccc @glm52`, and the dispatch pid is the survivor a future wall would
   wrap (`status_sync.py` measured this: the dispatch pid keeps both its pid
   and its argv for the lane's whole life). Keep dispatch a **single,
   loop-owned seam** — not fanned out across the codebase — so a wall wires
   in once. `#358`'s head/body fork is the shape that would use it, and it is
   his call, not this lane's; the obligation here is only to leave the attach
   point free.

## 4 — The warning next to a harness (copy, not implementation)

This is **copy for a future lane that holds `watch.py`**, not a change to this
file's surfaces. It is quoted here because `watch-design.md` is held by a live
lane; when that lane is free, the copy lands beside the agent/harness row in
the status panel (where `status.json`'s per-agent `name + in_flight` already
renders).

**The register, from `watch-design.md` §"Voice & tone":** *"copy is spare,
lowercase-leaning, and a touch oneiric… A failure names what he can do
instead, in the same breath and without apologising… The em dash is the
idiom's own punctuation — a state, then its consequence for him. Success is
shorter than failure."* And the colour rule that decides the treatment:
*"`--warn` amber means BROKEN rather than live… Nothing that is merely
important gets it."* A harness that lacks containment is a **standing
capability fact, not a fault** — so the warning must **not** spend `--warn`;
it is a quiet dim annotation, the register of `serving c552338` or
`this browser only`, not of a refused send.

**Proposed copy** (dim, beside the agent name; the full line in a
`title`/hover, per the "hover for detail already summarised accurately"
idiom):

> on the row: `uncontained`
> hover: `uncontained — the harness runs its own tools; the loop does not wall them off`

It states the fact and its consequence in one breath, names no remedy (there
is none the loop owns), and reads as a boundary rather than an apology —
which is the framing §1 exists to hold. A lane that wires the wall replaces
the word with `contained` and drops the hover; nothing else in the copy
changes, which is how a reader knows the boundary moved.

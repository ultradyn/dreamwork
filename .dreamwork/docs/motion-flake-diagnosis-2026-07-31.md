# #616 — the `motion` guard's flake, diagnosed (2026-07-31)

**Verdict: (a) — the GUARD is racy; the product is correct.** In 28 runs of my
own (12 stock + 16 instrumented, load ~24–33 on 16 cores), the departing
commit row performed the contract gesture — fell 14px, grew to 1.07, faded to
0 — in **every single run**, including every failing one. The row never rose.
What fails is the guard's *measurement*: its trace window can open on the
**settled corpse of a previous, guard-triggered departure**, and its two
failing assertions are first-to-last **deltas** over the sampled ghost series,
which collapse to zero when the series leads with a finished gesture.
Confidence: as high as this kind of diagnosis gets — the per-frame traces show
the mechanism directly, run by run (§3).

Everything here was measured from scratch copies outside the repo
(`scratchpad/mf-{stock,instr,fix,red1,red2}*`); the worktree carries no
production edits.

## 1. Reproduction (my runs, not the reporter's)

Stock guard, invoked exactly as the harness does (`node dev/capture/motion.mjs
<outdir>`, cwd = repo root, ephemeral port), sequential solo runs:

| set | runs | verdicts |
|---|---|---|
| stock | 12 | **3 FAIL** (runs 1, 3, 11), 9 PASS |
| instrumented (same guard + per-frame dump, no behaviour change) | 16 | **3 FAIL** (runs 3, 9, 15), 13 PASS |

Every FAIL names exactly the reporter's two sub-assertions and no others.
~21% here vs the reporter's 4/6: the failure is decided by *tick-phase
alignment* (§3), so the rate moves with the box's latency profile, not with
load level — consistent with the reporter's observation that PASS and FAIL
interleave across one load band ("the load hypothesis is dead" holds).

The guard's own `notes` output (swallowed by the harness summary, visible when
run directly) is bimodal with **no intermediate cases** across all 28 runs:

- every PASS: `departure: top 123->137 op 100->0 scale 1->1.07` — the full
  contract gesture, correct direction;
- every FAIL: `departure: top 137->137 op 0->0 scale 1.07->1.07` — first and
  last sampled ghost frames are both the **completed** fall: already +14px
  down, already grown, already faded. The *end state is correct*; only the
  deltas are zero.

## 2. What the two assertions actually sample (cited)

`dev/capture/motion.mjs`:

- The rAF trace (`TRACE`, lines 165–187) samples every frame for 4000ms; per
  frame it records each `.qaghost.commit` node's `getBoundingClientRect().top`,
  computed `opacity`, and computed `transform` (lines 179–184).
- Trace start, then `sleep(80)`, then the traced commit (lines 193–195).
- `ghostFrames` keeps only ghost-bearing frames and takes `g[0]` — the first
  ghost in DOM order — per frame (lines 229, 233–239).
- `FAIL 1` — "falls rather than rising" (lines 243–244):
  `tops[last] − tops[0] >= 4` — a positional **delta between the first and
  last sampled ghost frames**, whichever gesture(s) those frames belong to.
- `FAIL 2` — "growing as it goes" (lines 245–246):
  `scales[last] − scales[0] >= 0.02` — same shape over the transform matrix's
  scale component.
- The passing neighbour — "fading out" (line 247): `ops[last] < 20` is an
  **endpoint** check, satisfied by a settled corpse. That asymmetry (deltas
  fail, endpoint passes) is the whole observed signature.

The gesture being sampled is a **compositor-driven CSS transition**
(`client/style.css:756–757`: `.qaghost { transition: opacity .7s, transform
.7s }`; `:783`: `.qaghost.commit.gone { translateY(14px) scale(1.07) }`,
opacity 0 via `:769`). The ghost is created and `.gone`-armed synchronously in
`dreamAway` (`client/router.js:2049`) and removed by timer 1050ms later
(`router.js:2052`) — i.e. ~350ms of settled, opacity-0 **corpse** after the
700ms transition ends. Re-renders are driven by a self-rescheduling 2s tick
(`router.js:4345`).

## 3. The mechanism, shown per-frame

The guard's *own* earlier section plants the seed: the #179 loop fires
`commit('feat: a commit that lands while he is typing')` (motion.mjs:145) and
then waits a fixed `sleep(3000)` (line 151) before the #184/#174 trace begins.
That commit's re-render lands on a tick whose phase the guard does not
control; the departure ghost it creates lives `render + 1050ms`. When the
re-render lands ~1.95–2.3s after the commit, the ghost's corpse is still on
the page as the trace opens.

Instrumented traces (same guard, frames additionally timestamped and dumped;
`scratchpad/mf-instr-runs/run*/cycle.json`), episode structure of
`.qaghost.commit` across the window:

```
run3  FAIL: ep0 t 0..96ms    n=7  top 137->137 op 0->0    scale 1.07->1.07  ty 14->14
            ep1 t 1184..2221 n=43 top 123->137 op 100->0  scale 1.00->1.07  ty 0->14
run9  FAIL: ep0 t 1..93ms    n=5  top 137->137 op 0->0    scale 1.07->1.07  ty 14->14
            ep1 t 1147..2207 n=46 top 123->137 op 100->0  scale 1.00->1.07  ty 0->14
run15 FAIL: ep0 t 1..2ms     n=2  top 137->137 op 0->0    scale 1.07->1.07  ty 14->14
            ep1 t ...        ...  top 123->137 op 100->0  scale 1.00->1.07  ty 0->14
(all 13 PASS runs: exactly one episode, t≈930–1110ms in, top 123->137
 op 100->0 scale 1->1.07 ty 0->14)
```

Every FAIL has **two episodes**: ep0 is the typing-commit's corpse — already
settled, removed ≤96ms into the trace by its 1050ms timer (placing its
creation ≈2.05s after that commit: one tick) — and ep1 is the traced commit's
ghost running the full correct gesture. The assertions take endpoints across
both: `tops[0]` = corpse (137), `tops[last]` = ep1's settled end (137) →
delta 0 → FAIL; same for scale (1.07→1.07). run15 shows a corpse visible for
only **2 frames / 2ms** is enough to poison the endpoints.

Two rulings the data makes:

- **Not (b):** ep1 — the gesture under test — is correct in shape, sign, and
  magnitude in all 28/28 runs. A genuine product rise looks entirely
  different, and I measured what it looks like by reintroducing the #174
  regression in a sabotage copy: `top 123->113 ... scale 1->1 ty 0->-10`
  (§5). Nothing like it ever appeared un-sabotaged.
- **Not rAF starvation either (the reporter's framing of (a)):** in every
  FAIL the sampler was demonstrably healthy at the traced re-render — the
  *arrival* row was caught mid-flight (`arrival: op 0->100`) and ep1 carries
  32–46 frames. #442's starvation mode (transitions.md:185–199) is real and
  the reshaped assertions guard against it too, but it is not what produced
  these failures. The flake is **cross-episode contamination**, which is why
  it is load-*insensitive* within a band and phase-*sensitive* — exactly the
  reporter's interleaving.

## 4. The patch

Three hardenings to `dev/capture/motion.mjs` (a guard file; no production
code moves). First: **drain** the previous gesture — wait until the panel
shows the typing commit and no ghost remains — so the trace holds exactly
one departure episode; on timeout it goes red as a *named* check with the
page's actual state in the notes, never as an opaque throw. Second: per
transitions.md doctrine, read the two **signs** from the ghost's computed
transform maxed over every sampled frame (any frame of the monotonic
gesture carries the sign; a corpse-led or head-truncated series can no
longer zero a delta). Third: carry the travel-vs-snap burden on #442's
load-independent `transitionstart` detector instead of on frame luck.

Validation (scratch copies, same box, load ~24–33): first iteration (drain
as a bare 15s `waitForFunction`) went 19/20 — the one red was the drain
itself timing out after a ~15s page-convergence stall (a mode that fails
the STOCK guard harder, as "no ghost at all", and would have surfaced as an
opaque `TimeoutError`); hence the named-check shape with a 30s cap and
self-diagnosing notes. The hardened fix then ran a sequential 24-run batch:
**24/24 green** (stock on the same box: 3-in-12 and 3-in-16 red). Red-proofs
re-run against the hardened fix, both correct: the #174 regression
(`translateY(-10px)`, no scale) reds exactly the two sign checks; a
`transition:none` snap reds exactly the new transition check
(`scratchpad/mf-red{1,2}.log`).

```diff
diff --git a/dev/capture/motion.mjs b/dev/capture/motion.mjs
index 1abdd170..a5a4564a 100644
--- a/dev/capture/motion.mjs
+++ b/dev/capture/motion.mjs
@@ -188,8 +188,53 @@ const TRACE = ms => `new Promise(res => {
 const seriesOf = (frames, k, f) =>
   frames.map(x => x.at[k] && x.at[k][f]).filter(v => v !== undefined);
 
+/* ── #616: drain the PREVIOUS gesture before tracing the next ─────────────
+   The typing-commit above starts its own departure on a tick whose phase
+   this guard does not control: its re-render can land anywhere in the next
+   couple of ~2s ticks, and the ghost it makes lives 1050ms past that —
+   700ms of transition, then ~350ms of settled corpse (op 0, +14px, x1.07)
+   before node.remove(). Measured 2026-07-31 (28 runs): that corpse sat
+   INSIDE the trace window in every failing run — the ghost series LEADS
+   with a finished gesture, so the old first-to-last deltas read 0 (top
+   137->137, scale 1.07->1.07) while the fade endpoint still passed. Wait
+   for the panel to show the typing commit AND for its corpse to be gone,
+   so the trace holds exactly one departure episode.
+
+   A NAMED check rather than a bare throw: 1 of 20 validation runs saw the
+   page fail to converge for 15s (a tick stall — a mode that fails the old
+   shape harder, as "no ghost at all"), and a TimeoutError through the exit
+   handler reads as "the guard threw", diagnosing nothing. On timeout this
+   records what the page actually showed and goes red by name. */
+const HEAD7 = execFileSync('git', ['-C', DIR, 'rev-parse', 'HEAD'])
+  .toString().trim().slice(0, 7);
+let drained = true;
+try {
+  await p.waitForFunction(`(() => {
+    const first = document.querySelector('.git .commit[data-sha]');
+    return !!first && first.dataset.sha.slice(0, 7) === ${JSON.stringify(HEAD7)}
+        && !document.querySelector('.qaghost.commit');
+  })()`, null, { timeout: 30000 });
+} catch (e) {
+  drained = false;
+  notes.push('drain timeout: ' + JSON.stringify(await p.evaluate(`({
+    head: document.querySelector('.git .commit[data-sha]')?.dataset.sha,
+    want: ${JSON.stringify(HEAD7)},
+    ghosts: document.querySelectorAll('.qaghost.commit').length })`)));
+}
+ok('the page converges on the typing commit before the trace (#616 drain)',
+   drained);
+
 let cycle = null;                      // reused by #174 below
 {
+  /* #442's load-independent snap detector, armed page-side BEFORE the
+     commit (and after the #616 drain, so a stale episode cannot supply
+     the event): transitionstart fires iff the browser registered the
+     ghost's transition, whatever the frame rate did. */
+  await p.evaluate(`void (window.__ghostTrans = [],
+    addEventListener('transitionstart', e => {
+      if (e.target.matches && e.target.matches('.qaghost.commit'))
+        window.__ghostTrans.push(e.propertyName);
+    }, true))`);
   const trace = p.evaluate(TRACE(4000));
   await sleep(80);
   commit('feat: the commit whose cycle is traced', 0);
@@ -237,14 +282,34 @@ let cycle = null;                      // reused by #174 below
       return m ? Number(m[1]) : 1;
     };
     const scales = ghostFrames.map(g => scaleOf(g[0].tf));
+    const tyOf = tf => {
+      const m = /matrix\(([^)]+)\)/.exec(tf);
+      return m ? Number(m[1].split(',')[5]) : 0;
+    };
+    const tys = ghostFrames.map(g => tyOf(g[0].tf));
     notes.push(`departure: top ${tops[0]}->${tops[tops.length - 1]} ` +
                `op ${ops[0]}->${ops[ops.length - 1]} ` +
-               `scale ${scales[0]}->${scales[scales.length - 1]}`);
-    ok('the departing row falls rather than rising',
-       tops[tops.length - 1] - tops[0] >= 4);
+               `scale ${scales[0]}->${scales[scales.length - 1]} ` +
+               `ty ${tys[0]}->${tys[tys.length - 1]}`);
+    /* #616: the SIGN is read from the ghost's computed transform, maxed
+       over every sampled frame, never from a first-to-last delta — a
+       delta reads 0 whenever the sampler's first ghost frame lands late
+       in (or after) the 700ms compositor transition (#442's starvation
+       mode, and #616's corpse-led series). The gesture is monotonic
+       (ty 0->14, scale 1->1.07), so ANY frame carries the sign, and the
+       #174 regression (the generic rising departure: translateY(-10px),
+       scale 1) stays red at every frame rate — its ty never exceeds 0
+       and its scale never leaves 1. Floors mirror the old deltas. */
+    ok('the departing row falls rather than rising', Math.max(...tys) >= 4);
     ok('...growing as it goes, the way a view dissolves',
-       scales[scales.length - 1] - scales[0] >= 0.02);
+       Math.max(...scales) >= 1.02);
     ok('...and fading out', ops[ops.length - 1] < 20);
+    /* ...and the travel is a TRANSITION, not a snap to the settled pose —
+       the half the max-over-frames shape above no longer carries. The
+       browser is asked whether it animated (#442), not how many frames
+       the sampler caught. */
+    ok('...through a CSS transition rather than a snap',
+       (await p.evaluate('window.__ghostTrans')).includes('transform'));
   }
   // the arrival is the same gesture at the other end: it comes DOWN into the
   // row it now owns, growing, rather than rising up into it.
```

Why both halves, when the drain alone would have gone 28/28 green: the delta
shape stays one #442 starvation away from the same false red (first sampled
frame landing deep in the 700ms window under heavier load than I measured),
and the max-over-frames shape alone would leave the window able to admit a
second episode some other seam introduces later. The drain fixes the window;
the reshaped assertions fix the instrument; the `transitionstart` check keeps
the travel-vs-snap burden the delta shape had been carrying by accident.

Not changed on purpose: the trace length (4000ms — tail truncation never
occurred in 28 runs and the drain makes episode timing deterministic at
~1s in), the fade endpoint check, and the arrival checks. Note the drain
also closes a latent sibling: had the typing-commit's re-render landed
*after* trace start (a slower tick than any I observed), the trace would
have seen TWO arrivals and failed `exactly one row arrived` — same family,
same fix.

## 5. If it had been (b) — and how we know it is not

No product defect exists to file. The measured signature of a genuine #174
regression (sabotage copy, `scratchpad/mf-red1.log`): `departure: top
123->113 op 100->0 scale 1->1 ty 0->-10` — tops *decreasing* from the live
position with opacity starting at 100. That signature appeared in 0 of 28
un-sabotaged runs; the corpse signature (top pinned at the settled 137,
op pinned at 0) appeared in all 6 failures.

What would have changed the verdict to (b): any un-sabotaged run whose
ghost series showed a *descending-from-live* top with opacity starting
high — i.e. the red1 signature — or any episode whose transform carried a
negative translateY or a scale pinned at 1 while opacity fell. The
per-frame instrumentation would have caught a single such frame; none
exists in the 677 dumped ghost frames across the 16 instrumented runs,
and no stock run's endpoint pair admits one.

**Relation to #568:** same neighbourhood, different defect class, no shared
cause. #568 is an *absence* (bdhover's `.depart` arm bound by no check);
#616 is a *present check measuring the wrong window*. They connect only in
that both fixes converge on the same doctrine — bind gestures with
load-independent class/event assertions (#568's proposed shape; this patch's
`transitionstart` check) rather than frame-luck. Nothing in #568 needs
re-scoping because of #616.

## 6. What I could not establish

- **Why the reporter saw 4/6 while I see ~3/14 per set.** The corpse window
  is ~350ms of a ~2s tick phase (~17% a priori, matching my rate); 4/6 is
  plausible as small-N, or the box's render latencies that hour parked the
  phase in the window. Deciding would need the six original `$OUT/motion.log`
  files (deleted with their `mktemp -d`) or many runs under a reproduction of
  that hour's conditions. Immaterial to the mechanism: both rates come from
  the same bimodal signature.
- **The in-suite FAIL (load 31.89→33.08) that opened #616** cannot be
  re-attributed with certainty — its log is gone. Its two named FAILs match
  the corpse signature exactly, and the reporter's retro-judgement ("most
  likely a genuine motion failure") should be softened to "most likely this
  same guard race".
- **#442-style starvation as an *additional* failure mode of the stock
  deltas** — never observed here (load ceiling ~33); asserted as possible on
  #442's own measurements at load 40+. The patch covers it either way.
- **The root cause of the single ~15s page-convergence stall** seen in the
  first validation batch (1/20). Server-side request stall vs whole-renderer
  stall is undecided — the run predates the drain's diagnostic notes. The
  hardened drain records the page's actual state on any recurrence, so the
  next occurrence diagnoses itself; and the same stall fails the *stock*
  guard harder (its 4s window would simply contain no ghost).
- The patch is validated in scratch copies, not in the worktree
  (`dev/capture/` is held by lane-595scroll). The sequential batch + both
  red-proofs is strong; a post-application `DREAMWORK_GUARDS=motion` burn-in
  of ~10 runs in-repo is the remaining formality.

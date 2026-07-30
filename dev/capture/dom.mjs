/* Shared DOM readers and motion-trace helpers for the guards.
 *
 * One rule, one copy. Two guards asked the same question of the review dock
 * -- "is this still the question I docked?" -- and both answered it by
 * comparing a raw fixture title against `#qdock .qt` textContent. #385 then
 * put a LIVE AGE inside that headline, between the date and the ` — `
 * separator (`qtHtml` in watch.py), so the raw title stopped being a
 * contiguous substring of the rendered text and both guards went red on a
 * page that was behaving correctly. The submission targeting never broke:
 * `posted.question` comes from data, not from rendered text, and that
 * assertion (#266) stayed green throughout.
 *
 * So the identity question has to be asked of the headline MINUS its age,
 * and it has to be asked in one place, or the next thing added to a headline
 * reds two guards again.
 */

/** waitFor — deterministic RENDER readiness (#507). `goto` with
 *  `waitUntil:'networkidle'` returns once the network is idle (data.json
 *  fetched), but under load the client JS that BUILDS the DOM the assertion
 *  reads has not run yet, so a fixed `sleep()` after it grades a
 *  half-rendered page (the burndown bare-server panel read `no ledger: {}`
 *  over a correct server at load 58). Wait for the specific selector instead
 *  — the same primitive `filehl`/`fileview`/`answers` already use inline.
 *  Shared here so a guard composes server readiness (`serveVerified`) with
 *  DOM readiness rather than hand-tuning a sleep per surface. Returns true
 *  on ready; false on timeout (the caller's own absence-first check names
 *  what was missing, never this helper). */
export async function waitFor(page, selector, timeoutMs = 15000) {
  try {
    await page.waitForSelector(selector, { timeout: timeoutMs });
    return true;
  } catch (e) {
    return false;
  }
}

/* ── server readiness at the navigation seam (#388) ────────────────────────
 *
 * Under CPU starvation a guard's own watch.py takes seconds longer to bind
 * its socket — measured at load ~23 on 16 cores, startup was 7.7x baseline
 * (1422ms vs 185ms), and once bound the kernel keeps the listen socket
 * alive (0 drops across every run), so the failure is STARTUP, not mid-run
 * death. The guards that spawned their own server with a fixed
 * `await sleep(2500)` had no bound on that wait: under extreme load the
 * sleep finished before watch.py bound, and the guard's first `fetch` or
 * `goto` surfaced raw `TypeError: fetch failed [cause] ECONNREFUSED` — the
 * worst class a guard has, the "threw before finishing" verdict that is
 * neither pass nor fail and reads as a page problem rather than the
 * infrastructure failure it is.
 *
 * NOT a timeout bump (#388's explicit boundary): a longer sleep hides a
 * dead server; this NAMES it. The deadline is bounded and the last cause is
 * carried in the message so the reader is sent to the infrastructure. */

/** Poll `base` until it accepts a connection and responds, or throw a named
 *  error on deadline. The failure it converts is the ECONNREFUSED a starved
 *  watch.py produces before it binds — turned into "the server never came up
 *  in Ns", which names the harness, not the page. Returns true on ready;
 *  never returns on deadline (throws). Composed with `serveVerified` (spawn
 *  + identity) and `waitFor` (DOM): a guard does serveVerified →
 *  waitForServer → goto → waitFor(selector). The `intervalMs` default
 *  matches serve.mjs's poll cadence. */
export async function waitForServer(
  base, { timeoutMs = 15000, intervalMs = 150 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastCause = null;
  while (Date.now() < deadline) {
    try {
      await fetch(base);
      return true;
    } catch (e) {
      lastCause = e?.cause?.code ?? String(e?.cause ?? e?.message ?? e);
    }
    await new Promise(r => setTimeout(r, intervalMs));
  }
  throw new Error(
    `waitForServer: ${base} never came up in ${timeoutMs}ms` +
    (lastCause ? ` (last: ${lastCause})` : ''));
}

/** textContent of the review dock's question headline with the live age
 *  removed -- the stable part, which is what identifies the question.
 *  Returns null when the dock is empty, so a caller cannot mistake a missing
 *  dock for a matching one. */
export async function dockHeadline(page) {
  return page.evaluate(() => {
    const qt = document.querySelector('#qdock .qt');
    if (!qt) return null;
    const clone = qt.cloneNode(true);
    // `.qage` is the age #385 injects; `.age` covers the shared painter's
    // other placements; `.qup` is #473's "updated X ago"; `.rsep` is the
    // chrome separator in front of each of them. Removing the NODE (not
    // regex-stripping the text) means this keeps working whatever format the
    // age is rendered in -- two figures, one figure, or `today` after #392a.
    //
    // #474: `.rsep` was missing here and #456's separator was bare text, so
    // stripping the age left ` · ` behind and both dock guards failed on a
    // correct page for two days. The rule the strip depends on, now stated in
    // watch-design.md: any headline chrome that is not the title is a node,
    // and that node's class is listed here. A future addition still has to be
    // added to this list -- which is why the callers assert that the strip
    // actually REMOVED something rather than trusting it silently.
    // `.qfocus` is #452's per-card focus link — headline chrome like the
    // rest, removed for the same identity question. `.qroll` is #454's
    // roll-up button, emitted on dock cards too (CSS declines it there)
    // and stripped here for the same reason.
    clone.querySelectorAll('.qage, .age, .qup, .rsep, .qfocus, .qroll')
      .forEach(n => n.remove());
    return clone.textContent;
  });
}

/** `{raw, stable}` for the same headline: the rendered textContent and the
 *  chrome-stripped one. A caller wanting to prove the strip is not a no-op
 *  needs both -- `raw !== stable` is the runtime precondition that this
 *  headline actually HAD chrome in it, and it is what would have caught #474
 *  the day #456 landed. Returns nulls when the dock is empty. */
export async function dockHeadlineParts(page) {
  const raw = await page.evaluate(() =>
    document.querySelector('#qdock .qt')?.textContent ?? null);
  return { raw, stable: await dockHeadline(page) };
}

/* ── keyed-store contract resolution (#476) ────────────────────────────────
 *
 * A guard that reads a dw:* localStorage key hardcodes the shape the page is
 * expected to write. When the production builder moves (measured 2026-07-29:
 * the dw:draft:v1: → v2: red-proof), a bare getItem(expected) returns null
 * and the guard's options are both wrong: a bare "nothing was stored" FAIL
 * that cannot tell "the save broke" from "the key contract moved" — or, in
 * the dereference shape (`s.raw.includes(...)` on the absent read), an
 * uncaught TypeError whose only verdict is the crash sentinel, which #471's
 * accounting reads as did-not-judge. A FAIL says "the contract broke"; the
 * sentinel says "this guard gated nothing", and the reader chases the guard
 * instead of the change.
 *
 * So: RESOLVE the contract before asserting on it — one trip that reads the
 * expected key AND enumerates the whole key family — and fail with
 * found-vs-expected. Never throws: storage errors land in `err`.
 */

/** Read `expected` from the page's localStorage and list every key in
 *  `familyPrefix` (pass '' to list all keys). Returns
 *  `{ expected, raw, found }` — `raw` null when the key is absent (or when
 *  `expected` is '', e.g. the page's target was unknown), `found` the
 *  sorted family listing, possibly empty. `err` is set only if storage
 *  itself refused. The caller builds the FAIL line that names both halves:
 *  the key it expected and the keys it found. */
export async function resolveStoreKey(page, expected, familyPrefix) {
  return page.evaluate(({ expected, familyPrefix }) => {
    const found = [];
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && (!familyPrefix || k.indexOf(familyPrefix) === 0)) found.push(k);
      }
      found.sort();
      const raw = expected ? localStorage.getItem(expected) : null;
      return { expected, raw, found };
    } catch (e) {
      return { expected, raw: null, found, err: String(e) };
    }
  }, { expected, familyPrefix });
}

/* ── frame-rate-free motion assertions (#414) ──────────────────────────────
 *
 * The obvious way to prove a transition is not a snap is to count how many
 * DISTINCT values it visited and require several. That reading is wrong on a
 * busy machine, and the reason is arithmetic rather than luck: the sampler is
 * a `requestAnimationFrame` loop, so the number of samples IS the frame rate,
 * and "at least 4 distinct values" cannot hold below 4 frames however
 * correct the animation is. `confirmation` failed exactly this way inside a
 * loaded `just test` while passing solo on the same machine.
 *
 * `reviewsplit.mjs` got there first and named it: count the frames that
 * landed strictly BETWEEN the two ends. A snap has none of those at any frame
 * rate; a real transition has one as soon as a single frame catches it
 * part-way. That is a rank-1 requirement instead of a rank-N one, which is
 * the whole difference. These helpers are that idea, shared, so the third and
 * fourth guard to need it do not each re-derive the threshold.
 */

/** Frames whose numeric value is strictly between the trace's first and last
 *  -- the snap detector. Endpoints are taken from the trace itself, never
 *  assumed, so it works for a rise (0→100) and a fall (100→0) alike. */
export function midFrames(values) {
  if (!values || values.length < 2) return 0;
  const from = values[0], final = values[values.length - 1];
  const lo = Math.min(from, final), hi = Math.max(from, final);
  return values.filter(v => v > lo && v < hi).length;
}

/** The same idea for non-numeric samples (a CSS `transform` string): frames
 *  that match NEITHER end. A snap jumps end to end and produces none. */
export function midStates(values) {
  if (!values || values.length < 2) return 0;
  const from = values[0], final = values[values.length - 1];
  return values.filter(v => v !== from && v !== final).length;
}

/* ── compositor-driven transitions and the rAF sampling gap (#442) ─────────
 *
 * `midFrames`/`midStates` are frame-rate-free in the sense #414 intended: a
 * snap has zero mid-frames at ANY frame rate. But they share a blind spot
 * with every rAF-sampled assertion: rAF runs on the MAIN THREAD, while
 * opacity/transform CSS transitions run on the COMPOSITOR. Under host load
 * (or even at baseline, because the page's own `#dreambg` shader keeps the
 * main thread busy) the compositor animates the property in real time while
 * rAF callbacks are starved — so zero samples land inside the transition
 * window, `midFrames` reads 0, and the guard reports a motion defect for a
 * scheduling artifact. Measured (#442): a 350ms opacity departure drew zero
 * rAF samples inside its window in 6/6 runs under 8 burners, and the
 * existing `length >= 3` precondition passed on every one because it counts
 * frames that ARRIVED (including settling frames outside the window), not
 * frames that landed INSIDE it.
 *
 * FLIP animations (prominence, states, morph, qsec) do NOT have this problem:
 * the FLIP sets `element.style.transform` per frame on the main thread, so
 * the sampler and the animation share the thread and stay in sync — slow
 * frames spread apart but the mid-values are still caught. The gap is
 * specific to compositor-driven CSS transitions (confirmation's `.depart`
 * opacity/transform/filter).
 *
 * The load-independent snap detector for a compositor-driven transition is
 * `transitionstart`: it fires iff the browser registered and began a CSS
 * transition for the property. A snap (transition removed from CSS) never
 * fires it — it asks the browser "did you animate?" rather than "how many
 * frames did the sampler catch?". The helpers below process the transition
 * events a guard captures alongside its rAF trace so the two failure modes
 * print distinguishable lines: "snapped" (no transitionstart) vs "the trace
 * did not sample the window" (transitionstart fired but zero frames inside
 * [start, end]). */

/** Given an array of `{type, prop, t}` transition events (captured by
 *  listening for transitionrun/start/end in the page), find the window of a
 *  transition for `prop` that starts at or after `afterT`. `pick` selects
 *  'first' (the arrival) or 'last' (the departure) when multiple match.
 *  confirmation's success has two opacity transitions — arrival (0→100) and
 *  departure (100→0) — and the caller isolates the one under test with
 *  `afterT` and `pick`. Returns `{ran, start, end, dur}`; `ran` is false
 *  when no matching transitionstart fired.
 *
 *  `end` is the first end at-or-after the chosen `start`, never
 *  `ends.at(idx)` independently of `start`. An opacity transition that
 *  *started* before `afterT` can still *end* after it; pairing last-start
 *  with last-end independently then yields a negative `dur` (measured
 *  #444: popout departure −68…−178ms while `ran` stayed true). `dur` is a
 *  diagnostic note only — see transitions.md #444; existence (`ran`) is the
 *  snap detector. */
export function transitionWindow(events, prop, afterT = -Infinity, pick = 'last') {
  const starts = events.filter(e => e.type === 'start' && e.prop === prop && e.t >= afterT);
  const ends = events.filter(e => e.type === 'end' && e.prop === prop && e.t >= afterT);
  if (!starts.length) return { ran: false, start: null, end: null, dur: null };
  const start = pick === 'first' ? starts[0].t : starts.at(-1).t;
  const end = ends.find(e => e.t >= start)?.t ?? null;
  return { ran: true, start, end,
           dur: end !== null ? end - start : null };
}

/** Count trace frames whose timestamps fall inside a transition window.
 *  `frames` is the rAF trace (each entry has `.t`); `win` is the return of
 *  `transitionWindow`. When the window is null (no transition), returns 0. */
export function framesInWindow(frames, win) {
  if (win.start === null) return 0;
  const end = win.end ?? Infinity;
  return frames.filter(f => f.t >= win.start && f.t <= end).length;
}

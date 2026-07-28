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
    // other placements. Removing the NODE (not regex-stripping the text)
    // means this keeps working whatever format the age is rendered in --
    // two figures, one figure, or `today` after #392a.
    clone.querySelectorAll('.qage, .age').forEach(n => n.remove());
    return clone.textContent;
  });
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

/* Shared DOM readers for the guards.
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

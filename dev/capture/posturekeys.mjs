/* posturekeys — #661: derive the expected /summary.json posture key set
   from lint.py's POSTURE_AXES (the closed-set source of truth) rather than
   restating it, so the browser guard and the pytest stay in step with the
   _summary_posture projection without a hand-maintained literal.

   This is the #596 family: a hand-maintained list kept in step with a source
   of truth by hand, with nothing to diff them. #596's fix was to diff the
   route tables against the route set; the analogous fix here is to diff the
   projection's output against POSTURE_AXES. The projection
   (_summary_posture, watch.py) and POSTURE_AXES (lint.py) are TWO
   INDEPENDENT declarations — deriving both sides of the comparison from the
   SAME source (e.g. parsing _summary_posture's own tuple) would assert
   nothing (#671: a check that examined nothing must not read as passing).

   The invariant: /summary.json `posture` carries every recognised axis
   (POSTURE_AXES) plus `source` (where the axes came from: 'derived'|'file')
   and nothing else — the display chrome (delegation_label, subagent_policy*)
   is projected out. This helper reads the axis set so a guard/test comparing
   it against the served key set never needs a hand-maintained literal. */
import { readFileSync } from 'node:fs';

// POSTURE_AXES is a single-line tuple of double-quoted names:
//   POSTURE_AXES = ("pace", "asking", "delegation", "delivery", "orchestration")
// `[^)]*` spans it even if reformatted across lines (no `)` inside a string
// list); the quoted-name scan then takes only real keys. A cardinality floor
// turns a broken parse (the tuple rewritten to a call, the regex drifted)
// into a LOUD failure rather than a silently-empty set — the hollow-check
// failure mode this repo has paid for.
const AXES_RE = /POSTURE_AXES\s*=\s*\(([^)]*)\)/;
const QUOTED = /"([^"]+)"/g;

export function readPostureAxes(lintSource) {
  const m = AXES_RE.exec(lintSource);
  if (!m)
    throw new Error('POSTURE_AXES not found in lint source — regex drifted?');
  const keys = [...m[1].matchAll(QUOTED)].map(x => x[1]);
  if (keys.length < 3)
    throw new Error(
      `POSTURE_AXES parsed ${keys.length} axis/axes — the scan broke ` +
      `(rewritten to a call? quoted with single quotes?) and a guard ` +
      `must not read a silently-empty set as a pass (#671)`);
  return keys;
}

export function readPostureAxesFile(lintPath) {
  return readPostureAxes(readFileSync(lintPath, 'utf8'));
}

// The expected /summary.json posture key set: every recognised axis plus the
// one non-axis key the projection carries. `source` is NOT an axis (it is
// where the axes came from), so it is added here rather than read from
// POSTURE_AXES — and a cardinality check in the caller asserts that it is
// genuinely separate, so a future 'source' axis collision cannot make this
// a no-op.
export function expectedSummaryPostureKeys(axes) {
  return new Set([...axes, 'source']);
}

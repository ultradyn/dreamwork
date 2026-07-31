/* summaryjson — #275/Q5: the redacted /summary.json leaks nothing only the
   full /data.json carries.

   The endpoint this guard grades is the deliverable: a whitelist view of
   collect() served at /summary.json, for any non-loopback consumer. The
   full /data.json serves DREAMWORK.md, questions.md and lessons.md IN FULL
   plus parsed entries, transcripts and status.json — unfit to expose — and
   /summary.json is what replaces it. So the discriminating checks are LEAK
   checks, and the leak strings are DERIVED at runtime from the fixture's
   real documents, never hand-written: a planted "secret" proves only that
   the planted string is absent.

   This guard serves its OWN target (the shared fixture has no git history,
   and burndown_counts is shape-only here), takes the port from argv[3],
   and uses an ephemeral port only when argv[3] is absent — it hardcodes no
   exclusive port (reviewdraft does, and #471 is the open tax on that). It
   proves the responder is OURS via serveVerified (#461): a stale
   watch.py on the port would otherwise grade the wrong target invisibly.

   usage: node summaryjson.mjs <outdir> [port]   (port omitted → ephemeral) */
import { mkdirSync, rmSync, cpSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveVerified } from './serve.mjs';
import { readPostureAxesFile, expectedSummaryPostureKeys }
  from './posturekeys.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Take the port from argv[3]; only when it is absent do we ask for an
// ephemeral one. Never hardcode an exclusive port — `just guards` hands a
// port in, and a guard that ignores it collides with its siblings (#471).
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
// OWN-SERVER GUARD: the port is ALWAYS ephemeral; argv[3] is deliberately
// ignored. #461 made this adopt argv[3] so a squatter red-proof could aim, and
// because the recipe always passes {{port}} that silently forced this guard onto
// the shared server's port, where serveVerified rightly refused -- so the guard
// stopped running at all (#471). Registration is not execution.
const PORT = await freePort();

const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/summary.json served from a scratch fixture target — exact output ' +
          'key set, every denied field absent by name, and the DERIVED leak ' +
          'strings from DREAMWORK.md/questions.md/dream-transcript absent ' +
          'while their precondition (present in /data.json) holds',
  traceWindow: 'one fetch per endpoint after serveVerified readiness; no ' +
               'animation or poll window — this is a content/leak check, not ' +
               'a motion check',
});

// ── own target: the shared fixture holds the doc/transcript shapes ──────
const dir = join(OUT, 'target');
rmSync(dir, { recursive: true, force: true });
cpSync('dev/capture/fixture', dir, { recursive: true });

let child;
try {
  child = await serveVerified(dir, PORT);
} catch (e) {
  errs.push(`serve: ${e.message}`);
  finish(); process.exit(1);
}
const stop = () => { try { child.kill(); } catch (e) {} };
process.on('exit', stop);

const BASE = `http://127.0.0.1:${PORT}`;
const fetchJson = async (path) => {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json();
};

let full, summary;
try {
  full = await fetchJson('/data.json');
  summary = await fetchJson('/summary.json');
} catch (e) {
  errs.push(`fetch: ${e.message}`);
  finish(); process.exit(1);
}

// ── the exact whitelist output set ──────────────────────────────────────
const EXPECTED = new Set([
  'generated', 'open_questions', 'questions_health', 'answers_health',
  'tint', 'run_mode', 'posture', 'skill_identity', 'burndown_counts',
  'skill_version',
]);
ok('/summary.json carries exactly the whitelisted fields',
   JSON.stringify([...Object.keys(summary)].sort()) ===
   JSON.stringify([...EXPECTED].sort()));

// ── every denied field is absent by NAME ────────────────────────────────
const DENIED = ['target', 'linkable_paths', 'dreams', 'dreams_archive',
                'files', 'reviews', 'research', 'questions_open',
                'answered_entries', 'answers_open', 'answers_answered',
                'pending_handoffs', 'status', 'git', 'deployed',
                'plugin_commands', 'chats'];
for (const key of DENIED) {
  ok(`denied field ${key} is absent from /summary.json`, !(key in summary));
}

// ── the partition: every /data.json key is classified (the heart) ───────
// The source whitelist is the Python SUMMARY_ALLOWED/DENIED; this guard's
// half is that NO /data.json key reaches /summary.json unclassified. The
// interesting case is the field added in three weeks, so this derives the
// data.json key set at runtime rather than enumerating today's.
// (Allowed/denied are the guard's own mirror of the production constants;
// the pytest partition test is the binding one — this is the consumer view.)
const allowedSources = new Set(['generated', 'open_questions',
  'questions_health', 'answers_health', 'tint', 'run_mode', 'posture',
  'skill_identity', 'burndown', 'files']);
const deniedSources = new Set(DENIED);
const dataKeys = Object.keys(full);
const unclassified = dataKeys.filter(k => !allowedSources.has(k) &&
                                          !deniedSources.has(k));
ok('every /data.json key is classified allowed-or-denied (else a new field ' +
   'slipped through unreviewed)',
   unclassified.length === 0);
if (unclassified.length)
  notes.push('unclassified /data.json keys: ' + unclassified.join(', '));

// ── the leak checks, DERIVED from the real fixture documents ────────────
// A value in /summary.json must not contain content that only the full
// documents carry. The probes are taken from the fixture's real files at
// runtime — the first distinctive prose line of each — and the
// PRECONDITION that each probe really IS in /data.json is asserted first,
// or the absence is vacuous (the hollow red-run this repo has paid for).
const summaryBlob = JSON.stringify(summary);
const fullBlob = JSON.stringify(full);
const deriveProbe = (relPath) => {
  const txt = readFileSync(join(dir, relPath), 'utf8');
  // first non-heading prose line long enough to be distinctive
  const line = txt.split('\n').map(l => l.trim())
    .find(l => l && !l.startsWith('#') && l.length > 12);
  if (!line) throw new Error(`no usable probe in ${relPath}`);
  return line;
};

for (const [relPath, label] of [
  ['DREAMWORK.md', 'DREAMWORK.md'],
  ['.dreamwork/questions.md', 'questions.md'],
]) {
  let probe;
  try { probe = deriveProbe(relPath); }
  catch (e) { errs.push(e.message); continue; }
  notes.push(`${label} probe: ${JSON.stringify(probe)}`);
  // precondition: the probe really IS in the full payload — else the
  // absence below proves nothing.
  ok(`precondition: ${label} probe IS present in /data.json`,
     fullBlob.includes(probe));
  ok(`${label} prose is absent from /summary.json (no full-document leak)`,
     !summaryBlob.includes(probe));
}

// transcripts: explicitly OUT (#275 brief). Derive the probe from the real
// dream transcript the fixture ships, and assert its precondition too.
const dreamDir = join(dir, '.dreamwork', 'dreams');
import('node:fs').then(() => {});
const { readdirSync } = await import('node:fs');
const dreamFiles = readdirSync(dreamDir).filter(f => f.endsWith('.md'));
ok('precondition: fixture ships at least one dream transcript',
   dreamFiles.length > 0);
if (dreamFiles.length) {
  const probe = deriveProbe(join('.dreamwork', 'dreams', dreamFiles[0]));
  notes.push('dream transcript probe: ' + JSON.stringify(probe));
  ok('precondition: dream transcript IS present in /data.json',
     fullBlob.includes(probe));
  ok('dream transcript content is absent from /summary.json (transcripts OUT)',
     !summaryBlob.includes(probe));
}

// ── the posture axis set, DERIVED from lint.py (#661) ───────────────────
// The expected /summary.json posture keys are lint.py's POSTURE_AXES (the
// closed-set source of truth every recognised posture axis must be listed in)
// plus `source` (where the axes came from: 'derived'|'file'), and nothing
// else. The projection (_summary_posture, watch.py) and POSTURE_AXES
// (lint.py) are TWO INDEPENDENT declarations — a literal here was the trap
// #510 fell into (shipped orchestration, the guard's list didn't widen, and
// it was repaired later by b9248b11). Deriving from POSTURE_AXES means the
// next axis widens both at once, with no hand-maintained literal to drift.
// The cardinality precondition turns a broken parse (regex drifted, the
// tuple rewritten) into a LOUD red rather than a silently-empty set (#671).
const EXPECTED_POSTURE = expectedSummaryPostureKeys(
  readPostureAxesFile('lint.py'));

// ── the fields that DO leave are safe by shape ──────────────────────────
ok('open_questions is an integer count',
   Number.isInteger(summary.open_questions));
ok('questions_health is an enum token, not prose',
   ['ok', 'missing', 'unreadable', 'empty'].includes(summary.questions_health));
ok('answers_health is an enum token, not prose',
   ['ok', 'missing', 'unreadable', 'empty'].includes(summary.answers_health));
// ── the posture axis set: derived, not restated (#661) ──────────────────
// EXPECTED_POSTURE is read from lint.py's POSTURE_AXES + 'source' (see top),
// not hand-maintained here — so widening the projection's axis set widens
// this check at the same time. A missing or unexpected key is named in the
// failure (not just "mismatch"), so the drift is readable from the run.
const actualPosture = new Set(Object.keys(summary.posture));
const missingPosture = [...EXPECTED_POSTURE].filter(k => !actualPosture.has(k));
const extraPosture = [...actualPosture].filter(k => !EXPECTED_POSTURE.has(k));
ok('posture carries exactly POSTURE_AXES + source (no display chrome; #661)',
   missingPosture.length === 0 && extraPosture.length === 0);
if (missingPosture.length)
  notes.push('posture keys MISSING vs POSTURE_AXES+source: ' +
             missingPosture.join(', '));
if (extraPosture.length)
  notes.push('posture keys UNEXPECTED (display chrome leaked?): ' +
             extraPosture.join(', '));
ok('skill_identity carries only commit + skill_version',
   JSON.stringify([...Object.keys(summary.skill_identity)].sort()) ===
   JSON.stringify(['commit', 'skill_version']));
ok('burndown_counts carries only the three integer counts',
   JSON.stringify([...Object.keys(summary.burndown_counts)].sort()) ===
   JSON.stringify(['arrived', 'landed', 'open']));
ok('every burndown count is an integer',
   ['open', 'arrived', 'landed'].every(
     k => Number.isInteger(summary.burndown_counts[k])));

stop();
finish();

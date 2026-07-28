/* reviewask — #436 walking guard: every built review artifact is CHECKED or
   EXPLICITLY EXEMPT, and the coverage equation is asserted as sets.

   Build-time contracts (#436 ask, #455 if-silent) only run when a source is
   built. The 12 untemplated pre-#436 pages have no src/ and must not be
   hand-edited, so a guard that only inspected metas would silently pass over
   them — the hollow-check failure this repo has paid for most often. This
   guard closes that by walking the whole corpus and requiring each basename
   either carries the builder's ask meta or is named in the side-file
   `.dreamwork/review/legacy-contract-exemptions.txt` with a reason.

   THE COVERAGE EQUATION (sets, never a literal count):
     examined ∪ side_exempt == built
     examined ∩ side_exempt == ∅
     {src} − {built} == ∅

   Sourceless is `{built} − {src}`, not `|built| − |src|`.

   Production line the strip-#ask red-proof names:
     `check_examined_artifact` in review_artifact.py — when meta content is
     exactly "ask", `scan_ask` must report present+meaningful. Stripping the
     `#ask` element from a content="ask" artifact reds this guard.

   above_fold.mjs stays the per-artifact fold TOOL (lint.NOT_GUARDS); this file
   is the registered walker. It does not bind a browser port — it shells the
   Python corpus walk so pytest and the guard share one production path.

   usage: node reviewask.mjs <outdir> [port]   (port accepted, unused) */
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2] || '.';
const PORT = process.argv[3] || ''; // accepted for DEFAULT_GUARDS contract; unused
mkdirSync(OUT, { recursive: true });

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..', '..');
const REVIEW = join(ROOT, '.dreamwork', 'review');

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: 'filesystem walk of .dreamwork/review/*.html + legacy-contract-exemptions.txt '
        + '(no browser; shares review_artifact.py corpus with pytest)',
  traceWindow: 'none: pure file/meta coverage; above_fold remains the fold tool',
});
if (PORT) notes.push(`  port arg accepted and unused (shared-server contract): ${PORT}`);

let stdout = '';
let code = 0;
try {
  stdout = execFileSync(
    'python3',
    [join(ROOT, 'review_artifact.py'), 'corpus', '--review-dir', REVIEW],
    { encoding: 'utf-8', cwd: ROOT },
  );
} catch (err) {
  code = typeof err.status === 'number' ? err.status : 1;
  stdout = (err.stdout || '') + (err.stderr || '');
}

writeFileSync(join(OUT, 'corpus.txt'), stdout);
for (const line of stdout.split('\n')) {
  if (line.trim()) notes.push('  ' + line);
}

// Parse the summary lines the Python reporter always prints so the guard's own
// ok() rows name the equation rather than only "exit code was zero".
const examined = /examined=(\d+)/.exec(stdout);
const side = /side_exempt=(\d+)/.exec(stdout);
const built = /built=(\d+)/.exec(stdout);
const equation = /coverage equation[\s\S]*?→\s*(ok|FAIL)/.exec(stdout);
const corpusOk = /corpus: ok —/.test(stdout);

ok('python corpus walk exited 0', code === 0);
ok('coverage equation examined ∪ side_exempt == built reported ok',
   !!(equation && equation[1] === 'ok') && corpusOk);
ok('precondition: built corpus is non-empty (else the walk is vacuous)',
   !!(built && Number(built[1]) > 0));
ok('precondition: at least one artifact is examined (has ask meta)',
   !!(examined && Number(examined[1]) > 0));
ok('precondition: side-exempt set is non-empty while untemplated pages remain',
   !!(side && Number(side[1]) > 0));
ok('no FAIL lines in corpus report', !/^FAIL /m.test(stdout));

finish();

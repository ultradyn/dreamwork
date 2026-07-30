/* outdir — shared argv[2] validator for dev/capture guards (#376).

   Every guard is invoked `node dev/capture/<name>.mjs <outdir> [port]`. The
   one-argument mistake — a port passed where the outdir belongs — used to
   silently `mkdirSync` a directory NAMED AFTER THE PORT and screenshot into
   it (two such dirs, `39898/` and `39899/`, sat in the repo root for three
   days reading as server artifacts, not typos). This helper refuses that
   shape before any directory is made.

   Contract:
     - missing argv[2]: print a usage line and exit EX_USAGE (64), UNLESS a
       `default` is supplied (the handful of guards that fall back to a
       built-in outdir pass it; the all-digits rule still applies to them).
     - all-digits argv[2]: ALWAYS refuse — no plausible outdir is all digits,
       and that is exactly the port-as-outdir mistake, default or not.
     - otherwise: return argv[2] untouched.

   EX_USAGE (64) mirrors the repo's Python CLIs. stderr is written with
   process.stderr.write (a synchronous, blocking write on pipes/files) so the
   message is flushed before the nonzero exit. Guards import this the same way
   they already import ./dom.mjs / ./report.mjs:

       import { outdir } from './outdir.mjs';
       const OUT = outdir(process.argv);            // OUT,PORT = argv[2],argv[3]
       const OUT = outdir(process.argv, { default: '.' });  // guards with a fallback
*/
import { basename } from 'node:path';

const EX_USAGE = 64;

export function outdir(argv, opts = {}) {
  const script = basename(String(argv[1] ?? 'guard.mjs'));
  const usage = `usage: node dev/capture/${script} <outdir> [port]`;
  const val = argv[2];
  if (val === undefined) {
    if (opts.default !== undefined) return opts.default;
    process.stderr.write(`${usage}\n`);
    process.exit(EX_USAGE);
  }
  if (/^\d+$/.test(val)) {
    process.stderr.write(
      `refused: <outdir> "${val}" is all digits — that looks like a port, not a directory.\n${usage}\n`,
    );
    process.exit(EX_USAGE);
  }
  return val;
}

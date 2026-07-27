/* report — the shared reporter every guard in dev/capture/ inherits.

   #192: 18 of the gating guards print their checks at the TAIL of the
   script, so when one crashes partway it prints NO checks at all — and a
   FAIL-grep over that silence reads it as a clean sheet. The gate still
   holds (`just guards` branches on exit code); what lies is the EYEBALL:
   a human running one guard directly, scanning for FAIL, and seeing
   nothing because nothing printed. Three of this repo's own fault
   injections read as "proves nothing" that way.

   The fix is not a sweep of 18 files — that count was 17 of 39 eighteen
   minutes before it was measured, because every NEW guard is written
   without the sentinel (there was nothing to inherit it from). A one-time
   sweep is stale within a day. This module is the rate fix: a guard
   imports it and inherits the obligations by construction, so the next
   guard gets them for free.

   This is a MODULE the guards import, not a runner — #148's runner is the
   justfile recipe and does not block this. No guard in dev/capture/
   imported a sibling when this landed (zero relative imports across 49
   files), but ESM relative imports work here: the scripts already import
   playwright by absolute path. Guards adopt this one at a time; #148's
   runner adopts it later.

   THE FOUR OBLIGATIONS, and how each is made structural rather than
   remembered:

   1. THE CRASH SENTINEL. The exit handler registered here prints the
      checks whether or not the guard reached its own end. If it did not,
      a FAIL line is appended: "the guard threw before finishing its
      checks". A crash (uncaught throw) still fires process.on('exit') in
      Node, so the sentinel lands where a tail-printer printed nothing.
      The guard calls finish() at its successful end to mark the sentinel
      satisfied; forgetting to call it makes a CRASH visible (the point)
      and a clean run no quieter than before.

   2. ABSENCE-FIRST. present(page, selector, what) asserts the subject
      exists before anything drives it, so a build without the feature is
      one named FAIL in seconds, not a thirty-second Playwright timeout
      reported as "the guard threw" — a message that says nothing about
      the page and points at the guard. history.mjs is the reference; its
      red run against an absent subject costs 3.4s instead of 30.

   3. REPORT FROM FULL OUTPUT, NEVER A COUNT. This reporter prints
      checks.join('\n') — the whole list, every time. It offers no count,
      no summary, no tally: a grep -c in a compound command once reported
      6 FAILs where the full output held 14 (the server had been swapped
      beneath it). A guard using this module cannot accidentally report a
      count because the module does not provide one.

   4. THE COVERAGE + TRACE-WINDOW DECLARATION. declare({drives, traceWindow})
      states which routes and gestures the guard drives AND how long it
      traces — because a guard that watches long enough will see SOMETHING
      produce the result it wants (regroup.mjs traced 5.2s past a 1.6s
      holdRerenderUntil and the tick's own regroup supplied the motion it
      was asserting). The declaration prints in the output header so a
      reader sees the guard's reach before its verdicts. finish() flags a
      visible gap if a guard forgets to call declare().

   usage:

     import { makeReporter } from './report.mjs';
     const r = makeReporter();
     const { ok, present, declare, finish, checks, notes, errs } = r;
     declare({ drives: '…which routes/gestures…',
               traceWindow: '…how long it traces, and why…' });
     const br = await chromium.launch(...);
     const p = await br.newPage(...);
     p.on('pageerror', e => errs.push(String(e)));
     // ...
     if (!(await present(p, '#subject', 'the subject'))) { await br.close(); finish(); return; }
     ok('a check name', cond);
     // ...
     await br.close();
     finish();

   If the reporter itself throws, that is LOUDER than the guard's failure,
   never quieter: makeReporter does not swallow, and an exit-handler throw
   aborts the handler and Node prints the stack at its default non-zero
   exit. The guard's own ok() verdicts already printed are not lost, but
   the reader is sent to the reporter, not lulled by it. */
export function makeReporter() {
  const checks = [];
  const notes = [];
  const errs = [];
  let finished = false;
  let declared = null;

  // Obligation 1 — the crash sentinel. Registered once at construction;
  // fires on clean exit, process.exit(), and uncaught-throw (Node runs
  // 'exit' handlers before going down for an uncaught exception). A guard
  // that never calls finish() is a guard that crashed, and the sentinel
  // says so.
  process.on('exit', () => {
    if (!finished) checks.push('FAIL the guard threw before finishing its checks');
    const cov = declared
      ? `[coverage] drives: ${declared.drives} | trace window: ${declared.traceWindow}`
      : '[coverage] NONE DECLARED — call declare({drives, traceWindow}) ' +
        'so a reader knows what this guard reaches';
    process.stdout.write(
      cov + '\n' +
      notes.join('\n') + (notes.length ? '\n' : '') +
      '----\n' +
      checks.join('\n') + '\n' +
      (errs.length ? errs.join('\n') + '\n' : ''));
  });

  // Obligation 4 — the coverage + trace-window declaration. Both halves
  // are required: drives names WHAT the guard exercises (routes, gestures),
  // traceWindow names HOW LONG it watches (and so what it could miss). A
  // guard that traces past a holdRerenderUntil can assert motion the tick
  // itself supplied — the declaration is where that bound is stated.
  function declare({ drives, traceWindow }) {
    if (typeof drives !== 'string' || typeof traceWindow !== 'string' ||
        !drives.trim() || !traceWindow.trim()) {
      throw new TypeError(
        "report.declare needs {drives, traceWindow} as non-empty strings; " +
        "a guard may not leave its coverage or trace window unstated");
    }
    declared = { drives, traceWindow };
  }

  // Obligation 1 — finish() marks the sentinel satisfied and sets the
  // exit code from the guard's own verdicts. Call this exactly once, at
  // the successful end of the guard, after all browser/process cleanup.
  function finish() {
    finished = true;
    process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
  }

  // Obligation 2 — absence-first. Asserts the subject exists before the
  // guard drives it. Returns the existence bool so the guard can skip the
  // rest (a re-asserted absence would only repeat the same timeout under
  // a different name). `what` is the noun that goes in the check name, so
  // a red names the missing subject rather than "a selector".
  async function present(page, selector, what) {
    const there = await page.evaluate(
      s => !!document.querySelector(s), selector);
    checks.push(`${there ? 'PASS' : 'FAIL'} ${what} ` +
      `exists (else every check below is about a page that has none)`);
    return there;
  }

  function ok(name, cond) {
    checks.push(`${cond ? 'PASS' : 'FAIL'} ${name}`);
  }

  return { ok, present, declare, finish, checks, notes, errs };
}

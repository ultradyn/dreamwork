/* serve — start a watch.py for a guard and prove the answer comes from IT.

   #461. The shared runner (`justfile`'s `guards` recipe) already defends the
   port it owns: it refuses to start when someone holds it, and then checks
   `/data.json`'s `target` against the fixture it meant to serve. Its own
   comment explains why the check lives there — "only the guards that start
   their OWN server were immune, so the check belongs here rather than in each
   of the ten."

   That was true of #203's failure mode and false of this one. The own-server
   guards do not use ephemeral ports: they take a base port and increment it
   (`ports[name] = ++port`), so they land on fixed, predictable ports in the
   39890-39899 range — the same range that collects orphans. And their
   readiness step is typically `await sleep(2500)` with `stdio: 'ignore'`, so
   when the port is already held, python exits "address in use" invisibly, the
   sleep passes anyway, and every subsequent assertion grades a DIFFERENT
   target. The guard then reports feature bugs about a fixture nothing ever
   read.

   This is not hypothetical and it is not only guards. On 2026-07-29 the
   coordinator probed #263's `202` cutover twice and got `200` twice — the
   exact pre-cutover fallback — and read a correct change as broken. Two
   orphaned `watch.py` servers from a worktree deleted 2.5 hours earlier still
   held 39895 and 39896, and the probe's own server had died on an argparse
   error. Nothing was mocked; the answer simply came from somewhere other than
   the code under test.

   So the rule this module makes structural: **assert the responder's
   identity, not just that something responded.** Two independent things are
   checked, because either alone can pass over the failure:

     - the process is still alive (a dead spawn cannot be the responder), and
     - `/data.json`'s `target` is the directory we asked for (a live stranger
       on the port cannot pass this, and it is the only signal that
       distinguishes our server from another watch.py serving something else).

   Adopted one guard at a time, like `report.mjs` — a one-time sweep of 30
   files is stale the day a 31st guard is written, and the point is that the
   next guard inherits the obligation instead of remembering it.  */

import { spawn } from 'node:child_process';

const sleep = ms => new Promise(r => setTimeout(r, ms));

/* Fetch the served target, or null. A stranger may answer anything at all —
   including nothing parseable — so every failure mode collapses to null and
   the caller treats "cannot prove it is ours" identically to "it is not
   ours". */
async function servedTarget(port) {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/data.json`);
    if (!res.ok) return null;
    const j = await res.json();
    return typeof j.target === 'string' ? j.target : null;
  } catch (e) {
    return null;
  }
}

/* Start `watch.py --target dir --port port` and return the child once the
   answer on that port is provably ours. Throws otherwise — a guard that
   cannot establish whose server it is talking to must not go on to grade it.

   `expect` defaults to `dir`; pass it when watch.py reports a resolved path
   that differs from the one handed in (an absolute form of a relative dir).
   The comparison accepts either the literal or its realpath-resolved form so
   a guard is not forced to pre-resolve. */
export async function serveVerified(dir, port, { timeoutMs = 12000,
                                                 expect = null,
                                                 args = [] } = {}) {
  const child = spawn('python3',
                      ['watch.py', '--target', dir, '--port', String(port),
                       ...args],
                      { stdio: 'ignore' });
  let exited = null;
  child.on('exit', code => { exited = code === null ? 'signal' : code; });

  const want = expect === null ? dir : expect;
  const deadline = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < deadline) {
    if (exited !== null) {
      // The most common real cause is "address in use": something already
      // holds the port. Say so, because the symptom a guard would otherwise
      // report is a screenful of wrong assertions about the wrong fixture.
      const holder = await servedTarget(port);
      throw new Error(
        `serve: watch.py exited (${exited}) before serving :${port} for ` +
        `${dir}` +
        (holder === null
          ? ' — nothing is answering that port either'
          : ` — and :${port} is being served by ${holder} by someone else, ` +
            'so the port was already held (see: just reap)'));
    }
    last = await servedTarget(port);
    if (last !== null) break;
    await sleep(150);
  }

  if (last === null) {
    try { child.kill(); } catch (e) {}
    throw new Error(`serve: :${port} never answered for ${dir} ` +
                    `within ${timeoutMs}ms`);
  }
  if (last !== want && !last.endsWith(want) && !want.endsWith(last)) {
    try { child.kill(); } catch (e) {}
    throw new Error(
      `serve: :${port} is serving ${last}, not ${want} — a stale server ` +
      'holds the port and every assertion after this would grade the wrong ' +
      'target (inspect/clean: just reap)');
  }
  return child;
}

/* Start several targets at once, each on its own port, and prove every one.
   `entries` is [[name, dir], ...] and `basePort` is incremented per entry,
   matching the existing `ports[name] = ++port` idiom so an adopting guard
   keeps its port numbering. Returns { children, ports }.

   All spawns are verified — a partial check is how one stale server in a set
   of four goes unnoticed. On any failure every child started here is killed,
   so a throwing guard does not leak the orphans this module exists to fix. */
export async function serveAllVerified(entries, basePort, opts = {}) {
  const children = [];
  const ports = {};
  let port = basePort;
  try {
    for (const [name, dir] of entries) {
      ports[name] = ++port;
      children.push(await serveVerified(dir, ports[name], opts));
    }
  } catch (e) {
    children.forEach(c => { try { c.kill(); } catch (_) {} });
    throw e;
  }
  return { children, ports };
}

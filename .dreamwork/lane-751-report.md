# Lane 751 report — P3 `/research` native conversion

## Verdict

**BLOCKED before implementation.** The conversion needs one edit outside this
lane's allowed ownership: `watch.py` must load `client/dist/native.js` and place
it in the assembled page before `client/router.js` tries to consult
`dwNative.registry`. The brief expressly says to stop and report if that file
is needed, so I made no production change and did not attempt a workaround.

The task entry's binding instruction was:

> "THE WORK: /research (the listing) flips native. buildResearch is DELETED in
> the same commit — the flip-commit rule, zero-commit overlap"

That atomic flip cannot be made honestly while the runtime remains absent from
the served page.

## Evidence

- `watch.py:643-644` says explicitly that nothing under `client/dist/` reaches
  `PAGE`.
- `watch.py:694-707` assembles the sole inline script from morphdom and the
  eight `client/*` assets. It appends `ROUTER_JS + COMMAND_JS`; it neither reads
  nor appends `client/dist/native.js`.
- `watch.py:5167-5176 @ e6e44ddc` serves that one assembled page for `/research`.
  `watch.py` has no static route for `client/dist/native.js`; unmatched GETs
  fall through to 404.
- `dev/build/src/native-entry.js:26-27` states the intended seam: the bundle
  exports `window.dwNative`, and P3's router consults `dwNative.registry`.
- `test_client_dist.py:122-153` still enforces the P2-only invariant that
  `native.js` content must not reach the assembled page. P3 must deliberately
  replace that assertion with the new served-runtime contract in the same
  ownership window as the page-assembly edit.

The smallest coherent unblock is therefore to wait until the current
`watch.py` owner lands, then let P3 own the narrow assembly change (read the
committed bundle and append it as the second classic-script payload before the
router needs it) together with the corresponding P2-containment-test update.
Only then can the atomic flip contain the native component, registry routing,
`buildResearch` deletion, rebuilt dist, and its guard.

## Rejected route-arounds

- Fetching the runtime from `client/router.js` is not available: the server has
  no bundle endpoint, and the dashboard is intentionally one HTML response.
- Fetching through `/filedata` would read from the watched target rather than
  the skill checkout that owns the runtime, fail for ordinary external
  targets, and execute code through an unrelated data endpoint.
- Copying or evaluating the bundle from router source would introduce another
  generated/runtime truth and would no longer exercise the settled second
  classic-script position.

## Verification and red-proof status

No implementation or guard was written, so no browser guard, build, or lint run
is claimed. The required exit gate was run and reported exactly:

> `check: calm — no injections registered (opt-in discipline; nothing to evaluate).`

The worktree was inspected before stopping; the only pre-existing untracked
path is `BRIEF.md`, and this report is the only lane addition.

Rebase outcome: local `master` advanced by five commits while this report was
being written. The report commit rebased cleanly onto `master` at `3db7c26b`;
there was no conflict to resolve.

## DOGFOOD REPORT

The task head accurately anticipated this failure and saved a bad workaround:
its off-limits rule says to stop if `watch.py` is needed. The underlying plan,
however, assigns P3 the act of serving the P2 bundle while its stated P3 file
scope omits the only page-assembly owner. The P2 containment test also still
hard-codes the phase claim that no dist content may reach `PAGE`; the future P3
brief should explicitly transfer ownership of both `watch.py` and that test,
or state that a prerequisite landing has already installed the bundle. Without
that correction, every P3 lane will rediscover the same structural blocker.

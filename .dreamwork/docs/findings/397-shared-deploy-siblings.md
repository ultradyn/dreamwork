# The deploy dir's siblings are shared across targets, and since #397 that is the whole UI

**Status:** open. Found by both reviewers of #397 (lane-clientextract), deliberately
NOT fixed in that lane — see "Why it was not fixed here".

**Severity:** it lets a deploy from one checkout silently repaint another
target's dashboard, while every staleness check still reports `current`.

## The shape

`just deploy` names the snapshot per target:

```
snap="$dir/$(basename "$PWD")-watch.py"      # justfile, dir=~/.cache/dreamwork/deployed
```

but ships the siblings to the dir itself:

```
python3 dev/deploy_state.py --ship-siblings {{rev}} --dest "$dir"
```

So snapshots are namespaced and siblings are not. Every target deployed on
this machine shares one `~/.cache/dreamwork/deployed/client/`. The dir already
holds several snapshots (`ud-dreamwork-watch.py`, `425-scratch-*`).

This sharing predates #397 — it arrived with the sibling closure at #480, and
it covered `lint.py`, `ledger_parse.py` and `user_events/` then. What #397
changed is the blast radius: `client/` is now 10,500 lines of css and js, i.e.
**the entire front end**, so the shared surface went from "a few server-side
modules that rarely differ between checkouts" to "what the human looks at".

## Reproduced

A second repo shipped into the same dest; the first target's snapshot was
never touched; restarting it served the *other* repo's stylesheet:

```
shipped from the OTHER repo: [client/app_body.html … client/views.js, watch.py]
marker count after restart: 1                      # foreign CSS now served

sha256 deployed/lane-clientextract-watch.py  == sha256 git show HEAD:watch.py
2a39ae45c5917d45c3c0f5ceeeea758afeec29b54817582dd93684808a5aa94d   (both)
```

The snapshot is byte-identical to HEAD and the page is somebody else's. Note
this is a *live* hazard, not a hypothetical: a `just deploy` run from any
worktree under `.worktrees/` would repaint the dashboard deployed from the
main checkout.

## Why the staleness fixes do not cover it

#397's follow-up made `serving_report`, `deployed.report` and
`dev/deploy_state.stale_identity_paths` compare the client as well as
`watch.py`. That closes "a client-only commit is invisible". It does **not**
close this: those checks compare the deploy dir's `client/` against *this*
repo's HEAD, so after a foreign deploy they correctly report the target as
stale — but only once someone looks, and the foreign content is already being
served. The two issues are the same wound from opposite sides:
`snapshot_matches_head` is a strictly weaker claim than "the page is right"
for as long as the page's files are not per-target.

Secondary, same root: `--ship-siblings` runs at justfile:416, four steps
before the `mv` at :451. A refusal at `--assert-importable`, `--stop-deployed`
or `--wait-port-free` leaves **new client assets beside the old snapshot**.
The running server is unaffected (assets are read at import), but the next
manual restart boots a mixture.

## Fix options

1. **Per-snapshot sibling directory** — `$dir/<basename>/watch.py` plus
   `$dir/<basename>/client/…`, so `sys.path[0]` and `CLIENT_DIR` both land in
   the target's own directory. Cleanest; changes the snapshot path, so
   `deployed.snapshot_for`, `dev/deploy_state`'s `snap` construction and the
   justfile must move together, and it needs a `Migration:` trailer — an
   existing deployment reports `never deployed` until redeployed.
2. **Namespaced siblings only** — keep the snapshot path, ship to
   `$dir/<basename>-siblings/` and put that on `sys.path`. Smaller migration,
   but `CLIENT_DIR` resolves from `__file__`, so the client would need its own
   resolution rule — that is the thing #397 deliberately kept simple.
3. **Stage-and-swap** — ship into a per-deploy temp dir and rename into place
   as the last step. Fixes the partial-failure window (secondary, above) but
   not the cross-target sharing.

Option 1 is the recommendation.

## Why it was not fixed here

The deploy path has taken his dashboard down twice (#425, #480). Changing the
deployed layout is a migration with its own red-proof and its own deploy
rehearsal, and #397's rule — one commit, so the extraction cannot half-land —
argues against carrying it in the same change. Filed instead, with the
reproduction above, so it is picked up as its own increment rather than
inherited silently.

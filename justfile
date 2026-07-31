# ud-dreamwork — common tasks

# the verification every increment runs (there is no CI; this is the net).
# Three parts: pytest cannot see rendered structure, the guards cannot see
# Python, and neither reads the loop's OWN files. A change that passes one and
# fails another is still broken. The browser half is intentionally
# serial; run it on a reasonably idle machine. Its motion checks sample rAF
# geometry and heavy contention can produce honest “not enough frames” reds.
test: pytest lint guards

# the Python half — asserts on generated source, not on what renders
pytest:
    # #666 — concurrent-test advisory before the suite. Advisory only: it gates
    # nothing, exits 0, and the leading `-` means a crash in the helper never
    # blocks a lane's verification (the advisory must never become a gate).
    -python3 dev/concurrent_tests.py
    python3 -m pytest -q

# this target's own `.dreamwork/` files, read through the REAL parsers — so a
# clean pass means the dashboard can actually see what the loop wrote, rather
# than that the files look plausible.
lint:
    python3 lint.py

# #653 (P1 of #630) — rebuild client/dist from client/*.js.
#
# DEV-TIME ONLY. `client/dist/` is committed, so serving and deploying never
# need node: `just deploy` ships committed state (below) and watch.py imports
# nothing outside the stdlib. Only CHANGING what the build emits needs this.
#
# Run it after editing anything under `client/`, or `python3 lint.py` goes
# ERROR and names the file that is unbuilt. A machine without node can still
# serve, deploy, edit Python and edit the builders — it just cannot clear that
# red, and the red says so.
#
# `npm ci` (not `install`) so the toolchain is the pinned one in
# dev/build/package-lock.json; node_modules is gitignored, the way every other
# node dependency in this repo is.
#
# #695 — reinstall when the INSTALLED TREE no longer matches the lockfile, not
# when a single binary happens to be missing. The old presence test
# (`[ -x .bin/esbuild ]`) saw esbuild and skipped `npm ci` when #630 added
# react/react-dom, so the build silently failed on every worktree whose
# node_modules predated the change. A stamp records the lockfile's sha256 and a
# build compares it: a no-op is a hash compare (~3ms), not `npm ci`'s
# delete-and-recreate (~418ms warm, and it churns node_modules every time — the
# trap that gets a guard deleted within a day). The stamp lives INSIDE
# node_modules so deleting the install deletes the stamp, which is the
# reinstall trigger; a stamp that survived its install's deletion would be the
# false-green. package.json/lockfile divergence is left to `npm ci` itself,
# which errors loudly on the same path.
build-client:
    #!/usr/bin/env bash
    set -euo pipefail
    stamp=dev/build/node_modules/.lock-stamp
    want=$(sha256sum dev/build/package-lock.json | cut -d' ' -f1)
    if [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$want" ]; then
        (cd dev/build && npm ci --no-audit --no-fund)
        echo "$want" > "$stamp"
    fi
    python3 dev/build_client.py

# the derived halves of status.json, recomputed from the ledger and from live
# `ccc @` processes rather than from a coordinator's memory. `lint.py` reports
# the queue drift; this fixes it, and also catches `current_task_ids` still
# naming a lane that has exited — which lint cannot see and which renders.
# `--check` exits 1 without writing, for use before a commit.
status-sync *args:
    python3 status_sync.py {{args}}

# the structural half — real browser, real server, real DOM. Only scripts
# that exit non-zero belong here; the rest of dev/capture/ prints for a
# human and gates nothing. A guard joins this list when its feature lands.
#
# NO GUARD EVER RUNS AGAINST THIS REPO — every one works on a copy or on a
# fixture of its own. Two things follow, and both were #117:
#   - content is frozen, so a red light means the code broke rather than
#     that the loop folded the last awaiting-fold question overnight
#   - guards may WRITE (POST /answer, /comment) without touching the real
#     questions.md, which is what kept the most valuable ones ungated
#
# There are now THREE shapes, and this comment lists all three because a
# comment that is 90% true is worse than none — it gets believed. #148 is
# filed for collapsing them onto one runner; until then, read this:
#   $GUARDS      dev/capture/*.mjs (OUT, PORT). One shared watch.py on
#                {{port}}, its target reset from dev/capture/fixture before
#                EACH one — several of them answer questions and leave notes,
#                so without the reset the first writer eats what the next
#                needs and the red light is really a run-order bug.
#   health       also dev/capture/ and also (OUT, PORT), but it needs several
#                targets in states one shared fixture cannot hold at once (no
#                file / unparseable / seeded), so it builds them under OUT and
#                runs its own servers from the given port upward.
#   identity     same shape again, and (OUT) only: it drives a SEQUENCE of
#                loop states through one live page — the title has to keep
#                changing while nobody navigates, so a guard that reloaded
#                between states would prove the wrong thing.
#   dashboard    same shape as health and for the same reason, plus one worth
#                knowing: THE SHARED FIXTURE IS NOT A GIT REPO, so `git_tail`
#                returns [] and the commits panel is empty on the server
#                above. It inits a repo with commits at known ages (the only
#                way to reach the 100-day boundary at all) and takes an
#                EPHEMERAL port rather than the one it is handed.
#   motion       same shape as dashboard and for the same reason — it drives
#                the commits panel, so it needs a git target of its own. It
#                also TYPES into a card between renders, which is why it
#                cannot share a page with anything that navigates.
#   morph        same shape again, for a third reason: it runs four phases
#                (answer/note x normal/reduced) and each needs a PRISTINE
#                questions.md, because answering the first open question
#                changes which card the next phase would pick. Sharing the
#                server would make it order-dependent, and an order-dependent
#                guard reports run order as a bug in the page.
#   morphhold    morph's shape again (own server, pristine target per
#                phase), and it DRIVES `tick()` directly plus POSTs /command
#                to force the mtime — the 2s poll's phase is luck, and a
#                hold measurement that depends on luck is not one.
#   prominence   ordinary (OUT, PORT) on the shared server, but it visits BOTH
#                routes in one page: #169's expand idiom belongs to every
#                disclosure, and the four that exist live on two views.
#   reviewsplit  ordinary (OUT, PORT), and it WRITES one /command to force a
#                tick. It picks the LONGEST open question in the fixture on
#                purpose: every check about scrolling the question is vacuous
#                against one that fits its column, so the choice is derived
#                rather than a literal that today's fixture happens to satisfy
#                (#197's lesson). Its motion assertions are frame-rate-free
#                where they can be — the count of frames strictly between the
#                ends, not only the count of distinct positions.
#   qsec         ordinary (OUT, PORT), and it WRITES — it POSTs /command to
#                make the mtime change so it can drive a live tick over a
#                ghost. That only touches watch-events.log, so it changes
#                nothing rendered, but it is why the per-guard reset matters.
#   submitlog    ordinary (OUT, PORT), and the heaviest writer here: it
#                answers a question for real and forces two rejected writes,
#                so it changes questions.md AND appends to submissions.log.
#                Reads both back over /filedata rather than off disk — it is
#                handed a port, not a target.
#   indicator    ordinary (OUT, PORT). Its window is deliberately SHORT and
#                that is load-bearing: #198's wrongness does not heal, it is
#                laundered by the next view re-render, so a relaxed window
#                would pass over a bug he can see. It proves that laundering
#                path exists rather than assuming it.
#   draft        ordinary (OUT, PORT), and it RELOADS the page repeatedly on
#                purpose — closing and reopening the composer passed before
#                #163 existed, so only a real reload tests anything. Writes
#                one command event per run via a successful send.
#   subslog      ordinary (OUT, PORT). WRITES: it answers a question for real
#                and forces a rejected note, and it stubs `window.fetch` to
#                make one submission unreachable. Reads the client's log back
#                through the page's own accessor, never out of IndexedDB
#                behind the feature.
#   history      ordinary (OUT, PORT). WRITES one real command and forces one
#                unreachable send, then reads them back out of the composer's
#                history panel. Checks its subject EXISTS before driving it —
#                without that, a build without the feature costs a 30s
#                Playwright timeout and reports "the guard threw".
#   serving      OWN TARGET + OWN EPHEMERAL PORT (#140). The state under test
#                is a relationship between the RUNNING BYTES and a repo's
#                history of watch.py, so it evolves one repo through all four
#                answers in order. The shared fixture is not a repository, so
#                against it this could only ever reach "cannot tell".
#   gitrow       OWN TARGET + OWN EPHEMERAL PORT (#166), same reason as
#                dashboard: the shared fixture is not a repository, so the
#                commits panel is empty there and every check would pass
#                against nothing. Plants bodies and file lists it can name.
#   burndown     OWN TARGET + OWN EPHEMERAL PORT (#142), and it plants a
#                LEDGER history, then commits into it while the page is open
#                so the tick brings a real data change. Two of its checks are
#                about the premise the panel's motion rests on (the panel
#                height never changes) rather than about the motion itself.
#   bdinput      OWN TARGET + OWN EPHEMERAL PORT (#523/#524): planted long
#                ledger so the #499 limit control is present; asserts focus/
#                caret/typed-value survival across a real setContent swap,
#                −/+ step+clamp, hold-to-repeat, and hold across a mid-hold
#                tick (module-level interval composition with #523).
#   provenance   OWN TARGETS + OWN EPHEMERAL PORTS (#217), same shape as
#                burndown and for the same reason: the datum is a property
#                of a repository's ledger HISTORY. Plants a human filing, a
#                loop filing, an unmarked entry marked human LATER (first
#                sight is final, so it must stay unknown), a combined entry
#                and a deletion, plus a shallow clone for the
#                incomplete-coverage copy. Its load-bearing count check was
#                shown red against the unknown-counted-as-loop sabotage.
#   fileimg      #336, and it runs against the SHARED fixture: the datum is a
#                binary file served through /filedata, which used to arrive as
#                U+FFFD soup in a <pre>. Unregistered from the day it was
#                written until #377's check found it.
#   qfade        #326, a PIXEL guard on purpose — the claim is that the TEXT
#                fades rather than being covered by a painted band, and the
#                middle of its three claims cannot be written against the DOM
#                at all. Also unregistered from the day it was written.
#   coexist      #630 P2, and the only guard here whose subject is NOT on the
#                served page: it injects the committed client/dist/native.js
#                as a second classic script, which is the position P3 will
#                serve it from. P2 mounts nothing, so the page is byte-
#                identical to master's and this is the only way to reach the
#                runtime at all. It measures TWO different claims and must not
#                be read as one: with #view's ownership respected a real tick
#                reaches a mounted component and its React state survives; with
#                it violated, morphdom deletes the root and registry.verify()
#                REPORTS that. Coexistence is a partition, not a truce.
#   dreamfade    ordinary (OUT, PORT) on the shared server, and it is a PER-FRAME
#                guard because the claim is an ORDER, not an end state (#277):
#                the ghost must dissolve in place BEFORE it travels, and both
#                end states are identical either way. It samples the ghost's
#                computed filter/opacity/transform each frame and asserts
#                .pregone appears, appears BEFORE .gone, that blur rises past
#                5px inside the dissolve, and that blur never DECREASES during
#                departure — the last one exists because the first version of
#                this let the corpse un-blur by 2px as it left, which a
#                `blur >= 5px` assertion passes over.
#   artifactwrap ordinary (OUT, PORT) on the shared server, and it BUILDS its
#                fixture through review_artifact.py so the real template and the
#                real builder are what get measured — the bug it guards (#347)
#                does not reproduce when the labels are rewritten through the
#                DOM, because the scaffolding stands in front of it. Its
#                instrument is a `Range` over each WORD, not
#                `getClientRects()` on the box: `.topactions a` is
#                `inline-flex`, so the box stays one rect while the text wraps
#                inside it, and the box-level check reported 1 for four
#                visibly-broken labels.
#   filehead     OWN TARGET + OWN EPHEMERAL PORT (#284), gitrow-shaped: the
#                datum is a FILE at a chosen path, and the shared fixture has
#                no path long enough to make the heading compete with the
#                document it names. Plants a deep path, Tabs to the copy
#                button and reads the clipboard back, and derives its overflow
#                condition at runtime (the same text measured at
#                `white-space:pre` against the column it must wrap inside)
#                rather than pinning a width that today's fixture happens to
#                exceed.
#   fileview     OWN TARGET + OWN EPHEMERAL PORT (#252), same reason: it needs
#                a markdown file whose exact bytes it can compare against the
#                rendered Source pane, and a `<script>` plus an `onerror`
#                attribute it can prove are inert AND still visible as text.
#                Loads `?view=source` directly rather than clicking, because a
#                switch that works only on click is the bug a click test
#                cannot see.
#   hub contract dreamhub's, in dev/hub/, and (OUT) only — their input is N
#                targets plus a registry, and they pick ephemeral ports, so
#                they need no plumbing here and cannot fight the server above.
#   qlinkpip     ordinary (OUT, PORT) on the shared server (#506). The fixture
#                plants BOTH a known-internal path (`.dreamwork/lessons.md`)
#                and an unknown path (`nosuch/vanished.md`) in one open
#                question body so the guard can DERIVE both link kinds from
#                data.linkable_paths at runtime — a green without that
#                precondition is vacuous. Production line: pipBtn injection
#                inside linkify when the closed set matches.
#   mdquote      ordinary (OUT, PORT) on the shared server (#521+#522). Plants
#                a multi-line `>` quote, known + relative + unknown markdown
#                links, and a fence holding `>` into the target copy; derives
#                quote line count at runtime. Production lines: mdBlocks
#                quote kind, mdRender blockquote branch, linkifyMd promote
#                and literal branches, fence-before-quote order.
#   mdtable      ordinary (OUT, PORT) on the shared server (#525). Plants a
#                GFM pipe table (header+delimiter+body with an inline md link
#                in a cell), a fence holding pipe-looking lines, and a
#                malformed ragged pair; derives table/body row counts at
#                runtime. Production lines: mdBlocks table kind, fence-before-
#                pipes order, mdRender cell inline pipeline (linkifyMd).
#   gutter       ordinary (OUT, PORT) on the shared server (#597), with ONE
#                difference that is the point of the file: it is the only
#                guard here launched `ignoreDefaultArgs: ['--hide-scrollbars']`.
#                Playwright hides scrollbars in headless by default, so every
#                OTHER guard in this directory is blind to any layout effect a
#                scrollbar causes — which is why a 5px column snap on every
#                nav between a scrolling and a non-scrolling route survived to
#                a manual audit. Its first check refuses to grade until it has
#                confirmed the scrollbar consumes width in the browser actually
#                running. Production line: `html { scrollbar-gutter:stable }`.
#   hfit         ordinary (OUT, PORT) on the shared server (#312, #595). Plants
#                one markdown doc referencing a long path the fixture already
#                ships, so /file has a rendered pane to measure with no
#                closed-set readiness race. #595's lesson lives here: it passed
#                while the page was broken, because its subjects include two
#                crumbs whose LENGTH comes from data and the fixture's values
#                were short. It now asserts that length, and injects 160 chars
#                into every unbounded slot. Production lines: `.wrapany` at the
#                crumbsFor build sites, `.mdfile > code` in the wrap exception.
guards port="39899":
    #!/usr/bin/env bash
    set -uo pipefail
    DEFAULT_GUARDS="headertravel headcrumb reflow qacard docktarget noteprop oneinput regroup regroupdraft popbg typing wisp states dismiss confirmation thread status health pushhealth dashboard identity projtitle motion morph morphhold prominence qsec submitlog indicator draft reviewdraft subslog history plugcmd qorder revieworder reviewsplit serving gitrow burndown provenance answers hfit filehead fileview fileimg filehl qfade artifactwrap dreamfade markrail devoverlay autogrow dissolve burndownmock bdhover reviewask reviews5 staleremedy rejectwrite posture summaryjson qsignal qfocus qroll research restcollapse qlinkpip mdquote bdinput mdtable selectkeep corpse remindbtn note82 pip83 indtrace escattr chatsurface qgroup resize posturerecuse qdual gutter coexist"
    GUARDS=${DREAMWORK_GUARDS:-$DEFAULT_GUARDS}
    # `-` rather than `:-` lets a focused run deliberately set this empty.
    HUB_GUARDS=${DREAMWORK_HUB_GUARDS-"hub contract"}
    GUARD_TIMEOUT=${DREAMWORK_GUARD_TIMEOUT:-120}
    OUT=$(mktemp -d)
    trap 'rm -rf "$OUT"' EXIT
    cp -r dev/capture/fixture "$OUT/target"
    # #203 pre-flight: NAME the holder before we bind, instead of only saying
    # the port is busy after the fact. Our python exits "address in use" if the
    # port is taken, and the readiness probe below would then grade whatever
    # ALREADY holds the port — exactly how a stale fixture server answered a
    # probe and reported feature bugs for 20 minutes. ss -tlnp gives the pid
    # for same-user listeners; we read the full cmdline + cwd from /proc so the
    # operator knows exactly what to go look at (and `just reap` cleans it up).
    _holder_line=$(ss -tlnp 2>/dev/null | grep -E ":{{port}}\b" | grep -oE 'pid=[0-9]+' | head -1)
    if [ -n "$_holder_line" ]; then
      _hp=${_holder_line#pid=}
      echo "guards: :{{port}} already held by pid $_hp:"
      echo "        $(tr '\0' ' ' < /proc/$_hp/cmdline 2>/dev/null)"
      echo "        cwd: $(readlink /proc/$_hp/cwd 2>/dev/null)"
      echo "        (a stale server on a guard port is the #203 trap — inspect/clean: just reap)"
      exit 1
    fi
    python3 watch.py --target "$OUT/target" --port {{port}} >"$OUT/server.log" 2>&1 &
    SRV=$!
    trap 'kill $SRV 2>/dev/null; rm -rf "$OUT"' EXIT
    for _ in $(seq 1 40); do
      curl -sf "http://127.0.0.1:{{port}}/" >/dev/null && break
      sleep 0.25
    done
    if ! curl -sf "http://127.0.0.1:{{port}}/" >/dev/null; then
      echo "guards: server never came up on {{port}} — see $OUT/server.log"
      exit 1
    fi
    # ...and it must be OUR server. A readiness probe that accepts any answer
    # grades whatever already holds the port: a `just watch` left running on
    # this port serves the REAL repo, our python exits "address in use", and
    # ten guards then assert fixture facts about the live target and come back
    # red with messages about a fixture that was never being read. That is
    # exactly what happened on 2026-07-25 and it cost a 20-minute run. Only
    # the guards that start their OWN server were immune, so the check belongs
    # here rather than in each of the ten.
    served=$(curl -sf "http://127.0.0.1:{{port}}/data.json" \
             | python3 -c 'import json,sys; print(json.load(sys.stdin).get("target",""))' \
             2>/dev/null)
    if [ "$served" != "$OUT/target" ]; then
      echo "guards: :{{port}} is serving ${served:-<no answer>}, not $OUT/target"
      echo "        something else already holds the port — see $OUT/server.log"
      exit 1
    fi
    fail=0
    # LOAD IS RECORDED PER GUARD, and it is not decoration (#428). Roughly a
    # dozen guards assert that a transition HAPPENED by sampling frames, and they
    # fail intermittently — always from that subset, never outside it. Four runs
    # went looking for the cause by trying to run the suite on an "idle" machine,
    # and all four failed for the same reason: this host is a shared workstation
    # running several agent sessions, so its load average sits near 30 on 16
    # cores whether or not this loop has a lane out. There is no idle arm to
    # measure against, and "no lane of mine is running" was never the same claim
    # as "the machine is idle" — treating them as one is what wasted the four
    # runs. So stop trying to isolate the variable and instrument it instead:
    # every guard's load travels with its verdict, and the correlation
    # accumulates over ordinary use with no reserved window at all.
    _loadavg() { cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo '?'; }
    _cores=$(nproc 2>/dev/null || echo '?')
    echo "  (load $( _loadavg ) on $_cores cores at suite start)"
    for g in $GUARDS; do
      # Reset the target before EVERY guard — see the header. The server
      # re-reads from disk per request, so no restart is needed.
      rm -rf "$OUT/target" && cp -r dev/capture/fixture "$OUT/target"
      _l0=$(_loadavg)
      if timeout --kill-after=5s "$GUARD_TIMEOUT" \
          node "dev/capture/$g.mjs" "$OUT/$g" {{port}} \
          >"$OUT/$g.log" 2>&1; then
        echo "  PASS $g"
      else
        code=$?
        fail=1
        # The failing lines carry load because that is the whole point: a
        # frame-sampler red at load 30 and one at load 3 are different findings,
        # and previously the output could not tell them apart.
        echo "  FAIL $g${code:+ (exit $code)} [load $_l0->$(_loadavg) / $_cores cores]"
        grep -E "^(FAIL|Error)" "$OUT/$g.log" | head -5 | sed 's/^/        /'
      fi
    done
    # the hub's own guards (#96, #134). They start their own servers — their
    # input is N targets plus a registry, not one target dir — and pick
    # ephemeral ports, so they need no plumbing here and cannot fight the
    # watch server above for a port. Until these ran, a green `just test` did
    # not cover the hub at all, which is #117 verbatim one directory over.
    for h in $HUB_GUARDS; do
      if timeout --kill-after=5s "$GUARD_TIMEOUT" \
          node "dev/hub/$h.mjs" "$OUT/$h" >"$OUT/$h.log" 2>&1; then
        echo "  PASS $h"
      else
        code=$?
        fail=1
        echo "  FAIL $h${code:+ (exit $code)}"
        grep -E "^(FAIL|Error)" "$OUT/$h.log" | head -5 | sed 's/^/        /'
      fi
    done
    # A missing browser is a missing verifier, not a pass. Say so loudly.
    if [ "$fail" -ne 0 ] && grep -q "Cannot find module" "$OUT"/*.log 2>/dev/null; then
      echo "guards: playwright not resolvable — the structural half did NOT run"
    fi
    # #471 — registration is not execution. The loop above printed PASS/FAIL
    # per guard, but a guard that died before its first assertion (the #471
    # shape: serveVerified refused the shared port, the guard threw an Error:
    # and ran zero ok() checks) still got a FAIL line and GATED NOTHING for
    # 3.5h while the suite reported "N registered". So compare the guards
    # that ran AND judged against the requested set and fail when they
    # disagree. "Judged" = a genuine PASS/FAIL verdict (NOT the crash sentinel
    # "the guard threw before finishing its checks", which marks did-not-judge);
    # every guard shares that output contract (report.mjs users and the guards
    # that inline the same idiom). See lint.ran_and_judged / `lint.py
    # guard-execution`. This cannot be skipped inside a run: it feeds `fail`.
    python3 lint.py guard-execution "$OUT" $GUARDS || fail=1
    exit $fail

# #330 — deliberately refresh the committed provenance evidence plates.
# `just guards` runs provenance.mjs in its clean mode: it writes captures to
# its OUT tempdir and never touches the committed path, so verifying the tree
# no longer dirties it. The four PNGs under
# .dreamwork/review/evidence/provenance-coverage-217/ are #217's evidence of
# record (committed by `evidence(#217)`), so they stay in the repo — but they
# are refreshed by a deliberate act, not by every guard run. This recipe is
# that act: it sets DREAMWORK_PROVENANCE_EVIDENCE=1 so the guard writes both
# its OUT and the committed path, then stages the result for review.
# Run it when the provenance panel's visual design changes and the plates
# should reflect the new render.
provenance-evidence:
    #!/usr/bin/env bash
    set -euo pipefail
    OUT=$(mktemp -d)
    trap 'rm -rf "$OUT"' EXIT
    echo "refreshing committed provenance evidence (provenance.mjs → OUT + committed path)…"
    DREAMWORK_PROVENANCE_EVIDENCE=1 node dev/capture/provenance.mjs "$OUT" >/dev/null
    git add .dreamwork/review/evidence/provenance-coverage-217/
    echo "staged refreshed plates:"
    git status --porcelain .dreamwork/review/evidence/provenance-coverage-217/
    echo "review with: git diff --cached .dreamwork/review/evidence/provenance-coverage-217/"

# #203 — find (and with explicit flags, reap) orphaned watch.py guard servers.
# Dry-run by default: prints each server's classification and kills nothing.
#   - rule2 (dead-lane): cwd deleted -> the lane that started it is GONE. This
#     is the ONLY class that may be killed, and only with --kill plus a target.
#   - rule1 (stale):     old elapsed -> reported for a human, never killed.
# Killing needs a second flag: --pid PID (one) or --all-dead --yes (sweep).
# The recipe is a thin pass-through so the classifier and its safety live in
# ONE place (dev/reaper.py) and the test pins them there.
#
# examples:
#   just reap                         # dry-run, all watch.py servers
#   just reap --range 39880-39899     # dry-run, focus a port range
#   just reap --kill --pid 12345      # reap one dead-lane pid
#   just reap --kill --all-dead       # REFUSES; prints targets + never-kill env
#   just reap --kill --all-dead --yes # reap every dead-lane (rule2) server
reap *ARGS:
    python3 dev/reaper.py {{ARGS}}

# edit-and-see, for whoever is CHANGING the page. Deliberately not the
# persisted port: that one belongs to the deployed instance the human is
# reading, and two servers wanting it is a fight nobody wins. Pass a port
# if you are sharing the machine with another dreamer.
watch port="39890":
    python3 watch.py --target . --port {{port}} --autoreload --dev

# deploy the dashboard the HUMAN watches. Committed state only, never the
# working tree — a dreamer's half-finished edit must not reach him. Runs
# from a snapshot outside the repo so an agent editing watch.py cannot
# change what is already serving, and detached so it outlives the session
# that started it. Open tabs reload themselves on the generation bump.
deploy rev="HEAD":
    #!/usr/bin/env bash
    set -euo pipefail
    port=$(cat .dreamwork/watch-port)
    dir=~/.cache/dreamwork/deployed
    mkdir -p "$dir"
    snap="$dir/$(basename "$PWD")-watch.py"
    # #425 — resolve the link BEFORE snapshotting, then PROVE the snapshot is
    # the server BEFORE touching the live process. Git stores a symlink as a
    # blob whose content is the TARGET PATH, so once watch.py becomes a symlink
    # (the #368 plan: watch.py -> deprecated/watch.py), `git show {{rev}}:watch.py`
    # emits the 19-byte string `deprecated/watch.py`, the old `ast.parse` guard
    # accepted it (it parses as `deprecated / watch.py`), a bad stop took the
    # good server down, and the garbage snapshot died on import — leaving his
    # dashboard dark. Both calls below live in dev/deploy_state.py and are the
    # SAME resolver/guard the state report uses, so the recipe and deploy_state
    # agree by construction. The guard PRECEDES the stop on purpose: a snapshot
    # that is not the server is refused with the dashboard still up.
    python3 dev/deploy_state.py --resolve-snapshot {{rev}} > "$snap.tmp"
    python3 dev/deploy_state.py --assert-server "$snap.tmp" \
      || { rm -f "$snap.tmp"; echo "deploy refused: snapshot is not the server (broken link or corrupt {{rev}}) — his dashboard was left running"; exit 1; }
    # #480 — the snapshot is ONE file, but the server is not: Python puts the
    # snapshot's DIRECTORY on sys.path, not the repo, so watch.py's repo-local
    # imports (user_events/, ledger_parse.py, and lint.py — imported lazily
    # at page build — at HEAD; derived transitively from the snapshot's own
    # imports, never a hardcoded list) must live
    # beside it or the new server ImportErrors on boot AFTER the old one has
    # stopped. Ship the siblings, then PROVE the staged snapshot imports in
    # exactly the environment it will boot in. Both guards PRECEDE the stop,
    # like --assert-server: a snapshot that cannot boot is refused with his
    # dashboard still up (the #425 contract, extended from "is the server"
    # to "its imports resolve").
    python3 dev/deploy_state.py --ship-siblings {{rev}} --dest "$dir" \
      || { rm -f "$snap.tmp"; echo "deploy refused: sibling modules could not be staged beside the snapshot — his dashboard was left running"; exit 1; }
    python3 dev/deploy_state.py --assert-importable "$snap.tmp" \
      || { rm -f "$snap.tmp"; echo "deploy refused: the snapshot's imports do not resolve from the deploy dir — his dashboard was left running"; exit 1; }
    # #520 — STOP the old server BEFORE shipping the snapshot (`mv`). The old
    # order ran `mv $snap.tmp $snap` before --stop-deployed: against an
    # autoreloading occupant (the old --dev server was one) the `mv` overwrote
    # the file it watched, so autoreload os.execv'd the old process IN PLACE
    # (same pid, port flickered free via close-on-exec then rebound) — arming
    # the race the #508 identity checks then had to catch. The first
    # identity-verified deploy (2026-07-30 07:38) hit exactly this: stop
    # sampled the flicker, wait-port-free refused, a human step was needed.
    # The reorder is honest: --stop-deployed needs only the snap PATH
    # (argv_runs_snap compares realpaths, never shipped CONTENT), so the old
    # process — still running $snap with a matching argv — is correctly
    # identified and stopped. The #480 boot-proofs (ship-siblings +
    # assert-importable) stay BEFORE the stop: a snapshot that cannot boot is
    # still refused with the dashboard up; only the race-arming `mv` moved.
    # #431 — stop ONLY the process listening on $port whose argv is $snap.
    # Never `pkill -f <basename>`: that matches any process whose command line
    # merely *mentions* the pattern (the deploy shell, a pgrep, a comment) and
    # killed a coordinator shell with exit 144. Identify by the listening
    # socket, verify via /proc/<pid>/cmdline, signal that pid alone.
    python3 dev/deploy_state.py --stop-deployed --port "$port" --snap "$snap" \
      || { rm -f "$snap.tmp"; echo "deploy refused: could not identify the process to stop on :$port — left it alone"; exit 1; }
    # #508/#520 — wait for the port to be REALLY free before shipping + starting,
    # and confirm it STAYS free. #520 moved the `mv` after this wait, so this
    # recipe no longer arms the autoreload execv flicker itself; but the settle
    # is still belt-and-braces for the SIGTERM port-release window — a single
    # `listening_pid is None` sample is not proof the bind is gone.
    python3 dev/deploy_state.py --wait-port-free --port "$port" \
      || { rm -f "$snap.tmp"; echo "deploy refused: :$port never freed after stop (the old process re-exec'd/respawned) — his dashboard was left running, the new server was not started"; exit 1; }
    # #520 — SHIP the snapshot now that the old server is dead. Before #520 the
    # `mv` ran before the stop and armed the autoreload execv race above; now it
    # overwrites a path no live process watches.
    mv "$snap.tmp" "$snap"
    # #508 — the deployed server no longer runs with --dev: autoreload (implied
    # by --dev) was the mechanism that re-exec'd the old process in place on
    # this recipe's own `mv`, creating the residual port-holder the race needs.
    # The deployed snapshot is frozen between deploys and this recipe restarts
    # it on every deploy, so autoreload serves no purpose here — the GENERATION
    # still bumps on the fresh process, so open tabs reload on redeploy as
    # before. (--dev's only other effect is a dev fps counter, which the
    # dashboard the human watches does not need.)
    nohup python3 "$snap" --target "$PWD" >"$dir/serve.log" 2>&1 &
    newpid=$!
    # #508 — success is TRUE BY CONSTRUCTION: the listener on :$port must be
    # $newpid (the process this recipe just spawned) running $snap. The old
    # curl-liveness readiness graded whatever answered — the re-exec'd old
    # process, whose argv matches the new snap — and printed a false
    # 'deployed'. This verifies IDENTITY (pid + argv), so a foreign/respawned
    # holder or a new server that died on bind fails LOUDLY instead.
    python3 dev/deploy_state.py --verify-deployed --port "$port" --snap "$snap" --expect-pid "$newpid" \
      || { echo "deploy failed: the new server (pid $newpid) did not take :$port — the old process may still hold it, or the new server died on bind/boot. See $dir/serve.log"; exit 1; }
    echo "deployed {{rev}} ($(git rev-parse --short {{rev}})) on :$port (pid $newpid, identity-verified)"

# Does a watch.py change that touches PRESENTATION have a styleguide entry
# near it? Prints violations; silence means the check found nothing to complain
# about. The logic lives in dev/styleguide_audit.py — read its docstring for
# the full rationale; this comment says only what a caller needs to know.
#
# READ THIS BEFORE TRUSTING IT — what it proves is narrower than its name.
# It measures ADJACENCY (did watch-design.md change around here), not
# COVERAGE (is the behaviour actually written down). A whitespace edit to
# watch-design.md satisfies it. A standing MISS trains everyone to ignore the
# audit, which is the same failure family as a guard that only reddens under
# load (#203) — so the FILTER matters as much as the rule.
#
# #314 — the filter is on the DIFF, not the filename. watch.py is one file
# holding the HTTP server, the git and ledger parsers, AND the whole UI (#124
# is the split). "Did this commit touch watch.py?" could not tell a stylesheet
# change from a regex fix, so it accrued failures for parser/server work it
# was never about (06eacad, 1d089ad, db1a1bc, e51da7e) until "ignore me" was
# the only lesson a standing MISS could teach. The UI lives in line-bounded
# module constants (STYLE, APP_BODY, the *_JS blocks) whose contents are
# served verbatim to the browser; everything else is server/parser/helper. So
# "did this commit change presentation?" is mechanically answerable: does the
# commit's diff touch a line inside one of those constants? The constant
# boundaries are resolved AT THE COMMIT BEING AUDITED (git show <sha>:watch.py),
# never at HEAD — line numbers move, and judging last week's commit with
# today's line numbers is the "literal with an expiry date" trap. A non-UI
# commit passes by NOT TOUCHING a `client/` asset (or, before #397 extracted
# them, a UI constant in watch.py), not by remembering a trailer.
# `Styleguide: n/a` survives only as a narrow escape hatch for a genuine
# judgement case the diff filter calls wrong (reported as EXEMPT, auditable).
#
# Deliberately NOT gated in `just test`: making adjacency mandatory would be
# worse than the status quo. It is a prompt to look, not a proof (#155).
#
# Range defaults to 1d089ad..HEAD — retained from #313 for continuity. The
# pre-baseline burst (d1df255..1d089ad) is reported as a COUNT only and is NOT
# back-filled: reconstructed entries written from diffs by someone who did not
# make the change are the fabrication this check exists to prevent (#313).
# Under #314's diff filter the count is recomputed (parser/server false
# positives drop out; real UI misses remain), so it differs from #313's "11".
# Pass a wider range to list pre-baseline misses in full.
audit-styleguide range="1d089ad..HEAD" window="3":
    python3 dev/styleguide_audit.py {{range}} --window {{window}}

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
    python3 -m pytest -q

# this target's own `.dreamwork/` files, read through the REAL parsers — so a
# clean pass means the dashboard can actually see what the loop wrote, rather
# than that the files look plausible.
lint:
    python3 lint.py

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
#   provenance   OWN TARGETS + OWN EPHEMERAL PORTS (#217), same shape as
#                burndown and for the same reason: the datum is a property
#                of a repository's ledger HISTORY. Plants a human filing, a
#                loop filing, an unmarked entry marked human LATER (first
#                sight is final, so it must stay unknown), a combined entry
#                and a deletion, plus a shallow clone for the
#                incomplete-coverage copy. Its load-bearing count check was
#                shown red against the unknown-counted-as-loop sabotage.
#   hub contract dreamhub's, in dev/hub/, and (OUT) only — their input is N
#                targets plus a registry, and they pick ephemeral ports, so
#                they need no plumbing here and cannot fight the server above.
guards port="39899":
    #!/usr/bin/env bash
    set -uo pipefail
    DEFAULT_GUARDS="headertravel reflow qacard docktarget noteprop oneinput regroup popbg typing wisp states dismiss confirmation thread status health dashboard identity motion morph morphhold prominence qsec submitlog indicator draft subslog history plugcmd qorder revieworder reviewsplit serving gitrow burndown provenance answers runmode hfit"
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
    for g in $GUARDS; do
      # Reset the target before EVERY guard — see the header. The server
      # re-reads from disk per request, so no restart is needed.
      rm -rf "$OUT/target" && cp -r dev/capture/fixture "$OUT/target"
      if timeout --kill-after=5s "$GUARD_TIMEOUT" \
          node "dev/capture/$g.mjs" "$OUT/$g" {{port}} \
          >"$OUT/$g.log" 2>&1; then
        echo "  PASS $g"
      else
        code=$?
        fail=1
        echo "  FAIL $g${code:+ (exit $code)}"
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
    exit $fail

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
    git show {{rev}}:watch.py > "$snap"
    python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$snap"
    pkill -f "$(basename "$snap")" 2>/dev/null || true
    sleep 1
    nohup python3 "$snap" --target "$PWD" --dev >"$dir/serve.log" 2>&1 &
    for _ in $(seq 1 20); do
      curl -sf "http://127.0.0.1:$port/" >/dev/null && break
      sleep 0.25
    done
    curl -sf -o /dev/null "http://127.0.0.1:$port/" \
      && echo "deployed {{rev}} ($(git rev-parse --short {{rev}})) on :$port" \
      || { echo "deploy failed — see $dir/serve.log"; exit 1; }

# Does a change to watch.py have a styleguide entry NEAR it? Prints
# violations; silence means the check found nothing to complain about.
#
# READ THIS BEFORE TRUSTING IT — what it proves is narrower than its name.
# It measures ADJACENCY (did watch-design.md change around here), not
# COVERAGE (is the behaviour actually written down). Three consequences,
# all observed on 2026-07-25:
#   - Touching both files passes whether or not the doc says anything about
#     the change. A whitespace edit to watch-design.md satisfies it. This is
#     the failure nobody notices, and it means 29 green commits proved only
#     that the files moved together.
#   - Documenting BEFORE the code — better practice than co-committing — was
#     flagged as a miss when the two landed 2 minutes apart in adjacent
#     commits. Hence the window below.
#   - watch.py is both the page and the server, so a writer-only fix looked
#     like an undocumented page change. FIXED by widening rather than by
#     waiting for #124: EITHER watch-design.md OR file-formats.md counts,
#     because watch.py changes are page changes OR server-contract changes
#     and each documents itself in its own styleguide. #199 was the case —
#     `log_submission` documented correctly in file-formats.md and reported
#     as a MISS — and a standing MISS trains everyone to ignore the audit,
#     which is the same failure family as a guard that only reddens under
#     load (#203).
#     RESIDUAL RISK, stated rather than discovered: a PAGE change documented
#     only in file-formats.md now passes wrongly. Accepted — the reviewer
#     reads the commit, and this only ever read adjacency.
# Deliberately NOT gated in `just test`: making adjacency mandatory would be
# worse than the status quo. It is a prompt to look, not a proof (#155).
#
# Range defaults to 1d089ad — the most recent commit that violated the rule
# (fix(#304), 2026-07-27). Everything after it obeys; the 11 misses before it
# (a 2-day burst, 2026-07-26..27) are NOT back-filled: reconstructed entries
# written from diffs by someone who did not make the change are the fabrication
# this check exists to prevent (#313). The baseline is derived from history
# (the last miss), not a round number; the convention held for ~378 commits
# after d1df255 (where watch-design.md became authoritative) before the burst.
# The recipe prints a runtime count of pre-baseline misses so the gaps stay
# visible; pass 'just audit-styleguide d1df255..HEAD' to list them in full.
audit-styleguide range="1d089ad..HEAD" window="3":
    #!/usr/bin/env bash
    set -euo pipefail
    mapfile -t all < <(git log --format=%h {{range}})
    miss=0; ok=0
    for i in "${!all[@]}"; do
      c="${all[$i]}"
      git show --stat --format= --name-only "$c" | grep -qx "watch.py" || continue
      # Look at this commit and {{window}} either side: a styleguide entry
      # written just before or just after its code still documents it.
      lo=$(( i - {{window}} )); [ "$lo" -lt 0 ] && lo=0
      hi=$(( i + {{window}} )); [ "$hi" -ge "${#all[@]}" ] && hi=$(( ${#all[@]} - 1 ))
      found=""
      for j in $(seq "$lo" "$hi"); do
        # either styleguide: the page's or the server contracts' (see header)
        if git show --stat --format= --name-only "${all[$j]}" \
             | grep -qxE "watch-design.md|file-formats.md"; then
          found="${all[$j]}"; break
        fi
      done
      if [ -n "$found" ]; then
        ok=$((ok+1))
      else
        miss=$((miss+1))
        echo "MISS $c $(git log -1 --format=%s "$c" | cut -c1-64)"
      fi
    done
    echo "watch.py commits: $ok with a styleguide entry (watch-design.md or file-formats.md) within {{window}}, $miss without"
    echo "(adjacency, not coverage — see the comment above this recipe)"
    # Pre-baseline visibility — the default range skips commits before
    # 1d089ad, but silently narrowing coverage is its own dishonesty
    # (CLAUDE.md: a check that bounds coverage must say what it is not
    # covering). The count is derived at runtime; a hardcoded literal would
    # carry today's truth silently into next week (.dreamwork/lessons.md).
    if git rev-parse --verify -q 1d089ad >/dev/null 2>&1 && \
       git rev-parse --verify -q d1df255 >/dev/null 2>&1; then
      mapfile -t pre < <(git log --format=%h d1df255..1d089ad)
      p_wp=0; p_miss=0
      for p_i in "${!pre[@]}"; do
        git show --stat --format= --name-only "${pre[$p_i]}" | grep -qx "watch.py" || continue
        p_wp=$((p_wp+1))
        p_lo=$(( p_i - {{window}} )); [ "$p_lo" -lt 0 ] && p_lo=0
        p_hi=$(( p_i + {{window}} )); [ "$p_hi" -ge "${#pre[@]}" ] && p_hi=$(( ${#pre[@]} - 1 ))
        p_found=""
        for p_j in $(seq "$p_lo" "$p_hi"); do
          if git show --stat --format= --name-only "${pre[$p_j]}" \
               | grep -qxE "watch-design.md|file-formats.md"; then
            p_found=1; break
          fi
        done
        [ -n "$p_found" ] || p_miss=$((p_miss+1))
      done
      echo "pre-baseline (d1df255..1d089ad): $p_wp watch.py commits, $p_miss without a styleguide entry"
      echo "  list them: just audit-styleguide d1df255..HEAD"
    fi
    [ "$miss" -eq 0 ]

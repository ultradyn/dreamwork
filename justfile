# ud-dreamwork — common tasks

# the verification every increment runs (there is no CI; this is the net).
# Three parts: pytest cannot see rendered structure, the guards cannot see
# Python, and neither reads the loop's OWN files. A change that passes one and
# fails another is still broken.
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
#   hub contract dreamhub's, in dev/hub/, and (OUT) only — their input is N
#                targets plus a registry, and they pick ephemeral ports, so
#                they need no plumbing here and cannot fight the server above.
guards port="39899":
    #!/usr/bin/env bash
    set -uo pipefail
    GUARDS="headertravel reflow qacard oneinput regroup popbg typing wisp states dismiss thread status health"
    OUT=$(mktemp -d)
    trap 'rm -rf "$OUT"' EXIT
    cp -r dev/capture/fixture "$OUT/target"
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
    fail=0
    for g in $GUARDS; do
      # Reset the target before EVERY guard — see the header. The server
      # re-reads from disk per request, so no restart is needed.
      rm -rf "$OUT/target" && cp -r dev/capture/fixture "$OUT/target"
      if node "dev/capture/$g.mjs" "$OUT/$g" {{port}} >"$OUT/$g.log" 2>&1; then
        echo "  PASS $g"
      else
        fail=1
        echo "  FAIL $g"
        grep -E "^(FAIL|Error)" "$OUT/$g.log" | head -5 | sed 's/^/        /'
      fi
    done
    # the hub's own guards (#96, #134). They start their own servers — their
    # input is N targets plus a registry, not one target dir — and pick
    # ephemeral ports, so they need no plumbing here and cannot fight the
    # watch server above for a port. Until these ran, a green `just test` did
    # not cover the hub at all, which is #117 verbatim one directory over.
    for h in hub contract; do
      if node "dev/hub/$h.mjs" "$OUT/$h" >"$OUT/$h.log" 2>&1; then
        echo "  PASS $h"
      else
        fail=1
        echo "  FAIL $h"
        grep -E "^(FAIL|Error)" "$OUT/$h.log" | head -5 | sed 's/^/        /'
      fi
    done
    # A missing browser is a missing verifier, not a pass. Say so loudly.
    if [ "$fail" -ne 0 ] && grep -q "Cannot find module" "$OUT"/*.log 2>/dev/null; then
      echo "guards: playwright not resolvable — the structural half did NOT run"
    fi
    exit $fail

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

# every commit that changes the page must also update the styleguide
# (DREAMWORK.md routine). Prints violations; silence is compliance.
# Range defaults to the styleguide era — d1df255 is where watch-design.md
# became authoritative, so earlier commits could not have obeyed the rule.
audit-styleguide range="d1df255..HEAD":
    #!/usr/bin/env bash
    set -euo pipefail
    miss=0; ok=0
    for c in $(git log --format=%h {{range}}); do
      files=$(git show --stat --format= --name-only "$c")
      grep -qx "watch.py" <<<"$files" || continue
      if grep -qx "watch-design.md" <<<"$files"; then
        ok=$((ok+1))
      else
        miss=$((miss+1))
        echo "MISS $c $(git log -1 --format=%s "$c" | cut -c1-64)"
      fi
    done
    echo "page-changing commits: $ok compliant, $miss missing a styleguide update"
    [ "$miss" -eq 0 ]

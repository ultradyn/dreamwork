# ud-dreamwork — common tasks

# the verification every increment runs (there is no CI; this is the net).
# Both halves: pytest cannot see rendered structure, the guards cannot see
# Python. A change that passes one and fails the other is still broken.
test: pytest guards

# the Python half — asserts on generated source, not on what renders
pytest:
    python3 -m pytest -q

# the structural half — real browser, real server, real DOM. Only scripts
# that exit non-zero belong here; the rest of dev/capture/ prints for a
# human and gates nothing. A guard joins this list when its feature lands.
guards port="39899":
    #!/usr/bin/env bash
    set -uo pipefail
    # Gated: content-independent, so a red here means the code broke.
    GUARDS="headertravel reflow"
    # NOT gated yet, and why — silence about a gap reads as coverage:
    #   qacard  asserts all three question states exist on /questions, so it
    #           fails whenever the live questions.md happens not to hold one.
    #           A guard that depends on mutable content tests the content.
    #   popbg   takes (BASE_URL, OUT); every other script takes (OUT, PORT).
    # Both need a fixture target and one argv contract — that is the rest
    # of #117, and it belongs to whoever owns dev/capture/.
    UNGATED="qacard popbg"
    OUT=$(mktemp -d)
    trap 'rm -rf "$OUT"' EXIT
    python3 watch.py --target . --port {{port}} >"$OUT/server.log" 2>&1 &
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
      if node "dev/capture/$g.mjs" "$OUT/$g" {{port}} >"$OUT/$g.log" 2>&1; then
        echo "  PASS $g"
      else
        fail=1
        echo "  FAIL $g"
        grep -E "^(FAIL|Error)" "$OUT/$g.log" | head -5 | sed 's/^/        /'
      fi
    done
    # A missing browser is a missing verifier, not a pass. Say so loudly.
    if [ "$fail" -ne 0 ] && grep -q "Cannot find module" "$OUT"/*.log 2>/dev/null; then
      echo "guards: playwright not resolvable — the structural half did NOT run"
    fi
    echo "  not gated: $UNGATED (see the justfile comment — #117)"
    exit $fail

# serve the dashboard on the persisted port, edit-and-see
watch:
    python3 watch.py --target . --dev

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

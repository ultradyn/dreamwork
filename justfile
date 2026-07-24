# ud-dreamwork — common tasks

# the verification every increment runs (there is no CI; this is the net)
test:
    python3 -m pytest -q

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

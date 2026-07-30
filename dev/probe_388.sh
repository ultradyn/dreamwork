#!/usr/bin/env bash
# #388 measurement probe — startup vs mid-run under load.
# Self-contained: spawns burners + watch.py, polls /, prints a timeline,
# kills EVERYTHING it spawned via trap. Bounded: ~25s wall.
set -uo pipefail
PORT=39950
REPO=/home/xertrov/.llm-general/skills/ud-dreamwork
TARGET=$(mktemp -d)
BURNERS=()
SRV=""
cleanup() {
  for pid in "${BURNERS[@]}"; do kill "$pid" 2>/dev/null; done
  [ -n "$SRV" ] && kill "$SRV" 2>/dev/null
  rm -rf "$TARGET"
}
trap cleanup EXIT
cp -r "$REPO/dev/capture/fixture" "$TARGET/target"

echo "=== baseline (no added load) ==="
core_load=$(cut -d' ' -f1 /proc/loadavg)
echo "load at start: $core_load on $(nproc) cores"
t0=$(date +%s%N)
python3 "$REPO/watch.py" --target "$TARGET/target" --port "$PORT" >/dev/null 2>&1 &
SRV=$!
# poll every 50ms until first 200
first_ms=""
for i in $(seq 1 200); do
  if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    t1=$(date +%s%N)
    first_ms=$(( (t1 - t0) / 1000000 ))
    break
  fi
  sleep 0.05
done
echo "startup: first 200 in ${first_ms:-NEVER}ms"
# poll for 5s to see if it drops
drops=0; polls=0
for i in $(seq 1 100); do
  if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    polls=$((polls+1))
  else
    drops=$((drops+1))
  fi
  sleep 0.05
done
echo "stability: $polls ok / $drops drops over 5s"
kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""

echo ""
echo "=== under load (16 burners) ==="
for i in $(seq 1 16); do
  yes > /dev/null &
  BURNERS+=($!)
done
sleep 0.5  # let burners ramp
load_under=$(cut -d' ' -f1 /proc/loadavg)
echo "load with burners: $load_under on $(nproc) cores"
t0=$(date +%s%N)
python3 "$REPO/watch.py" --target "$TARGET/target" --port "$PORT" >/dev/null 2>&1 &
SRV=$!
first_ms=""
for i in $(seq 1 200); do
  if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    t1=$(date +%s%N)
    first_ms=$(( (t1 - t0) / 1000000 ))
    break
  fi
  sleep 0.05
done
echo "startup: first 200 in ${first_ms:-NEVER}ms"
drops=0; polls=0
for i in $(seq 1 100); do
  if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    polls=$((polls+1))
  else
    drops=$((drops+1))
  fi
  sleep 0.05
done
echo "stability: $polls ok / $drops drops over 5s"
kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""

echo ""
echo "=== under heavy load (48 burners) ==="
for i in $(seq 1 32); do
  yes > /dev/null &
  BURNERS+=($!)
done
sleep 1  # let burners ramp
load_heavy=$(cut -d' ' -f1 /proc/loadavg)
echo "load with burners: $load_heavy on $(nproc) cores"
t0=$(date +%s%N)
python3 "$REPO/watch.py" --target "$TARGET/target" --port "$PORT" >/dev/null 2>&1 &
SRV=$!
first_ms=""
for i in $(seq 1 200); do
  if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    t1=$(date +%s%N)
    first_ms=$(( (t1 - t0) / 1000000 ))
    break
  fi
  sleep 0.05
done
echo "startup: first 200 in ${first_ms:-NEVER}ms"
drops=0; polls=0
for i in $(seq 1 100); do
  if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    polls=$((polls+1))
  else
    drops=$((drops+1))
  fi
  sleep 0.05
done
echo "stability: $polls ok / $drops drops over 5s"
echo ""
echo "=== finding: ECONNREFUSED cause ==="
echo "polling a port with NO server to confirm the error shape:"
node -e '
fetch("http://127.0.0.1:39951/").then(r => console.log("got", r.status))
  .catch(e => { const c = e.cause; console.log("ERROR:", e.constructor.name, "| msg:", e.message, "| cause:", c && c.code ? c.code : String(c)); });
'
echo "done"

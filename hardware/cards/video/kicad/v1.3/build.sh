#!/bin/sh
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

# build.sh - build and verify the YACC1 video card v1.3 board (2026-10-22): the 4-layer board from scratch (v1.2's
# outline, X1 and placement; In1.Cu GND plane, In2.Cu VCC plane; every signal routed anew by Freerouting), the reports
# and the checks. The memory card v2.0's build (hardware/cards/memory/kicad/v2.0/build.sh) is the model, simpler.
#
#   hardware/cards/video/kicad/v1.3/build.sh        rebuild video-v1.3.kicad_pcb and every report, then verify
#
# Steps: the schematic netlist; the project rules (gen_v13.py project); the unrouted board (gen_v13.py board: v1.2 with
# every track and via removed, the planes, JP2 + R15, every pad on its schematic net); one Freerouting run per DSN
# component order (SEEDS, in parallel; Power = GND/VCC not routed: -inc Power), each imported, its planes refilled and
# DRC'd; the best kept (fewest unrouted, then fewest vias, then shortest); the texts beside the new parts; the reports
# (netlist, ERC, DRC with schematic parity, schematic PDF, renders, netlist proof); gen_v13.py verify.
# Needs KiCad 10 and Freerouting 1.9 (FRJAR, default ~/freerouting/freerouting.jar; it opens a window while it runs).
HERE=$(cd "$(dirname "$0")" && pwd)
PYK=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
FRJAR="${FRJAR:-$HOME/freerouting/freerouting.jar}"
JAVA="${JAVA:-$(command -v java || echo /opt/homebrew/opt/openjdk/bin/java)}"
SEEDS=${SEEDS:-"0 1 2 3 4 5 6 7"}
MP=${MP:-30}
WATCHDOG=${WATCHDOG:-1500}
P=video-v1.3
R="$HERE/reports"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
q() { grep --line-buffered -vE 'Debug|assert|wxApp|traits|Fontconfig|memory leak|^$'; }
cd "$HERE" || exit 1
TMP=$(mktemp -d /tmp/video-v13-build.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$R"

echo "== 1  netlist, project rules, the unrouted board =="
"$CLI" sch export netlist --format kicadsexpr -o "$R/netlist.net" "$P.kicad_sch" >/dev/null 2>&1 || exit 1
"$PYK" gen_v13.py project 2>&1 | q
"$PYK" gen_v13.py board "$R/netlist.net" "$TMP/unrouted.kicad_pcb" 2>&1 | q
cp "$P.kicad_pro" "$TMP/unrouted.kicad_pro"; cp "$P.kicad_dru" "$TMP/unrouted.kicad_dru"
"$PYK" gen_v13.py dsn "$TMP/unrouted.kicad_pcb" "$TMP/v13.dsn" 2>&1 | q

echo "== 2  Freerouting, one run per component order: $SEEDS =="
pids=""
for s in $SEEDS; do
  mkdir -p "$TMP/s$s"
  "$PYK" gen_v13.py shuffle "$TMP/v13.dsn" "$s" "$TMP/s$s/v13.dsn" 2>&1 | q
  ( cd "$TMP/s$s" && exec "$JAVA" -jar "$FRJAR" -de v13.dsn -do v13.ses -mp "$MP" -oit 100 -mt 1 -inc Power ) \
    > "$TMP/s$s/fr.log" 2>&1 &
  pids="$pids $!"
done
t0=$(date +%s)
alive() { for p in $pids; do kill -0 "$p" 2>/dev/null && return 0; done; return 1; }
while alive; do
  if [ $(( $(date +%s) - t0 )) -gt "$WATCHDOG" ]; then
    echo "  watchdog: Freerouting still running after ${WATCHDOG}s - killed"; kill $pids 2>/dev/null
    sleep 2; kill -9 $pids 2>/dev/null; break
  fi
  sleep 5
done
echo "  Freerouting: $(( $(date +%s) - t0 )) s"
for s in $SEEDS; do
  D="$TMP/s$s"
  [ -s "$D/v13.ses" ] || { echo "  seed $s: no session"; continue; }
  cp "$P.kicad_pro" "$D/r.kicad_pro"; cp "$P.kicad_dru" "$D/r.kicad_dru"
  "$PYK" gen_v13.py ses "$TMP/unrouted.kicad_pcb" "$D/v13.ses" "$D/r.kicad_pcb" 2>&1 | q
  "$CLI" pcb drc --format json --severity-all -o "$D/drc.json" "$D/r.kicad_pcb" >/dev/null 2>&1
  printf "  seed %s: " "$s"; "$PYK" gen_v13.py stats "$D/r.kicad_pcb" "$D/drc.json" "$D/stats.json" 2>&1 | q
done
BEST=$(python3 - "$TMP" $SEEDS <<'EOF'
import json, os, sys
t = sys.argv[1]; best = None
for s in sys.argv[2:]:
    f = os.path.join(t, "s" + s, "stats.json")
    if not os.path.exists(f): continue
    r = json.load(open(f))
    if r["copper"]: continue
    k = (r["unrouted"], r["vias"], r["length"])
    if best is None or k < best[0]: best = (k, s)
print(best[1] if best else "")
EOF
)
[ -n "$BEST" ] || { echo "no clean route"; exit 1; }
echo "  kept: seed $BEST"
cp "$TMP/s$BEST/r.kicad_pcb" "$P.kicad_pcb"
"$PYK" gen_v13.py silk "$P.kicad_pcb" 2>&1 | q

echo "== 3  reports =="
"$CLI" sch erc --format json --severity-all -o "$R/erc.json" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" pcb drc --format json --severity-all --schematic-parity -o "$R/drc.json" "$P.kicad_pcb" >/dev/null 2>&1
"$CLI" sch export pdf -o "$R/$P-schematic.pdf" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" pcb render --side top --width 1568 --height 1176 -o "$R/$P-top.png" "$P.kicad_pcb" >/dev/null 2>&1
"$CLI" pcb render --side bottom --width 1568 --height 1176 -o "$R/$P-bottom.png" "$P.kicad_pcb" >/dev/null 2>&1
python3 ../../../../../tools/kicad/compare_netlists.py "$R/netlist.net" "$P.kicad_pcb" > "$R/netlist-compare.txt"
tail -1 "$R/netlist-compare.txt"

echo "== 4  checks =="
fail=0
grep -q "RESULT: MATCH" "$R/netlist-compare.txt" || { echo "  netlist proof: MISMATCH"; fail=1; }
python3 - "$R/drc.json" "$R/erc.json" <<'EOF' || fail=1
import json, sys, collections
d = json.load(open(sys.argv[1])); e = json.load(open(sys.argv[2]))
COSMETIC = {"silk_overlap", "silk_edge_clearance", "silk_over_copper", "text_height", "lib_footprint_mismatch",
            "items_not_allowed"}            # items_not_allowed: X1's two mounting holes in X1's own keepout (v1.0 on)
c = collections.Counter(v["type"] for v in d["violations"])
copper = {k: n for k, n in c.items() if k not in COSMETIC}
erc = collections.Counter(v["type"] for s in e["sheets"] for v in s["violations"])
real = {k: n for k, n in erc.items() if k not in ("endpoint_off_grid", "isolated_pin_label", "pin_to_pin")}
print("  DRC: unconnected %d, copper %s, cosmetic %s" % (len(d["unconnected_items"]), copper or "none",
                                                       dict(c - collections.Counter(copper))))
print("  ERC: %s (cosmetic: the Eagle conversion's labels and grid), other %s" % (dict(erc), real or "none"))
sys.exit(1 if d["unconnected_items"] or copper or real else 0)
EOF
python3 gen_v13.py verify "$R/netlist.net" "$P.kicad_pcb" || fail=1
[ $fail = 0 ] && echo "build.sh: ALL CHECKS PASS" || echo "build.sh: FAILED"
exit $fail

#!/bin/sh
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

# build.sh - build and verify the YACC1 video card V2.0 (2026-10-22): the schematic and the 4-layer board from
# v20_netlist.py, every signal routed by Freerouting, the reports and the checks. The v1.3 build (../v1.3/build.sh,
# after the memory card v2.0's) is the model; here the schematic and the placement are generated too.
#
#   hardware/cards/video/kicad/v2.0/build.sh        rebuild everything from v20_netlist.py, then verify
#
# Steps: gen_v20.py sch (local libraries + the A0 schematic) and its netlist checked against v20_netlist.py; the project
# rules; the unrouted board (gen_v20.py board: the blank card's X1, a 218 mm outline, In1.Cu GND / In2.Cu VCC planes,
# every part placed, every pad on its net) and the placement check; one Freerouting run per DSN component order (SEEDS,
# in parallel; Power = GND/VCC not routed: -inc Power), each imported, its planes refilled and DRC'd; the best kept
# (fewest unrouted, then fewest vias, then shortest); the reports (netlist, ERC, DRC with schematic parity, schematic
# PDF, renders, netlist proof); gen_v20.py verify. Needs KiCad 10 and Freerouting 1.9 (FRJAR, default
# ~/freerouting/freerouting.jar; it opens a window while it runs).
HERE=$(cd "$(dirname "$0")" && pwd)
PYK=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
FRJAR="${FRJAR:-$HOME/freerouting/freerouting.jar}"
JAVA="${JAVA:-$(command -v java || echo /opt/homebrew/opt/openjdk/bin/java)}"
SEEDS=${SEEDS:-"3"}           # the committed board: order 3 at MP=60 (2026-10-22, after the review: complete, 308 vias; order 4 also completed, orders 17, 2, 0, 1 left 4-7 unrouted - Freerouting varies run to run here); a wider search: SEEDS="0 1 ... 19", at most four at a time (the M3 Pro's performance cores)
MP=${MP:-60}
WATCHDOG=${WATCHDOG:-5400}   # seconds; a completed route is optimised for up to ~40 min after ~20 min of passes
P=video-v2.0
R="$HERE/reports"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
q() { grep --line-buffered -vE 'Debug|assert|wxApp|traits|Fontconfig|memory leak|^$'; }
cd "$HERE" || exit 1
TMP=$(mktemp -d /tmp/video-v20-build.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$R"

echo "== 1  schematic, netlist, project rules, the unrouted board =="
"$PYK" gen_v20.py sch 2>&1 | q
"$PYK" gen_v20.py project 2>&1 | q
"$CLI" sch export netlist --format kicadsexpr -o "$R/netlist.net" "$P.kicad_sch" >/dev/null 2>&1 || exit 1
"$PYK" gen_v20.py checknet "$R/netlist.net" 2>&1 | q || exit 1
"$PYK" gen_v20.py board "$R/netlist.net" "$TMP/unrouted.kicad_pcb" 2>&1 | q
cp "$P.kicad_pro" "$TMP/unrouted.kicad_pro"; cp "$P.kicad_dru" "$TMP/unrouted.kicad_dru"
"$PYK" gen_v20.py place "$TMP/unrouted.kicad_pcb" 2>&1 | q || exit 1
"$PYK" gen_v20.py dsn "$TMP/unrouted.kicad_pcb" "$TMP/v20.dsn" 2>&1 | q

echo "== 2  Freerouting, one run per component order: $SEEDS =="
pids=""
for s in $SEEDS; do
  mkdir -p "$TMP/s$s"
  "$PYK" gen_v20.py shuffle "$TMP/v20.dsn" "$s" "$TMP/s$s/v20.dsn" 2>&1 | q
  ( cd "$TMP/s$s" && exec "$JAVA" -jar "$FRJAR" -de v20.dsn -do v20.ses -mp "$MP" -oit 100 -mt 1 -inc Power ) \
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
  [ -s "$D/v20.ses" ] || { echo "  seed $s: no session"; continue; }
  cp "$P.kicad_pro" "$D/r.kicad_pro"; cp "$P.kicad_dru" "$D/r.kicad_dru"
  "$PYK" gen_v20.py ses "$TMP/unrouted.kicad_pcb" "$D/v20.ses" "$D/r.kicad_pcb" 2>&1 | q
  "$CLI" pcb drc --format json --severity-all -o "$D/drc.json" "$D/r.kicad_pcb" >/dev/null 2>&1
  printf "  seed %s: " "$s"; "$PYK" gen_v20.py stats "$D/r.kicad_pcb" "$D/drc.json" "$D/stats.json" 2>&1 | q
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
COSMETIC = {"silk_overlap", "silk_edge_clearance", "silk_over_copper", "text_height", "text_thickness", "lib_footprint_mismatch",
            "lib_footprint_issues", "items_not_allowed"}  # items_not_allowed: X1's two mounting holes in their keepouts
c = collections.Counter(v["type"] for v in d["violations"])
copper = {k: n for k, n in c.items() if k not in COSMETIC}
erc = collections.Counter(v["type"] for s in e["sheets"] for v in s["violations"])
real = {k: n for k, n in erc.items() if k not in ("endpoint_off_grid",)}
parity = d.get("schematic_parity", [])
print("  DRC: unconnected %d, copper %s, cosmetic %s; schematic parity %d" % (
    len(d["unconnected_items"]), copper or "none", dict(c - collections.Counter(copper)), len(parity)))
for v in parity[:5]: print("    parity: %s" % v["description"])
print("  ERC: %s, real %s" % (dict(erc), real or "none"))
sys.exit(1 if d["unconnected_items"] or copper or real or parity else 0)
EOF
"$PYK" gen_v20.py verify "$R/netlist.net" "$P.kicad_pcb" 2>&1 | q || fail=1
[ $fail = 0 ] && echo "build.sh: ALL CHECKS PASS" || echo "build.sh: FAILED"
exit $fail

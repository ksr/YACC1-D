#!/bin/sh
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

# build.sh - build and verify the YACC1 video card V4.0 (2026-11-12): the schematic and the 4-layer, 250 mm board from
# v40_netlist.py, the four clocks laid first by gen_v40.py, every other signal routed by Freerouting, the reports and
# the checks. The V2.0 card's build (../v2.0/build.sh) is the model.
#
#   hardware/cards/video/kicad/v4.0/build.sh        rebuild everything from v40_netlist.py, then verify
#
# Steps: gen_v40.py sch (local libraries + the schematic: a root and eight wired sheets, node + elkjs) and its netlist
# checked against v40_netlist.py; the project rules; the unrouted board (gen_v40.py board: the blank card's X1, a
# 250 mm outline, In1.Cu GND / In2.Cu VCC planes, every part placed, every pad on its net) and the placement check;
# the clocks (gen_v40.py clockroute: CK, D2, D3 and STG as trees from their series resistors, locked; since
# 2026-11-13) and KiCad's DRC of them alone; one Freerouting run per DSN component order (SEEDS, in parallel; Power =
# GND/VCC not routed: -inc Power; the clocks are fixed wiring to it), each imported, its planes refilled and DRC'd,
# its clocks looked at again; the best kept (fewest unrouted, then fewest vias, then shortest) and its planes made
# one piece each (gen_v40.py planes); the reports (netlist, ERC, DRC with schematic parity, schematic PDF, the
# placement drawing, renders, netlist proof, the clock nets, BOM); gen_v40.py verify. Needs KiCad 10 and Freerouting
# 1.9 (FRJAR, default ~/freerouting/freerouting.jar; it opens a window for each run while it works).
HERE=$(cd "$(dirname "$0")" && pwd)
PYK=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
FRJAR="${FRJAR:-$HOME/freerouting/freerouting.jar}"
JAVA="${JAVA:-$(command -v java || echo /opt/homebrew/opt/openjdk/bin/java)}"
SEEDS=${SEEDS:-"0 1 2 3"}     # the component orders tried, all at once: at most four (the M3 Pro's performance cores).
                             # The committed board (2026-11-14, the clocks laid first): these four, MT=1,
                             # MP=100 - order 0 routed every connection (44 minutes) and was optimised (1 h
                             # 56 min more): kept, 455 vias; orders 1, 2 and 3 left one or two open. The route
                             # of 2026-11-13, nothing fixed: orders 0, 1 and 2 complete, order 0 kept (377
                             # vias). The board before the review's changes: all four, order 1 kept (350 vias)
MP=${MP:-100}                # Freerouting's most passes
MT=${MT:-1}                  # its optimiser's threads. MT=0: no optimising after the passes, for a quick answer to
                             # "does this placement route?" (half an hour; a run killed while it optimises leaves
                             # no result at all)
KEEP=${KEEP:-}               # a folder to keep each run's log and board in (for a look at a route that failed)
WATCHDOG=${WATCHDOG:-14400}  # seconds of running time (a sleeping Mac's hours do not count): the four runs of the
                             # committed board took 9580 s, those of 2026-11-13 7950 s (8 hours by the clock: the
                             # Mac slept three times). A run stopped while it optimises leaves no result
P=video-v4.0
R="$HERE/reports"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
q() { grep --line-buffered -vE 'Debug|assert|wxApp|traits|Fontconfig|memory leak|^$'; }
# run CMD...: its output through q, its own exit status kept (a pipe into q would give grep's)
run() { "$@" > "$TMP/run.log" 2>&1; st=$?; q < "$TMP/run.log"; return $st; }
cd "$HERE" || exit 1
TMP=$(mktemp -d "${TMPDIR:-/tmp}/video-v40-build.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$R"
# no idle sleep while this runs (macOS; it ends with this script). A closed lid still sleeps the Mac: the runs then
# go on when it wakes
command -v caffeinate >/dev/null 2>&1 && caffeinate -i -w $$ &

echo "== 1  schematic, netlist, project rules, the unrouted board =="
"$PYK" gen_v40.py sch 2>&1 | q
"$PYK" gen_v40.py project 2>&1 | q
"$CLI" sch export netlist --format kicadsexpr -o "$R/netlist.net" "$P.kicad_sch" >/dev/null 2>&1 || exit 1
run "$PYK" gen_v40.py checknet "$R/netlist.net" || exit 1
"$PYK" gen_v40.py board "$R/netlist.net" "$TMP/unrouted.kicad_pcb" 2>&1 | q
cp "$P.kicad_pro" "$TMP/unrouted.kicad_pro"; cp "$P.kicad_dru" "$TMP/unrouted.kicad_dru"
run "$PYK" gen_v40.py place "$TMP/unrouted.kicad_pcb" || exit 1

echo "== 2  the four clocks first: trees from their series resistors, locked =="
run "$PYK" gen_v40.py clockroute "$TMP/unrouted.kicad_pcb" "$TMP/clocks.kicad_pcb" || exit 1
cp "$P.kicad_pro" "$TMP/clocks.kicad_pro"; cp "$P.kicad_dru" "$TMP/clocks.kicad_dru"
# --refill-zones: the planes are filled anew round the clocks' vias, as they are on the finished board
"$CLI" pcb drc --format json --severity-all --refill-zones -o "$TMP/clocks-drc.json" "$TMP/clocks.kicad_pcb" >/dev/null 2>&1
printf "  the clocks alone: "; "$PYK" gen_v40.py stats "$TMP/clocks.kicad_pcb" "$TMP/clocks-drc.json" "$TMP/clocks-stats.json" 2>&1 | q
python3 -c 'import json, sys; sys.exit(1 if json.load(open(sys.argv[1]))["copper"] else 0)' "$TMP/clocks-stats.json" \
  || { echo "  the clocks break a rule of the board"; exit 1; }
run "$PYK" gen_v40.py clocks "$TMP/clocks.kicad_pcb" || exit 1
"$PYK" gen_v40.py dsn "$TMP/clocks.kicad_pcb" "$TMP/v40.dsn" 2>&1 | q

echo "== 3  Freerouting, one run per component order: $SEEDS =="
pids=""
for s in $SEEDS; do
  mkdir -p "$TMP/s$s"
  "$PYK" gen_v40.py shuffle "$TMP/v40.dsn" "$s" "$TMP/s$s/v40.dsn" 2>&1 | q
  ( cd "$TMP/s$s" && exec "$JAVA" -jar "$FRJAR" -de v40.dsn -do v40.ses -mp "$MP" -oit 100 -mt "$MT" -inc Power ) \
    > "$TMP/s$s/fr.log" 2>&1 &
  pids="$pids $!"
done
t0=$(date +%s); ran=0
alive() { for p in $pids; do kill -0 "$p" 2>/dev/null && return 0; done; return 1; }
while alive; do
  if [ "$ran" -gt "$WATCHDOG" ]; then
    echo "  watchdog: Freerouting still running after ${WATCHDOG}s - killed"; kill $pids 2>/dev/null
    sleep 2; kill -9 $pids 2>/dev/null; break
  fi
  sleep 5; ran=$(( ran + 5 ))
done
echo "  Freerouting: $ran s of running time, $(( $(date +%s) - t0 )) s by the clock"
for s in $SEEDS; do
  D="$TMP/s$s"
  [ -s "$D/v40.ses" ] || { echo "  seed $s: no session"; continue; }
  cp "$P.kicad_pro" "$D/r.kicad_pro"; cp "$P.kicad_dru" "$D/r.kicad_dru"
  "$PYK" gen_v40.py ses "$TMP/clocks.kicad_pcb" "$D/v40.ses" "$D/r.kicad_pcb" 2>&1 | q
  "$CLI" pcb drc --format json --severity-all -o "$D/drc.json" "$D/r.kicad_pcb" >/dev/null 2>&1
  printf "  seed %s: " "$s"; "$PYK" gen_v40.py stats "$D/r.kicad_pcb" "$D/drc.json" "$D/stats.json" 2>&1 | q
  # the clocks must come back as they went in: every input reached, every track still locked
  "$PYK" gen_v40.py clocks "$D/r.kicad_pcb" > "$D/clocks.log" 2>&1 || { echo "  seed $s: its clocks are not as laid"; rm -f "$D/stats.json"; }
done
if [ -n "$KEEP" ]; then
  mkdir -p "$KEEP"; cp "$TMP/clocks.kicad_pcb" "$KEEP/clocks.kicad_pcb"
  for s in $SEEDS; do
    for f in fr.log r.kicad_pcb drc.json clocks.log; do [ -f "$TMP/s$s/$f" ] && cp "$TMP/s$s/$f" "$KEEP/s$s-$f"; done
  done
fi
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
"$PYK" gen_v40.py planes "$P.kicad_pcb" > "$TMP/planes.log" 2>&1; st=$?   # each plane one piece
q < "$TMP/planes.log"; [ $st = 0 ] || exit 1

echo "== 4  reports =="
"$CLI" sch erc --format json --severity-all -o "$R/erc.json" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" pcb drc --format json --severity-all --schematic-parity -o "$R/drc.json" "$P.kicad_pcb" >/dev/null 2>&1
"$CLI" sch export pdf -o "$R/$P-schematic.pdf" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" pcb render --side top --width 2400 --height 1200 --zoom 1.9 -o "$R/$P-top.png" "$P.kicad_pcb" >/dev/null 2>&1
"$CLI" pcb render --side bottom --width 2400 --height 1200 --zoom 1.9 -o "$R/$P-bottom.png" "$P.kicad_pcb" >/dev/null 2>&1
"$PYK" gen_v40.py drawing "$P.kicad_pcb" 2>&1 | q
"$PYK" gen_v40.py clocks "$P.kicad_pcb" "$R/clocks.txt" 2>&1 | q | tail -2
"$PYK" gen_v40.py bom 2>&1 | q
python3 ../../../../../tools/kicad/compare_netlists.py "$R/netlist.net" "$P.kicad_pcb" > "$R/netlist-compare.txt"
tail -1 "$R/netlist-compare.txt"

echo "== 5  checks =="
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
run "$PYK" gen_v40.py place "$P.kicad_pcb" || fail=1
run "$PYK" gen_v40.py verify "$R/netlist.net" "$P.kicad_pcb" || fail=1
"$PYK" gen_v40.py clocks "$P.kicad_pcb" > "$TMP/run.log" 2>&1 || fail=1; tail -1 "$TMP/run.log"
[ $fail = 0 ] && echo "build.sh: ALL CHECKS PASS" || echo "build.sh: FAILED"
exit $fail

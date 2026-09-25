#!/bin/sh
# build.sh - build and verify the YACC1 memory card v2.0: the schematic (the built v1.3 + the CF section), THE v2.0
# BOARD memory-v2.0.kicad_pcb (Ken 2026-09-25: standoff option E, finished for fabrication, NOT ORDERED) with its fab
# outputs, the five STANDOFF placement options (the CF adapter on two standoffs on the card, J2 parallel to X1) with
# their trial routes and 1:1 prints, and the records. The built card = ../v1.3 ("v1.3" below).
#
#   hardware/cards/memory/kicad/v2.0/build.sh               verify the committed v2.0 board (placement check, DRC with
#                                                             schematic parity, finish_v2.py verify, netlist proof)
#                                                             and REGENERATE its fab outputs (gerbers/ + zip, NPTH/PTH
#                                                             drill, renders, placement PDF, order note, 1:1 print,
#                                                             BOM); verify the standoff options + trial routes and
#                                                             remake their images and 1:1 PDFs; the top-edge record
#   FINAL=trial hardware/cards/memory/kicad/v2.0/build.sh   + remake memory-v2.0.kicad_pcb from standoff E's committed
#                                                             trial route (finish_v2.py make-e)
#   FINAL=route hardware/cards/memory/kicad/v2.0/build.sh   + route standoff E's placement anew in the component orders
#                                                             SEEDS (the best kept) and make the board from it;
#                                                             FINAL=route SEEDS=15 remakes the committed board's route
#   STANDOFF="c d e" hardware/cards/memory/kicad/v2.0/build.sh + regenerate those standoff option boards and route
#                                                             each anew: one Freerouting run per DSN component order
#                                                             in SEEDS (default "0 1 2 3 4 5 6 7", in parallel;
#                                                             Freerouting 1.9 repeats itself for one file, the order
#                                                             changes the route), the best kept (fewest unrouted,
#                                                             then vias, then length); NOROUTE=1 keeps the committed
#                                                             trial routes; OPTS limits the options (default a-e)
#   The TOP-EDGE record (options-top-edge-J2/: the re-layout options A/B/C with J2 at the top edge and the board
#   finished from option B, fab files included - Ken's pick until the standoff decision):
#   FROM=trial hardware/cards/memory/kicad/v2.0/build.sh    + remake options-top-edge-J2/memory-v2.0.kicad_pcb from
#                                                             the committed option-B trial route (+ its fab outputs)
#   ROUTE=1 hardware/cards/memory/kicad/v2.0/build.sh       + route top-edge option B anew (ROUTES runs, default 4)
#   RELAYOUT="a b c" hardware/cards/memory/kicad/v2.0/build.sh   + regenerate the top-edge re-layout option boards
#                                                             with new trial routes; add NOROUTE=1 to keep the
#                                                             committed trial routes and only re-check them
#   KEEPCOPPER="a b c" hardware/cards/memory/kicad/v2.0/build.sh + regenerate the blocked keep-the-built-copper options
#                                                             (the record in options-keep-copper/)
#
# 1 gen_mem_v2.py sch: schematic (v1.3 sheets 1-6 + sheet 7 CF) + libraries; finish_v2.py project: the project
#   memory-v2.0.kicad_pro/.kicad_dru carries the re-layout rules (0.25 mm tracks, 0.2 mm clearance, vias 0.8/0.4, class
#   Power = GND/VCC on the planes, never routed); the built card's rules are kept aside for the keep-copper record
# 2 ERC (must equal v1.3's list + the one designed-in SRST single-pin label; the six bus labels that became global lose
#   their v1.3 "isolated label" warnings)
# 3 (RELAYOUT) per top-edge option: board, plane refill, placement check, DRC, airwire, review images, trial route
# s per standoff option (a-e): (STANDOFF: board, refill, trial routes) placement check (gen_standoff.py check), DRC
#   with schematic parity, airwire, trial-route numbers, review render / placement plot / trial plot, 1:1 PDF
# f THE v2.0 BOARD (standoff E): (FINAL=trial / route: finish_v2.py make-e) placement check (gen_standoff.py check e),
#   DRC with schematic parity (0 copper violations, 0 unconnected, the standoff keep-outs clear), finish_v2.py verify
#   (through vias, planes one piece, power pads on the planes, silkscreen texts clear), finish_v2.py fab-e (gerbers,
#   NPTH/PTH drill + drill-check: H1/H2 in the NPTH file, zip, renders, placement PDF, JLCPCB order note), the 1:1 print
# k (KEEPCOPPER) the keep-copper record
# 4 (FROM=trial / ROUTE=1) the top-edge record's finished board: finish_v2.py make (through vias, via clean-up, collinear merge, adapter
#   outline on F.Fab, J3 pin labels, silkscreen tidy, title block, C20-C23 taken off, plane refill)
# 5 DRC of the top-edge record's finished board with schematic parity + finish_v2.py verify: 0 unrouted, 0 copper violations, every
#   via a through via, both planes one solid piece, every GND/VCC pad on its plane, no silkscreen text on a pad / via /
#   other silk / the edge, none upside down; no parity item beyond the built card's inherited Eagle values/fields
# 6 netlist proof: v2.0 schematic = v1.3 - C20-C23 + CF section; the v2.0 board, the standoff boards, their trial
#   routes and the top-edge finished board = the schematic (the standoff boards + H1/H2, board-only standoff holes); the option boards,
#   trial routes and keep-copper boards (records, made before C20-C23 were removed, Ken 2026-09-24) = the schematic +
#   exactly C20-C23 as on v1.3 (check_netlist.py)
# 7 schematic PDF, BOM (+ H1/H2 and the hardware lines: finish_v2.py bom-hw); (FROM / ROUTE) the top-edge record's fab outputs: gerbers/ + drill + zip, renders, placement
#   PDF, the JLCPCB order note
# Exit status non-zero if a gate fails.
HERE=$(cd "$(dirname "$0")" && pwd)
PYK=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
INK=/Applications/Inkscape.app/Contents/MacOS/inkscape
FRJAR="${FRJAR:-$HOME/freerouting/freerouting.jar}"
WATCHDOG=${WATCHDOG:-1800}
P=memory-v2.0
R="$HERE/reports"
K="$HERE/options-keep-copper"
T="$HERE/options-top-edge-J2"          # the top-edge record (re-layout A/B/C + the board finished from B)
RT="$T/reports"
BRD="$T/$P.kicad_pcb"
RELAYOUT=${RELAYOUT:-""}
STANDOFF=${STANDOFF:-""}
SEEDS=${SEEDS:-"0 1 2 3 4 5 6 7"}   # the standoff trial routes: one Freerouting run per DSN component order, in
                                    # parallel (gen_standoff.py shuffle; seed 0 = as exported), the best kept
MP=${MP:-30}
KEEPCOPPER=${KEEPCOPPER:-""}
ROUTES=${ROUTES:-4}
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
q() { grep --line-buffered -vE 'Debug|assert|wxApp|traits|Fontconfig|memory leak|^$'; }
fail=0
mkdir -p "$R" "$K/reports" "$RT"
cd "$HERE" || exit 1
BASE=v1.3
LIB=memory-$BASE-eagle
TMP=$(mktemp -d /tmp/memory-v2-build.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
# the built card is read from a scratch copy, so no KiCad run can leave a file in ../$BASE (regenerated by its own tool)
cp -R "../$BASE" "$TMP/v13"
OLD="$TMP/v13/memory-$BASE"

echo "== 1  schematic (gen_mem_v2.py sch), project (finish_v2.py project) =="
"$PYK" gen_mem_v2.py sch 2>&1 | q || exit 1
cp "$P.kicad_pro" "$TMP/built-rules.kicad_pro"; cp "$P.kicad_dru" "$TMP/built-rules.kicad_dru"
"$PYK" finish_v2.py project 2>&1 | q | sed 's/^/  /'
"$CLI" sch export netlist --format kicadsexpr -o "$R/$P.net" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" sch export netlist --format kicadsexpr -o "$TMP/v1.3.net" "$OLD.kicad_sch" >/dev/null 2>&1

echo "== 2  ERC =="
"$CLI" sch erc --severity-all -o "$R/$P-erc.rpt" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" sch erc --severity-all --format json -o "$R/$P-erc.json" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" sch erc --severity-all --format json -o "$TMP/v1.3-erc.json" "$OLD.kicad_sch" >/dev/null 2>&1
python3 - "$R/$P-erc.json" "$TMP/v1.3-erc.json" <<'EOF' | tee "$R/erc-summary.txt"
import json, sys, collections
def load(p):
    c = collections.Counter()
    for s in json.load(open(p))["sheets"]:
        for v in s["violations"]:
            c[(v["severity"], v["type"], tuple(i["description"] for i in v["items"]))] += 1
    return c
v2, v1 = load(sys.argv[1]), load(sys.argv[2])
new, gone = v2 - v1, v1 - v2
by = lambda c: dict(collections.Counter((k[0], k[1]) for k in c.elements()))
print("  ERC v2.0: %d violations %s" % (sum(v2.values()), by(v2)))
print("  ERC built v1.3: %d violations (the Eagle-conversion residue, ../v1.3/README.md)" % sum(v1.values()))
print("  new on v2.0: %s" % ([(k[1], k[2]) for k in new] or "none"))
print("  gone on v2.0: %s" % ([(k[1], k[2]) for k in gone] or "none"))
unexpected = [k for k in new if not (k[1] == "isolated_pin_label" and k[2] == ("Label 'SRST'",))]
GLOBAL = {"Label '%s'" % n for n in ["IO-ADDR0", "IO-ADDR1", "IO-ADDR2", "IO-ADDR3", "-IO-RD", "-IO-WR"]}
odd_gone = [k for k in gone if not (k[1] == "isolated_pin_label" and len(k[2]) == 1 and k[2][0] in GLOBAL)]
print("  unexplained: %d new, %d gone -> %s" % (len(unexpected), len(odd_gone),
                                                 "PASS" if not unexpected and not odd_gone else "FAIL"))
sys.exit(0 if not unexpected and not odd_gone else 1)
EOF
grep -q -- "-> PASS" "$R/erc-summary.txt" || fail=1
"$CLI" pcb drc --schematic-parity --severity-all --format json -o "$TMP/v1.3-drc.json" "$OLD.kicad_pcb" >/dev/null 2>&1

# drc_parity <board> <its .kicad_pro> <its .kicad_dru> <out.json> [<out.rpt>]: DRC with schematic parity (the board
# needs the schematic beside it under the same name, and its own rules)
drc_parity() {
  rm -rf "$TMP/p"; mkdir "$TMP/p"
  cp -R "$HERE"/*.kicad_sch "$HERE"/*-lib-table "$HERE/$LIB".* "$TMP/p/"
  cp "$2" "$TMP/p/$P.kicad_pro"; cp "$3" "$TMP/p/$P.kicad_dru"; cp "$1" "$TMP/p/$P.kicad_pcb"
  "$CLI" pcb drc --schematic-parity --severity-all --format json -o "$4" "$TMP/p/$P.kicad_pcb" >/dev/null 2>&1
  [ -n "$5" ] && "$CLI" pcb drc --schematic-parity --severity-all -o "$5" "$TMP/p/$P.kicad_pcb" >/dev/null 2>&1
  true
}
# parity items beyond the built card's own (its Eagle board values / fields, inherited) -> none expected.
# parity_new <drc.json> record: a board made before C20-C23 were removed (option boards, trial routes) may also carry
# exactly those four as extra footprints (mem_v2_netlist.REMOVED)
parity_new() {
  python3 - "$1" "$TMP/v1.3-drc.json" "$2" <<'EOF'
import json, sys
sys.path.insert(0, ".")
from mem_v2_netlist import REMOVED
d, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
record = len(sys.argv) > 3 and sys.argv[3] == "record"
bpar = {(x["type"], x["description"]) for x in b.get("schematic_parity", []) if x["type"] != "net_conflict"}
rem = lambda x: x["type"] == "extra_footprint" and all(i["description"] in ["Footprint " + r for r in REMOVED]
                                                       for i in x["items"])
par = d.get("schematic_parity", [])
old = [x for x in par if rem(x)] if record else []
new = [x["description"] for x in par if (x["type"], x["description"]) not in bpar and x not in old]
print("     schematic parity: %d items (built v1.3: %d, all inherited Eagle values/fields%s); new: %s"
      % (len(par), len(b.get("schematic_parity", [])),
         "; + %d = %s, on this record board made before their removal" % (
             len(old), "/".join(sorted(i["description"].split()[-1] for x in old for i in x["items"]))) if old else "",
         new or "none"))
sys.exit(1 if new else 0)
EOF
}
freeroute() {   # freeroute <dsn> <ses> <log>: Freerouting 1.9, one thread, MP passes (default 30), class Power
                # (GND/VCC: planes) not routed
  dsn=$1; ses=$2; log=$3
  rm -f "$ses"; t0=$(date +%s)
  ( cd "$(dirname "$dsn")" && exec java -jar "$FRJAR" -de "$dsn" -do "$ses" -mp "$MP" -oit 100 -mt 1 -inc Power ) > "$log" 2>&1 &
  jp=$!
  while kill -0 $jp 2>/dev/null; do
    if [ $(( $(date +%s) - t0 )) -gt "$WATCHDOG" ]; then
      echo "  watchdog: Freerouting still running after ${WATCHDOG}s - killed"; kill $jp; sleep 2; kill -9 $jp 2>/dev/null
      break
    fi
    sleep 5
  done
  wait $jp 2>/dev/null
  [ -f "$(dirname "$dsn")/logs/freerouting.log" ] && cat "$(dirname "$dsn")/logs/freerouting.log" >> "$log"
  echo "  Freerouting $(basename "$(dirname "$dsn")"): $(( $(date +%s) - t0 )) s"
  [ -f "$ses" ]
}

# route_best <opt> <out.kicad_pcb> <report prefix>: route memory-v2.0-standoff-<opt>.kicad_pcb in the DSN component
# orders $SEEDS (one Freerouting run each, in parallel; gen_standoff.py shuffle, seed 0 = as exported), import each
# session, keep the best (fewest unrouted, then vias, then length) as <out>; <prefix>-order.txt (the order kept, every
# run's numbers) and <prefix>-freerouting.log
route_best() {
  o=$1; out=$2; rp=$3
  B="$P-standoff-$o.kicad_pcb"
  rm -rf "$TMP/s$o"*; mkdir -p "$TMP/s$o"
  "$PYK" gen_standoff.py dsn "$B" "$TMP/s$o/$o.dsn" 2>&1 | q | sed 's/^/  /'
  i=0
  for sd in $SEEDS; do
    i=$((i + 1))
    mkdir -p "$TMP/s$o$i"
    python3 gen_standoff.py shuffle "$TMP/s$o/$o.dsn" "$sd" "$TMP/s$o$i/$o.dsn" > /dev/null
    ( freeroute "$TMP/s$o$i/$o.dsn" "$TMP/s$o$i/$o.ses" "$TMP/s$o$i/freerouting.log" ) &
  done
  wait
  : > "$TMP/s$o-routes.txt"; : > "$TMP/s$o-runs.txt"
  n=$i
  i=1
  while [ $i -le "$n" ]; do
    if [ -f "$TMP/s$o$i/$o.ses" ]; then
      "$PYK" gen_standoff.py ses "$B" "$TMP/s$o$i/$o.ses" "$TMP/s$o$i/t.kicad_pcb" 2>&1 | q | sed 's/^/  /'
      cp "$P-standoff-$o.kicad_pro" "$TMP/s$o$i/t.kicad_pro"; cp "$P-standoff-$o.kicad_dru" "$TMP/s$o$i/t.kicad_dru"
      "$PYK" gen_standoff.py refill "$TMP/s$o$i/t.kicad_pcb" 2>&1 | q
      "$CLI" pcb drc --severity-all --format json -o "$TMP/s$o$i/drc.json" "$TMP/s$o$i/t.kicad_pcb" >/dev/null 2>&1
      "$PYK" gen_standoff.py stats "$TMP/s$o$i/t.kicad_pcb" "$TMP/s$o$i/drc.json" "$o" 2>&1 | q > "$TMP/s$o$i/stats.txt"
      u=$(sed -n 's/.*after Freerouting: \([0-9]*\).*/\1/p' "$TMP/s$o$i/stats.txt")
      v=$(sed -n 's/^  vias: \([0-9]*\).*/\1/p' "$TMP/s$o$i/stats.txt")
      l=$(sed -n 's/^  track length: \([0-9]*\) mm.*/\1/p' "$TMP/s$o$i/stats.txt")
      echo "  run $i (order $(echo $SEEDS | cut -d' ' -f$i)): unrouted $u, vias $v, track $l mm" | tee -a "$TMP/s$o-runs.txt"
      echo "$u $v $l $i" >> "$TMP/s$o-routes.txt"
    fi
    i=$((i + 1))
  done
  pick=$(sort -n -k1,1 -k2,2 -k3,3 "$TMP/s$o-routes.txt" | head -1 | awk '{print $4}')
  [ -n "$pick" ] || return 1
  { echo "  kept: run $pick (order $(echo $SEEDS | cut -d' ' -f$pick))"; cat "$TMP/s$o-runs.txt"; } > "$rp-order.txt"
  head -1 "$rp-order.txt"
  cp "$TMP/s$o$pick/t.kicad_pcb" "$out"
  cp "$TMP/s$o$pick/freerouting.log" "$rp-freerouting.log"
}

# 3: the top-edge re-layout options (the review record, options-top-edge-J2/; regenerated only on request)
boards=""
for o in $RELAYOUT; do
  B="$T/$P-relayout-$o.kicad_pcb"
  TR="$T/$P-relayout-$o-trial.kicad_pcb"
  echo "== 3$o  re-layout option $o =="
  "$PYK" gen_relayout.py board "$o" "$R/$P.net" 2>&1 | q | sed 's/^/  /' || { fail=1; continue; }
  "$PYK" gen_relayout.py refill "$B" 2>&1 | q
  "$PYK" gen_relayout.py check "$B" "$o" 2>&1 | q | tee "$RT/relayout-$o-placement-check.txt" | sed 's/^/  /'
  grep -q ": OK" "$RT/relayout-$o-placement-check.txt" || fail=1
  "$PYK" gen_relayout.py airwire "$B" 2>&1 | q | tee -a "$RT/relayout-$o-placement-check.txt" | sed 's/^/  /'
  drc_parity "$B" "$T/$P-relayout-$o.kicad_pro" "$T/$P-relayout-$o.kicad_dru" "$RT/relayout-$o-drc.json"
  parity_new "$RT/relayout-$o-drc.json" record | tee -a "$RT/relayout-$o-placement-check.txt" || fail=1
  "$PYK" gen_mem_v2.py review "$B" "$TMP/r.kicad_pcb" render 2>&1 | q
  "$CLI" pcb render --side top --width 2000 --height 1400 -o "$T/$P-relayout-$o-render-top.png" "$TMP/r.kicad_pcb" >/dev/null 2>&1 \
    && echo "  render -> $P-relayout-$o-render-top.png"
  "$PYK" gen_mem_v2.py review "$B" "$TMP/p2.kicad_pcb" plot 2>&1 | q | sed 's/^/  /'
  "$CLI" pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet \
    -l Edge.Cuts,F.Cu,B.Cu,F.Silkscreen,User.Drawings,User.Eco1 -o "$TMP/p2.svg" "$TMP/p2.kicad_pcb" >/dev/null 2>&1
  "$INK" "$TMP/p2.svg" --export-type=png --export-width=2400 --export-background=white \
    --export-filename="$T/$P-relayout-$o-placement.png" >/dev/null 2>&1 && echo "  plot   -> $P-relayout-$o-placement.png"

  echo "== 3r$o  trial route of option $o =="
  if [ -z "$NOROUTE" ]; then
    mkdir -p "$TMP/fr$o"
    "$PYK" gen_relayout.py dsn "$B" "$TMP/fr$o/$o.dsn" 2>&1 | q | sed 's/^/  /'
    if freeroute "$TMP/fr$o/$o.dsn" "$TMP/fr$o/$o.ses" "$RT/relayout-$o-freerouting.log"; then
      "$PYK" gen_relayout.py ses "$B" "$TMP/fr$o/$o.ses" "$TR" 2>&1 | q | sed 's/^/  /'
      "$PYK" gen_relayout.py refill "$TR" 2>&1 | q
      cp "$T/$P-relayout-$o.kicad_pro" "$T/$P-relayout-$o-trial.kicad_pro"
      cp "$T/$P-relayout-$o.kicad_dru" "$T/$P-relayout-$o-trial.kicad_dru"
    else
      echo "  TRIAL ROUTE FAILED (no session file) - see options-top-edge-J2/reports/relayout-$o-freerouting.log"; fail=1
    fi
  fi
  if [ -f "$TR" ]; then
    drc_parity "$TR" "$T/$P-relayout-$o.kicad_pro" "$T/$P-relayout-$o.kicad_dru" "$RT/relayout-$o-trial-drc.json"
    { "$PYK" gen_relayout.py stats "$TR" "$RT/relayout-$o-trial-drc.json" "$o" 2>&1 | q
      parity_new "$RT/relayout-$o-trial-drc.json" record; } | tee "$RT/relayout-$o-trial.txt" | sed 's/^/  /'
    grep -q "new: none" "$RT/relayout-$o-trial.txt" || fail=1
    "$CLI" pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet \
      -l Edge.Cuts,F.Cu,B.Cu,F.Silkscreen -o "$TMP/t.svg" "$TR" >/dev/null 2>&1
    "$INK" "$TMP/t.svg" --export-type=png --export-width=2400 --export-background=white \
      --export-filename="$T/$P-relayout-$o-trial.png" >/dev/null 2>&1 && echo "  plot   -> $P-relayout-$o-trial.png"
  fi
done

# s: the STANDOFF options (Ken 2026-09-24: the CF adapter on two standoffs on the card; Ken picks one)
for o in ${OPTS:-a b c d e}; do
  B="$P-standoff-$o.kicad_pcb"
  TR="$P-standoff-$o-trial.kicad_pcb"
  echo "== s$o  standoff option $o =="
  if echo " $STANDOFF " | grep -q " $o "; then
    "$PYK" gen_standoff.py board "$o" "$R/$P.net" 2>&1 | q | sed 's/^/  /' || { fail=1; continue; }
    "$PYK" gen_standoff.py refill "$B" 2>&1 | q
  fi
  [ -f "$B" ] || { echo "  $B missing"; fail=1; continue; }
  "$PYK" gen_standoff.py check "$B" "$o" 2>&1 | q | tee "$R/standoff-$o-placement-check.txt" | sed 's/^/  /'
  grep -q ": OK" "$R/standoff-$o-placement-check.txt" || fail=1
  "$PYK" gen_standoff.py airwire "$B" 2>&1 | q | tee -a "$R/standoff-$o-placement-check.txt" | sed 's/^/  /'
  drc_parity "$B" "$P-standoff-$o.kicad_pro" "$P-standoff-$o.kicad_dru" "$R/standoff-$o-drc.json"
  parity_new "$R/standoff-$o-drc.json" | tee -a "$R/standoff-$o-placement-check.txt" || fail=1
  if echo " $STANDOFF " | grep -q " $o " && [ -z "$NOROUTE" ]; then
    echo "== s$o  trial route: Freerouting runs in the component orders $SEEDS ($MP passes) =="
    if route_best "$o" "$TR" "$R/standoff-$o"; then
      cp "$P-standoff-$o.kicad_pro" "$P-standoff-$o-trial.kicad_pro"
      cp "$P-standoff-$o.kicad_dru" "$P-standoff-$o-trial.kicad_dru"
    else
      echo "  TRIAL ROUTE FAILED (no session file)"; fail=1
    fi
  fi
  if [ -f "$TR" ]; then
    drc_parity "$TR" "$P-standoff-$o.kicad_pro" "$P-standoff-$o.kicad_dru" "$R/standoff-$o-trial-drc.json"
    { "$PYK" gen_standoff.py stats "$TR" "$R/standoff-$o-trial-drc.json" "$o" "$TMP/s$o-stats.json" 2>&1 | q
      parity_new "$R/standoff-$o-trial-drc.json"; } | tee "$R/standoff-$o-trial.txt" | sed 's/^/  /'
    grep -q "new: none" "$R/standoff-$o-trial.txt" || fail=1
    grep -q "DRC copper violations: none" "$R/standoff-$o-trial.txt" || fail=1
    "$CLI" pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet \
      -l Edge.Cuts,F.Cu,B.Cu,F.Silkscreen -o "$TMP/t.svg" "$TR" >/dev/null 2>&1
    "$INK" "$TMP/t.svg" --export-type=png --export-width=2400 --export-background=white \
      --export-filename="$HERE/$P-standoff-$o-trial.png" >/dev/null 2>&1 && echo "  plot   -> $P-standoff-$o-trial.png"
  fi
  "$PYK" gen_standoff.py review "$B" "$TMP/r.kicad_pcb" render 2>&1 | q
  "$CLI" pcb render --side top --width 2000 --height 1400 -o "$HERE/$P-standoff-$o-render-top.png" "$TMP/r.kicad_pcb" >/dev/null 2>&1 \
    && echo "  render -> $P-standoff-$o-render-top.png"
  "$PYK" gen_standoff.py review "$B" "$TMP/p2.kicad_pcb" plot 2>&1 | q | sed 's/^/  /'
  "$CLI" pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet \
    -l Edge.Cuts,F.Cu,B.Cu,F.Silkscreen,User.Drawings,User.Eco1 -o "$TMP/p2.svg" "$TMP/p2.kicad_pcb" >/dev/null 2>&1
  "$INK" "$TMP/p2.svg" --export-type=png --export-width=2400 --export-background=white \
    --export-filename="$HERE/$P-standoff-$o-placement.png" >/dev/null 2>&1 && echo "  plot   -> $P-standoff-$o-placement.png"
  "$PYK" gen_standoff.py geom "$B" "$o" "$TMP/s$o-geom.json" "$TMP/s$o-stats.json" 2>&1 | q | sed 's/^/  /'
  python3 print_1to1.py "$TMP/s$o-geom.json" "$HERE/$P-standoff-$o-1to1.pdf" 2>&1 | sed 's/^/  /'
done

# f: THE v2.0 BOARD (Ken 2026-09-25: standoff option E) = memory-v2.0.kicad_pcb beside the schematic. A plain run
# verifies the committed board and regenerates its fab outputs; FINAL=trial remakes it from E's committed trial route,
# FINAL=route routes E's placement anew in the orders $SEEDS and makes it from the best (finish_v2.py make-e)
FB="$HERE/$P.kicad_pcb"
if [ "$FINAL" = "route" ]; then
  echo "== f  the v2.0 board: route standoff E anew in the component orders $SEEDS =="
  if route_best e "$TMP/final-e.kicad_pcb" "$R/$P"; then
    "$PYK" finish_v2.py make-e "$TMP/final-e.kicad_pcb" "$FB" 2>&1 | q | tee "$R/$P-make.txt" | sed 's/^/  /'
  else
    echo "  NO ROUTE - the committed board stays"; fail=1
  fi
elif [ "$FINAL" = "trial" ]; then
  echo "== f  the v2.0 board from standoff E's committed trial route =="
  "$PYK" finish_v2.py make-e "$P-standoff-e-trial.kicad_pcb" "$FB" 2>&1 | q | tee "$R/$P-make.txt" | sed 's/^/  /'
  echo "  kept: the committed trial route memory-v2.0-standoff-e-trial.kicad_pcb" > "$R/$P-order.txt"
fi
echo "== f  the v2.0 board ($P.kicad_pcb): placement, DRC, verify, fab outputs, 1:1 print =="
if [ -f "$FB" ]; then
  "$PYK" gen_standoff.py check "$FB" e 2>&1 | q | tee "$R/$P-placement-check.txt" | sed 's/^/  /'
  grep -q ": OK" "$R/$P-placement-check.txt" || fail=1
  drc_parity "$FB" "$HERE/$P.kicad_pro" "$HERE/$P.kicad_dru" "$R/$P-drc.json" "$R/$P-drc.rpt"
  { "$PYK" finish_v2.py verify "$FB" "$R/$P-drc.json" 2>&1 | q
    python3 - "$R/$P-drc.json" "$TMP/v1.3-drc.json" <<'EOF2'
import json, sys, collections
d, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
cd = collections.Counter(v["type"] for v in d["violations"])
cb = collections.Counter(v["type"] for v in b["violations"])
print("  DRC by type, v2.0 / built v1.3 (its own rules): %s"
      % ", ".join("%s %d/%d" % (t, cd.get(t, 0), cb.get(t, 0)) for t in sorted(set(cd) | set(cb))))
print("  DRC unconnected, v2.0 / built v1.3: %d/%d" % (len(d.get("unconnected_items", [])),
                                                        len(b.get("unconnected_items", []))))
EOF2
    parity_new "$R/$P-drc.json"; } | tee "$R/$P-final.txt" | sed 's/^/  /'
  grep -q -- "-> PASS" "$R/$P-final.txt" || fail=1
  grep -q "new: none" "$R/$P-final.txt" || fail=1
  "$PYK" gen_standoff.py stats "$FB" "$R/$P-drc.json" e "$TMP/final-stats.json" 2>&1 | q > /dev/null
  "$PYK" finish_v2.py fab-e "$FB" 2>&1 | q | tee "$R/$P-fab.txt" | sed 's/^/  /'
  grep -q "in the NPTH file: yes" "$R/$P-fab.txt" || fail=1
  "$PYK" gen_standoff.py geom "$FB" e "$TMP/final-geom.json" "$TMP/final-stats.json" final 2>&1 | q | sed 's/^/  /'
  python3 print_1to1.py "$TMP/final-geom.json" "$HERE/$P-1to1.pdf" 2>&1 | sed 's/^/  /'
else
  echo "  $P.kicad_pcb missing (FINAL=trial or FINAL=route makes it)"; fail=1
fi

# k: the blocked keep-the-built-copper options (the record, options-keep-copper/): regenerated only on request, with
# the built card's rules
for o in $KEEPCOPPER; do
  B="$K/$P-option-$o.kicad_pcb"
  echo "== k$o  keep-copper option $o (record) =="
  "$PYK" gen_mem_v2.py board "$o" "$R/$P.net" 2>&1 | q || { fail=1; continue; }
  "$PYK" gen_mem_v2.py locked "$B" "$OLD.kicad_pcb" "$K/reports/option-$o-locked.txt" 2>&1 | q | sed 's/^/  /'
  "$PYK" gen_mem_v2.py refill "$B" 2>&1 | q
  "$PYK" gen_mem_v2.py check "$B" "$o" 2>&1 | q | tee "$K/reports/option-$o-placement-check.txt" | sed 's/^/  /'
  cp "$TMP/built-rules.kicad_pro" "$K/$P-option-$o.kicad_pro"
  cp "$TMP/built-rules.kicad_dru" "$K/$P-option-$o.kicad_dru"
  drc_parity "$B" "$TMP/built-rules.kicad_pro" "$TMP/built-rules.kicad_dru" "$K/reports/option-$o-drc.json"
  "$PYK" gen_mem_v2.py review "$B" "$TMP/r.kicad_pcb" render 2>&1 | q
  "$CLI" pcb render --side top --width 2000 --height 1400 -o "$K/$P-option-$o-render-top.png" "$TMP/r.kicad_pcb" >/dev/null 2>&1
  "$PYK" gen_mem_v2.py review "$B" "$TMP/p2.kicad_pcb" plot 2>&1 | q | sed 's/^/  /'
  "$CLI" pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet \
    -l Edge.Cuts,F.Cu,B.Cu,F.Silkscreen,User.Drawings,User.Eco1 -o "$TMP/p2.svg" "$TMP/p2.kicad_pcb" >/dev/null 2>&1
  "$INK" "$TMP/p2.svg" --export-type=png --export-width=2400 --export-background=white \
    --export-filename="$K/$P-option-$o-placement.png" >/dev/null 2>&1
done
if [ -n "$KEEPCOPPER" ]; then
  echo "== ks space check (space_check.py, record) =="
  "$PYK" space_check.py 2000 2>&1 | q | sed 's/^/  /'
fi

# 4: the top-edge record's finished board (options-top-edge-J2/memory-v2.0.kicad_pcb, remade only on request)
if [ -n "$ROUTE" ]; then
  echo "== 4  route option B anew: $ROUTES Freerouting runs =="
  best=""
  i=1
  while [ $i -le "$ROUTES" ]; do
    mkdir -p "$TMP/final$i"
    "$PYK" gen_relayout.py dsn "$T/$P-relayout-b.kicad_pcb" "$TMP/final$i/b.dsn" 2>&1 | q | sed 's/^/  /'
    ( freeroute "$TMP/final$i/b.dsn" "$TMP/final$i/b.ses" "$TMP/final$i/freerouting.log" ) &
    i=$((i + 1))
  done
  wait
  i=1
  : > "$TMP/routes.txt"
  while [ $i -le "$ROUTES" ]; do
    if [ -f "$TMP/final$i/b.ses" ]; then
      "$PYK" gen_relayout.py ses "$T/$P-relayout-b.kicad_pcb" "$TMP/final$i/b.ses" "$TMP/final$i/b.kicad_pcb" 2>&1 | q | sed 's/^/  /'
      cp "$T/$P-relayout-b.kicad_pro" "$TMP/final$i/b.kicad_pro"; cp "$T/$P-relayout-b.kicad_dru" "$TMP/final$i/b.kicad_dru"
      "$PYK" gen_relayout.py refill "$TMP/final$i/b.kicad_pcb" 2>&1 | q
      "$CLI" pcb drc --severity-all --format json -o "$TMP/final$i/drc.json" "$TMP/final$i/b.kicad_pcb" >/dev/null 2>&1
      "$PYK" gen_relayout.py stats "$TMP/final$i/b.kicad_pcb" "$TMP/final$i/drc.json" b 2>&1 | q > "$TMP/final$i/stats.txt"
      u=$(sed -n 's/.*after Freerouting: \([0-9]*\).*/\1/p' "$TMP/final$i/stats.txt")
      v=$(sed -n 's/^  vias: \([0-9]*\).*/\1/p' "$TMP/final$i/stats.txt")
      l=$(sed -n 's/^  track length: \([0-9]*\) mm.*/\1/p' "$TMP/final$i/stats.txt")
      echo "  run $i: unrouted $u, vias $v, track $l mm"
      echo "$u $v $l $i" >> "$TMP/routes.txt"
    fi
    i=$((i + 1))
  done
  pick=$(sort -n -k1,1 -k2,2 -k3,3 "$TMP/routes.txt" | head -1 | awk '$1 == 0 {print $4}')
  if [ -n "$pick" ]; then
    echo "  best: run $pick"
    cp "$TMP/final$pick/freerouting.log" "$RT/$P-freerouting.log"
    "$PYK" finish_v2.py make "$TMP/final$pick/b.kicad_pcb" "$BRD" 2>&1 | q | tee "$RT/$P-make.txt" | sed 's/^/  /'
  else
    echo "  NO COMPLETE ROUTE - the committed board stays"; fail=1
  fi
elif [ "$FROM" = "trial" ]; then
  echo "== 4  final board from the committed option-B trial route =="
  "$PYK" finish_v2.py make "$T/$P-relayout-b-trial.kicad_pcb" "$BRD" 2>&1 | q | tee "$RT/$P-make.txt" | sed 's/^/  /'
fi

echo "== 5  DRC + verify of the top-edge record's finished board (options-top-edge-J2/$P.kicad_pcb) =="
"$PYK" gen_relayout.py check "$BRD" b 2>&1 | q | tee "$RT/$P-placement-check.txt" | sed 's/^/  /'
grep -q ": OK" "$RT/$P-placement-check.txt" || fail=1
drc_parity "$BRD" "$T/$P.kicad_pro" "$T/$P.kicad_dru" "$RT/$P-drc.json" "$RT/$P-drc.rpt"
{ "$PYK" finish_v2.py verify "$BRD" "$RT/$P-drc.json" 2>&1 | q
  python3 - "$RT/$P-drc.json" "$TMP/v1.3-drc.json" <<'EOF'
import json, sys, collections
x1 = lambda v: v["type"] == "items_not_allowed" and all(" of X1" in i["description"] for i in v["items"])
d, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
cd = collections.Counter(v["type"] for v in d["violations"])
cb = collections.Counter(v["type"] for v in b["violations"])
print("  DRC by type, v2.0 / built v1.3 (its own rules): %s"
      % ", ".join("%s %d/%d" % (t, cd.get(t, 0), cb.get(t, 0)) for t in sorted(set(cd) | set(cb))))
print("  DRC unconnected, v2.0 / built v1.3: %d/%d" % (len(d.get("unconnected_items", [])),
                                                        len(b.get("unconnected_items", []))))
EOF
  parity_new "$RT/$P-drc.json"; } | tee "$RT/$P-final.txt" | sed 's/^/  /'
grep -q -- "-> PASS" "$RT/$P-final.txt" || fail=1
grep -q "new: none" "$RT/$P-final.txt" || fail=1

echo "== 6  netlist proof =="
finals=""
for f in "$P"-standoff-?.kicad_pcb "$P"-standoff-?-trial.kicad_pcb "$FB" "$BRD"; do
  [ -f "$f" ] && finals="$finals $f"
done
for f in "$T/$P"-relayout-?.kicad_pcb "$T/$P"-relayout-?-trial.kicad_pcb "$K"/$P-option-?.kicad_pcb; do
  [ -f "$f" ] && boards="$boards $f"
done
python3 check_netlist.py "$R/$P.net" "$TMP/v1.3.net" "$OLD.kicad_pcb" $finals --records $boards | tee "$R/netlist-proof.txt" | sed 's/^/  /'
grep -q "^RESULT: MATCH" "$R/netlist-proof.txt" || fail=1

echo "== 7  schematic PDF, BOM (+ the top-edge record's fab outputs after FROM / ROUTE) =="
if [ -n "$ROUTE" ] || [ "$FROM" = "trial" ]; then
  "$PYK" finish_v2.py fab "$BRD" 2>&1 | q | sed 's/^/  /'
fi
"$CLI" sch export pdf -o "$HERE/$P-schematic.pdf" "$P.kicad_sch" >/dev/null 2>&1 && echo "  schematic PDF -> $P-schematic.pdf"
"$CLI" sch export bom --fields 'Reference,Value,Footprint,${QUANTITY}' --labels 'Refs,Value,Footprint,Qty' \
  --group-by 'Value,Footprint' --sort-field 'Reference' -o "$HERE/$P-bom.csv" "$P.kicad_sch" >/dev/null 2>&1 \
  && "$PYK" finish_v2.py bom-hw "$HERE/$P-bom.csv" 2>&1 | q | sed 's/^/  /' \
  && echo "  BOM -> $P-bom.csv ($(python3 -c "
import csv
r = [x for x in csv.DictReader(open('$HERE/$P-bom.csv')) if x['Refs'] != 'H1,H2' and not x['Refs'].startswith('HW')]
print('%d part lines, %d parts' % (len(r), sum(int(x['Qty']) for x in r)))") + H1/H2 + hardware lines)"
rm -f "$HERE"/*.kicad_prl "$K"/*.kicad_prl "$T"/*.kicad_prl "$HERE/fp-info-cache"

[ $fail -eq 0 ] && echo "== BUILD PASS ==" || echo "== BUILD FAIL (see above) =="
exit $fail

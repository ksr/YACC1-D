#!/bin/sh
# build.sh - build and verify the YACC1 I/O card v2.0 (v1.1 + the CF section): the routed board io-v2.0.kicad_pcb.
#
#   hardware/cards/io/kicad/v2.0/build.sh                 schematic + ERC, verify the routed board, fab outputs (~2 min)
#   ROUTE=1 hardware/cards/io/kicad/v2.0/build.sh         + re-route the board from option B (~40-60 min; a new,
#                                                           equally valid routing each time: Freerouting is not
#                                                           deterministic, so the committed board is the master)
#   OPTIONS="a b c" hardware/cards/io/kicad/v2.0/build.sh + regenerate the placement-option review boards in options/
#
# 1 gen_io_v2.py sch: schematic (v1.1 sheets 1-6 + sheet 7 CF) + project (net classes) + libraries
# 2 ERC (must equal v1.1's residual list + the one designed-in SRST single-pin label)
# 3 (OPTIONS) per option: board from v1.1 + moves + CF placement, trim, placement check, DRC, review images (options/)
# 4 (ROUTE) route_v2.py prep: options/io-v2.0-option-b.kicad_pcb (Ken's choice, 2026-09-23) -> io-v2.0.kicad_pcb, the
#   kept v1.1 copper locked, JP2 moved clear of the adapter, reference texts tidied, the adapter strip on F.Fab;
#   Freerouting stage A = the signal nets with a broken v1.1 connection, alone, + the grid router for what it leaves;
#   stage B = everything else (stage A fixed); route_v2.py finish --rip: dangling router stubs removed, leftovers
#   routed by the grid router, which may rip up router copper (never the kept v1.1 copper) and re-route it
# 5 DRC of io-v2.0.kicad_pcb with schematic parity: 0 unconnected, no copper violation v1.1 does not have, no silk
#   collision on a new or moved part's reference, and every kept v1.1 track/via still exactly where option B had it
# 6 netlist proof: v2.0 schematic = v1.1 schematic + CF section, and every board = the schematic (check_netlist.py)
# 7 fab: gerbers/ + drill + zip, top/bottom renders, placement PDF, schematic PDF, BOM
# Exit status non-zero if a gate fails.
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
PYK=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
INK=/Applications/Inkscape.app/Contents/MacOS/inkscape
FRJAR="${FRJAR:-$HOME/freerouting/freerouting.jar}"
KR="$ROOT/tools/kicad/kicad_route.py"
WATCHDOG=${WATCHDOG:-1500}
P=io-v2.0
BRD="$HERE/$P.kicad_pcb"
R="$HERE/reports"
OPTIONS=${OPTIONS:-""}
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
q() { grep --line-buffered -vE 'Debug|assert|wxApp|traits|Fontconfig|memory leak|^$'; }
fail=0
mkdir -p "$R" "$HERE/options"
cd "$HERE" || exit 1
TMP=$(mktemp -d /tmp/io-v2-build.XXXXXX)
trap 'rm -rf "$TMP"' EXIT

echo "== 1  schematic (gen_io_v2.py sch) =="
"$PYK" gen_io_v2.py sch 2>&1 | q || exit 1
"$CLI" sch export netlist --format kicadsexpr -o "$R/$P.net" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" sch export netlist --format kicadsexpr -o "$TMP/v1.1.net" ../v1.1/io-v1.1.kicad_sch >/dev/null 2>&1

echo "== 2  ERC =="
"$CLI" sch erc --severity-all -o "$R/$P-erc.rpt" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" sch erc --severity-all --format json -o "$R/$P-erc.json" "$P.kicad_sch" >/dev/null 2>&1
"$CLI" sch erc --severity-all --format json -o "$TMP/v1.1-erc.json" ../v1.1/io-v1.1.kicad_sch >/dev/null 2>&1
python3 - "$R/$P-erc.json" "$TMP/v1.1-erc.json" <<'EOF' | tee "$R/erc-summary.txt" || fail=1
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
print("  ERC v1.1: %d violations (the Eagle-conversion residue, ../v1.1/README.md)" % sum(v1.values()))
print("  new on v2.0: %s; gone: %s" % ([(k[1], k[2]) for k in new] or "none", [(k[1], k[2]) for k in gone] or "none"))
unexpected = [k for k in new if not (k[1] == "isolated_pin_label" and k[2] == ("Label 'SRST'",))]
print("  unexplained: %d -> %s" % (len(unexpected), "PASS" if not unexpected else "FAIL"))
sys.exit(0 if not unexpected else 1)
EOF
"$CLI" pcb drc --schematic-parity --severity-all --format json -o "$TMP/v1.1-drc.json" ../v1.1/io-v1.1.kicad_pcb >/dev/null 2>&1

# the DRC comparison with v1.1 (used for the options and for the routed board)
cat > "$TMP/drccmp.py" <<'EOF'
import json, sys, collections, re
d, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
routed = len(sys.argv) > 4 and sys.argv[4] == "routed"
c = collections.Counter(v["type"] for v in d["violations"])
cb = collections.Counter(v["type"] for v in b["violations"])
COSMETIC = {"silk_overlap", "silk_edge_clearance", "silk_over_copper", "text_height", "text_thickness",
            "lib_footprint_mismatch", "lib_footprint_issues"}
copper = {t: n for t, n in c.items() if t not in COSMETIC and n > cb.get(t, 0)}
unc = len(d.get("unconnected_items", []))
# parity: v1.1's own (run beside its converted schematic) has the Eagle net names (net_conflict, gone here) and the
# Eagle board values / 'Eagle name' fields; anything beyond those is new
bpar = {(x["type"], x["description"]) for x in b.get("schematic_parity", []) if x["type"] != "net_conflict"}
newpar = [x["description"] for x in d.get("schematic_parity", []) if (x["type"], x["description"]) not in bpar]
print("     schematic parity: %d items, all inherited from v1.1's Eagle values/fields; new: %s"
      % (len(d.get("schematic_parity", [])), newpar or "none"))
kept = len(re.findall(r"^\t\((segment|via|arc)\b", open(sys.argv[3]).read(), re.M))
print("DRC: %s; v1.1 had %s" % (dict(sorted(c.items())), dict(sorted(cb.items()))))
ok = not copper and not newpar
if routed:
    import route_check
    silk = route_check.silk_on_parts(d)
    print("     unrouted connections %d; copper items (tracks + vias) %d" % (unc, kept))
    print("     silk collisions on a new or moved part's reference text: %d %s" % (len(silk), silk[:6]))
    ok = ok and unc == 0 and not silk
else:
    print("     unrouted connections (ratsnest) %d; v1.1 copper items (tracks + vias) kept %d of 1567" % (unc, kept))
print("     non-cosmetic violations beyond v1.1's: %s -> %s" % (copper or "none", "PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
EOF

# 3: the placement options (the review record; regenerated only on request)
for o in $OPTIONS; do
  B="options/$P-option-$o.kicad_pcb"
  echo "== 3$o  option $o =="
  "$PYK" gen_io_v2.py board "$o" "$R/$P.net" 2>&1 | q || { fail=1; continue; }
  "$PYK" gen_io_v2.py trim "$B" ../v1.1/io-v1.1.kicad_pcb 2>&1 | q
  "$PYK" gen_io_v2.py check "$B" "$o" 2>&1 | q | tee "$R/option-$o-placement-check.txt" | sed 's/^/  /'
  grep -q ": OK" "$R/option-$o-placement-check.txt" || fail=1
  cp "$HERE/$P.kicad_pro" "$HERE/options/$P-option-$o.kicad_pro"
  # DRC with schematic parity: the board needs the schematic beside it under the same name
  rm -rf "$TMP/p"; mkdir "$TMP/p"
  cp -R "$HERE"/*.kicad_sch "$HERE/$P.kicad_pro" "$HERE"/*-lib-table "$HERE"/io-v1.1-eagle.* "$TMP/p/"
  cp "$B" "$TMP/p/$P.kicad_pcb"
  "$CLI" pcb drc --schematic-parity --severity-all --format json -o "$R/option-$o-drc.json" "$TMP/p/$P.kicad_pcb" >/dev/null 2>&1
  python3 "$TMP/drccmp.py" "$R/option-$o-drc.json" "$TMP/v1.1-drc.json" "$B" | tee "$R/option-$o-drc-summary.txt" | sed 's/^/  /' || fail=1
  "$PYK" gen_io_v2.py review "$B" "$TMP/r.kicad_pcb" render 2>&1 | q
  "$CLI" pcb render --side top --width 2000 --height 1400 -o "$HERE/options/$P-option-$o-render-top.png" "$TMP/r.kicad_pcb" >/dev/null 2>&1 \
    && echo "  render -> options/$P-option-$o-render-top.png"
  "$PYK" gen_io_v2.py review "$B" "$TMP/p2.kicad_pcb" plot 2>&1 | q | sed 's/^/  /'
  "$CLI" pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet \
    -l Edge.Cuts,F.Cu,B.Cu,F.Silkscreen,User.Drawings,User.Eco1 -o "$TMP/p2.svg" "$TMP/p2.kicad_pcb" >/dev/null 2>&1
  "$INK" "$TMP/p2.svg" --export-type=png --export-width=2400 --export-background=white \
    --export-filename="$HERE/options/$P-option-$o-placement.png" >/dev/null 2>&1 && echo "  plot   -> options/$P-option-$o-placement.png"
done

# 4: routing
freeroute() {   # freeroute <dsn> <ses> <log> [extra args]: Freerouting 1.9, one thread, watchdog
  dsn=$1; ses=$2; log=$3; shift 3
  rm -f "$ses"; t0=$(date +%s)
  java -jar "$FRJAR" -de "$dsn" -do "$ses" -mp 30 -oit 100 -mt 1 "$@" > "$log" 2>&1 &
  jp=$!
  while kill -0 $jp 2>/dev/null; do
    if [ $(( $(date +%s) - t0 )) -gt "$WATCHDOG" ]; then
      echo "  watchdog: Freerouting still running after ${WATCHDOG}s - killed"; kill $jp; sleep 2; kill -9 $jp 2>/dev/null
      break
    fi
    sleep 5
  done
  wait $jp 2>/dev/null
  [ -f "$HERE/logs/freerouting.log" ] && cat "$HERE/logs/freerouting.log" >> "$log" && rm -f "$HERE/logs/freerouting.log"
  rmdir "$HERE/logs" 2>/dev/null
  echo "  $(basename "$ses"): $(( $(date +%s) - t0 )) s ($(grep -oE 'Auto-routing was completed in [0-9a-z. ()]+ seconds' "$log" | tail -1))"
  [ -f "$ses" ] || { echo "  ROUTE FAILED - see $log"; tail -3 "$log"; exit 2; }
}
if [ -n "$ROUTE" ]; then
  echo "== 4  route option B -> $P.kicad_pcb =="
  cp "$P.kicad_pro" "$TMP/project"                  # pcbnew rewrites the project file when it saves a board
  rm -f "$R/route-kept-removed.txt"
  "$PYK" route_v2.py prep "options/$P-option-b.kicad_pcb" "$BRD" 2>&1 | q | sed 's/^/  /'
  "$PYK" route_v2.py first_nets "$BRD" "$R/route-stage-a-nets.txt" 2>&1 | q | sed 's/^/  /'
  echo "  -- stage A: Freerouting, only the signal nets with a broken v1.1 connection"
  "$PYK" "$KR" export_dsn "$BRD" 2>&1 | q | sed 's/^/  /'
  "$PYK" route_v2.py dsn_split "$P.dsn" "$R/route-stage-a-nets.txt" 2>&1 | q | sed 's/^/  /'
  freeroute "$P.dsn" "$TMP/stage-a.ses" "$R/freerouting-stage-a.log" -inc kicad_default,Power
  "$PYK" route_v2.py import "$BRD" "$TMP/stage-a.ses" --lock 2>&1 | q | sed 's/^/  /'
  "$PYK" route_v2.py finish "$BRD" "$R/route-stage-a-nets.txt" --lock 2>&1 | q | tee "$R/route-finish-stage-a.txt" | sed 's/^/  /'
  echo "  -- stage B: Freerouting, everything else (stage A fixed)"
  "$PYK" "$KR" export_dsn "$BRD" 2>&1 | q | sed 's/^/  /'
  freeroute "$P.dsn" "$TMP/stage-b.ses" "$R/freerouting-stage-b.log"
  "$PYK" route_v2.py import "$BRD" "$TMP/stage-b.ses" 2>&1 | q | sed 's/^/  /'
  echo "  -- leftovers: grid router with rip-up of router copper (never the kept v1.1 copper)"
  "$PYK" route_v2.py finish "$BRD" --rip 2>&1 | q | tee "$R/route-finish.txt" | sed 's/^/  /'
  rm -f "$BRD.kept" "$HERE/$P.dsn"
  cp "$TMP/project" "$P.kicad_pro"
fi

echo "== 5  DRC of the routed board ($P.kicad_pcb) =="
"$CLI" pcb drc --schematic-parity --severity-all -o "$R/$P-drc.rpt" "$BRD" >/dev/null 2>&1
"$CLI" pcb drc --schematic-parity --severity-all --format json -o "$R/$P-drc.json" "$BRD" >/dev/null 2>&1
PYTHONPATH="$HERE" python3 "$TMP/drccmp.py" "$R/$P-drc.json" "$TMP/v1.1-drc.json" "$BRD" routed | tee "$R/$P-drc-summary.txt" | sed 's/^/  /' || fail=1
PYTHONPATH="$HERE" python3 -c "import route_check, sys; sys.exit(route_check.main('$HERE/options/$P-option-b.kicad_pcb', '$BRD', '$R/route-kept-removed.txt'))" \
  | tee -a "$R/$P-drc-summary.txt" | sed 's/^/  /' || fail=1

echo "== 6  netlist proof =="
python3 check_netlist.py "$R/$P.net" "$TMP/v1.1.net" ../v1.1/io-v1.1.kicad_pcb "$BRD" options/$P-option-*.kicad_pcb \
  | tee "$R/netlist-proof.txt" | sed 's/^/  /'
grep -q "^RESULT: MATCH" "$R/netlist-proof.txt" || fail=1

echo "== 7  fab outputs, schematic PDF, BOM =="
"$PYK" "$KR" finish "$BRD" 2>&1 | q | sed 's/^/  /'
"$CLI" pcb render --side bottom --quality high --floor -w 1800 -h 1200 -o "$HERE/$P-render-bottom.png" "$BRD" >/dev/null 2>&1 \
  && echo "  render -> $P-render-top.png, $P-render-bottom.png"
"$CLI" sch export pdf -o "$HERE/$P-schematic.pdf" "$P.kicad_sch" >/dev/null 2>&1 && echo "  schematic PDF -> $P-schematic.pdf"
"$CLI" sch export bom --fields 'Reference,Value,Footprint,${QUANTITY}' --labels 'Refs,Value,Footprint,Qty' \
  --group-by 'Value,Footprint' --sort-field 'Reference' -o "$HERE/$P-bom.csv" "$P.kicad_sch" >/dev/null 2>&1 \
  && echo "  BOM -> $P-bom.csv ($(($(wc -l < "$HERE/$P-bom.csv") - 1)) lines)"
rm -f "$HERE"/*.kicad_prl "$HERE"/options/*.kicad_prl "$HERE/fp-info-cache"

[ $fail -eq 0 ] && echo "== BUILD PASS ==" || echo "== BUILD FAIL (see above) =="
exit $fail

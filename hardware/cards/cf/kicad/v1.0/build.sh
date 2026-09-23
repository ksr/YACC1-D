#!/bin/sh
# build.sh - build and verify the YACC1 CF card v1.0 from cf_netlist.py (2026-09-23).
#
#   hardware/cards/cf/kicad/v1.0/build.sh            full build (Freerouting takes a few minutes)
#   NOROUTE=1 hardware/cards/cf/kicad/v1.0/build.sh  schematic + unrouted board + ERC + netlist proof only
#
# 1 gen_cf.py: schematic + placed board + project     5 DRC (0 errors, 0 unconnected required; silk = cosmetic)
# 2 export Specctra DSN (pours left out)              6 ERC
# 3 Freerouting 1.9 (-mt 1, 20-minute watchdog)       7 netlist proof: schematic and board vs cf_netlist.py
# 4 import SES, stitch, edge heal, zone fill          8 fab: gerbers/ + drill + zip, placement PDF, top render, BOM,
#                                                       schematic PDF
# Reports land in reports/. Exit status is non-zero if any gate fails.
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
PYK=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
FRJAR="${FRJAR:-$HOME/freerouting/freerouting.jar}"
KR="$ROOT/tools/kicad/kicad_route.py"
P=yacc1-cf-card
BRD="$HERE/$P.kicad_pcb"; SCH="$HERE/$P.kicad_sch"; R="$HERE/reports"
WATCHDOG=${WATCHDOG:-1200}
export PYTHONDONTWRITEBYTECODE=1
q() { grep -vE 'Debug:|assert|wxApp|traits|Fontconfig|memory leak|^$'; }
fail=0
mkdir -p "$R"
cd "$HERE" || exit 1

echo "== 1/8  schematic + placed board + project (gen_cf.py) =="
"$PYK" "$HERE/gen_cf.py" 2>&1 | q || exit 1
[ -f "$BRD" ] || { echo "  gen_cf.py wrote no board"; exit 1; }

if [ -z "$NOROUTE" ]; then
  echo "== 2/8  export Specctra DSN =="
  "$PYK" "$KR" export_dsn "$BRD" 2>&1 | q
  echo "== 3/8  Freerouting (-mt 1, watchdog ${WATCHDOG}s) =="
  rm -f "$HERE/$P.ses"
  t0=$(date +%s)
  java -jar "$FRJAR" -de "$P.dsn" -do "$P.ses" -mp 30 -oit 100 -mt 1 > "$R/freerouting.log" 2>&1 &
  jp=$!
  while kill -0 $jp 2>/dev/null; do
    if [ $(( $(date +%s) - t0 )) -gt "$WATCHDOG" ]; then
      echo "  watchdog: Freerouting still running after ${WATCHDOG}s - killed"; kill $jp; sleep 2; kill -9 $jp 2>/dev/null
      break
    fi
    sleep 5
  done
  wait $jp 2>/dev/null
  [ -f "$HERE/logs/freerouting.log" ] && mv "$HERE/logs/freerouting.log" "$R/freerouting-internal.log"
  rmdir "$HERE/logs" 2>/dev/null
  echo "  routing took $(( $(date +%s) - t0 )) s ($(grep -oE 'Auto-routing was completed in [0-9.]+ seconds|improved the design by ~[0-9.]+%' "$R/freerouting.log" | tr '\n' ';'))"
  [ -f "$HERE/$P.ses" ] || { echo "  ROUTE FAILED - see reports/freerouting.log"; tail -3 "$R/freerouting.log"; exit 2; }
  echo "== 4/8  import routing + heal + zone fill =="
  "$PYK" "$KR" import_ses "$BRD" "$HERE/$P.ses" 2>&1 | q
else
  echo "== 2-4  routing skipped (NOROUTE) =="
  "$PYK" "$KR" fill "$BRD" 2>&1 | q
fi

echo "== 5/8  DRC =="
"$CLI" pcb drc --schematic-parity --severity-all -o "$R/$P-drc.rpt" "$BRD" >/dev/null 2>&1
"$CLI" pcb drc --schematic-parity --severity-all --format json -o "$R/$P-drc.json" "$BRD" >/dev/null 2>&1
python3 - "$R/$P-drc.json" <<'EOF' || fail=1
import json, sys, collections
d = json.load(open(sys.argv[1]))
COSMETIC = {"silk_overlap", "silk_edge_clearance", "silk_over_copper", "text_height", "text_thickness"}
v = d.get("violations", []) + d.get("schematic_parity", [])
unc = len(d.get("unconnected_items", []))
err = collections.Counter(x["type"] for x in v if x["severity"] == "error")
warn = collections.Counter(x["type"] for x in v if x["severity"] != "error")
blocking = sum(n for t, n in err.items() if t not in COSMETIC) + sum(n for t, n in warn.items() if t not in COSMETIC)
print("  DRC: %d error(s) %s, %d warning(s) %s, %d unconnected, schematic parity %d" % (
    sum(err.values()), dict(err), sum(warn.values()), dict(warn), unc, len(d.get("schematic_parity", []))))
print("  blocking (not silk/text cosmetics): %d -> %s" % (blocking, "PASS" if blocking == 0 and unc == 0 else "FAIL"))
sys.exit(0 if blocking == 0 and unc == 0 else 1)
EOF

echo "== 6/8  ERC =="
"$CLI" sch erc --severity-all -o "$R/$P-erc.rpt" "$SCH" >/dev/null 2>&1
"$CLI" sch erc --severity-all --format json -o "$R/$P-erc.json" "$SCH" >/dev/null 2>&1
python3 - "$R/$P-erc.json" <<'EOF' || fail=1
import json, sys, collections
d = json.load(open(sys.argv[1]))
v = [x for s in d["sheets"] for x in s["violations"]]
c = collections.Counter((x["severity"], x["type"]) for x in v)
print("  ERC: %d violation(s) %s" % (len(v), dict(c)))
# the one expected item: SRST (U3 Q3) is a one-pin net by design (cf_netlist.py: "readable on a test point only")
unexpected = [x for x in v if not (x["type"] == "isolated_pin_label" and "SRST" in str(x["items"]))]
for x in unexpected: print("   ", x["severity"], x["type"], x["description"], [i["description"] for i in x["items"]])
print("  unexplained: %d -> %s" % (len(unexpected), "PASS" if not unexpected else "FAIL"))
sys.exit(0 if not unexpected else 1)
EOF

echo "== 7/8  netlist proof =="
"$CLI" sch export netlist --format kicadsexpr -o "$R/$P.net" "$SCH" >/dev/null 2>&1
python3 "$HERE/compare_netlist.py" "$R/$P.net" "$BRD" | tee "$R/netlist-proof.txt" | sed 's/^/  /'
grep -q "^RESULT: MATCH" "$R/netlist-proof.txt" || fail=1

echo "== 8/8  fab outputs =="
if [ -z "$NOROUTE" ]; then
  "$PYK" "$KR" finish "$BRD" 2>&1 | q
fi
"$CLI" sch export pdf -o "$HERE/$P-schematic.pdf" "$SCH" >/dev/null 2>&1 && echo "  schematic PDF -> $P-schematic.pdf"
"$CLI" sch export bom --fields 'Reference,Value,Footprint,${QUANTITY}' --labels 'Refs,Value,Footprint,Qty' \
  --group-by 'Value,Footprint' --sort-field 'Reference' -o "$HERE/$P-bom.csv" "$SCH" >/dev/null 2>&1 \
  && echo "  BOM -> $P-bom.csv ($(($(wc -l < "$HERE/$P-bom.csv") - 1)) lines)"
rm -f "$HERE/fp-info-cache"

[ $fail -eq 0 ] && echo "== BUILD PASS ==" || echo "== BUILD FAIL (see above) =="
exit $fail

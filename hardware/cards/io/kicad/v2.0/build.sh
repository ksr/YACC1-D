#!/bin/sh
# build.sh - build and verify the YACC1 I/O card v2.0 (v1.1 + the CF section) and its placement options (2026-09-23).
#
#   hardware/cards/io/kicad/v2.0/build.sh            schematic + every option in placements.py
#   OPTIONS="a c" hardware/cards/io/kicad/v2.0/build.sh   only those options
#
# 1 gen_io_v2.py sch: schematic (v1.1 sheets 1-6 + sheet 7 CF) + project + libraries
# 2 ERC (must equal v1.1's residual list + the one designed-in SRST single-pin label)
# 3 per option: board from v1.1 + moves + CF placement; trim the v1.1 copper the moves broke (DRC-driven);
#   placement check (no new body overlaps, pads clear of the edge and the LCD keepout); DRC with schematic parity;
#   review images: <option>-render-top.png (3D, adapter outline shown on silk) and <option>-placement.png (2D:
#   copper, silk, adapter outline, ratsnest from DRC's unconnected items)
# 4 netlist proof: v2.0 schematic = v1.1 schematic + CF section, and every board = the schematic (check_netlist.py)
# 5 schematic PDF, BOM
# The CF section is NOT routed (placement review first). Exit status non-zero if a gate fails.
HERE=$(cd "$(dirname "$0")" && pwd)
PYK=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
INK=/Applications/Inkscape.app/Contents/MacOS/inkscape
P=io-v2.0
R="$HERE/reports"
OPTIONS=${OPTIONS:-"a b c"}
export PYTHONDONTWRITEBYTECODE=1
q() { grep -vE 'Debug|assert|wxApp|traits|Fontconfig|memory leak|^$'; }
fail=0
mkdir -p "$R"
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

boards=""
for o in $OPTIONS; do
  B="$P-option-$o.kicad_pcb"
  echo "== 3$o  option $o =="
  "$PYK" gen_io_v2.py board "$o" "$R/$P.net" 2>&1 | q || { fail=1; continue; }
  "$PYK" gen_io_v2.py trim "$B" ../v1.1/io-v1.1.kicad_pcb 2>&1 | q
  "$PYK" gen_io_v2.py check "$B" "$o" 2>&1 | q | tee "$R/option-$o-placement-check.txt" | sed 's/^/  /'
  grep -q ": OK" "$R/option-$o-placement-check.txt" || fail=1
  cp "$HERE/$P.kicad_pro" "$HERE/$P-option-$o.kicad_pro"
  # DRC with schematic parity: the board needs the schematic beside it under the same name
  rm -rf "$TMP/p"; mkdir "$TMP/p"
  cp -R "$HERE"/*.kicad_sch "$HERE/$P.kicad_pro" "$HERE"/*-lib-table "$HERE"/io-v1.1-eagle.* "$TMP/p/"
  cp "$B" "$TMP/p/$P.kicad_pcb"
  "$CLI" pcb drc --schematic-parity --severity-all --format json -o "$R/option-$o-drc.json" "$TMP/p/$P.kicad_pcb" >/dev/null 2>&1
  "$CLI" pcb drc --schematic-parity --severity-all --format json -o "$TMP/v1.1-drc.json" ../v1.1/io-v1.1.kicad_pcb >/dev/null 2>&1
  python3 - "$R/option-$o-drc.json" "$TMP/v1.1-drc.json" "$B" <<'EOF' | tee "$R/option-$o-drc-summary.txt" | sed 's/^/  /' || fail=1
import json, sys, collections, re
d, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
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
par = len(newpar)
print("     schematic parity: %d items, all inherited from v1.1's Eagle values/fields; new: %s"
      % (len(d.get("schematic_parity", [])), newpar or "none"))
kept = len(re.findall(r"^\t\((segment|via|arc)\b", open(sys.argv[3]).read(), re.M))
print("DRC: %s; v1.1 had %s" % (dict(c), dict(cb)))
print("     unrouted connections (ratsnest) %d; v1.1 copper items (tracks + vias) kept %d of 1567" % (unc, kept))
print("     non-cosmetic violations beyond v1.1's: %s -> %s" % (copper or "none", "PASS" if not copper and not par else "FAIL"))
sys.exit(0 if not copper and not par else 1)
EOF
  # review images
  "$PYK" gen_io_v2.py review "$B" "$TMP/r.kicad_pcb" render 2>&1 | q
  "$CLI" pcb render --side top --width 2000 --height 1400 -o "$HERE/$P-option-$o-render-top.png" "$TMP/r.kicad_pcb" >/dev/null 2>&1 \
    && echo "  render -> $P-option-$o-render-top.png"
  "$PYK" gen_io_v2.py review "$B" "$TMP/p2.kicad_pcb" plot 2>&1 | q | sed 's/^/  /'
  "$CLI" pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet \
    -l Edge.Cuts,F.Cu,B.Cu,F.Silkscreen,User.Drawings,User.Eco1 -o "$TMP/p2.svg" "$TMP/p2.kicad_pcb" >/dev/null 2>&1
  "$INK" "$TMP/p2.svg" --export-type=png --export-width=2400 --export-background=white \
    --export-filename="$HERE/$P-option-$o-placement.png" >/dev/null 2>&1 && echo "  plot   -> $P-option-$o-placement.png"
  boards="$boards $B"
done

echo "== 4  netlist proof =="
python3 check_netlist.py "$R/$P.net" "$TMP/v1.1.net" ../v1.1/io-v1.1.kicad_pcb $boards | tee "$R/netlist-proof.txt" | sed 's/^/  /'
grep -q "^RESULT: MATCH" "$R/netlist-proof.txt" || fail=1

echo "== 5  schematic PDF, BOM =="
"$CLI" sch export pdf -o "$HERE/$P-schematic.pdf" "$P.kicad_sch" >/dev/null 2>&1 && echo "  schematic PDF -> $P-schematic.pdf"
"$CLI" sch export bom --fields 'Reference,Value,Footprint,${QUANTITY}' --labels 'Refs,Value,Footprint,Qty' \
  --group-by 'Value,Footprint' --sort-field 'Reference' -o "$HERE/$P-bom.csv" "$P.kicad_sch" >/dev/null 2>&1 \
  && echo "  BOM -> $P-bom.csv ($(($(wc -l < "$HERE/$P-bom.csv") - 1)) lines)"
rm -f "$HERE"/*.kicad_prl "$HERE/fp-info-cache"

[ $fail -eq 0 ] && echo "== BUILD PASS ==" || echo "== BUILD FAIL (see above) =="
exit $fail

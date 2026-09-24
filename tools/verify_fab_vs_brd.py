#!/usr/bin/env python3
"""Check that an Eagle board file is the design a fab house actually received, by comparing it with the CAM output.

Reads the Eagle .brd (XML) and the gerber/drill set (a zip; a zip nested inside the given zip is searched too, so a
JLCPCB order archive works as-is) and checks, independently of KiCad:
  1. HOLES   every plated/non-plated hole of the board (package pads, package holes, vias, board holes) against the
             Excellon drill file: same position (0.01 mm) and same diameter (0.001 mm), and nothing extra either way.
  2. TRACKS  every copper wire on Top (1) / Bottom (16) against the strokes (D01) in the top / bottom copper gerbers:
             same end points (0.01 mm, either direction) drawn with a round aperture of the wire's width. Gerber strokes
             that match no wire are listed; strokes lying inside a pad (Eagle draws long/oval pads as short strokes)
             are counted separately.
  3. PLANES  polygons on inner layers (2, 15): which net each belongs to, and whether the inner gerbers hold filled
             regions (G36/G37).
  4. PARTS   the fab part list (Assembly/*.txt) and pick-and-place (PnP_*_front.txt, if present) against the
             board's elements: same reference designators; PnP position = element origin or, for packages whose
             origin is off-centre, the centre of the pads (0.01 mm).
  5. SAME    optional --same-as <zip>: every file in both gerber sets byte-identical (compared by basename).
Exit code 0 when 1, 2 and 4 pass (and 5 when asked); the report goes to stdout.
usage: verify_fab_vs_brd.py <board.brd> <gerbers-or-order.zip> [--same-as <other gerber zip>]
"""
import sys, re, io, math, zipfile, hashlib, collections, xml.etree.ElementTree as ET

POS_TOL = 0.01; DRILL_TOL = 0.001

# ----------------------------------------------------------------------------------------------- gerber set
def gerber_files(path):
    """-> {basename: bytes} for the innermost zip that holds a drill file"""
    def walk(zf):
        names = zf.namelist()
        if any(n.lower().endswith((".xln", ".drl", ".txt")) and "drill" in n.lower() for n in names):
            return {n.split("/")[-1]: zf.read(n) for n in names if not n.endswith("/")}
        for n in names:
            if n.lower().endswith(".zip"):
                got = walk(zipfile.ZipFile(io.BytesIO(zf.read(n))))
                if got: return got
        return None
    got = walk(zipfile.ZipFile(path))
    if not got: sys.exit("no drill file found in %s" % path)
    return got

def parse_excellon(text):
    """-> list of (x_mm, y_mm, dia_mm).  Handles METRIC/INCH with TZ/LZ and an explicit 000.000 format."""
    tools = {}; cur = None; holes = []; unit = 1.0; idig = 3; ddig = 3; tz = True
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"(METRIC|INCH)(?:,(TZ|LZ))?(?:,(0+)\.(0+))?", line)
        if m:
            unit = 1.0 if m.group(1) == "METRIC" else 25.4
            tz = m.group(2) != "LZ"   # "TZ" = trailing zeros kept, leading suppressed
            if m.group(3): idig, ddig = len(m.group(3)), len(m.group(4))
            continue
        m = re.match(r"T(\d+)C([\d.]+)", line)
        if m: tools[int(m.group(1))] = float(m.group(2)) * unit; continue
        m = re.match(r"T(\d+)$", line)
        if m: cur = int(m.group(1)); continue
        m = re.match(r"X([-\d.]+)Y([-\d.]+)", line)
        if m and cur is not None:
            def num(s):
                if "." in s: return float(s) * unit
                neg = s.startswith("-"); s = s.lstrip("-")
                v = int(s) / 10 ** ddig if tz else int(s.ljust(idig + ddig, "0")) / 10 ** ddig
                return (-v if neg else v) * unit
            holes.append((num(m.group(1)), num(m.group(2)), tools[cur]))
    return holes

def parse_gerber(text):
    """-> strokes [(x1,y1,x2,y2,aperture_dia or None)], flashes [(x,y)], region count"""
    fmt = re.search(r"%FSLAX(\d)(\d)Y\d\d\*%", text); dec = int(fmt.group(2))
    unit = 25.4 if "%MOIN*%" in text else 1.0
    aps = {}
    for m in re.finditer(r"%ADD(\d+)([A-Za-z0-9_]+),([^*]*)\*%", text):
        aps[int(m.group(1))] = float(m.group(3).split("X")[0]) * unit if m.group(2) == "C" else None
    x = y = 0.0; ap = None; strokes = []; flashes = []; regions = text.count("G36*"); inreg = False
    for tok in text.replace("\n", "").split("*"):
        if tok.startswith("%"): continue
        if tok == "G36": inreg = True; continue
        if tok == "G37": inreg = False; continue
        m = re.fullmatch(r"(?:G54)?D(\d+)", tok)
        if m and int(m.group(1)) >= 10: ap = int(m.group(1)); continue
        m = re.fullmatch(r"(?:G0?1)?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I-?\d+)?(?:J-?\d+)?D0?([123])", tok)
        if m:
            nx = int(m.group(1)) / 10 ** dec * unit if m.group(1) else x
            ny = int(m.group(2)) / 10 ** dec * unit if m.group(2) else y
            op = m.group(3)
            if op == "1" and not inreg: strokes.append((x, y, nx, ny, aps.get(ap)))
            elif op == "3": flashes.append((nx, ny))
            x, y = nx, ny
    return strokes, flashes, regions

# ----------------------------------------------------------------------------------------------- Eagle board
def xform(el, px, py):
    rot = el.get("rot") or "R0"
    mirror = "M" in rot; ang = float(re.sub(r"[^\d.]", "", rot) or 0)
    if mirror: px = -px
    a = math.radians(ang); c, s = math.cos(a), math.sin(a)
    return float(el.get("x")) + px * c - py * s, float(el.get("y")) + px * s + py * c

def parse_brd(path):
    root = ET.parse(path).getroot(); b = root.find("drawing/board")
    pkgs = {}
    for lib in b.findall("libraries/library"):
        for p in lib.findall("packages/package"):
            pkgs[(lib.get("name"), p.get("name"))] = p
    holes = []; pads = []   # holes: (x, y, dia, what); pads: (x, y, half-size) for the stroke-in-pad test
    elements = {}
    for el in b.findall("elements/element"):
        elements[el.get("name")] = (float(el.get("x")), float(el.get("y")), el.get("rot") or "R0", el.get("package"))
        p = pkgs[(el.get("library"), el.get("package"))]
        for pad in p.findall("pad"):
            x, y = xform(el, float(pad.get("x")), float(pad.get("y"))); d = float(pad.get("drill"))
            holes.append((x, y, d, "%s.%s" % (el.get("name"), pad.get("name"))))
            dia = float(pad.get("diameter") or 0) or d * 2
            pads.append((x, y, max(dia, d * 2) * (2 if pad.get("shape") == "long" else 1) / 2 + 0.01))
        for h in p.findall("hole"):
            x, y = xform(el, float(h.get("x")), float(h.get("y")))
            holes.append((x, y, float(h.get("drill")), "%s hole" % el.get("name")))
    for h in b.findall("plain/hole"):
        holes.append((float(h.get("x")), float(h.get("y")), float(h.get("drill")), "board hole"))
    wires = collections.defaultdict(list); polys = []; nvias = 0
    for s in b.findall("signals/signal"):
        for v in s.findall("via"):
            holes.append((float(v.get("x")), float(v.get("y")), float(v.get("drill")), "via %s" % s.get("name"))); nvias += 1
        for w in s.findall("wire"):
            wires[w.get("layer")].append((float(w.get("x1")), float(w.get("y1")), float(w.get("x2")), float(w.get("y2")),
                                          float(w.get("width")), s.get("name"), w.get("curve")))
        for pg in s.findall("polygon"):
            polys.append((pg.get("layer"), s.get("name")))
    return dict(holes=holes, pads=pads, wires=wires, polys=polys, elements=elements, nvias=nvias)

# ----------------------------------------------------------------------------------------------- checks
def near(a, b, tol=POS_TOL): return abs(a - b) <= tol

def match_holes(brd_holes, drill):
    left = list(drill); missing = []
    grid = collections.defaultdict(list)
    for i, (x, y, d) in enumerate(left): grid[(round(x, 1), round(y, 1))].append(i)
    used = set()
    for x, y, d, what in brd_holes:
        hit = None
        for gx in (round(x, 1) - 0.1, round(x, 1), round(x, 1) + 0.1):
            for gy in (round(y, 1) - 0.1, round(y, 1), round(y, 1) + 0.1):
                for i in grid.get((round(gx, 1), round(gy, 1)), []):
                    if i not in used and near(drill[i][0], x) and near(drill[i][1], y):
                        hit = i; break
                if hit is not None: break
            if hit is not None: break
        if hit is None: missing.append((x, y, d, what, "no drill hit"))
        elif abs(drill[hit][2] - d) > DRILL_TOL: missing.append((x, y, d, what, "drill file says %.3f" % drill[hit][2])); used.add(hit)
        else: used.add(hit)
    extra = [drill[i] for i in range(len(drill)) if i not in used]
    return missing, extra

def match_tracks(wires, strokes, pads):
    key = lambda x1, y1, x2, y2: tuple(sorted([(round(x1, 2), round(y1, 2)), (round(x2, 2), round(y2, 2))]))
    pool = collections.defaultdict(list)
    for i, (x1, y1, x2, y2, d) in enumerate(strokes): pool[key(x1, y1, x2, y2)].append(i)
    used = set(); missing = []
    for x1, y1, x2, y2, w, net, curve in wires:
        cand = [i for i in pool.get(key(x1, y1, x2, y2), []) if i not in used and strokes[i][4] is not None and abs(strokes[i][4] - w) <= 0.001]
        if curve: missing.append((x1, y1, x2, y2, w, net, "arc (not checked)")); continue
        if cand: used.add(cand[0])
        else: missing.append((x1, y1, x2, y2, w, net, "no matching stroke"))
    def in_pad(x, y): return any(abs(x - px) <= r and abs(y - py) <= r for px, py, r in pads)
    extra = [s for i, s in enumerate(strokes) if i not in used]
    on_pads = [s for s in extra if in_pad(s[0], s[1]) and in_pad(s[2], s[3])]
    other = [s for s in extra if s not in on_pads]
    return missing, on_pads, other

def parts_check(files, elements, holes):
    out = []; ok = True
    centre = {}
    for ref in elements:   # pad bounding-box centre: Fusion's pick-and-place uses it when the package origin is off-centre
        ps = [(x, y) for x, y, d, w in holes if w.startswith(ref + ".")]
        if ps: centre[ref] = ((min(p[0] for p in ps) + max(p[0] for p in ps)) / 2, (min(p[1] for p in ps) + max(p[1] for p in ps)) / 2)
    for n in [n for n in files if n.lower().endswith(".txt") and not n.lower().startswith("pnp")]:
        lines = files[n].decode("latin-1").splitlines()
        hdr = [i for i, l in enumerate(lines) if l.startswith("Qty") and " Parts " in l]
        if not hdr: continue
        h = lines[hdr[0]]; a, b = h.index("Parts"), h.index("Description")
        refs = set()
        for l in lines[hdr[0] + 1:]:
            refs.update(r.strip() for r in l[a:b].split(",") if r.strip())
        pa, pb = sorted(refs - set(elements)), sorted(set(elements) - refs)
        out.append("part list %s: %d references; only in the part list %s; only on the board %s" % (n, len(refs), pa or "none", pb or "none"))
        ok &= not pa and not pb
    for n in [n for n in files if n.lower().startswith("pnp") and n.lower().endswith(".txt")]:
        bad = []; cnt = 0; byc = []
        for line in files[n].decode("latin-1").splitlines():
            f = line.split("\t")
            if len(f) < 3 or f[0] not in elements: continue
            cnt += 1; x, y = float(f[1]), float(f[2]); ex, ey = elements[f[0]][:2]
            if near(x, ex) and near(y, ey): continue
            c = centre.get(f[0])
            if c and near(x, c[0]) and near(y, c[1]): byc.append(f[0]); continue
            bad.append((f[0], f[1], f[2], ex, ey))
        out.append("pick-and-place %s: %d parts, all at the board's coordinates (%s at the pad centre, the rest at the origin); %d differ %s"
                   % (n, cnt, ", ".join(byc) or "none", len(bad), bad[:6] if bad else ""))
        ok &= not bad
    return out, ok

def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    brdp, zp = argv[0], argv[1]; same = argv[argv.index("--same-as") + 1] if "--same-as" in argv else None
    B = parse_brd(brdp); files = gerber_files(zp); ok = True
    print("board   :", brdp); print("gerbers :", zp, "(%d files)" % len(files))
    drill_name = [n for n in files if n.lower().endswith(".xln") or (n.lower().endswith((".drl", ".txt")) and "drill" in n.lower())][0]
    drill = parse_excellon(files[drill_name].decode("latin-1"))
    missing, extra = match_holes(B["holes"], drill)
    kinds = collections.Counter(("via" if w.startswith("via") else "hole" if "hole" in w else "pad") for *_, w in B["holes"])
    print("\n1. HOLES: board %d (%d pads, %d vias, %d holes), drill file %s %d; board holes not in the drill file %d; drill hits not on the board %d"
          % (len(B["holes"]), kinds["pad"], kinds["via"], kinds["hole"], drill_name, len(drill), len(missing), len(extra)))
    for m in missing[:20]: print("   MISSING", m)
    for e in extra[:20]: print("   EXTRA  ", e)
    sizes = collections.Counter(round(d, 3) for *_, d in drill)
    print("   drill sizes (mm: count):", ", ".join("%.3f: %d" % kv for kv in sorted(sizes.items())))
    ok &= not missing and not extra
    names = {"1": "copper_top", "16": "copper_bottom"}
    for layer, label in (("1", "Top"), ("16", "Bottom")):
        gname = [n for n in files if n.startswith(names[layer])]
        if not gname: print("\n2. TRACKS %s: no %s gerber" % (label, names[layer])); ok = False; continue
        strokes, flashes, regions = parse_gerber(files[gname[0]].decode("latin-1"))
        miss, onpad, other = match_tracks(B["wires"][layer], strokes, B["pads"])
        widths = collections.Counter(round(w[4], 4) for w in B["wires"][layer])
        print("\n2. TRACKS %s: board %d wires, gerber %s %d strokes + %d flashes + %d regions; wires with no matching stroke %d; "
              "unmatched strokes inside pads (oval/long pads) %d; other unmatched strokes %d"
              % (label, len(B["wires"][layer]), gname[0], len(strokes), len(flashes), regions, len(miss), len(onpad), len(other)))
        print("   wire widths (mm: count):", ", ".join("%.4f: %d" % kv for kv in sorted(widths.items())))
        for m in miss[:20]: print("   MISSING", m)
        for o in other[:20]: print("   EXTRA  ", o)
        ok &= not miss and not other
    print("\n3. PLANES:", ", ".join("layer %s = %s" % p for p in sorted(B["polys"])) or "none")
    for n in sorted(files):
        if n.startswith("copper_inner"):
            s, f, r = parse_gerber(files[n].decode("latin-1")); print("   %s: %d filled regions, %d strokes, %d flashes" % (n, r, len(s), len(f)))
    lines, pok = parts_check(files, B["elements"], B["holes"])
    print("\n4. PARTS: board has %d elements" % len(B["elements"])); [print("   " + l) for l in lines]; ok &= pok
    if same:
        other = gerber_files(same); h = lambda b: hashlib.sha256(b).hexdigest()
        common = sorted(set(files) & set(other)); diff = [n for n in common if h(files[n]) != h(other[n])]
        only = sorted(set(files) ^ set(other))
        print("\n5. SAME AS %s: %d files in common, %d differ %s, %d only on one side %s" % (same, len(common), len(diff), diff, len(only), only))
        ok &= not diff and not only
    print("\nRESULT:", "PASS - the board file is the design in this gerber set" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

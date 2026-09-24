#!/usr/bin/env python3
"""space_check.py - does the CF section fit on the BUILT memory card with all of its copper kept? (2026-09-24)

Run with KiCad's bundled Python (pcbnew, PIL):
    $PYK space_check.py [trials]            -> reports/space-check.txt, memory-v2.0-free-space.png

The built card (../v1.3-fusion-export-2026-09-24) routes the TMP registers' data lines DATA8-15 as a bundle of eight
B.Cu tracks from the bus connector along the bottom edge and diagonally up to IC27/IC29 (the earlier save had those
parts off the board and no such bundle). A through-hole pad cannot sit on a track, so a CF footprint can only go where
none of its pads comes near the built copper. This script finds every such spot and then tries to pack the CF parts:

  1. obstacles = every track and via on F.Cu/B.Cu and every pad of the built card; a pad centre is allowed where it is
     at least PAD_R + CLR from all of them (PAD_R 0.8 mm = a DIP pad; CLR 0.3 mm, above the card's 10 mil track-to-pad
     rule) and 1.4 mm inside the board edge;
  2. a footprint position (0.635 mm grid, rotations 0/90/180/270) is allowed if all its pads are, its courtyard is
     inside the outline and at least 0.2 mm from every built part's body (Eagle footprints: pads + silk outline);
  3. random packing (TRIALS permutations x random choices): the largest number of the five CF DIPs (IC30-IC34) that fit
     at the same time, courtyards 0.2 mm apart - with no IDE header at all, and with J2 where options A and C put it.
The passives (RN9, R10-R14, C25-C30, LED1, J3, JP2) are not even counted: if the DIPs do not fit, nothing does.
"""
import os, sys, json, random, collections
import pcbnew
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mem_v2_netlist as NL                       # noqa: E402
import placements                                  # noqa: E402

T, FM = pcbnew.ToMM, pcbnew.FromMM
BASE = os.path.join(HERE, "..", "v1.3-fusion-export-2026-09-24", "memory-v1.3-fusion-export-2026-09-24.kicad_pcb")
KFP = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
PAD_R, CLR, EDGE, BODY_GAP, STEP, CELL = 0.8, 0.3, 1.4, 0.2, 0.635, 0.127
DIPS = ["IC34", "IC30", "IC32", "IC31", "IC33"]


def load_geometry():
    b = pcbnew.LoadBoard(BASE)
    E = b.GetBoardEdgesBoundingBox()
    edge = (T(E.GetX()), T(E.GetY()), T(E.GetRight()), T(E.GetBottom()))
    segs, pads, bodies = [], [], {}
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            segs.append((T(p.x), T(p.y), T(p.x), T(p.y), T(t.GetWidth(pcbnew.F_Cu)) / 2, "via"))
        elif t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
            segs.append((T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y), T(t.GetWidth()) / 2,
                         "F" if t.GetLayer() == pcbnew.F_Cu else "B"))
    for f in b.GetFootprints():
        bs = [p.GetBoundingBox() for p in f.Pads()] + [g.GetBoundingBox() for g in f.GraphicalItems()
              if g.GetClass() not in ("PCB_TEXT", "PCB_FIELD") and g.GetLayer() in (pcbnew.F_SilkS, pcbnew.F_Fab)]
        bodies[f.GetReference()] = (min(T(q.GetX()) for q in bs), min(T(q.GetY()) for q in bs),
                                    max(T(q.GetRight()) for q in bs), max(T(q.GetBottom()) for q in bs))
        for p in f.Pads():
            q = p.GetBoundingBox()
            pads.append((T(q.GetX()), T(q.GetY()), T(q.GetRight()), T(q.GetBottom())))
    return edge, segs, pads, bodies


def footprint_shapes(ref):
    """rotation -> (pad centres relative to the origin, courtyard box relative to the origin)"""
    lib, name = NL.PARTS[ref][2].split(":")
    fp = pcbnew.FootprintLoad(os.path.join(KFP, lib + ".pretty"), name)
    out = {}
    for r in (0, 90, 180, 270):
        fp.SetOrientationDegrees(r)
        fp.SetPosition(pcbnew.VECTOR2I(0, 0))
        fp.BuildCourtyardCaches()
        q = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        out[r] = ([(T(p.GetPosition().x), T(p.GetPosition().y)) for p in fp.Pads()],
                  (T(q.GetX()), T(q.GetY()), T(q.GetRight()), T(q.GetBottom())))
    return out


class Raster:
    def __init__(self, edge, segs, pads):
        self.x0, self.y0, self.x1, self.y1 = edge
        self.nx, self.ny = int((self.x1 - self.x0) / CELL) + 2, int((self.y1 - self.y0) / CELL) + 2
        self.blk = bytearray(self.nx * self.ny)
        for ax, ay, bx, by, hw, _ in segs:
            self.seg(ax, ay, bx, by, hw + PAD_R + CLR)
        for x0, y0, x1, y1 in pads:
            self.rect(x0, y0, x1, y1, PAD_R + CLR)

    def _range(self, x0, y0, x1, y1):
        return (max(0, int((x0 - self.x0) / CELL)), max(0, int((y0 - self.y0) / CELL)),
                min(self.nx - 1, int((x1 - self.x0) / CELL) + 1), min(self.ny - 1, int((y1 - self.y0) / CELL) + 1))

    def seg(self, ax, ay, bx, by, r):
        ix0, iy0, ix1, iy1 = self._range(min(ax, bx) - r, min(ay, by) - r, max(ax, bx) + r, max(ay, by) + r)
        vx, vy = bx - ax, by - ay
        ll = vx * vx + vy * vy
        for iy in range(iy0, iy1 + 1):
            py = self.y0 + iy * CELL
            for ix in range(ix0, ix1 + 1):
                px = self.x0 + ix * CELL
                s = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / ll))
                dx, dy = px - ax - s * vx, py - ay - s * vy
                if dx * dx + dy * dy < r * r:
                    self.blk[iy * self.nx + ix] = 1

    def rect(self, x0, y0, x1, y1, r):
        ix0, iy0, ix1, iy1 = self._range(x0 - r, y0 - r, x1 + r, y1 + r)
        for iy in range(iy0, iy1 + 1):
            py = self.y0 + iy * CELL
            for ix in range(ix0, ix1 + 1):
                px = self.x0 + ix * CELL
                dx, dy = max(x0 - px, 0, px - x1), max(y0 - py, 0, py - y1)
                if dx * dx + dy * dy < r * r:
                    self.blk[iy * self.nx + ix] = 1

    def free(self, x, y):
        if not (self.x0 + EDGE <= x <= self.x1 - EDGE and self.y0 + EDGE <= y <= self.y1 - EDGE):
            return False
        return not self.blk[int(round((y - self.y0) / CELL)) * self.nx + int(round((x - self.x0) / CELL))]


def overlap(a, b, g=0.0):
    return min(a[2], b[2]) + g - max(a[0], b[0]) > 0 and min(a[3], b[3]) + g - max(a[1], b[1]) > 0


def candidates(R, shapes, bodies, edge_margin=0.3):
    out = []
    y = R.y0
    while y <= R.y1:
        x = R.x0
        while x <= R.x1:
            for r, (pads, cb) in shapes.items():
                bb = (cb[0] + x, cb[1] + y, cb[2] + x, cb[3] + y)
                if bb[0] < R.x0 + edge_margin or bb[1] < R.y0 + edge_margin or bb[2] > R.x1 - edge_margin or \
                        bb[3] > R.y1 - edge_margin:
                    continue
                if all(R.free(px + x, py + y) for px, py in pads) and \
                        not any(overlap(bb, o, BODY_GAP) for o in bodies.values()):
                    out.append((round(x, 3), round(y, 3), r, bb))
            x += STEP
        y += STEP
    return out


def pack(cands, fixed, trials, seed=1):
    rnd = random.Random(seed)
    best, bestpl = -1, None
    for t in range(trials):
        placed = dict(fixed)
        for ref in rnd.sample(DIPS, len(DIPS)):
            ok = [p for p in cands[ref] if all(not overlap(p[3], q[3], BODY_GAP) for q in placed.values())]
            if not ok:
                continue
            placed[ref] = rnd.choice(ok)
        n = len(placed) - len(fixed)
        if n > best:
            best, bestpl = n, placed
        if best == len(DIPS):
            break
    return best, bestpl


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    edge, segs, pads, bodies = load_geometry()
    R = Raster(edge, segs, pads)
    shapes = {ref: footprint_shapes(ref) for ref in DIPS + ["J2"]}
    cands = {ref: candidates(R, shapes[ref], bodies) for ref in DIPS}
    L = ["space_check.py (%s): can the CF section sit on the built memory card with all its copper kept?" % NL.DATE,
         "built card: %d track segments + vias, %d pads, %d parts; pad keep-out %.1f mm + %.1f mm from copper, %.1f mm "
         "inside the edge" % (len(segs), len(pads), len(bodies), PAD_R, CLR, EDGE), ""]
    L.append("allowed positions per CF DIP (0.635 mm grid, 4 rotations): " +
             ", ".join("%s %d" % (r, len(cands[r])) for r in DIPS))
    xs = [p[3] for r in DIPS for p in cands[r]]
    L.append("  all of them lie in x %.1f-%.1f, y %.1f-%.1f (courtyards)"
             % (min(b[0] for b in xs), max(b[2] for b in xs), min(b[1] for b in xs), max(b[3] for b in xs)))
    # area bound: every DIP courtyard must lie inside the union of the allowed courtyards; if the five courtyards
    # together are larger than that union, no packing exists
    cov = bytearray(R.nx * R.ny)
    for r in DIPS:
        for p in cands[r]:
            ix0, iy0, ix1, iy1 = R._range(*p[3])
            for iy in range(iy0, iy1):
                cov[iy * R.nx + ix0: iy * R.nx + ix1] = b"\x01" * (ix1 - ix0)
    union = sum(cov) * CELL * CELL
    need = sum((shapes[r][0][1][2] - shapes[r][0][1][0]) * (shapes[r][0][1][3] - shapes[r][0][1][1]) for r in DIPS)
    L.append("  area: the union of all allowed DIP courtyards is %.0f mm2; the five DIP courtyards need %.0f mm2 "
             "(%s)" % (union, need, "cannot fit, whatever the packing" if need > union else "an area bound alone does not decide it"))
    # the same bound for the whole CF section (all 21 parts, J2 included)
    allrefs = sorted(NL.PARTS)
    for ref in allrefs:
        if ref not in shapes:
            shapes[ref] = footprint_shapes(ref)
    allc = {ref: (cands[ref] if ref in cands else candidates(R, shapes[ref], bodies, 0.0 if ref == "J2" else 0.3))
            for ref in allrefs}
    cov = bytearray(R.nx * R.ny)
    for ref in allrefs:
        for p in allc[ref]:
            ix0, iy0, ix1, iy1 = R._range(*p[3])
            for iy in range(iy0, iy1):
                cov[iy * R.nx + ix0: iy * R.nx + ix1] = b"\x01" * (ix1 - ix0)
    union_all = sum(cov) * CELL * CELL
    need_all = sum((shapes[r][0][1][2] - shapes[r][0][1][0]) * (shapes[r][0][1][3] - shapes[r][0][1][1]) for r in allrefs)
    L.append("  whole CF section (21 parts): allowed courtyards cover %.0f mm2 of the board, the parts need %.0f mm2 (%s); "
             "parts with no allowed position at all: %s"
             % (union_all, need_all, "cannot fit, whatever the packing" if need_all > union_all else "not decided by area",
                [r for r in allrefs if not allc[r]] or "none"))
    results = {}
    for label, fixed in [("no IDE header at all", {})] + [
            ("J2 where option %s puts it %s" % (o.upper(), placements.OPTIONS[o]["place"]["J2"]), {"J2": placements.OPTIONS[o]["place"]["J2"]})
            for o in ("a", "c")]:
        fx = {}
        for ref, (x, y, r) in fixed.items():
            pads_, cb = shapes[ref][r]
            fx[ref] = (x, y, r, (cb[0] + x, cb[1] + y, cb[2] + x, cb[3] + y))
        n, pl = pack(cands, fx, trials)
        results[label] = (n, pl)
        L.append("%-60s at most %d of the 5 DIPs fit together (%d random packings)" % (label + ":", n, trials))
    n0 = results["no IDE header at all"][0]
    L += ["", "RESULT: %s" % ("the five CF DIPs fit" if n0 == 5 else
                              "the CF section does NOT fit on the built card with its copper kept: at most %d of its "
                              "five DIPs fit even without J2 and without any of its 16 other parts" % n0)]
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    open(os.path.join(HERE, "reports", "space-check.txt"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    # picture: built copper, the area where a CF DIP can go, the best packing without J2
    S = 12.0
    W, H = int((R.x1 - R.x0) * S), int((R.y1 - R.y0) * S)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img, "RGBA")
    P = lambda x, y: ((x - R.x0) * S, (y - R.y0) * S)
    for r in DIPS:
        for p in cands[r]:
            d.rectangle([P(p[3][0], p[3][1]), P(p[3][2], p[3][3])], fill=(120, 120, 255, 12))
    for ax, ay, bx, by, hw, ly in segs:
        col = {"F": (200, 40, 40), "B": (40, 90, 200), "via": (90, 90, 90)}[ly]
        if ly == "via":
            d.ellipse([P(ax - hw, ay - hw), P(ax + hw, ay + hw)], fill=col)
        else:
            d.line([P(ax, ay), P(bx, by)], fill=col, width=max(1, int(2 * hw * S)))
    for x0, y0, x1, y1 in pads:
        d.rectangle([P(x0, y0), P(x1, y1)], fill=(60, 60, 60))
    for ref, b in bodies.items():
        d.rectangle([P(b[0], b[1]), P(b[2], b[3])], outline=(170, 150, 0))
    for ref, p in (results["no IDE header at all"][1] or {}).items():
        d.rectangle([P(p[3][0], p[3][1]), P(p[3][2], p[3][3])], outline=(0, 150, 0), width=4)
        d.text(P(p[3][0] + 1, p[3][1] + 1), ref, fill=(0, 120, 0))
    d.rectangle([P(R.x0, R.y0), P(R.x1, R.y1)], outline=(0, 0, 0), width=2)
    d.text((10, 10), "Built memory card: blue haze = where a CF DIP can sit without touching the built copper; "
           "green = the best packing found (%d of 5 DIPs, no IDE header)" % n0, fill=(0, 0, 0))
    img.save(os.path.join(HERE, "memory-v2.0-free-space.png"))
    return 0 if n0 == 5 else 1


if __name__ == "__main__":
    rc = main()
    sys.stdout.flush()
    os._exit(rc)

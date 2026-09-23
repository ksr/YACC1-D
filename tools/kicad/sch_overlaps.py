#!/usr/bin/env python3
"""sch_overlaps.py - measure overlapping text in KiCad schematics (.kicad_sch).

    python3 tools/kicad/sch_overlaps.py [options] <file.kicad_sch | dir> ...

For every sheet it builds approximate boxes for every VISIBLE text item:
  ref / value / field   symbol fields, with KiCad's own placement rule (the box is justified and rotated in the symbol's
                        frame, then carried through the symbol's rotation/mirror; the text is drawn centred in that box,
                        always horizontal or vertical, so it stays readable)
  pinnum / pinname      pin numbers and pin names taken from lib_symbols and transformed by the instance
                        (KiCad hides numbers/names per SYMBOL only - pin_numbers / pin_names (hide yes); a per-pin
                        (hide yes) inside a pin's name/number effects is ignored by KiCad, and so is it here)
  label / glabel / hlabel   local, global, hierarchical labels (a global label includes its flag outline)
  text                  free text (multi-line aware), and text inside symbols (libtext)
and for every symbol the region of its body graphics (convex hull of the rectangles, polylines, arcs, circles, beziers
of the placed unit: a gate's outline, a triangle, an IC box), plus line work: wires, buses, graphic lines, sheet rectangles, pin lines, no-connect crosses.

It reports three kinds of collision, plus the frame check:
  text/text   two visible texts overlap
  text/body   a text lies over a symbol body (a symbol's own pin NAMES inside its own body are by design and not
              counted; its Reference/Value/pin numbers inside its own body ARE counted)
  text/line   a text is crossed by a wire, bus, graphic line or another symbol's pin line (a label's own wire, and a
              pin's own texts against its own pin line, are not counted)
  frame       an item (text, symbol body, wire, pin, graphic line) outside the drawing frame (KiCad's default drawing
              sheet: 12 mm inner border) or on the title block (108 x 28 mm, bottom right)

Character widths are KiCad's stroke-font advances (measured from a kicad-cli SVG export of every ASCII character);
ink width = sum of advances - 0.3 x size; ink height = size. Boxes are shrunk by 0.12 mm before testing, so
touching is not overlapping.

Options:
  --detail N        list the N worst items per sheet (default 5; 0 = none)
  --pairs N         list N example colliding pairs per sheet
  --json FILE       write every sheet's counts and offenders as JSON
  --calibrate SVG   compare the computed text boxes of ONE sheet with the ink boxes in its kicad-cli SVG export
                    (kicad-cli sch export svg -e) and print the fit
  --summary         one line per project directory (sum of its sheets) instead of one per sheet

2026-09-23, for the Eagle->KiCad conversions (tools/kicad/eagle_sch_to_kicad.py) and the CF card (gen_cf.py).
"""
import sys, os, re, math, json, collections

# ------------------------------------------------------------------------------------------------ s-expressions
_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(text):
    stack, cur = [], []
    for t in _TOK.findall(text):
        if t == "(":
            stack.append(cur); cur = []
        elif t == ")":
            done = cur; cur = stack.pop(); cur.append(done)
        else:
            cur.append(t)
    return cur[0]


def unq(t):
    if isinstance(t, str) and t.startswith('"'):
        return t[1:-1].replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
    return t


def kids(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def kid(node, key):
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def num(x, i, d=0.0):
    try:
        return float(x[i])
    except (TypeError, IndexError, ValueError):
        return d


def hidden(node):
    """KiCad writes (hide yes) (v9+), or a bare 'hide' token (v6-8), in effects or directly in the item"""
    for x in node:
        if x == "hide":
            return True
        if isinstance(x, list) and x and x[0] == "hide":
            return len(x) == 1 or x[1] == "yes"
    e = kid(node, "effects")
    return e is not None and e is not node and hidden(e)


def font_of(node):
    e = kid(node, "effects")
    fnt = kid(e, "font") if e else None
    sz = kid(fnt, "size") if fnt else None
    h = num(sz, 1, 1.27) if sz else 1.27
    w = num(sz, 2, h) if sz else h
    j = kid(e, "justify") if e else None
    jus = set(j[1:]) if j else set()
    return h, w, jus


# ------------------------------------------------------------------------------------------------ text metrics
# KiCad stroke font advance per character in units of the font width (kicad-cli SVG textLength of 10 vs 1 copies)
ADV = {'!': .476, '"': .762, '#': 1.0, '$': .952, '%': 1.143, '&': 1.238, "'": .476, '(': .667, ')': .667, '*': .762,
       '+': 1.238, ',': .476, '-': 1.238, '.': .476, '/': 1.048, ':': .476, ';': .476, '<': 1.238, '=': 1.238,
       '>': 1.238, '?': .857, '@': 1.286, 'A': .857, 'B': 1.0, 'C': 1.0, 'D': 1.0, 'E': .905, 'F': .857, 'G': 1.0,
       'H': 1.048, 'I': .476, 'J': .762, 'K': 1.0, 'L': .81, 'M': 1.143, 'N': 1.048, 'O': 1.048, 'P': 1.0, 'Q': 1.048,
       'R': 1.0, 'S': .952, 'T': .762, 'U': 1.048, 'V': .857, 'W': 1.143, 'X': .952, 'Y': .857, 'Z': .952, '[': .667,
       '\\': .667, ']': .667, '^': .571, '_': .762, '`': .381, 'a': .905, 'b': .905, 'c': .857, 'd': .905, 'e': .857,
       'f': .571, 'g': .905, 'h': .905, 'i': .476, 'j': .476, 'k': .81, 'l': .524, 'm': 1.333, 'n': .905, 'o': .905,
       'p': .905, 'q': .905, 'r': .619, 's': .81, 't': .571, 'u': .905, 'v': .762, 'w': 1.048, 'x': .81, 'y': .762,
       'z': .81, '{': .667, '|': .952, '}': .667, '~': .714, ' ': .7}
LINE_PITCH = 1.62          # KiCad interline spacing, x text height


def plain(s):
    """strip KiCad text markup (~{overbar}, _{sub}, ^{super})"""
    return re.sub(r'[~_^]\{([^}]*)\}', r'\1', s)


def text_wh(s, h, w):
    lines = plain(s).split("\n")
    width = max(max(sum(ADV.get(c, .952) for c in ln) * w - 0.3 * w, 0.4 * w) if ln else 0 for ln in lines)
    height = h + (len(lines) - 1) * h * LINE_PITCH
    return width, height


def jbox(w, h, jus):
    """text box relative to its anchor, y UP, unrotated: (x0, y0, x1, y1)"""
    x0 = 0 if "left" in jus else -w if "right" in jus else -w / 2
    # KiCad: justify bottom = text above the anchor (y up), top = below; multi-line text grows downward from line 1
    y0 = 0 if "bottom" in jus else -h if "top" in jus else -h / 2
    return x0, y0, x0 + w, y0 + h


def rot(x, y, a):
    a = a % 360
    if a == 0: return x, y
    if a == 90: return -y, x
    if a == 180: return -x, -y
    if a == 270: return y, -x
    r = math.radians(a)
    return x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)


class Xf:
    """symbol instance transform: local (y up) -> sheet (y down). KiCad rotates first, then mirrors (checked against
    kicad-cli renders of every rotation x mirror combination)."""
    def __init__(self, x, y, a, mirror):
        self.x, self.y, self.a, self.m = x, y, a % 360, mirror

    def vec(self, dx, dy):
        dx, dy = rot(dx, dy, self.a)
        if self.m == "y": dx = -dx
        elif self.m == "x": dy = -dy
        return dx, dy

    def pt(self, lx, ly):
        dx, dy = self.vec(lx, ly)
        return self.x + dx, self.y - dy

    def box(self, ax, ay, rel):
        """rel = (x0,y0,x1,y1) y-up offsets around local anchor (ax, ay) -> sheet box"""
        px, py = self.pt(ax, ay)
        pts = [self.vec(u, v) for u in (rel[0], rel[2]) for v in (rel[1], rel[3])]
        xs = [px + p[0] for p in pts]; ys = [py - p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)


IDENT = Xf(0, 0, 0, None)


def rbox(x0, y0, x1, y1, a):
    """rotate a y-up relative box by a degrees -> y-up relative box"""
    pts = [rot(u, v, a) for u in (x0, x1) for v in (y0, y1)]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def arc_points(a, m, b, n=12):
    """points along the circular arc a -> m -> b"""
    ax, ay = a; bx_, by = b; mx, my = m
    d = 2 * (ax * (my - by) + mx * (by - ay) + bx_ * (ay - my))
    if abs(d) < 1e-9: return [a, m, b]
    ux = ((ax * ax + ay * ay) * (my - by) + (mx * mx + my * my) * (by - ay) + (bx_ * bx_ + by * by) * (ay - my)) / d
    uy = ((ax * ax + ay * ay) * (bx_ - mx) + (mx * mx + my * my) * (ax - bx_) + (bx_ * bx_ + by * by) * (mx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t0, tm, t1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (a, m, b))
    span = (t1 - t0) % (2 * math.pi)
    if (tm - t0) % (2 * math.pi) > span: span -= 2 * math.pi
    return [(ux + r * math.cos(t0 + span * k / n), uy + r * math.sin(t0 + span * k / n)) for k in range(n + 1)]


def hull(pts):
    """convex hull (monotone chain), counter-clockwise"""
    P = sorted(set((round(x, 4), round(y, 4)) for x, y in pts))
    if len(P) <= 2: return P
    cr = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def box_hits_poly(b, poly):
    """axis-aligned box b vs convex polygon (the symbol body outline)"""
    if len(poly) < 3:
        return any(seg_hits(b, *poly[i], *poly[(i + 1) % len(poly)]) for i in range(len(poly))) if poly else False
    if any(b[0] < x < b[2] and b[1] < y < b[3] for x, y in poly): return True
    def inside(x, y):
        sgn = 0
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            c = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
            if c != 0:
                if sgn == 0: sgn = 1 if c > 0 else -1
                elif (c > 0) != (sgn > 0): return False
        return True
    if any(inside(x, y) for x in (b[0], b[2]) for y in (b[1], b[3])): return True
    return any(seg_hits(b, *poly[i], *poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def unit_suffix(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def label_box(kind, s, h, w, x, y, a, jus):
    """sheet box of a label ('label' local, 'glabel' global incl. its flag, 'hlabel') anchored at (x, y).
    KiCad 10 draws labels at 0 or 90 degrees; the justify picks the side: left = runs right/up, right = left/down."""
    tw, th = text_wh(s, h, w)
    vert = a % 360 in (90, 270)
    fwd = "right" not in jus
    if kind == "label":
        along = (0.0, tw); across = (0.25, 0.25 + th)       # text just above (or left of) the wire
    else:
        pad = 0.45 * h
        along = (0.0, tw + h * (1.4 if kind == "glabel" else 1.2)); across = (-th / 2 - pad, th / 2 + pad)
    if not vert and fwd: b = (x + along[0], y - across[1], x + along[1], y - across[0])
    elif not vert: b = (x - along[1], y - across[1], x - along[0], y - across[0])
    elif fwd: b = (x - across[1], y - along[1], x - across[0], y - along[0])
    else: b = (x - across[1], y + along[0], x - across[0], y + along[1])
    return (min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3]))


# ------------------------------------------------------------------------------------------------ paper, frame
PAPER = {"A5": (210, 148), "A4": (297, 210), "A3": (420, 297), "A2": (594, 420), "A1": (841, 594), "A0": (1189, 841),
         "A": (279.4, 215.9), "B": (431.8, 279.4), "C": (558.8, 431.8), "D": (863.6, 558.8), "E": (1117.6, 863.6),
         "USLetter": (279.4, 215.9), "USLegal": (355.6, 215.9), "USLedger": (431.8, 279.4)}
# KiCad's default drawing sheet (measured from a kicad-cli SVG): outer border 10 mm in, inner border 12 mm in; title
# block 108 x 28 mm in the inner border's bottom-right corner
FRAME_IN, TB_W, TB_H = 12.0, 108.0, 28.0


def paper_of(root):
    p = kid(root, "paper")
    if p is None: return 297.0, 210.0
    name = unq(p[1])
    if name == "User": return num(p, 2, 297), num(p, 3, 210)
    w, h = PAPER.get(name, (297, 210))
    return (h, w) if "portrait" in p else (w, h)


def frame_rects(w, h):
    """(drawing area inside the frame, title block) for a w x h page"""
    return (FRAME_IN, FRAME_IN, w - FRAME_IN, h - FRAME_IN), (w - FRAME_IN - TB_W, h - FRAME_IN - TB_H, w - FRAME_IN, h - FRAME_IN)


# ------------------------------------------------------------------------------------------------ sheet model
class Item:
    __slots__ = ("kind", "text", "box", "owner", "ident", "extra")

    def __init__(self, kind, text, box, owner=None, ident=None, extra=None):
        self.kind, self.text, self.box, self.owner, self.ident, self.extra = kind, text, box, owner, ident, extra


class LibSym:
    def __init__(self, node):
        self.name = unq(node[1])
        pn = kid(node, "pin_names")
        self.name_off = 0.508
        self.hide_names = False
        if pn is not None:
            o = kid(pn, "offset")
            if o is not None: self.name_off = num(o, 1, 0.508)
            self.hide_names = hidden(pn)
        pnum = kid(node, "pin_numbers")
        self.hide_nums = pnum is not None and hidden(pnum)
        self.power = kid(node, "power") is not None
        self.units = collections.defaultdict(list)   # (unit, style) -> child nodes
        for sub in kids(node, "symbol"):
            m = re.match(r'.*_(\d+)_(\d+)$', unq(sub[1]))
            if m:
                self.units[(int(m.group(1)), int(m.group(2)))].extend(x for x in sub[2:] if isinstance(x, list))
        self.nunits = max([u for u, s in self.units] + [1])

    def parts(self, unit, style=1):
        out = []
        for (u, s), items in self.units.items():
            if u in (0, unit) and s in (0, style):
                out += items
        return out


def sheet_items(path):
    """-> (texts, bodies, lines) for one .kicad_sch"""
    root = parse(open(path, encoding="utf-8").read())
    libs = {}
    ls = kid(root, "lib_symbols")
    if ls:
        for s in kids(ls, "symbol"):
            libs[unq(s[1])] = LibSym(s)
    texts, bodies, lines = [], [], []
    sheet_items.paper = paper_of(root)
    for sh in kids(root, "sheet"):      # sheet symbols on a hierarchy (root) sheet
        at, sz = kid(sh, "at"), kid(sh, "size")
        bodies.append((num(at, 1), num(at, 2), num(at, 1) + num(sz, 1), num(at, 2) + num(sz, 2), "sheet", "sheet", []))

    def seg(x1, y1, x2, y2, owner=None, kind="wire", w=0.15):
        lines.append((x1, y1, x2, y2, owner, kind, w))

    for n, sym in enumerate(kids(root, "symbol")):
        lid = unq(kid(sym, "lib_id")[1])
        ls_ = libs.get(lid)
        at = kid(sym, "at")
        mir = kid(sym, "mirror")
        xf = Xf(num(at, 1), num(at, 2), num(at, 3), mir[1] if mir else None)
        unit = int(num(kid(sym, "unit"), 1, 1)) if kid(sym, "unit") else 1
        style = int(num(kid(sym, "body_style") or kid(sym, "convert"), 1, 1)) if (kid(sym, "body_style") or kid(sym, "convert")) else 1
        props = {unq(p[1]): p for p in kids(sym, "property")}
        ref = unq(props["Reference"][2]) if "Reference" in props else "?"
        owner = "sym%d:%s" % (n, ref)
        # ---- fields
        for pname, p in props.items():
            if hidden(p): continue
            val = unq(p[2])
            if pname == "Reference" and ls_ and ls_.nunits > 1:
                val = val + unit_suffix(unit)
            if not val or val.startswith("${"): continue
            h, w, jus = font_of(p)
            tw, th = text_wh(val, h, w)
            pat = kid(p, "at")
            fx, fy, fa = num(pat, 1), num(pat, 2), num(pat, 3)
            rel = rbox(*jbox(tw, th, jus), fa)
            # the field position in the file is the displayed anchor; the box offsets go through the symbol transform
            pts = [xf.vec(u, v) for u in (rel[0], rel[2]) for v in (rel[1], rel[3])]
            box = (fx + min(p_[0] for p_ in pts), fy - max(p_[1] for p_ in pts), fx + max(p_[0] for p_ in pts), fy - min(p_[1] for p_ in pts))
            kind = {"Reference": "ref", "Value": "value"}.get(pname, "field")
            if ls_ and ls_.power and pname == "Value": kind = "power"
            texts.append(Item(kind, val, box, owner, "%s %s" % (ref, pname)))
        if ls_ is None:
            continue
        # ---- body graphics, lib texts, pins
        bx = []
        for it in ls_.parts(unit, style):
            t = it[0]
            if t == "rectangle":
                s_, e_ = kid(it, "start"), kid(it, "end")
                a_, b_ = xf.pt(num(s_, 1), num(s_, 2)), xf.pt(num(e_, 1), num(e_, 2))
                bx += [a_, b_]
                c = [a_, (a_[0], b_[1]), b_, (b_[0], a_[1])]
                for i in range(4): seg(*c[i], *c[(i + 1) % 4], owner, "body")
            elif t in ("polyline", "bezier"):
                pts = [xf.pt(num(p, 1), num(p, 2)) for p in kids(kid(it, "pts") or [], "xy")]
                bx += pts
                for a_, b_ in zip(pts, pts[1:]): seg(*a_, *b_, owner, "body")
            elif t == "circle":
                c = kid(it, "center"); r = num(kid(it, "radius"), 1)
                cx, cy = xf.pt(num(c, 1), num(c, 2))
                bx += [(cx - r, cy - r), (cx + r, cy + r)]
                pts = [(cx + r * math.cos(k * math.pi / 8), cy + r * math.sin(k * math.pi / 8)) for k in range(17)]
                for a_, b_ in zip(pts, pts[1:]): seg(*a_, *b_, owner, "body")
            elif t == "arc":
                pts = [xf.pt(num(kid(it, k), 1), num(kid(it, k), 2)) for k in ("start", "mid", "end") if kid(it, k)]
                if len(pts) == 3: pts = arc_points(*pts)
                bx += pts
                for a_, b_ in zip(pts, pts[1:]): seg(*a_, *b_, owner, "body")
            elif t == "text":
                if hidden(it): continue
                s = unq(it[1]); h, w, jus = font_of(it)
                tat = kid(it, "at")
                tw, th = text_wh(s, h, w)
                rel = rbox(*jbox(tw, th, jus), num(tat, 3) / (10 if num(tat, 3) > 360 else 1))
                texts.append(Item("libtext", s, xf.box(num(tat, 1), num(tat, 2), rel), owner, "%s text" % ref))
        if bx:
            bodies.append((min(p[0] for p in bx), min(p[1] for p in bx), max(p[0] for p in bx), max(p[1] for p in bx), owner, ref, hull(bx)))
        for it in ls_.parts(unit, style):
            if it[0] != "pin" or hidden(it): continue
            pat = kid(it, "at")
            L = num(kid(it, "length"), 1, 2.54)
            px, py, pa = num(pat, 1), num(pat, 2), num(pat, 3)
            dx, dy = rot(1, 0, pa)
            (x1, y1), (x2, y2) = xf.pt(px, py), xf.pt(px + dx * L, py + dy * L)
            seg(x1, y1, x2, y2, owner, "pin")
            ux, uy = (x2 - x1) / L if L else 0, (y2 - y1) / L if L else 0      # sheet direction connection -> body
            if L == 0:
                wdx, wdy = xf.vec(dx, dy); ux, uy = wdx, -wdy
            horiz = abs(ux) > abs(uy)
            nm = unq(kid(it, "name")[1]) if kid(it, "name") else ""
            nu = unq(kid(it, "number")[1]) if kid(it, "number") else ""
            nh, nw, _ = font_of(kid(it, "name")) if kid(it, "name") else (1.27, 1.27, set())
            uh, uw, _ = font_of(kid(it, "number")) if kid(it, "number") else (1.27, 1.27, set())
            gap = 0.3
            if nu and not ls_.hide_nums:
                tw, th = text_wh(nu, uh, uw)
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                if ls_.name_off > 0 or not nm or ls_.hide_names or nm == "~":
                    off = -gap - th / 2            # above (horizontal) / left (vertical)
                else:
                    off = gap + th / 2             # names outside take the upper side, numbers go below
                if horiz: b = (mx - tw / 2, my + off - th / 2, mx + tw / 2, my + off + th / 2)
                else: b = (mx + off - th / 2, my - tw / 2, mx + off + th / 2, my + tw / 2)
                texts.append(Item("pinnum", nu, b, owner, "%s pin %s" % (ref, nu), extra=(x1, y1, x2, y2)))
            if nm and nm != "~" and not ls_.hide_names:
                tw, th = text_wh(nm, nh, nw)
                if ls_.name_off > 0:
                    s0 = L + ls_.name_off
                    c0 = (x1 + ux * s0, y1 + uy * s0); c1 = (x1 + ux * (s0 + tw), y1 + uy * (s0 + tw))
                    if horiz: b = (min(c0[0], c1[0]), c0[1] - th / 2, max(c0[0], c1[0]), c0[1] + th / 2)
                    else: b = (c0[0] - th / 2, min(c0[1], c1[1]), c0[0] + th / 2, max(c0[1], c1[1]))
                else:
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    if horiz: b = (mx - tw / 2, my - gap - th, mx + tw / 2, my - gap)
                    else: b = (mx - gap - th, my - tw / 2, mx - gap, my + tw / 2)
                texts.append(Item("pinname", nm, b, owner, "%s pin %s name" % (ref, nu), extra=(x1, y1, x2, y2)))

    # ---- sheet-level items
    for w in kids(root, "wire") + kids(root, "bus") + kids(root, "polyline"):
        pts = [(num(p, 1), num(p, 2)) for p in kids(kid(w, "pts") or [], "xy")]
        for a_, b_ in zip(pts, pts[1:]): seg(*a_, *b_, None, w[0])
    for r in kids(root, "rectangle"):
        s_, e_ = kid(r, "start"), kid(r, "end")
        c = [(num(s_, 1), num(s_, 2)), (num(s_, 1), num(e_, 2)), (num(e_, 1), num(e_, 2)), (num(e_, 1), num(s_, 2))]
        for i in range(4): seg(*c[i], *c[(i + 1) % 4], None, "rect")
    for nc in kids(root, "no_connect"):
        x, y = num(kid(nc, "at"), 1), num(kid(nc, "at"), 2)
        seg(x - .635, y - .635, x + .635, y + .635, "nc@%g,%g" % (x, y), "nc")
        seg(x - .635, y + .635, x + .635, y - .635, "nc@%g,%g" % (x, y), "nc")
    for kind, tag in (("label", "label"), ("glabel", "global_label"), ("hlabel", "hierarchical_label"), ("text", "text")):
        for t in kids(root, tag):
            s = unq(t[1]); at = kid(t, "at"); x, y, a = num(at, 1), num(at, 2), num(at, 3) % 360
            h, w, jus = font_of(t)
            tw, th = text_wh(s, h, w)
            # KiCad 10 draws text and labels at 0 or 90 degrees only (180 -> 0, 270 -> 90) and takes the side from the
            # justify: left = text runs right (or up), right = runs left (or down); checked against kicad-cli renders
            vert = a in (90, 270)
            if kind == "text":
                if hidden(t): continue
                rel = rbox(*jbox(tw, th, jus), 90 if vert else 0)
                b = (x + rel[0], y - rel[3], x + rel[2], y - rel[1])
                texts.append(Item("text", s, b, None, "text"))
                continue
            b = label_box(kind, s, h, w, x, y, a, jus)
            texts.append(Item(kind, s, b, "lbl@%g,%g" % (x, y), "%s %s" % (tag, s), extra=(x, y)))
    return texts, bodies, lines


# ------------------------------------------------------------------------------------------------ collisions
EPS = 0.12


def shrink(b, e=EPS):
    return (b[0] + e, b[1] + e, b[2] - e, b[3] - e)


def inter(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def seg_hits(b, x1, y1, x2, y2):
    """does segment (x1,y1)-(x2,y2) pass through box b (Liang-Barsky)"""
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - b[0]), (dx, b[2] - x1), (-dy, y1 - b[1]), (dy, b[3] - y1)):
        if abs(p) < 1e-12:
            if q < 0: return False
        else:
            t = q / p
            if p < 0: t0 = max(t0, t)
            else: t1 = min(t1, t)
            if t0 > t1: return False
    return True


class Grid:
    def __init__(self, cell=5.0):
        self.c = cell; self.g = collections.defaultdict(list)

    def keys(self, b):
        c = self.c
        for i in range(int(math.floor(b[0] / c)), int(math.floor(b[2] / c)) + 1):
            for j in range(int(math.floor(b[1] / c)), int(math.floor(b[3] / c)) + 1):
                yield i, j

    def add(self, b, v):
        for k in self.keys(b): self.g[k].append(v)

    def near(self, b):
        seen = set()
        for k in self.keys(b):
            for v in self.g[k]:
                if id(v) not in seen:
                    seen.add(id(v)); yield v


def frame_check(texts, bodies, lines, paper):
    """items that leave the drawing frame or touch the title block -> list of (what, box)"""
    area, tb = frame_rects(*paper)
    out = []
    def chk(what, b):
        if b[0] < area[0] or b[1] < area[1] or b[2] > area[2] or b[3] > area[3]:
            out.append(("outside frame", what, b))
        elif inter(shrink(b, 0.05), tb):
            out.append(("on title block", what, b))
    for t in texts: chk(desc(t), t.box)
    for bd in bodies: chk("body of %s" % bd[5], bd[:4])
    for x1, y1, x2, y2, owner, kind, w in lines:
        if kind == "body": continue
        chk("%s %s (%.1f,%.1f)-(%.1f,%.1f)" % (kind, owner or "", x1, y1, x2, y2), (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    return out


def analyse(path):
    texts, bodies, lines = sheet_items(path)
    frame = frame_check(texts, bodies, lines, sheet_items.paper)
    tb = [(shrink(t.box), t) for t in texts]
    tb = [(b, t) for b, t in tb if b[0] < b[2] and b[1] < b[3]]
    gt, gb, gl = Grid(), Grid(), Grid()
    for b, t in tb: gt.add(b, (b, t))
    for bd in bodies: gb.add(bd[:4], bd)
    for ln in lines:
        gl.add((min(ln[0], ln[2]), min(ln[1], ln[3]), max(ln[0], ln[2]), max(ln[1], ln[3])), ln)
    hits = collections.Counter(); pairs = []
    cnt = collections.Counter()
    for i, (b, t) in enumerate(tb):
        for b2, t2 in gt.near(b):
            if t2 is t or id(t2) < id(t) or not inter(b, b2): continue
            if t.owner and t.owner == t2.owner and {t.kind, t2.kind} <= {"pinname", "pinnum"} and t.extra == t2.extra:
                continue
            cnt["text/text"] += 1; hits[id(t)] += 1; hits[id(t2)] += 1
            pairs.append(("text/text", t, t2))
        for bd in gb.near(b):
            if not inter(b, shrink(bd[:4], 0)) or not box_hits_poly(b, bd[6]): continue
            if t.owner == bd[4] and t.kind in ("pinname", "libtext"): continue      # pin names / symbol text inside own body: by design
            if t.kind in ("glabel", "label", "hlabel") and False: continue
            cnt["text/body"] += 1; hits[id(t)] += 1
            pairs.append(("text/body", t, bd[5]))
        for ln in gl.near(b):
            x1, y1, x2, y2, owner, kind, w = ln
            if kind == "body": continue                            # body line work is covered by text/body
            if owner is not None and owner == t.owner and kind == "pin" and t.kind in ("pinnum", "pinname"):
                continue                                           # a pin's texts sit on/next to their own pin line
            if t.kind in ("label", "glabel", "hlabel"):
                ax, ay = t.extra
                # the label's own wire/pin: anything touching its anchor point
                if min(math.hypot(x1 - ax, y1 - ay), math.hypot(x2 - ax, y2 - ay)) < 0.05 or _on(ax, ay, ln):
                    continue
            if kind == "pin" and t.kind in ("pinnum", "pinname") and t.extra == (x1, y1, x2, y2): continue
            if seg_hits(b, x1, y1, x2, y2):
                cnt["text/line"] += 1; hits[id(t)] += 1
                pairs.append(("text/line", t, "%s %s" % (kind, owner or "")))
    byid = {id(t): t for _, t in tb}
    worst = sorted(((n, byid[k]) for k, n in hits.items()), key=lambda x: -x[0])
    cnt["frame"] = len(frame)
    return dict(counts=cnt, worst=worst, pairs=pairs, ntexts=len(texts), frame=frame, paper=sheet_items.paper)


def _on(x, y, ln):
    x1, y1, x2, y2 = ln[:4]
    if abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) > 1e-3 * max(1, math.hypot(x2 - x1, y2 - y1)): return False
    return min(x1, x2) - 1e-3 <= x <= max(x1, x2) + 1e-3 and min(y1, y2) - 1e-3 <= y <= max(y1, y2) + 1e-3


def desc(t):
    b = t.box
    return "%-8s %-28s %s @(%.1f,%.1f)" % (t.kind, repr(t.text[:26]), t.ident or "", (b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


# ------------------------------------------------------------------------------------------------ calibration
def calibrate(sch, svg):
    """match computed boxes to the SVG's stroked-text ink boxes (same text, nearest centre)"""
    import html
    s = open(svg).read()
    ink = collections.defaultdict(list)
    for m in re.finditer(r'<g class="stroked-text"><desc>(.*?)</desc>(.*?)</g>', s, re.S):
        nums = [float(v) for v in re.findall(r'-?[\d.]+', " ".join(re.findall(r'd="([^"]*)"', m.group(2))))]
        if not nums: continue
        xs, ys = nums[0::2], nums[1::2]
        ink[plain(html.unescape(m.group(1)))].append((min(xs), min(ys), max(xs), max(ys)))
    texts, _, _ = sheet_items(sch)
    errs = collections.defaultdict(list); miss = collections.Counter(); bad = []
    for t in texts:
        if t.kind in ("glabel", "hlabel"): continue            # the flag outline is not in the text ink
        cands = ink.get(plain(t.text).replace("\n", " "), []) or ink.get(plain(t.text), [])
        if not cands: miss[t.kind] += 1; continue
        cx, cy = (t.box[0] + t.box[2]) / 2, (t.box[1] + t.box[3]) / 2
        k = min(cands, key=lambda b: ((b[0] + b[2]) / 2 - cx) ** 2 + ((b[1] + b[3]) / 2 - cy) ** 2)
        e = max(abs(k[i] - t.box[i]) for i in range(4))
        errs[t.kind].append(e)
        if e > 1.0: bad.append((e, t, k))
    print("calibration of %s against %s" % (os.path.basename(sch), os.path.basename(svg)))
    for kind, es in sorted(errs.items()):
        es.sort()
        print("  %-8s n=%4d  worst-edge error median %.2f mm, 90%% %.2f mm, max %.2f mm  (unmatched %d)" % (
            kind, len(es), es[len(es) // 2], es[int(len(es) * .9)], es[-1], miss[kind]))
    for e, t, k in sorted(bad, key=lambda x: -x[0])[:10]:
        print("   off by %.2f: %s  ink (%.1f,%.1f,%.1f,%.1f) computed (%.1f,%.1f,%.1f,%.1f)" % ((e, desc(t)) + k + t.box))


# ------------------------------------------------------------------------------------------------ main
def sheets_in(p):
    if os.path.isfile(p): return [p]
    out = []
    for r, ds, fs in os.walk(p):
        ds.sort()
        out += [os.path.join(r, f) for f in sorted(fs) if f.endswith(".kicad_sch")]
    return out


def main(argv):
    detail, npairs, jpath, cal, summary = 5, 0, None, None, False
    args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--detail": detail = int(argv[i + 1]); i += 2; continue
        if a == "--pairs": npairs = int(argv[i + 1]); i += 2; continue
        if a == "--json": jpath = argv[i + 1]; i += 2; continue
        if a == "--calibrate": cal = argv[i + 1]; i += 2; continue
        if a == "--summary": summary = True; i += 1; continue
        args.append(a); i += 1
    if not args:
        print(__doc__); return 2
    if cal:
        calibrate(args[0], cal); return 0
    files = list(collections.OrderedDict.fromkeys(os.path.normpath(f) for a in args for f in sheets_in(a)))
    res = {}; tot = collections.Counter()
    groups = collections.OrderedDict()
    for f in files:
        r = analyse(f)
        res[f] = r
        tot.update(r["counts"])
        groups.setdefault(os.path.dirname(f), collections.Counter()).update(r["counts"])
        if not summary:
            c = r["counts"]
            print("%-70s texts %5d  text/text %4d  text/body %4d  text/line %4d  frame %4d  (%gx%g)" % (
                os.path.relpath(f), r["ntexts"], c["text/text"], c["text/body"], c["text/line"], c["frame"], *r["paper"]))
            for k, what, b in r["frame"][:detail]:
                print("      %s: %s" % (k, what))
            for n, t in r["worst"][:detail]:
                print("      %3d x %s" % (n, desc(t)))
            for k, a_, b_ in r["pairs"][:npairs]:
                print("      %s: %s  <->  %s" % (k, desc(a_), desc(b_) if isinstance(b_, Item) else b_))
    if summary:
        for g, c in groups.items():
            print("%-70s text/text %5d  text/body %5d  text/line %5d  total %5d  frame %4d" % (
                os.path.relpath(g), c["text/text"], c["text/body"], c["text/line"],
                c["text/text"] + c["text/body"] + c["text/line"], c["frame"]))
    print("TOTAL  text/text %d  text/body %d  text/line %d  frame %d  (%d sheets)" % (
        tot["text/text"], tot["text/body"], tot["text/line"], tot["frame"], len(files)))
    if jpath:
        json.dump({os.path.relpath(f): dict(counts=dict(r["counts"]), texts=r["ntexts"],
                                            worst=[(n, desc(t)) for n, t in r["worst"][:20]]) for f, r in res.items()},
                  open(jpath, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

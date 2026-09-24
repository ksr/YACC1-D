#!/usr/bin/env python3
"""route_check.py - checks of the routed I/O card v2.0 board that DRC does not make (plain Python, no KiCad import).

    python3 route_check.py <options/io-v2.0-option-b.kicad_pcb> <io-v2.0.kicad_pcb>

main():        every v1.1 track segment and via that option B kept is in the routed board unchanged (start, end, width,
               layer, net; via position, size, drill, net), and a summary of the routed copper.
silk_on_parts: the DRC silk items (silk over pads, silk over silk, silk at the edge) that involve the reference text
               of a new (CF) or moved part - build.sh requires none.
The part lists are shared with route_v2.py.
"""
import re, sys, collections

CF_PARTS = ["IC12", "IC13", "IC14", "IC15", "J2", "J3", "JP2", "RN3", "R11", "R12", "R13", "R14", "R15", "LED1",
            "C18", "C19", "C20", "C21", "C22"]
SWITCHES = ["S%d" % i for i in range(8)] + ["IN0"]
MOVED = SWITCHES + ["INPUT0", "IC3", "C16", "IC10", "C15", "JP2"]


def form_key(kind, body):
    """the identity of one (segment ...) / (via ...) form: geometry, width/size, layer, net"""
    g = lambda k: re.search(r"\(%s ([^)]*)\)" % k, body).group(1)
    net = re.search(r'\(net "([^"]*)"\)', body).group(1)
    if kind == "segment":
        a = tuple(round(float(v), 4) for v in g("start").split())
        b = tuple(round(float(v), 4) for v in g("end").split())
        return ("segment",) + tuple(sorted([a, b])) + (float(g("width")), g("layer").strip('"'), net)
    return ("via", tuple(round(float(v), 4) for v in g("at").split()), float(g("size")), float(g("drill")), net)


def copper(path):
    """-> Counter of (kind, geometry..., net) and the per-form lock flags"""
    t = open(path).read()
    items, locked = collections.Counter(), collections.Counter()
    for m in re.finditer(r"^\t\((segment|via)\b(.*?)^\t\)", t, re.M | re.S):
        kind, body = m.group(1), m.group(2)
        key = form_key(kind, body)
        items[key] += 1
        if "(locked yes)" in body:
            locked[key] += 1
    return items, locked


def silk_on_parts(drc):
    refs = set(CF_PARTS) | set(MOVED)
    out = []
    for v in drc["violations"]:
        if v["type"] not in ("silk_overlap", "silk_over_copper", "silk_edge_clearance"):
            continue
        for i in v["items"]:
            m = re.match(r"Reference field of (\S+)", i["description"])
            if m and m.group(1) in refs:
                out.append("%s: %s" % (v["type"], " / ".join(x["description"] for x in v["items"])))
                break
    return out


def main(optb, routed, removed=None):
    """removed: the file route_v2.py finish writes when it had to rip up kept v1.1 copper (one repr(key) per line);
    exactly those items may be missing"""
    kept, _ = copper(optb)
    got, locked = copper(routed)
    lost = kept - got
    allowed = collections.Counter()
    if removed:
        try:
            import ast
            allowed = collections.Counter(ast.literal_eval(l) for l in open(removed) if l.strip())
        except FileNotFoundError:
            pass
    unexplained = lost - allowed
    n = sum(kept.values())
    new = got - kept
    layers = collections.Counter(k[4] for k in new.elements() if k[0] == "segment")
    widths = collections.Counter((k[3], "power" if k[5] in ("GND", "VCC") else "signal")
                                 for k in new.elements() if k[0] == "segment")
    print("v1.1 copper kept from option B: %d of %d items intact, %d of them locked; %d removed by the router's "
          "last-resort rip-up (listed in reports/route-kept-removed.txt)"
          % (n - sum(lost.values()), n, sum((locked & kept).values()), sum((lost & allowed).values())))
    print("routed copper added: %d track segments (%s), %d vias; widths %s"
          % (sum(layers.values()), ", ".join("%s %d" % kv for kv in sorted(layers.items())),
             sum(1 for k in new.elements() if k[0] == "via"),
             ", ".join("%s %.4g mm: %d" % (w[1], w[0], c) for w, c in sorted(widths.items()))))
    print("totals: %d track segments, %d vias" % (sum(1 for k in got.elements() if k[0] == "segment"),
                                                  sum(1 for k in got.elements() if k[0] == "via")))
    if unexplained:
        print("LOST v1.1 items (not in the removal list): %s" % sorted(unexplained)[:5])
    print("kept-copper check -> %s" % ("PASS" if not unexplained else "FAIL"))
    return 0 if not unexplained else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))

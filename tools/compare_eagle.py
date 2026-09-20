#!/usr/bin/env python3
"""Compare two Eagle designs (schematic and, if present, board) and say whether the newer one has anything new.

usage: compare_eagle.py <A.sch> <B.sch>      (boards are found by swapping the extension)

Schematic: parts (name, deviceset, device, value) and CONNECTIVITY = partition of (part,gate,pin) into nets,
compared independently of net names (a renamed net is not a change); net-name changes reported separately.
Board: elements (name, package, value) and connectivity as a partition of (element,pad); placement moves and
copper-geometry hash reported separately (a re-route with the same connectivity is 'layout only').
Text/attribute-only differences (values, descriptions, frame) are listed but not counted as electrical.
"""
import sys, os, hashlib, xml.etree.ElementTree as ET

def sch_model(path):
    r = ET.parse(path).getroot(); s = r.find("drawing/schematic")
    parts = {p.get("name"): (p.get("deviceset"), p.get("device"), p.get("value") or "") for p in s.findall("parts/part")}
    nets = {}
    for sh in s.findall("sheets/sheet"):
        for n in sh.findall("nets/net"):
            for pr in n.iter("pinref"):
                nets.setdefault(n.get("name"), set()).add((pr.get("part"), pr.get("gate"), pr.get("pin")))
    # supply symbols (GND/VCC parts) join nets by name across sheets already; drop unconnected nets
    nets = {k: v for k, v in nets.items() if v}
    return parts, nets

def brd_model(path):
    r = ET.parse(path).getroot(); b = r.find("drawing/board")
    els = {e.get("name"): (e.get("package"), e.get("value") or "") for e in b.findall("elements/element")}
    pos = {e.get("name"): (e.get("x"), e.get("y"), e.get("rot") or "R0") for e in b.findall("elements/element")}
    sigs = {}
    for sg in b.findall("signals/signal"):
        for c in sg.findall("contactref"):
            sigs.setdefault(sg.get("name"), set()).add((c.get("element"), c.get("pad")))
    copper = hashlib.md5()
    for sg in b.findall("signals/signal"):
        for w in sg.findall("wire") + sg.findall("via") + sg.findall("polygon"):
            copper.update(ET.tostring(w))
    nwires = sum(len(sg.findall("wire")) for sg in b.findall("signals/signal"))
    nvias = sum(len(sg.findall("via")) for sg in b.findall("signals/signal"))
    return els, pos, sigs, copper.hexdigest()[:8], nwires, nvias

def partition_diff(na, nb):
    """nets as name->set(pins). Compare the set of pin-sets (connectivity), ignoring names."""
    pa = {frozenset(v) for v in na.values()}; pb = {frozenset(v) for v in nb.values()}
    only_a = pa - pb; only_b = pb - pa
    # try to explain as renames: identical pin-set under a different name
    name_a = {frozenset(v): k for k, v in na.items()}; name_b = {frozenset(v): k for k, v in nb.items()}
    renames = [(name_a[f], name_b[f]) for f in pa & pb if name_a[f] != name_b[f]]
    return only_a, only_b, renames, name_a, name_b

def show_nets(sets, names, limit=8):
    out = []
    for f in sorted(sets, key=lambda f: names.get(f, ""))[:limit]:
        pins = sorted("%s.%s%s" % (p, g if g and g != "G$1" else "", "." + pin) for p, g, pin in f)
        out.append("      %-12s %s%s" % (names.get(f, "?"), ", ".join(pins[:6]), " ..." if len(pins) > 6 else ""))
    if len(sets) > limit: out.append("      ... %d more" % (len(sets) - limit))
    return "\n".join(out)

def compare(a, b):
    print("=" * 100); print("A (older/active): %s\nB (newer):        %s" % (a, b))
    pa, na = sch_model(a); pb, nb = sch_model(b)
    electrical = False
    # parts
    added = sorted(set(pb) - set(pa)); removed = sorted(set(pa) - set(pb))
    changed = sorted(k for k in set(pa) & set(pb) if pa[k][:2] != pb[k][:2])
    valchg = sorted(k for k in set(pa) & set(pb) if pa[k][:2] == pb[k][:2] and pa[k][2] != pb[k][2])
    print("SCHEMATIC parts: A=%d B=%d | added %d, removed %d, device changed %d, value-only changed %d" % (len(pa), len(pb), len(added), len(removed), len(changed), len(valchg)))
    for k in added[:10]: print("   + %s %s" % (k, pb[k]))
    for k in removed[:10]: print("   - %s %s" % (k, pa[k]))
    for k in changed[:10]: print("   ~ %s %s -> %s" % (k, pa[k][:2], pb[k][:2]))
    for k in valchg[:10]: print("   v %s %r -> %r" % (k, pa[k][2], pb[k][2]))
    if added or removed or changed: electrical = True
    oa, ob, ren, nma, nmb = partition_diff(na, nb)
    print("SCHEMATIC connectivity: nets A=%d B=%d | pin-sets only in A: %d, only in B: %d, renamed nets: %d" % (len(na), len(nb), len(oa), len(ob), len(ren)))
    if oa: print("   nets in A not in B:\n" + show_nets(oa, nma))
    if ob: print("   nets in B not in A:\n" + show_nets(ob, nmb))
    for x, y in ren[:6]: print("   renamed: %s -> %s" % (x, y))
    if oa or ob: electrical = True
    ba, bb = os.path.splitext(a)[0] + ".brd", os.path.splitext(b)[0] + ".brd"
    if os.path.exists(ba) and os.path.exists(bb):
        ea, posa, sa, ha, wa, va = brd_model(ba); eb, posb, sb, hb, wb, vb = brd_model(bb)
        e_add = sorted(set(eb) - set(ea)); e_rem = sorted(set(ea) - set(eb)); e_pkg = sorted(k for k in set(ea) & set(eb) if ea[k][0] != eb[k][0])
        so, sn, sren, _, _ = partition_diff(sa, sb)
        moved = sum(1 for k in set(posa) & set(posb) if posa[k] != posb[k])
        print("BOARD elements: A=%d B=%d | added %d, removed %d, package changed %d, moved %d" % (len(ea), len(eb), len(e_add), len(e_rem), len(e_pkg), moved))
        for k in e_add[:8]: print("   + %s %s" % (k, eb[k]))
        for k in e_rem[:8]: print("   - %s %s" % (k, ea[k]))
        for k in e_pkg[:8]: print("   ~ %s %s -> %s" % (k, ea[k][0], eb[k][0]))
        print("BOARD connectivity: pad-sets only in A: %d, only in B: %d | copper hash A=%s B=%s | wires %d->%d vias %d->%d" % (len(so), len(sn), ha, hb, wa, wb, va, vb))
        if so or sn: print("   pad-sets in A not in B: %d, in B not in A: %d" % (len(so), len(sn)))
        b_elec = bool(e_add or e_rem or e_pkg or so or sn)
        layout_only = (not b_elec) and (ha != hb or moved)
    else:
        b_elec = None; layout_only = None
        print("BOARD: %s" % ("no board on one side" if os.path.exists(ba) != os.path.exists(bb) else "no boards"))
    verdict = "ELECTRICALLY DIFFERENT" if (electrical or b_elec) else ("IDENTICAL NETLIST AND PARTS" + (" (board re-laid out / moved parts only)" if layout_only else (" (board identical too)" if b_elec is False else "")))
    if not electrical and not b_elec and valchg: verdict += "; value text differs on %d parts" % len(valchg)
    print("VERDICT: " + verdict)
    return verdict

if __name__ == "__main__":
    compare(sys.argv[1], sys.argv[2])

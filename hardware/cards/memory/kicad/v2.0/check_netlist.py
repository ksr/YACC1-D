#!/usr/bin/env python3
"""check_netlist.py - prove the memory card v2.0 schematic (and each board) = the built v1.3 minus C20-C23 + the CF
section.

"v1.3" below = the built card, ../v1.3 (build.sh passes its netlist and board).

usage: check_netlist.py <v2.0 schematic .net> <v1.3 schematic .net> <v1.3 .kicad_pcb> [<v2.0 board .kicad_pcb> ...]
                        [--records <record board .kicad_pcb> ...]
       (both .net files from: kicad-cli sch export netlist --format kicadsexpr <root .kicad_sch>)

What must hold, exactly (mem_v2_netlist.expected() builds the expectation):
  schematic  every part of v1.3 but the REMOVED four (C20-C23, Ken 2026-09-24) is in v2.0; each removed one was on
             v1.3 a capacitor with pin 1 on GND and pin 2 on VCC and nothing else (mem_v2_netlist.removed_pins());
             every net of v1.3 is in v2.0 with the same pins (less the removed caps' pins) and the same name, except that
               - IO-ADDR0-3 / -IO-RD / -IO-WR (v1.3: sheet-1 local labels on X1 only) are global now and ALSO carry
                 the CF section's pins,
               - DATA0-7, -RESET, VCC, GND also carry the CF section's pins,
               - nets KiCad names after a pin (Net-(...)) are compared by their pins only;
             every CF section net (mem_v2_netlist.NETS) is there with exactly its pins (name /Sheet 7/<name>, or the
             shared name); there is no other net; every pin KiCad leaves unconnected is either unconnected on v1.3 or a
             documented CF no-connect, and nothing else is unconnected; every part is v1.3's (same value, footprint)
             or a CF part (value, footprint of cf_netlist.py), and nothing else.
  board      every pad of every footprint is on exactly the net the v2.0 schematic gives that pin (same names), the
             pads with no net are exactly the schematic's unconnected pins + the v1.3 pads no schematic pin names
             (X1's mounting holes, and the unused gate pins the
             Eagle board left without a net: IC3, IC4, IC12, IC13, IC14, IC18), and the footprints are the schematic's parts with the same library
             footprints and values (v1.3 parts: the value on the v1.3 board, which is the Eagle board's), plus at
             most the two standoff holes H1 / H2 of the CF adapter (the standoff options, gen_standoff.py): board-only
             footprints holding nothing but a non-plated hole with no net (is_mech()).
             The boards before --records (the final board) must equal the schematic.
  records    the boards after --records (re-layout options, trial routes, keep-copper options) were made BEFORE C20-C23
             were removed: each must equal the schematic PLUS exactly C20-C23 as on the v1.3 board (same footprint and
             value, pin 1 on GND, pin 2 on VCC), nothing else. A record board without the four is checked like the
             final board (a regenerated record would be one).
Exit status 0 only if everything matches. Plain Python (no KiCad import).
"""
import os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mem_v2_netlist as NL                        # noqa: E402
from compare_netlist import sparse, kids, val     # noqa: E402  (the CF card's s-expression helpers; NL put it on the path)


def read_net(path):
    root = sparse(open(path).read())[0]
    parts = {}
    for comp in kids(kids(root, "components")[0], "comp"):
        ref = val(comp, "ref")
        if not ref.startswith("#"):
            parts[ref] = (val(comp, "value"), val(comp, "footprint"))
    nets = {}
    for net in kids(kids(root, "nets")[0], "net"):
        nodes = {(val(nd, "ref"), val(nd, "pin")) for nd in kids(net, "node") if not val(nd, "ref").startswith("#")}
        if nodes:
            nets[val(net, "name")] = nodes
    return nets, parts


def auto(name):
    return name.startswith("Net-(") or name.startswith("unconnected-(")


def check_schematic(v2file, v13file):
    v13_nets, v13_parts = read_net(v13file)
    want, want_parts, want_lone, notes = NL.expected(v13_nets, v13_parts)
    got, got_parts = read_net(v2file)
    bad = []
    got_lone = set()
    for n, s in list(got.items()):
        if n.startswith("unconnected-("):
            if len(s) != 1:
                bad.append("unconnected net %s has %d pins" % (n, len(s)))
            got_lone |= s
            del got[n]
    by_pins = {frozenset(s): n for n, s in got.items()}
    matched = set()
    for n, s in want.items():
        if auto(n):
            g = by_pins.get(frozenset(s))
            if g is None:
                bad.append("net %s %s missing (by pins)" % (n, sorted(s)))
            elif not auto(g):
                bad.append("net %s is named %s in v2.0" % (n, g))
            else:
                matched.add(g)
            continue
        if n not in got:
            bad.append("net %s missing" % n)
            continue
        matched.add(n)
        if got[n] != s:
            bad.append("net %s differs: missing %s, extra %s" % (n, sorted(s - got[n]), sorted(got[n] - s)))
    for n in sorted(set(got) - matched):
        bad.append("extra net %s %s" % (n, sorted(got[n])))
    if got_lone != want_lone:
        bad.append("unconnected pins differ: should be connected %s; should be unconnected %s"
                   % (sorted(got_lone - want_lone), sorted(want_lone - got_lone)))
    for ref, vf in want_parts.items():
        if ref not in got_parts:
            bad.append("part %s missing" % ref)
        elif got_parts[ref] != vf:
            bad.append("part %s is %s, should be %s" % (ref, got_parts[ref], vf))
    for ref in sorted(set(got_parts) - set(want_parts)):
        bad.append("extra part %s" % ref)
    # summary
    cf_nets = [n for n in want if n.startswith("/%s/" % NL.CF_SHEET)]
    shared = [n for n in NL.SHARED + NL.POWER]
    npins = sum(len(s) for s in want.values())
    print("schematic: v1.3 %d parts / %d nets  +  CF section %d parts / %d own nets, %d pins joined onto %d shared nets"
          % (len(v13_parts), len(v13_nets), len(NL.PARTS), len(cf_nets),
             sum(len(v) for n, v in NL.NETS.items() if n in shared), len(shared)))
    print("           expected v2.0: %d parts, %d named/auto nets holding %d pins, %d unconnected pins (%d v1.3 + %d CF "
          "no-connect)" % (len(want_parts), len(want), npins, len(want_lone),
                           len(want_lone) - sum(len(v) for v in NL.NO_CONNECT.values()),
                           sum(len(v) for v in NL.NO_CONNECT.values())))
    for x in notes:
        print("           " + x)
    print("           KiCad v2.0 schematic: %d parts, %d nets, %d unconnected pins: %s"
          % (len(got_parts), len(got), len(got_lone), "MATCH" if not bad else "MISMATCH"))
    for x in bad:
        print("    ", x)
    gone = NL.removed_pins(v13_nets, v13_parts)
    return not bad, got, got_lone, got_parts, gone


def board_parts(pcb):
    """-> ({ref: (value, footprint)}, {(ref, pad) with no net}) of a .kicad_pcb"""
    root = sparse(open(pcb).read())[0]
    parts, nonet = {}, set()
    for fp in kids(root, "footprint"):
        props = {p[1]: p[2] for p in kids(fp, "property")}
        parts[props.get("Reference")] = (props.get("Value"), fp[1])
        for pad in kids(fp, "pad"):
            if not val(pad, "net"):
                nonet.add((props.get("Reference"), pad[1]))
    return parts, nonet


def check_board(pcb, sch_nets, sch_lone, sch_parts, v13_board, gone=None):
    """v13_board: the v1.3 .kicad_pcb. Its footprints keep their Eagle board values (the converted symbols carry the
    Eagle deviceset names instead: inherited, see ../v1.3), and its pads that no schematic pin names (X1's mounting
    holes, unused gate pins the Eagle board left netless) stay netless.
    gone: {(ref, pin): net} of the removed parts -> the board is a pre-removal record: it must carry exactly those
    parts too, on those nets (footprint and value as on the v1.3 board)."""
    v13_parts, v13_nonet = board_parts(v13_board)
    kind = "final"
    if gone:
        sch_nets = {n: set(s) for n, s in sch_nets.items()}
        for rp, n in gone.items():
            sch_nets[n].add(rp)
        sch_parts = dict(sch_parts)
        for r in {r for r, p in gone}:
            sch_parts[r] = v13_parts[r]
        kind = "record, before the removal of %s" % ", ".join(sorted({r for r, p in gone}))
    pinless = {rp for rp in v13_nonet if rp not in sch_lone and not any(rp in s for s in sch_nets.values())}
    root = sparse(open(pcb).read())[0]
    parts, nets, alone, bad, mech = {}, collections.defaultdict(set), set(), [], []
    for fp in kids(root, "footprint"):
        props = {p[1]: p[2] for p in kids(fp, "property")}
        ref = props.get("Reference")
        if is_mech(fp, ref):
            mech.append(ref)                                  # a standoff hole: board only, not a schematic part
            continue
        parts[ref] = (props.get("Value"), fp[1])
        for pad in kids(fp, "pad"):
            num, net = pad[1], val(pad, "net")
            if (ref, num) in pinless and not net:
                continue                                      # a v1.3 pad with no schematic pin (mounting holes)
            if num == "":
                bad.append("unnumbered pad on %s (net %s)" % (ref, net))
                continue
            if net and not net.startswith("unconnected-("):
                nets[net].add((ref, num))
            else:
                alone.add((ref, num))
    for n, s in sch_nets.items():
        if nets.get(n) != s:
            bad.append("net %s: board %s, schematic %s" % (n, sorted(nets.get(n, ())), sorted(s)))
    for n in sorted(set(nets) - set(sch_nets)):
        bad.append("extra board net %s" % n)
    if alone != sch_lone:
        bad.append("unconnected pads differ from the schematic: %s / %s" % (sorted(alone - sch_lone),
                                                                           sorted(sch_lone - alone)))
    for ref, (v, f) in sch_parts.items():
        want = (v13_parts[ref][0], f) if ref in v13_parts else (v, f)
        if ref in v13_parts and v13_parts[ref][1] != f:
            bad.append("v1.3 footprint %s is %s on the v1.3 board, %s in the schematic" % (ref, v13_parts[ref][1], f))
        if parts.get(ref) != want:
            bad.append("footprint %s is %s, should be %s" % (ref, parts.get(ref), want))
    for ref in sorted(set(parts) - set(sch_parts)):
        bad.append("extra footprint %s" % ref)
    print("board %s: %d footprints%s, %d nets / %d pads, %d unconnected pads (+ %d pinless v1.3 pads) [%s]: %s"
          % (os.path.basename(pcb), len(parts), " + %s (board-only standoff holes)" % "/".join(sorted(mech)) if mech else "",
             len(nets), sum(len(s) for s in nets.values()), len(alone), len(pinless),
             kind, "MATCH" if not bad else "MISMATCH"))
    for x in bad[:30]:
        print("    ", x)
    return not bad


MECH = ("H1", "H2")      # the standoff holes of the CF adapter (gen_standoff.py): the only board-only footprints allowed


def is_mech(fp, ref):
    """a mechanical hole: reference H1 / H2, attribute board_only (not in the schematic, not in the BOM), nothing but
    non-plated holes with no net"""
    attr = [a for x in kids(fp, "attr") for a in x[1:]]
    pads = kids(fp, "pad")
    return (ref in MECH and "board_only" in attr and pads
            and all(len(p) > 2 and p[2] == "np_thru_hole" and not val(p, "net") for p in pads))


def is_record(pcb):
    """a record board made before the removal carries the removed parts"""
    return bool(set(board_parts(pcb)[0]) & set(NL.REMOVED))


if __name__ == "__main__":
    ok, sn, sl, sp, gone = check_schematic(sys.argv[1], sys.argv[2])
    args = sys.argv[4:]
    finals = args[:args.index("--records")] if "--records" in args else args
    records = args[args.index("--records") + 1:] if "--records" in args else []
    oks = [check_board(p, sn, sl, sp, sys.argv[3]) for p in finals]
    nrec = 0
    for p in records:
        rec = is_record(p)
        nrec += rec
        oks.append(check_board(p, sn, sl, sp, sys.argv[3], gone if rec else None))
    good = ok and all(oks)
    print("RESULT:", "MATCH (v2.0 = v1.3 - %s + the CF section, pin for pin%s%s)" % (
        "/".join(sorted(NL.REMOVED)), "; every board = the schematic" if oks else "",
        " (%d record board(s) made before the removal = the schematic + exactly %s as on v1.3)"
        % (nrec, "/".join(sorted(NL.REMOVED))) if nrec else "") if good else "MISMATCH")
    sys.exit(0 if good else 1)

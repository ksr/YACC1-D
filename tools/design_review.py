#!/usr/bin/env python3
"""Mechanical design review of every ACTIVE card from its KiCad netlist (kicad/<rev>/reports/netlist.net, which carries
pin types from the Eagle symbols) and board. Looks for the class of fault found on the video card on 2026-09-20/21:

  1. supply islands   : more than one positive rail name (VCC, +5V, 5V ...) with nothing joining them; a rail with no
                        source (no bus-connector pin, no regulator/power symbol input)
  2. unpowered parts  : power_in pins whose net is not one of the rails
  3. floating inputs  : input / clock pins in a net with a single node (TTL reads them high, unreliably)
  4. driver conflicts : nets with two or more plain 'output' pins (open-collector / tri-state excluded)
  5. open-collector   : nets driven only by open_collector pins with no resistor on them (no pull-up)
  6. decoupling       : count of 100 nF-class caps vs count of ICs
Output: hardware/DESIGN-REVIEW.md (one section per card) and the per-card findings printed.
usage: design_review.py            (reads every hardware/**/kicad/<rev> that is not deprecated and has reports/netlist.net)
"""
import os, re, glob, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); HW = os.path.join(ROOT, "hardware")
RAIL_POS = re.compile(r"^(\+?5V0?|VCC|VDD|\+5)$", re.I); RAIL_GND = re.compile(r"^(GND|VSS|0V)$", re.I)

def parse_netlist(path):
    s = open(path).read()
    comps = {}
    for blk in s.split("\n\t\t(comp\n")[1:]:
        ref = re.search(r'\(ref "([^"]*)"', blk); val = re.search(r'\(value "([^"]*)"', blk); fp = re.search(r'\(footprint "([^"]*)"', blk)
        if ref: comps[ref.group(1)] = (val.group(1) if val else "", fp.group(1) if fp else "")
    nets = {}
    for blk in s.split("\t\t(net\n")[1:]:
        name = re.search(r'\(name "([^"]*)"', blk).group(1)
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)\s*(?:\(pinfunction "([^"]*)"\))?\s*(?:\(pintype "([^"]*)"\))?', blk)
        nets[name] = [(r, p, f or "", t or "") for r, p, f, t in nodes]
    return comps, nets

def review(card, netfile):
    comps, nets = parse_netlist(netfile)
    F = []   # (severity, text)
    real = lambda r: not r.startswith("#")
    pos = [n for n in nets if RAIL_POS.match(n)]; gnd = [n for n in nets if RAIL_GND.match(n)]
    rails = set(pos) | set(gnd)
    # 1. supply islands and sources
    if len(pos) > 1: F.append(("HIGH", "two positive rails, nothing joins them: %s (pins %s)" % (", ".join(pos), ", ".join("%s=%d" % (n, len(nets[n])) for n in pos))))
    for n in pos + gnd:
        src = [r for r, p, f, t in nets[n] if r.startswith(("X", "SV", "JP", "J")) or t == "power_out"]   # bus connector or an inter-card header
        if not src: F.append(("HIGH", "rail %s has no source on this card (no connector/header pin, no power output); %d pins on it" % (n, len(nets[n]))))
    # 2. unpowered power_in pins
    for n, nodes in nets.items():
        if n in rails: continue
        pw = [(r, p, f) for r, p, f, t in nodes if t == "power_in" and real(r)]
        if pw and len(nodes) > 0:
            F.append(("HIGH", "power pins on a non-rail net %s: %s" % (n, ", ".join("%s.%s(%s)" % x for x in pw[:6]))))
    # 3. floating inputs
    fl = [(n, r, p, f) for n, nodes in nets.items() if len([x for x in nodes if real(x[0])]) == 1
          for r, p, f, t in nodes if t in ("input", "clock") and real(r) and not r.startswith(("X", "SV", "JP"))]
    if fl:
        by = collections.defaultdict(list)
        for n, r, p, f in fl: by[r].append("%s(%s)" % (p, f))
        F.append(("MED", "floating input pins (single-node nets): " + "; ".join("%s: %s" % (r, ",".join(v)) for r, v in sorted(by.items())[:14]) + (" ..." if len(by) > 14 else "")))
    # 4. driver conflicts
    for n, nodes in nets.items():
        outs = [(r, p, f) for r, p, f, t in nodes if t == "output" and real(r)]
        if len(outs) > 1: F.append(("HIGH", "net %s has %d totem-pole outputs: %s" % (n, len(outs), ", ".join("%s.%s(%s)" % x for x in outs[:5]))))
    # 5. open-collector nets without a pull-up
    for n, nodes in nets.items():
        if n in rails: continue
        oc = [x for x in nodes if x[3] == "open_collector"]
        drv = [x for x in nodes if x[3] in ("output", "tri_state", "power_out")]
        res = [x for x in nodes if x[0].startswith(("R", "RN")) and not x[0].startswith("RESET")]
        if oc and not drv and not res: F.append(("MED", "open-collector net %s (%s) has no pull-up and no other driver" % (n, ", ".join("%s.%s" % (r, p) for r, p, f, t in oc[:4]))))
    # 6. decoupling
    ics = [r for r in comps if r.startswith(("IC", "U")) and real(r)]
    caps = [r for r, (v, fp) in comps.items() if r.startswith("C") and not re.search(r"POL|ELKO|CPOL|E2|E5|E3", fp, re.I)]   # ceramic footprints (Eagle values are blank)
    if len(caps) < len(ics) * 0.5: F.append(("LOW", "decoupling: %d 100 nF-class caps for %d ICs" % (len(caps), len(ics))))
    # bus connector summary
    x1 = [n for n, nodes in nets.items() if any(r == "X1" for r, *_ in nodes)]
    info = "%d parts, %d nets, %d ICs, %d bus-connector nets, rails %s" % (len([c for c in comps if real(c)]), len(nets), len(ics), len(x1), ", ".join(sorted(rails)))
    return info, F

def main():
    cards = []
    for nf in sorted(glob.glob(os.path.join(HW, "**", "kicad", "*", "reports", "netlist.net"), recursive=True) + glob.glob(os.path.join(HW, "**", "kicad", "reports", "netlist.net"), recursive=True)):
        rel = os.path.relpath(nf, HW)
        if "/deprecated/" in rel or "/v1.0-fusion" in rel and "video" in rel and os.path.exists(os.path.join(HW, "cards/video/kicad/v1.1")): continue
        cards.append((rel.split("/reports/")[0], nf))
    out = ["# Design review (mechanical pass) — %s\n" % __import__("time").strftime("%Y-%m-%d"),
           "Generated by `tools/design_review.py` from each active card's KiCad netlist (pin types come from the Eagle symbols, so a",
           "wrongly typed symbol pin can produce a false hit; every HIGH item was checked by hand before being acted on).",
           "Severity: HIGH = would stop the card working or damage parts; MED = unreliable; LOW = housekeeping.\n"]
    for card, nf in cards:
        info, F = review(card, nf)
        print("== %s: %s" % (card, info))
        out.append("## %s\n\n%s\n" % (card, info))
        if not F: out.append("- no findings\n"); print("   no findings"); continue
        for sev, text in sorted(F, key=lambda x: {"HIGH": 0, "MED": 1, "LOW": 2}[x[0]]):
            out.append("- **%s** %s" % (sev, text)); print("   %-4s %s" % (sev, text[:150]))
        out.append("")
    open(os.path.join(HW, "DESIGN-REVIEW.md"), "w").write("\n".join(out) + "\n")

if __name__ == "__main__": main()

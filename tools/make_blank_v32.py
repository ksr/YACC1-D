#!/usr/bin/env python3
"""Derive hardware/bus/blank-card/eagle/v3.2/ from v3.1/ by renaming the four C3-C6 bus nets to the Bus V3.2 names
(and the bus ribbon label + silk title). Pure text substitution on the Eagle XML; see the v3.2 README."""
import re, os, xml.etree.ElementTree as ET
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, "hardware/bus/blank-card/eagle/")
ren = {"-ADDR-REG-RD0": "ADDR-REG-ID0", "-ADDR-REG-LD0": "ADDR-REG-ID1", "-ADDR-REG-RD1": "ADDR-REG-ID2", "-ADDR-REG-LD1": "ADDR-REG-ID3"}
bus32 = re.search(r'<bus name="([^"]*)"', open(os.path.join(ROOT, "hardware/bus/bus-template/eagle/v3.2/Bus Template V3.2.sch")).read()).group(1)
sch = open(B + "v3.1/Blank V3.1.sch").read(); brd = open(B + "v3.1/Blank V3.1.brd").read()
sch = sch.replace('<bus name="%s"' % re.search(r'<bus name="([^"]*)"', sch).group(1), '<bus name="%s"' % bus32)
for a, b in ren.items():
    for pat in ('name="%s"' % a, '>%s<' % a):
        sch = sch.replace(pat, pat.replace(a, b)); brd = brd.replace(pat, pat.replace(a, b))
brd = brd.replace(">YACC1 Blank V1.0<", ">YACC1 Blank V3.2<"); sch = sch.replace(">YACC1 Blank V1.0<", ">YACC1 Blank V3.2<")
assert not any(a in sch or a in brd for a in ren)
os.makedirs(B + "v3.2", exist_ok=True)
open(B + "v3.2/Blank V3.2.sch", "w").write(sch); open(B + "v3.2/Blank V3.2.brd", "w").write(brd)
ET.parse(B + "v3.2/Blank V3.2.sch"); ET.parse(B + "v3.2/Blank V3.2.brd"); print("Blank V3.2 written")

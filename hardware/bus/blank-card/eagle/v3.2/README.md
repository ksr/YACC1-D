# Blank V3.2 (derived 2026-09-20, not fabricated)

Blank V3.1 with its bus signal names brought up to Bus Template V3.2, so the next card starts from the naming the
machine is actually built to. The ONLY changes versus `../v3.1/`:

| Pin | V3.1 name | V3.2 name |
|---|---|---|
| C3 | -ADDR-REG-RD0 | ADDR-REG-ID0 |
| C4 | -ADDR-REG-LD0 | ADDR-REG-ID1 |
| C5 | -ADDR-REG-RD1 | ADDR-REG-ID2 |
| C6 | -ADDR-REG-LD1 | ADDR-REG-ID3 |

plus the bus ribbon label (copied from `Bus Template V3.2.sch`) and the silkscreen title (was still "YACC1 Blank V1.0",
now "YACC1 Blank V3.2"). Parts, connectivity, outline and copper are byte-for-byte those of V3.1 apart from the four
net/signal names. Made by text substitution in the Eagle XML by `tools/make_blank_v32.py`; verified with
`tools/compare_eagle.py` (identical parts and connectivity to V3.1; zero renamed nets against the V3.2 template).
Open it once in Eagle/Fusion and re-save before using it as a template.

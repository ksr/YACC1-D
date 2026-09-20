# Bus connector / signal specification

The 96-pin DIN 41612 bus pinout and signal names, as the PDF that every card folder used to carry a copy of.
Canonical = **V3.2** (2020-09-10; matches `hardware/bus/bus-template/eagle/v3.2/` and the machine as built).

| File | Date | Meaning |
|---|---|---|
| `YACC1 Connector - YACC 3.0-old.pdf` | 2020 | the first 2020 bus (pre -VMA) |
| `YACC1 Connector - V3 - June-18-2020.pdf` | 2020-06-18 | V3 with the Address+TMP strobes on C3–C6 (-ADDR-REG-RD/LD) |
| `YACC1 Connector - V3.1.pdf` | 2020-08 | adds -VMA (row C pin 12) |
| `YACC1 Connector - V3.2.pdf` | 2020-09-10 | C3–C6 = ADDR-REG-ID0..3 (index-register number) – **current** |

Which spec each card folder was drawn against (the copy it carried before consolidation, 2026-09-20):

| Card folder | Spec in the folder |
|---|---|
| bus/blank-card v3.1 | V3.1 |
| cards/address-tmp v1.0 | V3 June-2020 |
| cards/alu v3.0-2layer | V3 June-2020 + YACC 3.0-old |
| cards/alu v3.1, v3.1-resubmit, v3.1-buried-vias, **v3.2** | V3 June-2020 |
| cards/io v1.0 | V3 June-2020 + V3.1 |
| cards/io **v1.1**, mem-register v1.0, mem-switch v1.0 / **v1.1** | V3.1 |
| cards/memory v1.0, v1.1, v1.2, **v1.3** | V3 June-2020 |
| cards/register v1.0, **v1.1** | V3 June-2020 |

Note that no card folder carried V3.2: the built cards were re-saved with V3.2 net names on 2020-11-29 (see
`hardware/FABRICATED.md`), but the PDF beside them was never refreshed. The signal table in machine-readable form is
`embedded/libraries/YACC/YACC_Common_header.h` (bus tester) and `firmware/microcode/yaccsignaldata2.h` (sequencer).

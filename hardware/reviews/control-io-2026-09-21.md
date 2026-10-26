# Design review — control paths and I/O (sequencer logic/memory, IO, bus tester, backplane, video) — 2026-09-21

Second pass after the mechanical one in [`mechanical-2026-09-21.md`](mechanical-2026-09-21.md). Read from the KiCad netlists (`reports/netlist.net`, pin
types from the Eagle symbols), chip values from the Eagle boards, the firmware that drives the ATmegas
(`embedded/bus-tester/bus-driver`, `embedded/sequencer-card/sequencer4`) and the microcode generator
(`firmware/microcode/ucode-generator2`). Gate pin-outs were checked against the symbol pin functions (I0/I1/O for
7400/08/32, O/I/I for 7402; 74175/74/192/244/374 pin functions as printed in the netlist).

Every finding: the trace (ref.pin -> net -> ref.pin, chip types), the failure scenario, severity
(HIGH = stops the card / damages parts, MED = unreliable or latent, LOW = housekeeping), and how to confirm it on
the bench. Already-known items (BACKLOG.md, video README) are not repeated except where a new detail changes them.
Report only; no redesign.

Scripts used (not committed): a netlist dumper (parts + nets with pin function/type), an SV1/SV2 pin-by-pin
comparator, a bus-driver-table-vs-tester-wiring check and a microcode-bit-vs-RAM-wiring check; the results of the
three checks are in the "checked, no issue" lists below.

Each section of the review is in its card's own `reviews/` folder:

| Section | Card | File |
|---|---|---|
| 1 | Sequencer logic v2.1 | [`hardware/cards/sequencer-logic/reviews/v2.1-control-io-2026-09-21.md`](../cards/sequencer-logic/reviews/v2.1-control-io-2026-09-21.md) |
| 2 | Sequencer memory v2.1 | [`hardware/cards/sequencer-memory/reviews/v2.1-control-io-2026-09-21.md`](../cards/sequencer-memory/reviews/v2.1-control-io-2026-09-21.md) |
| 3 | IO card v1.1 | [`hardware/cards/io/reviews/v1.1-control-io-2026-09-21.md`](../cards/io/reviews/v1.1-control-io-2026-09-21.md) |
| 4 | Bus tester v1.1 | [`hardware/cards/bus-tester/reviews/v1.1-control-io-2026-09-21.md`](../cards/bus-tester/reviews/v1.1-control-io-2026-09-21.md) |
| 5 | Backplane v2.0 | [`hardware/bus/backplane/reviews/v2.0-control-io-2026-09-21.md`](../bus/backplane/reviews/v2.0-control-io-2026-09-21.md) |
| 6 | Video card v1.1 | [`hardware/cards/video/reviews/v1.1-control-io-2026-09-21.md`](../cards/video/reviews/v1.1-control-io-2026-09-21.md) |

This page keeps the parts that belong to no single card: the cross-card notes and the summary.

---

## Cross-card notes

- Two drivers on -RESET, OUT, -REG-LD-LO/HI, REG-RD-ID, REG-LD-ID, ADDR-REG-ID (logic card totem poles vs tester
  push-pull) — [1.1](../cards/sequencer-logic/reviews/v2.1-control-io-2026-09-21.md) / [4.1](../cards/bus-tester/reviews/v1.1-control-io-2026-09-21.md) — is the item that decides whether the tester can ever be used with the logic card in.
- Reset polarity is consistent across the cards: -RESET active low on C30; logic card inverts its internal RESET
  (IC36 p6); IO card re-inverts to the 16550's active-high pin; memory card uses it as a 74LS74 preset; video
  card as the 6845's active-low reset; register card into a 4077; tester and sequencer-memory keep their local
  ATmega resets separate.
- Floating-bus dependence: the machine relies on "LS input floating = high = inactive" for every strobe during the
  54 s microcode load and whenever the tester tri-states; the backplane has no pull-ups ([5.1](../bus/backplane/reviews/v2.0-control-io-2026-09-21.md)).
- BOM/value gaps found on the way (all "value" blank in the Eagle boards): logic card R-values are present, but
  IO card RN2 and R1; bus tester RN1–RN4; video Q2, C1 ("1"), C16 ("10.0"); backplane C1–C8. Each is load-bearing
  for one of the findings above.

## Summary

HIGH: ([1.1](../cards/sequencer-logic/reviews/v2.1-control-io-2026-09-21.md)/[4.1](../cards/bus-tester/reviews/v1.1-control-io-2026-09-21.md)) the logic card drives 17 bus lines regardless of -BUS-EN — IC4/IC5/IC18 74LS244 enables come
from the pipeline, not from -BUS-EN, and -REG-LD-LO/HI, -RESET and OUT are plain LS04/ALS02 outputs — while the
bus tester's firmware makes every one of those lines a push-pull output at boot; the planned v2.2 "CPU off" fix
must cover them. ([1.2](../cards/sequencer-logic/reviews/v2.1-control-io-2026-09-21.md)) IC33/IC34 and the register-card counters are drawn and BOM'd as 74LS192 decade counters;
the microcode layout needs binary parts, so either the boards carry 193s or the fetch runs by accident — read the
chips, fix the BOM. ([6.1](../cards/video/reviews/v1.1-control-io-2026-09-21.md)) The video card's 6845 E clock is an RC one-shot (IC26/IC27 p12/R1/C1/IC1) with no
pull-up on the open-collector output, so C1 can only recharge through IC1's input current; at run speed E is
unreliable and the CRTC is unreachable independently of the RS fix. MED: ([1.3](../cards/sequencer-logic/reviews/v2.1-control-io-2026-09-21.md)) reset does not reload the pipeline
(only reset release does), so a stale -MEM-WR/-VMA word sits on the bus for the whole reset with the EEPROM mapped
everywhere; ([1.4](../cards/sequencer-logic/reviews/v2.1-control-io-2026-09-21.md)) JP2 would hold the sequencer-memory ATmega in reset because SPARE3 is 0 in every microcode line;
([6.2](../cards/video/reviews/v1.1-control-io-2026-09-21.md)/[6.3](../cards/video/reviews/v1.1-control-io-2026-09-21.md)) the character clock is a ~50 ns self-clear runt used as the 74LS166 load, and 74HC160 inputs are driven
by LS levels. LOW items: interrupt jumper needs two jumpers / edge mode fires on release; combinational
-REG-LD-LO/HI (not exercised by the current microcode); floating pipeline outputs and a pull-up-free backplane;
sequencer-memory RAM control lines float during ATmega reset; DTR auto-reset dead-ends on both ATmega cards;
IO strobes through OC inverters with an unrecorded RN2; IO device-select bits not mutually exclusive; LCD
backlight resistor; video read-back latch enabled on writes; 6845 LPSTB floating; tester pull-ups RN1–RN4 of
unknown value. Checked and clean: SV1/SV2 and JP1 pinouts (80/80, 4/4), microcode bit map to RAM to pipeline
(64/64), bus-driver signal table to tester wiring to V3.2 pinout (52/52), sequencer4 run-mode RAM gating, I2C
address maps, UART register/chip select, reset polarity on every card, the IO XTAL2 "floating" item (false
positive), backplane power distribution.

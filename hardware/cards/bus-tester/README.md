# cards/bus-tester — Bus Test Card

ATmega328 + MCP23017 port expanders driving/monitoring every bus line from a serial console (FTDI, 19200):
the card the host scripts in `tools/busdrv.py` and `embedded/bus-tester/` talk to.

- `eagle/v1.1/` – **the board in use** (Ken 2026-09-20). Board dated 2018-03-15 = the gen-1 TESTER-PROD-V1.1
  (its gerbers in `fab/` are byte-identical to the 2016 ones); schematic re-saved 2020-08-15. The May-2020 note in
  this folder ("FIX on PCB: join R21 to R9 to GND, 8 LEDs – reflected in schematic, PCB uses a jumper") describes the
  rework applied to this board. `Build Notes.rtf` is the bring-up procedure.
- `eagle/v3.1/` – the July-2020 redesign, never ordered: latches IC11–IC15 drive the bus instead of the MCP23017
  outputs, soft bus-enable and soft reset from the ATmega, bypass caps, reset switch removed. 114 x 178 mm, 4-layer,
  routed, CAM output in `fab/`. `v3.11-horizontal-unrouted/tester.brd` is the next day's reshape to 243 x 114 mm with
  the routing removed (the "V3.11" folder, folded in 2026-09-20; its schematic was identical). `Notes.rtf` here is the
  V3.11 superset: adds "bypass cap for ATmega" and "should IN/INT support read mode, reportable through the CLI".
- Gen-1 tester boards (TESTER-PROD-V1.0/V1.1, 2016) are in `archive/gen1-2015-2018/`.

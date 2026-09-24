# CompactFlash interface (on the I/O card v2.0) — theory of operation

The YACC1's mass storage: a CompactFlash card, run in 8-bit True IDE mode, reached through two I/O ports, **P4 and
P5**. It is what lets Y1/OS leave the emulators: the ROM monitor's `O` command boots the OS from the card, and the OS's
file layer reads and writes its sectors.

Written 2026-09-23 from the YACC1-D tree, while the interface was being designed (not yet built); restructured the
same evening, when it moved from its own card onto the I/O card v2.0.

Sources: `hardware/cards/cf/kicad/v1.0/cf_netlist.py` (the circuit as first designed, a standalone card: everything
after the port decoder is unchanged on the I/O card v2.0), `hardware/cards/io/kicad/v2.0/README.md` (the v2.0 board and
its reference designators), `docs/cards/io.md` (the I/O card, its decoder IC5 and its straps), `docs/system/OS-PLAN.md`
(the decision for two ports in I/O space, and the 2026-09-23 update moving them to P4/P5), `docs/system/BUS.md` (the
bus pins), `firmware/microcode/ucode-generator2/io.c` (the I/O strobe timing), `firmware/monitor/monitor.asm` (the CF
driver: `cfwait`, `cfinit`, `cfread`, `cfwrite`), `software/cfmodel.h` (the emulators' model of the interface),
`~/Developer/p8x/generators/gen_eagle.py` (the P8X CF card, the source of the proven IDE pinout),
`docs/datasheets/` (74LS parts). The ATA and CompactFlash timing figures quoted below are the standard PIO mode 0 values;
**To verify:** against the datasheet of the card actually used (none is in the tree).

## 0. Where the circuit lives (2026-09-23)

- **CF card v1.0** (`hardware/cards/cf/kicad/v1.0/`): the interface as a card of its own, five chips, decoding **P8/P9**
  with its own 74LS138 (U1, enabled by IO-ADDR3). Routed and checked, **never ordered; superseded**.
- **I/O card v2.0** (`hardware/cards/io/kicad/v2.0/`, being designed, not built): the backplane has only eight slots, so
  the interface moved onto the I/O card. The I/O card's own 74LS138 (IC5), strapped to P0-P7 by its IO-ADDR-HL header,
  had six unused outputs; **Y4 (-IO-SEL4) and Y5 (-IO-SEL5) become the CF's select and data ports**, and U1 goes. The
  CF section is four chips — the 74LS32 strobe gating, the 74LS175 register latch, the 74LS08 enables/reset/ACT LED and
  the 74LS245 data buffer — plus the 40-pin IDE header, which takes a SinLoon CF-to-IDE adapter mounted above the card
  on standoffs. It shares the I/O card's bus connector; the CF's DASP LED is dropped. P2 was not used because it is the
  emulators' console and test-output port.
- The ROM driver (build `ROM 2026-09-23B`, not yet burned: `firmware/rom/README.md`) and both emulators
  (`software/cfmodel.h`) use **P4/P5**. The chip in the machine on 2026-09-23 is the earlier build, which still talks
  to P8/P9.
- **Consequences for the I/O card's jumpers**: the IO-ADDR-HL strap must stay at P0-P7, and neither the IO-ADDR nor the
  DATA-ADDR header may select P4 or P5 (`docs/cards/io.md` section 3.1).
- If the v1.0 card were ever built after all, its decode would have to change to match the ROM: U1 G1 (pin 6) = VCC,
  G2A (pin 4) = IO-ADDR3, G2B (pin 5) low, and the two selects taken from Y4 (pin 11) and Y5 (pin 10) instead of Y0/Y1.

The rest of this document describes the circuit by function, with the v1.0 reference designators (U2..U5, J1, RN1…)
as names; the v2.0 board's designators are chosen in its own design and listed in
`hardware/cards/io/kicad/v2.0/README.md`.

## 1. Purpose and place in the machine

A CompactFlash card can pretend to be an IDE hard disk ("True IDE mode"). In that mode it has eight registers, the
ATA task file, and talks 8 bits at a time once told to (SET FEATURES $01, which the ROM's `cfinit` sends). So the
interface the YACC1 needs is small: something to choose which of the eight registers the next access means, a buffer
to put the data bus onto the CF's data lines in the right direction, and read and write strobes that happen only when
the CPU is talking to the CF.

The interface sits in **I/O space**, not memory space, on two ports (`docs/system/OS-PLAN.md`, decision 1 and its
2026-09-23 update):

| Port | Direction | What |
|---|---|---|
| P4 | write | a 4-bit latch: bits 0..2 = the ATA register number (0 data, 1 error/features, 2 sector count, 3..5 LBA 0..2, 6 drive/head, 7 status/command), bit 3 = CF reset (1 = held in reset), bits 4..7 ignored |
| P5 | read/write | the register P4 selected |

(P8 and P9 on the v1.0 card and in the ROM builds up to `ROM 2026-09-23`.)

A sector read is therefore: select the LBA registers one by one on P4 and write their bytes on P5, write the READ
SECTORS command, poll status, then select register 0 once and read P5 512 times. The ROM driver does exactly that;
selecting the data register once and streaming 512 bytes costs one `OUTI` for the whole sector.

```
            bus                    I/O card v2.0, CF section (v1.0 names)                  40-pin IDE header
 IOADDR0..2 ─────►┌──────────┐ -IO-SEL4 ┌────────┐ LATCHCLK ┌──────────┐ DA0..2 ───────────► J1 35/33/36
 IOADDR3 ─strap──►│ IC5 138  ├─────────►│ U2 32  ├─────────►│ U3 175   │ -SRST ─┐
 (P0-P7)          │ Y4=P4    │ -IO-SEL5 │ (OR:   │          │ latch    │        │  ┌────────┐
                  │ Y5=P5    ├─────────►│ strobe │ -IOR ────┼──────────┼────────┼─►│ U4 08  │ -CFRESET ──► J1 1
                  └──────────┘          │ gating)│ -IOW ─┐  └──────────┘        └─►│ (AND)  │ -CFOE ─┐
 -IO-WR ───────────────────────────────►│        │       │   ▲ DATA0..3           │        │ ACTK ──┼─► ACT LED
 -IO-RD ───────────────────────────────►└────────┘       │   │  -RESET ─────────► └────────┘        │
                                                         │   │                                      │
 DATA0..7 ◄────────────────────────────────────────────► │ ┌─┴──────────┐ CFD0..7 (pull-ups RN1) ─────┼─► J1 17..3 (odd)
                                                         └►│ U5 245     │◄───────────────────────────┘ -OE
                                                DIR=-IOR ─►│ A=bus B=CF │
                                                           └────────────┘   J1 23 -IOW, 25 -IOR, 37 -CS0=GND, 38 -CS1=VCC
```

On the v1.0 card the decoder box was its own U1 (Y0 = P8, Y1 = P9; nets `-P8SEL`, `-P9SEL`).

## 2. Bus signals

| Signal | Pin | Direction | Use by the CF section |
|---|---|---|---|
| `DATA0..7` | A19–A26 | both | through U5 to and from the CF; DATA0..3 also into the P4 latch |
| `IO-ADDR0..3` | C7–C10 | in | the port number, decoded by the I/O card's IC5 (IO-ADDR3 through the IO-ADDR-HL strap) |
| `-IO-RD` | B25 | in | gated with the port-5 select into the CF's `-IOR` |
| `-IO-WR` | B26 | in | gated with the port-4 select into the latch clock, and with port 5 into `-IOW` |
| `-RESET` | C30 | in | clears the latch (register 0, reset bit off) and resets the CF |
| VCC, GND | A/B/C 2, 31 and 1, 32 | | power |

The pins were cross-checked on 2026-09-23 against the connector of the I/O card v1.1 schematic, a card that works in
the machine; on v2.0 it is the same connector. The CF section reads nothing else from the bus: no memory address
lines, no `-VMA`, no `-BUS-EN`. It drives the data bus only while the CPU reads port 5.

## 3. Circuit, part by part

**The port decoder: the I/O card's IC5, 74LS138** (on v1.0 the card's own U1). Its select inputs take IO-ADDR0..2; the
IO-ADDR-HL strap enables it only while IO-ADDR3 is low (G1 = VCC, G2A = IO-ADDR3), so it answers P0-P7. Y4 goes low
for port 4 and Y5 for port 5. Y0/Y1 are the I/O card's own control and data ports (through its IO-ADDR and DATA-ADDR
headers), Y2 is the emulators' console port with nothing wired on the hardware, Y3, Y6 and Y7 stay spare and reserved
to the I/O card. The select outputs carry no timing: they follow the port number, which the microcode sets two or three
steps before the strobe (section 4). On v1.0, U1 had G1 = IO-ADDR3 and both active-low enables tied low, so Y0/Y1 were
P8/P9 and nothing responded in P0-P7.

**U2, 74LS32: strobe gating.** Three OR gates, each an active-low AND: the output is low only when both inputs are low.
- `-IO-SEL4` OR `-IO-WR` = `LATCHCLK`: low while the CPU writes port 4, rising when the write strobe ends.
- `-IO-SEL5` OR `-IO-RD` = `-IOR`, the CF's read strobe.
- `-IO-SEL5` OR `-IO-WR` = `-IOW`, the CF's write strobe.
The fourth gate is unused, its inputs tied to ground. (On v1.0 the two selects were U1's `-P8SEL` and `-P9SEL`.)

**U3, 74LS175: the register-select latch.** Four D flip-flops clocked on the rising edge of `LATCHCLK`, that is at the
end of an `OUT` to port 4, taking DATA0..3. Q1..Q3 drive the CF's register address DA0..2 directly, so the register
number is stable long before and long after every access to port 5. Q4 is the reset bit; its inverted output `-SRST`
goes to U4. The bus `-RESET` clears all four, so after a front-panel reset the card points at register 0 and is out of
reset.

**U4, 74LS08: enables and reset.** Three AND gates, each an active-low OR:
- `-IOR` AND `-IOW` = `-CFOE`: low during any access to port 5. It enables the buffer U5.
- `-RESET` AND `-SRST` = `-CFRESET`: the CF is reset while the bus reset is active or while software holds bit 3 of
  P4 at 1.
- `-CFOE` AND `-CFOE` = `ACTK`: a buffered copy that sinks the ACT LED, so the LED current does not load the enable.

**U5, 74LS245: the data buffer.** Its A side is the bus DATA0..7, its B side the CF's D0..7. `-OE` is `-CFOE`, so it
connects the two only during a port-5 access. `DIR` is `-IOR`: high (A to B, bus to CF) except during a read, when it
is low (B to A, CF to bus). So the CF section drives the data bus only while the CPU reads port 5, and never fights
another card or the rest of the I/O card.

**J1: the 40-pin IDE header**, for a commercial CF-to-IDE adapter, as on the P8X. The pin assignment is the P8X card's,
which works: data D0..7 on pins 17, 15, 13, 11, 9, 7, 5 and 3; DA0 35, DA1 33, DA2 36; `-IOW` 23, `-IOR` 25; reset
pin 1; grounds on 2, 19, 22, 24, 26, 30 and 40. D8..15 on the even pins 4..18 are left open: the card runs 8 bits wide.
The other pins:
- `-CS0` (37) is tied low and `-CS1` (38) high: see section 4 for why chip select is not gated.
- `CSEL` (28) grounded: the CF is the master drive.
- `IORDY` (27), `-PDIAG` (34) and `-DASP` (39) have 10k pull-ups; on v1.0 `-DASP` also lit a DASP LED, the CF's
  own activity signal; v2.0 drops that LED.
- `-DMACK` (29) is held high through 10k: no DMA.
- `DMARQ` (21), `INTRQ` (31) and `-IOCS16` (32) are unused: the driver polls, and the card never asks for 16-bit
  transfers once in 8-bit mode.
- Pin 20 is the IDE key position. Some CF-to-IDE adapters take +5 V there; jumper JP1 connects it to VCC for those.
  Leave JP1 open otherwise: on a real IDE cable pin 20 is blocked or unconnected.

**RN1**, a 10k SIP network, pulls CF D0..7 up. Without a card in the adapter those lines would float; with the pull-ups
a status read returns $FF, which has the BSY bit set, so the ROM's bounded `cfwait` times out and reports `CF ERROR`
instead of acting on noise.

**J2: adapter power** (v1.0). A 4-pin header in the floppy-power order: pin 1 +5 V, pins 2 and 3 ground, pin 4
(+12 V on a floppy lead) unconnected. Most CF-to-IDE adapters take their power through a floppy connector. C6, 10 µF,
sits beside it: a CF card can draw about 100 mA in bursts. **To verify:** the power connector and pinout of the adapter
Ken uses (on v2.0 the SinLoon adapter sits above the card on standoffs; how it takes its power is part of that design).

**LEDs.** ACT (yellow) during every port-5 access, so a sector transfer shows as a flicker, through a 1k resistor. The
v1.0 card also had PWR (green) on VCC and DASP (red), driven by the CF itself while it is busy; on v2.0 the I/O card's
own PWR LED serves and DASP is dropped. Every IC has its own 100 nF capacitor.

## 4. Timing

The microcode sets the port number on IO-ADDR0..3 two or three steps before the strobe and holds it to the end of the
instruction (`firmware/microcode/ucode-generator2/io.c`: `setIo()` is written into every following step;
`docs/isa/INP.json`, `OUTA.json`, `OUTI.json` for the step numbers):

| Instruction | IO-ADDR valid from | strobe low | strobe released | IO-ADDR released |
|---|---|---|---|---|
| `OUTI Pn,byte` | step 5 | `-IO-WR` step 8 | step 9 | end of instruction |
| `OUTA Pn` | step 6 | `-IO-WR` step 9 | step 10 | end of instruction |
| `INP Pn` | step 6 | `-IO-RD` step 8 | end of instruction | end of instruction |

A step is two clocks, so at 1 MHz every margin here is at least 2 µs. Against the CF's PIO mode 0 figures (address
set-up before a strobe about 70 ns, strobe width about 165 ns, data set-up for a write about 60 ns, holds 20–30 ns)
there is nothing tight:

- **The register number** comes from the latch, written by an earlier instruction, so it is valid for thousands of
  nanoseconds before and after every port-5 strobe.
- **Port-5 strobes** start at least two steps after the port select settles, so `-IOR`/`-IOW` begin with a single clean edge.
  A write ends one step before the port number changes, so the CF samples its data on a steady bus. For an `OUTA` the
  accumulator stays on the bus to the end of the instruction; for an `OUTI` the memory keeps driving the operand byte
  until after the strobe.
- **The latch clock** rises at the end of the port-4 write strobe while the port select is still steady, and U3
  samples DATA0..3 at that edge, while the bus still holds the byte.
- **The one simultaneous edge** is at the end of an `INP`: the port number and `-IO-RD` are both released by the same
  clock. `-IOR` is an OR of the two, so it simply goes high once, at whichever arrives first, with no glitch. The CPU
  has already taken the byte into the accumulator a step earlier (`-AC-LD`, step 9). This is why **chip select is not
  gated by the decoder**: if `-CS0` were the port-5 select, it would rise straight from the decoder while `-IOR` rises
  one OR-gate delay later, so chip select would end before the read strobe. That breaks the CF's chip-select hold time
  after `-IOR`, and a data-register read is exactly the access where the CF advances its sector-buffer pointer on the
  end of `-IOR`. With `-CS0` tied low permanently, the strobes alone define each cycle, which True IDE allows.

- **The buffer's direction at the end of a read.** `DIR` is `-IOR` itself, while the enable `-CFOE` comes one AND
  gate later. So when `-IOR` rises, the 245 turns back towards the CF (A to B) about one gate delay, roughly 10 ns,
  before it switches off, and for that moment it can drive the CF's data lines while the CF is still releasing them.
  The CPU took its byte a step earlier, so no data is at risk; the effect is a brief current spike through two
  drivers. The alternatives are worse: taking direction from the write strobe instead moves the same race to the
  start of every write, where the bus byte is being driven, and the bus carries no direction signal earlier than the
  strobes (reads and writes use the same port). The P8X CF card has the same arrangement. If it ever shows on a scope
  as ringing on the CF data lines, a revision could delay the rising edge of `DIR` with an RC or spare gates.

## 5. Programming model

What the ROM driver does (`firmware/monitor/monitor.asm`; the same sequence is in `software/cfmodel.h`):

```
cfwait:  P4 <- 7, then INP P5 until status BSY (bit 7) is clear (bounded: an absent card reads $FF and times out)
cfinit:  cfwait
         P4 <- 6, P5 <- $E0           drive/head: LBA mode, master, LBA bits 24..27 = 0
         P4 <- 1, P5 <- $01           features: 8-bit transfers
         P4 <- 7, P5 <- $EF           SET FEATURES
         cfwait; ACC = the ERR bit (0 = ok)
cfsetl:  P4 <- 3, 4, 5 with P5 <- CFLBA0, CFLBA1, CFLBA2 (the ROM variables at $0F10..$0F12)
         P4 <- 6, P5 <- $E0; P4 <- 2, P5 <- 1 (one sector)
cfread:  cfwait, cfsetl, P4 <- 7, P5 <- $20 READ SECTORS, wait for DRQ (bit 3)
         P4 <- 0, then 512 x INP P5   the sector, one byte per read, into the buffer at R7
cfwrite: the same with $30 WRITE SECTORS and 512 x OUTA P5
```

Status bits: 7 BSY, 6 DRDY, 3 DRQ, 0 ERR. The emulators model the card with these commands ($EF, $EC IDENTIFY, $20, $30)
behind a disk image (`-c disk.img`); an absent card reads $FF, as the real card's pull-ups make it.

**Bit 3 of P4** holds the CF in reset while 1. The ROM never sets it (it writes register numbers 0..7), and the
emulators ignore it. It is there so a later driver can recover a card that stops answering without a front-panel reset:
write 8 to P4, wait at least 25 µs, write 0, then run `cfinit` again. **To verify:** the reset pulse and recovery time
of the card used; 25 µs is the ATA minimum, CF cards may need up to about 2 ms before BSY clears.

`docs/system/OS-PLAN.md` first pencilled bit 3 as the selector for the ATA control block (the alternate status and
device control registers on `-CS1`). This design ties `-CS1` off instead: the driver polls the ordinary status
register, which gives the same bits, and the device-control soft reset is covered more simply by the hardware reset
bit.

## 6. Jumpers, connectors, LEDs

On the v1.0 card (the v2.0 equivalents, and their designators, are in `hardware/cards/io/kicad/v2.0/README.md`):

| Item | Setting | Purpose |
|---|---|---|
| JP1 | open (default) | fit only for a CF-to-IDE adapter powered on IDE pin 20 |
| J1 | 40-pin IDE header, pin 1 marked | the CF-to-IDE adapter, directly or on a short ribbon |
| J2 | +5 V, GND, GND, n/c | the adapter's power lead |
| LED1 PWR, LED2 ACT, LED3 DASP | | power; any port access; the CF busy (v2.0 keeps only ACT) |

On the I/O card v2.0 the CF depends on the card's own jumpers (`docs/cards/io.md` sections 3.1 and 6): the
`IO-ADDR-HL` strap **must** be at P0-P7 (3-5 and 4-6), which is how the card has always been used, and neither the
`IO-ADDR` nor the `DATA-ADDR` header may sit on -IO-SEL4 or -IO-SEL5 (jumpers on pins 7-8 or 5-6), or the I/O
card's control latch or data port would answer on a CF port as well. **To verify** on the bench before fitting the
adapter.

## 7. Bring-up and test

0. Burn the `ROM 2026-09-23B` build first (`firmware/rom/shipped/rom.bin`, `docs/procedures/BRING-UP.md` section 5;
   the banner ends `ROM 2026-09-23B`). The earlier chip talks to P8/P9, where nothing answers: its `O` prints
   `CF ERROR` whatever the hardware does, so step 1 would prove nothing. Check the console still works (P0/P1 on the
   same card) and the jumpers of section 6.
1. Without the CF adapter: power up, reset, and in the monitor type `O`. With nothing in J1 the pull-ups make status
   read $FF, so `cfinit` should time out and print `CF ERROR` after about a second. That proves the decode, the strobes
   and the buffer direction for reads, without any risk to a card.
2. With the bus tester (port 4 on IO-ADDR0..3, a byte on the data bus, a `-IO-WR` pulse) or a two-instruction program
   entered with the monitor's `E` command (`OUTI P4,n` / `RET`, run with `G`), write to P4 and watch DA0..2 on J1 pins
   35, 33, 36 with a meter or LEDs: each value 0..7 must appear, and bit 3 must pull J1 pin 1 low.
3. Fit the adapter with a card prepared on the Mac: `make -C os`, then `python3 tools/cfcard.py write os/disk.img --disk diskN`
   (`docs/procedures/CF-CARD.md`). Then `O` should boot Y1/OS.
4. `tests/os/*.session` then run on the machine by hand: `dir`, `cat README.TXT`, `hello`.

If it misbehaves: ACT not flickering during `O` means no port-5 strobes (IC5's Y5 and the `IO-ADDR-HL` strap, U2), or
a chip still holding the old ROM; status always $FF with a card fitted means the buffer is not enabled or points the
wrong way (U4 gate 1, U5 DIR); reads right but writes lost means `-IOW` or the data set-up (U2 gate 3); a card that
works once and hangs after a reset suggests the reset path (U3 Q4, U4 gate 2); the console failing once the CF section
is fitted suggests an `IO-ADDR`/`DATA-ADDR` jumper on -IO-SEL4/5.

## 8. History and next revision

- 2026-09-22: the two-port design chosen over an eight-port memory-mapped one like the P8X's
  (`docs/system/OS-PLAN.md`); the emulator model and the ROM driver written against it, on P8/P9.
- 2026-09-23: the circuit written as `hardware/cards/cf/kicad/v1.0/cf_netlist.py`; the KiCad schematic and board are
  generated from it (`hardware/cards/cf/README.md`). Never fabricated.
- 2026-09-23 evening: the ports moved to **P4/P5** and the interface onto the **I/O card v2.0** (the backplane's eight
  slots): the I/O card's IC5 decodes it on Y4/Y5, so U1 is gone and the section is four chips; the DASP and PWR LEDs
  are dropped; the SinLoon CF-to-IDE adapter sits above the card on standoffs. The ROM driver and `software/cfmodel.h`
  moved with it (commit 24378cb; ROM `2026-09-23B`, not yet burned). The v1.0 card is superseded.

For a next revision: a second drive (the P8X card has two headers), `INTRQ` to the bus `-INT` if the OS ever wants
interrupt-driven transfers, and a CF socket on the card itself instead of the adapter (surface-mount on most
footprints, which the YACC1 has avoided so far).

# CompactFlash card (v1.0) — theory of operation

The YACC1's mass storage: a CompactFlash card, run in 8-bit True IDE mode, reached through two I/O ports. It is what
lets Y1/OS leave the emulators: the ROM monitor's `O` command boots the OS from the card, and the OS's file layer reads
and writes its sectors.

Written 2026-09-23 from the YACC1-D tree, while the card was being designed (not yet built).

Sources: `hardware/cards/cf/kicad/v1.0/cf_netlist.py` (the circuit: the single source the schematic and the board are
generated from), `docs/system/OS-PLAN.md` (the decision for two ports in I/O space), `docs/system/BUS.md` (the bus
pins), `firmware/microcode/ucode-generator2/io.c` (the I/O strobe timing), `firmware/monitor/monitor.asm` (the CF
driver: `cfwait`, `cfinit`, `cfread`, `cfwrite`), `software/cfmodel.h` (the emulators' model of the card),
`~/Developer/p8x/generators/gen_eagle.py` (the P8X CF card, the source of the proven IDE pinout),
`docs/datasheets/` (74LS parts). The ATA and CompactFlash timing figures quoted below are the standard PIO mode 0 values;
**To verify:** against the datasheet of the card actually used (none is in the tree).

## 1. Purpose and place in the machine

A CompactFlash card can pretend to be an IDE hard disk ("True IDE mode"). In that mode it has eight registers, the
ATA task file, and talks 8 bits at a time once told to (SET FEATURES $01, which the ROM's `cfinit` sends). So the card
the YACC1 needs is small: something to choose which of the eight registers the next access means, a buffer to put
the data bus onto the CF's data lines in the right direction, and read and write strobes that happen only when the
CPU is talking to this card.

The card sits in **I/O space**, not memory space, on two ports (`docs/system/OS-PLAN.md`, decision 1):

| Port | Direction | What |
|---|---|---|
| P8 | write | a 4-bit latch: bits 0..2 = the ATA register number (0 data, 1 error/features, 2 sector count, 3..5 LBA 0..2, 6 drive/head, 7 status/command), bit 3 = CF reset (1 = held in reset), bits 4..7 ignored |
| P9 | read/write | the register P8 selected |

A sector read is therefore: select the LBA registers one by one on P8 and write their bytes on P9, write the READ
SECTORS command, poll status, then select register 0 once and read P9 512 times. The ROM driver does exactly that;
selecting the data register once and streaming 512 bytes costs one `OUTI` for the whole sector.

```
            bus                                   CF card v1.0                              40-pin IDE header
 IOADDR0..3 ─────►┌──────────┐ -P8SEL ┌────────┐ LATCHCLK ┌──────────┐ DA0..2 ─────────────► J1 35/33/36
                  │ U1 138   ├───────►│ U2 32  ├─────────►│ U3 175   │ -SRST ─┐
                  │ Y0=P8    │ -P9SEL │ (OR:   │          │ latch    │        │  ┌────────┐
                  │ Y1=P9    ├───────►│ strobe │ -IOR ────┼──────────┼────────┼─►│ U4 08  │ -CFRESET ──► J1 1
                  └──────────┘        │ gating)│ -IOW ─┐  └──────────┘        └─►│ (AND)  │ -CFOE ─┐
 -IO-WR ────────────────────────────► │        │       │   ▲ DATA0..3           │        │ ACTK ──┼─► LED2 ACT
 -IO-RD ────────────────────────────► └────────┘       │   │  -RESET ─────────► └────────┘        │
                                                       │   │                                      │
 DATA0..7 ◄──────────────────────────────────────────► │ ┌─┴──────────┐ CFD0..7 (pull-ups RN1) ─────┼─► J1 17..3 (odd)
                                                       └►│ U5 245     │◄───────────────────────────┘ -OE
                                              DIR=-IOR ─►│ A=bus B=CF │
                                                         └────────────┘   J1 23 -IOW, 25 -IOR, 37 -CS0=GND, 38 -CS1=VCC
```

## 2. Bus signals

| Signal | Pin | Direction | Use on this card |
|---|---|---|---|
| `DATA0..7` | A19–A26 | both | through U5 to and from the CF; DATA0..3 also into the P8 latch |
| `IO-ADDR0..3` | C7–C10 | in | the port number, decoded by U1 |
| `-IO-RD` | B25 | in | gated with the port-9 select into the CF's `-IOR` |
| `-IO-WR` | B26 | in | gated with the port-8 select into the latch clock, and with port 9 into `-IOW` |
| `-RESET` | C30 | in | clears the latch (register 0, reset bit off) and resets the CF |
| VCC, GND | A/B/C 2, 31 and 1, 32 | | power |

The pins were cross-checked on 2026-09-23 against the connector of the I/O card v1.1 schematic, a card that works in
the machine. The card reads nothing else from the bus: no memory address lines, no `-VMA`, no `-BUS-EN`. It drives
the data bus only while the CPU reads port 9.

## 3. Circuit, part by part

**U1, 74LS138: the port decoder.** Its select inputs take IO-ADDR0..2 and its active-high enable G1 takes IO-ADDR3, the
two active-low enables are tied low. So Y0 goes low for port 8 and Y1 for port 9, and nothing responds in ports 0..7,
the I/O card's half. Y2..Y7 (ports 10..15) are unused; `docs/system/OS-PLAN.md` reserves them for the next video card
and the PS/2 interface, which will decode their own ports. The select outputs carry no timing: they follow the port
number, which the microcode sets two or three steps before the strobe (section 4).

**U2, 74LS32: strobe gating.** Three OR gates, each an active-low AND: the output is low only when both inputs are low.
- `-P8SEL` OR `-IO-WR` = `LATCHCLK`: low while the CPU writes port 8, rising when the write strobe ends.
- `-P9SEL` OR `-IO-RD` = `-IOR`, the CF's read strobe.
- `-P9SEL` OR `-IO-WR` = `-IOW`, the CF's write strobe.
The fourth gate is unused, its inputs tied to ground.

**U3, 74LS175: the register-select latch.** Four D flip-flops clocked on the rising edge of `LATCHCLK`, that is at the
end of an `OUT` to port 8, taking DATA0..3. Q1..Q3 drive the CF's register address DA0..2 directly, so the register
number is stable long before and long after every access to port 9. Q4 is the reset bit; its inverted output `-SRST`
goes to U4. The bus `-RESET` clears all four, so after a front-panel reset the card points at register 0 and is out of
reset.

**U4, 74LS08: enables and reset.** Three AND gates, each an active-low OR:
- `-IOR` AND `-IOW` = `-CFOE`: low during any access to port 9. It enables the buffer U5.
- `-RESET` AND `-SRST` = `-CFRESET`: the CF is reset while the bus reset is active or while software holds bit 3 of
  P8 at 1.
- `-CFOE` AND `-CFOE` = `ACTK`: a buffered copy that sinks the ACT LED, so the LED current does not load the enable.

**U5, 74LS245: the data buffer.** Its A side is the bus DATA0..7, its B side the CF's D0..7. `-OE` is `-CFOE`, so it
connects the two only during a port-9 access. `DIR` is `-IOR`: high (A to B, bus to CF) except during a read, when it
is low (B to A, CF to bus). So the card drives the data bus only while the CPU reads port 9, and never fights another
card.

**J1: the 40-pin IDE header**, for a commercial CF-to-IDE adapter, as on the P8X. The pin assignment is the P8X card's,
which works: data D0..7 on pins 17, 15, 13, 11, 9, 7, 5 and 3; DA0 35, DA1 33, DA2 36; `-IOW` 23, `-IOR` 25; reset
pin 1; grounds on 2, 19, 22, 24, 26, 30 and 40. D8..15 on the even pins 4..18 are left open: the card runs 8 bits wide.
The other pins:
- `-CS0` (37) is tied low and `-CS1` (38) high: see section 4 for why chip select is not gated.
- `CSEL` (28) grounded: the CF is the master drive.
- `IORDY` (27), `-PDIAG` (34) and `-DASP` (39) have 10k pull-ups; `-DASP` also lights the DASP LED, the CF's own
  activity signal.
- `-DMACK` (29) is held high through 10k: no DMA.
- `DMARQ` (21), `INTRQ` (31) and `-IOCS16` (32) are unused: the driver polls, and the card never asks for 16-bit
  transfers once in 8-bit mode.
- Pin 20 is the IDE key position. Some CF-to-IDE adapters take +5 V there; jumper JP1 connects it to VCC for those.
  Leave JP1 open otherwise: on a real IDE cable pin 20 is blocked or unconnected.

**RN1**, a 10k SIP network, pulls CF D0..7 up. Without a card in the adapter those lines would float; with the pull-ups
a status read returns $FF, which has the BSY bit set, so the ROM's bounded `cfwait` times out and reports `CF ERROR`
instead of acting on noise.

**J2: adapter power.** A 4-pin header in the floppy-power order: pin 1 +5 V, pins 2 and 3 ground, pin 4 (+12 V on a
floppy lead) unconnected. Most CF-to-IDE adapters take their power through a floppy connector. C6, 10 µF, sits beside
it: a CF card can draw about 100 mA in bursts. **To verify:** the power connector and pinout of the adapter Ken uses.

**LEDs.** PWR (green) on VCC; ACT (yellow) during every port-9 access, so a sector transfer shows as a flicker; DASP
(red), driven by the CF itself while it is busy. Each has a 1k resistor. Every IC has its own 100 nF capacitor.

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
  nanoseconds before and after every port-9 strobe.
- **Port-9 strobes** start at least two steps after the port select settles, so `-IOR`/`-IOW` begin with a single clean edge.
  A write ends one step before the port number changes, so the CF samples its data on a steady bus. For an `OUTA` the
  accumulator stays on the bus to the end of the instruction; for an `OUTI` the memory keeps driving the operand byte
  until after the strobe.
- **The latch clock** rises at the end of the port-8 write strobe while the port select is still steady, and U3
  samples DATA0..3 at that edge, while the bus still holds the byte.
- **The one simultaneous edge** is at the end of an `INP`: the port number and `-IO-RD` are both released by the same
  clock. `-IOR` is an OR of the two, so it simply goes high once, at whichever arrives first, with no glitch. The CPU
  has already taken the byte into the accumulator a step earlier (`-AC-LD`, step 9). This is why **chip select is not
  gated by the decoder**: if `-CS0` were the port-9 select, it would rise straight from the decoder while `-IOR` rises
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
cfwait:  P8 <- 7, then INP P9 until status BSY (bit 7) is clear (bounded: an absent card reads $FF and times out)
cfinit:  cfwait
         P8 <- 6, P9 <- $E0           drive/head: LBA mode, master, LBA bits 24..27 = 0
         P8 <- 1, P9 <- $01           features: 8-bit transfers
         P8 <- 7, P9 <- $EF           SET FEATURES
         cfwait; ACC = the ERR bit (0 = ok)
cfsetl:  P8 <- 3, 4, 5 with P9 <- CFLBA0, CFLBA1, CFLBA2 (the ROM variables at $0F10..$0F12)
         P8 <- 6, P9 <- $E0; P8 <- 2, P9 <- 1 (one sector)
cfread:  cfwait, cfsetl, P8 <- 7, P9 <- $20 READ SECTORS, wait for DRQ (bit 3)
         P8 <- 0, then 512 x INP P9   the sector, one byte per read, into the buffer at R7
cfwrite: the same with $30 WRITE SECTORS and 512 x OUTA P9
```

Status bits: 7 BSY, 6 DRDY, 3 DRQ, 0 ERR. The emulators model the card with these commands ($EF, $EC IDENTIFY, $20, $30)
behind a disk image (`-c disk.img`); an absent card reads $FF, as the real card's pull-ups make it.

**Bit 3 of P8** holds the CF in reset while 1. The ROM never sets it (it writes register numbers 0..7), and the
emulators ignore it. It is there so a later driver can recover a card that stops answering without a front-panel reset:
write 8 to P8, wait at least 25 µs, write 0, then run `cfinit` again. **To verify:** the reset pulse and recovery time
of the card used; 25 µs is the ATA minimum, CF cards may need up to about 2 ms before BSY clears.

`docs/system/OS-PLAN.md` first pencilled bit 3 as the selector for the ATA control block (the alternate status and
device control registers on `-CS1`). This design ties `-CS1` off instead: the driver polls the ordinary status
register, which gives the same bits, and the device-control soft reset is covered more simply by the hardware reset
bit.

## 6. Jumpers, connectors, LEDs

| Item | Setting | Purpose |
|---|---|---|
| JP1 | open (default) | fit only for a CF-to-IDE adapter powered on IDE pin 20 |
| J1 | 40-pin IDE header, pin 1 marked | the CF-to-IDE adapter, directly or on a short ribbon |
| J2 | +5 V, GND, GND, n/c | the adapter's power lead |
| LED1 PWR, LED2 ACT, LED3 DASP | | power; any port-9 access; the CF busy |

The card needs the I/O card strapped to ports 0..7 (its `IO-ADDR-HL` header), which is how it has always been used;
**To verify** on the bench before plugging the CF card in (`docs/cards/io.md`).

## 7. Bring-up and test

1. Without the CF adapter: power up, reset, and in the monitor type `O`. With nothing in J1 the pull-ups make status
   read $FF, so `cfinit` should time out and print `CF ERROR` after about a second. That proves the decode, the strobes
   and the buffer direction for reads, without any risk to a card.
2. With the bus tester or the monitor's `E` command, write to P8 and watch DA0..2 on J1 pins 35, 33, 36 with a meter or
   LEDs: each value 0..7 must appear, and bit 3 must pull J1 pin 1 low.
3. Fit the adapter with a card prepared on the Mac: `make -C os`, then `python3 tools/cfcard.py write os/disk.img --disk diskN`
   (`docs/procedures/CF-CARD.md`). Then `O` should boot Y1/OS.
4. `tests/os/*.session` then run on the machine by hand: `dir`, `cat README.TXT`, `hello`.

If it misbehaves: ACT not flickering during `O` means no port-9 strobes (U1/U2, the I/O card's strap); status always
$FF with a card fitted means the buffer is not enabled or points the wrong way (U4 gate 1, U5 DIR); reads right but
writes lost means `-IOW` or the data set-up (U2 gate 3); a card that works once and hangs after a reset suggests the
reset path (U3 Q4, U4 gate 2).

## 8. History and next revision

- 2026-09-22: the two-port design chosen over an eight-port memory-mapped one like the P8X's
  (`docs/system/OS-PLAN.md`); the emulator model and the ROM driver written against it.
- 2026-09-23: the circuit written as `hardware/cards/cf/kicad/v1.0/cf_netlist.py`; the KiCad schematic and board are
  generated from it (`hardware/cards/cf/README.md`). Not yet fabricated.

For a next revision: a second drive (the P8X card has two headers), `INTRQ` to the bus `-INT` if the OS ever wants
interrupt-driven transfers, and a CF socket on the card itself instead of the adapter (surface-mount on most
footprints, which the YACC1 has avoided so far).

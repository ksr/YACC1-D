# Sequencer memory card (V2.1) with the EEPROM adaptor and the Sequencer4 firmware — theory of operation

The control store of the YACC1: 256 opcodes x 64 steps x 8 bytes of microcode in eight 62256 SRAMs, copied at every
power-up from two I2C EEPROMs by an on-card ATmega328 that also receives new microcode over a serial port. It rides
piggyback on the sequencer-logic card and has no backplane connector of its own.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/sequencer-memory/eagle/v2.1/Sequencer-Memory-V2.1.sch` and `.brd` (parsed with Python's
`xml.etree`), `eagle/v2.1/bom/Sequencer-Memory-V2.1.csv`, `hardware/cards/sequencer-memory/README.md`, `eagle/v2.1/Notes.md`,
`accessories/eeprom-adaptor/eeprom adaptor.sch` and its README, `hardware/FABRICATED.md`, `hardware/PROVENANCE.md`,
`hardware/DESIGN-REVIEW.md`, `hardware/DESIGN-REVIEW-NOTES-control-io.md` (section 2), `embedded/sequencer-card/README.md`,
`embedded/sequencer-card/sequencer4/{Sequencer4.ino,download.ino,uCodeRAM.ino,uCodeROM.ino,IO.ino}`,
`embedded/sequencer-card/readback/README.md`, `tools/ucode_send.py`, `tests/sequencer/{run.py,mock_card.py,*.log}`,
`firmware/microcode/README.md`, `firmware/microcode/yaccsignaldata2.h`, `firmware/microcode/ucode-generator2/controlLine.c`,
`docs/system/MACHINE.md`, `BACKLOG.md`, `docs/history/status-2021.md`, `media/sequencer memory v2.1 top.jpeg`,
`media/sequencer top.jpeg`.

---

## 1. Purpose and place in the machine

A microcode step is one 8-byte word; a record (one opcode) is 64 words = 512 bytes; the whole store is 256 x 512 =
131,072 bytes = 1 Mbit. The store must be **random-access at bus speed** (the logic card presents a 14-bit address
`CADDR0..13` = opcode:step and wants the word within one clock period) and **non-volatile**. The card meets both with two
memories and a small computer between them:

- eight 32K x 8 SRAMs (IC1..IC8, 62256) in parallel make a 32K x 64 store, addressed by `CADDR0..14` and read by the
  logic card while it runs (A14 selects one of two 16K halves, of which the machine uses one);
- two I2C EEPROMs (on the adaptor plugged into IC9's socket, 2 x 64 KB) hold the image;
- an ATmega328P (IC15, Arduino bootloader) with five MCP23017 I2C port expanders (IC10..IC14) — 80 GPIO lines — owns
  the SRAM's address and data pins at boot, copies the EEPROM into the SRAM, verifies the copy, then turns all 80 lines
  into inputs, ties the SRAM to "selected, output enabled", and raises `READY`. The logic card turns `READY` into `-BUS-EN`.

In DOWNLOAD mode the same ATmega receives a new image over its FTDI serial header and writes it into the EEPROMs.

```
                FTDI (115200) ----> IC15 ATmega328P ----I2C (SDA/SCL, 400 kHz)----+---- IC9 socket: EEPROM adaptor
                DTR ---(DTR-RESET, C19)---> /RESET                                |      IC1 24LC512 @0x57 (ins 128..255)
                UCODE switch (PC0), START (PC2)                                    |      IC2 24LC512 @0x56 (ins 0..127)
                LEDs FAULT (PB3) READY (PB4) LOADING (PB5)                         |
                PB0 -CMEMWR, PB1 -CMEMRD, PB2 -CMEMSEL ---------------------+       +---- IC10 MCP23017 @0x20: CADDR0..13
                PD7 BUS-READY ----> SV1 pin 12 ----> logic card -BUS-EN     |       +---- IC14 @0x21: bytes 0,1  (RAM IC4, IC3)
                                                                            |       +---- IC13 @0x22: bytes 2,3  (RAM IC2, IC1)
   logic card SV1: CADDR0..13 ======> A0..A13 of IC1..IC8 (A14 = jumper)     |       +---- IC11 @0x23: bytes 4,5  (RAM IC8, IC7)
   logic card SV1/SV2/JP1 <====== I/O0..7 of IC1..IC8 = the 64 control bits  |       +---- IC12 @0x24: bytes 6,7  (RAM IC6, IC5)
                                     -CS / -OE / -WE  <---------------------+
```

Fabricated 2020-12-01 (V2.1, `hardware/FABRICATED.md`), in the machine with the adaptor fitted in IC9 (Ken 2026-09-20,
`docs/system/MACHINE.md`). The photo `media/sequencer memory v2.1 top.jpeg` shows Alliance AS6C62256-55PCN SRAMs,
MCP23017-E/SP expanders, an Atmel ATmega328P-PU, and two Microchip 24LC512 on the orange adaptor board.

## 2. Signals

The card has no DIN 41612 connector; everything goes through SV1/SV2 (2 x 40 pins) and JP1 (2 x 2) to the logic card,
where the names get a `U` prefix. Direction is seen from this card.

| Header pins | Signal | Dir | What it is |
|---|---|---|---|
| SV1 14,16,...,38 (even), SV1 2 | CADDR0..12, CADDR13 | in (run) / out (load) | the microcode address from the logic card's step counter (0..5) and instruction register (6..13); in load mode the same lines are driven by IC10 |
| SV1/SV2, 60 pins | the 64 control bits minus SPARE3/SRC-ADDR/DEST-ADDR (see JP1) | out | the RAM data pins, read by the logic card's pipeline registers; in load mode they are driven by IC11..IC14 |
| JP1 1, 3, 4 | SPARE3, SRC-ADDR, DEST-ADDR | out | three control bits that travel over the 2x2 header instead of SV1/SV2 (RAM IC5 I/O5, IC6 I/O6, IC5 I/O0) |
| JP1 2 | -MEM-CPU-RESET | in | the ATmega's /RESET and all five MCP23017 /RESET (R4 10k pull-up, LOCAL-CPU-RESET button, C19 from the DTR jumper); the logic card's JP2 can drive it from SPARE3 (must stay open — `docs/cards/sequencer-logic.md` 3.2) |
| SV1 12 | BUS-READY (READY on the logic card) | out | ATmega PD7 ("READYLINE", Arduino pin 7): low from reset until the copy is verified, then high; the logic card's IC36D inverts it into bus `-BUS-EN` |
| SV1 39, 40; SV2 1, 2 | GND; VCC | in | power comes from the logic card through the headers (no other supply pin) |

Byte-to-chip map (`yaccsignaldata2.h` gives each signal as (chip, port, bit); the generator writes byte index
(chip-1)*2+port, `controlLine.c`; the firmware's `writeGPIOAB` puts byte 2n on GPA and 2n+1 on GPB of data chip n+1):

| Byte | Signals (bit 0 first) | RAM | MCP23017 (I2C address) port |
|---|---|---|---|
| 0 | -REG-FUNC-RD, -REG-FUNC-LD, REG-RD-ID0..3, REG-LD-ID0..1 | IC4 | IC14 (0x21) GPA |
| 1 | REG-LD-ID2..3, -REG-RD-LO, REG-LD-LO, -REG-RD-HI, REG-LD-HI, -REG-DN, -REG-UP | IC3 | IC14 GPB |
| 2 | -MEM-RD, -MEM-WR, -IO-RD, -IO-WR, -TMP-REG-RD0, -TMP-REG-LD0, -TMP-REG-RD1, -TMP-REG-LD1 | IC2 | IC13 (0x22) GPA |
| 3 | ADDR-REG-ID0..3, IOADDR0..3 | IC1 | IC13 GPB |
| 4 | -IO-ADDR-LD, -VMA, -ALU-FUNC, ALU0..3, -AC-LD-INV | IC8 | IC11 (0x23) GPA |
| 5 | -AC-RD, -AC-LD, -SR-LD, BR-TEST, -HL-SWAP, SOFT-HALT, OUT-OFF, OUT-ON | IC7 | IC11 GPB |
| 6 | -INTA, -SRC-ADDR, INT-LD-HI, INT-START, INT-EN, LD-INS-REG, UCODE-COUNT-RESET, OPERAND-CLK | IC6 | IC12 (0x24) GPA |
| 7 | -BRANCH-RD, BRANCH-LD-LO, SPARE3, BRANCH-LD-HI, -INT-JMP, INT-LD-LO, -2-BYTE-OPERAND-SEL, -DEST-ADDR | IC5 | IC12 GPB |

On RAM IC1..IC4 the table's bit n is on I/On; on IC5..IC8 the schematic wires the nets in reverse pin order (IC8 I/O0 =
-AC-LD-INV, I/O7 = -IO-ADDR-LD). It does not matter: the same MCP23017 pin writes and the same SV pin reads a given net, and
the SRAM does not care which of its eight data pins stores which bit. The 2026-09-21 review verified all 64 (signal ->
RAM pin -> SV pin -> logic-card D input) mappings (`DESIGN-REVIEW-NOTES-control-io.md`, "checked, no issue").

`REG-LD-LO`, `REG-LD-HI`, `BRANCH-RD` and `-SRC-ADDR`/`-DEST-ADDR` are stored with the polarity the table says (the
comments in `yaccsignaldata2.h`: "this active low on the bus"): the logic card inverts or gates them on its side.

## 3. Schematic walkthrough

Four sheets: 1 = the SRAM array, 2 = SV1/SV2/JP1, 3 = the ATmega, EEPROM, switches and LEDs, 4 = the five expanders.

### 3.1 Sheet 1 — the SRAM array (IC1..IC8)

Eight 62256P (Eagle `memory-hitachi`; fitted AS6C62256-55PCN, 55 ns) with all address pins paralleled: `A0..A13` =
`CADDR0..13` from SV1, `A14` = `CADDR14` from the on-card header (3.4). All three control pins are common and come
straight from the ATmega: `!CS` = `-CMEMSEL` (PB2), `!OE` = `-CMEMRD` (PB1), `!WE` = `-CMEMWR` (PB0). There are no
pull-ups on these three lines, so while the ATmega is in reset or in its bootloader (the ~1 s after power-up, or whenever
`-MEM-CPU-RESET` is low) the SRAMs see undefined `-CS/-OE/-WE` — harmless, because the copy that follows rewrites
everything, but it is why nothing on the bus should depend on the store before READY (`DESIGN-REVIEW-NOTES-control-io.md` 2.1).
The data pins are the 64 control nets of section 2. 62256 timing: with `-CS` and `-OE` low the outputs follow the address
after tAA (55 ns for the fitted part); the logic card gives them one clock period.

### 3.2 Sheet 4 — the port expanders (IC10..IC14)

Five MCP23017SP on the I2C bus (SDA/SCL with R2/R3 = 2.2k to VCC), `!RESET` = `-MEM-CPU-RESET`, addresses set on A0..A2:

| IC | A2 A1 A0 | Address | GPA | GPB |
|---|---|---|---|---|
| IC10 | 0 0 0 | 0x20 | CADDR0..7 | CADDR8..13 (GPB6/7 unused) |
| IC14 | 0 0 1 | 0x21 | byte 0 | byte 1 |
| IC13 | 0 1 0 | 0x22 | byte 2 | byte 3 |
| IC11 | 0 1 1 | 0x23 | byte 4 | byte 5 |
| IC12 | 1 0 0 | 0x24 | byte 6 | byte 7 |

The firmware's `mcp[i].begin(i)` (i = 0..4) matches this exactly (`Sequencer4.ino setup()`; `ADDRESS_CHIP 0`,
`DATA_CHIP_START 1`). No expander pin touches `CADDR14`: load and run address the same 16K half (3.4).

In load mode the expanders drive: `setAddressOutput()` / `setDataOutput()` make every pin an output (`IO.ino`); in run
mode `setAddressInput()` / `setDataInput()` make them inputs with the 100k internal pull-ups on — the review notes this is a
negligible load on the SRAM outputs and on the logic card's CADDR drivers. The MCP23017 outputs and the logic card's
IC15/IC35 (74*244 on CADDR, enabled by `-BUS-EN`) are on the same nets: the design relies on `-BUS-EN` being high (READY low)
while the ATmega drives the address. That is exactly what breaks when the bus tester asserts `-BUS-EN` from outside (6).

### 3.3 Sheet 3 — the ATmega328P, EEPROM socket, switches and LEDs

IC15 ATMEGA328P_PDIP, 16 MHz crystal Q1 with C16/C18 = 20 pF, AREF decoupled by C15, `AVCC` = VCC. Pin use (Arduino
numbering as in the sketch):

| ATmega pin | Arduino | Net | Use |
|---|---|---|---|
| PB0 | 8 | -CMEMWR | SRAM `-WE`, pulsed low/high by `uCodeRamWritePulse()` |
| PB1 | 9 | -CMEMRD | SRAM `-OE` (`uCodeRamRead(true)` = low) |
| PB2 | 10 | -CMEMSEL | SRAM `-CS` (`uCodeRamSelect(true)` = low) |
| PB3 | 11 | FAULT | red LED through R7 (330); blink codes (5) |
| PB4 | 12 | LED-READY | green LED through R8 |
| PB5 | 13 | LD | yellow LOADING LED through R9 |
| PD7 | 7 | BUS-READY | SV1 pin 12 -> logic card READY -> `-BUS-EN` |
| PC0 (ADC0) | A0 | N$30 | UCODE toggle: `O` = VCC (WRITEMEM = 1), `S` = GND (DOWNLOAD = 0), `P` common to PC0 |
| PC2 (ADC2) | A2 | N$39 | START push button to GND, R1 10k pull-up |
| PC4 / PC5 | A4 / A5 | SDA / SCL | I2C to the expanders and the EEPROM(s) |
| PC6 | /RESET | -MEM-CPU-RESET | R4 10k to VCC; LOCAL-CPU-RESET button to GND; C19 (100 nF) from the DTR-RESET jumper; JP1 pin 2; all MCP23017 /RESET |
| PD0 / PD1 | RX / TX | ARD-RXIN / ARD-TXOUT | JP3 FTDI header RXI / TXO |

JP3 is the 6-pin FTDI header (SparkFun `FTDI_DEVICE`: GND, CTS = GND, VCC = N$34, TXO, RXI, DTR = N$33). Two solder/pin
jumpers hang off it:

- **DTR-RESET**: pin 1 = N$33 (FTDI DTR), pin 2 = N$8 = C19 -> `-MEM-CPU-RESET`. Closed, this is the ordinary Arduino
  auto-reset: opening the serial port pulls DTR low and the 100 nF edge resets the ATmega into its bootloader. The
  schematic, the `.brd` (signals `N$8` = C19.1 + DTR-RESET.2; `-MEM-CPU-RESET` includes C19.2) and the KiCad netlist all
  show C19 in circuit; `DESIGN-REVIEW-NOTES-control-io.md` 2.2 ("nothing reaches /RESET and there is no series 100 nF")
  is contradicted by all three and by use: `tools/ucode_send.py` and `embedded/sequencer-card/readback/README.md` both rely
  on the DTR reset (run the sender first, then press START; avrdude through the bootloader). The photo shows a blue cap
  on the DTR-RESET header. **To verify:** whether the review looked at an older netlist; the design as in the tree is fine.
- **FTDI-VCC**: pin 1 = VCC, pin 2 = N$34 (the FTDI's 5 V). Closed, it would parallel the USB 5 V with the backplane rail
  through the logic card — leave it open when the card is in the machine (photo: open).

**IC9** is the 8-pin socket for a 24*P I2C EEPROM with A0 = A1 = A2 = VCC (device address 7 = 0x57) and `WP` = N$32 =
JP2 pin 2 (JP2: 1 = GND, 2 = WP, 3 = VCC — a jumper on 1–2 allows writes, on 2–3 protects). The BOM lists a 24AA01P
(128 bytes: a placeholder value); the machine has the **EEPROM adaptor** in this socket (3.5). UCODE is a 9070-1W toggle,
START a tactile switch, LOCAL-CPU-RESET a 6.2 mm push button. The PWR LED is on R6 (330).

### 3.4 CADDR14 header

`CADDR14` (SRAM A14) has R5 (10k) to VCC and a 2-pin header to GND. Jumper off: A14 = 1, the upper 16K x 64 half;
jumper on: A14 = 0, the lower half. Since neither the logic card nor the expanders drive A14, the half used for loading
is the half used for running — the other half is spare storage (a second microcode image, if a switch replaced the
jumper). The photo shows a cap on the header (lower half selected). **To verify:** on the card in hand.

### 3.5 The EEPROM adaptor (`accessories/eeprom-adaptor/`)

A 29 x 16 mm board with two AT24C*P footprints sharing SDA, SCL, VCC, GND and WP with the 8-pin plug that goes into IC9's
socket: IC1 with A0 = A1 = A2 = VCC (address 7, 0x57) and IC2 with A0 = GND, A1 = A2 = VCC (address 6, 0x56). It exists
because the microcode needs 128 KB and the largest 8-pin 24Cxx is 64 KB (24LC512): two of them, selected by the low
address bit of the device address, give one 128 KB store. Designed 2020-12-19/21, one OSH Park order (rmD8XYsD, 2024-06-19,
three boards), fitted (Ken 2026-09-20). The photo shows two 24LC512 (one E/P, one I/P) on it. The mechanical design review
flags the adaptor's VCC/GND as "no source" — expected, the socket pins are its supply (`hardware/DESIGN-REVIEW.md`); it has
no decoupling of its own (the card's C1..C14 are nearby). `docs/datasheets/24lc512.pdf` is the part's datasheet.

The firmware's view (`uCodeROM.ino`): `EEPROM_DEV_LO 0x56` holds instructions 0..127 (byte address = instruction x 512 +
offset, 0..65535), `EEPROM_DEV_HI 0x57` holds 128..255 (the same 16-bit address after subtracting 65536); an instruction
never straddles a device. `EEPROM_PAGE 128` is the 24LC512's page size. **To verify:** part numbers on the adaptor in the
machine (the photo shows 24LC512; the firmware comment also allows 24LC1025).

### 3.6 Sheet 2 — SV1, SV2, JP1

The two 2x20 headers and the 2x2 header carry the nets listed in section 2, in the same positions as on the logic card
(checked pin by pin in the 2026-09-21 review). `SV1` pins 39/40 and `SV2` 1/2 are the card's only GND and VCC.

## 4. The Sequencer4 firmware (`embedded/sequencer-card/sequencer4/`)

Flashed 2026-09-21 (Arduino Uno target, ATmega328P through the FTDI at 115200); the previous Sequencer3 build that was in
the chip was read out first (`readback/sequencer-flash-2026-09-21.hex`, with the avrdude commands to restore it). Sequencer4
is Sequencer3 with: I2C at 400 kHz (set **after** the expanders' `begin()`, which resets the clock to 100 kHz), EEPROM reads
in 32-byte blocks and writes in page writes, the boot-time test-pattern fill removed, the whole copy read back and compared
before READY, and every string in flash (`F()`) because the plain-string build crashed with ~500 bytes of RAM left. Measured:
copy 16 s, verify 29 s, READY 54 s after reset (Sequencer3: 156 s, unverified).

### 4.1 Modes

`setup()` reads `UCODESWITCH` (A0) once: `WRITEMEM` (1, switch to VCC) or `DOWNLOAD` (0, switch to GND). Then it starts
the five expanders, sets the I2C clock, makes the LED and RAM-control pins outputs with `-CMEMRD/-CMEMWR/-CMEMSEL` high and
`READYLINE` low, and flashes FAULT, READY, LOADING once each (100 ms). In WRITEMEM mode it also prints the banner
`Sequencer4 2026-09-21 (400 kHz I2C, block EEPROM reads, verified copy)`; in DOWNLOAD mode it stays silent so that nothing
but the prompt reaches the sender.

**WRITEMEM (run) mode**, `loop()`:

1. `EEPROM to RAM`: LOADING on; address and data expanders as outputs; for each instruction 0..255 (`WORKING_INSTRUCTION_SET`)
   `readCodeFromROM()` (512 bytes, 16 I2C transactions of 32 bytes using the EEPROM's address auto-increment) then
   `writeInstruction()` (`-CS` low; for each of the 64 lines: `writeAddress(instruction*64 + line)`, `writeData()` = one
   `writeGPIOAB` per data chip, then `-WE` pulsed low/high; `-CS` high). Progress every 32 instructions; LOADING toggles per
   instruction; "- done, 16 s".
2. `Verify RAM against EEPROM` (`VERIFY_COPY`): data expanders as inputs, `-OE` and `-CS` low; for each instruction
   `readInstruction()` (address out, read GPA/GPB of the four data chips per line) and compare with the EEPROM 32 bytes at a
   time (`readCodeFromROMPart()`, because only ~500 bytes of stack are free). On a mismatch it prints the counts and the
   first bad instruction, the hint `is -BUS-EN inactive? (the logic card drives the microcode address lines when it is
   asserted)`, deselects the RAM, and calls `doError("RAM verify failed", 6)`: FAULT blinks 6 forever, READY never rises.
3. `DISPLAY_MEM`: dumps instructions 0, 1, 7, 124 and 255 (RAM then EEPROM, 64 lines of 8 hex bytes each) — the transcript
   that `tools/ucode_send.py --boot-check` compares with `test.hex`.
4. Hand-over: address and data expanders to inputs, `-OE` low, `-CS` low (the SRAM now answers the logic card), LOADING off,
   READY LED on, `READYLINE` high, `RAM copy complete and verified, READY!!!`.
5. Monitor loop forever: once a second read the address the logic card presents (`readAddress()` on IC10), and when
   instruction or line changed, print `RAW=.. Addr=.. Seq=.. Ins=.. Line=.. Data= ..` and the list of control bits that
   changed since the last print (`sig=[n]=v`, n = byte*8+bit). With the CPU single-stepped this is a live microcode monitor.

**DOWNLOAD mode**, `loop()`: LOADING on; wait for START to be pressed; then `while (waitInstructionBegin()) downloadInstruction();`
toggling LOADING per instruction; LOADING off; idle forever (a reset with the switch back in WRITEMEM starts the copy).

### 4.2 The serial download protocol (`download.ino`, the `OLD` section is the compiled one)

```
card -> host   ">>\r\n"                                a prompt before every instruction
card           flashLed(READY): READY LED on for 100 ms — the card is NOT reading during this time
host -> card   "%" cc ii d0 d1 ... d511                 '%' start, cc = 2-hex checksum (read and ignored),
                                                        ii = 2-hex instruction number, then 512 bytes as 2 hex digits each
               'Z' in place of a byte = "the rest of this instruction is zero" (getCode fills with 0)
host -> card   "!" after a prompt                       end of download; anything else at a prompt = doError("Unexpected Char", 5)
```

`readHexNumber()` waits for two characters (`delay(1)` polling, `Serial.available()`), upper-case hex only
(`converCharToInt`: '0'..'9', 'A'..'F'). The 64-byte hardware serial buffer of the ATmega and the 100 ms LED flash after
the prompt are the two constraints on the host: whatever is sent during the flash lands in the 64-byte buffer, and a
record is 1029 characters, so a sender that fires the record as soon as it sees `>>` at full speed loses its head and
the card then waits forever for the missing bytes (observed 2026-09-22 at 1 ms/char). `tools/ucode_send.py` therefore
waits `--settle` 250 ms after every prompt and paces characters at `--delay` 2 ms (the Processing sender used 25 ms/char,
which hid the problem). The trailing `-` of each `test.hex` record is **not** sent (the card reads exactly 512 values; a
stray `-` would be an Unexpected Char, FAULT blinking 5).

`test.hex` format (`firmware/microcode/README.md`, `ucode_send.py load_records()`): 256 lines `%ccii<1024 hex digits>-`
in instruction order, then a line `!`. `test.hexz` is byte-identical (the Processing sender's file name); `cache` is what
was last sent — the loader sends only records that differ from it and rewrites it as it goes, so an interrupted load
resumes; `--all` sends everything (what Ken chose for the 2026-09-22 reload: "six records differed, all 256 sent").

Host-side sequence (`ucode_send.py` docstring): UCODE to DOWNLOAD, reset the card (LOADING comes on), start the sender
(opening the port resets the ATmega through DTR — hence sender first), press START, wait; then UCODE back to WRITEMEM,
reset, and `ucode_send.py --boot-check` captures the run-mode boot and compares its five dumps with `test.hex`.
`tests/sequencer/run.py` exercises the sender against `mock_card.py` (a fake card on a pty: differential send, `--all`, and
the dump comparison on the 2026-09-21 transcript, where only the pre-fix PUSHR record $07 may differ).

### 4.3 EEPROM access (`uCodeROM.ino`) and the write path

`writeCodeToROM(instruction, data[512])`: page writes of `WRITE_CHUNK` = 30 bytes (the AVR Wire buffer of 32 minus the two
address bytes), never crossing a 128-byte page (`room = EEPROM_PAGE - ((addr + done) % EEPROM_PAGE)`), `delay(5)` per
transaction for the EEPROM's write cycle. Records start page-aligned (512 = 4 x 128). Sequencer3 wrote one byte per
transaction with a 5 ms wait each — 512 x 5 ms = 2.6 s per instruction, which is where its 156 s came from.
`i2c_eeprom_read_byte()` is kept for anything that still wants single-byte access.

### 4.4 LEDs and blink codes

| LED | Pin | Meaning |
|---|---|---|
| LOADING (yellow) | PB5 | on while waiting for START in DOWNLOAD mode; toggles per instruction during a download or a copy |
| READY (green) | PB4 | 100 ms flash after every `>>` prompt (download); steady on after the verified copy (run) |
| FAULT (red) | PB3 | `doError(msg, code)`: blinks `code` times, 2 s pause, forever (the message print is commented out). Codes: 3 = data written with the data expanders set to input, 4 = address written with the address expanders set to input, 5 = unexpected character at a prompt, 6 = RAM verify failed |
| PWR | – | 5 V present |
| all three | – | one 100 ms flash each at every reset (`setup()`) |

### 4.5 READYLINE and -BUS-EN

`READYLINE` (PD7) is low from reset until step 4 of the run-mode boot. On the logic card `-BUS-EN` = NOT READY
(IC36D), and `-BUS-EN` is the output enable of its pipeline registers and of its CADDR buffers, and goes to the backplane
(C28) where every other card gates its bus drivers with it. So for ~54 s after power-up the whole machine is tri-stated
except the 17 logic-card lines that ignore `-BUS-EN` (`docs/cards/sequencer-logic.md` section 4) — and the CADDR lines
belong to this card's IC10.

The interaction that bit on 2026-09-21 (`tests/sequencer/boot-run-mode-2026-09-21.log` versus `-bus-quiet.log`,
`embedded/sequencer-card/README.md`): the bus tester was still asserting `-BUS-EN` from the backplane while the card
copied. That enabled the logic card's IC15/IC35 onto `CADDR0..13` against IC10's outputs; the address the SRAM saw was
0 (or whatever the fight resolved to), every write went to address 0, and the dumps came back all zero (`Data= 00: 00: ...`
in the first log's monitor line, versus `03 d4 ff 00 85 57 03 d1` — instruction 0 step 0 — with the bus quiet). Sequencer4's
verify pass now catches this (FAULT x 6, the `-BUS-EN` hint) instead of raising READY over a corrupt store. Rule: nothing
may drive `-BUS-EN` low while LOADING is on.

The run-mode boot on the Sequencer4 firmware (`boot-run-mode-2026-09-21-sequencer4.log`, and the identical
`boot-run-mode-2026-09-22-reload.log` after the H-1/H-2/BRUR reload): `Copying Instruction 0 ... 224`, `- done, 16 s`,
`- 29 s, RAM == EEPROM for all 256 instructions`, the five dumps, `READY!!!`, then the monitor line for the address the
logic card is presenting.

## 5. Jumpers, switches, LEDs, connectors — settings in the machine

| Item | Function | Setting |
|---|---|---|
| UCODE toggle (silk DOWNLOAD / WRITE MEM) | PC0: mode read once at reset | WRITE MEM to run the machine; DOWNLOAD only to load microcode |
| START button | PC2: starts the download after the prompt is awaited | – |
| LOCAL-CPU-RESET button | pulls -MEM-CPU-RESET (ATmega + expanders) low | use it to restart the copy (or to reflash if DTR fails) |
| DTR-RESET (2 pins) | FTDI DTR -> C19 -> reset | closed (photo: blue cap) so the sender and avrdude can reset the card |
| FTDI-VCC (2 pins) | FTDI 5 V -> card VCC | open in the machine (photo) |
| CADDR14 (2 pins) | SRAM A14 to GND (on) or 10k to VCC (off) | on (photo) = lower 16K half; **To verify** |
| JP2 (3 pins) | EEPROM WP: 1–2 = writable, 2–3 = protected | must be 1–2 for a download; **To verify** on the card |
| JP1 (2x2) | SPARE3, -MEM-CPU-RESET, SRC-ADDR, DEST-ADDR to the logic card | mated with the logic card's JP1 |
| SV1, SV2 | the store's address/data to the logic card | mated |
| JP3 (FTDI, 6 pins, silk BLK ... GRN) | GND CTS VCC RXI TXO DTR | the FTDI cable, black to BLK; port `/dev/cu.usbserial-AB6WZCQX` in `readback/README.md` |
| IC9 socket | I2C EEPROM | the adaptor with two 24LC512 |
| LEDs | PWR, LOADING, READY, FAULT | 4.4 |

## 6. Bring-up and test

**How the card was proven.**

- 2020-12: `embedded/sequencer-card/deprecated/test-eeprom-2020-12` tested the on-card I2C EEPROM at 0x57 through the ATmega;
  `sequencer2` / `sequencer3` loaded the machine's microcode from 2020-12 and 2021-08 on.
- 2026-09-21: the ATmega's flash was read out and identified as a Sequencer3 build (`readback/`); a tree build of sequencer3
  was flashed and read back byte-identical, then Sequencer4. Run-mode boot captured three times that day (`tests/sequencer/`):
  the clobbered copy with the tester asserting `-BUS-EN` (all zeros), the clean copy with the bus quiet (RAM == EEPROM ==
  `test.hex` for every dumped instruction), and the Sequencer4 boot with its 256-instruction verify. **EEPROM contents
  verified** = the tree's `test.hex` of that day.
- 2026-09-22: `tools/ucode_send.py --all` loaded the regenerated image (BRUR at $AD, the H-1 and H-2 fixes); the boot after
  it verified (`boot-run-mode-2026-09-22-reload.log`); `cache` == `test.hex`.
- 2026-09-22/23: the CPU ran `tests/assembler/romcount` overnight from the ROM on that store.
- `tests/sequencer/run.py` (no hardware) checks the sender's differential logic, `--all`, and the dump comparison.

**If it misbehaves — what to look at.**

1. No banner on the FTDI at reset in WRITE MEM: baud 115200; the UCODE switch position (DOWNLOAD mode is silent by design);
   DTR-RESET closed (or press LOCAL-CPU-RESET after opening the port).
2. `Copying Instruction` stalls or the boot takes minutes: I2C — the expanders' `begin()` resetting the clock is handled,
   but a missing 2.2k pull-up or an adaptor EEPROM that does not ACK makes `Wire.requestFrom` return short reads (the code
   fills with 0xFF, which then fails the verify). `readback/` says the chip "may report not in sync" on flashing — retry
   with the reset button.
3. `MISMATCH ... first at instruction N` with FAULT x 6: first suspect `-BUS-EN` driven by something on the bus (the bus
   tester's firmware drives it push-pull from `setup()`); with the bus quiet, suspect the SRAM control lines (`-CMEMSEL`
   on IC15 pin 16 low during the copy) or a bad SRAM (the first bad instruction tells which 16K address region).
4. READY on but the CPU does nothing: the logic card's `-BUS-EN` (C28) should be low; the monitor loop's `RAW=` line shows
   whether the logic card is presenting an address at all and whether the data on the RAM pins is the record you expect
   (compare with `test.hex` line `%..ii`, byte offset step*8).
5. Download fails with FAULT x 5: a stray character before `%` (the record's trailing `-`, or a sender that did not wait
   for the prompt); FAULT x 6 after a download is a verify failure of the *copy*, not of the EEPROM write — the EEPROM
   image itself can be read with `dumpram` (`embedded/sequencer-card/dumpram/`).
6. A record loads but the machine misbehaves on one opcode: `ucode_send.py --boot-check` compares the five dumped
   instructions; for another opcode, edit the `dumpInstruction()` list in `Sequencer4.ino` (it is one line per instruction)
   or read the RAM with `dumpram`.

## 7. Revision history and what the next revision should change

| Revision | Date | What | Source |
|---|---|---|---|
| gen-1 SEQUENCER-MEMORY-Prod-V1.0 | 2016 | the 2016 store (32-step format, v1 generator, 19200-baud senders) | `archive/gen1-2015-2018/`, `embedded/sequencer-card/deprecated/sequencer1` |
| V2.0 | 2020-07-25 | the 2020 redesign for 64 steps x 8 bytes; "Move CPU reset to top edge of board" done; fabricated, retired 2021-01 | `docs/history/general-notes/NOTES-Update from old project.md`, `eagle/deprecated/v2.0/` |
| V2.1 | 2020-12-01 | reworked the ATmega section and jumpers (README); `Notes.md` carries no change list | `hardware/FABRICATED.md`; **in the machine** |
| EEPROM adaptor | design 2020-12-19/21, ordered 2024-06-19 | two 24LC512 in the IC9 socket = 128 KB (the 2021 status note's "Add second 512k EEPROM") | `accessories/eeprom-adaptor/`, `docs/history/status-2021.md` |
| firmware Sequencer3 -> Sequencer4 | 2021-08 -> 2026-09-21 | verified copy, 3x faster boot | `embedded/sequencer-card/README.md` |

**A V2.2 should** (from `BACKLOG.md`, the reviews and the 2026-09 sessions):

1. Put the second EEPROM on the card (the adaptor's two footprints, or one 24LC1025 with its A2-tied-high convention) and
   fit the decoupling the adaptor lacks; keep JP2 (WP) but label it.
2. Pull-ups on `-CMEMSEL/-CMEMRD/-CMEMWR` so the SRAM idles deselected while the ATmega is in reset or in its bootloader
   (review 2.1), and a pull-down on `BUS-READY` so `-BUS-EN` is not asserted by a floating PD7 in that window.
3. Give the ATmega a way to see `-BUS-EN` (one spare port pin to SV1 or JP1) so the loader can refuse to copy while
   something else owns the bus, instead of finding out at the verify.
4. Bring `CADDR14` to a switch (two selectable microcode images) or drive it from the ATmega.
5. Correct the BOM (IC9 = 24LC512 x 2 on the adaptor, not 24AA01P) and record that DTR-RESET is a pin header, not the
   solder jumper the library symbol implies.
6. Keep the 40-pin headers and JP1 as they are — the logic card depends on them pin for pin.

Related documents: `docs/cards/sequencer-logic.md` (what happens to the 64 bits), `docs/system/MICROCODE.md` (the
control-store format and the generator, when written), `firmware/microcode/README.md` (images, cache, regeneration),
`embedded/sequencer-card/README.md` (firmware history).

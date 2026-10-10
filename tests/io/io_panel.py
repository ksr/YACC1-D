#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""The I/O card's front panel through the Bus Test Card, one step per run, for someone watching the card (2026-10-10).

  io_panel.py leds [HEX]     LEDs 0..7 lit one at a time (0.5 s each), then all, then none, then HEX (default A5)
  io_panel.py til [HEX]      both TIL311s count 00, 11, 22 .. FF (0.6 s each), then show HEX (default 5A)
  io_panel.py out on|off     the OUT LED (the bus line OUT, which the sequencer's ON/OFF instructions drive)
  io_panel.py lcd [TEXT1 [TEXT2]]   HD44780 set up (8-bit, 2 lines), cleared, the two lines written
  io_panel.py switches       reads S0..S7 and shows the value on the LEDs and the TIL311s
  io_panel.py in             reads the IN switch through the ALU card's condition mux (BR-COND, ALU = 5)
The tester is reset each time its port opens; the I/O card's latches (LEDs, TIL311, control) are not (no -RESET is
sent), so what a step leaves on the panel stays. OUT is driven by the tester itself and holds until the next open.
Ports as on the machine: P0 the control latch, P1 the device it selects (docs/cards/io.md 3.3).
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT

SWITCHLED, LCDENABLE, LCDREGISTER, TIL = 0x01, 0x02, 0x04, 0x80
if len(sys.argv) < 2:
    sys.exit(__doc__)
step, rest = sys.argv[1], sys.argv[2:]
bd = BusDriver(PORT); bd.wait_prompt(timeout=20)
c = bd.cmd
for s in ("-IO-RD", "-IO-WR", "-ALU-FUNC", "-AC-RD", "-AC-LD", "-MEM-RD", "-MEM-WR", "-VMA", "-REG-FUNC-RD",
          "-REG-FUNC-LD", "-TMP-REG-RD0", "-TMP-REG-RD1"):
    c(s, 0)
c("-BUS-EN", 1); bd.no_registers()

def ioaddr(p):
    for i in range(4): c("IOADDR%d" % i, (p >> i) & 1)

def out(p, v):
    ioaddr(p); c("DATABUS-WR-MODE", 1); c("WR-DATABUS", v & 0xFF); c("-IO-WR", 1); c("-IO-WR", 0)

def inp(p, precharge=0x00):
    ioaddr(p); c("DATABUS-WR-MODE", 1); c("WR-DATABUS", precharge)
    c("DATABUS-RD-MODE", 1); c("-IO-RD", 1); v = int(c("RD-DATABUS-L")); c("-IO-RD", 0)
    return v

def leds(v): out(0, SWITCHLED); out(1, v)
def til(v): out(0, TIL); out(1, v)

if step == "leds":
    final = int(rest[0], 16) if rest else 0xA5
    out(0, SWITCHLED)
    for i in range(8):
        out(1, 1 << i); print("LED %d" % i, flush=True); time.sleep(0.5)
    out(1, 0xFF); print("all on", flush=True); time.sleep(1)
    out(1, 0x00); print("all off", flush=True); time.sleep(1)
    out(1, final); print("now showing $%02X = %s (LED7 .. LED0)" % (final, format(final, "08b")))
elif step == "til":
    final = int(rest[0], 16) if rest else 0x5A
    out(0, TIL)
    for d in range(16):
        out(1, d * 0x11); print("%X%X" % (d, d), end=" ", flush=True); time.sleep(0.6)
    out(1, final); print("\nnow showing %02X (HI digit = high nibble)" % final)
elif step == "out":
    on = (rest[:1] or ["on"])[0].lower() == "on"
    c("OUT", 1 if on else 0); print("OUT LED %s" % ("on" if on else "off"))
elif step == "lcd":
    l1 = (rest[0] if rest else "YACC1 I/O card")[:16]; l2 = (rest[1] if len(rest) > 1 else "LCD test 10-10")[:16]
    def cmd(b): out(0, LCDENABLE); out(1, b); time.sleep(0.005)
    def data(s):
        out(0, LCDENABLE | LCDREGISTER)
        for ch in s.encode("ascii", "replace"): out(1, ch)
    for b in (0x38, 0x38, 0x38, 0x0C, 0x01, 0x06):    # 8-bit 2-line 5x8 (three times, the reset sequence), on, clear, entry
        cmd(b)
    data(l1); cmd(0xC0); data(l2); out(0, 0x00)
    print("LCD line 1: %r\nLCD line 2: %r  (if blank: the contrast trimmer TM1)" % (l1, l2))
elif step == "switches":
    out(0, SWITCHLED); a = inp(1, 0x00); b = inp(1, 0xFF)
    if a != b:
        print("switch buffer not driving: read $%02X then $%02X" % (a, b))
    out(1, a); til(a); out(0, 0x00)
    print("switches S7..S0 = %s = $%02X (shown on the LEDs and the TIL311s)" % (format(a, "08b"), a))
elif step == "in":
    c("DATABUS-WR-MODE", 1); c("WR-DATABUS", 0); c("-ALU-FUNC", 1)
    for i, b in enumerate((1, 0, 1, 0)): c("ALU%d" % i, b)
    v = int(c("RBR-COND")); c("-ALU-FUNC", 0)
    print("IN switch = %d" % v)
else:
    sys.exit(__doc__)
c("DATABUS-RD-MODE", 1); c("-BUS-EN", 0); bd.ser.close()

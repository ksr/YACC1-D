#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""I/O card (V1.1) test through the Bus Test Card (bus-driver firmware), CPU out, console cable on the Mac (2026-10-10).

The tester plays the sequencer for OUTI/INP: IOADDR0..3 = the port, the byte on DATA0..7, a -IO-WR pulse (the card's
latches take it at the trailing edge) or -IO-RD held while DATA is read. P0 = the control latch, P1 = the device
selected by it (docs/cards/io.md 3.3: $01 switches/LEDs, $40 + register<<3 the 16550, $80 the TIL311s).

  uart regs     the 16550's scratch register (7) and LCR/DLL/DLM through P0/P1: every data bit both ways
  uart init     the monitor's setup: divisor 3 (38400 with a 1.8432 MHz oscillator), 8N1
  uart tx       bytes written to THR arrive on the Mac's console port (38400 8N1) - the oscillator, MAX232, JP1, cable
  uart rx       bytes sent by the Mac appear in RBR (LSR bit 0 polled) - the receive path
  switches      P1 read with SWITCHLED: printed, compare with the toggles (up = 1, S0 = bit 0)
  leds / TIL311 P1 writes: left showing LEDs = $A5 and the TIL311s = 5A, plus a short walking-bit run on the LEDs
  OUT           the tester drives OUT: the OUT LED blinks three times
The IN switch is read through the ALU's condition mux (BR-COND with ALU = 5) when the ALU card is in.
usage: io_test.py [tester port] [--console PORT]
"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
from busdrv import BusDriver, PORT
import monload, serial

args = sys.argv[1:]
cport = args.pop(args.index("--console") + 1) if "--console" in args else None
if "--console" in args: args.remove("--console")
port = next((a for a in args if not a.startswith("--")), PORT)
con = serial.Serial(cport or monload.find_port(), 38400, timeout=0.5)
bd = BusDriver(port); bd.wait_prompt(timeout=20)
c = bd.cmd
fails = 0
SWITCHLED, UARTCS, TIL = 0x01, 0x40, 0x80
THR = RBR = DLL = 0; DLM = 1; LCR = 3; LSR = 5; SCR = 7

def report(name, bad, detail=""):
    global fails; fails += bool(bad)
    print("%-12s %s  %s" % (name, "FAIL" if bad else "PASS", "; ".join(bad[:6]) + (" (+%d)" % (len(bad) - 6) if len(bad) > 6 else "") if bad else detail), flush=True)

def ioaddr(p):
    for i in range(4): c("IOADDR%d" % i, (p >> i) & 1)

def out(p, v):
    ioaddr(p); c("DATABUS-WR-MODE", 1); c("WR-DATABUS", v & 0xFF); c("-IO-WR", 1); c("-IO-WR", 0)

def inp(p, precharge=0x00):
    ioaddr(p); c("DATABUS-WR-MODE", 1); c("WR-DATABUS", precharge)   # the undriven bus keeps its last value
    c("DATABUS-RD-MODE", 1); c("-IO-RD", 1); v = int(c("RD-DATABUS-L")); c("-IO-RD", 0)
    return v

def uart_w(reg, v): out(0, UARTCS | reg << 3); out(1, v)
def uart_r(reg, pre=0x00): out(0, UARTCS | reg << 3); return inp(1, pre)

for s in ("-IO-RD", "-IO-WR", "-ALU-FUNC", "-AC-RD", "-AC-LD", "-MEM-RD", "-MEM-WR", "-VMA", "-REG-FUNC-RD",
          "-REG-FUNC-LD", "-TMP-REG-RD0", "-TMP-REG-RD1"):
    c(s, 0)
c("-BUS-EN", 1); bd.no_registers(); c("ADDRBUS-WR-MODE", 1); c("WR-ADDRBUS", 0)
bd.pulse("-RESET")

bad = []
for v in [0x00, 0xFF, 0x55, 0xAA] + [1 << i for i in range(8)] + [0xFF ^ (1 << i) for i in range(8)]:
    uart_w(SCR, v); r = uart_r(SCR, v ^ 0xFF)
    if r != v: bad.append("SCR $%02X read $%02X" % (v, r))
uart_w(LCR, 0x80); uart_w(DLL, 0x5A); uart_w(DLM, 0xA5)
r1, r2, r3 = uart_r(DLL, 0xA5), uart_r(DLM, 0x5A), uart_r(LCR, 0x7F)
if (r1, r2, r3) != (0x5A, 0xA5, 0x80): bad.append("DLL/DLM/LCR read $%02X $%02X $%02X (exp $5A $A5 $80)" % (r1, r2, r3))
report("uart regs", bad, "scratch register 20 values, divisor latch and LCR read back")

uart_w(LCR, 0x80); uart_w(DLL, 3); uart_w(DLM, 0); uart_w(LCR, 0x03)
r = uart_r(LCR, 0xFC); lsr = uart_r(LSR)
report("uart init", [] if r == 0x03 else ["LCR $%02X" % r], "divisor 3, 8N1; LSR = $%02X" % lsr)

msg = b"YACC1 I/O card test: tester -> UART -> Mac\r\n"
con.reset_input_buffer(); bad = []
for ch in msg:
    for _ in range(50):
        if uart_r(LSR) & 0x20: break
    else:
        bad.append("THR never empty (LSR $%02X)" % uart_r(LSR)); break
    uart_w(THR, ch)
time.sleep(0.3); got = con.read(len(msg) + 16)
if got != msg: bad.append("Mac got %r" % got)
report("uart tx", bad, "%d bytes arrived on %s" % (len(msg), con.port))

bad = []; got = b""
uart_r(RBR); uart_r(LSR)                              # clear anything stale
for ch in b"Mac -> UART 0123 \x00\xff\x55\xaa":
    con.write(bytes([ch])); con.flush(); time.sleep(0.01)
    for _ in range(20):
        l = uart_r(LSR)
        if l & 0x01: break
    else:
        bad.append("no byte for $%02X (LSR $%02X)" % (ch, l)); continue
    r = uart_r(RBR, ch ^ 0xFF); got += bytes([r])
    if r != ch: bad.append("sent $%02X got $%02X" % (ch, r))
    if l & 0x0E: bad.append("LSR $%02X (overrun/parity/framing) at $%02X" % (l, ch))
report("uart rx", bad, "%d bytes received" % len(got))

out(0, SWITCHLED); sw = inp(1, 0x00); sw2 = inp(1, 0xFF)
report("switches", [] if sw == sw2 else ["unstable: $%02X / $%02X (not driving?)" % (sw, sw2)],
       "S7..S0 = %s ($%02X) - check against the toggles" % (format(sw, "08b"), sw))

out(0, SWITCHLED)
for i in range(8):
    out(1, 1 << i); time.sleep(0.15)
out(1, 0xA5); out(0, TIL); out(1, 0x5A); out(0, 0x00)
print("leds/TIL311 ----  check: the LEDs walked 0..7 and now show $A5 (10100101, LED7 on the left), TIL311s show 5A", flush=True)

for _ in range(3):
    c("OUT", 1); time.sleep(0.3); c("OUT", 0); time.sleep(0.3)
print("OUT         ----  check: the OUT LED blinked three times", flush=True)

c("DATABUS-WR-MODE", 1); c("WR-DATABUS", 0); c("-ALU-FUNC", 1)
for i, b in enumerate((1, 0, 1, 0)): c("ALU%d" % i, b)
inval = int(c("RBR-COND")); c("-ALU-FUNC", 0)
print("IN          ----  IN switch reads %d through the ALU (only meaningful with the ALU card in)" % inval, flush=True)

c("DATABUS-RD-MODE", 1); c("-BUS-EN", 0); bd.ser.close(); con.close()
print("I/O card:", "ALL PASS" if not fails else "%d FAIL" % fails, "(plus the visual checks above)")
sys.exit(1 if fails else 0)

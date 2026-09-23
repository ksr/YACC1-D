#!/usr/bin/env python3
"""ucode_send.py - load the microcode into the sequencer card's EEPROM over its serial port (2026-09-22).

A Python replacement for the Processing sketch embedded/sequencer-card/microcode-loader/simple_microcode_sender_64,
speaking the same download protocol to the Sequencer4 firmware (embedded/sequencer-card/sequencer4/download.ino):

    card:  ">>\\r\\n"                              a prompt before every instruction
    host:  "%" cc ii <1024 hex digits>            checksum (ignored by the card), instruction number, 512 bytes
    ...
    host:  "!"                                    end of the download

After its prompt the card flashes a LED for 100 ms before it reads, and its serial buffer holds 64 bytes, so the sender
waits `--settle` ms (default 250) after every prompt before the record goes out; without that the head of the record is
lost and the card waits forever for the rest (seen 2026-09-22 at 1 ms/char). The record's trailing "-" in test.hex is NOT sent (the card reads exactly 512 byte values; a stray "-" would be an
"Unexpected Char" fault, FAULT LED blinking 5). Like the Processing sender, only the records that differ from
firmware/microcode/ucode-generator2/cache (what the card holds) are sent, and the cache is rewritten as they go, so an
interrupted load can be resumed by running the command again.

Bench order (2026-09-22): UCODESWITCH to DOWNLOAD, then RUN THIS TOOL FIRST - opening the FTDI port resets the ATmega
through DTR - and only then press STARTSWITCH (LOADING on); pressing START before the tool opens the port is undone by
that reset, so START must be pressed again.
Afterwards:  UCODESWITCH back to run, reset: Sequencer4 copies the EEPROM to the microcode RAM and verifies it
(READY after ~54 s). `--boot-check` captures that transcript and compares the five instructions it dumps with test.hex.

  ucode_send.py [--port /dev/cu.usbserial-XXXX] [--all] [--dry-run] [--delay MS] [--hex FILE] [--cache FILE]
  ucode_send.py --boot-check [--port ...] [--log FILE]
"""
import os, sys, time, glob, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEN = os.path.join(ROOT, "firmware/microcode/ucode-generator2")
PROMPT = b">>"
RECORD_LEN = 1 + 2 + 2 + 1024                 # % cc ii data (the '-' is not sent)


def find_port():
    ports = sorted(glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*"))
    if not ports: sys.exit("ucode_send: no /dev/cu.usbserial* or usbmodem* port: is the sequencer card's FTDI plugged in?")
    if len(ports) > 1: sys.exit("ucode_send: several ports, pick one with --port: " + " ".join(ports))
    return ports[0]


def load_records(path):
    """test.hex -> list of record lines (without newline) ending with the '!' sentinel line."""
    lines = open(path).read().split("\n")
    if lines and lines[-1] == "": lines.pop()
    if not lines or lines[-1] != "!": sys.exit("ucode_send: %s does not end with the '!' sentinel" % path)
    recs = lines[:-1]
    if len(recs) != 256: sys.exit("ucode_send: %s has %d records, expected 256" % (path, len(recs)))
    for i, r in enumerate(recs):
        if not (r.startswith("%") and r.endswith("-") and len(r) == RECORD_LEN + 1):
            sys.exit("ucode_send: record %d is malformed (%d chars)" % (i, len(r)))
        if int(r[3:5], 16) != i: sys.exit("ucode_send: record %d carries instruction number %s" % (i, r[3:5]))
    return recs


def load_cache(path):
    if not os.path.exists(path): return [""] * 256
    lines = open(path).read().split("\n")
    while lines and lines[-1] == "": lines.pop()             # the Processing sender leaves an empty 257th line
    if not lines: return [""] * 256                          # an empty file: nothing known about the card
    if len(lines) != 256: sys.exit("ucode_send: %s has %d lines, expected 256" % (path, len(lines)))
    return lines


def save_cache(path, cache):
    tmp = path + ".tmp"
    with open(tmp, "w") as f: f.write("\n".join(cache) + "\n\n")   # same shape as the Processing sender's file
    os.replace(tmp, path)


def open_port(name, timeout):
    try: import serial
    except ImportError: sys.exit("ucode_send: pyserial is needed (pip3 install pyserial)")
    return serial.Serial(name, 115200, timeout=timeout)


def wait_prompt(port, timeout, log=None):
    """Read until a line equal to '>>' arrives; returns the text seen before it. None on timeout."""
    deadline = time.time() + timeout; buf = b""; seen = b""
    while time.time() < deadline:
        c = port.read(1)
        if not c: continue
        buf += c
        if c in b"\r\n":
            line = buf.strip(); buf = b""
            if line == PROMPT: return seen.decode("latin1")
            if line:
                seen += line + b"\n"
                if log: log.write(line.decode("latin1") + "\n"); log.flush()
    return None


def send(args):
    recs = load_records(args.hex)
    cache = load_cache(args.cache)
    todo = [i for i in range(256) if args.all or recs[i] != cache[i]]
    print("%s: %d of 256 records differ from the card's cache%s" % (os.path.relpath(args.hex, ROOT), len(todo), " (--all: sending everything)" if args.all else ""))
    for i in todo: print("  $%02X  %s" % (i, "new" if not cache[i] else "changed"))
    if not todo: print("nothing to send: the card already holds this image"); return
    secs = len(todo) * (RECORD_LEN * (args.delay / 1000.0 + 10.0 / 115200) + args.settle / 1000.0 + 0.1)
    print("about %d s at %g ms per character" % (secs, args.delay))
    if args.dry_run: return
    port = open_port(args.port or find_port(), 0.1)
    print("port %s: waiting for the card's prompt (DOWNLOAD switch, reset, press START)" % port.port)
    try:
        sent = 0
        for i in todo:
            before = wait_prompt(port, args.timeout)
            if before is None: sys.exit("ucode_send: no '>>' prompt within %d s (after %d records)" % (args.timeout, sent))
            time.sleep(args.settle / 1000.0)                  # the card's flashLed(READY) after the prompt
            body = recs[i][:RECORD_LEN]
            for ch in body:
                port.write(ch.encode("ascii"))
                if args.delay: time.sleep(args.delay / 1000.0)
            port.flush()
            cache[i] = recs[i]; save_cache(args.cache, cache); sent += 1
            print("  $%02X sent (%d/%d)" % (i, sent, len(todo)))
        if wait_prompt(port, args.timeout) is None: sys.exit("ucode_send: no prompt before the '!' end mark")
        port.write(b"!"); port.flush()
        print("done: %d records written, cache updated (%s)" % (sent, os.path.relpath(args.cache, ROOT)))
        print("now: UCODESWITCH to run, reset the card, and `ucode_send.py --boot-check` (or watch READY)")
    finally: port.close()


def parse_dump(text):
    """The run-mode boot transcript -> {instruction: {line: bytes}} from its 'Ins=N' / 'LINE:nn b0..b7' blocks."""
    dumps = {}; cur = None
    for line in text.splitlines():
        if line.startswith("Ins="):
            cur = int(line[4:].strip()); dumps[cur] = {}
        elif line.startswith("LINE:") and cur is not None:
            n = int(line[5:7]); dumps[cur][n] = bytes.fromhex(line[8:].replace(" ", ""))
    return dumps


def check_dumps(text, recs):
    """Compare the dumped instructions with test.hex; returns (checked, list of mismatch strings)."""
    bad = []; checked = 0
    for ins, lines in parse_dump(text).items():
        want = bytes.fromhex(recs[ins][5:5 + 1024])
        for n, got in lines.items():
            checked += 1
            if got != want[n * 8:n * 8 + 8]: bad.append("$%02X line %02d: card %s, tree %s" % (ins, n, got.hex(), want[n * 8:n * 8 + 8].hex()))
    return checked, bad


def boot_check(args):
    recs = load_records(args.hex)
    port = open_port(args.port or find_port(), 0.2)
    print("port %s: reset the card in run mode; capturing until READY (or %d s)" % (port.port, args.timeout))
    text = ""; deadline = time.time() + args.timeout
    try:
        while time.time() < deadline:
            c = port.read(4096)
            if c:
                s = c.decode("latin1"); text += s; sys.stdout.write(s); sys.stdout.flush()
                if "READY!!!" in text or "RAM verify failed" in text or "MISMATCH" in text: time.sleep(1); text += port.read(4096).decode("latin1"); break
    finally: port.close()
    if args.log:
        with open(args.log, "w") as f: f.write(text)
        print("\ntranscript saved to %s" % args.log)
    checked, bad = check_dumps(text, recs)
    ok = "RAM == EEPROM for all 256 instructions" in text
    print("\ncard verify: %s" % ("RAM == EEPROM" if ok else "NOT confirmed"))
    print("dump vs test.hex: %d lines compared, %d mismatches" % (checked, len(bad)))
    for b in bad[:20]: print("  " + b)
    if not ok or bad or checked == 0: sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", help="serial port (default: the single /dev/cu.usbserial*)")
    ap.add_argument("--hex", default=os.path.join(GEN, "test.hex"))
    ap.add_argument("--cache", default=os.path.join(GEN, "cache"))
    ap.add_argument("--all", action="store_true", help="send all 256 records, ignoring the cache")
    ap.add_argument("--dry-run", action="store_true", help="list what would be sent, touch nothing")
    ap.add_argument("--delay", type=float, default=2.0, help="ms between characters (the Processing sender used 25)")
    ap.add_argument("--settle", type=float, default=250.0, help="ms to wait after the card's prompt before sending (its LED flash)")
    ap.add_argument("--timeout", type=int, default=120, help="seconds to wait for the card's prompt / READY")
    ap.add_argument("--boot-check", action="store_true", help="capture a run-mode boot and compare its dumps with test.hex")
    ap.add_argument("--log", help="--boot-check: save the transcript here")
    args = ap.parse_args()
    if args.boot_check: boot_check(args)
    else: send(args)


if __name__ == "__main__":
    main()

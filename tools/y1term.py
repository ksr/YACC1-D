#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""y1term.py - a terminal for the YACC1 console that can also type a text file into BASIC (2026-10-08).

  y1term.py [--port /dev/cu.usbserial-AB0MVHSQ] [--log FILE]       the terminal (Ctrl-] for the menu)
  y1term.py --send PROG.BAS [--new] [--run] [--stay] [options]      type PROG.BAS into BASIC and exit (or --stay)

The terminal: what is typed goes to the machine, what it sends is shown (the monitor and BASIC echo, so there is no
local echo). Enter sends CR (the ROM's uartin makes it LF); backspace sends what the keyboard sends ($7F on a Mac:
BASIC takes $7F and $08 since ROM 2026-10-07; the monitor's own commands take neither). Ctrl-] then:
  s  send a file to BASIC (asks for the path)      q  quit
  n  NEW before the next file is sent (toggle)      h  this help
  ]  send a Ctrl-] itself

Sending a file: the lines go one at a time, each typed a character at a time (--delay, default 5 ms: the monitor
spends ~1.6 ms on each character at 1 MHz, BASIC's line input about the same), then CR, then the tool waits for
BASIC's prompt (`>>`, --prompt) before the next line. A line BASIC answers with SYNTAX ERROR or UNKNOWN COMMAND is
reported (with its line number in the file) and the rest is sent (--stop-on-error to stop there). Blank lines and
lines starting with '#' (comments for the host) are skipped; tabs become spaces; a line longer than --maxlen
(default 200: BASIC's input line holds 256 bytes and nothing checks it, docs/programming/MEMORY-MAP.md 2a) is
refused. Before the first line the tool sends a CR and reads the prompt: at the monitor's `>` it types `I` to start
BASIC first. --new sends NEW first; --run sends RUN after the last line and shows its output until the prompt
returns (--run-timeout, default 60 s).

Exit status (--send): 0 all lines accepted, 1 a line was refused or a prompt did not come.
"""
import os, sys, time, select, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import monload                                   # noqa: E402  (find_port: the console FTDI, never the sequencer's)

ERRORS = (b"SYNTAX ERROR", b"UNKNOWN COMMAND")
CTRL_RB = 0x1D                                   # Ctrl-]


class Console:
    def __init__(self, port, baud, log):
        import serial
        self.s = serial.Serial(port, baud, timeout=0)
        self.log = open(log, "ab") if log else None
        self.show = True                         # copy what arrives to the screen

    def out(self, data):
        if self.show:
            os.write(sys.stdout.fileno(), data)
        if self.log:
            self.log.write(data); self.log.flush()

    def read(self, t):
        """everything that arrives in t seconds (shown and logged)"""
        end = time.time() + t; got = b""
        while time.time() < end:
            r, _, _ = select.select([self.s.fileno()], [], [], max(0, end - time.time()))
            if r:
                b = self.s.read(4096)
                if b:
                    got += b; self.out(b)
        return got

    def type(self, text, delay):
        for ch in text:
            self.s.write(bytes([ch])); self.s.flush()
            if delay: time.sleep(delay)

    def until(self, test, timeout, quiet=0.3):
        """read until test(received) holds and the line has been quiet for `quiet` s, or timeout -> (received, ok)"""
        end = time.time() + timeout; got = b""; last = time.time()
        while time.time() < end:
            r, _, _ = select.select([self.s.fileno()], [], [], 0.05)
            if r:
                b = self.s.read(4096)
                if b:
                    got += b; last = time.time(); self.out(b); continue
            if test(got) and time.time() - last >= quiet:
                return got, True
        return got, False


def at_prompt(prompt):
    p = prompt.encode()
    return lambda got: got.rstrip(b" ").endswith(p)


def basic_lines(path, maxlen):
    """-> [(line number in the file, text)], or SystemExit on a line too long"""
    out = []
    for n, raw in enumerate(open(path, encoding="latin-1").read().splitlines(), 1):
        t = raw.replace("\t", " ").rstrip()
        if not t.strip() or t.lstrip().startswith("#"):
            continue
        if len(t) > maxlen:
            sys.exit("y1term: %s line %d is %d characters, more than --maxlen %d" % (path, n, len(t), maxlen))
        out.append((n, t.lstrip()))
    return out


def to_basic(con, a):
    """make sure BASIC's prompt is up: a CR, then I if the monitor answers -> True"""
    con.type(b"\r", a.delay / 1000.0)
    got, ok = con.until(lambda g: at_prompt(a.prompt)(g) or g.rstrip().endswith(b">"), a.timeout)
    if at_prompt(a.prompt)(got):
        return True
    if ok:                                            # the monitor's '>'
        con.type(b"I\r", a.delay / 1000.0)
        got, ok = con.until(at_prompt(a.prompt), a.timeout)
        if ok:
            return True
    sys.stderr.write("\ny1term: no BASIC prompt (%r) - is the machine reset and at the monitor or in BASIC?\n" % a.prompt)
    return False


def send_file(con, path, a, new=False, run=False):
    """type path into BASIC, line by line -> (lines sent, [(file line, text, answer)], prompt lost)"""
    lines = basic_lines(path, a.maxlen)
    if not to_basic(con, a):
        return 0, [], True
    d = a.delay / 1000.0
    pre = [(0, "NEW")] if new else []
    bad, sent = [], 0
    t0 = time.time()
    for n, text in pre + lines:
        con.type(text.encode("latin-1") + b"\r", d)
        got, ok = con.until(at_prompt(a.prompt), a.timeout)
        if not ok:
            sys.stderr.write("\ny1term: no prompt after %s line %d (%r) within %g s - stopped\n" % (path, n, text, a.timeout))
            return sent, bad, True
        if n:
            sent += 1
        err = [e for e in ERRORS if e in got]
        if err:
            bad.append((n, text, err[0].decode()))
            if a.stop_on_error:
                break
    if run and not (bad and a.stop_on_error):
        con.type(b"RUN\r", d)
        con.until(at_prompt(a.prompt), a.run_timeout)
    sys.stderr.write("\ny1term: %s: %d lines sent in %.1f s%s\n" % (
        path, sent, time.time() - t0, "; refused:" if bad else ", all accepted"))
    for n, text, e in bad:
        sys.stderr.write("  line %d: %s  -> %s\n" % (n, text, e))
    return sent, bad, False


MENU = b"\r\n[y1term] s send a file to BASIC   n NEW before sending (now %s)   q quit   ] send Ctrl-]   h help\r\n"


def terminal(con, a):
    import termios, tty
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    new_first = a.new
    sys.stderr.write("y1term: %s at %d baud - Ctrl-] then h for help, q to quit\r\n" % (con.s.port, a.baud))
    try:
        tty.setraw(fd)
        while True:
            r, _, _ = select.select([fd, con.s.fileno()], [], [])
            if con.s.fileno() in r:
                b = con.s.read(4096)
                if b:
                    con.out(b)
            if fd in r:
                k = os.read(fd, 1)
                if not k:
                    break
                if k[0] != CTRL_RB:
                    con.s.write(k); con.s.flush()
                    continue
                os.write(sys.stdout.fileno(), b"\r\n[y1term] ? ")
                c = os.read(fd, 1)
                if c in (b"q", b"Q"):
                    break
                elif c == bytes([CTRL_RB]) or c == b"]":
                    con.s.write(bytes([CTRL_RB])); con.s.flush()
                elif c in (b"n", b"N"):
                    new_first = not new_first
                    os.write(sys.stdout.fileno(), b"NEW before the next file: %s\r\n" % (b"yes" if new_first else b"no"))
                elif c in (b"s", b"S"):
                    termios.tcsetattr(fd, termios.TCSADRAIN, saved)
                    try:
                        path = input("\nfile to send to BASIC: ").strip()
                    except EOFError:
                        path = ""
                    path = os.path.expanduser(path)
                    if path and os.path.isfile(path):
                        try:
                            send_file(con, path, a, new=new_first)
                        except SystemExit as e:
                            sys.stderr.write("%s\n" % e)
                    elif path:
                        sys.stderr.write("y1term: no file %s\n" % path)
                    tty.setraw(fd)
                else:
                    os.write(sys.stdout.fileno(), MENU % (b"yes" if new_first else b"no"))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        sys.stderr.write("\ny1term: closed\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=38400)
    ap.add_argument("--log", help="append everything the machine sends to this file")
    ap.add_argument("--send", metavar="FILE", help="type FILE into BASIC, then exit (or --stay)")
    ap.add_argument("--new", action="store_true", help="send NEW before the file")
    ap.add_argument("--run", action="store_true", help="send RUN after the file")
    ap.add_argument("--stay", action="store_true", help="after --send, stay in the terminal")
    ap.add_argument("--delay", type=float, default=5.0, help="ms between characters (default 5)")
    ap.add_argument("--timeout", type=float, default=10.0, help="s to wait for the prompt after a line (default 10)")
    ap.add_argument("--run-timeout", type=float, default=60.0, help="s to wait for the prompt after RUN (default 60)")
    ap.add_argument("--prompt", default=">>", help="BASIC's prompt (default >>)")
    ap.add_argument("--maxlen", type=int, default=200, help="longest line sent (default 200)")
    ap.add_argument("--stop-on-error", action="store_true", help="stop at the first refused line")
    a = ap.parse_args()
    con = Console(a.port or monload.find_port(), a.baud, a.log)
    if a.send:
        if not os.path.isfile(a.send):
            sys.exit("y1term: no file %s" % a.send)
        sent, bad, lost = send_file(con, a.send, a, new=a.new, run=a.run)
        if a.stay and sys.stdin.isatty():
            terminal(con, a)
        sys.exit(1 if bad or lost else 0)
    if not sys.stdin.isatty():
        sys.exit("y1term: the terminal needs a keyboard (or use --send FILE)")
    terminal(con, a)


if __name__ == "__main__":
    main()

# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""The debugger's command language, shared by the terminal UI, the browser (web.py) and scripts (-c, --script).

  s [N]              step N instructions (default 1)        n            step over a JSR/JSRUR (else s)
  us [N]             step N microcode steps                  c            continue: until a breakpoint, a watch, HALT
  pause | stop       pause a run                             until ADDR   run to ADDR
  reset              the machine's reset (RAM and the video card keep their contents)
  b ADDR | bd ADDR | bd all | bl           breakpoints (the next instruction is at ADDR)
  w r|w|rw ADDR | wd r|w|rw ADDR | wd all | wl     memory watches (a read watch also sees fetches)
  r                  registers                               set R3=1234 | set acc=41 | set pc=F000 ...
  m [ADDR] [LEN]     memory dump (hex LEN, default 80)       poke ADDR BB [BB...]
  d [ADDR] [N]       disassemble N instructions (default 16, at PC)
  trace [N]          the last N instructions run (default 20)
  screen             the video screen as text                video        the CRTC registers, the card model
  key TEXT           type into the UART (\\n = Enter, \\e = Esc, \\xHH a byte, \\\\ a backslash)
  console            the UART's output since the last `console`
  waitfor TEXT [S]   run until the UART prints TEXT (at most S seconds, default the timeout); for scripts
  sym FILE           symbols from an RC/asm listing           load FILE    an Intel-hex image into memory
  sleep S            wait S seconds (the machine runs on if it is running)
  help | quit
ADDR: hex (F06A, $F06A, 0xF06A, 0F06AH), a symbol (cmdloop, vputc, any case), r0..r7, pc, sp, or name+hex.
"""
import os, time
from .debugger import Symbols, parse_addr, listing, disasm, block_reader, screen as draw_screen
from .emu import EmulatorError


class Shell:
    def __init__(self, emu, syms=None, timeout=60.0):
        self.emu = emu; self.syms = syms or Symbols(); self.timeout = timeout
        self.blocking = True              # scripts: c/until/n/waitfor wait for the stop; the TUI runs them in the background
        self.con = ""                     # every byte the UART has sent (the last 1 MB)
        self.con_shown = 0                # `console` shows from here
        self.wait_from = 0                # `waitfor` searches from here
        self.dropped = 0
        self.seen = "stopped"             # the state a UI last saw (snapshot(): a run's end is reported once)

    # ------------------------------------------------------------------ the emulator
    def regs(self):
        return self.emu.ok("regs")

    def read(self, a, n):
        out = b""
        while len(out) < n:               # wraps at $FFFF
            k = min(n - len(out), 0x10000 - ((a + len(out)) & 0xFFFF))
            out += self.emu.mem((a + len(out)) & 0xFFFF, k)
        return out

    def fetch_console(self):
        """the UART's new output, appended to self.con; returns it"""
        t = self.emu.ok("console")["text"]
        if t:
            self.con += t
            if len(self.con) > 1 << 20:
                cut = len(self.con) - (1 << 19)
                self.con = self.con[cut:]; self.dropped += cut
                self.con_shown = max(0, self.con_shown - cut); self.wait_from = max(0, self.wait_from - cut)
        return t

    def addr(self, text, regs=None):
        return parse_addr(text, self.syms, regs if regs is not None else self.regs())

    def running(self):
        return self.emu.ok("status")["state"] == "running"

    def wait_stop(self, timeout=None):
        """scripts: wait until the machine stops; after timeout, pause it"""
        end = time.time() + (self.timeout if timeout is None else timeout)
        while True:
            st = self.emu.ok("status")
            if st["state"] != "running": return st["reason"]
            if time.time() > end:
                self.emu.ok("pause"); return "timeout: paused after %g s" % (self.timeout if timeout is None else timeout)
            self.fetch_console(); time.sleep(0.02)

    # ------------------------------------------------------------------ the language
    def exec(self, line):
        """run one command line; returns the text to show"""
        line = line.strip()
        if not line or line.startswith("#"): return ""
        cmd, _, rest = line.partition(" ")
        a = rest.split()
        try:
            return self._exec(cmd.lower(), rest, a)
        except (ValueError, IndexError) as e:
            return "error: %s (help)" % e
        except EmulatorError as e:
            return "error: %s" % e

    def _exec(self, cmd, rest, a):
        e = self.emu
        if cmd in ("help", "?", "h"):
            return __doc__.split("\n", 2)[2].rstrip()
        if cmd == "s":
            n = int(a[0], 0) if a else 1
            r = e.ok("step %d" % n); return self._after(r)
        if cmd == "us":
            n = int(a[0], 0) if a else 1
            r = e.ok("ustep %d" % n); return self._after(r)
        if cmd == "n":
            regs = self.regs(); pc = regs["pc"]
            L, text, _ = disasm(self.read, pc, self.syms)
            if regs["step"] == 0 and text.split()[0] in ("JSR", "JSRUR"):
                return self._run("until %X" % ((pc + L) & 0xFFFF))
            return self._after(e.ok("step 1"))
        if cmd == "c":
            return self._run("run")
        if cmd == "until":
            return self._run("until %X" % self.addr(a[0]))
        if cmd in ("pause", "stop"):
            r = e.ok("pause"); self.seen = r["state"]; return self._after(r)
        if cmd == "reset":
            e.ok("reset"); return "reset\n" + self.here()
        if cmd == "b":
            x = self.addr(a[0]); e.ok("break add %X" % x); return "breakpoint %04X%s" % (x, self.syms.tag(x))
        if cmd == "bd":
            if a and a[0] == "all": e.ok("break del all"); return "breakpoints cleared"
            x = self.addr(a[0]); e.ok("break del %X" % x); return "deleted %04X" % x
        if cmd == "bl":
            return "\n".join("%04X%s" % (x, self.syms.tag(x)) for x in e.ok("break list")["breaks"]) or "no breakpoints"
        if cmd in ("w", "wd"):
            if cmd == "wd" and a and a[0] == "all": e.ok("watch del all"); return "watches cleared"
            kind = a[0].lower()
            if kind not in ("r", "w", "rw"): raise ValueError("w r|w|rw ADDR")
            x = self.addr(a[1])
            e.ok("watch %s %s %X" % ("add" if cmd == "w" else "del", kind, x))
            return ("watch %s %04X%s" if cmd == "w" else "deleted %s %04X%s") % (kind, x, self.syms.tag(x))
        if cmd == "wl":
            ws = e.ok("watch list")["watches"]
            return "\n".join("%-2s %04X%s" % ({1: "r", 2: "w", 3: "rw"}[k], x, self.syms.tag(x)) for x, k in ws) or "no watches"
        if cmd == "r":
            return "\n".join(self.regs_text(self.regs()))
        if cmd == "set":
            k, _, v = rest.replace(" ", "").partition("=")
            if not v: raise ValueError("set NAME=VALUE")
            r = e.ok("set %s %X" % (k.lower(), int(v.lstrip("$"), 16)))
            return "\n".join(self.regs_text(r))
        if cmd == "m":
            regs = self.regs()
            x = self.addr(a[0], regs) if a else regs["pc"]
            n = int(a[1], 16) if len(a) > 1 else 0x80
            return self.dump(x, n)
        if cmd == "poke":
            x = self.addr(a[0]); bs = [int(b.lstrip("$"), 16) for b in a[1:]]
            if not bs or any(b > 255 for b in bs): raise ValueError("poke ADDR BB [BB...]")
            e.ok("poke %X %s" % (x, " ".join("%02X" % b for b in bs)))
            return self.dump(x, max(16, len(bs)))
        if cmd == "d":
            regs = self.regs()
            x = self.addr(a[0], regs) if a else regs["pc"]
            n = int(a[1], 0) if len(a) > 1 else 16
            return "\n".join(self.lines(x, n, regs["pc"]))
        if cmd == "trace":
            n = int(a[0], 0) if a else 20
            out = []
            for pc, op, acc, c, *r in e.ok("trace %d" % n)["trace"]:
                L, text, _ = disasm(self.read, pc, self.syms)
                out.append("%04X %-30s ACC=%02X C=%d R1=%04X R3=%04X R7=%04X%s" % (pc, text[:30], acc, c, r[1], r[3], r[7], self.syms.tag(pc)))
            return "\n".join(out) or "no trace yet"
        if cmd == "screen":
            sc = draw_screen(e.ok("video"))
            if sc["absent"]: return "no video card (-N)"
            border = "+" + "-" * sc["cols"] + "+"
            head = "video: %d x %d from $%04X (%s)%s" % (sc["cols"], sc["rows"], 0xD000 + (sc["start"] & 0x7FF), sc["source"],
                                                        ", cursor row %d col %d" % sc["cursor"] if sc["cursor"] else "")
            return "\n".join([head, border] + ["|%s|" % l for l in sc["lines"]] + [border])
        if cmd == "video":
            v = e.ok("video")
            card = "behavioural model" if v.get("model", "behavioural") == "behavioural" else \
                "%s at gate level, %d bus events" % (v["model"], v.get("events", 0))
            return "CRTC " + " ".join("%02X" % r if w else "--" for r, w in zip(v["regs"], v["written"])) + \
                "  (R0..R17, -- = never written); address register = R%d; card: %s" % (v["sel"], card)
        if cmd == "key":
            r = e.ok("key " + rest); return "typed %d" % r["queued"]
        if cmd == "console":
            self.fetch_console()
            t = self.con[self.con_shown:]; self.con_shown = len(self.con)
            return printable(t)
        if cmd == "waitfor":
            text, secs = rest, self.timeout
            head, _, last = rest.rpartition(" ")
            if head.strip():
                try: text, secs = head, float(last)
                except ValueError: pass
            return self.waitfor(text.replace("\\n", "\n").replace("\\r", "\r"), secs)
        if cmd == "sym":
            return "%d symbols from %s" % (self.syms.load(rest.strip()), rest.strip())
        if cmd == "load":
            r = e.ok("load " + os.path.abspath(rest.strip())); return "loaded %d bytes" % r["bytes"]
        if cmd == "sleep":
            time.sleep(float(a[0])); self.fetch_console(); return ""
        if cmd in ("quit", "q", "exit"):
            return ""
        return "unknown command '%s' (help)" % cmd

    def _run(self, what):
        r = self.emu.ok(what)
        if not self.blocking:
            self.seen = r["state"]
            return "running" if r["state"] == "running" else self._after(r)
        reason = self.wait_stop()
        self.fetch_console()
        return reason + "\n" + self.here()

    def waitfor(self, text, secs):
        """run (if stopped) until the UART's output since the last waitfor holds text"""
        end = time.time() + secs
        started = False
        while True:
            self.fetch_console()
            i = self.con.find(text, self.wait_from)
            if i >= 0:
                self.wait_from = i + len(text)
                if started: self.emu.ok("pause")
                return "found %r" % text
            st = self.emu.ok("status")
            if st["state"] != "running":
                if started and st["reason"] != "running": return "stopped (%s) before %r appeared" % (st["reason"], text)
                self.emu.ok("run"); started = True
            if time.time() > end:
                self.emu.ok("pause"); return "timeout: %r did not appear in %g s" % (text, secs)
            time.sleep(0.01)

    # ------------------------------------------------------------------ what the UIs show
    def snapshot(self, code=40, mem=None, mem_len=256):
        """one look at the machine for a UI (the terminal's and the browser's): the UART's new output fetched, the
        registers (with the status), the video card's state, the breakpoints and watches, `code` instructions from PC
        (read in one block) and, with mem, mem_len bytes from mem. `note` is the text to log when a run has just
        stopped (its reason and the instruction it stopped at), once, else None."""
        e = self.emu
        self.fetch_console()
        regs = self.regs()
        snap = {"regs": regs, "video": e.ok("video"), "breaks": e.ok("break list")["breaks"],
                "watches": e.ok("watch list")["watches"], "note": None}
        try:
            snap["code"] = listing(block_reader(self.read, regs["pc"], 3 * code + 3), regs["pc"], code, self.syms)
        except Exception as ex:                 # noqa: BLE001 - never let the disassembly stop a UI
            snap["code"] = []; snap["note"] = "disassembly: %s" % ex
        if mem is not None:
            snap["mem"] = self.read(mem, mem_len)
        if self.seen == "running" and regs["state"] != "running":
            snap["note"] = "%s\n%s" % (regs["reason"], self.here())
        self.seen = regs["state"]
        return snap

    def console_total(self):
        """how many bytes the UART has sent in all (a UI's 'anything new?')"""
        return self.dropped + len(self.con)

    # ------------------------------------------------------------------ formatting
    def _after(self, r):
        return "%s\n%s" % (r["reason"], self.here())

    def here(self):
        regs = self.regs()
        return "\n".join(self.lines(regs["pc"], 1, regs["pc"]) + self.regs_text(regs))

    def lines(self, a, n, pc=None):
        out = []
        for ad, bs, text in listing(self.read, a, n, self.syms):
            lab = self.syms.name(ad)
            if lab: out.append("        %s:" % lab)
            out.append("%s%04X  %-9s %s" % (">" if ad == pc else " ", ad, bs.hex(" "), text))
        return out

    def regs_text(self, r):
        rr = r["r"]
        return ["PC=%04X%s  " % (r["pc"], self.syms.tag(r["pc"])) + " ".join("R%d=%04X" % (i, rr[i]) for i in range(8)),
                "ACC=%02X C=%d TMP0=%04X TMP1=%04X SR=%02X IR=%02X step=%d%s  instr=%d steps=%d clocks=%d  %s (%s)" % (
                    r["acc"], r["carry"], r["tmp0"], r["tmp1"], r["sreg"], r["ir"], r["step"],
                    " FORCE-ROM" if r["force_rom"] else "", r["instr"], r["steps"], r["clocks"], r["state"], r["reason"])]

    def dump(self, x, n):
        data = self.read(x, n); out = []
        for i in range(0, n, 16):
            row = data[i:i + 16]
            out.append("%04X  %-48s %s" % ((x + i) & 0xFFFF, row.hex(" "), "".join(chr(b) if 32 <= b < 127 else "." for b in row)))
        return "\n".join(out)


def printable(t):
    """UART text for a terminal: CR LF and LF CR become one newline, other control bytes shown as ^X"""
    t = t.replace("\r\n", "\n").replace("\n\r", "\n").replace("\r", "")
    return "".join(c if c == "\n" or c == "\t" or 32 <= ord(c) < 127 else "^" + chr(64 + (ord(c) & 31)) for c in t)


def console_lines(text, width):
    """the UART text as the lines a terminal would show (CR LF / LF CR as one newline, BS erases, tabs to 8)"""
    out, cur = [], []
    for ch in printable(text[-65536:]).replace("^H", "\b"):
        if ch == "\n": out.append("".join(cur)); cur = []
        elif ch == "\b":
            if cur: cur.pop()
        elif ch == "\t":
            cur.append(" ")
            while len(cur) % 8: cur.append(" ")
        else:
            cur.append(ch)
            if len(cur) >= width: out.append("".join(cur)); cur = []
    out.append("".join(cur))
    return out

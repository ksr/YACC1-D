# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""The terminal debugger (curses).

  +-- YACC1 screen 64x24 (CRTC) RUNNING ------------+ +-- registers ----------------------+
  |  the video card's display RAM, drawn with the    | | PC, R0-R7, ACC, C, TMP0/1, IR ... |
  |  6845's geometry; inverse = bit 7; the cursor    | +-- code ---------------------------+
  |  from R14:R15                                    | | the disassembly from PC           |
  +--------------------------------------------------+ +-- output -------------------------+
  +-- console (UART) --------------------------------+ | what the commands said            |
  |  what the machine sent on its serial port        | |                                   |
  +--------------------------------------------------+ +-----------------------------------+
  > command line                                      (status line)

Commands as in shell.py (help), plus `snap FILE` (write this whole screen as text) and `q` (quit).
Keys: F5 continue, F6 or Esc pause, F7 step, F8 step over; Up/Down command history; PgUp/PgDn scroll the console.
While the machine runs, typed keys go to its UART (Enter = CR, which the UART path turns into LF, as for a
terminal); Tab switches between the UART and the command line while it runs; Esc pauses. While it is stopped the
command line has the keys. Ctrl-C at the command line quits. The panes refresh 10 times a second while it runs.
A terminal of at least 120 x 36 shows all the panes; a smaller one shows the screen (clipped), the console and the
output, with the registers in the status line.
"""
import curses, os, time
from .debugger import screen as draw_screen
from .shell import printable, console_lines

GUTTER = 84                               # the screen pane's width: 80 columns + borders + 2


class TUI:
    def __init__(self, shell):
        self.sh = shell; self.sh.blocking = False
        self.out = ["y1dbg - the YACC1 debugger on y1ucemu (microcode level). 'help' for commands, F5 or 'c' to run."]
        self.cmd = ""; self.history = []; self.hpos = 0
        self.focus = "cmd"; self.state = {}; self.video = None; self.code = []; self.breaks = set()
        self.con_scroll = 0; self.last_state = "stopped"; self.keys = ""

    def log(self, text):
        for l in str(text).splitlines() or [""]:
            self.out.append(l)
        self.out = self.out[-500:]

    # ------------------------------------------------------------------ state
    def refresh_state(self):
        sh = self.sh
        if self.keys:
            sh.emu.cmd("key " + self.keys); self.keys = ""
        snap = sh.snapshot(code=40)               # shared with the browser (shell.py)
        self.state, self.video, self.code = snap["regs"], snap["video"], snap["code"]
        self.breaks = set(snap["breaks"])
        if snap["note"]:
            self.log(snap["note"])
            if self.state["state"] != "running": self.focus = "cmd"
        self.last_state = self.state["state"]

    # ------------------------------------------------------------------ drawing
    def put(self, scr, y, x, text, attr=0, width=None):
        H, W = scr.getmaxyx()
        if y < 0 or y >= H or x >= W: return
        width = W - x if width is None else min(width, W - x)
        if width <= 0: return
        try: scr.addstr(y, x, text[:width], attr)
        except curses.error: pass             # the bottom-right cell

    def box(self, scr, y, x, h, w, title):
        if h < 2 or w < 2: return
        H, W = scr.getmaxyx()
        try:
            win = scr.derwin(min(h, H - y), min(w, W - x), y, x); win.box()
        except curses.error:
            return
        self.put(scr, y, x + 2, " %s " % title, curses.A_BOLD, w - 4)

    def draw_screen_pane(self, scr, y, x, h, w):
        st = self.state; running = st.get("state") == "running"
        sc = draw_screen(self.video) if self.video else None
        if not sc or sc["absent"]:
            self.box(scr, y, x, h, w, "YACC1 screen: no video card (-N)"); return
        self.box(scr, y, x, h, w, "YACC1 screen %dx%d %s%s" % (sc["cols"], sc["rows"], "(CRTC)" if "CRTC" in sc["source"] else "(default)",
                                                             "  RUNNING" if running else ""))
        cur = sc["cursor"]
        for r in range(min(sc["rows"], h - 2)):
            line, inv = sc["lines"][r], sc["inverse"][r]
            c = 0
            while c < min(sc["cols"], w - 2):
                a = inv[c] ^ (cur == (r, c))
                e = c
                while e < min(sc["cols"], w - 2) and (inv[e] ^ (cur == (r, e))) == a: e += 1
                self.put(scr, y + 1 + r, x + 1 + c, line[c:e], curses.A_REVERSE if a else 0)
                c = e

    def draw_regs(self, scr, y, x, h, w):
        s = self.state
        self.box(scr, y, x, h, w, "registers")
        if not s: return
        r = s["r"]; sym = self.sh.syms.tag(s["pc"])
        rows = ["PC %04X%s" % (s["pc"], sym),
                "  ".join("R%d %04X" % (i, r[i]) for i in range(4)),
                "  ".join("R%d %04X" % (i, r[i]) for i in range(4, 8)),
                "ACC %02X  C %d  SR %02X  TMP0 %04X  TMP1 %04X" % (s["acc"], s["carry"], s["sreg"], s["tmp0"], s["tmp1"]),
                "IR %02X  step %d  operand %02X  branch %04X%s" % (s["ir"], s["step"], s["operand"], s["branch"], "  FORCE-ROM" if s["force_rom"] else ""),
                "instr %d  clocks %d  fights %d" % (s["instr"], s["clocks"], s["fights"]),
                "%s: %s" % (s["state"], s["reason"])]
        for i, t in enumerate(rows[:h - 2]):
            self.put(scr, y + 1 + i, x + 1, t, curses.A_BOLD if i == len(rows) - 1 and s["state"] == "running" else 0, w - 2)

    def draw_code(self, scr, y, x, h, w):
        self.box(scr, y, x, h, w, "code" + (" (where it was)" if self.state.get("state") == "running" else ""))
        pc = self.state.get("pc"); i = 0
        for a, bs, text in self.code:
            if i >= h - 2: break
            lab = self.sh.syms.name(a)
            if lab and i < h - 3:
                self.put(scr, y + 1 + i, x + 1, "        %s:" % lab, curses.A_DIM, w - 2); i += 1
            mark = ">" if a == pc else ("*" if a in self.breaks else " ")
            self.put(scr, y + 1 + i, x + 1, "%s%04X %-9s %s" % (mark, a, bs.hex(" "), text), curses.A_REVERSE if a == pc else 0, w - 2)
            i += 1

    def draw_text(self, scr, y, x, h, w, title, lines):
        self.box(scr, y, x, h, w, title)
        for i, l in enumerate(lines[-(h - 2):] if h > 2 else []):
            self.put(scr, y + 1 + i, x + 1, l, 0, w - 2)

    def draw(self, scr):
        scr.erase()
        H, W = scr.getmaxyx()
        if H < 12 or W < 40:
            self.put(scr, 0, 0, "y1dbg: the terminal is too small (%d x %d)" % (W, H)); scr.refresh(); return
        sc_rows = (draw_screen(self.video)["rows"] if self.video else 24)
        body = H - 2
        con = console_lines(self.sh.con, max(10, min(W, GUTTER) - 2))
        if self.con_scroll: con = con[:-self.con_scroll] if self.con_scroll < len(con) else con[:1]
        if W >= GUTTER + 36 and H >= 36:          # all the panes
            sh_ = min(sc_rows + 2, body - 8)
            self.draw_screen_pane(scr, 0, 0, sh_, GUTTER - 2)
            self.draw_text(scr, sh_, 0, body - sh_, GUTTER - 2, "console (UART)%s" % (" - scrolled" if self.con_scroll else ""), con)
            rw = W - GUTTER + 2; rx = GUTTER - 2
            self.draw_regs(scr, 0, rx, 9, rw)
            ch = (body - 9) // 2
            self.draw_code(scr, 9, rx, ch, rw)
            self.draw_text(scr, 9 + ch, rx, body - 9 - ch, rw, "output", self.out)
        else:                                      # compact: screen, console, output
            sh_ = min(sc_rows + 2, max(4, body - 8))
            self.draw_screen_pane(scr, 0, 0, sh_, min(W, GUTTER - 2))
            rest = body - sh_; ch = rest // 2
            self.draw_text(scr, sh_, 0, ch, W, "console (UART)", con)
            self.draw_text(scr, sh_ + ch, 0, rest - ch, W, "output", self.out)
        s = self.state
        if self.focus == "uart" and s.get("state") == "running":
            prompt = "[running: keys go to the UART; Tab = command line, Esc/F6 = pause] " + printable(self.keys)
        else:
            prompt = ("[running] " if s.get("state") == "running" else "") + "> " + self.cmd
        self.put(scr, H - 2, 0, prompt[-(W - 1):])
        if s:
            stat = "PC %04X  %s (%s)  instr %d  clocks %d" % (s["pc"], s["state"], s["reason"], s["instr"], s["clocks"])
            if not (W >= GUTTER + 36 and H >= 36):
                stat = "PC %04X R1 %04X R3 %04X R7 %04X ACC %02X C %d  " % (s["pc"], s["r"][1], s["r"][3], s["r"][7], s["acc"], s["carry"]) + \
                    "%s (%s)" % (s["state"], s["reason"])
            self.put(scr, H - 1, 0, stat, curses.A_DIM, W - 1)
        scr.refresh()

    def snap(self, scr, path):
        H, W = scr.getmaxyx()
        acs = {"q": "-", "x": "|"}                 # the box lines (the alternate character set) as plain ASCII
        rows = []
        for y in range(H):
            row = ""
            for x in range(W - (1 if y == H - 1 else 0)):
                c = scr.inch(y, x); ch = chr(c & 0xFF)
                row += acs.get(ch, "+") if c & curses.A_ALTCHARSET else ch
            rows.append(row.rstrip())
        with open(path, "w") as f: f.write("\n".join(rows) + "\n")
        return "wrote %s (%d x %d)" % (path, W, H)

    # ------------------------------------------------------------------ input
    def run_command(self, scr, line):
        line = line.strip()
        if not line: return True
        if not self.history or self.history[-1] != line: self.history.append(line)
        self.hpos = len(self.history)
        word = line.split()[0]
        if word in ("q", "quit", "exit"): return False
        self.log("> " + line)
        if word == "snap":
            self.draw(scr); self.log(self.snap(scr, os.path.expanduser(line.split(None, 1)[1]) if len(line.split()) > 1 else "y1dbg-snap.txt"))
            return True
        out = self.sh.exec(line)
        if out: self.log(out)
        if word in ("c", "until", "n") and out == "running": self.focus = "uart"; self.last_state = "running"
        if word == "console": self.con_scroll = 0
        return True

    def uart_key(self, k):
        if k in (10, 13, curses.KEY_ENTER): self.keys += "\\r"
        elif k in (8, 127, curses.KEY_BACKSPACE): self.keys += "\\x08"
        elif k == 92: self.keys += "\\\\"
        elif 32 <= k < 127: self.keys += chr(k)
        elif 0 < k < 32: self.keys += "\\x%02X" % k

    def main(self, scr):
        curses.curs_set(0); scr.keypad(True); curses.raw(); scr.timeout(20)
        try: curses.use_default_colors()
        except curses.error: pass
        last = 0; dirty = True
        while True:
            now = time.time()
            running = self.state.get("state") == "running"
            if dirty or now - last > (0.1 if running else 0.5):
                try:
                    self.refresh_state()
                except Exception as e:                # noqa: BLE001
                    self.log("error: %s" % e)
                    if not self.sh.emu.alive(): return
                self.draw(scr); last = now; dirty = False
            k = scr.getch()
            if k == -1: continue
            running = self.state.get("state") == "running"
            if k == curses.KEY_RESIZE: dirty = True; continue
            if k in (27, curses.KEY_F6) and running:
                self.log("> pause"); self.log(self.sh.exec("pause")); self.focus = "cmd"; self.last_state = "stopped"; dirty = True; continue
            if k == 9 and running:
                self.focus = "cmd" if self.focus == "uart" else "uart"; dirty = True; continue
            if k == curses.KEY_PPAGE: self.con_scroll += 10; dirty = True; continue
            if k == curses.KEY_NPAGE: self.con_scroll = max(0, self.con_scroll - 10); dirty = True; continue
            if running and self.focus == "uart":
                self.uart_key(k)
                while True:                            # everything typed since the last frame goes in one `key`
                    k = scr.getch()
                    if k == -1 or k in (27, 9, curses.KEY_F6): break
                    self.uart_key(k)
                if k in (27, 9, curses.KEY_F6): curses.ungetch(k)
                dirty = True; continue
            if k == curses.KEY_F5: self.run_command(scr, "c"); dirty = True
            elif k == curses.KEY_F7: self.run_command(scr, "s"); dirty = True
            elif k == curses.KEY_F8: self.run_command(scr, "n"); dirty = True
            elif k in (10, 13, curses.KEY_ENTER):
                if not self.run_command(scr, self.cmd): return
                self.cmd = ""; dirty = True
            elif k in (8, 127, curses.KEY_BACKSPACE): self.cmd = self.cmd[:-1]; dirty = True
            elif k == curses.KEY_UP and self.history:
                self.hpos = max(0, self.hpos - 1); self.cmd = self.history[self.hpos]; dirty = True
            elif k == curses.KEY_DOWN and self.history:
                self.hpos = min(len(self.history), self.hpos + 1)
                self.cmd = self.history[self.hpos] if self.hpos < len(self.history) else ""; dirty = True
            elif k == 3: return                        # Ctrl-C at the command line
            elif 32 <= k < 127: self.cmd += chr(k); dirty = True


def run(shell):
    os.environ.setdefault("ESCDELAY", "25")           # Esc pauses at once, not after curses' default second
    curses.wrapper(TUI(shell).main)

"""The browser debugger: a local web server (standard library only) around the same Shell as the terminal UI.

  python3 software/y1dbg --ui web [--port 8803]      then open http://127.0.0.1:8803/

  GET  /              the page (web/index.html)
  GET  /api/font      the character generator: 64 glyphs x 8 rows of 5 dots (bit 4 the leftmost), from tools/vidsim.py
                      (font_rows, the same font `vidsim.py chargen` writes for the 2732), or a 2732 image (--chargen)
  GET  /api/state?con=N&log=N
                      the status, registers, code at PC, breakpoints and watches, the memory window, the video card
                      (the 2K display RAM, the CRTC registers and the scan geometry: debugger.geometry), and the UART
                      console and the command output when they have grown past N (their totals so far)
  POST /api/cmd       {"cmd": "..."} -> {"out": "..."}   any command of the language (shell.py); q ends the debugger
  POST /api/key       {"text": "..."}                   typed into the UART (as `key`, every byte escaped)
  POST /api/mem       {"addr": "..."}                   the memory window: an address, kept as written, so `sp` or
                                                        `r3` follows the register
  POST /api/quit      ends the debugger (and the emulator with it)

Every command goes through Shell.exec, as in the terminal UI: c, until and n start a run and return at once; the page
polls the state (10 times a second while the machine runs). A lock keeps the HTTP threads' commands to the emulator
one at a time; `waitfor` and `sleep` hold it, so the page waits while they run. Bound to 127.0.0.1 only.
"""
import json, os, signal, sys, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from .debugger import ROOT, geometry, parse_addr
from .emu import EmulatorError
from .shell import console_lines

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8803                                   # ELF's System-5 debugger is on 8802
CODE = 24                                     # instructions in the code panel
CON_WIDTH = 80                                # the UART console's lines, as a terminal shows them


def font(chargen=None):
    """the 64 glyphs for the page: [[8 rows of 5 dots]]; chargen = a 2732 image (dots in D7..D3, code*8 + row)"""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import vidsim                               # noqa: E402 - the one source of the drawn font
    if chargen:
        img = open(chargen, "rb").read()
        glyphs = [[img[c * 8 + r] >> 3 for r in range(8)] for c in range(64)]
        source = os.path.basename(chargen)
    else:
        glyphs = [vidsim.font_rows(c) for c in range(64)]
        source = "tools/vidsim.py (2513-style)"
    return {"dots": vidsim.DOTS, "rows": 8, "glyphs": glyphs, "source": source}


def key_escape(text):
    """text for `key`: every byte that is not a printable non-space character as \\xHH, a backslash doubled"""
    out = []
    for ch in text:
        c = ord(ch) & 0xFF
        out.append("\\\\" if ch == "\\" else ch if 33 <= c < 127 else "\\x%02X" % c)
    return "".join(out)


class App:
    def __init__(self, shell, chargen=None, ran=()):
        self.sh = shell; shell.blocking = False
        self.lock = threading.RLock()
        self.font = font(chargen)
        self.out = ["y1dbg - the YACC1 debugger on y1ucemu (microcode level). 'help' for commands, F5 or Run to run."]
        self.out_total = len(self.out)        # lines ever logged (the page asks for the tail when this grows)
        for t in ran: self.log(t)             # what -c / --script ran before the page opened
        self.mem_expr = "0F00"                # the monitor's variables
        self.quit = None                      # set by serve(): ends the server

    def log(self, text):
        lines = str(text).splitlines() or [""]
        self.out.extend(lines); self.out_total += len(lines)
        del self.out[:-500]

    def cmd(self, line):
        line = line.strip()
        if not line: return ""
        word = line.split()[0].lower()
        if word in ("q", "quit", "exit"):
            self.quit(); return "the debugger has ended"
        if word == "snap": return "snap is the terminal UI's (the browser: save the page or a screenshot)"
        self.log("> " + line)
        with self.lock:
            out = self.sh.exec(line)
        if out: self.log(out)
        return out

    def key(self, text):
        if not text: return {"queued": 0}
        with self.lock:
            r = self.sh.emu.ok("key " + key_escape(text))
        return {"queued": r["queued"], "pending": r["pending"]}

    def set_mem(self, expr):
        with self.lock:
            self.sh.addr(expr)                  # ValueError if it is not an address
        self.mem_expr = expr.strip()

    def state(self, con_seen=-1, out_seen=-1):
        with self.lock:
            sh = self.sh
            snap = sh.snapshot(code=CODE)
            try:
                mem, err = parse_addr(self.mem_expr, sh.syms, snap["regs"]), ""
            except ValueError as e:
                mem, err = 0, str(e)
            snap["mem"] = sh.read(mem, 256)
            con_total = sh.console_total()
            con = console_lines(sh.con, CON_WIDTH)[-1000:] if con_total != con_seen else None
        if snap["note"]: self.log(snap["note"])
        r, v, syms = snap["regs"], snap["video"], sh.syms
        status = {k: r[k] for k in ("state", "reason", "pc", "step", "instr", "steps", "clocks")}
        status["sym"] = syms.name(r["pc"]) or ""
        return {
            "status": status,
            "regs": {k: r[k] for k in ("r", "acc", "tmp0", "tmp1", "carry", "shift_out", "sreg", "ir", "operand", "branch",
                                       "intvec", "cond", "force_rom", "int_en", "out_led", "fights", "weak") if k in r},
            "code": [{"a": a, "b": bs.hex(" "), "t": t, "l": syms.name(a) or "", "bp": a in snap["breaks"]}
                     for a, bs, t in snap["code"]],
            "breaks": [{"a": a, "s": syms.name(a) or ""} for a in snap["breaks"]],
            "watches": [{"a": a, "k": {1: "r", 2: "w", 3: "rw"}[k], "s": syms.name(a) or ""} for a, k in snap["watches"]],
            "mem": {"expr": self.mem_expr, "addr": mem, "hex": snap["mem"].hex(), "error": err},
            "video": {"absent": v.get("absent", 0), "ram": v["ram"], "regs": v["regs"], "written": v["written"],
                      "sel": v["sel"], "geom": geometry(v)},
            "console": {"total": con_total, "lines": con},
            "out": {"total": self.out_total, "lines": self.out[-500:] if self.out_total != out_seen else None},
        }


def serve(shell, port=PORT, chargen=None, announce=print, ran=()):
    app = App(shell, chargen, ran)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _send(self, body, ctype, code=200):
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(json.dumps(obj).encode(), "application/json", code)

        def _guard(self, f):
            try:
                return f()
            except EmulatorError as e:
                if not shell.emu.alive(): app.quit()
                self._json({"error": str(e)}, 503)
            except (ValueError, IndexError, KeyError) as e:
                self._json({"error": str(e)}, 400)

        def do_GET(self):
            u = urlparse(self.path); q = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                self._send(open(os.path.join(HERE, "web", "index.html"), "rb").read(), "text/html; charset=utf-8")
            elif u.path == "/api/font":
                self._json(app.font)
            elif u.path == "/api/state":
                self._guard(lambda: self._json(app.state(int(q.get("con", ["-1"])[0]), int(q.get("log", ["-1"])[0]))))
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/cmd":
                self._guard(lambda: self._json({"out": app.cmd(body.get("cmd", ""))}))
            elif self.path == "/api/key":
                self._guard(lambda: self._json(app.key(body.get("text", ""))))
            elif self.path == "/api/mem":
                self._guard(lambda: (app.set_mem(body.get("addr", "0")), self._json({"ok": True})))
            elif self.path == "/api/quit":
                self._json({"ok": True}); app.quit()
            else:
                self._json({"error": "not found"}, 404)

    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request, client_address):
            if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)): return   # the page dropped a poll
            super().handle_error(request, client_address)

    try:
        srv = Server(("127.0.0.1", port), H)
    except OSError as e:
        raise SystemExit("y1dbg: port %d is busy (%s): is a debugger already running? --port N picks another" % (port, e.strerror))
    app.quit = lambda: threading.Thread(target=srv.shutdown, daemon=True).start()
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *a: app.quit())
    announce("y1dbg: the browser debugger is on http://127.0.0.1:%d/  (Ctrl-C, or Quit on the page, ends it)" % srv.server_address[1])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()

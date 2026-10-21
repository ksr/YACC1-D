#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/y1dbg/run.py - the debugger: y1ucemu's debug server (-D) and software/y1dbg's command language (2026-10-11).

  run.py [name ...] [-v]      run the cases (all by default); -v prints each command's output

Each case starts y1ucemu -D with the tree's ROM through software/y1dbg (no curses, except the `tui` case, which runs
the terminal UI in a pseudo-terminal) and checks:

  break     a breakpoint at the monitor's command loop (cmdloop, from monitor.lst) stops there; the registers are sane
            (SP in the monitor's stack, FORCE-ROM released, at an instruction boundary); s, us, d and trace
  video     the monitor's video driver (V I, V M1, then the help text mirrored to the screen): `screen` shows the text
            with the CRTC's 80 x 24 and a cursor; a byte poked into the display RAM shows as its glyph, bit 7 inverse
  basic     `key` drives the monitor into BASIC (I, a program line with CR, RUN): the console shows the result
  pause     a BASIC loop runs; status, regs, video and console answer during the run; pause stops it at an
            instruction boundary in the ROM; a write watch on the loop's variable stops it again
  reset     reset: PC $F000, counts 0, FORCE-ROM set
  cli       python3 software/y1dbg -c "...": the commands' output, exit 0, and no emulator left running
  gone      the emulator exits when the debugger closes, and when the connection just drops in the middle of a run
  tui       the curses UI in a pty: the screen pane shows what BASIC printed (snap), q quits, nothing left running
  web       the browser debugger (--ui web --port 0, driven with urllib, no browser): the page, the font (tools/vidsim.py's
            glyphs), a breakpoint by command, keys typed into the UART (V I, V M1, H) appearing in the state's video RAM
            with the CRTC's geometry and cursor and in the console, pause, the memory window following `sp`, quit
  webstop   the web server ends cleanly, the emulator with it: SIGTERM during a run, SIGINT, and `q` typed as a command
  gate      --video-rev passes the gate-level card through (y1ucemu -G): with v1.0 the monitor's VR0E 12 / VR0E reads 12
            back and `video` says "v1.0 at gate level, 0 bus events"; with v1.0-no-rs (no RS fix) R14 is never written
            and `video` counts the undriven reads; an unknown revision ends y1dbg with an error; nothing left running
"""
import os, re, sys, time, socket, subprocess, select, struct, json, signal, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "software"))
from y1dbg.emu import Emulator                      # noqa: E402
from y1dbg.debugger import Symbols, screen          # noqa: E402
from y1dbg.shell import Shell                       # noqa: E402
from y1dbg.web import key_escape                    # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "tools"))
import vidsim                                       # noqa: E402

VERBOSE = "-v" in sys.argv
MON = os.path.join(ROOT, "firmware/monitor/monitor.lst")
BAS = os.path.join(ROOT, "firmware/basic/basic.lst")
CMDLOOP = int(re.search(r"^([0-9a-f]{4})h: CMDLOOP\b", open(MON).read(), re.M).group(1), 16)
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-7s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def start():
    syms = Symbols(); syms.load(MON); syms.load(BAS)
    return Shell(Emulator(["-m"]), syms, timeout=30)


def x(sh, line):
    out = sh.exec(line)
    if VERBOSE: print("> %s\n%s" % (line, out))
    return out


def emulators():
    r = subprocess.run(["pgrep", "-f", "ucemu/y1ucemu -D"], capture_output=True, text=True)
    return set(r.stdout.split())


def case_break():
    sh = start()
    try:
        out = x(sh, "b cmdloop")
        check("break", out.startswith("breakpoint %04X <cmdloop>" % CMDLOOP), out)
        out = x(sh, "c")
        r = sh.regs()
        check("break", out.startswith("breakpoint %04X" % CMDLOOP) and r["pc"] == CMDLOOP and r["state"] == "stopped", out[:200])
        ok = 0x0C00 <= r["r"][1] <= 0x0EFF and r["force_rom"] == 0 and r["step"] == 0 and r["instr"] > 1000 and \
            r["clocks"] > r["steps"] > r["instr"] and r["r"][0] == CMDLOOP and r["fights"] == 0
        check("break", ok, "regs: %r" % r)
        d = x(sh, "d")
        check("break", "        cmdloop:" in d and re.search(r"^>%04X  1f .. ..  MVIW R7,0[0-9A-F]{4}H" % CMDLOOP, d, re.M) is not None, d[:300])
        i0 = r["instr"]
        x(sh, "s"); r1 = sh.regs()
        x(sh, "us 5"); r2 = sh.regs()
        check("break", r1["instr"] == i0 + 1 and r1["step"] == 0 and r1["pc"] == CMDLOOP + 3 and r2["steps"] == r1["steps"] + 5,
              "s/us: %r %r" % (r1, r2))
        x(sh, "s 3")                                    # finish the instruction ustep left half done, and two more
        t = x(sh, "trace 4").splitlines()
        check("break", len(t) == 4 and t[0].startswith("%04X MVIW R7" % CMDLOOP), "\n".join(t))
        out = x(sh, "bl")
        check("break", out.startswith("%04X <cmdloop>" % CMDLOOP), out)
    finally:
        sh.emu.close()


def case_video():
    sh = start()
    try:
        x(sh, "until cmdloop")
        x(sh, "key VI\\nVM1\\nH\\n")
        out = x(sh, "waitfor INTEL-HEX LOAD")
        sc = screen(sh.emu.ok("video"))
        text = x(sh, "screen")
        ok = out.startswith("found") and sc["cols"] == 80 and sc["rows"] == 24 and "CRTC" in sc["source"] and \
            any("INTEL-HEX LOAD" in l for l in sc["lines"]) and sc["cursor"] is not None and "INTEL-HEX LOAD" in text
        check("video", ok, "%s\n%s" % (out, text))
        x(sh, "poke D000 19 80 99 21")                  # Y, @ inverse, Y inverse, !
        sc = screen(sh.emu.ok("video"))
        check("video", sc["lines"][0][:4] == "Y@Y!" and sc["inverse"][0][:4] == [False, True, True, False],
              "%r %r" % (sc["lines"][0][:4], sc["inverse"][0][:4]))
        v = x(sh, "video")
        check("video", v.startswith("CRTC 74 50 5E") and " 18 " in v, v)
    finally:
        sh.emu.close()


def case_basic():
    sh = start()
    try:
        x(sh, "until cmdloop")
        x(sh, "key I")
        a = x(sh, "waitfor >>")
        x(sh, "key 10 print 6*7\\r")
        x(sh, "key run\\r")
        b = x(sh, "waitfor 42\\n")
        con = x(sh, "console")
        check("basic", a.startswith("found") and b.startswith("found") and ">>run" in con and "\n42\n" in con, "%s %s\n%s" % (a, b, con))
    finally:
        sh.emu.close()


def case_pause():
    sh = start()
    try:
        x(sh, "until cmdloop")
        x(sh, "key I"); x(sh, "waitfor >>")
        x(sh, "key 10 c=c+1\\r20 goto 10\\rrun\\r")
        sh.emu.ok("run"); time.sleep(0.6)
        e = sh.emu
        st = e.ok("status"); r = e.ok("regs"); v = e.ok("video"); c = e.ok("console")
        live = st["state"] == "running" and r["state"] == "running" and len(v["ram"]) == 4096 and "ok" in c
        p = e.ok("pause"); r2 = sh.regs()
        check("pause", live and p["state"] == "stopped" and p["reason"] == "paused" and r2["step"] == 0 and
              r2["pc"] >= 0xE000 and r2["instr"] > r["instr"] > 0, "%r\n%r" % (st, r2))
        mem = sh.read(0x0100, 0x40)
        x(sh, "w w 0104")                               # BASIC's variables from $0100, two bytes each: C is the third
        out = x(sh, "c")
        r3 = sh.regs()
        check("pause", out.startswith("watch: write 0104 = ") and r3["step"] == 0 and r3["state"] == "stopped",
              "%s\n%s" % (out, mem.hex(" ")))
        out = x(sh, "wl")
        check("pause", out.startswith("w  0104"), out)
        x(sh, "wd all")
    finally:
        sh.emu.close()


def case_reset():
    sh = start()
    try:
        x(sh, "s 100")
        x(sh, "reset")
        r = sh.regs()
        check("reset", r["pc"] == 0xF000 and r["r"][0] == 0 and r["instr"] == 0 and r["force_rom"] == 1 and r["reason"] == "reset", "%r" % r)
        out = x(sh, "s 2")
        check("reset", "MVIW R1,0EFFH" in x(sh, "trace 2") and sh.regs()["pc"] == 0xF006, out)
    finally:
        sh.emu.close()


def case_cli():
    before = emulators()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "software/y1dbg"), "-c", "b cmdloop; c; r; key H\\n; waitfor >; console"],
                       capture_output=True, text=True, timeout=120)
    if VERBOSE: print(r.stdout + r.stderr)
    ok = r.returncode == 0 and "breakpoint %04X" % CMDLOOP in r.stdout and "PC=%04X <cmdloop>" % CMDLOOP in r.stdout and \
        "INTEL-HEX LOAD" in r.stdout
    check("cli", ok, r.stdout[-500:] + r.stderr[-500:])
    time.sleep(0.2)
    check("cli", emulators() <= before, "left running: %s" % (emulators() - before))


def case_gone():
    sh = start(); e = sh.emu; port = e.port
    e.close()
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close(); refused = False
    except OSError:
        refused = True
    check("gone", e.p.poll() is not None and refused, "returncode %r, port %d %s" % (e.p.poll(), port, "refused" if refused else "open"))
    sh = start(); e = sh.emu
    e.ok("run"); time.sleep(0.2)
    e.rf.close(); e.sock.close()                        # the front end vanishes in the middle of a run
    try: e.p.wait(2); gone = True
    except subprocess.TimeoutExpired: gone = False; e.p.kill(); e.p.wait()
    check("gone", gone and e.p.returncode == 0, "still running after the connection dropped")


def case_tui():
    import pty, fcntl, termios
    before = emulators()
    snap = os.path.join(HERE, "build", "tui.snap.txt")
    os.makedirs(os.path.dirname(snap), exist_ok=True)
    if os.path.exists(snap): os.unlink(snap)
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.execv(sys.executable, [sys.executable, os.path.join(ROOT, "software/y1dbg")])
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 140, 0, 0))

    def drain(t):
        end = time.time() + t
        while time.time() < end:
            if select.select([fd], [], [], 0.05)[0]:
                try: os.read(fd, 65536)
                except OSError: return

    def send(s, t=0.4):
        os.write(fd, s.encode()); drain(t)

    drain(2)
    send("until cmdloop\r", 2)
    send("key VI\\nVM1\\nI10 print \"hello, screen\"\\nrun\\n\r")
    send("c\r", 3)
    send("\x1b", 0.6)                                   # Esc: pause
    send("snap %s\r" % snap, 0.6)
    send("q\r", 0)
    end = time.time() + 10; status = None
    while time.time() < end:
        drain(0.1)
        p, status = os.waitpid(pid, os.WNOHANG)
        if p: break
    else:
        os.kill(pid, 9); os.waitpid(pid, 0)
    text = open(snap).read() if os.path.exists(snap) else ""
    if VERBOSE: print(text)
    rows = text.splitlines()
    pane = [l[1:81] for l in rows[1:25]] if len(rows) > 25 else []
    ok = status == 0 and any("HELLO, SCREEN" == l.strip() for l in pane) and "registers" in text and "console (UART)" in text and \
        "stopped: paused" in text
    check("tui", ok, "exit %r\n%s" % (status, text))
    time.sleep(0.2)
    check("tui", emulators() <= before, "left running: %s" % (emulators() - before))


def web_start():
    """python3 software/y1dbg --ui web --port 0 -> (process, base URL)"""
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, "software/y1dbg"), "--ui", "web", "--port", "0"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    line = p.stdout.readline()
    m = re.search(r"http://127\.0\.0\.1:(\d+)/", line)
    if not m:
        p.kill(); p.wait(); raise RuntimeError("no URL from --ui web: %r" % line)
    return p, "http://127.0.0.1:%s" % m.group(1)


def http(base, path, body=None):
    """GET (body None) or POST JSON -> (status, parsed JSON or text)"""
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read().decode(); code = r.status; ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        data = e.read().decode(); code = e.code; ctype = e.headers.get("Content-Type", "")
    return code, json.loads(data) if ctype.startswith("application/json") else data


def web_until(base, pred, secs=30):
    """poll /api/state until pred(state) (as the page does), at most secs; -> the last state"""
    end = time.time() + secs
    while True:
        _, st = http(base, "/api/state")
        if pred(st) or time.time() > end: return st
        time.sleep(0.1)


def web_gone(p, secs=10):
    try: p.wait(secs); return True
    except subprocess.TimeoutExpired: p.kill(); p.wait(); return False


def case_web():
    before = emulators()
    p, base = web_start()
    try:
        code, page = http(base, "/")
        check("web", code == 200 and "<canvas" in page and "/api/state" in page, "page %d" % code)
        code, f = http(base, "/api/font")
        check("web", code == 200 and f["dots"] == 6 and len(f["glyphs"]) == 64 and
              all(f["glyphs"][c] == vidsim.font_rows(c) for c in range(64)), "font %d" % code)
        check("web", key_escape("a b\\\r~") == "a\\x20b\\\\\\x0D~", key_escape("a b\\\r~"))
        _, r = http(base, "/api/cmd", {"cmd": "b cmdloop"})
        _, r2 = http(base, "/api/cmd", {"cmd": "c"})
        st = web_until(base, lambda s: s["status"]["state"] != "running")
        ok = r["out"].startswith("breakpoint %04X <cmdloop>" % CMDLOOP) and r2["out"] == "running" and \
            st["status"]["pc"] == CMDLOOP and st["status"]["reason"] == "breakpoint %04X" % CMDLOOP and \
            st["code"][0]["a"] == CMDLOOP and st["code"][0]["bp"] and st["code"][0]["l"] == "cmdloop" and \
            st["breaks"] == [{"a": CMDLOOP, "s": "cmdloop"}] and any(l.startswith("breakpoint %04X" % CMDLOOP) for l in st["out"]["lines"])
        check("web", ok, json.dumps(st["status"]) + " " + json.dumps(st["code"][:2]))
        http(base, "/api/cmd", {"cmd": "bd all"})
        _, k = http(base, "/api/key", {"text": "VI\rVM1\rH"})
        http(base, "/api/cmd", {"cmd": "c"})
        st = web_until(base, lambda s: s["console"]["lines"] and any("INTEL-HEX LOAD" in l for l in s["console"]["lines"]))
        v = st["video"]; g = v["geom"]; sc = screen(v)
        ok = k["queued"] == 8 and st["status"]["state"] == "running" and g["crtc"] and g["cols"] == 80 and g["rows"] == 24 and \
            g["lines"] == 8 and g["cursor"] is not None and g["cursor"]["blink"] == 32 and len(v["ram"]) == 4096 and \
            any("INTEL-HEX LOAD" in l for l in sc["lines"]) and v["regs"][:3] == [0x74, 0x50, 0x5E]
        check("web", ok, "%r %r" % (k, g))
        _, again = http(base, "/api/state?con=%d&log=%d" % (st["console"]["total"], st["out"]["total"]))
        check("web", again["console"]["lines"] is None and again["out"]["lines"] is None, "unchanged console/log resent")
        _, r = http(base, "/api/cmd", {"cmd": "pause"})
        _, regs = http(base, "/api/cmd", {"cmd": "r"})
        code, _ = http(base, "/api/mem", {"addr": "sp"})
        code2, bad = http(base, "/api/mem", {"addr": "nosuchname"})
        st = web_until(base, lambda s: True)
        ok = r["out"].startswith("paused") and regs["out"].startswith("PC=") and code == 200 and code2 == 400 and \
            st["status"]["state"] == "stopped" and st["mem"]["expr"] == "sp" and st["mem"]["addr"] == st["regs"]["r"][1] and \
            len(st["mem"]["hex"]) == 512
        check("web", ok, "%r %r %d %r %r" % (r, regs["out"][:40], code2, bad, st["mem"]["expr"]))
        code, _ = http(base, "/api/quit", {})
        check("web", code == 200 and web_gone(p) and p.returncode == 0, "quit: exit %r" % p.returncode)
    finally:
        if p.poll() is None: p.kill(); p.wait()
    time.sleep(0.2)
    check("web", emulators() <= before, "left running: %s" % (emulators() - before))


def case_webstop():
    before = emulators()
    for how in ("SIGTERM", "SIGINT", "q"):
        p, base = web_start()
        try:
            if how == "SIGTERM":
                http(base, "/api/cmd", {"cmd": "c"}); time.sleep(0.3)
                p.send_signal(signal.SIGTERM)
            elif how == "SIGINT":
                p.send_signal(signal.SIGINT)
            else:
                http(base, "/api/cmd", {"cmd": "q"})
            gone = web_gone(p)
            check("webstop", gone and p.returncode == 0, "%s: exit %r" % (how, p.returncode))
        finally:
            if p.poll() is None: p.kill(); p.wait()
    time.sleep(0.2)
    check("webstop", emulators() <= before, "left running: %s" % (emulators() - before))


def case_gate():
    before = emulators()
    cmds = "until cmdloop; key VR0E 12\\nVR0E\\nVS\\n; waitfor MIRROR 00  CRTC 60; video"
    got = {}
    for rev in ("v1.0", "v1.0-no-rs"):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "software/y1dbg"), "--video-rev", rev, "-c", cmds],
                           capture_output=True, text=True, timeout=120)
        if VERBOSE: print(r.stdout + r.stderr)
        got[rev] = (r.returncode, re.search(r"^CRTC .*$", r.stdout, re.M))
    ok = got["v1.0"][0] == 0 and got["v1.0"][1] and got["v1.0"][1].group(0).split()[15] == "12" and \
        "card: v1.0 at gate level, 0 bus events" in got["v1.0"][1].group(0)
    check("gate", bool(ok), "%r" % got["v1.0"][1])
    m = got["v1.0-no-rs"][1]
    ok = got["v1.0-no-rs"][0] == 0 and m and m.group(0).split()[15] == "--" and re.search(r"card: v1\.0-no-rs at gate level, [1-9]\d* bus events", m.group(0))
    check("gate", bool(ok), "%r" % m)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "software/y1dbg"), "--video-rev", "v9", "-c", "r"], capture_output=True, text=True, timeout=60)
    check("gate", r.returncode == 2 and "-G list" in r.stderr, r.stderr)
    time.sleep(0.2)
    check("gate", emulators() <= before, "left running: %s" % (emulators() - before))


CASES = {"break": case_break, "video": case_video, "basic": case_basic, "pause": case_pause, "reset": case_reset,
         "cli": case_cli, "gone": case_gone, "tui": case_tui,
         "web": case_web, "webstop": case_webstop, "gate": case_gate}
names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(CASES)
for n in names:
    CASES[n]()
print("%d failed" % fails)
sys.exit(1 if fails else 0)

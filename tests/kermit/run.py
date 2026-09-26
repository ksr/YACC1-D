#!/usr/bin/env python3
"""tests/kermit/run.py - /BIN/KERMIT against tools/y1kermit.py on both emulators, through a pseudo-terminal
(2026-09-26).

  run.py [--emu int|uc] [--keep] [--only NAME...]      the transfer sessions (make check runs them all)
  run.py --calib                                        the timing claims of os/kermit_io.asm on the microcode emulator

Each emulator boots Y1/OS from a copy of os/disk.img (-c) with its console on pipes; a pump thread copies the
emulator's output into a transcript and, while tools/y1kermit.py runs, onto the master side of a pty whose slave is
y1kermit's "serial port" (as tests/monload does for monload.py), and copies what y1kermit writes back into the
emulator's input. The script types the shell commands straight into the emulator's input and waits for the prompt.
On the instruction-level emulator the program watch (-S) and the PC histogram (-P) give each kermit run's
instructions, less the ones spent waiting in kermit_io's poll loops: that is the throughput at 1 MHz.

Sessions (each checks the files byte for byte on the host: y1kermit's copies, and the disk image through
tools/p8xfs.py get; fsck at the end):
  files     kermit -r: a text file, all 256 byte values, a 70K file (over 64K: 24-bit sizes), a file of long runs
            (repeat counts), an empty file, a lower-case long name (cleaned to 12 upper-case characters) - one
            session; then kermit -s sends them all back (a glob)
  options   block checks 1 and 2, 8th-bit prefixing both ways, text mode both ways (CR LF on the line, LF on disk),
            no attributes, -n (a second copy gets a new name), -a (load/exec address), -b 1 on the sender
  errors    a damaged packet each way (NAK, resend), a packet never sent (kermit -r times out and NAKs), an ACK
            never sent (kermit -s times out and sends again), three Ctrl-Cs cancel a waiting kermit -r
  server    kermit -x: SEND, GET (a glob, and a name in lower case), an unknown GET, FINISH
"""
import os, sys, pty, tty, re, time, shutil, select, subprocess, threading, tempfile, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(HERE, "build")
YK = os.path.join(ROOT, "tools/y1kermit.py")
FS = os.path.join(ROOT, "tools/p8xfs.py")
EMUS = {"int": os.path.join(ROOT, "software/emulator/emulator"), "uc": os.path.join(ROOT, "software/ucemu/y1ucemu")}
MON_EXIT = int(re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", open(os.path.join(ROOT, "firmware/monitor/monitor.lst")).read(), re.M).group(1), 16)
PROMPT = b"/K> "


def files():
    """the host files the sessions send: name -> bytes"""
    rnd = random.Random(1926)
    f = {}
    f["TEXT.TXT"] = open(os.path.join(ROOT, "os/man/kermit"), "rb").read()
    f["ALL256.BIN"] = bytes(range(256)) + bytes(range(255, -1, -1)) + bytes((i * 37) & 255 for i in range(512))
    f["BIG.BIN"] = bytes(rnd.getrandbits(8) for _ in range(70 * 1024 + 13))
    f["RUNS.BIN"] = (b"\0" * 3000 + b"A" * 95 + b"~" * 200 + b"#" * 94 + b"&" * 3 + b"\xff" * 500 + b"xy" * 40 +
                     bytes([13, 10]) * 30 + b"\x80" * 2 + b"z" * 1)
    f["EMPTY.DAT"] = b""
    return f


class Target:
    """an emulator running Y1/OS, its console on pipes, a pty for y1kermit"""
    def __init__(self, tag, img, histo=None):
        self.tag = tag
        self.m, self.s = pty.openpty(); tty.setraw(self.m); tty.setraw(self.s)
        cmd = [EMUS[tag], "-x", "-m", "-c", img]
        if tag == "int": cmd += ["-l", "4000000000"] + (["-P", histo] if histo else [])
        else: cmd += ["-l", "90000000000", "-E", "%X" % MON_EXIT]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.out = bytearray(); self.fwd = False; self.lock = threading.Lock(); self.stop = False
        self.err = bytearray()
        threading.Thread(target=self.pump, daemon=True).start()
        threading.Thread(target=self.errpump, daemon=True).start()

    def pump(self):
        fo = self.p.stdout.fileno()
        while not self.stop:
            r, _, _ = select.select([self.m, fo], [], [], 0.05)
            if self.m in r:
                b = os.read(self.m, 1024)
                if b:
                    with self.lock: self.p.stdin.write(b); self.p.stdin.flush()
            if fo in r:
                b = os.read(fo, 4096)
                if not b: break
                self.out += b
                if self.fwd: os.write(self.m, b)

    def errpump(self):
        for line in self.p.stderr: self.err += line

    def type(self, text):
        with self.lock: self.p.stdin.write(text.encode("latin1")); self.p.stdin.flush()

    def wait(self, what, since, timeout=600):
        end = time.time() + timeout
        while time.time() < end:
            i = self.out.find(what, since)
            if i >= 0: return i + len(what)
            if self.p.poll() is not None: break
            time.sleep(0.02)
        raise RuntimeError("%s: no %r in the output; its end: %r" % (self.tag, what, bytes(self.out[-400:])))

    def cmd(self, line, timeout=900):
        """type a shell line, wait for the next prompt; returns what the command printed"""
        mark = len(self.out)
        self.type(line + "\n")
        j = self.wait(PROMPT, mark, timeout)
        return bytes(self.out[mark:j]).decode("latin1")

    def kermit(self, line, yargs, ready=b"kermit: ", timeout=900):
        """type a kermit command, run y1kermit against it, wait for the prompt; -> (y1kermit rc, its output, what
        the target printed)"""
        mark = len(self.out)
        self.type(line + "\n")
        self.wait(ready, mark, 120)
        self.fwd = True
        r = subprocess.run([sys.executable, YK] + yargs + ["--port", os.ttyname(self.s)], capture_output=True,
                           text=True, timeout=timeout)
        j = self.wait(PROMPT, mark, timeout)
        self.fwd = False
        return r.returncode, r.stdout + r.stderr, bytes(self.out[mark:j]).decode("latin1")

    def close(self):
        self.type("exit\n0\n")
        try: self.p.wait(timeout=120)
        except subprocess.TimeoutExpired: self.p.kill()
        self.stop = True
        os.close(self.m); os.close(self.s)


def p8get(img, path):
    tmp = img + ".get"
    r = subprocess.run([sys.executable, FS, "get", img, path, "--out", tmp], capture_output=True, text=True)
    if r.returncode: return None
    b = open(tmp, "rb").read(); os.remove(tmp); return b


class Run:
    def __init__(self, tag, keep):
        self.tag, self.keep, self.failed, self.n = tag, keep, 0, 0
        self.dir = os.path.join(BUILD, tag); shutil.rmtree(self.dir, ignore_errors=True); os.makedirs(self.dir)
        self.src = os.path.join(self.dir, "src"); os.makedirs(self.src)
        self.f = files()
        for n, b in self.f.items(): open(os.path.join(self.src, n), "wb").write(b)
        open(os.path.join(self.src, "lower case name.text"), "wb").write(b"a lower-case name\n")
        self.img = os.path.join(self.dir, "disk.img")
        shutil.copy(os.path.join(ROOT, "os/disk.img"), self.img)
        self.histo = os.path.join(self.dir, "pc.txt") if tag == "int" else None
        self.t = Target(tag, self.img, self.histo)
        self.t.wait(b"RUN TEST CODE", 0, 60)
        self.t.type("O\n")
        self.t.wait(b"/> ", 0, 300)
        mark = len(self.t.out); self.t.type("mkdir /K\ncd /K\n"); self.t.wait(PROMPT, mark, 300)
        self.progs = 0                          # /BIN programs run so far (the -S / -P numbering)

    def check(self, name, ok, detail=""):
        self.n += 1
        print("%-4s %-44s %s" % (self.tag, name, "PASS" if ok else "FAIL " + detail), flush=True)
        if not ok: self.failed += 1

    def src_(self, n): return os.path.join(self.src, n)

    def kermit(self, line, yargs, **kw):
        self.progs += 1
        return self.t.kermit(line, yargs, **kw)

    def ondisk(self, path, want):
        got = p8get(self.img, path)
        return got == want, "%s: %s bytes on the disk, want %d" % (path, None if got is None else len(got), len(want))

    # ---- sessions ----
    def s_files(self):
        names = ["TEXT.TXT", "ALL256.BIN", "BIG.BIN", "RUNS.BIN", "EMPTY.DAT"]
        rc, yo, to = self.kermit("kermit -r", ["send"] + [self.src_(n) for n in names] + [self.src_("lower case name.text"),
                                 "-q", "--time", "10"])
        self.recv_prog = self.progs
        self.check("receive 6 files in one session", rc == 0 and "6 files received" in to, yo + to)
        self.check("names: the long lower-case one cleaned", "LOWER_CA.TEX" in to, to)
        out = os.path.join(self.dir, "back"); os.makedirs(out)
        rc, yo, to = self.kermit("kermit -s *", ["receive", out, "-q"])
        self.send_prog = self.progs
        ok = rc == 0 and all(open(os.path.join(out, n), "rb").read() == self.f[n] for n in names)
        self.check("send them back (kermit -s *)", ok and "6 files sent" in to, yo + to)
        self.check("the renamed one came back", os.path.exists(os.path.join(out, "LOWER_CA.TEX")), str(os.listdir(out)))
        self.disk_checks = [("/K/" + n, self.f[n]) for n in names] + [("/K/LOWER_CA.TEX", b"a lower-case name\n")]

    def s_options(self):
        a = self.f["ALL256.BIN"]; r = self.f["RUNS.BIN"]; txt = self.f["TEXT.TXT"]
        open(self.src_("B1.BIN"), "wb").write(a); open(self.src_("B2.BIN"), "wb").write(r)
        open(self.src_("E8.BIN"), "wb").write(a + r)
        open(self.src_("T.TXT"), "wb").write(txt); open(self.src_("NA.BIN"), "wb").write(a)
        for fn, ya, what in (("B1.BIN", ["--check", "1"], "block check 1"), ("B2.BIN", ["--check", "2"], "block check 2"),
                             ("E8.BIN", ["--ebq"], "8th-bit prefixing (sender asks)"), ("T.TXT", ["--text"], "text mode in (CR LF -> LF)"),
                             ("NA.BIN", ["--noattr", "--norpt"], "no attributes, no repeat counts")):
            rc, yo, to = self.kermit("kermit -r", ["send", self.src_(fn), "-q"] + ya)
            ok, d = self.ondisk("/K/" + fn, open(self.src_(fn), "rb").read())
            self.check("receive, " + what, rc == 0 and ok, d + yo + to)
        out = os.path.join(self.dir, "opt"); os.makedirs(out)
        for line, ya, fn, what in (("kermit -s E8.BIN", ["--ebq"], "E8.BIN", "send, 8th-bit prefixing (receiver asks)"),
                                   ("kermit -s -T T.TXT", [], "T.TXT", "send, text mode (LF -> CR LF)"),
                                   ("kermit -s -b 1 B2.BIN", ["--check", "1"], "B2.BIN", "send, block check 1"),
                                   ("kermit -s -b 2 B1.BIN", ["--check", "2"], "B1.BIN", "send, block check 2")):
            rc, yo, to = self.kermit(line, ["receive", out, "-q"] + ya)
            got = open(os.path.join(out, fn), "rb").read() if os.path.exists(os.path.join(out, fn)) else None
            self.check(what, rc == 0 and got == open(self.src_(fn), "rb").read(), yo + to)
        rc, yo, to = self.kermit("kermit -r -n -a 6000", ["send", self.src_("B1.BIN"), "-q"])
        ok, d = self.ondisk("/K/B1.BIN~1", a)
        self.check("-n: an existing name gets ~1", rc == 0 and ok and "B1.BIN~1" in to, d + yo + to)
        ls = subprocess.run([sys.executable, FS, "ls", self.img, "/K"], capture_output=True, text=True).stdout
        m = re.search(r"B1\.BIN~1.*", ls)
        self.check("-a 6000: the load address", bool(m) and "6000" in m.group(0).upper(), ls)

    def s_errors(self):
        a = self.f["ALL256.BIN"] * 4
        open(self.src_("ERR1.BIN"), "wb").write(a)
        rc, yo, to = self.kermit("kermit -r", ["send", self.src_("ERR1.BIN"), "--corrupt", "4"])
        ok, d = self.ondisk("/K/ERR1.BIN", a)
        self.check("receive: a damaged packet is NAKed, resent", rc == 0 and ok and "NAKs 1" in yo, d + yo + to)
        open(self.src_("ERR2.BIN"), "wb").write(a[::-1])
        t0 = time.time()
        rc, yo, to = self.kermit("kermit -r", ["send", self.src_("ERR2.BIN"), "--drop", "5", "--time", "2"])
        ok, d = self.ondisk("/K/ERR2.BIN", a[::-1])
        self.check("receive: kermit times out, NAKs (%.1f s)" % (time.time() - t0), rc == 0 and ok and "NAKs 1" in yo, d + yo + to)
        out = os.path.join(self.dir, "err"); os.makedirs(out)
        rc, yo, to = self.kermit("kermit -s ERR1.BIN", ["receive", out, "--nak", "4"])
        self.check("send: a NAKed packet is sent again", rc == 0 and open(os.path.join(out, "ERR1.BIN"), "rb").read() == a, yo + to)
        os.remove(os.path.join(out, "ERR1.BIN"))
        t0 = time.time()
        rc, yo, to = self.kermit("kermit -s ERR1.BIN", ["receive", out, "--mute", "5", "--time", "2"])
        self.check("send: kermit times out, sends again (%.1f s)" % (time.time() - t0),
                   rc == 0 and open(os.path.join(out, "ERR1.BIN"), "rb").read() == a and "repeats 1" in yo, yo + to)
        rc, yo, to = self.kermit("kermit -s ERR1.BIN", ["receive", out, "--corrupt", "3"])
        self.check("send: a damaged ACK, the packet again", rc == 0 and open(os.path.join(out, "ERR1.BIN"), "rb").read() == a, yo + to)
        mark = len(self.t.out)
        self.t.type("kermit -r\n"); self.t.wait(b"kermit: ready", mark, 60)
        self.t.type("\x03\x03\x03")
        j = self.t.wait(PROMPT, mark, 300); self.progs += 1
        to = bytes(self.t.out[mark:j]).decode("latin1")
        self.check("three Ctrl-Cs cancel kermit -r", "cancelled" in to, to)

    def s_server(self):
        out = os.path.join(self.dir, "srv"); os.makedirs(out)
        mark = len(self.t.out)
        self.t.type("kermit -x\n"); self.t.wait(b"kermit: server", mark, 60); self.progs += 1
        self.t.fwd = True
        def yk(*args):
            r = subprocess.run([sys.executable, YK] + list(args) + ["--port", os.ttyname(self.t.s)], capture_output=True, text=True, timeout=900)
            return r.returncode, r.stdout + r.stderr
        rc, o = yk("send", self.src_("TEXT.TXT"), "--as", "SRV.TXT", "-q")
        ok, d = self.ondisk("/K/SRV.TXT", self.f["TEXT.TXT"])
        self.check("server: SEND", rc == 0 and ok, d + o)
        rc, o = yk("get", "B?.BIN", out, "-q")
        self.check("server: GET a glob", rc == 0 and sorted(os.listdir(out)) == ["B1.BIN", "B2.BIN"], o + str(os.listdir(out)))
        rc, o = yk("get", "srv.txt", out, "-q")
        self.check("server: GET a lower-case name", rc == 0 and open(os.path.join(out, "SRV.TXT"), "rb").read() == self.f["TEXT.TXT"], o)
        rc, o = yk("get", "NOSUCH.X", out, "-q")
        self.check("server: GET a missing file: an error packet", rc == 1 and "File not found" in o, o)
        rc, o = yk("finish", "-q")
        j = self.t.wait(PROMPT, mark, 120)
        self.t.fwd = False
        to = bytes(self.t.out[mark:j]).decode("latin1")
        self.check("server: FINISH ends it", rc == 0 and "files moved" in to, o + to)

    def throughput(self):
        """instructions each kermit run spent working (not waiting in kio's poll loops) per byte, at 1 MHz"""
        if not self.histo or not os.path.exists(self.histo): return
        sys.path.insert(0, os.path.join(ROOT, "os"))
        import mkkio
        kb, _, L = mkkio.build()                  # kio[]'s bytes (as in the binary: relocated only at run time)
        img = open(os.path.join(ROOT, "os/build/bin/kermit.bin"), "rb").read()
        if img.count(kb) != 1: print("%-4s throughput: kio[] not found in kermit.bin" % self.tag); return
        base = 0x5000 + img.find(kb)
        # the poll loops: hunt..hgot and lwait..lgot are waiting but for their last pass (4 instructions: the poll
        # that found the character); bwait..bad is waiting, plus the 4-instruction poll that sent it there
        rng = lambda lo, hi: (base + L[lo], base + L[hi])
        blocks, cur = {}, None
        for line in open(self.histo):
            if line.startswith("program"): cur = int(line.split()[1]); blocks[cur] = {}; continue
            a, c = line.split(); blocks[cur][int(a, 16)] = int(c)
        res = []
        for prog, nbytes, what in ((self.recv_prog, sum(len(self.f[n]) for n in self.f) + 18, "receive"),
                                   (self.send_prog, sum(len(self.f[n]) for n in self.f) + 18, "send")):
            h = blocks.get(prog, {})
            total = sum(h.values())
            span = lambda r: sum(c for a, c in h.items() if r[0] <= a < r[1])
            idle = (span(rng("HUNT", "HGOT")) - 4 * h.get(base + L["HGOT"], 0) + span(rng("LWAIT", "LGOT")) -
                    4 * h.get(base + L["LGOT"], 0) + span(rng("BWAIT", "BAD")) + 4 * h.get(base + L["BWAIT"], 0))
            busy = total - idle
            res.append((what, nbytes, total, busy))
        for what, nbytes, total, busy in res:
            print("%-4s throughput %-8s %d bytes: %d instructions, %d waiting, %d working = %.0f a byte; "
                  "at 1 MHz (32.4 clocks an instruction) %.0f bytes/s" % (self.tag, what, nbytes, total, total - busy,
                  busy, busy / nbytes, nbytes / (busy * 32.4 / 1e6)), flush=True)

    def finish(self):
        self.t.close()
        if self.tag == "uc":
            st = self.t.err.decode("latin1").strip().splitlines()
            print("%-4s emulator: %s" % (self.tag, st[-1] if st else ""))
        for path, want in getattr(self, "disk_checks", []):
            ok, d = self.ondisk(path, want)
            self.check("on the disk: " + path, ok, d)
        r = subprocess.run([sys.executable, FS, "fsck", self.img], capture_output=True, text=True)
        self.check("fsck of the disk afterwards", r.returncode == 0, r.stdout[-500:])
        self.throughput()
        if not self.keep and not self.failed: shutil.rmtree(self.dir, ignore_errors=True)


def calib():
    """PPS and the receive loop's clocks a character, on the microcode emulator (standalone, under the monitor)"""
    d = os.path.join(BUILD, "calib"); os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "software/assembler/yacc1.def"), d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    shutil.copy(os.path.join(ROOT, "os/kermit_io.c"), d)
    src = ('#include "kermit_io.c"\nchar buf[100];\nint r;\n'
           'void main() { int i, o, w, base; base = kio;\n'
           '  for (i = 0; kio_rel[i]; i++) { o = kio_rel[i]; w = (kio[o] << 8) + kio[o + 1] + base; kio[o] = w >> 8; kio[o + 1] = w & 255; }\n'
           '  pokew(kio + KIO_KBUF, buf); pokew(kio + KIO_KCNT, 94); pokew(kio + KIO_KTIMO, TIMO);\n'
           '  r = call(kio + KIO_KRX); halt(); }\n')
    res = {}
    for tag, timo, inp in (("t1", 1, None), ("t3", 3, None), ("p3", 1, b"\x01#abc\r"), ("p94", 1, b"\x01~" + b"x" * 94 + b"\r")):
        open(os.path.join(d, "cal.c"), "w").write("#define TIMO %d\n" % timo + src)
        subprocess.run([sys.executable, os.path.join(ROOT, "software/compiler/y1cc.py"), os.path.join(d, "cal.c"),
                        "-o", os.path.join(d, "cal.asm"), "--boot"], check=True)
        subprocess.run([os.path.join(ROOT, "software/assembler/asm"), "cal", "-d=yacc1"], cwd=d, capture_output=True)
        ef = open(os.path.join(d, "cal.err"), "w+")
        p = subprocess.Popen([EMUS["uc"], "-x", "-m", "-f", os.path.join(d, "cal.img")], stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=ef)
        if inp: p.stdin.write(inp); p.stdin.flush()
        p.wait(timeout=600)                    # stdin stays open meanwhile: an empty line, not the end of input
        p.stdin.close(); ef.seek(0)
        m = re.search(r"(\d+) clocks", ef.read())
        res[tag] = int(m.group(1))
    per_s = res["t3"] - res["t1"]
    per_ch = (res["p94"] - res["p3"]) / 91.0
    print("calib: a second of krx timeout = %d clocks (1,000,000 at 1 MHz: %+.2f%%)" % (per_s / 2, (per_s / 2 - 1e6) / 1e4))
    print("calib: krx reads a character in %.1f clocks (the line brings one every 260 at 38400 baud)" % per_ch)
    ok = abs(per_s / 2 - 1e6) < 20000 and per_ch < 300
    print("calib: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    av = sys.argv[1:]
    if "--calib" in av: sys.exit(calib())
    tags = [av[av.index("--emu") + 1]] if "--emu" in av else ["int", "uc"]
    only = ["files", "options", "errors", "server"]
    if "--only" in av:
        only = []
        for w in av[av.index("--only") + 1:]:
            if w.startswith("--"): break
            only.append(w)
    keep = "--keep" in av
    r = subprocess.run([sys.executable, os.path.join(ROOT, "os/mkkio.py"), "--check"], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
    failed = 0
    for tag in tags:
        t0 = time.time()
        run = Run(tag, keep)
        try:
            for s in only: getattr(run, "s_" + s)()
        except Exception as e:
            run.check("session", False, repr(e))
        run.finish()
        print("%-4s %d checks, %d failed, %.0f s" % (tag, run.n, run.failed, time.time() - t0), flush=True)
        failed += run.failed
    if only == ["files", "options", "errors", "server"] and "--emu" not in av:
        failed += calib()
    print("%d failed" % failed)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

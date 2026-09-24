#!/usr/bin/env python3
"""tests/bench/run.py - the bench test set (2026-09-23): programs loaded into RAM through the ROM monitor's ':' loader,
run with G3000, their console output compared with the transcript the microcode-level emulator produces.

  run.py                      build the images (tests/bench/images/, committed), check them against the committed
                              ones, run every image on both emulators through the monitor exactly as on the bench
                              (the .img text + "G3000"), compare with expected/NAME.uc.out and NAME.int.out
  run.py --update             rewrite the expected transcripts from this run (read the diff first)
  run.py --port /dev/cu.X     THE BENCH: load and run every image on the machine (tools/monload.py's link), compare
                              with expected/NAME.uc.out, log everything to tests/bench/logs/bench-DATE.log
         [--delay MS] [--only NAME,NAME] [--baud 38400]

The set, in the order a bench session should read it (simplest first):
  hello      compiled C: putchar/puts through the ROM's console vector
  brur       tests/assembler/brur (BRUR Rn, the 2026-09-22 instruction): prints ABC0123
  isa        tests/ucemu/isa.asm: every arithmetic, logic, shift, compare, register, memory and stack instruction,
             each result a hex byte (PUSHR/POPR: H-1; the taken BRZ/BRNZ: H-2; carry after ADD/ADDC); BRDEV prints
             D on the microcode and the machine, I then D on the instruction-level emulator
  arith calls control arrays structs globals switch switchnb fib sieve syscall   compiled C (tests/compiler)
             rt_sub, rt_mul, rt_divmod, the shifts, comparisons, calls, switch via BRUR tables
  xisa       (2026-09-24) tests/compiler/xisa.c compiled with y1cc --xisa: LDZ/STZ through the page register R6,
             ADDIW, SHL16 in compiled code (the page, a recursive frame in it, R6 reloaded after the ROM's charout);
             needs the 2026-09-24 microcode in the sequencer EEPROM (isa checks the instructions one by one first)

Why the assembly tests are rewritten: the originals write each result to port 2, which exists only on the emulators,
and several results depend on the carry surviving to the next instruction, so they cannot call a ROM print routine
(its shifts reload the carry on the hardware). The bench versions store each result with `JSR outb`, a routine that
touches neither ACC, the flags nor the stack beyond its own call (LDR/STR/STAVR/INCR through a pointer in memory),
into a buffer at $5000, and print the buffer at the end through the ROM vectors. HALT becomes a return to the monitor
and the $F000 boot stub is dropped (the loader refuses ROM addresses). Not in the set: io.c (writes port 2 directly),
chars.c (needs console input), the compile-error tests.
"""
import os, sys, re, glob, time, shutil, subprocess, tempfile, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CC = os.path.join(ROOT, "software/compiler/y1cc.py"); ASM = os.path.join(ROOT, "software/assembler/asm")
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
IMAGES = os.path.join(HERE, "images"); EXPECTED = os.path.join(HERE, "expected"); LOGS = os.path.join(HERE, "logs")
MONLST = os.path.join(ROOT, "firmware/monitor/monitor.lst")
C_TESTS = ["hello", "arith", "calls", "control", "arrays", "structs", "globals", "switch", "switchnb", "fib", "sieve", "syscall",
           "xisa"]
ORDER = ["hello", "brur", "isa"] + [t for t in C_TESTS if t != "hello"]

EPILOGUE = """;
; ---- bench harness (tests/bench/run.py) ----
; outb: ACC -> the next byte of the buffer at $5000. Uses no ALU operation, no flags and no stack beyond JSR/RET:
; R7 is saved and restored through memory (LDR/STR address through the hidden R2, as every LDR/STR does).
outb:   STR  R7,bsave7
        LDR  R7,bptr
        STAVR R7
        INCR R7
        STR  R7,bptr
        LDR  R7,bsave7
        RET
bsave7: DW 0
bptr:   DW 5000H
; benchend: print the buffer (MODE hex: two hex digits and a space each, 16 to a line; text: as characters), then
; return to the monitor
benchend:
        MVIW R3,5000H
bloop:  MVRLA R3                ; done when R3's low byte reaches the pointer's (the buffer is under 256 bytes)
        LDT  bptr+1
        BREQ bdone
        LDAVR R3
%(PRINT)s
        INCR R3
        BR   bloop
bdone:  LDAI 13
        JSR  0FFC4H
        LDAI 10
        JSR  0FFC4H
        RET
"""
PRINT_HEX = """        JSR  0FFE0H             ; SHOWBYTEA: ACC as two hex digits
        LDAI ' '
        JSR  0FFC4H             ; CHAROUT
        MVRLA R3
        ANDI 0FH
        LDTI 0FH
        BRNEQ bnext
        LDAI 13
        JSR  0FFC4H
        LDAI 10
        JSR  0FFC4H
bnext:"""
PRINT_TEXT = """        JSR  0FFC4H             ; CHAROUT"""


def bench_asm(src, mode):
    """An assembly test rewritten for the bench: OUTA P2 -> JSR outb, HALT -> BR benchend, the $F000 stub dropped."""
    out = ["; GENERATED by tests/bench/run.py from %s - do not edit; see the run.py docstring" % os.path.relpath(src, ROOT)]
    entry = None
    for line in open(src):
        code = line.split(";")[0]
        if re.match(r"\s*ORG\s+0F000H", code, re.I): break          # the boot stub and END
        if re.search(r"\bOUTA\s+P2\b", code, re.I): line = re.sub(r"OUTA\s+P2", "JSR outb", line, flags=re.I)
        if re.match(r"\s*HALT\b", code, re.I): line = re.sub(r"HALT", "BR benchend", line, flags=re.I)
        out.append(line.rstrip("\n"))
    out.append(EPILOGUE % {"PRINT": PRINT_HEX if mode == "hex" else PRINT_TEXT})
    return "\n".join(out) + "\n"


def sh(cmd, **kw): return subprocess.run(cmd, capture_output=True, **kw)


def build(d):
    """Build every image into d; returns {name: path}."""
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    paths = {}
    for name, src, mode in (("brur", "tests/assembler/brur/brur.asm", "text"), ("isa", "tests/ucemu/isa.asm", "hex")):
        open(os.path.join(d, name + ".asm"), "w").write(bench_asm(os.path.join(ROOT, src), mode))
    for name in C_TESTS:
        src = os.path.join(ROOT, "tests/compiler", name + ".c")
        flags = re.search(r"//\s*y1cc:\s*(.*)", open(src).read())
        r = sh([sys.executable, CC, src, "-o", os.path.join(d, name + ".asm")] + (flags.group(1).split() if flags else []))
        if r.returncode: sys.exit("compile %s failed: %s" % (name, r.stderr.decode()[-300:]))
    for name in ORDER:
        a = sh([ASM, name, "-d=yacc1"], cwd=d)
        if not re.search(rb"^0 Errors", a.stdout, re.M): sys.exit("assembling %s failed:\n%s" % (name, a.stdout.decode("latin1")[-600:]))
        img = open(os.path.join(d, name + ".img")).read()
        bad = [l for l in img.splitlines() if l.startswith(":") and l[7:9] == "00" and not (0x1000 <= int(l[3:7], 16) < 0xE000)]
        if bad: sys.exit("%s writes outside $1000-$DFFF: %s" % (name, bad[0]))
        paths[name] = os.path.join(d, name + ".img")
    return paths


def monitor_label(name):
    m = re.search(r"^([0-9a-f]{4})h: %s\b" % name.upper(), open(MONLST).read(), re.M)
    return m.group(1)


def transcript(out):
    """The program's output: after "GO ADDRESS:" (and the typed 3000, which the machine and the microcode emulator
    echo and the instruction-level emulator does not) up to the last monitor prompt, which the run ends at (the
    harness types 0 after G3000: the microcode emulator stops at the monitor's stop loop, -E; the other exits)."""
    i = out.find("GO ADDRESS:")
    if i < 0: return None
    i += len("GO ADDRESS:")
    if out[i:i + 4] == "3000": i += 4
    j = out.rfind(">")
    return out[i:j] if j >= i else None


def emulators(img):
    data = open(img, "rb").read() + b"G3000" + b"0"
    stop = monitor_label("stop")
    runs = {"uc": [os.path.join(ROOT, "software/ucemu/y1ucemu"), "-x", "-m", "-E", stop, "-l", "400000000"],
            "int": [os.path.join(ROOT, "software/emulator/emulator"), "-x", "-m", "-l", "30000000"]}
    res = {}
    for tag, cmd in runs.items():
        r = sh(cmd, input=data, timeout=900)
        res[tag] = (transcript(r.stdout.decode("latin1")), r.stderr.decode("latin1").strip().splitlines()[-1:] or [""])
    return res


def check_images(paths):
    ok = True
    for name, p in paths.items():
        committed = os.path.join(IMAGES, name + ".img")
        if not os.path.exists(committed) or open(committed).read() != open(p).read():
            ok = False; print("images: %s differs from tests/bench/images (run with --update to refresh)" % name)
    return ok


def main():
    av = sys.argv[1:]
    update = "--update" in av
    port = av[av.index("--port") + 1] if "--port" in av else None
    only = av[av.index("--only") + 1].split(",") if "--only" in av else None
    d = tempfile.mkdtemp()
    if port: p, f = bench(port, av, only); sys.exit(1 if f else 0)
    paths = build(d)
    failed = 0
    if update:
        os.makedirs(IMAGES, exist_ok=True)
        for name, p in paths.items(): shutil.copy(p, os.path.join(IMAGES, name + ".img"))
    elif not check_images(paths): failed += 1
    os.makedirs(EXPECTED, exist_ok=True)
    for name in ORDER:
        if only and name not in only: continue
        res = emulators(paths[name])
        for tag in ("uc", "int"):
            got, status = res[tag]
            f = os.path.join(EXPECTED, "%s.%s.out" % (name, tag))
            if got is None: print("%-9s %-4s FAIL  no transcript: %s" % (name, tag, status[0][:100])); failed += 1; continue
            if update: open(f, "w", newline="").write(got)
            exp = open(f, newline="").read() if os.path.exists(f) else None
            if got == exp: print("%-9s %-4s PASS  %d bytes of output" % (name, tag, len(got)))
            else:
                open(os.path.join(d, name + "." + tag + ".got"), "w", newline="").write(got)
                print("%-9s %-4s FAIL  output differs (%s)" % (name, tag, os.path.join(d, name + "." + tag + ".got"))); failed += 1
        if res["uc"][0] is not None and res["int"][0] is not None and name != "isa" and res["uc"][0].replace("\r", "") != res["int"][0].replace("\r", ""):
            print("%-9s      NOTE  the two emulators disagree (beyond BRDEV): read both transcripts" % name)
    if not update: failed += selftest(d)
    print("%d failed" % failed); sys.exit(1 if failed else 0)


def selftest(d):
    """The --port path itself, against the microcode emulator through a pseudo-terminal (as tests/monload does):
    hello, brur and isa loaded, run and compared exactly as on the bench. Returns the number of failures."""
    import pty, tty, select, threading
    m, s = pty.openpty(); tty.setraw(m); tty.setraw(s)
    emu = subprocess.Popen([os.path.join(ROOT, "software/ucemu/y1ucemu"), "-x", "-m", "-l", "900000000"],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    stop = threading.Event()

    def pump():
        while not stop.is_set():
            r, _, _ = select.select([m, emu.stdout], [], [], 0.05)
            if m in r:
                b = os.read(m, 256)
                if b: emu.stdin.write(b); emu.stdin.flush()
            if emu.stdout in r:
                b = os.read(emu.stdout.fileno(), 256)
                if not b: break
                os.write(m, b)
    threading.Thread(target=pump, daemon=True).start()
    try:
        p, f = bench(os.ttyname(s), ["--delay", "0"], ["hello", "brur", "isa"], logdir=d, drain=False)
    finally:
        stop.set(); emu.kill()
    print("%-9s %-4s %s" % ("bench", "pty", "PASS  the --port path ran hello, brur, isa against the microcode emulator"
                            if (p, f) == (3, 0) else "FAIL  %d passed, %d failed" % (p, f)))
    return 0 if (p, f) == (3, 0) else 1


def bench(port, av, only, logdir=LOGS, drain=True):
    """Load and run every committed image on the machine and compare with the microcode emulator's transcript.
    Returns (passed, failed)."""
    spec = importlib.util.spec_from_file_location("monload", os.path.join(ROOT, "tools/monload.py"))
    ml = importlib.util.module_from_spec(spec); spec.loader.exec_module(ml)
    delay = float(av[av.index("--delay") + 1]) if "--delay" in av else 3.0
    baud = int(av[av.index("--baud") + 1]) if "--baud" in av else 38400
    link = ml.Link(port, baud, drain)
    os.makedirs(logdir, exist_ok=True)
    log = open(os.path.join(logdir, "bench-%s.log" % time.strftime("%Y-%m-%d-%H%M")), "w", newline="", buffering=1)
    log.write("tests/bench on the machine, %s, port %s, %g ms/char\n" % (time.strftime("%Y-%m-%d %H:%M"), port, delay))
    # 2026-09-23: first make sure the monitor answers. A CR at the prompt is the "continue" command, which after a
    # reset (NOMODE) or a load (LOADMODE) does nothing but print the prompt again.
    link.s.reset_input_buffer(); prompt = None
    for attempt in range(3):
        link.write(b"\r", 0)
        prompt = link.wait_for([b">"], 3)
        if prompt: break
    if not prompt:
        log.write("no '>' from the monitor after 3 CRs\n"); log.close()
        print("no answer from the monitor on %s at %d baud: is the machine reset and at its '>' prompt, the cable on the"
              " I/O card's DB9, nothing else holding the port?" % (port, baud))
        return 0, 1
    print("monitor answers on %s; loading at %g ms per character" % (port, delay)); sys.stdout.flush()
    passed = failed = 0
    for name in ORDER:
        if only and name not in only: continue
        img = os.path.join(IMAGES, name + ".img")
        recs = ml.records(img)
        link.seen = b""; err = None
        for n, r in enumerate(recs, 1):
            link.write(r.encode("ascii"), delay)
            if r[7:9] == "01":
                got = link.wait_for([b"LOADED WITH ERRORS", b"LOADED\r", b"LOADED\n"], 5)
                if got != b"LOADED\r" and got != b"LOADED\n": err = "load: %s" % (got or b"no LOADED").decode()
                break
            got = link.wait_for([b".", b"?", b"!"], 5)
            sys.stdout.write("\r%-9s record %d/%d " % (name, n, len(recs))); sys.stdout.flush()
            if got != b".":
                err = "load: record %d answered %s" % (n, got.decode() if got else "nothing"); link.write(b"\x1b", 0); break
        if not err:
            link.wait_for([b">"], 5); link.seen = b""
            link.write(b"G3000", delay)
            end = time.time() + 120; quiet = time.time()
            while time.time() < end:
                c = link.s.read(256)
                if c: link.seen += c; quiet = time.time()
                elif link.seen.rstrip().endswith(b">") and time.time() - quiet > 1.5: break
            out = link.seen.decode("latin1")
            i = out.find("3000"); j = out.rstrip().rfind(">")
            got = out[i + 4:j] if i >= 0 and j > i else out
            exp = open(os.path.join(EXPECTED, name + ".uc.out"), newline="").read()
            ok = got == exp
            if not ok: err = "output differs"
        log.write("\n==== %s: %s\n%s\n" % (name, "PASS" if not err else "FAIL " + err, link.seen.decode("latin1")))
        if err and err == "output differs":
            log.write("---- expected (microcode emulator) ----\n%s\n" % exp)
        print("\r%-9s %s          " % (name, "PASS" if not err else "FAIL  " + err)); sys.stdout.flush()
        passed += not err; failed += bool(err)
        if err and err.startswith("load"): link.write(b"\x1b", 0); time.sleep(0.5)
    log.close()
    print("%d passed, %d failed; log in %s" % (passed, failed, log.name))
    return passed, failed


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""tests/sequencer/run.py - exercise tools/ucode_send.py against mock_card.py (no hardware).

  1. differential send: a cache that differs from test.hex in a few records -> exactly those records reach the
     card, with the right bytes, and the cache ends up equal to test.hex (minus the '!' sentinel)
  2. --all send: all 256 records reach the card
  3. --boot-check's dump comparison on the 2026-09-21 run-mode transcript against the tree's test.hex
"""
import os, sys, subprocess, tempfile, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SEND = os.path.join(ROOT, "tools/ucode_send.py")
HEX = os.path.join(ROOT, "firmware/microcode/ucode-generator2/test.hex")
MOCK = os.path.join(HERE, "mock_card.py")


def records():
    lines = open(HEX).read().split("\n")
    return [l for l in lines if l.startswith("%")]


def run_send(extra, cache_lines, tmp):
    cache = os.path.join(tmp, "cache"); out = os.path.join(tmp, "card.txt")
    open(cache, "w").write("\n".join(cache_lines) + "\n")
    mock = subprocess.Popen([sys.executable, MOCK, out], stdout=subprocess.PIPE, text=True)
    port = mock.stdout.readline().strip()
    r = subprocess.run([sys.executable, SEND, "--port", port, "--cache", cache, "--delay", "0", "--timeout", "20"] + extra,
                       capture_output=True, text=True)
    if r.returncode: mock.kill(); sys.exit("ucode_send failed:\n" + r.stdout + r.stderr)
    mock.wait(timeout=60)
    got = {}
    for l in open(out):
        i, h = l.strip().split(": "); got[int(i, 16)] = None if h == "-" else bytes.fromhex(h)
    c = open(cache).read().split("\n")
    while c and c[-1] == "": c.pop()
    return got, c, r.stdout


def main():
    recs = records(); failed = 0
    tmp = tempfile.mkdtemp()
    want = {i: bytes.fromhex(recs[i][5:5 + 1024]) for i in range(256)}

    # 1. differential
    cache = list(recs); changed = [0x03, 0xAD, 0x40, 0xFF]
    for i in changed: cache[i] = cache[i][:5] + ("00" if cache[i][5:7] != "00" else "FF") + cache[i][7:]
    cache[0x10] = ""                                            # never sent before
    got, newcache, out = run_send([], cache, tmp)
    sent = sorted(i for i in got if got[i] is not None)
    if sent != sorted(changed + [0x10]): print("FAIL differential: sent %s" % [hex(i) for i in sent]); failed += 1
    elif any(got[i] != want[i] for i in sent): print("FAIL differential: bytes differ"); failed += 1
    elif newcache != recs: print("FAIL differential: cache not updated to test.hex"); failed += 1
    else: print("PASS differential send: %d records" % len(sent))

    # 2. --all
    got, newcache, out = run_send(["--all"], [""] * 256, tmp)
    if any(got[i] != want[i] for i in range(256)): print("FAIL --all: image differs"); failed += 1
    elif newcache != recs: print("FAIL --all: cache"); failed += 1
    else: print("PASS --all send: 256 records")

    # 3. boot transcript comparison
    spec = importlib.util.spec_from_file_location("ucode_send", SEND); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    text = open(os.path.join(HERE, "boot-run-mode-2026-09-21-sequencer4.log"), encoding="latin1").read()
    checked, bad = m.check_dumps(text, recs)
    # that transcript predates the 2026-09-22 PUSHR fix (H-1), so instruction $07 differs and nothing else may
    other = [b for b in bad if not b.startswith("$07 ")]
    if checked != 5 * 64 or other or not bad: print("FAIL boot-check: %d lines, %d mismatches %s" % (checked, len(bad), (other or bad)[:3])); failed += 1
    else: print("PASS boot-check: %d dumped lines compared, only the pre-fix $07 (PUSHR) lines differ (%d)" % (checked, len(bad)))

    print("%d failed" % failed); sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

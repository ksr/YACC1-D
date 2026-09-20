#!/usr/bin/env python3
"""Rebuild the firmware from the migrated sources in a scratch dir and diff against the committed images.
Proves the tree can reproduce what is in the machine. Never writes into the tree.
  1. software/assembler  -> asm ; assemble firmware/monitor/monitor.asm + firmware/basic/basic.asm with yacc1.def
     -> compare monitor.img / basic.img ; makerom -> compare firmware/rom/shipped/rom (== the burned EEPROM)
  2. firmware/microcode/ucode-generator2 -> regenerate test.hex -> compare the committed test.hex
Exit 1 on any mismatch."""
import os, sys, subprocess, tempfile, shutil, hashlib, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def md5(p): return hashlib.md5(open(p, "rb").read()).hexdigest()
def sh(cmd, cwd): return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
ok = True; tmp = tempfile.mkdtemp(prefix="yacc1-verify-")
try:
    A = os.path.join(ROOT, "software/assembler"); B = os.path.join(tmp, "asm")
    r = sh("cc -w -o %s/asm-bin asm.c asmcmds.c support.c mstrings.c" % tmp, A); assert r.returncode == 0, r.stderr
    os.makedirs(B); shutil.copy(os.path.join(A, "rcasm.rc"), B); shutil.copy(os.path.join(A, "yacc1.def"), B)
    for name in ("monitor", "basic"):
        shutil.copy(os.path.join(ROOT, "firmware", name, name + ".asm"), B)
        r = sh("%s/asm-bin %s -d=yacc1 > %s.log" % (tmp, name, name), B)          # NOTE: source name BEFORE -d=… (the -d handler skips the next arg)
        same = os.path.exists(os.path.join(B, name + ".img")) and md5(os.path.join(B, name + ".img")) == md5(os.path.join(ROOT, "firmware", name, name + ".img"))
        print("%-32s %s" % (name + ".img", "IDENTICAL" if same else "MISMATCH")); ok &= same
    r = sh("awk 'n>=1 { print a[n%1] } { a[n%1]=$0; n=n+1 }' basic.img > tmprom && cat tmprom monitor.img > rom", B)   # = firmware/rom/makerom
    same = md5(os.path.join(B, "rom")) == md5(os.path.join(ROOT, "firmware/rom/shipped/rom")); print("%-32s %s" % ("rom (shipped = burned EEPROM)", "IDENTICAL" if same else "MISMATCH")); ok &= same
    G = os.path.join(ROOT, "firmware/microcode/ucode-generator2"); GT = os.path.join(tmp, "ucode"); shutil.copytree(G, GT, ignore=shutil.ignore_patterns("nbproject"))
    # the generator uses ../../opcodes.h and ../yaccsignal*.h relative to its folder: reproduce that layout in tmp
    os.makedirs(os.path.join(tmp, "u", "gen")); shutil.rmtree(GT); shutil.copytree(G, os.path.join(tmp, "u", "gen", "g"), ignore=shutil.ignore_patterns("nbproject"))
    for h in ("yaccsignaldefine.h", "yaccsignaldata2.h"): shutil.copy(os.path.join(ROOT, "firmware/microcode", h), os.path.join(tmp, "u", "gen"))
    shutil.copy(os.path.join(ROOT, "software/opcodes.h"), os.path.join(tmp, "u"))
    GG = os.path.join(tmp, "u", "gen", "g")
    r = sh("cc -w -o ucodegen *.c && rm -f test.hex && ./ucodegen > gen.log 2>&1; ls test.hex", GG); assert r.returncode == 0, r.stderr + r.stdout
    same = md5(os.path.join(GG, "test.hex")) == md5(os.path.join(G, "test.hex")); print("%-32s %s" % ("microcode test.hex", "IDENTICAL" if same else "MISMATCH")); ok &= same
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("FIRMWARE VERIFIED" if ok else "FIRMWARE MISMATCH"); sys.exit(0 if ok else 1)

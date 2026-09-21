#!/usr/bin/env python3
"""Build the current Processing sketch (embedded/command-sender/command_sender_8) with the Processing 4 command-line
builder, then compile the generated Java once more with Processing's bundled Eclipse compiler with warnings on, so the
sketch is held to the same "zero warnings" bar as the C tools and the Arduino sketches.
Cosmetic ECJ categories are excluded (non-externalised strings, unqualified field access, "could be static", and the
"overrides without super" notes that Processing's setup/draw/keyPressed callbacks always trigger).
Never writes into the tree; everything goes to a scratch dir."""
import os, sys, subprocess, tempfile, shutil, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = "/Applications/Processing.app/Contents"
PROCESSING = os.path.join(APP, "MacOS/Processing")
RES = os.path.join(APP, "app/resources")
SKETCHES = ["embedded/command-sender/command_sender_8"]
IGNORE = ("-nls,-unqualifiedField,-javadoc,-allJavadoc,-serial,-static-access,-static-method,-boxing,-unusedArgument,"
          "-syntheticAccess,-specialParamHiding,-over-ann,-enumSwitch,-switchDefault,-unlikelyCollectionMethodType,-super")
NOISE = ("is overriding a method without making a super invocation", "can potentially be declared as static",
         "Unnecessary semicolon")   # the last two come from preprocessor-generated lines only
def find(pattern, base):
    for root, _, files in os.walk(base):
        for f in files:
            if re.fullmatch(pattern, f): return os.path.join(root, f)
    return None
def main():
    if not os.path.exists(PROCESSING):
        print("Processing.app not found; skipping"); return 0
    core = find(r"core-[\d.]+\.jar", os.path.join(RES, "core/library"))
    ecj = find(r"org\.eclipse\.jdt\.core-[\d.]+\.jar", os.path.join(RES, "modes/java/mode"))
    serial_dir = os.path.join(RES, "modes/java/libraries/serial/library")
    java = os.path.join(RES, "jdk/bin/java")
    cp = ":".join([core] + [os.path.join(serial_dir, j) for j in os.listdir(serial_dir) if j.endswith(".jar")])
    bad = 0
    for rel in SKETCHES:
        src = os.path.join(ROOT, rel); name = os.path.basename(rel)
        pde = open(os.path.join(src, name + ".pde")).read().split("\n")
        tmp = tempfile.mkdtemp(prefix="yacc1-processing-"); out = os.path.join(tmp, "build")
        try:
            r = subprocess.run([PROCESSING, "cli", f"--sketch={src}", f"--output={out}", "--build"],
                               capture_output=True, text=True)
            gen = os.path.join(out, "source", name + ".java")
            if r.returncode != 0 or not os.path.exists(gen):
                print(f"{rel}: PROCESSING BUILD FAILED\n{r.stdout}{r.stderr}"); bad += 1; continue
            jlines = open(gen).read().split("\n")
            # line offset between the generated Java and the .pde: locate the sketch's first declaration line
            anchor = next(l for l in pde if l.strip() and not l.lstrip().startswith(("import", "/*", "*", "//")))
            offset = jlines.index(anchor) - pde.index(anchor)
            stripped = {l.strip() for l in pde}
            r = subprocess.run([java, "-cp", ecj, "org.eclipse.jdt.internal.compiler.batch.Main", "-warn:+all," + IGNORE,
                                "-proc:none", "-source", "9", "-target", "9", "-cp", cp, "-d", os.path.join(tmp, "cls"), gen],
                               capture_output=True, text=True)
            warns = []
            for m in re.finditer(r"^\d+\. (WARNING|ERROR) in .*?\(at line (\d+)\)\n(.*)\n.*\n(.*)$", r.stdout + r.stderr, re.M):
                kind, line, srcline, msg = m.group(1), int(m.group(2)), m.group(3).strip(), m.group(4).strip()
                if kind == "WARNING" and any(n in msg for n in NOISE): continue
                if kind == "WARNING" and msg.startswith("The import") and srcline not in stripped: continue  # preprocessor's own imports
                pline = pde.index(next(l for l in pde if l.strip() == srcline)) + 1 if msg.startswith("The import") else line - offset
                warns.append(f"  {name}.pde:{pline}: {kind.lower()}: {msg}   <- {srcline}")
            print(f"{rel}: build ok, {len(warns)} warnings/errors")
            for w in warns: print(w)
            bad += bool(warns)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"{len(SKETCHES)} Processing sketch(es), {bad} with problems -> " + ("PROCESSING VERIFIED" if not bad else "FAILED"))
    return 1 if bad else 0
if __name__ == "__main__": sys.exit(main())

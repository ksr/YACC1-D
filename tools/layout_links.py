#!/usr/bin/env python3
"""Create the symlinks that let the migrated C tools build UNCHANGED in the YACC1-D layout.
The sources still use the relative paths of the old 'Software/' tree:
  software/emulator/main.c              #include "../opcodes.h"            -> software/opcodes.h (real file, fine)
  firmware/microcode/ucode-generator2/* #include "../../opcodes.h"         -> firmware/opcodes.h            (link -> ../software/opcodes.h)
  software/disassembler/disasm2/main.c  #include "../yaccsignaldefine.h"   -> software/disassembler/yaccsignaldefine.h (link)
  software/disassembler/disasm2/main.c  readSource("../ucode-Generator2/test.123") -> software/disassembler/ucode-Generator2 (link to the generator dir)
Sources are never edited (they must stay byte-identical to YACCS); these links are the whole adaptation.
Re-run after any re-migration. Idempotent."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINKS = {"firmware/opcodes.h": "../software/opcodes.h",
         "software/disassembler/yaccsignaldefine.h": "../../firmware/microcode/yaccsignaldefine.h",
         "software/disassembler/yaccsignaldata2.h": "../../firmware/microcode/yaccsignaldata2.h",
         "software/disassembler/ucode-Generator2": "../../firmware/microcode/ucode-generator2"}
for link, target in LINKS.items():
    p = os.path.join(ROOT, link)
    if os.path.islink(p) and os.readlink(p) == target: continue
    if os.path.lexists(p): os.remove(p)
    os.symlink(target, p)
    assert os.path.exists(p), (link, target)
print("layout links in place:", ", ".join(LINKS))

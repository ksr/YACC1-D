# tests/assembler/brur — BRUR Rn (opcode $AD, added 2026-09-22)

`brur.asm` exercises the new direct register branch: a plain `BRUR R5`, a jump through an address fetched from a
table, and a four-way dispatch driven by a counter. Expected console output `ABC0123`, then HALT (89 instructions).

```
cp brur.asm ../../../software/assembler/yacc1.def <dir> && cd <dir> && echo -h > rcasm.rc && asm brur -d=yacc1
../../../software/emulator/emulator -x -f brur.img
```

BRUR is two bytes (`AD nn`, nn = register number 0-7, like JSRUR): PC ← Rn, nothing pushed, Rn unchanged. It is the
direct form; `BRVR Rn` is the indirect one (PC ← the word at Rn, Rn += 2). Microcode: `firmware/microcode/ucode-generator2/branch.c`,
steps in `docs/isa/steps.txt` and `docs/isa/BRUR.svg`. Emulator-proven only; the sequencer EEPROM must be reloaded with the
regenerated `test.hex` and the register-to-branch-register path (`-REG-RD-HI/LO` + `-HL-SWAP` into `BRANCH-LD-HI/LO`
with `-2-BYTE-OPERAND-SEL`, the same steps JSRUR uses) checked on the bench before code relies on it.

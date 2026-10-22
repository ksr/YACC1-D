# firmware/basic/programs

BASIC programs for the ROM's Tiny BASIC, typed into the machine with `tools/y1term.py` (it waits for the `>>` prompt
after each line and reports a refused one with its line number):

```
python3 tools/y1term.py --send NAME --new --run
```

A bare name is found here (`--dir` changes the folder); in the terminal, Ctrl-] then `s` lists these programs and takes a
name the same way.

| Program | What it does |
|---|---|
| `baslook.bas` | nested counting loops: the inner one counts `C` to 32000, the outer one prints `L` each time round and never ends (a long soak of GOTO, IF and PRINT at the machine's speed; stop it with reset - BASIC has no break key yet, `BACKLOG.md`) |
| `test.bas` | the same program as `baslook.bas` (a working copy kept from the bench, 2026-10-21) |

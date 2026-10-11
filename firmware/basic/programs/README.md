# firmware/basic/programs

BASIC programs for the ROM's Tiny BASIC, typed into the machine with `tools/y1term.py` (it waits for the `>>` prompt
after each line and reports a refused one with its line number):

```
python3 tools/y1term.py --send firmware/basic/programs/NAME.bas --new --run
```

| Program | What it does |
|---|---|
| `baslook.bas` | nested counting loops: the inner one counts `C` to 32000, the outer one prints `L` each time round and never ends (a long soak of GOTO, IF and PRINT at the machine's speed; stop it with reset - BASIC has no break key yet, `BACKLOG.md`) |

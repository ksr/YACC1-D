# firmware/basic

`basic.asm` — the hand-assembled port of uBASIC (`software/ubasic-c/`) as burned (git ff7d85a, 2021-07-09) with its
`.img` (reproducible, see `tools/verify_firmware.py`) and `.lst`. Lives at $E000, variables at $0100/$0200.
- `candidates/2021-09-8afde21/` — adds ON/OFF statements and break-in via `charavail`; never burned.
- `candidates/2021-09-02-3bcacf3-not-working/` — git HEAD, "not working"; with its build products.
- `candidates/2020-11-10-port-draft/` — `basic.asmtmp copy`, the port in progress (Nov 2020); `basic.asmold.asm` — the
  first 1 KB sketch of it.

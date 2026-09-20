# bus-tester-scripts

Format: one `SIGNAL:VALUE#` per line, `//` comments; signal names as in `embedded/libraries/YACC/YACC_Common_header.h`
(leading `-` = active-low, inverted by the firmware; decimal on the wire). Always assert `-BUS-EN:1#` and `-VMA:1#`
before driving memory. Sent by the command sender GUI (file dialog) or `tools/busdrv.py`.

| Folder | Scripts | For |
|---|---|---|
| `ALU/` | `add.new and.new branch.new or.new sub.new zero test.new` (2020-07/08) | the 2020 ALU V3.2 |
| `IO/` | `basic-out serialin serialout` (2020-07/08) | IO card, UART |
| `Index Register/` | `commands-1 copy.txt` (2020-10-09, 372 lines) | Index Registers 1.1 |
| `Memory Card Tests/` | low/hi RAM + EPROM tests, dumps (2020-07/08) | memory card |
| `Gen Test Vectors/` | C generator (2020-06-30, NetBeans project) | producing vector scripts |
| `deprecated/gen1-2016/` | `ALU/*` originals, `commands-1/2.txt`, `Test Vectors/` + `fix` | the 2016 gen-1 machine (old signal names) |
| `deprecated/address-register-2020-07/` | `address registers.txt` | the retired Address+TMP card |

Cleanup 2026-09-20: identical copies (`comands.txt`=`zero`, `IO/and`=`ALU/and`, two `Test Vectors` files = `ALU/data` /
`commands-1.txt`) reduced to one; `xx` (an unrelated shell script) dropped; `test` (a BASIC program) moved to `tests/basic/`.

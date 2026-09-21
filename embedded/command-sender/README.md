# command-sender — Processing host for the bus tester

`command_sender_8/` (2020-08-16) is the current version: a Swing/Processing GUI that opens the bus tester's serial
port and sends the `CMD:OPERAND#` scripts from `tests/bus-tester-scripts/` (hex in the scripts, decimal on the wire),
with tabs per test group. Earlier generations (`old/command_sender` 2016-12 for the gen-1 tester → `command_sender_7`
2020-08-01) are under `deprecated/`, with the one 2016 "ideas" note that used to be copied into every version.

Build check (2026-09-20): `tools/verify_processing.py` builds `command_sender_8` with the Processing 4 command-line
builder (`Processing cli --build`, Processing 4.5.6 in /Applications) and then re-compiles the generated Java with
Processing's bundled Eclipse compiler with warnings on; it passes with zero warnings and is part of the root `make check`.
Two things had to change for the 2020 sketch to build under Processing 4 at all: `import java.io.*` now drags in
`java.io.Serial` (Java 14+), which made `Serial` ambiguous, and the Processing 2 `frame` field no longer exists (the two
JOptionPane dialogs now use `null` as parent). Fourteen unused imports, a parameter that shadowed the global `index`, two
empty `while` bodies and an unguarded cancel of the port dialog were cleaned up at the same time. Not changed: the sketch
still opens the file chooser at `../tests/Test Vectors/` relative to the sketch, the old tree's path; the scripts now live
in `tests/bus-tester-scripts/`.

Planned: replace this Processing sketch with a Python host (see BACKLOG). `tools/busdrv.py` already speaks the wire
protocol; the script interpreter (labels, GOTO, LET/FOR/NEXT, DUMP, WAIT, expected-value matching) is what is missing.

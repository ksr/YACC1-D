# command-sender — Processing host for the bus tester

`command_sender_8/` (2020-08-16) is the current version: a Swing/Processing GUI that opens the bus tester's serial
port and sends the `CMD:OPERAND#` scripts from `tests/bus-tester-scripts/` (hex in the scripts, decimal on the wire),
with tabs per test group. Earlier generations (`old/command_sender` 2016-12 for the gen-1 tester → `command_sender_7`
2020-08-01) are under `deprecated/`, with the one 2016 "ideas" note that used to be copied into every version.

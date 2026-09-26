# Moving files between the Mac and Y1/OS with Kermit

Written 2026-09-26 with `/BIN/KERMIT` (`os/commands/kermit.c`, `man kermit`). The console cable is the only link: the
I/O card's 16C550 at 38400 8N1 behind the MAX232, no flow control, the FTDI cable on the Mac
(`/dev/cu.usbserial-AB0MVHSQ`; the sequencer card's FTDI, `usbserial-AB6WZCQX`, is not the console). The same line
is the terminal and the transfer: you type the kermit command on the YACC1, then go back to the Kermit on the Mac and
start its half. Tested on both emulators against `tools/y1kermit.py` (`tests/kermit/run.py`); **not yet run on the
machine with C-Kermit** (BACKLOG.md).

## 1. Install C-Kermit (once)

```
brew install c-kermit            # C-Kermit 9.0.302; the program is `kermit`
```

## 2. Open the line

The settings are in `tools/y1.ksc`; running it opens the line, sets them all and connects:

```
cd ~/Developer/YACC1-D
kermit tools/y1.ksc
```

or by hand (the same settings):

```
kermit -l /dev/cu.usbserial-AB0MVHSQ -b 38400
C-Kermit> set modem type none
C-Kermit> set carrier-watch off
C-Kermit> set flow-control none
C-Kermit> set parity none
C-Kermit> set prefixing all
C-Kermit> set streaming off
C-Kermit> set window 1
C-Kermit> set block-check 3
C-Kermit> set file type binary
C-Kermit> set transfer mode manual
C-Kermit> set file names literal
C-Kermit> set terminal autodownload on
C-Kermit> connect
```

What each one is for:

| Setting | Why |
|---|---|
| `carrier-watch off`, `modem type none` | a three-wire cable: no carrier detect, no modem |
| `flow-control none` | RTS/CTS are not wired; with hardware flow control C-Kermit would wait for a CTS that never comes |
| `parity none` | the line is 8N1, so bytes over 127 travel as they are (no 8th-bit prefixing needed) |
| `prefixing all` | every control character goes prefixed (`#`). `/BIN/KERMIT` reads packets by their length, so C-Kermit's default (cautious) works too; `all` costs a few percent and never depends on that |
| `streaming off`, `window 1` | `/BIN/KERMIT` answers every packet (stop-and-wait); it does not offer windows or long packets, so C-Kermit would fall back anyway |
| `block-check 3` | the 16-bit CRC; `/BIN/KERMIT` takes 1, 2 or 3 |
| `file type binary`, `transfer mode manual` | every byte arrives as sent. Y1/OS text files end lines with LF like the Mac's, so text needs no conversion. In text mode C-Kermit sends CR LF (kermit drops the CR) and may translate the character set; for exact copies stay binary |
| `file names literal` | a file from the YACC1 keeps its upper-case name (C-Kermit would lower-case it) |
| `terminal autodownload on` | when `kermit -s` on the YACC1 starts sending, C-Kermit in CONNECT mode starts receiving by itself |

Packet length: `/BIN/KERMIT` tells C-Kermit to send it packets of up to 94 characters (the short-packet maximum; `-l N`
lowers it) and sends up to what C-Kermit asks for; nothing to set. Timeout: it asks C-Kermit to wait 15 s for its
packets and itself uses what C-Kermit asks for (else 5 s).

## 3. Terminal and transfer

- **CONNECT** (`connect`, or `c`): the YACC1's console. Boot with `O` at the monitor's `>` if the OS is not running.
- **Back to C-Kermit**: `Ctrl-\` then `C`. The YACC1 program keeps running (kermit waits for packets); C-Kermit's
  prompt is back.
- A transfer is started on both sides: first the YACC1 command (in CONNECT), then C-Kermit's (at its prompt). After it,
  `connect` again: kermit's summary is waiting there (it prints nothing while packets flow: the console is the line).

## 4. Mac to YACC1

```
C-Kermit> connect
/> cd /WORK                       (the files land in the current directory)
/WORK> kermit -r                  kermit: ready to receive: start the sender (3 Ctrl-Cs cancel)
Ctrl-\ C
C-Kermit> send report.txt         (or: send *.c   several files in one go)
   ... C-Kermit's transfer display ...
C-Kermit> connect
  REPORT.TXT  1234 bytes
kermit: 1 file received
/WORK>
```

Names arrive upper-cased and cut to Y1/OS's 12 characters (`lower case name.text` becomes `LOWER_CA.TEX`); the name
used is sent back to C-Kermit, which shows it. A file of the same name is replaced once the new one is complete
(`kermit -r -n` keeps it and names the new one `REPORT.TXT~1`); a transfer that fails leaves nothing behind
(`-k` keeps the part that arrived). For a program: `kermit -r -a 5000` gives the received files load and exec address
$5000, so `run NAME` (or just `NAME`) works.

## 5. YACC1 to Mac

```
C-Kermit> connect
/WORK> kermit -s REPORT.TXT *.C   kermit: sending 3 files: start the receiver
   (with autodownload on, C-Kermit starts receiving here by itself; otherwise:)
Ctrl-\ C
C-Kermit> receive
C-Kermit> connect
  REPORT.TXT  1234 bytes
  ...
kermit: 3 files sent
```

Files go to C-Kermit's current directory (`cd` at its prompt; `set file collision overwrite` if you want an existing Mac
file replaced, the default renames it). `kermit -s -T FILE` sends text (LF as CR LF); the default is binary.

## 6. Server mode: several transfers without switching

```
C-Kermit> connect
/WORK> kermit -x                  kermit: server; the other side: send, get, finish (3 Ctrl-Cs quit)
Ctrl-\ C
C-Kermit> send notes.txt
C-Kermit> get REPORT.TXT          (a Y1/OS glob works: get *.C; a lower-case name is tried in upper case too)
C-Kermit> send prog
C-Kermit> finish                  (ends kermit -x; the shell prompt comes back)
C-Kermit> connect
```

The server does SEND, GET, FINISH and BYE (both end it; C-Kermit's `bye` also closes its line, so use `finish`).
`remote dir`, `remote cd`... answer "Unimplemented server command" (BACKLOG.md).

## 7. When something goes wrong

- **Cancel on the YACC1 side**: three Ctrl-Cs while kermit waits for a packet (in CONNECT). On the Mac: Ctrl-C in
  C-Kermit's transfer display. Either way kermit sends or gets an error packet, deletes the partial file and prints why.
- **Nothing starts**: kermit waits 5 minutes for the first packet (sending an NAK, or its S packet again, every 5 s:
  that is the `#N3`-like noise seen in CONNECT) and then gives up with "Too many retries".
- **Transfers stall with many retries**: the receive side of the YACC1 at 1 MHz reads a character in 279 clocks while
  the line brings one every 260, so it relies on the 16C550's 16-byte receive FIFO, which kermit switches on for a
  transfer (and off after). If the FIFO does not work on the card, a packet longer than ~13 characters overruns:
  `kermit -r -l 20` (the shortest packets) is the test; C-Kermit's first packet (~25 characters) would still be too
  long, so then the line speed has to come down (the ROM sets 38400).
- **Speed**: at 1 MHz about 260 bytes/s to the YACC1 and 240 bytes/s from it (the CPU, not the line: ~120-130
  instructions a byte; `os/README.md` "kermit"). A 10K file takes about 40 s.

## 8. Without C-Kermit: tools/y1kermit.py

The Python Kermit the tests use speaks the same protocol (pyserial, as `tools/monload.py`):

```
python3 tools/y1kermit.py term                      a terminal on the line (Ctrl-] quits): type kermit -r there
python3 tools/y1kermit.py send report.txt           to kermit -r (or a kermit -x server)
python3 tools/y1kermit.py receive ~/incoming        from kermit -s
python3 tools/y1kermit.py get 'REPORT.TXT' ~/in     from kermit -x;   y1kermit.py finish   ends it
```

`--port /dev/cu.usbserial-AB0MVHSQ` if more than one USB serial port is present; `tools/README.md` lists its options.

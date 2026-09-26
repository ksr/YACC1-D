# E-Kermit 1.8, unmodified — the source /BIN/KERMIT was ported from

Every file in this folder except this README is **exactly as distributed** by the Kermit Project: E-Kermit
("Embedded Kermit") version 1.8 of 25 May 2021, by Frank da Cruz, Columbia University. They are kept only as the
reference for the port; nothing builds them. The port is `os/commands/kermit.c` (the protocol module `kermit.c`, the
control loop of `main.c`, the I/O of `unixio.c`, rewritten for the y1cc C subset and Y1/OS; its header lists every
change) with `os/kermit_io.asm` (the UART and the per-byte loops in YACC1 assembly).

| | |
|---|---|
| Home page | https://www.kermitproject.org/ek.html ("Version: 1.8") |
| Downloaded | 2026-09-26, `curl -L https://www.kermitproject.org/ftp/kermit/archives/ek18.tar` (the page's DOWNLOAD link for E-Kermit 1.8; the official Kermit Project site, nothing else) |
| Archive | `ek18.tar`, 143,360 bytes, POSIX tar; SHA-256 `59c54f3fee05797ae2c3fbb9905cd518938bce86db83675a377532289ea2da1b` (the tar itself is not kept; its 14 files are, unpacked, with their dates) |
| Licence | the Revised 3-Clause BSD License, in `COPYING` (and at the top of `kermit.c`, `kermit.h`): redistribution in source form must keep the copyright notice, the conditions and the disclaimer, which `os/commands/kermit.c` does |
| Copyright | (C) 1995, 2021, Trustees of Columbia University in the City of New York |

SHA-256 of the files as unpacked:

```
869a8672a34c15dd5a9972690e523ec70a23b0e6f76a0fd2f49788f976311352  AAREADME.TXT
b3b95dc15c77b7c10ee26da078d5eb8a2221ddb3428ea1cdce03ff9717044d03  COPYING
4f4fd6159ea5252bc3cb6c01ae71c5789f7349bdb71e75bbf42199f6808d296e  archives.sh
eab3437abd24b8840191a9066c9b96dbf2ea18e58040fdfdcb420c097afad0f1  cdefs.h
400380b5fb1a672cd51e98c285511c6bd36de95056c36cf33df0692a0ad24bfb  debug.h
7717c6815e506f834931ff54c8e383166b1cd62a412ea37ce2eac7f8e1f41c74  ek17.diff
e8867dec40b8c1308f40b1e868719cbf4c315dcc93611bc2c1df50798d0f9957  ek18.diff
1af3aa55bbd49154ea4d03192ad48a5d9205bf761101dbdf1f1b73d1c4dff5e8  kermit.c
022b13072d451cff1b52b125b77d07f5180837e8c37f327f0ad4fbb1cdc4195f  kermit.h
6367243a8801dcd0b32da4dff34f73639b07b27dcb8d670c63ddab5bbe5f8970  main.c
f5fbe88035eb06cb351baffea1125ea5f2c5fb20f732423477bdccaf7f4d5de5  makefile
048317210ff26a36806d69f626fc9fc722660aa910728c3c8428aa9674172fd3  platform.h
048317210ff26a36806d69f626fc9fc722660aa910728c3c8428aa9674172fd3  unix.h
a5b03af4389d0a17d74c765c402efbbef55d2d34f555ef04a371c50fa289bdce  unixio.c
```

What the files are (upstream's own description is in `AAREADME.TXT` and on the home page): `kermit.c` the protocol
module (no I/O, no library calls: the host program passes packets in and gets packets out through callbacks in
`struct k_data`), `kermit.h` its data structures and feature switches (`F_AT` attributes, `F_CRC` block checks 2 and 3,
`F_LP` long packets, `F_SSW` simulated sliding windows...), `main.c` a Unix command-line driver (`-r`, `-s files`,
`-b`, `-B`, `-T`...), `unixio.c` its Unix I/O module, `cdefs.h`, `debug.h`, `platform.h`/`unix.h` the portability
headers, `makefile` its Unix build, `ek17.diff`/`ek18.diff` the changes of the last two versions, `archives.sh` the
maintainer's packaging script.

Why a port and not a clean-room Kermit: E-Kermit was written for exactly this kind of machine (no C library, no
dynamic memory, the I/O supplied by the host), and its protocol module needed only the changes the y1cc subset
forces (function pointers, `long`, signed values, `#ifdef`) plus timeouts, which it leaves to the other Kermit.

#!/usr/bin/env python3
"""mock_card.py - a fake Sequencer4 in download mode on a pseudo-terminal, for testing tools/ucode_send.py.

  mock_card.py OUTFILE      prints the pty's slave path on the first stdout line, then speaks the card's protocol:
                            '>>' prompt, '%' cc ii + 512 hex byte values per instruction, '!' ends the download.
                            The received image is written to OUTFILE as 256 lines (instruction number: hex bytes,
                            '-' for an instruction never written), then the process exits.
"""
import os, sys, pty, tty, select


def rd(fd, n):
    b = b""
    while len(b) < n:
        c = os.read(fd, n - len(b))
        if not c: raise EOFError
        b += c
    return b


def main():
    out = sys.argv[1]
    m, s = pty.openpty(); tty.setraw(m)
    print(os.ttyname(s)); sys.stdout.flush()
    image = [None] * 256
    while True:
        while True:                                      # the prompt, repeated until the host answers: the sender
            os.write(m, b">>\r\n")                        # opens its side after this process started, and a pty
            if select.select([m], [], [], 0.3)[0]: break   # drops what was written before the slave was opened
        c = rd(m, 1)
        if c == b"!": break
        if c != b"%": sys.exit("mock_card: unexpected char %r (the card would blink FAULT 5)" % c)
        rd(m, 2)                                         # checksum, ignored like the card
        ins = int(rd(m, 2), 16)
        data = bytearray()
        while len(data) < 512:
            h = rd(m, 1)
            if h == b"Z": data += b"\0" * (512 - len(data)); break
            data.append(int(h + rd(m, 1), 16))
        image[ins] = bytes(data)
    with open(out, "w") as f:
        for i in range(256): f.write("%02X: %s\n" % (i, image[i].hex() if image[i] is not None else "-"))


if __name__ == "__main__":
    main()

# Preparing a CompactFlash card for the YACC1

How to put Y1/OS on a real CF card from the Mac, check it, and read a card back. The card then goes into the CF-to-IDE
adapter on the CF interface's IDE header (`docs/cards/cf.md`: the CF card v1.0 circuit, planned onto the memory card,
not built yet), and the monitor's `O` command boots it (the CF on ports P8/P9, as in the ROM in the machine).

Written 2026-09-23. The tool (`tools/cfcard.py`) has been tested against an ordinary file standing in for a card and
against the Mac's internal disk, which it refuses; **it has not yet written a real card** (no reader was attached).

## What goes on the card

A P8XFS v2 volume, built by `make -C os` as `os/disk.img` (1 MB, 2048 sectors):

| Sectors | What |
|---|---|
| LBA 0 | the boot block: `P8`, version 2, OSCNT (sectors of OS), the free-sector pointer |
| LBA 1..32 | the OS image (`Y1OS.BIN`), loaded to $1000 by the ROM's `O` command |
| LBA 33..36 | the root directory |
| LBA 37.. | directories and files: `/BIN`, `/MAN`, `/DOCS`, the samples |

The image is written to the **start** of the card. Only its own sectors are written; the rest of the card is left as it
was. The OS allocates new files from the volume's free pointer, never from the card's size, so a card of any size works
(the tool refuses cards over 64 GB only as a guard against picking the wrong disk).

## Writing a card

1. Build the image: `make -C os` (the tests, `make -C os test`, prove it on both emulators first).
2. Put the CF card in a USB CF reader and plug it in. If macOS says the disk is not readable and offers to initialise
   it, choose **Ignore**. Initialising would write a Mac partition table over LBA 0.
3. Find it:

   ```
   python3 tools/cfcard.py list
   ```

   Only external physical disks are listed, with size and bus; the CF card is the one of the card's size, typically
   `disk4` or similar. **Check the size** against the card's label.
4. Write it:

   ```
   python3 tools/cfcard.py write os/disk.img --disk disk4
   ```

   The tool re-checks that the disk is external, physical, removable or ejectable, and no bigger than 64 GB, prints
   what it found, and asks you to type the disk name back. It unmounts the disk, runs `sudo dd` (macOS asks for your
   password), reads the written sectors back, compares them with the image, and ejects the card. It reports
   `read back IDENTICAL`, or `DIFFERENT - do not use this card` and exits with an error.
5. Put the card in the adapter, the adapter on the CF interface's IDE header (powered as the adapter needs:
   `docs/cards/cf.md` sections 0 and 3), and in the monitor type `O`.
   `BOOT FROM CF` then the Y1/OS banner and `/>` mean it worked. What to check if it does not: `docs/cards/cf.md`
   section 7.

Writing the whole 1 MB takes a second or two; the read-back check about the same.

## Reading a card back

To see what the machine wrote (files saved, `pack` results) or to keep a backup:

```
python3 tools/cfcard.py read card.img --disk disk4
python3 tools/p8xfs.py ls card.img /
python3 tools/p8xfs.py fsck card.img
python3 tools/p8xfs.py get card.img /SOME/FILE --out file
```

`read` copies as many sectors as the volume's free pointer says are in use, at least 2048; `--sectors N` overrides it.

## Updating only the OS, or only files

A card keeps its files when only the OS changes if you update the image rather than rebuild it: read the card
(`read card.img`), install the new OS into that image (`python3 tools/p8xfs.py boot card.img os/build/y1os.bin`),
`put` new programs with `p8xfs.py`, and `write card.img` back. Rebuilding `os/disk.img` with `make -C os` starts from
a fresh volume, discarding whatever the machine wrote.

## Safety

- The tool only accepts a disk that macOS reports as external, physical and removable or ejectable, that appears in
  `diskutil list external physical`, and that is at most 64 GB. It refuses a partition (`disk4s1`): the image needs
  the whole disk from LBA 0.
- It always asks for the disk name to be typed back (`--yes` skips that; do not use `--yes` by hand).
- `dd` runs as root through `sudo`: the tool never writes anywhere else, and a mistyped disk name that passes every
  check would still be an external removable disk of CF-card size. **Unplug other USB sticks and SD cards** before
  writing, so the only candidate is the CF card.

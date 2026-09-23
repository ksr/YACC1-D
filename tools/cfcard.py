#!/usr/bin/env python3
"""cfcard.py - put a Y1/OS disk image on a real CompactFlash card from the Mac, or read one back (2026-09-23).

  cfcard.py list                               the external physical disks macOS sees (a CF card in a USB reader)
  cfcard.py write IMAGE --disk diskN [--yes]   write IMAGE (e.g. os/disk.img) to the card's first sectors, verify it
  cfcard.py read OUT.img --disk diskN [--sectors N]
                                               copy the card's first N sectors (default: as many as the volume's
                                               free pointer says are in use, at least 2048) to a file, to inspect it
                                               on the Mac with tools/p8xfs.py or keep a backup

Writing a raw image means dd onto a whole disk device: one wrong disk number and the wrong disk is erased. So `write`
and `read` only accept a disk that macOS reports as external (not Internal), physical, removable or ejectable, and no
bigger than MAX_GB; they show what they found and ask you to type the disk's name back before writing. dd needs root,
so the tool runs `sudo dd` and macOS asks for your password in the terminal.

The image is written to the start of the card: LBA 0 = the P8XFS boot block, exactly where the ROM's `O` command
reads it. Only the image's own sectors are written (os/disk.img is 1 MB); the rest of the card is left alone, and the
OS allocates from the volume's free pointer, not from the card's size. The card is unmounted first (macOS may also
offer to initialise an unreadable disk: choose Ignore) and ejected at the end.

docs/procedures/CF-CARD.md is the whole procedure. For tests, --target-file PATH writes to or reads from an ordinary
file instead of a device, skipping every disk check (tests/cfcard/run.py).
"""
import os, sys, json, struct, argparse, subprocess, filecmp, tempfile

MAX_GB = 64            # CF cards used with the YACC1 are small; anything bigger is refused as probably not the card
SEC = 512


def diskinfo(disk):
    r = subprocess.run(["diskutil", "info", "-plist", disk], capture_output=True)
    if r.returncode: sys.exit("cfcard: diskutil does not know %s" % disk)
    j = subprocess.run(["plutil", "-convert", "json", "-o", "-", "-"], input=r.stdout, capture_output=True).stdout
    return json.loads(j)


def external_disks():
    r = subprocess.run(["diskutil", "list", "-plist", "external", "physical"], capture_output=True)
    j = json.loads(subprocess.run(["plutil", "-convert", "json", "-o", "-", "-"], input=r.stdout, capture_output=True).stdout or b"{}")
    return j.get("WholeDisks", [])


def check_disk(disk):
    """Refuse anything that is not plausibly the CF card. Returns (device path, info)."""
    disk = disk.replace("/dev/", "").replace("rdisk", "disk")
    if not disk.startswith("disk") or not disk[4:].isdigit():
        sys.exit("cfcard: give a whole disk like disk4 (from `cfcard.py list`), not a partition such as disk4s1")
    i = diskinfo(disk)
    size_gb = i.get("TotalSize", 0) / 1e9
    problems = []
    if i.get("Internal", True): problems.append("macOS says it is INTERNAL")
    if i.get("VirtualOrPhysical") == "Virtual": problems.append("it is a virtual disk")
    if not (i.get("RemovableMedia") or i.get("Ejectable")): problems.append("it is neither removable nor ejectable")
    if size_gb > MAX_GB: problems.append("it is %.1f GB (more than %d GB is refused)" % (size_gb, MAX_GB))
    if size_gb == 0: problems.append("it reports no size (no card in the reader?)")
    if disk not in external_disks(): problems.append("it is not in `diskutil list external physical`")
    print("%s: %s, %.2f GB, %s, internal=%s removable=%s ejectable=%s" % (disk, i.get("MediaName", "?"), size_gb,
          i.get("BusProtocol", "?"), i.get("Internal"), i.get("RemovableMedia"), i.get("Ejectable")))
    if problems: sys.exit("cfcard: refusing %s: %s" % (disk, "; ".join(problems)))
    return "/dev/r" + disk, disk, i


def confirm(disk, what, yes):
    if yes: return
    ans = input("Type %s to %s it, anything else to stop: " % (disk, what)).strip()
    if ans != disk: sys.exit("cfcard: stopped, nothing written")


def volume_sectors(path):
    """Sectors a P8XFS volume uses: its free pointer (boot block byte 4, LE16), at least 2048."""
    with open(path, "rb") as f: b = f.read(SEC)
    if b[:2] != b"P8": return 2048
    return max(2048, struct.unpack_from("<H", b, 4)[0])


def cmd_list(a):
    disks = external_disks()
    if not disks: print("no external physical disks: put the CF card in a USB reader"); return
    for d in disks:
        i = diskinfo(d)
        print("%-8s %-28s %8.2f GB  %-10s removable=%s ejectable=%s" % (d, i.get("MediaName", "?")[:28],
              i.get("TotalSize", 0) / 1e9, i.get("BusProtocol", "?"), i.get("RemovableMedia"), i.get("Ejectable")))


def cmd_write(a):
    img = a.image
    if not os.path.exists(img): sys.exit("cfcard: no image %s (make -C os builds os/disk.img)" % img)
    data = open(img, "rb").read()
    if len(data) % SEC or data[:2] != b"P8":
        sys.exit("cfcard: %s is not a P8XFS volume image (size %d, signature %r)" % (img, len(data), data[:2]))
    n = len(data) // SEC
    if a.target_file:
        with open(a.target_file, "r+b" if os.path.exists(a.target_file) else "wb") as f: f.write(data)
        dev = a.target_file
    else:
        dev, disk, info = check_disk(a.disk)
        confirm(disk, "OVERWRITE the first %d sectors of" % n, a.yes)
        subprocess.run(["diskutil", "unmountDisk", disk], check=True)
        r = subprocess.run(["sudo", "dd", "if=" + img, "of=" + dev, "bs=65536"])
        if r.returncode: sys.exit("cfcard: dd failed")
    back = tempfile.mktemp()
    readback(dev, back, n, a.target_file)
    same = open(back, "rb").read() == data
    os.unlink(back)
    print("%d sectors written to %s, read back %s" % (n, dev, "IDENTICAL" if same else "DIFFERENT - do not use this card"))
    if not a.target_file and same: subprocess.run(["diskutil", "eject", a.disk.replace("/dev/", "")])
    if not same: sys.exit(1)


def readback(dev, out, n, is_file):
    if is_file:
        with open(dev, "rb") as f: data = f.read(n * SEC)
        open(out, "wb").write(data); return
    r = subprocess.run(["sudo", "dd", "if=" + dev, "of=" + out, "bs=512", "count=%d" % n])
    if r.returncode: sys.exit("cfcard: dd read failed")


def cmd_read(a):
    if a.target_file:
        dev = a.target_file; n = a.sectors or volume_sectors(dev)
    else:
        dev, disk, info = check_disk(a.disk)
        subprocess.run(["diskutil", "unmountDisk", disk], check=True)
        if a.sectors: n = a.sectors
        else:
            head = tempfile.mktemp(); readback(dev, head, 1, False); n = volume_sectors(head); os.unlink(head)
    readback(dev, a.out, n, bool(a.target_file))
    print("%d sectors from %s -> %s   (inspect: python3 tools/p8xfs.py ls %s /)" % (n, dev, a.out, a.out))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list")
    w = sp.add_parser("write"); w.add_argument("image"); w.add_argument("--disk"); w.add_argument("--yes", action="store_true")
    w.add_argument("--target-file", help=argparse.SUPPRESS)
    r = sp.add_parser("read"); r.add_argument("out"); r.add_argument("--disk"); r.add_argument("--sectors", type=int)
    r.add_argument("--target-file", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.cmd in ("write", "read") and not a.disk and not a.target_file: sys.exit("cfcard: --disk diskN is required (see `cfcard.py list`)")
    {"list": cmd_list, "write": cmd_write, "read": cmd_read}[a.cmd](a)


if __name__ == "__main__":
    main()

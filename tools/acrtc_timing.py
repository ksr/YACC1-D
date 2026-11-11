#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tools/acrtc_timing.py - monitor timings for an HD63484 ACRTC card (2026-11-11; docs/cards/video-v3.md).

  acrtc_timing.py                the table of docs/cards/video-v3.md: every mode in each memory arrangement
  acrtc_timing.py MODE [--access single|dual] [--gai N] [--bpp N] [--grade 4|6|8]
                                 one mode: the clock, the timing registers, the memory it needs
  acrtc_timing.py --check        the note's figures, asserted (make check)

The ACRTC's clock is 2CLK; a memory cycle is two 2CLK cycles (the address, then the data). A display cycle is one
memory cycle in single access and two in the dual modes (interleaved, superimposed), and fetches 16 x GAI bits of
graphics (GAI: the graphic address increment, the frame buffer's width in words). So the memory cycle rate is
    Fc = dots x bits a pixel x (1 single, 2 dual) / (GAI x 16)        (the user's manual, section 2.2.1)
and 2CLK = 2 Fc, which must be 1 MHz to the grade's 4, 6 or 8 MHz. The horizontal registers count memory cycles: HC =
the line - 1, HSW = the sync width (2..31), HDS = the back porch - 1 (from HSYNC's rising edge to the display), HDW =
the displayed width - 1 (even widths in the dual modes); the vertical ones count rasters: VC = the frame, VSW = the
sync width (1..31), VDS = the back porch - 1, and the Base screen's height SP1 = the displayed lines (section 5.8).
Monitor timings are the VESA / IBM figures: dots (active, front porch, sync, back porch), lines (the same), the
sync polarities.
"""
import sys

# name: (dot clock Hz, (h active, front, sync, back), (v active, front, sync, back), hsync polarity, vsync polarity)
MODES = {
    "640x480@60": (25.175e6, (640, 16, 96, 48), (480, 10, 2, 33), "-", "-"),
    "640x400@70": (25.175e6, (640, 16, 96, 48), (400, 12, 2, 35), "-", "+"),
    "800x600@56": (36.0e6, (800, 24, 72, 128), (600, 1, 2, 22), "+", "+"),
    "800x600@60": (40.0e6, (800, 40, 128, 88), (600, 1, 4, 23), "+", "+"),
    "1024x768@60": (65.0e6, (1024, 24, 136, 160), (768, 3, 6, 29), "-", "-"),
    "640x240tv": (12.5875e6, (640, 16, 96, 48), (240, 4, 3, 15), "-", "-"),      # the same crystal / 2: TV / CGA rate
}
# the HD63484-8's figures used for the memory's access time (ns): address delay, read data set-up (the manual's AC table)
T_MAD, T_MRDS = 70, 40
T_LATCH, T_BUFFER = 12, 10            # the address latch and the data buffer round the memory (74F / 74AC, allowed)


class Bad(Exception):
    pass


def plan(mode, access="dual", gai=1, bpp=1, grade=8):
    dot, (ha, hf, hs, hb), (va, vf, vs, vb), hpol, vpol = MODES[mode]
    d = 2 if access == "dual" else 1
    dots_mc = 16.0 * gai / (bpp * d)                    # dots a memory cycle
    if dots_mc != int(dots_mc): raise Bad("%g dots a memory cycle" % dots_mc)
    dots_mc = int(dots_mc)
    clk2 = 2 * dot / dots_mc
    why = []
    if not 1e6 <= clk2 <= grade * 1e6: why.append("2CLK %.3f MHz is outside 1-%d MHz" % (clk2 / 1e6, grade))
    if ha % dots_mc: why.append("%d dots is not a whole number of memory cycles" % ha)
    width = ha // dots_mc
    if d == 2 and width % 2: why.append("the displayed width must be even in a dual mode")
    total = round((ha + hf + hs + hb) / dots_mc)
    sync = max(2, round(hs / dots_mc))
    back = max(1, round(hb / dots_mc))
    front = total - sync - back - width
    if front < 0: why.append("no room for the front porch")
    if sync > 31: why.append("HSW over 31")
    if total > 256: why.append("the line is over 256 memory cycles")
    vtotal = va + vf + vs + vb
    line_hz = dot / (total * dots_mc)
    mem_ns = 2e9 / clk2
    words_line = ha * bpp // 16
    return {
        "mode": mode, "access": access, "gai": gai, "bpp": bpp, "dot": dot, "clk2": clk2, "dots_mc": dots_mc,
        "HC": total - 1, "HSW": sync, "HDS": back - 1, "HDW": width - 1, "front": front,
        "VC": vtotal, "VSW": vs, "VDS": vb - 1, "SP1": va,
        "line_hz": line_hz, "frame_hz": line_hz / vtotal, "hpol": hpol, "vpol": vpol,
        "mem_ns": mem_ns, "ram_ns": mem_ns - T_MAD - T_MRDS - T_LATCH - T_BUFFER,
        "MW": words_line, "words": words_line * va, "bits_wide": 16 * gai, "why": why,
    }


def show(p):
    print("%s, %s access, %d bit%s a pixel, memory %d bits wide (GAI +%d)" % (
        p["mode"], p["access"], p["bpp"], "" if p["bpp"] == 1 else "s", p["bits_wide"], p["gai"]))
    print("  dot clock %.4f MHz, 2CLK %.4f MHz (dot clock / %g), %d dots a memory cycle of %.1f ns" % (
        p["dot"] / 1e6, p["clk2"] / 1e6, p["dot"] / p["clk2"], p["dots_mc"], p["mem_ns"]))
    print("  line %.3f kHz, frame %.2f Hz; HSYNC %s, VSYNC %s" % (p["line_hz"] / 1e3, p["frame_hz"], p["hpol"], p["vpol"]))
    print("  HSR (r82) = $%02X%02X  HC %d, HSW %d      HDR (r84) = $%02X%02X  HDS %d, HDW %d   (front porch %d cycles)" % (
        p["HC"], p["HSW"], p["HC"], p["HSW"], p["HDS"], p["HDW"], p["HDS"], p["HDW"], p["front"]))
    print("  VSR (r86) = $%04X  VC %d      VDR (r88) = $%02X%02X  VDS %d, VSW %d      SP1 (r8A) = %d" % (
        p["VC"], p["VC"], p["VDS"], p["VSW"], p["VDS"], p["VSW"], p["SP1"]))
    print("  memory width MW = %d words a line, %d words a screen (%d bytes); RAM access within about %.0f ns" % (
        p["MW"], p["words"], 2 * p["words"], p["ram_ns"]))
    for w in p["why"]: print("  NOT POSSIBLE: " + w)


def table():
    print("%-12s %-6s %3s %4s  %9s %8s  %-22s %s" % ("mode", "access", "bpp", "bits", "2CLK MHz", "RAM ns", "HC HSW HDS HDW / VC VDS", "result"))
    for mode in MODES:
        for access in ("single", "dual"):
            for bpp, gai in ((1, 1), (1, 2), (1, 4), (2, 1), (2, 2), (4, 2), (4, 4)):
                try: p = plan(mode, access, gai, bpp)
                except Bad: continue
                regs = "%3d %2d %2d %3d / %3d %2d" % (p["HC"], p["HSW"], p["HDS"], p["HDW"], p["VC"], p["VDS"])
                print("%-12s %-6s %3d %4d  %9.3f %8.0f  %-22s %s" % (
                    mode, access, bpp, p["bits_wide"], p["clk2"] / 1e6, p["ram_ns"], regs,
                    "ok" if not p["why"] else p["why"][0]))


def check():
    p = plan("640x480@60", "dual")
    assert (p["HC"], p["HSW"], p["HDS"], p["HDW"], p["front"]) == (99, 12, 5, 79, 2), p
    assert (p["VC"], p["VSW"], p["VDS"], p["SP1"]) == (525, 2, 32, 480), p
    assert abs(p["clk2"] - 6.29375e6) < 1 and not p["why"] and p["words"] == 19200 and p["MW"] == 40
    assert abs(p["line_hz"] - 31468.75) < 0.01 and abs(p["frame_hz"] - 59.94) < 0.01
    s = plan("640x480@60", "single")
    assert (s["HC"], s["HSW"], s["HDS"], s["HDW"], s["front"]) == (49, 6, 2, 39, 1) and abs(s["clk2"] - 3.146875e6) < 1
    assert plan("640x480@60", "dual", grade=6)["why"] and not plan("640x480@60", "single", grade=4)["why"]
    assert plan("800x600@60", "dual")["why"] and not plan("800x600@60", "single")["why"]         # 10 MHz / 5 MHz
    assert not plan("800x600@60", "dual", gai=2)["why"]                                          # 32 bits wide
    assert plan("1024x768@60", "single")["why"] and not plan("1024x768@60", "single", gai=2)["why"]   # 8.125 / 4.06 MHz
    assert plan("1024x768@60", "dual", gai=2)["why"] and not plan("1024x768@60", "dual", gai=4)["why"]
    assert not plan("640x480@60", "dual", gai=2, bpp=2)["why"]                                   # four colours
    assert not plan("640x480@60", "single", bpp=2)["why"] and plan("640x480@60", "dual", bpp=2)["why"]
    assert not plan("640x480@60", "single", gai=2, bpp=4)["why"] and plan("640x480@60", "single", bpp=4)["why"]
    assert not plan("640x480@60", "dual", gai=4, bpp=4)["why"] and plan("640x480@60", "dual", gai=2, bpp=4)["why"]
    t = plan("640x240tv", "dual")
    assert abs(t["line_hz"] - 15734.4) < 0.1 and t["VC"] == 262 and not t["why"]
    print("acrtc_timing: the note's figures hold")


def main():
    a = sys.argv[1:]
    if "--check" in a: return check()
    if not a: return table()
    opt = lambda name, default: a[a.index(name) + 1] if name in a else default
    if a[0] not in MODES: sys.exit("modes: " + ", ".join(MODES))
    try: show(plan(a[0], opt("--access", "dual"), int(opt("--gai", 1)), int(opt("--bpp", 1)), int(opt("--grade", 8))))
    except Bad as e: sys.exit("not possible: %s" % e)


if __name__ == "__main__":
    main()

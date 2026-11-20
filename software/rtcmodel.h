/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/*
 * rtcmodel.h - the I/O card V1.2's real-time clock, a DS12885, shared by both YACC1 emulators (2026-11-20).
 *
 * The I/O card V1.2 (hardware/cards/io/kicad/v1.2, docs/cards/rtc.md; designed, not built) is the V1.1 card in the
 * machine with a DS12885 clock beside it: port 6 takes the register number (write only: the chip latches it as the
 * strobe ends), port 7 reads or writes the register chosen. The machine as built has the V1.1 card and nothing on
 * these ports, so the clock is here only when it is asked for:
 *
 *   Y1IO_CARD=v1.2       the I/O card V1.2: the clock answers on P6 / P7 (default v1.1: nothing there, as before)
 *   Y1RTC_TIME="2026-11-20 12:34:56"
 *                        the chip's time when the emulator starts; from there it runs on the MACHINE's clocks (the
 *                        emulated CPU clock, Y1_CLOCK Hz, default 1 MHz), so a transcript repeats. Without it the
 *                        chip has the Mac's local time and runs with the Mac's clock, whatever the emulator's speed
 *   Y1RTC_NEW=1          a chip that was never set: the oscillator stopped (register A = 0), register B = 0 (BCD,
 *                        12-hour), the time registers 0 - what `date -s` meets on a new card
 *
 * The chip, as its data sheet and the MC146818 family have it:
 *   00 seconds  01 seconds alarm  02 minutes  03 minutes alarm  04 hours  05 hours alarm  06 day of the week (1-7,
 *   a counter of its own: the chip does not work it out from the date)  07 day of the month  08 month  09 year (00-99)
 *   0A register A: bit 7 UIP (read only), bits 6-4 DV (010 = the oscillator on and counting; 000 stopped; 11x the
 *      divider held in reset: no counting, and the first update comes 500 ms after 010 is written), bits 3-0 RS, the
 *      periodic rate (0 none, 1 = 256 Hz, 2 = 128 Hz, 3..15 = 32768 >> (RS - 1) Hz: 6 is 1024 Hz)
 *   0B register B: bit 7 SET (1 = no updates: the program writes the time), 6 PIE, 5 AIE, 4 UIE, 3 SQWE, 2 DM (1 =
 *      binary, 0 = BCD), 1 24/12 (1 = 24-hour; in 12-hour mode bit 7 of an hours byte is PM), 0 DSE
 *   0C register C (read only, cleared by the read): bit 7 IRQF, 6 PF, 5 AF, 4 UF
 *   0D register D (read only): bit 7 VRT = 1, the cell is good
 *   0E-7F 114 bytes of RAM. This chip has no century register: $32 is RAM like the rest.
 * A year is a leap year when it divides by 4, and 99 is followed by 00.
 *
 * As a chip that is set and running (no Y1RTC_NEW) it starts with A = $26 and B = $06: binary, 24-hour, the choice
 * of docs/cards/rtc.md section 6. Changing DM or 24/12 does not convert what the registers hold, as on the chip: the
 * program writes the time again.
 *
 * UIP is 1 from 244 us before a second ends to 1984 us after it (the update cycle), and never while SET is 1 or the
 * oscillator is off. Register C's flags are worked out when it is read, from the chip's time since the read
 * before: UF if a second ended, AF if a second in that time (the last 24 hours of it) matched the three alarm bytes
 * (a byte of $C0-$FF matches anything), PF if a period of the rate RS ended; IRQF if a flag's enable bit is set.
 *
 * Not modelled: the -IRQ pin (JP8 on the card is left off, and nothing in the emulators raises -INT for it; the
 * flags can be polled), SQW, daylight saving (DSE), the periodic flag while SET is 1, and the cell - the RAM and a
 * time the program set last as long as the emulator runs. -RESET is tied high on the card: a reset of the machine
 * does not touch the chip. A read of port 6 gives $FF (nothing drives the card's data lines, which are pulled up).
 *
 * Include after <stdio.h>/<string.h>/<stdint.h>; call rtc_init() once, keep rtc_clk at the machine's clocks so far,
 * and pass ports 6 and 7 to rtc_io_read(port) / rtc_io_write(port, v) while rtc.present is set.
 */
#ifndef RTCMODEL_H
#define RTCMODEL_H

#include <stdlib.h>
#include <time.h>
#include <sys/time.h>

#define RTC_PORT_REG  6
#define RTC_PORT_DATA 7
#define RTC_SET 0x80
#define RTC_DM  0x04
#define RTC_24H 0x02

static struct {
    int present;                 /* Y1IO_CARD=v1.2 */
    int fixed;                   /* Y1RTC_TIME: the chip runs on the machine's clocks */
    double hz;                   /* the CPU clock (Y1_CLOCK) */
    long long host0;             /* the host's time at rtc_init, in us (the other time base) */
    long long base;              /* running: the chip's time = base + the time base, in us since 2000-01-01 00:00:00 */
    long long seen;              /* the chip's time up to which register C's flags are worked out */
    int dow_shift;               /* the day-of-the-week counter against the calendar's own day */
    uint8_t sel, a, b, c;
    uint8_t reg[10];             /* the alarm bytes always; the time bytes while the chip does not count */
    uint8_t ram[128];            /* 0E-7F, by register number */
} rtc;
static unsigned long long rtc_clk;                /* the machine's clocks so far: the emulator keeps it */

static const int rtc_mdays[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};

static long long rtc_elapsed(void) {              /* the time base, in us */
    if (rtc.fixed) return (long long)((long double)rtc_clk * 1e6L / (long double)rtc.hz);
    struct timeval tv; gettimeofday(&tv, NULL);
    return (long long)tv.tv_sec * 1000000LL + tv.tv_usec - rtc.host0;
}
static int rtc_runs(void) { return ((rtc.a >> 4) & 7) == 2 && !(rtc.b & RTC_SET); }
static long long rtc_days(int y, int m, int d) {  /* days from 2000-01-01 to year 2000 + y, month m, day d */
    long long n = (long long)y * 365 + (y + 3) / 4;
    for (int i = 1; i < m; i++) n += rtc_mdays[i - 1] + (i == 2 && y % 4 == 0);
    return n + d - 1;
}
static uint8_t rtc_enc(int v) { return (rtc.b & RTC_DM) ? (uint8_t)v : (uint8_t)((v / 10) << 4 | v % 10); }
static int rtc_dec(uint8_t v, int lo, int hi) {
    int n = (rtc.b & RTC_DM) ? v : (v >> 4) * 10 + (v & 15);
    return n < lo ? lo : n > hi ? hi : n;
}

/* the chip's time t (us) as the ten registers would hold it now: the time bytes into out, the alarm bytes kept */
static void rtc_encode(long long t, uint8_t out[10]) {
    long long s = t / 1000000, days = s / 86400;
    int sec = (int)(s % 60), min = (int)(s / 60 % 60), hr = (int)(s / 3600 % 24);
    int dow = (int)((days + 6 + rtc.dow_shift) % 7) + 1, d = (int)(days % 36525), y = 0, m = 0;   /* 2000-01-01: a Saturday, day 7 */
    for (int len; d >= (len = y % 4 ? 365 : 366); y++) d -= len;
    for (int len; d >= (len = rtc_mdays[m] + (m == 1 && y % 4 == 0)); m++) d -= len;
    out[0] = rtc_enc(sec); out[2] = rtc_enc(min);
    if (rtc.b & RTC_24H) out[4] = rtc_enc(hr);
    else out[4] = (uint8_t)(rtc_enc(hr % 12 ? hr % 12 : 12) | (hr >= 12 ? 0x80 : 0));
    out[6] = rtc_enc(dow); out[7] = rtc_enc(d + 1); out[8] = rtc_enc(m + 1); out[9] = rtc_enc(y);
    out[1] = rtc.reg[1]; out[3] = rtc.reg[3]; out[5] = rtc.reg[5];
}
/* the time (us) that rtc.reg's time bytes say, in register B's format; the day of the week is taken as written */
static long long rtc_decode(void) {
    const uint8_t *r = rtc.reg;
    int hr;
    if (rtc.b & RTC_24H) hr = rtc_dec(r[4], 0, 23);
    else hr = rtc_dec(r[4] & 0x7F, 1, 12) % 12 + (r[4] & 0x80 ? 12 : 0);
    long long days = rtc_days(rtc_dec(r[9], 0, 99), rtc_dec(r[8], 1, 12), rtc_dec(r[7], 1, 31));
    rtc.dow_shift = (rtc_dec(r[6], 1, 7) - 1 - (int)((days + 6) % 7) + 7) % 7;
    return (days * 86400 + hr * 3600LL + rtc_dec(r[2], 0, 59) * 60 + rtc_dec(r[0], 0, 59)) * 1000000LL;
}
static long long rtc_now(void) { return rtc.base + rtc_elapsed(); }   /* the chip's time; only while it counts */

/* register C's flags for the chip's time up to t */
static void rtc_flags(long long t) {
    if (t <= rtc.seen) return;
    long long s0 = rtc.seen / 1000000, s1 = t / 1000000;
    if (s1 > s0) {
        rtc.c |= 0x10;                                                              /* UF: an update ended */
        for (long long k = s1 - s0 > 86400 ? s1 - 86399 : s0 + 1; k <= s1 && !(rtc.c & 0x20); k++) {
            uint8_t now[10]; rtc_encode(k * 1000000, now);
            int hit = 1;
            for (int i = 0; i < 3; i++) if (rtc.reg[2 * i + 1] < 0xC0 && rtc.reg[2 * i + 1] != now[2 * i]) hit = 0;
            if (hit) rtc.c |= 0x20;                                                 /* AF: the alarm's second */
        }
    }
    int rs = rtc.a & 15;
    if (rs) {                                                                       /* PF: a period of 32768 Hz / div ended */
        long long div = rs == 1 ? 128 : rs == 2 ? 256 : 1LL << (rs - 1);
        long long k0 = (rtc.seen / 1000000 * 32768 + rtc.seen % 1000000 * 32768 / 1000000) / div;
        long long k1 = (t / 1000000 * 32768 + t % 1000000 * 32768 / 1000000) / div;
        if (k1 > k0) rtc.c |= 0x40;
    }
    rtc.seen = t;
}

/* a write to register A or B, or to a time byte: what the chip counts from afterwards */
static void rtc_change(int r, uint8_t v) {
    int was = rtc_runs(), dv = (rtc.a >> 4) & 7;
    long long t = was ? rtc_now() : 0;
    if (was) { rtc_flags(t); rtc_encode(t, rtc.reg); }       /* the registers as they stand, in the format they had */
    if (r == 0x0A) rtc.a = v & 0x7F; else if (r == 0x0B) rtc.b = v; else rtc.reg[r] = v;
    if (!rtc_runs()) return;
    long long phase = was ? t % 1000000 : dv != ((rtc.a >> 4) & 7) ? 500000 : 0;   /* the divider released: 500 ms to the update */
    rtc.seen = rtc_decode() + phase;
    rtc.base = rtc.seen - rtc_elapsed();
}

static uint8_t rtc_io_read(int port) {
    if (port != RTC_PORT_DATA) return 0xFF;
    int r = rtc.sel;
    long long t = rtc_runs() ? rtc_now() : 0;
    if (r < 10) {
        uint8_t now[10];
        if (!rtc_runs()) return rtc.reg[r];
        rtc_encode(t, now);
        return now[r];
    }
    switch (r) {
        case 0x0A: {
            long long f = t % 1000000;
            return (uint8_t)(rtc.a | (rtc_runs() && (f >= 1000000 - 244 || f < 1984) ? 0x80 : 0));
        }
        case 0x0B: return rtc.b;
        case 0x0C: {
            if (rtc_runs()) rtc_flags(t);
            uint8_t v = rtc.c;
            rtc.c = 0;
            return (uint8_t)(v | (v & rtc.b & 0x70 ? 0x80 : 0));
        }
        case 0x0D: return 0x80;
        default:   return rtc.ram[r];
    }
}

static void rtc_io_write(int port, uint8_t v) {
    if (port == RTC_PORT_REG) { rtc.sel = v & 0x7F; return; }
    if (port != RTC_PORT_DATA) return;
    int r = rtc.sel;
    if (r == 1 || r == 3 || r == 5) rtc.reg[r] = v;          /* an alarm byte */
    else if (r <= 0x0B) rtc_change(r, v);
    else if (r >= 0x0E) rtc.ram[r] = v;                      /* C and D are read only */
}

static void rtc_init(void) {
    const char *e = getenv("Y1IO_CARD");
    memset(&rtc, 0, sizeof rtc);
    if (e && *e) {
        if (*e == 'v' || *e == 'V') e++;
        if (!strcmp(e, "1.2")) rtc.present = 1;
        else if (strcmp(e, "1.1")) { fprintf(stderr, "Y1IO_CARD=%s: the I/O cards are v1.1 and v1.2\n", getenv("Y1IO_CARD")); exit(2); }
    }
    e = getenv("Y1_CLOCK");
    rtc.hz = e && atof(e) > 0 ? atof(e) : 1e6;
    struct timeval tv; gettimeofday(&tv, NULL);
    rtc.host0 = (long long)tv.tv_sec * 1000000LL + tv.tv_usec;
    int y, mo, d, h, mi, s;
    long long us = tv.tv_usec;
    e = getenv("Y1RTC_TIME");
    if (e && *e) {
        if (sscanf(e, "%d-%d-%d%*1[ T]%d:%d:%d", &y, &mo, &d, &h, &mi, &s) != 6 || y < 2000 || y > 2099 || mo < 1 || mo > 12 ||
            d < 1 || d > 31 || h < 0 || h > 23 || mi < 0 || mi > 59 || s < 0 || s > 59) {
            fprintf(stderr, "Y1RTC_TIME=%s: a time is \"2026-11-20 12:34:56\", in the years 2000-2099\n", e); exit(2);
        }
        rtc.fixed = 1; us = 0;
    } else {
        time_t now = tv.tv_sec; struct tm tm; localtime_r(&now, &tm);
        y = tm.tm_year + 1900; mo = tm.tm_mon + 1; d = tm.tm_mday; h = tm.tm_hour; mi = tm.tm_min; s = tm.tm_sec;
    }
    e = getenv("Y1RTC_NEW");
    if (e && *e && *e != '0') return;                        /* never set: everything 0, the oscillator off */
    rtc.a = 0x26; rtc.b = RTC_DM | RTC_24H;
    rtc.seen = (rtc_days((y - 2000) % 100, mo, d) * 86400 + h * 3600LL + mi * 60 + s) * 1000000LL + us;
    rtc.base = rtc.seen - rtc_elapsed();
}

#endif

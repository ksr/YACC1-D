/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/*
 * model_test.c - software/rtcmodel.h on its own (2026-11-20): the I/O card V1.2's DS12885 as the emulators model it.
 * Built and run by run.py; the chip runs here on the machine's clocks (Y1RTC_TIME), a clock a microsecond, so every
 * check repeats. The last part is the chip on the host's clock.
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "../../../software/rtcmodel.h"

static int fails;
#define CHECK(name, cond) do { if (!(cond)) { fails++; printf("FAIL %s (line %d)\n", name, __LINE__); } } while (0)

static uint8_t rd(int r) { rtc_io_write(RTC_PORT_REG, (uint8_t)r); return rtc_io_read(RTC_PORT_DATA); }
static void wr(int r, int v) { rtc_io_write(RTC_PORT_REG, (uint8_t)r); rtc_io_write(RTC_PORT_DATA, (uint8_t)v); }
static void us(long long n) { rtc_clk += (unsigned long long)n; }
static void start(const char *card, const char *time, const char *fresh) {
    if (card) setenv("Y1IO_CARD", card, 1); else unsetenv("Y1IO_CARD");
    if (time) setenv("Y1RTC_TIME", time, 1); else unsetenv("Y1RTC_TIME");
    if (fresh) setenv("Y1RTC_NEW", fresh, 1); else unsetenv("Y1RTC_NEW");
    rtc_clk = 0;
    rtc_init();
}
/* the time set as a program does it: SET held, the bytes in the format b names */
static void set(int b, int y, int mo, int d, int dow, int h, int mi, int s) {
    wr(0x0B, b | 0x80);
    wr(9, y); wr(8, mo); wr(7, d); wr(6, dow); wr(4, h); wr(2, mi); wr(0, s);
    wr(0x0B, b);
}

int main(void) {
    unsetenv("Y1_CLOCK");
    start(NULL, NULL, NULL);
    CHECK("no card named: the V1.1 card, no clock", !rtc.present);
    start("v1.1", NULL, NULL);
    CHECK("Y1IO_CARD=v1.1: no clock", !rtc.present);

    start("v1.2", "2026-11-20 12:34:56", NULL);
    CHECK("Y1IO_CARD=v1.2: the clock is there", rtc.present && rtc.fixed);
    CHECK("the time it was started with, binary and 24-hour", rd(9) == 26 && rd(8) == 11 && rd(7) == 20 && rd(4) == 12 &&
          rd(2) == 34 && rd(0) == 56);
    CHECK("2026-11-20 is a Friday: day 6", rd(6) == 6);
    CHECK("registers A (UIP apart), B, D", (rd(0x0A) & 0x7F) == 0x26 && rd(0x0B) == 0x06 && rd(0x0D) == 0x80);
    CHECK("a read of port 6 gives $FF", rtc_io_read(RTC_PORT_REG) == 0xFF);
    rtc_io_write(RTC_PORT_REG, 0x82);
    CHECK("the register number is 7 bits", rtc_io_read(RTC_PORT_DATA) == 34);
    us(3999999); CHECK("3.999999 s on: still 59 seconds", rd(0) == 59 && rd(2) == 34);
    us(1);       CHECK("4 s on: 12:35:00", rd(0) == 0 && rd(2) == 35 && rd(4) == 12);

    /* UIP: from 244 us before a second ends to 1984 us after it */
    start("v1.2", "2026-11-20 12:34:56", NULL);
    CHECK("UIP as a second begins", rd(0x0A) == 0xA6);
    us(1983);          CHECK("UIP 1983 us in", rd(0x0A) == 0xA6);
    us(1);             CHECK("no UIP 1984 us in", rd(0x0A) == 0x26);
    us(1000000 - 1984 - 245); CHECK("no UIP 245 us before the end", rd(0x0A) == 0x26);
    us(1);             CHECK("UIP 244 us before the end", rd(0x0A) == 0xA6 && rd(0) == 56);
    us(244);           CHECK("the second after", rd(0) == 57);
    wr(0x0B, 0x86);    CHECK("no UIP while SET is 1", rd(0x0A) == 0x26);

    /* BCD and 12-hour; a leap day; midnight is 12 AM, noon 12 PM */
    start("v1.2", "2026-11-20 12:34:56", NULL);
    wr(0x0B, 0x80);
    CHECK("changing the format does not convert the registers", rd(0) == 56 && rd(9) == 26);
    set(0x00, 0x28, 0x02, 0x28, 2, 0x91, 0x59, 0x58);       /* 2028-02-28 11:59:58 PM, a Monday */
    CHECK("BCD, 12-hour: read back", rd(0) == 0x58 && rd(2) == 0x59 && rd(4) == 0x91 && rd(7) == 0x28 && rd(6) == 2);
    us(2000000);
    CHECK("2028 is a leap year: 02-29, 12 AM, day 3", rd(0) == 0 && rd(2) == 0 && rd(4) == 0x12 && rd(7) == 0x29 && rd(8) == 0x02 &&
          rd(9) == 0x28 && rd(6) == 3);
    us(12 * 3600 * 1000000LL); CHECK("noon is 12 PM", rd(4) == 0x92);
    us(3600 * 1000000LL);      CHECK("then 1 PM", rd(4) == 0x81);
    us(11 * 3600 * 1000000LL); CHECK("the day after the leap day: 03-01", rd(7) == 0x01 && rd(8) == 0x03 && rd(4) == 0x12);

    /* the calendar: a year that is not a leap year, and 99 to 00 */
    set(0x06, 27, 2, 28, 1, 23, 59, 59);
    us(1000000); CHECK("2027-02-28 is followed by 03-01", rd(7) == 1 && rd(8) == 3 && rd(9) == 27 && rd(4) == 0 && rd(6) == 2);
    set(0x06, 99, 12, 31, 7, 23, 59, 59);
    us(1000000); CHECK("2099-12-31 is followed by 00-01-01, day 1", rd(9) == 0 && rd(8) == 1 && rd(7) == 1 && rd(4) == 0 && rd(6) == 1);
    us(366 * 86400 * 1000000LL); CHECK("and 00 is a leap year", rd(9) == 1 && rd(8) == 1 && rd(7) == 1);

    /* SET holds the registers; the oscillator off (DV) holds them too, and the first update is 500 ms after it starts */
    set(0x06, 26, 11, 20, 6, 8, 0, 0);
    wr(0x0B, 0x86); us(5000000);
    CHECK("SET = 1: no update in 5 s", rd(0) == 0);
    wr(0x0B, 0x06); us(999999); CHECK("SET = 0: it counts from where it stood", rd(0) == 0);
    us(1);          CHECK("a second later", rd(0) == 1);
    wr(0x0A, 0x06); us(5000000);
    CHECK("DV = 000: the oscillator is off", rd(0) == 1 && rd(0x0A) == 0x06);
    wr(0x0A, 0x26); us(499999); CHECK("DV = 010: no update before 500 ms", rd(0) == 1);
    us(1);          CHECK("the update at 500 ms", rd(0) == 2);
    wr(0x0A, 0x66); us(3000000); CHECK("DV = 110: the divider held", rd(0) == 2);
    wr(0x0A, 0x26);

    /* a time byte written while it counts; the day of the week is a counter of its own */
    set(0x06, 26, 11, 20, 6, 8, 0, 10);
    us(250000); wr(2, 30);
    CHECK("minutes written while counting", rd(2) == 30 && rd(0) == 10 && rd(4) == 8);
    us(750000); CHECK("the second still ends when it would have", rd(0) == 11);
    wr(6, 3);   CHECK("the day of the week as written", rd(6) == 3 && rd(7) == 20);
    us(16 * 3600 * 1000000LL); CHECK("and it counts on at midnight", rd(6) == 4 && rd(7) == 21);

    /* the RAM: 114 bytes, $32 among them; C and D cannot be written */
    for (int r = 0x0E; r < 0x80; r++) wr(r, r ^ 0x5A);
    int ok = 1;
    for (int r = 0x0E; r < 0x80; r++) if (rd(r) != (uint8_t)(r ^ 0x5A)) ok = 0;
    CHECK("114 bytes of RAM", ok && rd(0x32) == (0x32 ^ 0x5A));
    wr(0x0D, 0x00); wr(0x0C, 0xFF);
    CHECK("C and D are read only", rd(0x0D) == 0x80 && (rd(0x0C) & 0x0F) == 0);
    CHECK("the time is not the RAM", rd(9) == 26 && rd(8) == 11);

    /* register C: PF by the rate, UF each second, AF at the alarm, IRQF by the enables; the read clears */
    set(0x06, 26, 11, 20, 6, 8, 0, 0);
    rd(0x0C);
    us(100);     CHECK("nothing 100 us into a second", rd(0x0C) == 0);
    us(900);     CHECK("PF after a period of 1024 Hz", rd(0x0C) == 0x40);
    CHECK("the read cleared it", rd(0x0C) == 0);
    us(1000000); CHECK("UF and PF after a second", rd(0x0C) == 0x50);
    wr(0x0A, 0x20); us(1000000);
    CHECK("no rate: UF alone", rd(0x0C) == 0x10);
    wr(0x0A, 0x2F); us(400000); CHECK("2 Hz: nothing in 0.4 s", rd(0x0C) == 0);
    us(200000);                 CHECK("2 Hz: PF at the half second", rd(0x0C) == 0x40);
    wr(0x0A, 0x20);
    set(0x16, 26, 11, 20, 6, 8, 0, 0);                      /* UIE */
    us(1000000); CHECK("UIE: IRQF with UF", rd(0x0C) == 0x90);
    set(0x06, 26, 11, 20, 6, 8, 0, 0);
    wr(1, 3); wr(3, 0); wr(5, 8);                           /* the alarm: 08:00:03 */
    us(2000000); CHECK("no alarm at 08:00:02", rd(0x0C) == 0x10);
    us(1000000); CHECK("the alarm at 08:00:03", rd(0x0C) == 0x30);
    us(1000000); CHECK("and not the second after", rd(0x0C) == 0x10);
    wr(1, 0xFF); wr(3, 0xC0); wr(5, 0xFF);
    us(1000000); CHECK("three bytes of $C0-$FF: every second", rd(0x0C) == 0x30);
    wr(0x0B, 0x26); us(1000000);
    CHECK("AIE: IRQF with AF", rd(0x0C) == 0xB0);
    wr(3, 5);
    us(3600 * 1000000LL); CHECK("a second of minute 5 passed in that hour", (rd(0x0C) & 0x20) != 0);
    us(60 * 1000000LL);   CHECK("and none in minute 6", (rd(0x0C) & 0x20) == 0);

    /* the CPU clock: at 2 MHz a second is two million clocks */
    setenv("Y1_CLOCK", "2000000", 1);
    start("v1.2", "2026-11-20 12:34:56", NULL);
    us(1999999); CHECK("2 MHz: 1,999,999 clocks", rd(0) == 56);
    us(1);       CHECK("2 MHz: 2,000,000 clocks are a second", rd(0) == 57);
    unsetenv("Y1_CLOCK");

    /* a chip that was never set */
    start("1.2", "2026-11-20 12:34:56", "1");
    CHECK("new: the oscillator off, BCD and 12-hour, the cell good", rd(0x0A) == 0 && rd(0x0B) == 0 && rd(0x0D) == 0x80);
    us(3000000); CHECK("new: it does not count", rd(0) == 0 && rd(2) == 0 && rd(0x0C) == 0);
    wr(0x0B, 0x86);
    wr(9, 26); wr(8, 11); wr(7, 20); wr(6, 6); wr(4, 9); wr(2, 15); wr(0, 0);
    wr(0x0A, 0x26); wr(0x0B, 0x06);
    us(1000000); CHECK("new: set and started, it counts", rd(0) == 1 && rd(2) == 15 && rd(4) == 9 && rd(7) == 20);

    /* the host's clock: the Mac's local time, within two seconds */
    start("v1.2", NULL, NULL);
    time_t now = time(NULL); struct tm tm; localtime_r(&now, &tm);
    int chip = rd(4) * 3600 + rd(2) * 60 + rd(0), host = tm.tm_hour * 3600 + tm.tm_min * 60 + tm.tm_sec;
    int diff = (chip - host + 86400 + 43200) % 86400 - 43200;
    CHECK("the host's time of day", !rtc.fixed && diff >= -2 && diff <= 2);
    CHECK("the host's date", (rd(9) == tm.tm_year % 100 && rd(8) == tm.tm_mon + 1 && rd(7) == tm.tm_mday && rd(6) == tm.tm_wday + 1) ||
          host < 3 || host > 86396);

    printf("rtc model: %d failed\n", fails);
    return fails != 0;
}

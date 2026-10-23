/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/*
   video-ps2 (2026-10-22) - the PS/2 keyboard and mouse controller of the YACC1 video card V2.0
   (hardware/cards/video/kicad/v2.0, BACKLOG "Video card V2.0", embedded/video-ps2/README.md).
   Revised 2026-10-22 after the design review (hardware/DESIGN-REVIEW-video-v2.0.md): BUSY and SRC swapped (V2-1,
   Optiboot's LED pin PB5 is now the SRC output), host-to-device bit count (V2-3), LDDATA idle high (V2-7), MD released
   with pull-ups (V2-9), the V2-18 robustness items. 2026-10-23 after the re-review (hardware/DESIGN-REVIEW-video-v2.0-r2.md
   R2-10): ps2_wait() takes only reply bytes; a key typed while a command waits for its answer goes to the key queue.

   An ATmega328P at 16 MHz between two PS/2 jacks and the YACC1 bus. The CPU never talks to it directly: it reads and
   writes three latches on the card (so a 1 MHz CPU never waits for this firmware):
     IN PE   a 74LS374 the firmware loads (MD0..7 + LDDATA); loading it sets FULL, the CPU's read clears FULL
     IN PD   status (a 74LS244): bit 0 FULL, bit 1 SRC (this pin: 0 keyboard, 1 mouse), bit 2 BUSY
     OUT PD  a 74LS374 the CPU loads (sets BUSY); the firmware reads it onto MD0..7 with -RDCMD, which clears BUSY

   Pins (Arduino Uno numbering = the ATmega328P's port pins):
     D0 / D1   PD0 RXD / PD1 TXD     the FTDI header J4 (bootloader, debug console 38400 8N1)
     D2        PD2 INT0              keyboard CLOCK (J2 pin 5, 4.7k pull-up)
     D3        PD3 INT1              mouse CLOCK (J3 pin 5)
     D4        PD4                   keyboard DATA (J2 pin 1)
     D5        PD5                   mouse DATA (J3 pin 1)
     D6        PD6  LDDATA  out      idle high (10k pull-up R22); a low pulse: the data latch takes MD0..7 and FULL
                                     sets on its rising edge
     D7        PD7  -RDCMD  out      low: the command latch drives MD0..7 (and BUSY clears); 10k pull-up R23
     A0..A5    PC0..PC5  MD0..MD5    the local bus (both directions)
     D8, D9    PB0, PB1  MD6, MD7
     D10       PB2  FULL    in       1 = the CPU has not read the last byte yet
     D11       PB3  BUSY    in       1 = the CPU wrote a command (OUT PD) the firmware has not read yet
     D12       PB4  INTREQ  out      1 = request -INT: the card ANDs it with FULL (IC54/B) into IC27/D (open
                                     collector) and jumper JP3 INT-EN; 10k pull-down R24
     D13       PB5  SRC     out      0 = the byte in the data latch is from the keyboard, 1 = from the mouse
                                     (PB5 is the Uno bootloader's LED pin: it may flash during Optiboot, harmless on
                                     SRC, which only matters with FULL)
   The PS/2 lines are open drain: a pin is either an input (the 4.7k pull-up makes 1) or an output driving 0.

   Commands (OUT PD): $01 interrupts on, $02 off, $03 acknowledge (-INT released until the next byte), $04 mouse on
   (reset + enable data reporting), $05 mouse off, $06 flush both queues, $07 keyboard reset, $10-$17 keyboard LEDs
   (bit 0 scroll, 1 num, 2 caps lock), $FF start again (as after a reset). The bus -RESET resets the ATmega (through
   IC27/E,F, open collector: the bus line only ever pulls MRST down).
   The CPU's side (the driver rule, R2-10): IN PE only after IN PD showed FULL = 1. feed_cpu() checks FULL a few
   microseconds after each load and loads the byte again if FULL did not set (a read strobe overlapped the load); a
   CPU that read PE without waiting for FULL could clear it inside that check and get the byte twice.
   Keyboard bytes are ASCII (set-2 scan codes translated: shift, caps lock, ctrl, the keypad, arrows and the editing
   keys as VT100 sequences ESC [ A..D / H / F / 5~ / 6~, Delete $7F); mouse bytes are its 3-byte packets, raw and
   whole (a packet is queued only when all three bytes are in).
*/

#define KCLK 2
#define MCLK 3
#define KDAT 4
#define MDAT 5
#define LDDATA 6
#define RDCMD 7
#define PIN_FULL 10
#define PIN_BUSY 11                    // V2-1: BUSY on PB3, SRC on PB5 (Optiboot's LED pin)
#define PIN_INTREQ 12
#define PIN_SRC 13

#define QSIZE 64                      // the queue to the CPU: (byte, source) pairs
#define RXSIZE 64                     // each port's receive ring (64: the mouse's packets during LED commands)
#define FRAME_TIMEOUT_US 2000UL       // a gap this long between clock edges restarts the frame

// ---------------------------------------------------------------- the two PS/2 ports (interrupt side)
struct Ps2 {
  uint8_t clk, dat;
  volatile uint8_t n, bits, ones, sending, sendbyte, sendparity, ack;
  volatile uint32_t last;
  volatile uint8_t rx[RXSIZE];
  volatile uint8_t head, tail, errors;
  uint8_t held[16], nh;                           // bytes that arrived while a command waited for its reply (R2-10)
};
Ps2 kb = {KCLK, KDAT}, ms = {MCLK, MDAT};

static inline void ps2_edge(Ps2 &p) {             // called on every falling clock edge
  uint8_t d = digitalRead(p.dat);                 // the data bit first: it is valid only while the clock is low
  uint32_t now = micros();
  if (now - p.last > FRAME_TIMEOUT_US) p.n = 0;   // a stray or broken frame: start again
  p.last = now;
  if (p.sending) {                                // host to device: put the next bit while the clock is low
    if (p.n < 8) { if ((p.sendbyte >> p.n) & 1) pinMode(p.dat, INPUT); else { pinMode(p.dat, OUTPUT); digitalWrite(p.dat, LOW); } }
    else if (p.n == 8) { if (p.sendparity) pinMode(p.dat, INPUT); else { pinMode(p.dat, OUTPUT); digitalWrite(p.dat, LOW); } }
    else if (p.n == 9) pinMode(p.dat, INPUT);     // stop bit: released
    else { p.ack = (d == 0) ? 1 : 2; p.sending = 0; p.n = 0; return; }   // the device's acknowledge bit
    p.n++;
    return;
  }
  if (p.n == 0) { if (d) return; p.bits = 0; p.ones = 0; }               // the start bit must be 0
  else if (p.n <= 8) { p.bits |= d << (p.n - 1); p.ones += d; }
  else if (p.n == 9) { p.ones += d; }                                     // odd parity over data + parity
  else {                                                                  // the stop bit
    if (d && (p.ones & 1)) {
      uint8_t h = (p.head + 1) % RXSIZE;
      if (h != p.tail) { p.rx[p.head] = p.bits; p.head = h; }
    } else p.errors++;
    p.n = 0;
    return;
  }
  p.n++;
}
void kb_isr() { ps2_edge(kb); }
void ms_isr() { ps2_edge(ms); }

int ps2_get(Ps2 &p) {                            // the next received byte, or -1
  if (p.head == p.tail) return -1;
  uint8_t b = p.rx[p.tail];
  p.tail = (p.tail + 1) % RXSIZE;
  return b;
}

bool ps2_send(Ps2 &p, uint8_t b) {               // host to device; true when the device acknowledged
  uint8_t ones = 0;
  for (uint8_t i = 0; i < 8; i++) ones += (b >> i) & 1;
  // Request to send: the clock low for 120 us. INT0/INT1 fire on this, the host's own falling edge (they trigger on
  // output pins too), so the transmitter is armed only afterwards: the edge reaches the receive side with the data
  // line released (high) and is ignored there (V2-3; armed first, it was counted as the device's first clock and
  // every byte went out one bit late).
  digitalWrite(p.clk, LOW); pinMode(p.clk, OUTPUT);
  delayMicroseconds(120);
  noInterrupts();
  p.sendbyte = b; p.sendparity = (ones & 1) ? 0 : 1; p.ack = 0; p.n = 0; p.sending = 1;
  interrupts();
  digitalWrite(p.dat, LOW); pinMode(p.dat, OUTPUT);        // the start bit
  pinMode(p.clk, INPUT);                                   // released: a rising edge; the device now clocks the bits in
  uint32_t t0 = millis();
  while (p.sending && millis() - t0 < 20) ;
  pinMode(p.dat, INPUT);
  bool ok = p.ack == 1;
  noInterrupts(); p.sending = 0; p.n = 0; interrupts();
  return ok;
}

int ps2_next(Ps2 &p) {                           // the main loop's next byte: the held ones first, in order
  if (p.nh) {
    uint8_t b = p.held[0];
    for (uint8_t i = 1; i < p.nh; i++) p.held[i - 1] = p.held[i];
    p.nh--;
    return b;
  }
  return ps2_get(p);
}

static inline bool ps2_is_reply(uint8_t b) {    // what a device sends in answer to the host: acknowledge, resend,
  return b == 0xFA || b == 0xFE || b == 0xEE || b == 0xAA || b == 0xFC || b == 0x00;   // echo, BAT ok / failed, ID
}

int ps2_wait(Ps2 &p, uint16_t ms) {             // the next REPLY byte within ms, or -1 (R2-10): a scan code or a
  uint32_t t0 = millis();                       // mouse packet byte that arrives meanwhile is held for the main loop
  int b;
  do {
    while ((b = ps2_get(p)) >= 0) {
      if (ps2_is_reply(b)) return b;
      if (p.nh < sizeof p.held) p.held[p.nh++] = b;
    }
  } while (millis() - t0 < ms);
  return -1;
}

bool ps2_command(Ps2 &p, uint8_t b) {             // send and expect $FA (acknowledge), one retry on $FE (resend);
  for (uint8_t i = 0; i < 2; i++) {               // another reply byte (a stray $AA / $00) is skipped, for 50 ms
    if (!ps2_send(p, b)) continue;
    uint32_t t0 = millis();
    int r;
    do r = ps2_wait(p, 50); while (r >= 0 && r != 0xFA && r != 0xFE && millis() - t0 < 50);
    if (r == 0xFA) return true;
    if (r != 0xFE) return false;
  }
  return false;
}

// ---------------------------------------------------------------- the queue to the CPU and the bus latches
uint8_t qbyte[QSIZE], qsrc[QSIZE], qh, qt;
bool int_on, acked, mouse_on, debug_on;

uint8_t qfree() { return (qt + QSIZE - qh - 1) % QSIZE; }
void qput(uint8_t b, uint8_t src) {
  if (!qfree()) return;
  qbyte[qh] = b; qsrc[qh] = src; qh = (qh + 1) % QSIZE;
  acked = false;                                  // a new byte asks for attention again
}

void md_write(uint8_t b) {
  DDRC |= 0x3F; DDRB |= 0x03;
  PORTC = (PORTC & 0xC0) | (b & 0x3F);
  PORTB = (PORTB & 0xFC) | (b >> 6);
}

void md_release() { DDRC &= 0xC0; DDRB &= 0xFC; PORTC |= 0x3F; PORTB |= 0x03; }   // inputs with pull-ups (V2-9)

uint8_t read_command() {                          // the command latch onto MD (and BUSY cleared)
  md_release();
  digitalWrite(RDCMD, LOW);
  delayMicroseconds(1);
  uint8_t b = (PINC & 0x3F) | ((PINB & 0x03) << 6);
  digitalWrite(RDCMD, HIGH);
  return b;
}

void feed_cpu() {                                 // the next queued byte into the data latch once the CPU took the last
  if (qh == qt || digitalRead(PIN_FULL)) return;
  delayMicroseconds(5);                           // FULL is held clear while the CPU's read strobe lasts: INP holds
  if (digitalRead(PIN_FULL)) return;              // -IO-RD 7 clocks (7 us at 1 MHz); a load inside it is caught below
  digitalWrite(PIN_SRC, qsrc[qt]);
  md_write(qbyte[qt]);
  delayMicroseconds(1);
  digitalWrite(LDDATA, LOW);                      // LDDATA idles high (V2-7): a low pulse,
  delayMicroseconds(1);
  digitalWrite(LDDATA, HIGH);                     // the 74LS374 and FULL take the byte on its rising edge
  md_release();
  if (digitalRead(PIN_FULL)) qt = (qt + 1) % QSIZE;   // else a read strobe overlapped: load it again next time
}

// ---------------------------------------------------------------- keyboard: set-2 scan codes -> ASCII
const uint8_t PROGMEM kmap[][3] = {           // {set-2 code, unshifted, shifted}
  {0x0D, 9, 9}, {0x0E, '`', '~'}, {0x15, 'q', 'Q'}, {0x16, '1', '!'}, {0x1A, 'z', 'Z'},
  {0x1B, 's', 'S'}, {0x1C, 'a', 'A'}, {0x1D, 'w', 'W'}, {0x1E, '2', '@'}, {0x21, 'c', 'C'},
  {0x22, 'x', 'X'}, {0x23, 'd', 'D'}, {0x24, 'e', 'E'}, {0x25, '4', '$'}, {0x26, '3', '#'},
  {0x29, ' ', ' '}, {0x2A, 'v', 'V'}, {0x2B, 'f', 'F'}, {0x2C, 't', 'T'}, {0x2D, 'r', 'R'},
  {0x2E, '5', '%'}, {0x31, 'n', 'N'}, {0x32, 'b', 'B'}, {0x33, 'h', 'H'}, {0x34, 'g', 'G'},
  {0x35, 'y', 'Y'}, {0x36, '6', '^'}, {0x3A, 'm', 'M'}, {0x3B, 'j', 'J'}, {0x3C, 'u', 'U'},
  {0x3D, '7', '&'}, {0x3E, '8', '*'}, {0x41, ',', '<'}, {0x42, 'k', 'K'}, {0x43, 'i', 'I'},
  {0x44, 'o', 'O'}, {0x45, '0', ')'}, {0x46, '9', '('}, {0x49, '.', '>'}, {0x4A, '/', '?'},
  {0x4B, 'l', 'L'}, {0x4C, ';', ':'}, {0x4D, 'p', 'P'}, {0x4E, '-', '_'}, {0x52, '\'', '"'},
  {0x54, '[', '{'}, {0x55, '=', '+'}, {0x5A, 13, 13}, {0x5B, ']', '}'},
  {0x5D, '\\', '|'}, {0x66, 8, 8}, {0x76, 27, 27}, {0x7C, '*', '*'}, {0x7B, '-', '-'},
  {0x79, '+', '+'},
};
// the keypad's digit keys: [code] = {digit (Num Lock on), navigation key (off)}
enum { K_NONE, K_UP, K_DOWN, K_LEFT, K_RIGHT, K_HOME, K_END, K_PGUP, K_PGDN, K_INS, K_DEL };
const uint8_t kpad[][3] = { {0x70, '0', K_INS}, {0x69, '1', K_END}, {0x72, '2', K_DOWN}, {0x7A, '3', K_PGDN},
                            {0x6B, '4', K_LEFT}, {0x73, '5', K_NONE}, {0x74, '6', K_RIGHT}, {0x6C, '7', K_HOME},
                            {0x75, '8', K_UP}, {0x7D, '9', K_PGUP}, {0x71, '.', K_DEL} };
bool lshift, rshift, lctrl, rctrl, caps, num, scroll, brk, ext;
uint8_t skip;                                     // bytes of a Pause sequence (E1 ...) still to swallow

void send_leds() {
  if (ps2_command(kb, 0xED)) ps2_command(kb, (scroll ? 1 : 0) | (num ? 2 : 0) | (caps ? 4 : 0));
}

void key_nav(uint8_t k) {                         // the editing keys as VT100 sequences
  const char *s = 0;
  switch (k) {
    case K_UP: s = "\x1b[A"; break;   case K_DOWN: s = "\x1b[B"; break;  case K_RIGHT: s = "\x1b[C"; break;
    case K_LEFT: s = "\x1b[D"; break; case K_HOME: s = "\x1b[H"; break;  case K_END: s = "\x1b[F"; break;
    case K_PGUP: s = "\x1b[5~"; break; case K_PGDN: s = "\x1b[6~"; break; case K_DEL: qput(0x7F, 0); return;
    default: return;
  }
  if (qfree() < 4) return;                        // a sequence goes in whole or not at all
  while (*s) qput(*s++, 0);
}

void keyboard_byte(uint8_t c) {
  if (skip) { skip--; return; }
  if (c == 0xE1) { skip = 7; return; }            // Pause/Break: E1 14 77 E1 F0 14 F0 77
  if (c == 0xE0) { ext = true; return; }
  if (c == 0xF0) { brk = true; return; }
  if (c == 0xAA || c == 0xFA || c == 0xEE || c >= 0xFC) { brk = ext = false; return; }   // BAT, acks, errors
  bool up = brk, e = ext;
  brk = ext = false;
  if (c == 0x12 && e) return;                     // Print Screen's fake shifts
  if (c == 0x12) { lshift = !up; return; }
  if (c == 0x59 && !e) { rshift = !up; return; }   // (E0 59 is a fake shift)
  if (c == 0x14) { if (e) rctrl = !up; else lctrl = !up; return; }
  if (c == 0x11) return;                          // Alt: no meaning here
  if (up) return;                                 // other releases: nothing
  if (c == 0x58) { caps = !caps; send_leds(); return; }
  if (c == 0x77) { num = !num; send_leds(); return; }
  if (c == 0x7E && !e) { scroll = !scroll; send_leds(); return; }   // E0 7E is Ctrl-Break, not Scroll Lock
  if (e) {
    switch (c) {
      case 0x75: key_nav(K_UP); return;   case 0x72: key_nav(K_DOWN); return;
      case 0x6B: key_nav(K_LEFT); return; case 0x74: key_nav(K_RIGHT); return;
      case 0x6C: key_nav(K_HOME); return; case 0x69: key_nav(K_END); return;
      case 0x7D: key_nav(K_PGUP); return; case 0x7A: key_nav(K_PGDN); return;
      case 0x71: key_nav(K_DEL); return;
      case 0x4A: qput('/', 0); return;            // keypad /
      case 0x5A: qput(13, 0); return;             // keypad Enter
      default: return;                            // GUI, menu, Insert, Print Screen ...
    }
  }
  for (uint8_t i = 0; i < sizeof kpad / sizeof kpad[0]; i++)
    if (kpad[i][0] == c) { if (num) qput(kpad[i][1], 0); else key_nav(kpad[i][2]); return; }
  bool shift = lshift || rshift;
  uint8_t ch = 0;
  for (uint8_t i = 0; i < sizeof kmap / sizeof kmap[0]; i++)
    if (pgm_read_byte(&kmap[i][0]) == c) { ch = pgm_read_byte(&kmap[i][shift ? 2 : 1]); break; }
  if (!ch) return;
  if (caps && ch >= 'a' && ch <= 'z') ch -= 32;
  else if (caps && shift && ch >= 'A' && ch <= 'Z') ch += 32;
  if ((lctrl || rctrl) && ch >= '@' && ch <= '~') ch &= 0x1F;
  qput(ch, 0);
}

void keyboard_reset() {
  lshift = rshift = lctrl = rctrl = caps = num = scroll = brk = ext = false; skip = 0;
  if (ps2_command(kb, 0xFF)) ps2_wait(kb, 1000);  // the self-test answer ($AA)
  send_leds();
}

// ---------------------------------------------------------------- mouse: reset, enable reporting, whole packets
uint8_t mpkt[3], mn;

bool mouse_start() {
  mn = 0;
  if (!ps2_command(ms, 0xFF)) return false;       // reset: $FA, then $AA and the device ID $00
  if (ps2_wait(ms, 1000) != 0xAA) return false;
  ps2_wait(ms, 100);
  return ps2_command(ms, 0xF4);                   // enable data reporting
}

void mouse_byte(uint8_t b) {
  if (!mouse_on) return;
  if (mn == 0 && !(b & 0x08)) return;             // byte 1 always has bit 3 set: resynchronise
  mpkt[mn++] = b;
  if (mn == 3) {
    mn = 0;
    if (qfree() >= 3) { qput(mpkt[0], 1); qput(mpkt[1], 1); qput(mpkt[2], 1); }
  }
}

// ---------------------------------------------------------------- commands from the CPU
void start_all() {
  qh = qt = 0; int_on = false; acked = false;
  keyboard_reset();
  mouse_on = mouse_start();
  Serial.print(F("video-ps2: keyboard ready, mouse ")); Serial.println(mouse_on ? F("on") : F("absent"));
}

void command(uint8_t c) {
  if (debug_on) { Serial.print(F("cmd ")); Serial.println(c, HEX); }
  if (c == 0x01) int_on = true;
  else if (c == 0x02) int_on = false;
  else if (c == 0x03) acked = true;
  else if (c == 0x04) mouse_on = mouse_start();
  else if (c == 0x05) { mouse_on = false; ps2_command(ms, 0xF5); }
  else if (c == 0x06) { noInterrupts(); kb.head = kb.tail; ms.head = ms.tail; interrupts(); kb.nh = ms.nh = 0; qh = qt; mn = 0; }
  else if (c == 0x07) keyboard_reset();
  else if ((c & 0xF8) == 0x10) { scroll = c & 1; num = c & 2; caps = c & 4; send_leds(); }
  else if (c == 0xFE) debug_on = !debug_on;       // the FTDI console shows commands and bytes
  else if (c == 0xFF) start_all();
}

void setup() {
  Serial.begin(38400);
  pinMode(KCLK, INPUT); pinMode(KDAT, INPUT); pinMode(MCLK, INPUT); pinMode(MDAT, INPUT);   // released: the pull-ups
  digitalWrite(LDDATA, HIGH); pinMode(LDDATA, OUTPUT);     // idle high, as the pull-up held it through the reset
  digitalWrite(RDCMD, HIGH); pinMode(RDCMD, OUTPUT);
  pinMode(PIN_FULL, INPUT); pinMode(PIN_BUSY, INPUT);
  pinMode(PIN_SRC, OUTPUT); pinMode(PIN_INTREQ, OUTPUT); digitalWrite(PIN_INTREQ, LOW);
  md_release();
  attachInterrupt(digitalPinToInterrupt(KCLK), kb_isr, FALLING);
  attachInterrupt(digitalPinToInterrupt(MCLK), ms_isr, FALLING);
  Serial.println(F("video-ps2 2026-10-23"));
  if (digitalRead(PIN_BUSY)) read_command();      // a command latched before a reset: dropped
  start_all();
}

void loop() {
  int b;
  while ((b = ps2_next(kb)) >= 0) { if (debug_on) { Serial.print(F("kb ")); Serial.println(b, HEX); } keyboard_byte(b); }
  while ((b = ps2_next(ms)) >= 0) mouse_byte(b);
  if (digitalRead(PIN_BUSY)) command(read_command());
  feed_cpu();
  digitalWrite(PIN_INTREQ, int_on && !acked && digitalRead(PIN_FULL));
}

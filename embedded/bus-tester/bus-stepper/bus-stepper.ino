/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/*
   BUS Stepper (2026-10-10)

   The bus tester as a single-step clock that reads the whole bus after every edge. Everything is read as in
   bus-monitor (every MCP23017 pin an input with its 100K pull-up), except IC6 (MCP 5) GPA4, the OUT-LED pin, which
   becomes the clock output. OUT-LED drives only the card's own LED through R16, so the pin is free; a jumper takes
   it to the sequencer's JP4 pin 2 (EXTERNAL-SINGLESTEP-CLK) with SS-SEL on 2-3 and the SS/WAIT toggle on SS. With
   the toggle on FREERUN the machine runs from its oscillator as usual, so a program can be started at full speed and
   then stepped from wherever it is.

   Serial 115200, one command per line (CR or LF):
     p              print the bus
     t              one clock edge, print
     n N            N edges, print after each
     q N            N edges, print after the last only
     l 0|1          set the clock level without counting an edge
     f AAAA,BB[,M]  step (at most M edges, default 20000) until -MEM-RD is asserted with address AAAA and DATA0..7
                    = BB (an opcode fetch), print; "notfound" otherwise
   Bus line: "E=edges K=clk A=aaaa D=dddd 2=xxxx 3=xxxx 4=xxxx 5=xxxx" - the raw 16-bit GPIO of MCP 0 (address),
   1 (data) and 2..5 (control lines, as YACC_Common_header.h maps them); tools/busstep.py decodes it.
*/

#include <Wire.h>
#include "Adafruit_MCP23017.h"
#include "YACC_Common_header.h"

#define BANNER "bus-stepper 2026-10-10"
#define CLK_CHIP 5
#define CLK_PIN 4             /* GPA4 = OUT-LED */

Adafruit_MCP23017 mcp[NUMBER_OF_CONTROLLERS];
unsigned int cur[NUMBER_OF_CONTROLLERS];
unsigned long edges = 0;
int clk = 0;
int memrdChip = -1, memrdBit = 0;
char line[40];
int len = 0;

void readBus() {
  for (int i = 0; i < NUMBER_OF_CONTROLLERS; i++) cur[i] = mcp[i].readGPIOAB();
}

void printBus() {
  char tmp[80];
  sprintf(tmp, "E=%lu K=%d A=%04X D=%04X 2=%04X 3=%04X 4=%04X 5=%04X", edges, clk, cur[0], cur[1], cur[2], cur[3],
          cur[4], cur[5]);
  Serial.println(tmp);
}

void edge() {
  clk = !clk;
  mcp[CLK_CHIP].digitalWrite(CLK_PIN, clk);
  edges++;
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(400000);
  for (int i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
    mcp[i].begin(i);
    for (int j = 0; j < BITS_PER_CONTROLLER; j++) {
      mcp[i].pinMode(j, INPUT);
      mcp[i].pullUp(j, HIGH);
    }
  }
  mcp[CLK_CHIP].digitalWrite(CLK_PIN, 0);
  mcp[CLK_CHIP].pinMode(CLK_PIN, OUTPUT);
  for (int i = 0; strlen(opcodes[i].code) > 0; i++)
    if (strcmp(opcodes[i].code, "-MEM-RD") == 0) {
      memrdChip = opcodes[i].chip; memrdBit = opcodes[i].port * PINS_PER_PORT + opcodes[i].pin;
    }
  Serial.println(F(BANNER));
  Serial.println(F(">>"));
}

void command(char *c) {
  char op = c[0];
  long n = atol(c + 1);
  if (op == 'p') { readBus(); printBus(); }
  else if (op == 't') { edge(); readBus(); printBus(); }
  else if (op == 'n') { for (long k = 0; k < n; k++) { edge(); readBus(); printBus(); } }
  else if (op == 'q') { for (long k = 0; k < n; k++) edge(); readBus(); printBus(); }
  else if (op == 'l') { clk = n ? 1 : 0; mcp[CLK_CHIP].digitalWrite(CLK_PIN, clk); readBus(); printBus(); }
  else if (op == 'f') {
    unsigned int addr = strtoul(c + 1, NULL, 16);
    char *p = strchr(c, ',');
    unsigned int data = p ? strtoul(p + 1, NULL, 16) : 0;
    char *p2 = p ? strchr(p + 1, ',') : NULL;
    long max = p2 ? atol(p2 + 1) : 20000;
    for (long k = 0; k < max; k++) {
      edge();
      readBus();
      bool rd = memrdChip >= 0 && !(cur[memrdChip] & (1u << memrdBit));
      if (rd && cur[ADDRESS_CHIP] == addr && (cur[DATA_CHIP] & 0xFF) == data) { printBus(); return; }
    }
    readBus(); Serial.print(F("notfound ")); printBus();
  }
  else Serial.println(F("? p t nN qN l0|1 fAAAA,BB[,M]"));
}

void loop() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\r' || ch == '\n') {
      if (len) { line[len] = 0; command(line); Serial.println(F(">>")); len = 0; }
    } else if (len < (int)sizeof(line) - 1) line[len++] = ch;
  }
}

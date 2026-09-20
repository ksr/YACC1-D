
/*
   SET ARDUINO MONITOR TO "No Line Ending"

   Command Format  CMD:OPERAND#
   EX: REG-FUNC:1#

   0 is off
   1 is on

   this program adjusts for active low vs active high

   SERIAL MONITOR NO LINE ENDING

*/

#include <Wire.h>
#include "Adafruit_MCP23017.h"
#include <avr/pgmspace.h>

//#define DEBUG

#define NUMBER_OF_CONTROLLERS 6
#define PINS_PER_PORT 8
#define PORTS_PER_CONTROLLER 2
#define ACTIVE_LOW 8 /* add 8 to pin number to signify active low signal */

#define ADDRESS_CHIP 0
#define DATA_CHIP 1

#define SPECIAL_OPCODE 9

Adafruit_MCP23017 mcp[NUMBER_OF_CONTROLLERS];

String command = "";
boolean commandReady = false;
//String result = "Result: ";
String result = "";

typedef struct {
  char const *code;
  char chip;
  char port;
  char pin;
} opcode;

const opcode opcodes[]  = {
  //  "A0", 0, 0, 0,
  //  "A1", 0, 0, 1,
  //  "A2", 0, 0, 2,
  //  "A3", 0, 0, 3,
  //  "A4", 0, 0, 4,
  //  "A5", 0, 0, 5,
  //  "A6", 0, 0, 6,
  //  "A7", 0, 0, 7,
  //  "A8", 0, 1, 0,
  //  "A9", 0, 1, 1,
  //  "A10", 0, 1, 2,
  //  "A11", 0, 1, 3,
  //  "A12", 0, 1, 4,
  //  "A13", 0, 1, 5,
  //  "A14", 0, 1, 6,
  //  "A15", 0, 1, 7,
  //  "D0", 1, 0, 0,
  //  "D1", 1, 0, 1,
  //  "D2", 1, 0, 2,
  //  "D3", 1, 0, 3,
  //  "D4", 1, 0, 4,
  //  "D5", 1, 0, 5,
  //  "D6", 1, 0, 6,
  //  "D7", 1, 0, 7,
  //  "D8", 1, 1, 0,
  //  "D9", 1, 1, 1,
  //  "D10", 1, 1, 2,
  //  "D11", 1, 1, 3,
  //  "D12", 1, 1, 4,
  //  "D13", 1, 1, 5,
  //  "D14", 1, 1, 6,
  //  "D15", 1, 1, 7,

  "REG-FUNC-LD", 2, 0, 0,
  "REG-FUNC-RD", 2, 0, 1,

  "REG-BRD-RD-ID", 2, 0, 5,
  "REG-RD-ID0", 2, 0, 6,
  "REG-RD-ID1", 2, 0, 7,
  "REG-RD-ID2", 2, 1, 0,
  "REG-BRD-LD-ID", 2, 1, 1,
  "REG-LD-ID0", 2, 1, 2,
  "REG-LD-ID1", 2, 1, 3,
  "REG-LD-ID2", 2, 1, 4,
  "REG-RD-LO", 2, 1, 5,
  "REG-LD-LO", 2, 1, 6,
  "REG-RD-HI", 2, 1, 7,
  "REG-LD-HI", 3, 0, 0,
  "MEM-WR", 3, 0, 1,
  "MEM-RD", 3, 0, 2,
  "I/O-WR", 3, 0, 3,
  "I/O-RD", 3, 0, 4,
  "I/O-ADDR", 3, 0, 5,
  "INT", 3, 0, 6,
  "INTA", 3, 0, 7,
  "I/D-REG-LD", 3, 1, 0,
  "I/D-REG-RD", 3, 1, 1,
  "I/D-REG-DN", 3, 1, 2,
  "I/D-REG-UP", 3, 1, 3,
  "SP/PC-SEL", 3, 1, 4,
  "SP/PC-DATA-RD-LO", 3, 1, 5,
  "SP/PC-DATA-RD-HI", 3, 1, 6,
  "SP/PC-ADDR-RD", 3, 1, 7,
  "SP/PC-LD-LO", 4, 0, 0,
  "SP/PC-LD-HI", 4, 0, 1,
  "SP/PC-DN", 4, 0, 2,
  "SP/PC-UP", 4, 0, 3,
  "ALU-FUNC", 4, 0, 4,
  "ALU0", 4, 0, 5,
  "ALU1", 4, 0, 6,
  "ALU2", 4, 0, 7,
  "ALU3", 4, 1, 0,
  "AC-LD-INV", 4, 1, 1,
  "AC-LD", 4, 1, 2,
  "AC-RD", 4, 1, 3,
  "SR-LD", 4, 1, 4,
  "BR-COND", 4, 1, 5,
  "H/L-SWAP", 4, 1, 6,
  "IN", 4, 1, 7,
  "OUT", 5, 0, 0,

  "RUN", 5, 0, 2,
  "RESET", 5, 0, 3,
  "OUT-LED", 5, 0, 4,
  "IN-SWITCH", 5, 0, 5,
  "LEDS-LD", 5, 0, 6,
  "SWITCHES-RD", 5, 0, 7 + ACTIVE_LOW,

  "BIT0", 5, 1, 0,
  "BIT1", 5, 1, 1,
  "BIT2", 5, 1, 2,
  "BIT3", 5, 1, 3,
  "BIT4", 5, 1, 4,
  "BIT5", 5, 1, 5,
  "BIT6", 5, 1, 6,
  "BIT7", 5, 1, 7,

  "RDATA", SPECIAL_OPCODE, 0, 0,
  "WDATA", SPECIAL_OPCODE, 0, 0,
  "RDATAL", SPECIAL_OPCODE, 0, 0,
  "RDATAH", SPECIAL_OPCODE, 0, 0,
  "RADDR", SPECIAL_OPCODE, 0, 0,
  "WADDR", SPECIAL_OPCODE, 0, 0,
  "BUS-RD", SPECIAL_OPCODE, 0, 0,
  "BUS-WR", SPECIAL_OPCODE, 0, 0,
  "ADDR-RD", SPECIAL_OPCODE, 0, 0,
  "ADDR-WR", SPECIAL_OPCODE, 0, 0,
  "RBR-COND", SPECIAL_OPCODE, 0, 0,
  "", 0, 0, 0,
};



unsigned int previous[NUMBER_OF_CONTROLLERS];

void flash(int led) {
  digitalWrite(led, HIGH);
  delay(250);
  digitalWrite(led, LOW);
  delay(250);
}

String  strOpcode(int chip, int pinab) {
  int i;
  int port;
  int pin;

#ifdef DEBUG
  char tmp[100];
  sprintf(tmp, "strOpcode chip=%d, pinab=%d", chip, pinab);
  Serial.println(tmp);
#endif

  if (pinab >= PINS_PER_PORT) {
    port = 1;
    pin = pinab - PINS_PER_PORT;
  } else {
    port = 0;
    pin = pinab;
  }
  i = 0;
  while (strlen(opcodes[i].code) != 0 ) {
    if ((opcodes[i].chip == chip) &&
        (opcodes[i].port == port) &&
        (opcodes[i].pin == pin))
      return (opcodes[i].code);
    i++;
  }
  return ("YIKES NO OPCODE FOUND");

}

void setup() {
  int i, j, chip, pin;

  Serial.begin(19200);
  Serial.println("Setup Start");
  for (i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
    mcp[i].begin(i);      // use default address 0
    previous[i] = 0;

    for (j = 0; j < 16; j++) {
      mcp[i].pinMode(j, INPUT);
      mcp[i].pullUp(j, HIGH);  // turn on a 100K pullup internally
    }
  }

  for(i=9;i<=13;i++){
    pinMode(13,OUTPUT);
    flash(i);
  }

  
  Serial.println("Setup Done");
}
//#define DEBUG1
unsigned int current[NUMBER_OF_CONTROLLERS];
int loopcount = 0;
void loop() {
  bool changed;
  int i, j;
  char tmp[100];
  unsigned int mask;

  changed = false;

  for (i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
    current[i] = mcp[i].readGPIOAB();
    if (current[i] != previous[i]) {
      //Serial.println(i);
      changed = true;
    }
  }
  if (changed) {
    sprintf(tmp, "Address=%04x Data Hi=%02x Lo=%02x ",
            current[ADDRESS_CHIP], (current[DATA_CHIP] & 0xff00) >> 8 , current[DATA_CHIP] & 0x00ff);
    Serial.print(tmp);
    for (i = 2; i < NUMBER_OF_CONTROLLERS; i++) {
#ifdef DEBUG1
      sprintf(tmp, "C=%04x P=%04x ", current[i], previous[i]);
      Serial.print(tmp);
#endif
      mask = 0x0001;
      for (j = 0; j < 16; j++) {
        if ((current[i] & mask) != (previous[i] & mask)) {
          if (current[i] & mask) {
            sprintf(tmp, "(1)");
            Serial.print(tmp);
          }
          else {
            sprintf(tmp, "(0)");
            Serial.print(tmp);
          }
          Serial.print(strOpcode(i, j)); Serial.print(" ");
        }
        mask = mask << 1;
      }
    }
    Serial.println();
    for (i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
      previous[i] = current[i];
    }
  }
  //delay(1);
  //Serial.println();
#ifdef DEBUG
  if (loopcount++ > 3)
    while (1)
      delay(1000);
#endif
}

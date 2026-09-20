
/*
   SET ARDUINO MONITOR TO "No Line Ending"

   Command Format  CMD:OPERAND#
   EX: REG-FUNC:1#

   0 is off
   1 is on

   this program adjusts for active low vs active high

*/

#include <Wire.h>
#include "Adafruit_MCP23017.h"

#define NUMBER_OF_CONTROLERS 6
#define PINS_PER_PORT 8
#define PORTS_PER_CONTROLLER 2
#define ACTIVE_LOW 8 /* add 8 to pin number to signify active low signal */


#define ADDRESS_CHIP 0
#define DATA_CHIP 1

#define OPCODE_VALUE_SPLIT ":"
#define PROMPT ">>"

#define BUS_WRITE 1
#define BUS_READ 0

#define SPECIAL_OPCODE 9

Adafruit_MCP23017 mcp[NUMBER_OF_CONTROLERS];

String command = "";
boolean commandReady = false;
String result = "Result: ";

typedef struct {
  char const *code;
  char chip;
  char port;
  char pin;
} opcode;

opcode opcodes[] = {
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

  "REG-FUNC", 2, 0, 1,

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
  "ALU3", 4, 1, 0,    // added  use dir for now
  "AC-LD-INV", 4, 1, 1,
  "AC-LD", 4, 1, 2,
  "AC-RD", 4, 1, 3,
  "SR-LD", 4, 1, 4, // reuse of br-reg-ld-hi
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
  "RBR-COND", SPECIAL_OPCODE, 0, 0,
  "", 0, 0, 0,
};

unsigned int readData();
unsigned int readDataLo();
unsigned int readDataHi();
unsigned int  writeData(unsigned int);
unsigned int readAddress();
unsigned int writeAddress(unsigned int);
int busDir(int);
int busMode = 0;

void doError(String errorMsg) {
  Serial.print("Error: ");
  Serial.println(errorMsg);
  while (1);
}



int setCntlPin(int codeIndex, boolean state) {
  int chip, pin;
  chip = opcodes[codeIndex].chip;
  pin = opcodes[codeIndex].port * PINS_PER_PORT + opcodes[codeIndex].pin;
   if (opcodes[codeIndex].pin < ACTIVE_LOW) {
      mcp[chip].digitalWrite(pin, state);
    }
    else {
      mcp[chip].digitalWrite(pin, !state);
    }
  
}

/*
   Return index of opcode in opcodes array or -1 if not found
*/
int opLookUp(char *codeToLookup) {
  int i;

  i = 0;
  Serial.println(codeToLookup);
  while (strlen(opcodes[i].code) != 0 ) {
    //Serial.println(opcodes[i].code);
    if (!strcmp(codeToLookup, opcodes[i].code)) {
      return (i);
    }
    i++;
  }
  return (-1);
}


void setup() {
  int i, chip, pin;

  Serial.begin(9600);
  Serial.println("Setup Start");

  i = 0;
  while (strlen(opcodes[i].code) > 0) {
    chip = opcodes[i].chip;
    pin = opcodes[i].port * PINS_PER_PORT + opcodes[i].pin;
    mcp[chip].pinMode(pin, OUTPUT);
    mcp[chip].pullUp(pin, HIGH);  // turn on a 100K pullup internally
    if (opcodes[i].pin < ACTIVE_LOW) {
      mcp[chip].digitalWrite(pin, LOW);
    }
    else {
      mcp[chip].digitalWrite(pin, HIGH);
    }
    i++;
  }

  busMode = BUS_WRITE;
  //mcp[3].pinMode(15, INPUT);??
  Serial.println("Setup Done");
  Serial.println(PROMPT);
}


void loop() {
  int opcodeIndex;
  char mc[25];
  char opcode[20];
  int val;


  if (commandReady) {
    Serial.print("Command: ");
    Serial.println(command);

    command.toCharArray(mc, 20);  // convert input of Type String to char array

    int i = command.indexOf(OPCODE_VALUE_SPLIT); // find opcode/value

    Serial.print(i);

    strncpy(opcode, mc, i);
    opcode[i] = 0;

    val = atoi(&mc[i + 1]);


    Serial.print("Pin / Val: ");
    Serial.print(opcode);
    Serial.print(" / ");
    Serial.print(val);
    Serial.print("  code from lookup ");

    if ((opcodeIndex = opLookUp(opcode)) == -1)
      doError("Bad opcode");

    Serial.println(opcodes[opcodeIndex].code);

    if (opcodes[opcodeIndex].chip != SPECIAL_OPCODE) {
      setCntlPin(opcodeIndex, val);
      Serial.println("Complete");
    }
    else {
      Serial.print("Data: ");
      if (strcmp(opcode, "RDATA") == 0)
        Serial.println(result + String(readData()));
      else if (strcmp(opcode, "RDATAL") == 0)
        Serial.println(result + String(readDataLo()));
      else if (strcmp(opcode, "RDATAH") == 0)
        Serial.println(result + String(readDataHi()));
      else if (strcmp(opcode, "RBR-COND") == 0)
        Serial.println(result + String(mcp[3].digitalRead(15)));
      else if (strcmp(opcode, "WDATA") == 0)
        Serial.println(result + String(writeData(val)));
      else if (strcmp(opcode, "RADDR") == 0)
        Serial.println(result +  String(readAddress()));
      else if (strcmp(opcode, "WADDR") == 0)
        Serial.println(result + String(writeAddress(val)));
      else if (strcmp(opcode, "BUS-RD") == 0)
        Serial.println(result + String(busDir(BUS_READ)));
      else if (strcmp(opcode, "BUS-WR") == 0)
        Serial.println(result + String(busDir(BUS_WRITE)));
      else {
        doError("Bad Special Opcode");
      }
      Serial.println("Complete");
    }
    command = "";
    commandReady = false;
    Serial.println(PROMPT);

  }

}

void serialEvent() {
  while (Serial.available()) {
    // get the new byte:
    char inChar = (char)Serial.read();
    // add it to the inputString:
    command += inChar;
    // if the incoming character is a newline, set a flag
    // so the main loop can do something about it:
    if (inChar == '#') {
      commandReady = true;
    }
  }
}

//FIX setting input/output for addr
unsigned int readAddress() {
  return (mcp[ADDRESS_CHIP].readGPIOAB());
}

unsigned int writeAddress(unsigned int address) {


  mcp[ADDRESS_CHIP].writeGPIOAB(address);
  return (address);
}


unsigned int readData() {

  if (busMode == BUS_WRITE)
    doError("Bus Mode is Write");

  return (mcp[DATA_CHIP].readGPIOAB());
}


unsigned int writeData(unsigned int data) {
  if (busMode == BUS_READ)
    doError("Bus Mode is Read");

  mcp[DATA_CHIP].writeGPIOAB(data);
  return (data);
}


unsigned int readDataLo() {

  if (busMode == BUS_WRITE)
    doError("Bus Mode is Write");

  return (mcp[DATA_CHIP].readGPIO(0));


}

int writeDataLo() {
  doError("Write Data Low Dows Not Exist");
}


unsigned int readDataHi() {

  if (busMode == BUS_WRITE)
    doError("Bus Mode is Write");

  return (mcp[DATA_CHIP].readGPIO(1));

}

int busDir(int state) { // 1=wr 0 = rd
  int i;

  if (state == BUS_WRITE) {
    for (i = 0; i < 16; i++)
      mcp[DATA_CHIP].pinMode(i, OUTPUT);
  }
  else {
    for (i = 0; i < 16; i++)
      mcp[DATA_CHIP].pinMode(i, INPUT);
  }
  busMode = state;
  return (state);
}





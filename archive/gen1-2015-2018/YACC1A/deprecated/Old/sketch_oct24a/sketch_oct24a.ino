#include <Wire.h> //I2C library
#include "Adafruit_MCP23017.h"

/*
   Format ":AIXXXXXXXX....XXXXX"
   ":"  Start charachter
   "A" Checksum (not including instruction number) (Ignore for now)
   "I" Instruction Number (0-255)- 2 hex ascii chars
   "XXXXXXXX....XXXXX" Data Bytes -  2 hex ascii chars

  Pin 11 FAULT
  Pin 12 Bus-EN READY
  Pin 13 Loading
*/

//RAM Control Lines
#define MEMWR 8
#define MEMRD 9
#define MEMSEL 10

// LEDS
#define FAULT 11
#define READY 12
#define LOADING 13

//Swithces
#define UCODESWITCH A0
#define STARTSWITCH A2

//UCODESWITCH Modes
#define DOWNLOAD 0
#define WRITEMEM 1

int mode;

#define LINES_PER_INSTRUCTION 2  // total number of rows of BYTES_PER_LINE
#define BYTES_PER_LINE 8         // total bytes/row (mem chips) should be 8
#define TOTAL_INSTRUCTIONS  256
#define INSTRUCTION_SIZE  BYTES_PER_LINE*LINES_PER_INSTRUCTION

#define NUMBER_OF_CONTROLERS 5
#define ADDRESS_CHIP 0
#define DATA_CHIP_START 1
#define DATA_CHIPS 4

Adafruit_MCP23017 mcp[NUMBER_OF_CONTROLERS];

unsigned char prog1[] = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  //blank line
  0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0x00, 0x00,  //Out on
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00,  //Out off
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00,  //Reset ucode counter
};
#define PROG1_SIZE 2

void writeCodeToROM(int, unsigned char *);



void doError(String errorMsg) {
  Serial.print("Error: ");
  Serial.println(errorMsg);
  digitalWrite(FAULT, HIGH);
  while (1);
}

void flash(int led) {
  digitalWrite(led, HIGH);
  delay(250);
  digitalWrite(led, LOW);
}

/*
   Read instruction from RAM
*/

void dumpInstruction(int instruction) {
  int i, j;
  char tmp[100];
  unsigned char data[BYTES_PER_LINE * LINES_PER_INSTRUCTION];

  Serial.print("Instruction=");
  Serial.println(instruction);

  //print header
  for (i = 0; i < BYTES_PER_LINE; i++) {
    sprintf(tmp, "%02x ", i); Serial.print(tmp);
  }
  Serial.println();

  readInstruction(instruction, data);
  for (j = 0; j < LINES_PER_INSTRUCTION; j++) {
    for (i = 0; i < BYTES_PER_LINE; i++) {
      sprintf(tmp, "%02x ", data[i + j * BYTES_PER_LINE]); Serial.print(tmp);
    }
    Serial.println();

  }
}

void setup() {
  int i;

  Serial.begin(19200);
  Wire.begin();

  for (i = 0; i < NUMBER_OF_CONTROLERS; i++) {
    mcp[i].begin(i);
  }


  pinMode(FAULT, OUTPUT);
  pinMode(READY, OUTPUT);
  pinMode(LOADING, OUTPUT);

  pinMode(MEMRD, OUTPUT);
  pinMode(MEMWR, OUTPUT);
  pinMode(MEMSEL, OUTPUT);

  digitalWrite(MEMRD, HIGH);
  digitalWrite(MEMWR, HIGH);
  digitalWrite(MEMSEL, HIGH);

  pinMode(UCODESWITCH, INPUT);
  pinMode(STARTSWITCH, INPUT);

  flash(FAULT);
  flash(READY);
  flash(LOADING);

  mode = digitalRead(UCODESWITCH);

}

void loop() {


  //unsigned char instructionBytes[INSTRUCTION_SIZE];
  //unsigned char currentChecksum;
  //unsigned char currentInstruction;
  //unsigned char instructionChecksum;
  //unsigned char readIns[INSTRUCTION_SIZE];

  unsigned char insData[BYTES_PER_LINE * LINES_PER_INSTRUCTION];

  int instruction;

  // Select 1 loop program to run, they never return

  loop1();

  if (mode == WRITEMEM) { // This is default condition, on powerup copy eprom to ram
    digitalWrite(LOADING, HIGH);
    setAddressOutput();
    setDataOutput();

    for (instruction = 0; instruction < TOTAL_INSTRUCTIONS; instruction++) {
      readCodeFromROM(instruction, insData);
      writeInstruction(instruction, insData);
    }

    setDataInput();
    setAddressInput();

    uCodeRamRead(true);
    //digitalWrite(MEMRD, LOW);
    uCodeRamSelect(true);
    //digitalWrite(MEMSEL, LOW);
    digitalWrite(LOADING, LOW);
    digitalWrite(READY, HIGH);

    while (1)
      delay(1000);

  }
  else { // download instructions
    
    //FIX maybe wait for swith press STARTSWITCH

    while(digitalRead(STARTSWITCH) == false);
    digitalWrite(READY,HIGH);
    while(digitalRead(STARTSWITCH) == true);
    digitalWrite(READY,LOW);
    
    digitalWrite(LOADING, HIGH);

    while ( waitInstructionBegin()) {
      downloadInstruction();
    }
    
    digitalWrite(LOADING, LOW);

    while (1)
      delay(1000);
  }
}

// Sequencer Memory card code
// Mode Determined by UCODESWITCH
//Mode 1 download uCode from serial line and store in EEPROM, press STARTSWITCH to begin (READY and LOADING LEDs ON)
//MODE 2 Write EEPROM into UCode RAM and set READY line high


#include <Wire.h> //I2C library
#include "Adafruit_MCP23017.h"
//#include "YACC_Common_headera.h"


#include <extEEPROM.h>
extEEPROM eep(kbits_512, 2, 64, 0x56);

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
#define STARTSWITCH A2 // Default HIGH

//
#define READYLINE 7

//UCODESWITCH Modes
#define DOWNLOAD 0
#define WRITEMEM 1

int mode;
int verbose = 0;

#define LINES_PER_INSTRUCTION 64 // tmp back to 32 HACK  // total number of rows of BYTES_PER_LINE
#define BYTES_PER_LINE 8         // total bytes/row (mem chips) should be 8
#define INSTRUCTION_SIZE  BYTES_PER_LINE*LINES_PER_INSTRUCTION

#define WORKING_INSTRUCTION_SET  256  // FIX shoud be 256
#define ALL_INSTRUCTIONS 256

#define NUMBER_OF_CONTROLERS 5
#define ADDRESS_CHIP 0
#define DATA_CHIP_START 1
#define DATA_CHIPS 4

Adafruit_MCP23017 mcp[NUMBER_OF_CONTROLERS];
unsigned char insData[BYTES_PER_LINE * LINES_PER_INSTRUCTION] = {0,};

void writeCodeToROM(int, unsigned char *);

//opcode myArraySRAM;

/*
   Routines to read/write data to eeprom
*/

/*
   Should deviceaddress be an unsigned int for both routines ???
*/
void myi2c_eeprom_write_byte( int deviceaddress,  unsigned char wdata, unsigned long eeaddress) {
  char tmp[35];

  sprintf(tmp, "W-%04x %02x %08lu", deviceaddress, wdata, eeaddress);
  Serial.println(tmp);

  byte i2cStat = eep.write(eeaddress, wdata);
  if ( i2cStat != 0 ) {
    sprintf(tmp, "E-[%08x] A-[%08lu]", i2cStat,eeaddress); Serial.println(tmp);
    doError("eep write error", 3);
    while (1);
  }
}

/*
   TODO maybe modify to accept 3rd param - pointer to return value location
   AND return 0 if succesful and -1 if fails
*/

byte i2c_eeprom_read_byte( int deviceaddress, unsigned long eeaddress ) {
  unsigned int rdata;
  char tmp[35];


  rdata = eep.read(eeaddress);
  if ( rdata  < 0 ) {
    sprintf(tmp, "E-[%08x] A-[%08lu]", rdata,eeaddress); Serial.println(tmp);
    doError("eep read error", 2);
    while (1);
  }
  return rdata;
}

void doError(String errorMsg, int code) {
  ///Serial.print("Error: ");
  ///Serial.println(errorMsg);
  while (1) {
    for (int i = 0; i < code; i++) {
      blinkLed(FAULT);
      delay(1000);
    }
    delay(5000);
  }
}

void flashLed(int led) {
  digitalWrite(led, HIGH);
  delay(100);
  digitalWrite(led, LOW);
}

void blinkLed(int led) {
  digitalWrite(led, HIGH);
  delay(100);
  digitalWrite(led, LOW);
  delay(100);
}

/*
   Test Pattern, for each line of instruction - BYTE 0 instruction #, BYTE 1, LINE #, remaining 0s
*/
void fillTestPattern(int instruction) {
  int i, j;

  if (verbose > 0) {
    Serial.print("Filling Memory - ");
    Serial.println(instruction);
  }

  for (i = 0; i < LINES_PER_INSTRUCTION; i++) {
    insData[i * BYTES_PER_LINE] = instruction;
    insData[i * BYTES_PER_LINE + 1] = i;
    for (j = 2; j < BYTES_PER_LINE; j++) {
      insData[i * BYTES_PER_LINE + j] = 0;
    }
  }
  writeInstruction(instruction, insData);

}

/*
   Read instruction from RAM
*/
void dumpInstruction(int instruction) {
  int i, j;
  char tmp[15];

  Serial.print("Ins=");
  Serial.println(instruction);

  Serial.print("        ");
  for (i = 0; i < BYTES_PER_LINE; i++) {
    sprintf(tmp, "%02x ", i); Serial.print(tmp);
  }
  Serial.println();

  readCodeFromROM(instruction, insData);
  Serial.println("after read ins");

  for (j = 0; j < LINES_PER_INSTRUCTION; j++) {
    sprintf(tmp, "LINE:%02d ", j); Serial.print(tmp);
    for (i = 0; i < BYTES_PER_LINE; i++) {
      sprintf(tmp, "%02x ", insData[i + j * BYTES_PER_LINE]); Serial.print(tmp);
    }
    Serial.println();

  }
  Serial.println();
}

void setup() {
  int i;
  char tmp[20];

  Serial.begin(19200);
  Serial.println("\n\nStartup");
  Wire.begin();

  uint8_t eepStatus = eep.begin(eep.twiClock100kHz);   //go fast!
  if (eepStatus) {
    doError("eep begin err", 1);
  }

  pinMode(UCODESWITCH, INPUT);
  mode = digitalRead(UCODESWITCH);


  if (mode == WRITEMEM)
    Serial.println("\n\nStartup");

  for (i = 0; i < NUMBER_OF_CONTROLERS; i++) {
    mcp[i].begin(i);
  }


  pinMode(FAULT, OUTPUT);
  pinMode(READY, OUTPUT);
  pinMode(LOADING, OUTPUT);
  pinMode(READYLINE, OUTPUT);

  pinMode(MEMRD, OUTPUT);
  pinMode(MEMWR, OUTPUT);
  pinMode(MEMSEL, OUTPUT);

  digitalWrite(MEMRD, HIGH);
  digitalWrite(MEMWR, HIGH);
  digitalWrite(MEMSEL, HIGH);
  digitalWrite(READYLINE, LOW);

  pinMode(UCODESWITCH, INPUT);
  pinMode(STARTSWITCH, INPUT);

  flashLed(FAULT);
  flashLed(READY);
  flashLed(LOADING);

  if (mode == WRITEMEM)
    Serial.println("Startup done\n");



#define EEPROMTEST1 1
#ifdef EEPROMTEST1
  Serial.println("\n1-Start EEPROM TESTS");
  for (int j = 0; j < 20; j++) {
    myi2c_eeprom_write_byte(0x57, 0x55, 0x8000); sprintf(tmp, "%02x\n", eep.read(0x8000)); Serial.println(tmp);
    eep.write(0, 0x11 + j);
    Serial.println("0");
   eep.write(32767, 0x22 + j );
    Serial.println("32767");
   eep.write(32768, 0x33 + j );
    Serial.println("32768");
    eep.write(65535, 0x44 + j);
    Serial.println("65535");
  eep.write(65536, 0x55 + j);
    Serial.println("65536");
    eep.write(131071, 0x66 + j );
    Serial.println("131071");

    sprintf(tmp, "%02x", eep.read(0)); Serial.println(tmp);
    sprintf(tmp, "%02x",eep.read(32767)); Serial.println(tmp);
    sprintf(tmp, "%02x", eep.read(32768)); Serial.println(tmp);
    sprintf(tmp, "%02x",eep.read(65535)); Serial.println(tmp);
    sprintf(tmp, "%02x",eep.read(65536)); Serial.println(tmp);
    sprintf(tmp, "%02x", eep.read(131071)); Serial.println(tmp);
  }
  dumpInstruction(0);
  dumpInstruction(4);

  //while (1);
#endif
}

void loop() {

  int address;
  int line;
  int instruction;
  unsigned char data[BYTES_PER_LINE];
  unsigned int counter;
  char tmp[50];
  boolean statusLed = false;
  int i, j;

  int previousLine;
  int previousInstruction;
  unsigned char previousData[8];
  unsigned char mask;
  int val;

  //bool printed=false;

  if (mode == WRITEMEM) { // LOADING on while copying, READY on when complete

    Serial.println("Write Mem");

#define FILLRAM
#ifdef FILLRAM
    //Serial.println("test pattern");

    setAddressOutput();
    setDataOutput();

    for (instruction = 0; instruction < ALL_INSTRUCTIONS; instruction++) {
      digitalWrite(LOADING, statusLed);
      statusLed = !statusLed;
      fillTestPattern(instruction);
    }
    Serial.println("-done");
#endif

#define ROMTORAM
#ifdef ROMTORAM
    Serial.println("EEPROM to RAM");
    digitalWrite(LOADING, HIGH);
    setAddressOutput();
    setDataOutput();

    for (instruction = 0; instruction < WORKING_INSTRUCTION_SET; instruction++) {
      Serial.print("Ins=");
      Serial.println(instruction);

      digitalWrite(LOADING, statusLed);
      statusLed = !statusLed;

      readCodeFromROM(instruction, insData);
      writeInstruction(instruction, insData);
    }
    Serial.println("-done");
#endif


#define DISPLAY_MEM
#ifdef DISPLAY_MEM
    // Set all lines to input, therefore can be driven by logic card
    setDataInput();
    setAddressOutput();
    uCodeRamRead(true);
    uCodeRamSelect(true);

    dumpInstruction(0);
    //dumpInstruction(1);
    //dumpInstruction(5);
    //dumpInstruction(6);
    dumpInstruction(124);
#endif

    setAddressInput();
    setDataInput();
    uCodeRamRead(true);
    uCodeRamSelect(true);
    // Set uCode RAM to read enabled and selected


    digitalWrite(LOADING, LOW);
    digitalWrite(READY, HIGH);
    digitalWrite(READYLINE, HIGH);
    Serial.println("RAM READY!");


    counter = 0;
    previousLine = -1;
    previousInstruction = -1;


    while (1) {
      // Monitor
      delay(1000);
      address = readAddress();
      line = address & 0x1f;
      instruction = (address & 0x1fe0) >> 5;
      if ((previousLine != line) || (previousInstruction != instruction)) {
        readData(data);
        sprintf(tmp, "Addr= % 04x Seq= % 05d Ins= % 02x Line= % 02x Data= ", address & 0x1fff, counter++, instruction, line); //why spaces after %
        Serial.print(tmp);
        for (int i = 0; i < BYTES_PER_LINE; i++) {
          sprintf(tmp, " %02x: ", data[i]);
          Serial.print(tmp);
        }
        Serial.println();

        if (line != 0) {
#ifdef JUNK
          sprintf(tmp, "---Addr = % 04x Seq = % 05d Inst = % 02x Line = % 02x Data = ", address & 0x1fff, counter++, instruction, line);
          Serial.print(tmp);
          for (int i = 0; i < 8; i++) {
            sprintf(tmp, " %02x! ", data[i]^previousData[i]);
            Serial.print(tmp);
          }
          Serial.println();
#endif
          for (int bytee = 0; bytee < 8; bytee++) {
            mask = 0x01;
            for (int bit = 0; bit < 8; bit++) {
              if ( ((data[bytee]^previousData[bytee]) & mask) != 0) {
                //memcpy_P( &myArraySRAM, &opcodesPROGMEM[(bytee * 8) + bit], sizeof(opcode));
                //sprintf(tmp, "sig=[%d][%s] ", (bytee * 8) + bit, myArraySRAM.code);
                val = data[bytee] & mask;
                if (val != 0)
                  val = 1;
                sprintf(tmp, "sig=[%d]=%d ", (bytee * 8) + bit, val);
                Serial.print(tmp);
              }
              mask = mask << 1;
            }

          }
          Serial.println();
        }
        previousLine = line;
        previousInstruction = instruction;
        for (i = 0; i < 8; i++)
          previousData[i] = data[i];
      }
    }
  }
  else { // download instructions

    digitalWrite(LOADING, HIGH);
    digitalWrite(READY, HIGH);
    while (digitalRead(STARTSWITCH) == true);
    digitalWrite(READY, LOW);

    while ( waitInstructionBegin()) { // Returns true when instruction downloaded, false when end of instruction list
      downloadInstruction();
      digitalWrite(LOADING, statusLed);
      statusLed = !statusLed;
    }

    digitalWrite(LOADING, LOW);

    while (1)
      delay(1000);
  }
}

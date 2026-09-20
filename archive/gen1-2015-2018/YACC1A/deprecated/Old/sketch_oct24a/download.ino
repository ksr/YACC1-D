/*
   Format ":AIXXXXXXXX....XXXXX"
   ":"  Start charachter
   "A" Checksum (not including instruction number) (Ignore for now) - 2 hex assci chars
   "I" Instruction Number (0-255)- 2 hex ascii chars
   "XXXXXXXX....XXXXX" Data Bytes -  2 hex ascii chars

*/

#define PROMPT ">>"
#define START_CHARACTER ':'
#define END_CHARACTER '!'

void sendReadyPrompt() {
  Serial.println(PROMPT);
}

void downloadInstruction() {
  unsigned char instructionBytes[INSTRUCTION_SIZE];
  unsigned char currentChecksum;
  unsigned char currentInstruction;
  unsigned char instructionChecksum;
  unsigned char readIns[INSTRUCTION_SIZE];

  int instruction;
  currentChecksum = getChecksum();
  currentInstruction = getInstructionNumber();
  instructionChecksum = getCode(instructionBytes);

  Serial.print("checksum:");
  Serial.print( currentChecksum);
  Serial.print(" ");
  Serial.print(currentInstruction);
  Serial.print(" ");
  for (int i = 0; i < INSTRUCTION_SIZE; i++) {
    Serial.print(instructionBytes[i]);
    Serial.print(":");
  }
  Serial.print(instructionChecksum);
  Serial.println();

  writeCodeToROM(currentInstruction, instructionBytes);
  readCodeFromROM(currentInstruction, readIns);
  for (int i = 0; i < INSTRUCTION_SIZE; i++) {
    Serial.print(readIns[i]);
    Serial.print(":");
  }
  Serial.println();
}

boolean waitInstructionBegin() {
  unsigned char c;

  sendReadyPrompt();
  while (Serial.available() < 1)
    delay(1);
  c = Serial.read();
  if (c == START_CHARACTER)
    return (true);
  else if (c == END_CHARACTER)
    return (false);
  else
    doError("Unexpected Character");
}

unsigned char getChecksum() {
  return (readHexNumber());
}

unsigned char getInstructionNumber() {
  return (readHexNumber());
}

unsigned char getCode(unsigned char *data) {
  int i;
  unsigned char checksum;

  checksum = 0;
  for (i = 0; i < INSTRUCTION_SIZE; i++) {

    data[i] = readHexNumber();
    checksum += data[i];
  }
  return (checksum);
}


unsigned char readHexNumber() {
  unsigned char cHigh, cLow;
  while (Serial.available() < 1)
    delay(1);
  cHigh = Serial.read();
  while (Serial.available() < 1)
    delay(1);
  cLow = Serial.read();
  return (convertAsciiToNum(cHigh, cLow));
}


unsigned char convertAsciiToNum(char cHigh, char cLow) {
  unsigned char res;

  res = converCharToInt(cLow) + converCharToInt(cHigh) << 4;
  return (res);

}

unsigned char converCharToInt(char c) {

  //c=toupper(c);
  if (c >= '0' && c <= '9')
    return (byte)(c - '0');
  else
    return (byte)(c - 'A' + 10);
}



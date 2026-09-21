/*
   Microcode EEPROM access - Sequencer4 (YACC1-D 2026-09-21).

   The EEPROM is two 64K I2C devices (0x56 = instructions 0-127, 0x57 = 128-255; 512 bytes per instruction, so an
   instruction never straddles the boundary). Sequencer3 read and wrote it ONE BYTE PER I2C TRANSACTION (five bus
   bytes and a stop per data byte on reads; a 5 ms write cycle per data byte on writes). Here:
     - reads set the address once per instruction and stream it out 32 bytes per requestFrom (the AVR Wire buffer),
       using the EEPROM's address auto-increment: 16 transactions per instruction instead of 512
     - writes use page writes: 30 data bytes per transaction (Wire buffer minus the 2 address bytes), one 5 ms write
       cycle per transaction instead of per byte; 512-byte instructions start page-aligned, and 30-byte chunks never
       cross a 128-byte page because every chunk that would is split at the boundary
*/

#define EEPROM_DEV_LO 0x56
#define EEPROM_DEV_HI 0x57
#define READ_CHUNK 32            // BUFFER_LENGTH of the AVR Wire library
#define WRITE_CHUNK 30           // 32 - 2 address bytes
#define EEPROM_PAGE 128          // 24LC1025 / 24LC512 page size
#define WRITE_CYCLE_MS 5

static int eepromDevice(unsigned long location) { return (location > 0xFFFFUL) ? EEPROM_DEV_HI : EEPROM_DEV_LO; }

/* read 'len' bytes of an instruction starting at byte 'offset' (any len; streamed 32 bytes per transaction) */
void readCodeFromROMPart(int instruction, unsigned int offset, unsigned int len, unsigned char *data) {
  unsigned long start = (unsigned long)instruction * (unsigned long)INSTRUCTION_SIZE + offset;
  int device = eepromDevice(start);
  unsigned int addr = (unsigned int)(start & 0xFFFFUL);
  unsigned int done = 0;

  // set the address once; the device auto-increments through the rest
  Wire.beginTransmission(device);
  Wire.write((int)(addr >> 8));
  Wire.write((int)(addr & 0xFF));
  Wire.endTransmission();
  while (done < len) {
    unsigned int n = len - done;
    if (n > READ_CHUNK) n = READ_CHUNK;
    unsigned int got = Wire.requestFrom(device, (int)n);
    for (unsigned int i = 0; i < n; i++) data[done + i] = (i < got && Wire.available()) ? Wire.read() : 0xFF;
    done += n;
  }
}

void readCodeFromROM(int instruction, unsigned char *data) {
  readCodeFromROMPart(instruction, 0, INSTRUCTION_SIZE, data);
}

void writeCodeToROM(int instruction, unsigned char data[INSTRUCTION_SIZE]) {
  unsigned long start = (unsigned long)instruction * (unsigned long)INSTRUCTION_SIZE;
  int device = eepromDevice(start);
  unsigned int addr = (unsigned int)(start & 0xFFFFUL);
  unsigned int done = 0;

  while (done < INSTRUCTION_SIZE) {
    unsigned int n = INSTRUCTION_SIZE - done;
    if (n > WRITE_CHUNK) n = WRITE_CHUNK;
    unsigned int room = EEPROM_PAGE - ((addr + done) % EEPROM_PAGE);   // stay inside the page
    if (n > room) n = room;
    Wire.beginTransmission(device);
    Wire.write((int)((addr + done) >> 8));
    Wire.write((int)((addr + done) & 0xFF));
    for (unsigned int i = 0; i < n; i++) Wire.write(data[done + i]);
    Wire.endTransmission();
    delay(WRITE_CYCLE_MS);
    done += n;
  }
}

/* single-byte access kept for anything that still wants it */
byte i2c_eeprom_read_byte(int deviceaddress, int eeaddress) {
  byte rdata = 0xFF;
  Wire.beginTransmission(deviceaddress);
  Wire.write((int)(eeaddress >> 8));
  Wire.write((int)(eeaddress & 0xFF));
  Wire.endTransmission();
  Wire.requestFrom(deviceaddress, 1);
  if (Wire.available()) rdata = Wire.read();
  return rdata;
}

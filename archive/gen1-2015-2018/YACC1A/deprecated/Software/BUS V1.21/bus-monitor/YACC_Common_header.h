#define NUMBER_OF_CONTROLLERS 6
#define PINS_PER_PORT 8
#define BITS_PER_CONTROLLER 16
#define PORTS_PER_CONTROLLER 2
#define ACTIVE_LOW 8 /* add 8 to pin number to signify active low signal */
#define FIRST_BUS_SIGNAL_CONTROLLER 2 /*first controller with bus signal lines */
#define ADDRESS_CHIP 0
#define DATA_CHIP 1

#define SPECIAL_OPCODE 9


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

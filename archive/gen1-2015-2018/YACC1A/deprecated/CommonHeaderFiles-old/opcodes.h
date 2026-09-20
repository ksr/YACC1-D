#define START           0x00
#define OUT_ON          0x01
#define OUT_OFF         0x02
#define BRANCH          0x03
#define BRANCH_IN_TRUE  0x04
#define BRANCH_IN_FALSE 0x05
#define LD_ACC_I        0x06
#define ADD_ACC_I       0x07
#define BRANCH_ACC_NZ   0x08
#define ACC_OUT         0x09
#define LD_SP_I         0x0a
#define LD_REG_I        0x10 //last 3 bits are reg num
#define OUT_REG            0x18 //last 3 bit are reg num, out to addr pointed to by SP
#define MV_REG_ACC      0x20 //last 3 bits are reg num
#define MV_ACC_REG      0x28 //last 3 bits are reg num


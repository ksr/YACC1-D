void test1(){
 
  digitalWrite(LOADING, HIGH);
  setAddressOutput();
  setDataOutput();

  //fillmem(prog1, 4);
  blockFillInstructions(PROG1_SIZE, prog1); // test this change

  setDataInput();

  dumpInstruction(0);
  dumpInstruction(1);

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


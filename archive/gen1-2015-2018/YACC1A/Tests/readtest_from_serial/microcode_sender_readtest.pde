// Test reading from serial port
import processing.serial.*;

Serial myPort;

void setup() {
  myPort = new Serial(this, "/dev/cu.usbserial-AL00FSLF", 38400);
}


void draw() {
  getLine();
}

void getLine() {
  while (myPort.available() > 0) {
    int c = myPort.read();
    println("C=["+int(c)+"]");
  }
}
import processing.serial.*;
import java.io.*;
import java.util.Date;

Serial myPort;
int lf = 10;    // Linefeed in ASCII
int cr = 13;    // CR in ASCII

int delayString = 35;

String myString = null;
String[] commands;

void setup() {

  println("Start");
  println(dataPath(""));
  println(sketchPath(""));

  size(640, 400);
  fill(100);

  commands = loadStrings("../../NewFolder/CppApplication_1/test.hex"); //read command file
  for (int i=0; i < commands.length; i++) {
    print(i);
    print(" ");
    println(commands[i]);
  }

  myPort = new Serial(this, "/dev/cu.usbserial-AL00FSLF", 19200);
  //myPort = new Serial(this, "/dev/cu.usbserial-FTGNNBHP", 19200);
  //delay(2000);
  //while (!isPrompt(getLine()));

  println("Setup Complete");
}

int doCommand() {


  String instruction ="";
  String checksum="";
  String data="";
  
  print("in doCommand instruction=");println(index);
  if (commands[index].indexOf("!") == 0) {
    myPort.write("!");
    return(0);
  }
  if (commands[index].indexOf("%") != 0) {
    doError("Line did not start with %");
  }

  checksum=commands[index].substring(1, 3);
  instruction=commands[index].substring(3, 5);
  data=commands[index].substring(5, commands[index].indexOf("-"));
  //print(checksum);print(" ");
  //print(instruction); print(" ");
  //println(data);


  //sendinfo
  for(int i=0;i <commands[index].indexOf("-");i++){
    //println(commands[index].substring(i, i+1));
    myPort.write(commands[index].substring(i, i+1));
    delay(delayString);
  }
  //myPort.write(commands[index].substring(0, commands[index].indexOf("-")));

  delay(5);

  return(1);
}


int index=0;
void draw() {


  background(555);
  while (!isPrompt(getLine()));
  if (index < commands.length) {
    println("Command: " + commands[index]);
    if (doCommand() == 0) {
      println("Test Complete");
      exit();
    }
    delay(delayString);
    index = index + 1;
  }
}


void doError(String msg) {
  println(msg);
  exit();
}

boolean isPrompt(String line) {
  return(line.equals(">>") == true);
}

String getLine() {

  String tmpString="";
  char c=0;
  boolean done=false;

  //println("in getline");

  while (!done) {
    c = getChar();
    //c=myPort.readChar();
    //println("C=["+int(c)+"]");
    tmpString += c;  ///ksr test if c = 'cr' return string with no crlf appended
    if (c == lf) {
      println("Line done :" + tmpString);
      //println(tmpString.length());
      //println(tmpString.substring(0, tmpString.length()-2));
      return(tmpString.substring(0, tmpString.length()-2));
    }
  }

  return("");
  /*
  String tmpString = myPort.readStringUntil(lf);
   print("getLine: ");
   print(tmpString);
   return(tmpString);
   */
}

char getChar() {

  //println("in getChar");
  while (myPort.available() <= 0)
    delay(35);
  char c = myPort.readChar();
  //println("C=["+int(c)+"]["+c+"]");
  return(c);
}
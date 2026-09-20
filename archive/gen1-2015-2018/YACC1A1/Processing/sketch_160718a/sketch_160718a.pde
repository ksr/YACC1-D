import processing.serial.*;
import java.io.*;


Serial myPort;
int lf = 10;    // Linefeed in ASCII
String myString = null;
String[] commands;

void setup() {

  commands = loadStrings("commands.txt"); //read command file
  for (int i=0; i < commands.length; i++)
    println(commands[i]);
  myPort = new Serial(this, "/dev/cu.usbserial-FTGNNBHP", 9600);
  delay(5000);
  while (!isPrompt(getLine()));


  println("Setup Complete");
}

//String line;
int index=0;
void draw() {

  boolean returnExpected = false;
  int returnValueExpected=0;
  int returnValueActual=0;

  if (index < commands.length) {
    println("Command: " + commands[index]);

    if (commands[index].indexOf("!") != -1) {
      returnExpected = true;
      String returnStringExpected = commands[index].substring(commands[index].indexOf("#")+1,commands[index].indexOf("!"));
      returnValueExpected = int(returnStringExpected);
      println("Return expected =[" + returnValueExpected + "]");
    }

    myPort.write(commands[index].substring(0, commands[index].indexOf("#")+1));
    delay(100);
    println("A:"+getLine()); //command line echo

    if (returnExpected) {
      String returnString = getLine();
      println("B:"+ returnString);
      String returnStringActual = returnString.substring(returnString.indexOf(":")+2,returnString.indexOf("\n")-1);
      println("[" +returnStringActual+ "]");
      returnValueActual = int(returnStringActual);
      println("Return Actual =[" + returnValueActual + "]");
      if (returnValueExpected != returnValueActual) {
        println("MisMatch");
        while (true)
          delay(1000);
      }
    }
    println("C:"+ getLine()); //complete
    delay(100);
    while (!isPrompt(getLine()));
    delay(100);
    index = index + 1;
    returnExpected = false;
  }
}


void commandResult(String line) {
  println(line);
}

boolean isError(String line) {
  return(line.equals("Error\r\n") != true);
}

boolean isPrompt(String line) {
  return(line.equals(">>\r\n") == true);
}

String getLine() {

  String tmpString="";
  char c=0;
  boolean done=false;

  //println("in getline");

  while (!done) {
    while (myPort.available() > 0) {
      c = myPort.readChar();
      //println("C=["+c+"]");
      tmpString += c;
      if (c == lf) {
        //println("Line done :" + tmpString);
        return(tmpString);
      }
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
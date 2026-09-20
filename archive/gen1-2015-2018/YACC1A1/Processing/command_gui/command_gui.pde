import processing.serial.*;
import java.io.*;
import controlP5.*;

Serial myPort;
int lf = 10;    // Linefeed in ASCII
String myString = null;
String[] commands;

ControlP5 cp5;
CheckBox checkbox;
int myColorBackground;

void setup() {

  commands = loadStrings("commands.txt"); //read command file
  for (int i=0; i < commands.length; i++)
    println(commands[i]);
  //myPort = new Serial(this, "/dev/cu.usbserial-FTGNNBHP", 9600);
  delay(5000);
  while (!isPrompt(getLine()));

  size(700, 400);
  smooth();
  cp5 = new ControlP5(this);
  
  checkbox = cp5.addCheckBox("checkBox")
                .setPosition(100, 200)
                .setColorForeground(color(120))
                .setColorActive(color(255))
                .setColorLabel(color(255))
                .setSize(40, 40)
                .setItemsPerRow(3)
                .setSpacingColumn(30)
                .setSpacingRow(20)
                .addItem("0", 0)
                .addItem("50", 50)
                .addItem("100", 100)
                .addItem("150", 150)
                .addItem("200", 200)
                .addItem("255", 255)
                ;
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
      tmpString += c;  ///ksr test if c = 'cr' return string with no crlf appended
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

void controlEvent(ControlEvent theEvent) {
  if (theEvent.isFrom(checkbox)) {
    myColorBackground = 0;
    print("got an event from "+checkbox.getName()+"\t\n");
    // checkbox uses arrayValue to store the state of 
    // individual checkbox-items. usage:
    println(checkbox.getArrayValue());
    int col = 0;
    for (int i=0;i<checkbox.getArrayValue().length;i++) {
      int n = (int)checkbox.getArrayValue()[i];
      print(n);
      if(n==1) {
        myColorBackground += checkbox.getItem(i).internalValue();
      }
    }
    println();    
  }
}
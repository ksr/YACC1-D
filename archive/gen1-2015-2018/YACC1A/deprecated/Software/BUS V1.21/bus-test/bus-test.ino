
/*
   BUS Monitor

   Loops watching bus for changes.
   Works well when combined with single step mode on sequencer

   Usgae notes:
   Monitor via Arduino IDE Monitor program
   SET ARDUINO MONITOR TO "No Line Ending"

   0 is off
   1 is on

   this program adjusts for active low vs active high
*/

#include <Wire.h>
#include "Adafruit_MCP23017.h"
#include <avr/pgmspace.h>
#include "YACC_Common_header.h"

//#define DEBUG

Adafruit_MCP23017 mcp[NUMBER_OF_CONTROLLERS];

// Hold previous state of bus signal lines (16 bits)
unsigned int previous[NUMBER_OF_CONTROLLERS];

/* Flash an LED */
void flash(int led) {
  digitalWrite(led, HIGH);
  delay(250);
  digitalWrite(led, LOW);
  delay(250);
}

bool is_busline(int controller, int pin) {
  char tmp[100];

  if ( ((controller  * 16) + pin)  < 84) {
    sprintf(tmp, "is busline yes %d %d\n", controller, pin);
    Serial.print(tmp);
    return (true);
  }
  else {
    sprintf(tmp, "is busline no %d %d\n", controller, pin);
    Serial.print(tmp);
    return (false);
  }
}

void show_all_lines() {
  int i, j;
  char tmp[100];

  sprintf(tmp, "\nShow all lines\n\n");
  Serial.print(tmp);

  for (i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
    sprintf(tmp, "Controller %d - ", i);
    Serial.print(tmp);
    for (j = 0; j < BITS_PER_CONTROLLER; j++) {
      if ( ((i  * 16) + j)  < 84) {
        sprintf(tmp, "%d ", mcp[i].digitalRead(j));
        Serial.print(tmp);
      }

    }
    sprintf(tmp, "\n");
    Serial.print(tmp);
  }
  sprintf(tmp, "\n\n");
  Serial.print(tmp);
}




void setup() {
  int i, j;

  Serial.begin(115200);
  Serial.println("Setup Start");

  /* Set all controllers to input, turn on internal pullups */
  for (i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
    mcp[i].begin(i);
    previous[i] = 0;

    for (j = 0; j < 16; j++) {
      mcp[i].pinMode(j, INPUT);
      mcp[i].pullUp(j, HIGH);  // turn on a 100K pullup internally
    }
  }

  /* Flash all leds
    ??? Looks like 9,10,11,12,13 are Arduino ports
  */
  for (i = 9; i <= 13; i++) {
    pinMode(13, OUTPUT); /*??? Should 13 actually be i ??*/
    flash(i);
  }
  Serial.println("Setup Done");

  //#define DEBUG
#ifdef DEBUG
  mcp[0].pinMode(0, OUTPUT);
  mcp[0].digitalWrite(0, LOW);

  char tmp[100];
  int x = 100;
  while (x--) {
    sprintf(tmp, "%d %d \n", mcp[0].digitalRead(2));
    Serial.print(tmp);
  }
  mcp[0].pinMode(0, INPUT);
  exit(0);
#endif
}

bool test_bus_for_low(int controller, int testbit) {
  int i, j;
  unsigned int in;
  char tmp[100];

  sprintf(tmp, "\ntest hi start %d %d\n\n", controller, testbit);
  Serial.print(tmp);
  for (i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
    show_all_lines();
    for (j = 0; j < BITS_PER_CONTROLLER; j++) {
      if (is_busline(i, j)) {
        sprintf(tmp, "test hi %d %d\n", i, j);
        Serial.print(tmp);
        if ((i != controller) || ( j != testbit)) {

          sprintf(tmp, " do test " );
          Serial.print(tmp);
          in = mcp[i].digitalRead(j);
          sprintf(tmp, "%d\n", in);
          Serial.print(tmp);
          if (in == 0) {
            return (true);
          }
        }
      }

    }
  }
  return (false);
}



void loop() {
  int i, j;
  unsigned int mask;
  char tmp[100];

  /*
     set all bus lines to OUTPUT and LOW
  */
  /*
       sprintf(tmp, "Hi Test setup all bus lines to low\n");
    Serial.print(tmp);
    for (i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
      for (j = 0; j < BITS_PER_CONTROLLER; j++) {
        if (is_busline(i, j)) {
          mcp[i].pinMode(j, OUTPUT);
          mcp[i].digitalWrite(j, LOW);
        }
      }
    }
    sprintf(tmp, "Hi Test setup all bus lines complete\n");
    Serial.print(tmp);
  */
  show_all_lines();

  /*
     cycle through all bus lines setting a single line to high
     then testing if any other lines are high
  */

  for (i = 0; i < NUMBER_OF_CONTROLLERS; i++) {
    for (j = 0; j < BITS_PER_CONTROLLER; j++) {
      sprintf(tmp, "Hi Test %d %d\n", i, j);
      Serial.print(tmp);
      if (is_busline(i, j)) {
        mcp[i].pinMode(j, OUTPUT);
        mcp[i].digitalWrite(j, LOW);
        if (test_bus_for_low(i, j)) {
          sprintf(tmp, "SHORT FOUND %d %d\n", i, j);
          Serial.print(tmp);
          delay(2000);
          exit(0);
        }
        mcp[i].pinMode(j, INPUT);
        //mcp[i].digitalWrite(j, LOW);
      }
    }
  }

  sprintf(tmp, "Bus test done\n");
  Serial.print(tmp);
  delay(2000);
  exit(0);
}

This file needs to placed in Arduino Library Tree

On my mac this is:

~/Documents/Arduino/libraries/YACC



---
*YACC1-D note (2026-09-19): the text above is the original Readme.md migrated from `YACC gitversion/YACC1-2020/Utilities/arduino/Readme.md`. Placeholder description from the tree layout:*

# embedded/libraries

VENDORED: Adafruit_MCP23017 1.1.0 (the sketches need the 1.x API) and YACC_Common_header.h (bus signal table). Neither is in any repo copy today.

_Contents migrated 2026-09-19; MIGRATION.md at the repo root says which copy each item came from._


Install: copy `Adafruit_MCP23017_Arduino_Library/` and `YACC/` into `~/Documents/Arduino/libraries/` (the sketches
`#include "Adafruit_MCP23017.h"` and `"YACC_Common_header.h"`). `YACC_Common_header.h` (2020-09-01) is the tester's bus signal
table: name, MCP23017 chip, port, bit – the same table the microcode generator's `yaccsignaldata2.h` encodes for the
sequencer. `YACC_Common_header-pre3-2.h` is its previous version. Neither file existed in any YACCS copy; they came from
`~/Documents/Arduino/libraries/YACC/` on 2026-09-19.

`extEEPROM/` (JChristensen, 3.4.1) is used only by the deprecated `sequencer-card/deprecated/sequencer2` sketch; vendored 2026-09-20
from `~/Documents/Arduino/old-libraries/` so that sketch still compiles.

# EEPROM adaptor (accessory of the sequencer-memory card)

A 29 x 16 mm board that plugs into IC9, the 8-pin I2C EEPROM (24Cxx) socket of the sequencer-memory card, and
carries two 24Cxx EEPROMs on the same SDA/SCL: IC1 with A2 A1 A0 = 1 1 1 (device address 7) and IC2 with
A2 A1 A0 = 1 1 0 (address 6), WP common. It doubles the microcode storage seen by the ATmega loader without
changing the card. One design (schematic 2020-12-19, board 2020-12-21; every copy in the old tree identical).

- `eeprom adaptor.sch/.brd/.pro` – the design. `pdf/` – generated drawings.
- `fab/oshpark-order-invoice-rmD8XYsD.pdf` – OSH Park order rmD8XYsD, 2024-06-19, one set of three boards ($7.30).
  OSH Park takes the `.brd` directly, so the board file is the fab file.

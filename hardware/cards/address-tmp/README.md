# cards/address-tmp — Address and TMP register card (RETIRED)

The first-generation-2020 way of getting a 16-bit address onto the bus: two 16-bit address registers plus the TMP
register, built from eight 74373 transparent latches with resistor-network pull-ups, loaded and read by dedicated
strobes -ADDR-REG-LD0/RD0 and -ADDR-REG-LD1/RD1 on bus pins C3–C6 (Bus Template V3.0/V3.1 naming).

Fabricated in June 2020 and used during early bring-up; replaced within months by the Index Registers card
(register number on ADDR-REG-ID0..3, Bus V3.2) and moved to "Old & obsolete – do not use" in January 2021.
No active version exists, so everything lives under `eagle/deprecated/`:

- `eagle/deprecated/v1.0/` – the fabricated design (2020-06-20), CAM output in `fab/`. A later Working copy of the
  same files differed only by a stray "test text" element and was dropped 2026-09-20.

Why it matters today: this card is the reason the Blank V3.1 template still carries the RD/LD names on C3–C6.

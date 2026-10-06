# Reverse-engineered property map

This project identified 269 EH-800/EH-800B property entries during hardware testing.

The complete raw capture is kept out of the first code commit while the entries are being classified into read-only values and safe writable controls.

## Confirmed L1 controls

| ID | Property | Raw value observed | Meaning |
|---:|---|---:|---|
| 54 | L1_SAATIMEN_MENOVEDEN_MINIMI | 140 | Supply minimum 14.0 °C |
| 55 | L1_SAATIMEN_MENOVEDEN_MAKSIMI | 890 | Supply maximum 89.0 °C |
| 56 | L1_SAATIMEN_P_ALUE | 250 | P band |
| 57 | L1_SAATIMEN_I_AIKA | 50 | I time |
| 58 | L1_SAATIMEN_D_AIKA | 0 | D time |
| 67 | L1_KAYRAN_MENOVESI_5A | 900 | -20 °C → 90.0 °C |
| 68 | L1_KAYRAN_ULKOLAMPO_5A | -200 | -20.0 °C |
| 69 | L1_KAYRAN_MENOVESI_5B | 700 | -10 °C → 70.0 °C |
| 70 | L1_KAYRAN_ULKOLAMPO_5B | -100 | -10.0 °C |
| 71 | L1_KAYRAN_MENOVESI_5C | 550 | 0 °C → 55.0 °C |
| 72 | L1_KAYRAN_ULKOLAMPO_5C | 0 | 0.0 °C |
| 73 | L1_KAYRAN_MENOVESI_5D | 490 | +10 °C → 49.0 °C |
| 74 | L1_KAYRAN_ULKOLAMPO_5D | 100 | +10.0 °C |
| 75 | L1_KAYRAN_MENOVESI_5E | 180 | +20 °C → 18.0 °C |
| 76 | L1_KAYRAN_ULKOLAMPO_5E | 200 | +20.0 °C |
| 91 | L1_SAATIMEN_KESASULUN_RAJA | 24 | Summer shutoff |
| 92 | L1_KASIAJO_ASENTO | 81 | Manual valve position |
| 126 | L1_MENOVEDEN_MAKS_MUUTOSNOPEUS | 40 | Max supply change rate |
| 127 | L1_MENOVEDEN_ASETUSARVO | 150 | Supply setpoint |
| 134 | L1_HIENOSAATO_VESI | 0 | Fine adjustment |

Negative values can be returned by the controller as unsigned 16-bit values (for example -200 as 65336).

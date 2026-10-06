# Protocol notes

Transport: USB CDC ACM. Tested device identifies as OUMAN Ouman EH-800, VID:PID eb03:0920.

Line-oriented ASCII commands terminate with newline.

## Read
- `MEASUREMENTS`
- `LIST`
- `TYPE <filename>`
- `OSINFO`
- `DEVINFO`
- `TIME`

## Write
- `SET PROPERTY <property-id> <raw-value>`
- `SET CLOCK <hh> <mm> <ss>`
- `SET DATE <yyyy> <mm> <dd>`
- `SET DAY <0..6>`

Confirmed hardware example:

`SET PROPERTY 67 910`

Response:

`PROPERTY(67):'L1_KAYRAN_MENOVESI_5A'(0-1000) = 910`

Many temperatures use tenths of a degree as the raw representation. Signed values may appear as unsigned 16-bit values in controller output.

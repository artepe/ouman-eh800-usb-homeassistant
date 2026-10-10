#!/usr/bin/env python3
import argparse, serial, time, sys
from pathlib import Path

PORT="/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00"
SIZE=3192
CURVE={-20:2536,-10:2556,0:2576,10:2596,20:2616}
FINE=2776

def tx(port,cmd,wait=.8,n=65536):
    with serial.Serial(port,timeout=2) as s:
        time.sleep(.25); s.reset_input_buffer()
        s.write(cmd.encode("ascii")+b"\n"); s.flush(); time.sleep(wait)
        return s.read(n)

def get_objects(port):
    d=tx(port,"TYPE objects.dat",1)
    if len(d)<SIZE: raise RuntimeError(f"Received {len(d)} bytes, expected >= {SIZE}")
    return d[:SIZE],d[SIZE:]

def backup(port,out):
    b,tail=get_objects(port); Path(out).write_bytes(b)
    print(f"Saved {len(b)} bytes -> {out}"); print("Tail:",repr(tail))

def s16(b,o): return int.from_bytes(b[o:o+2],"little",signed=True)
def u16(b,o): return int.from_bytes(b[o:o+2],"little")
def s8(b,o): return int.from_bytes(b[o:o+1],"little",signed=True)

def inspect(fn):
    b=Path(fn).read_bytes()
    if len(b)!=SIZE: raise ValueError(f"Expected {SIZE} bytes, got {len(b)}")
    for x,o in CURVE.items():
        print(f"{x:+3d} C -> {u16(b,o)/10:.1f} C  stored X={s16(b,o+10)/10:+.1f} C  offset={o}")
    print(f"Fine adjustment {s8(b,FINE)/10:+.1f} C offset={FINE}")

def patch(src,dst,args):
    b=bytearray(Path(src).read_bytes())
    if len(b)!=SIZE: raise ValueError(f"Expected {SIZE} bytes, got {len(b)}")
    vals={-20:args.m20,-10:args.m10,0:args.p0,10:args.p10,20:args.p20}
    for x,v in vals.items():
        if v is None: continue
        o=CURVE[x]; raw=round(v*10)
        if not 0<=raw<=65535: raise ValueError("Curve value out of range")
        print(f"{x:+3d}: {u16(b,o)/10:.1f} -> {v:.1f} C")
        b[o:o+2]=raw.to_bytes(2,"little")
    if args.fine is not None:
        raw=round(args.fine*10)
        if not -128<=raw<=127: raise ValueError("Fine adjustment out of range")
        print(f"fine: {s8(b,FINE)/10:+.1f} -> {args.fine:+.1f} C")
        b[FINE]=raw & 255
    Path(dst).write_bytes(b)
    print(f"LOCAL patched image -> {dst}")
    print("Not uploaded: EH-800B general file-upload command is not verified yet.")

def fwprobe(port):
    with serial.Serial(port,timeout=.2) as s:
        time.sleep(.25); s.reset_input_buffer(); s.write(b"FIRMWARE\n"); s.flush()
        end=time.time()+2; d=b""
        while time.time()<end: d+=s.read(4096)
        s.write(b"\n"); s.flush(); time.sleep(.3); d+=s.read(4096)
    print(repr(d)); print(d.decode("latin1",errors="replace")); print("HEX",d.hex(" "))

def main():
    a=argparse.ArgumentParser(); a.add_argument("--port",default=PORT)
    sp=a.add_subparsers(dest="cmd",required=True)
    for x in ("list","measurements","devinfo","osinfo","firmware-probe"): sp.add_parser(x)
    q=sp.add_parser("backup"); q.add_argument("out",nargs="?",default="objects_backup.bin")
    q=sp.add_parser("inspect"); q.add_argument("file")
    q=sp.add_parser("shell"); q.add_argument("text")
    q=sp.add_parser("patch"); q.add_argument("src"); q.add_argument("dst")
    for n in ("m20","m10","p0","p10","p20","fine"): q.add_argument("--"+n,type=float)
    x=a.parse_args()
    if x.cmd=="list": sys.stdout.write(tx(x.port,"LIST").decode("latin1","replace"))
    elif x.cmd=="measurements": sys.stdout.write(tx(x.port,"MEASUREMENTS").decode("latin1","replace"))
    elif x.cmd=="devinfo": sys.stdout.write(tx(x.port,"DEVINFO").decode("latin1","replace"))
    elif x.cmd=="osinfo": sys.stdout.write(tx(x.port,"OSINFO").decode("latin1","replace"))
    elif x.cmd=="backup": backup(x.port,x.out)
    elif x.cmd=="inspect": inspect(x.file)
    elif x.cmd=="patch": patch(x.src,x.dst,x)
    elif x.cmd=="firmware-probe": fwprobe(x.port)
    elif x.cmd=="shell":
        d=tx(x.port,x.text,1); print("RAW",repr(d)); print("HEX",d.hex(" ")); print(d.decode("latin1","replace"))
if __name__=="__main__": main()
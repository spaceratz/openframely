#!/usr/bin/env python3
"""Reboot via FIQ at 1.5M, then listen/spam Ctrl+C at a second baud to read the bootloader."""
import sys, time, serial
PORT, LOG = "/dev/cu.usbserial-XXXXXXXX", "/Users/you/dp159k/dump/uboot-baud.log"
baud2 = int(sys.argv[1]) if len(sys.argv) > 1 else 115200
with serial.Serial(PORT, 1500000, timeout=0.05) as s:
    s.write(b"\r"); time.sleep(0.5); pre = s.read(65536)
    if b"debug>" not in pre[-300:]:
        s.write(b"fiq\r"); time.sleep(0.8); s.read(65536)
    s.write(b"reboot\r"); s.flush()
with serial.Serial(PORT, baud2, timeout=0.01) as s, open(LOG, "ab") as log:
    log.write(f"\n=== {time.ctime()} baud2={baud2}\n".encode())
    buf, end = b"", time.time() + 6
    while time.time() < end:
        s.write(b"\x03"); buf += s.read(4096); time.sleep(0.01)
    for c in ["", "version", "help"]:
        s.write((c + "\r").encode()); time.sleep(2); buf += s.read(65536)
    log.write(buf)
    print(buf.decode("latin-1")[:5000])

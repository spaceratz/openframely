#!/usr/bin/env python3
"""Read-only UART capture. Logs raw bytes; tries common baud rates until text looks readable."""
import sys, time, serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-XXXXXXXX"
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 60
BAUDS = [int(b) for b in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1500000]
OUT = "/Users/you/dp159k/dump/uart-{}.log"

for baud in BAUDS:
    with serial.Serial(PORT, baud, timeout=0.2) as s, open(OUT.format(baud), "ab") as f:
        f.write(f"\n=== {time.ctime()} baud={baud}\n".encode())
        end, total = time.time() + SECS, 0
        while time.time() < end:
            d = s.read(4096)
            if d:
                f.write(d); f.flush(); total += len(d)
        print(f"baud={baud} bytes={total} -> {OUT.format(baud)}")

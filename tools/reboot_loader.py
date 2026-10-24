#!/usr/bin/env python3
"""Enter FIQ debugger and send 'reboot loader' (Rockchip USB download mode). No eMMC writes."""
import time, serial
with serial.Serial("/dev/cu.usbserial-XXXXXXXX", 1500000, timeout=0.05) as s, \
     open("/Users/you/dp159k/dump/reboot-loader.log", "ab") as log:
    s.write(b"\r"); time.sleep(0.5); out = s.read(65536)
    if b"debug>" not in out[-300:]:
        s.write(b"fiq\r"); time.sleep(1); out += s.read(65536)
    print("debug prompt:", b"debug>" in out)
    s.write(b"reboot loader\r"); time.sleep(4); out += s.read(65536)
    log.write(f"\n=== {time.ctime()}\n".encode() + out)
    print(out.decode("latin-1")[-800:])

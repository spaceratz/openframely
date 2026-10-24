#!/usr/bin/env python3
"""Reboot via FIQ debugger, spam Ctrl+C to stop U-Boot autoboot, then run read-only commands."""
import time, serial, re

PORT, LOG = "/dev/cu.usbserial-XXXXXXXX", "/Users/you/dp159k/dump/uboot-session.log"
READONLY = ["version", "printenv", "mmc list", "mmc info", "part list mmc 0", "usb info", "help"]

def drain(s, secs):
    out, end = b"", time.time() + secs
    while time.time() < end:
        out += s.read(4096)
    return out

with serial.Serial(PORT, 1500000, timeout=0.01) as s, open(LOG, "ab") as log:
    log.write(f"\n=== {time.ctime()}\n".encode())
    s.write(b"\r"); out = drain(s, 1.5)
    if b"debug>" not in out:
        s.write(b"fiq\r"); out += drain(s, 1.5)
    log.write(out)
    print("pre-reboot prompt:", "debug>" in out.decode("utf-8", "replace"))
    s.write(b"reboot\r")
    buf, end, caught = b"", time.time() + 25, False
    while time.time() < end:
        s.write(b"\x03")
        buf += s.read(4096)
        if re.search(rb"(=>|rockchip #|# )\s*$", buf[-200:]) and b"U-Boot" in buf:
            caught = True
            break
        time.sleep(0.005)
    buf += drain(s, 1)
    log.write(buf)
    print("caught U-Boot prompt:", caught)
    print(buf.decode("utf-8", "replace")[-3000:])
    if caught:
        for c in READONLY:
            s.write((c + "\r").encode())
            r = drain(s, 4)
            log.write(f"\n>>> {c}\n".encode() + r)
            print(f"\n>>> {c}\n" + r.decode("utf-8", "replace")[:6000])

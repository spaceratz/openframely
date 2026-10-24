#!/usr/bin/env python3
"""Send one line to the UART console and print the reply. Usage: uart_cmd.py 'cmd' [secs]"""
import sys, time, serial
cmd = sys.argv[1] if len(sys.argv) > 1 else ""
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 3
with serial.Serial("/dev/cu.usbserial-XXXXXXXX", 1500000, timeout=0.2) as s, open("/Users/you/dp159k/dump/uart-session.log", "ab") as f:
    s.read(65536)
    s.write((cmd + "\r").encode())
    out, end = b"", time.time() + secs
    while time.time() < end:
        out += s.read(4096)
    f.write(f"\n>>> {cmd}\n".encode() + out)
    sys.stdout.write(out.decode("utf-8", "replace"))

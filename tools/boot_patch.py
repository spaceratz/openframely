#!/usr/bin/env python3
"""Swap the stock boot screens for the OpenFramely ones, writing raw bytes over USB Mass Storage.

Two same-size, in-place overwrites on the eMMC (no partition or filesystem changes):

  logo.bmp           inside the boot partition's Rockchip resource block (bootloader logo)
  bootanimation.zip  inside the system image in the super partition (Android boot animation)

Both files are located by searching your own backup dump for the stock bytes, so nothing here is
specific to one firmware build. The bootanimation.zip slot keeps its exact length: the new zip's
archive comment is grown to fill it, so the end-of-central-directory record stays at the very end
(zip readers find it by scanning back from the end of the file). Before writing, the disk's GPT
must match the dump's, and the live bytes must be stock (write) or ours (undo).

Usage (all read-only unless --write):
  boot_patch.py plan  --dump dump/                     find the offsets, build the patched blobs
  boot_patch.py check --dump dump/ --disk /dev/rdiskN  board in UMS: confirm the live bytes are stock
  boot_patch.py write --dump dump/ --disk /dev/rdiskN  back up both regions, write, read back, verify
  boot_patch.py undo  --dump dump/ --disk /dev/rdiskN  write the stock bytes back

Needs: the board in UMS (FIQ console: `reboot ums`), sudo for raw disk access, and
kiosk/.shots/boot/{logo-openframely.bmp,bootanimation-openframely.zip} from tools/boot_logo.py.
"""

from __future__ import annotations

import argparse
import hashlib
import mmap
import os
import pathlib
import struct
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOT_DIR = ROOT / "kiosk" / ".shots" / "boot"
SECTOR = 512


def need(ok: bool, msg: str) -> None:
    """Hard check (not assert: python -O would strip it, and this script writes to a disk)."""
    if not ok:
        raise SystemExit(f"boot_patch: {msg}")


def read_file(path: pathlib.Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as e:
        raise SystemExit(f"boot_patch: can't read {path}: {e}") from e


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def gpt_parts(disk_img: bytes) -> dict[str, int]:
    """Partition name -> first LBA, from a GPT (dump/gpt_idbloader.img holds LBA 0 onwards)."""
    hdr = disk_img[SECTOR : 2 * SECTOR]
    need(hdr[:8] == b"EFI PART", "no GPT header")
    ent_lba, n, size = struct.unpack("<QII", hdr[72:88])
    out = {}
    for i in range(n):
        e = disk_img[ent_lba * SECTOR + i * size : ent_lba * SECTOR + (i + 1) * size]
        if e[:16] == b"\0" * 16:
            continue
        name = e[56:128].decode("utf-16-le").rstrip("\0")
        out[name] = struct.unpack("<Q", e[32:40])[0]
    return out


def find_logo(boot: bytes) -> tuple[int, int]:
    """(offset in the boot partition, length) of logo.bmp in the Rockchip RSCE resource block."""
    base = boot.find(b"RSCE")
    need(base >= 0, "no RSCE resource block in boot.img")
    num = struct.unpack("<I", boot[base + 12 : base + 16])[0]
    for k in range(num):
        ent = boot[base + SECTOR * (1 + k) : base + SECTOR * (2 + k)]
        need(ent[:4] == b"ENTR", "bad resource entry")
        name = ent[4:260].split(b"\0")[0].decode()
        off, size, hash_size = struct.unpack("<III", ent[260:272])
        if name == "logo.bmp":
            need(hash_size == 0, "resource entry is hashed: patching it would need the hash updated too")
            return base + off * SECTOR, size
    raise SystemExit("logo.bmp not found in the resource block")


def find_zip(super_path: pathlib.Path, stock_zip: bytes) -> int:
    try:
        f = open(super_path, "rb")  # noqa: SIM115 (closed below)
    except OSError as e:
        raise SystemExit(f"boot_patch: can't read {super_path}: {e}") from e
    with f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        i = m.find(stock_zip[:4096])
        need(i >= 0 and i % 4096 == 0, "stock bootanimation.zip not found block-aligned in super.img")
        need(m[i : i + len(stock_zip)] == stock_zip, "stock bootanimation.zip is not stored contiguously")
        need(m.find(stock_zip[:4096], i + 1) < 0, "stock bootanimation.zip found twice")
        return i


def padded_zip(new: bytes, length: int) -> bytes:
    """Rebuild the new zip at exactly `length` bytes by adding a stored `padding.bin` member.
    The boot animation only reads desc.txt and the part folders it names, so the extra file is
    ignored, and the zip stays valid (central directory still at the end)."""
    import io
    import zipfile

    src = zipfile.ZipFile(io.BytesIO(new))

    def build(pad: int) -> bytes:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
            for info in src.infolist():
                z.writestr(info, src.read(info.filename), compress_type=zipfile.ZIP_STORED)
            z.writestr(zipfile.ZipInfo("padding.bin", (2026, 1, 1, 0, 0, 0)), b"\0" * pad, compress_type=zipfile.ZIP_STORED)
        return out.getvalue()

    pad = length - len(build(0))
    need(pad >= 0, f"new boot animation ({len(new)} bytes) is bigger than the {length} byte slot")
    out = build(pad)
    need(len(out) == length, f"padded zip is {len(out)} bytes, slot is {length}")
    return out


def is_ours(it: dict, live: bytes) -> bool:
    """An earlier OpenFramely build in this slot (so re-running write after a design change works)."""
    if it["name"] == "bootanimation.zip":
        import io
        import zipfile

        try:
            return "padding.bin" in zipfile.ZipFile(io.BytesIO(live)).namelist()
        except zipfile.BadZipFile:
            return False
    return live[:54] == it["new"][:54]  # logo.bmp: our BMP header (tools/boot_logo.py writes it the same every time)


def plan(dump: pathlib.Path) -> list[dict]:
    parts = gpt_parts(read_file(dump / "gpt_idbloader.img"))
    boot = read_file(dump / "boot.img")
    logo_off, logo_len = find_logo(boot)
    stock_logo = boot[logo_off : logo_off + logo_len]
    new_logo = read_file(BOOT_DIR / "logo-openframely.bmp")
    need(len(new_logo) == logo_len, f"new logo is {len(new_logo)} bytes, slot is {logo_len}")
    need(new_logo[:2] == b"BM" and new_logo[18:30] == stock_logo[18:30], "BMP header (size/depth) differs from stock")

    stock_zip = read_file(BOOT_DIR / "bootanimation.zip")  # pulled from the board, = the stock file
    zip_off = find_zip(dump / "super.img", stock_zip)
    new_zip = padded_zip(read_file(BOOT_DIR / "bootanimation-openframely.zip"), len(stock_zip))

    return [
        {"name": "logo.bmp", "part": "boot", "byte": parts["boot"] * SECTOR + logo_off, "stock": stock_logo, "new": new_logo},
        {"name": "bootanimation.zip", "part": "super", "byte": parts["super"] * SECTOR + zip_off, "stock": stock_zip, "new": new_zip},
    ]


def _span(byte: int, n: int) -> tuple[int, int]:
    """Sector-aligned (start, length) covering [byte, byte + n): raw disks only take whole sectors."""
    start = byte - byte % SECTOR
    end = byte + n
    return start, end + (-end) % SECTOR - start


def raw_read(disk: str, byte: int, n: int) -> bytes:
    start, length = _span(byte, n)
    try:
        fd = os.open(disk, os.O_RDONLY)
    except OSError as e:
        raise SystemExit(f"boot_patch: can't open {disk} (run with sudo, board in UMS?): {e}") from e
    try:
        os.lseek(fd, start, os.SEEK_SET)
        buf = b""
        while len(buf) < length:
            chunk = os.read(fd, min(length - len(buf), 1 << 20))
            need(bool(chunk), f"short read at byte {start + len(buf)}")
            buf += chunk
    finally:
        os.close(fd)
    return buf[byte - start : byte - start + n]


def raw_write(disk: str, byte: int, data: bytes) -> None:
    """Read-modify-write the covering sectors, so bytes either side of the slot are untouched."""
    start, length = _span(byte, len(data))
    buf = bytearray(raw_read(disk, start, length))
    buf[byte - start : byte - start + len(data)] = data
    try:
        fd = os.open(disk, os.O_RDWR)
    except OSError as e:
        raise SystemExit(f"boot_patch: can't open {disk} for writing: {e}") from e
    try:
        os.lseek(fd, start, os.SEEK_SET)
        for i in range(0, length, 1 << 20):
            need(os.write(fd, bytes(buf[i : i + (1 << 20)])) == len(buf[i : i + (1 << 20)]), "short write")
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["plan", "check", "write", "undo"])
    ap.add_argument("--dump", type=pathlib.Path, default=ROOT / "dump")
    ap.add_argument("--disk", help="raw UMS disk, e.g. /dev/rdisk4 (check with diskutil list)")
    a = ap.parse_args()

    items = plan(a.dump)
    for it in items:
        print(
            f"{it['name']:18s} {it['part']:5s} byte {it['byte']:>11d}  {len(it['new']):>8d} bytes  "
            f"stock {sha(it['stock'])}  new {sha(it['new'])}"
        )
    if a.cmd == "plan":
        return 0
    if not a.disk:
        raise SystemExit("--disk is required")
    # identity: the disk's partition table must be byte-identical to the dump's (wrong disk = stop)
    gpt = read_file(a.dump / "gpt_idbloader.img")[: 34 * SECTOR]
    need(raw_read(a.disk, 0, len(gpt)) == gpt, f"{a.disk} partition table doesn't match {a.dump}/gpt_idbloader.img")
    print(f"{a.disk}: partition table matches the dump")
    if a.disk.startswith("/dev/"):
        subprocess.run(["diskutil", "unmountDisk", a.disk.replace("rdisk", "disk")], capture_output=True)

    # writable states: stock, this build ("new"), or an earlier OpenFramely build ("older": our padded
    # zip, or a BMP that is neither stock nor new but has the stock header). Anything else: stop.
    for it in items:
        live = raw_read(a.disk, it["byte"], len(it["stock"]))
        state = "stock" if live == it["stock"] else "new" if live == it["new"] else "older" if is_ours(it, live) else "UNKNOWN"
        print(f"live {it['name']}: {state}")
        if a.cmd != "check" and state == "UNKNOWN":
            raise SystemExit(f"refusing to write: live {it['name']} is neither stock nor an OpenFramely build")
    if a.cmd == "check":
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    for it in items:
        data = it["new"] if a.cmd == "write" else it["stock"]
        live = raw_read(a.disk, it["byte"], len(data))
        bak = a.dump / f"pre-{a.cmd}-{it['name']}-{stamp}.bin"
        bak.write_bytes(live)
        if live == data:
            print(f"{it['name']}: already done, skipped")
            continue
        raw_write(a.disk, it["byte"], data)
        back = raw_read(a.disk, it["byte"], len(data))
        need(back == data, f"read-back mismatch on {it['name']}: restore from {bak}")
        print(f"{it['name']}: written and verified ({sha(back)}), backup {bak.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

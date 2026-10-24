#!/bin/sh
# Read-only dump of every partition before userdata, plus the first 8 MiB (GPT + idbloader).
set -e
cd "$(dirname "$0")/../dump"
RK=../tools/rkdeveloptool
rd() { echo "== $1 lba=$2 sectors=$3"; $RK rl "$2" "$3" "$1.img"; }
rd gpt_idbloader 0       0x2000
rd security      0x2000  0x2000
rd uboot         0x4000  0x2000
rd trust         0x6000  0x2000
rd misc          0x8000  0x2000
rd dtbo          0xA000  0x2000
rd vbmeta        0xC000  0x800
rd boot          0xC800  $((0x20800-0xC800))
rd recovery      0x20800 $((0x624DB-0x20800))
rd backup        0x624DB $((0x1224DB-0x624DB))
rd metadata      0x1E24DB $((0x1EA4DB-0x1E24DB))
rd baseparameter 0x1EA4DB $((0x1EACDB-0x1EA4DB))
rd super         0x1EACDB $((0x7C6CDB-0x1EACDB))
echo DONE; ls -la *.img; shasum -a 256 *.img > SHA256SUMS

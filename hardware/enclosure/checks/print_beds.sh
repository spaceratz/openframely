#!/bin/sh
# Contact sheet of every print-ready STL as it sits on the bed. Usage: checks/print_beds.sh
set -e
cd "$(dirname "$0")/.."
export CADGEN_TELEMETRY=0 DO_NOT_TRACK=1
C="uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.21 cadgen"
tmp=renders/.bed
rm -rf "$tmp"
mkdir -p "$tmp"
for p in frame_left back_plate gpo_saddle clamp_bars coupons; do
  $C stl snapshot "STL/$p.stl" "$tmp/$p.png" --camera iso --size-profile simple >/dev/null
done
magick montage "$tmp"/frame_left.png "$tmp"/back_plate.png "$tmp"/gpo_saddle.png "$tmp"/clamp_bars.png "$tmp"/coupons.png \
  -tile 3x2 -geometry 800x600+6+6 -background '#F0F2F5' "renders/print-beds.png"
rm -rf "$tmp"
echo "print beds: renders/print-beds.png"

#!/bin/sh
# Composite the demo calendar screenshot (made-up data) into the straight-on render's window.
# Usage: checks/on_wall.sh   (needs renders/hero-front.png; writes renders/on-wall.png)
set -e
cd "$(dirname "$0")/.."
src="renders/hero-front.png"
ui="../../kiosk/screenshots/calendar-month.png"
[ -f "$src" ] && [ -f "$ui" ] || exit 0
# the window is the one dark rectangle in the render: find it, then paste the UI at that size
geo=$(magick "$src" -colorspace gray -threshold 50% -negate -define connected-components:verbose=true \
  -connected-components 8 null: | awk '/graya\(255/ {print $2; exit}')
size=${geo%%+*}
off=${geo#"$size"}
magick "$ui" -resize "$size!" renders/.ui.png
magick "$src" renders/.ui.png -geometry "$off" -composite "renders/on-wall.png"
rm -f renders/.ui.png
echo "on-wall mockup: renders/on-wall.png ($size at $off)"

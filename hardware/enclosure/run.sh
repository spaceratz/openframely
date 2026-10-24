#!/bin/sh
# Rebuild every part, export watertight STLs, run the checks, render the review images.
# Usage: ./run.sh render   (also re-renders renders/*.png, overwriting the old ones)
set -e
mkdir -p checks/out
cd "$(dirname "$0")"
export CADGEN_TELEMETRY=0 DO_NOT_TRACK=1
CAD="uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.21"
# preset: OFLY_PRESET=generic-13.3 OFLY_GPO=uk-single ./run.sh   (see PANELS/GPOS in src/params.py)
if [ -n "$OFLY_PRESET$OFLY_GPO$OFLY_MECH$OFLY_GPO_Y" ]; then
  printf '{"panel": "%s", "gpo": "%s", "mech": "%s", "gpo_y": %s}\n' "${OFLY_PRESET:-framely-15.6}" "${OFLY_GPO:-clipsal-2000}" \
    "${OFLY_MECH:-removed}" "${OFLY_GPO_Y:-0}" >src/preset.json
fi
(cd src && $CAD python assembly.py >/dev/null && $CAD python exploded.py >/dev/null && $CAD python coupons.py >/dev/null && $CAD python saddle_drawing.py >/dev/null && $CAD python plate_drawing.py >/dev/null && $CAD python service_pose.py >/dev/null && $CAD python back_plate_split.py >/dev/null && $CAD python colours.py >/dev/null) # every part + the exploded view
$CAD python checks/export_stls.py
checks/dfam.sh
$CAD python checks/bom.py >/dev/null
$CAD python checks/assembly_guide.py >/dev/null
$CAD python checks/wall_template.py >/dev/null
$CAD python checks/check_fit.py # last, so it sees this run's BOM.md and STLs
if [ "$1" = "render" ]; then
  for j in renders/job-*.json; do
    $CAD cadgen step snapshot --job "$j" >/dev/null
  done
  checks/on_wall.sh
  checks/print_beds.sh
  echo "renders: renders/*.png"
fi

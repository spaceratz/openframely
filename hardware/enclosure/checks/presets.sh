#!/bin/sh
# Build and check every panel/GPO preset in a scratch copy (main outputs untouched).
# Usage: checks/presets.sh     Exit 1 if any combination fails a check.
cd "$(dirname "$0")/.."
rm -rf .variant && mkdir .variant && cp -R src checks run.sh README.md BRIEF.md .variant/ && mkdir -p .variant/renders
fail=0
for combo in "framely-15.6 clipsal-2000 removed" "generic-13.3 clipsal-2000 removed" "generic-17.3 clipsal-2000 removed" \
             "framely-15.6 uk-single removed" "framely-15.6 clipsal-2000 plug" \
             "framely-15.6 clipsal-2000 removed -25" "framely-15.6 clipsal-2000 removed 35" \
             "framely-15.6 clipsal-2000 removed 0 tight" "framely-15.6 clipsal-2000 removed 0 even split"; do
  set -- $combo
  printf '{"panel": "%s", "gpo": "%s", "mech": "%s", "gpo_y": %s, "bezel": "%s", "plate_split": %s}\n' "$1" "$2" "$3" "${4:-0}" \
    "${5:-even}" "$([ "$6" = split ] && echo true || echo false)" \
    > .variant/src/preset.json
  out=$(cd .variant && ./run.sh 2>&1)
  n=$(printf '%s\n' "$out" | grep -c '^FAIL')
  size=$(printf '%s\n' "$out" | grep '^overall:' | sed 's/overall: //')
  printf '%-4s %-13s %-13s %-8s y%-4s %s\n' "$([ "$n" = 0 ] && echo PASS || echo FAIL)" "$1" "$2" "$3" "${4:-0}${5:+ $5}" "$size"
  [ "$n" = 0 ] || { printf '%s\n' "$out" | grep '^FAIL' | sed 's/^/     /'; fail=1; }
done
rm -rf .variant
exit $fail

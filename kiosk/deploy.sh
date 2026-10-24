#!/bin/sh
# Deploy the wall web app to Home Assistant /config/www/kiosk (no HA restart).
# Every open wall polls version.json and reloads itself within about 3s.
# Env: HASS_HOST (ssh alias, default "hass"), OPENFRAMELY_HA_URL (echoed URL, cosmetic).
set -e
cd "$(dirname "$0")/web"
v=$(date +%s)
printf '{"v":"%s"}\n' "$v" > version.json
# cache-bust every asset (HA /local sends max-age=31d; WebView memory cache ignores no-cache)
stage=$(mktemp -d)
cp -R . "$stage/"
sed -i '' -E "s/(href|src)=\"([a-z]+\.(css|js))\"/\1=\"\2?v=$v\"/g" "$stage/index.html"
sed -i '' -E "s/url\(fonts\/([a-z-]+\.woff2)\)/url(fonts\/\1?v=$v)/g" "$stage/style.css"
# font preloads must match the CSS font URLs exactly or the browser downloads them twice
sed -i '' -E "s/href=\"(fonts\/[a-z-]+\.woff2)\"/href=\"\1?v=$v\"/g" "$stage/index.html"
tar czf - -C "$stage" --exclude version.json . | ssh -o BatchMode=yes -o ConnectTimeout=10 "${HASS_HOST:-hass}" \
  'mkdir -p /config/www/kiosk && tar xzf - -C /config/www/kiosk'
# version last, so a reload never sees half-copied files
scp -q -o BatchMode=yes version.json "${HASS_HOST:-hass}":/config/www/kiosk/version.json
rm -rf "$stage"
echo "deployed build $v"

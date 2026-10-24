BOARD="${OPENFRAMELY_BOARD:-192.168.1.50:5555}"
#!/bin/sh
# Build + sign the kiosk APK. Usage: ./build.sh [install]
set -e
cd "$(dirname "$0")"
BT=/opt/homebrew/share/android-commandlinetools/build-tools/36.0.0
JAR=/opt/homebrew/share/android-commandlinetools/platforms/android-36/android.jar
rm -rf build && mkdir -p build/gen build/classes
"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -o build/app-unsigned.apk -I "$JAR" --manifest AndroidManifest.xml \
  --java build/gen build/res.zip --min-sdk-version 26 --target-sdk-version 30
javac --release 11 -classpath "$JAR" -d build/classes build/gen/au/openframely/kiosk/R.java src/au/openframely/kiosk/*.java
"$BT/d8" --min-api 26 --lib "$JAR" --output build $(find build/classes -name '*.class')
(cd build && zip -q app-unsigned.apk classes.dex)
"$BT/zipalign" -f 4 build/app-unsigned.apk build/app-aligned.apk
"$BT/apksigner" sign --ks debug.keystore --ks-pass pass:android --out build/framely-kiosk.apk build/app-aligned.apk
echo "built build/framely-kiosk.apk"
if [ "$1" = install ]; then
  adb -s "$BOARD" install -r build/framely-kiosk.apk
  adb -s "$BOARD" shell am start -n au.openframely.kiosk/.KioskActivity
fi

# OpenFramely agent install guide

Use this guide to take a stock Whale Framely / Zeasn DP159K (BPSDC01) wall calendar and a Home Assistant install, and set up the wall to run this kiosk on your LAN. Read `README.md` first for the hardware overview.

**Verify each step before moving on.** Run the check at the end of each section, and ask the owner when a step needs a physical action (power cable, soldering) or touches production config.

## 0. Preconditions

- Board: DP159K-V3.0 (Rockchip RK3326/PX30, Android 11, `com.zeasn.android.photo.pro` firmware).
- A USB-UART adapter at **3.3 V** (e.g. FT232RL), jumper set to 3V3.
- A **USB-A to USB-C data cable** (USB-C to USB-C does not power this board).
- Home Assistant 2026.10+ with HTTPS (`/config` reachable over a hostname with a valid cert, not a raw IP).
- Android SDK build-tools 36 + platform android-36 (for `aapt2/d8/javac/zipalign/apksigner`).
- A long-lived HA access token for the kiosk, created from the owner's HA user.

## 1. Hardware access (read-only first)

1. Open the case. Pads are labelled on the board (see `docs/board-photos/board-pads.jpg`).
2. Solder or clip: board **TX -> adapter RXD**, board **RX -> adapter TXD**, **GND -> GND**. Leave VCC unconnected.
3. Serial console at **1500000 8N1** (macOS: `tio -b 1500000 /dev/cu.usbserial-XXXX`).
4. Type `fiq` + Enter to get the `debug>` FIQ prompt. The console runs at 1500000 baud; plain `115200` shows garbage.
5. **Full eMMC backup before any write.** From the FIQ prompt, `reboot ums` reboots the board into USB Mass Storage: the whole eMMC enumerates as a disk on your computer (macOS: `/dev/disk4`, needs sudo). Dump every partition with SHA256s into `dump/` (never in git). The FIQ console is dead while in UMS: power-cycle to leave.

Check: dumps exist, sizes match `rkdeveloptool ppt` output, no `0xCC` filler (Rockchip loader-mode reads cap at 32 MiB, so use UMS for the dump).

## 2. Enable ADB (eMMC patches)

The board's bootloader is unlocked (`verifiedbootstate=orange`), so direct partition writes are the install path. Three properties need changing, plus one init rc. **Find the exact sector locations in your own dump** (they change between firmware builds): search the partition image for each property string and patch it in place.

| File | Change | Effect |
|---|---|---|
| `system/etc/prop.default` | `ro.adb.secure=1` -> `0` | adb needs no RSA keys |
| `system/etc/prop.default` | `persist.sys.usb.config=none` -> `mtp,adb` | adb USB gadget exists |
| `vendor/build.prop` | `sys.rkadb.root=0` -> `1`, `persist.items.usb.host=true` -> `false`, add `service.adb.tcp.port=5555` | root adb, device-mode USB, adbd on TCP |

Write via UMS (`reboot ums`, patch the sectors on your computer, power-cycle). Preserve byte lengths (trim trailing padding, pad at EOF). Then verify after boot: `adb connect <board-ip>:5555` works.

Also push `/system/etc/init/zzz_kiosk.rc` (trigger it `on boot` and `on property:sys.boot_completed=1`; `late-init` runs before the vendor's USB setup and gets overridden) that forces the adb USB config and starts adbd.

Checks: `adb shell id` answers; adbd survives a power cycle.

## 3. Home Assistant backend

1. Copy `ha-integration/custom_components/family_kiosk/` to `/config/custom_components/family_kiosk/`.
2. Add `family_kiosk:` to `configuration.yaml`.
3. Validate (`ha core check`) and restart core once.
4. Create a long-lived token for the wall.

Checks with the token:
- `GET /api/family_kiosk/state` returns JSON (`rev`, `events`, `kids`).
- `GET /api/family_kiosk/ics_url` returns a URL whose fetch gives `BEGIN:VCALENDAR`.

Data lives in `/config/.storage/family_kiosk`. Pure logic is unit-tested: `pytest ha-integration/tests -q`.

## 4. Web app

1. Edit `kiosk/web/config.js` from `config.example.js`: your HA URL, people (`members`: key/name/colour), kids, lights, ACs, weather entity, night hours, and `aliases` (every spelling of each person's name used in calendar titles). **No secrets go in web files.**
2. Deploy: `kiosk/deploy.sh` copies to `/config/www/kiosk/` with cache-busting. Every open wall reloads itself within about 3 s (it polls `version.json`). No HA restart.
3. The wall talks to HA only: REST for the family_kiosk API (with the token), WebSocket for lights/AC/weather/sun live state.

Check: open `https://<ha>/local/kiosk/index.html#token=<token>` in a desktop browser at 1920x1080; month, day, chores, home and settings views all render.

## 5. APK

1. Edit `DEFAULT_URL` in `android/src/au/openframely/kiosk/KioskActivity.java` if you don't want to pass it at runtime.
2. Build: `android/build.sh` (needs the SDK tools). Install: `build.sh install` over network adb.
3. Store secrets on the device (never in web files):
   `adb shell am start -n au.openframely.kiosk/.KioskActivity --es token <ha-token> --es url <kiosk-url>`
   They land in the app's private storage and are passed to the page in the URL fragment (never sent to the server).
4. Make it HOME so the wall boots into it:
   `adb shell cmd package set-home-package au.openframely.kiosk` (or tap once on the HOME picker).
5. Disable the stock app so no telemetry leaves: `adb shell pm disable-user com.zeasn.android.photo.pro`, and block `whalephoto.zeasn.tv` / `saas.zeasn.tv` at the router.

Checks: `adb shell dumpsys window | grep mCurrentFocus` shows the kiosk; a reboot lands back in it; the board's only open TCP connections go to HA (and adb).

### On-device settings

The gear icon opens the settings view. The APK applies Wi-Fi scan/join (with an on-screen keyboard), timezone, brightness and screen-off-at-night **on the device** by speaking the adb protocol to the board's own adbd on 127.0.0.1:5555 (`LocalShell.java`, enabled by `ro.adb.secure=0`) as the shell user. This board rejects AOSP platform-signed APKs because its platform cert is vendor-specific. The APK mirrors current settings to `/sdcard/Android/data/au.openframely.kiosk/files/settings.json` for remote inspection.

## 6. Optional: Google Calendar one-way sync

1. `kiosk/google/Code.gs` is an Apps Script web app (logged in as the calendar owner): new project, paste, run `setup()` once (writes the KEY property and prints it), deploy as web app (Execute as Me, access: **Anyone**).
2. On the wall: settings -> Google Calendar -> paste `<exec-url>?key=<KEY>`.
3. Home Assistant polls the feed every 30 s and caches the last good copy, so the wall talks to HA rather than Google and keeps working offline. Title tags (`Riley, Casey: Swimming`, `[Riley Casey]`, `#riley`, aliases like Dad/Mum/Family/All) assign people and are stripped for display.

### Tagging people in Google event titles

Case-insensitive, formats can be combined, and recognised names are removed from the displayed title.

| Title in Google | Shows as | For |
|---|---|---|
| `Riley, Casey: Swimming` | Swimming | Riley, Casey |
| `Swimming [Riley Casey]` | Swimming | Riley, Casey |
| `Swimming #riley #casey` | Swimming | Riley, Casey |
| `Everyone: BBQ`, `Family: BBQ`, `BBQ [all]` or `BBQ #everyone` | BBQ | everyone |
| `School photos` (no tags) | School photos | everyone |

Add every spelling of each person's name to `aliases` in `kiosk/web/config.js`. Anything that
isn't a known name is left alone (`Note: bins out`, `Meeting [Zoom]`).

After editing `Code.gs`, use **Deploy -> Manage deployments -> edit -> Version: New version** so the URL stays the same.

## 7. Optional: fully offline

- Local DNS on your LAN (e.g. Pi-hole `dns.hosts`) so the HA hostname resolves to HA's LAN address: the cert stays valid and the wall needs no internet.
- Router as NTP server, and set the board's `settings global ntp_server` to it.
- ICS feed from `/api/family_kiosk/ics_url` for Thunderbird/phones (add `&events=all` to include the cached Google copy).

## 8. Migrating existing Framely events

`kiosk/tools/framely_export.py` exports events from the Zeasn cloud to tagged ICS + raw JSON without HA (needs `kiosk/.secrets/framely-device.json` and `kiosk/.secrets/keys.json`, both untracked). Import the ICS into Google Calendar, or POST the JSON to `/api/family_kiosk/op` with `{"op":"import_events","source":"framely",...}`. `tools/whale_api.py` documents the cloud API. Keep your board's MAC and SN private: they are the only credentials the vendor cloud checks.

## 8b. Optional: replace the boot screens

The stock board shows a vendor logo (bootloader, `logo.bmp` in the boot partition's resource
block) then a vendor boot animation (`/system/media/bootanimation.zip`) before the kiosk.
Both are swapped by same-size, in-place overwrites over UMS, located by searching your own dump:

1. `uv run --no-project --python 3.12 --with pillow --with fonttools --with brotli python tools/boot_logo.py`
   builds the OpenFramely logo and a one-frame animation in `kiosk/.shots/boot/`.
2. Pull the stock animation: `adb pull /system/media/bootanimation.zip kiosk/.shots/boot/`.
3. `python3 tools/boot_patch.py plan` finds both offsets in `dump/` and builds the patched bytes.
4. FIQ console `reboot ums`, then `sudo python3 tools/boot_patch.py check --disk /dev/rdiskN`
   (refuses unless the disk's partition table matches your dump and the bytes are stock).
5. `sudo python3 tools/boot_patch.py write --disk /dev/rdiskN` backs up both regions to `dump/`,
   writes, and reads back. Power-cycle. `undo` puts the stock bytes back.

## 9. Verification (whole system)

1. Wall boots into the kiosk with no adb interaction.
2. Create an event on the wall -> appears on every other screen (phone browser) in about a second (long-poll).
3. Create/tick a chore box -> week total updates; tick is once per day; future days locked.
4. Toggle a light on the wall -> the HA state flips, and an external flip reflects on the wall in under a second.
5. Unplug the internet -> everything above still works (LAN only).
6. `git ls-files | xargs grep -l <token>` finds nothing.
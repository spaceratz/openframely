# Development

How the pieces fit, how to ship a change, and what trips people up on this hardware.
Install steps are in `AGENT-GUIDE.md`.

## Key files

| Path | What |
|---|---|
| `kiosk/web/index.html`, `style.css`, `app.js` | the wall app |
| `kiosk/web/lib.js` | pure helpers (dates, times, chores), unit-tested |
| `kiosk/web/tags.js` | title tag parser, unit-tested |
| `kiosk/web/icons.js` | inline SVG icons and weather icons |
| `kiosk/web/fonts/` | Inter woff2 (bundled, no CDN) |
| `kiosk/web/config.example.js` | members, kids, lights, ACs, weather entity, night hours (copy to `config.js`, no secrets) |
| `ha-integration/custom_components/family_kiosk/` | HA backend: events, Google cache, chore money, ICS |
| `kiosk/android/src/.../LocalShell.java` | on-device adb client used to apply settings |
| `kiosk/google/Code.gs` | Apps Script calendar feed |
| `kiosk/deploy.sh` | hot deploy of the web app |
| `kiosk/tools/board.mjs` | `bun kiosk/tools/board.mjs eval '<js>'` / `shot out.png` against the board's live WebView over DevTools |
| `kiosk/tools/shots.py` | README screenshots against a fake HA with demo data (`kiosk/tools/demo/mock.js`) |
| `kiosk/tools/framely_export.py` | Framely cloud to ICS + raw JSON |

## Deploying changes

- **Web app (no HA restart):** `kiosk/deploy.sh`. It stages `web/`, adds `?v=<build>` to every
  asset and font URL, copies to `/config/www/kiosk/`, then writes `version.json` last. Every open
  wall polls `version.json` every 3 s and reloads itself, so a change shows in about 5 s.
- **APK:** `kiosk/android/build.sh install` (bump `versionCode` in the manifest). Settings survive
  reinstalls. Set or replace secrets with `am start ... --es token <HA token> --es gcal <url>`.
- **HA integration:** Python only loads at startup, so it needs a Core restart. Copy
  `family_kiosk` to `/config/custom_components/`, run `ha core check`, then `ha core restart`.
  The wall reconnects by itself about 30 s later.

## ICS export (Thunderbird, phones)

`GET /api/family_kiosk/ics_url` (HA auth) returns a subscribe URL. Add `&events=all` to include
the cached Google events.

- **Thunderbird:** Calendar -> New Calendar -> On the Network -> paste the URL -> Subscribe.
- **iPhone:** Settings -> Calendar -> Accounts -> Add Account -> Other -> Add Subscribed Calendar.

## Gotchas

- **WebView 109** (Android 11) has no `color-mix()`. Member tints are set as `--mc`, `--mc-t1`,
  `--mc-t2`, `--mc-l` by `tint()` in `app.js`. Check new CSS against Chrome 109.
- **The wall is slow** (RK3326, GPU at 200 MHz). Only the visible view redraws; other views are
  marked stale and redrawn when opened. Keep it that way.
- **HA `/local` sends `max-age=31 days`**, and the WebView memory cache ignores `no-cache` on
  script tags. `deploy.sh` cache-busts with `?v=`; keep that step.
- **Settings sent by `am start` to a running kiosk** arrive as a fragment-only navigation (no
  page load). The page listens for `hashchange`, stores them, then reloads.
- Top-level `let`/`const` in `app.js` aren't `window` properties, though `board.mjs eval` can
  reach them in the same script scope. DevTools returns `{}` for unserialisable values, so wrap
  results in `JSON.stringify`.
- HA websocket: `call_service` uses `service_data` + `target`. `subscribe_entities` events arrive
  as `{a:{...}}` (initial) then `{c:{eid:{"+":{s,a},"-":{a:[...]}}}}`.
- macOS Android File Transfer claims the board's USB interface, so use network adb.

## Rules

- Never commit the HA token, the Google feed URL or key, or the device MAC/SN.
- Don't break HOME (`au.openframely.kiosk/.KioskActivity`) and don't write the eMMC without a backup.

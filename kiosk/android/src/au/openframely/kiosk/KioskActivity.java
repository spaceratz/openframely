package au.openframely.kiosk;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Calendar;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Fullscreen WebView kiosk with on-device settings.
 *
 * Secrets (HA token, Google feed URL) live only in private prefs and are
 * handed to the page in the URL fragment. Set remotely with:
 *   adb shell am start -n au.openframely.kiosk/.KioskActivity --es token T --es gcal URL
 *
 * Device settings (Wi-Fi, timezone, brightness, screen sleep schedule) are
 * changed from the page through the "Kiosk" JS bridge and applied by this app
 * itself through LocalShell (the board's own adbd on 127.0.0.1), so nothing
 * external is needed. A copy of the settings is written to
 * /sdcard/Android/data/au.openframely.kiosk/files/settings.json for remote reading.
 */
public class KioskActivity extends Activity {
    private static final String DEFAULT_URL =
        "https://ha.example.test:8123/local/kiosk/index.html";
    private static final long WAKE_MS = 120_000;

    private WebView web;
    private View sleepCover;
    private SharedPreferences prefs;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService bg = Executors.newSingleThreadExecutor();
    private boolean asleep = false;
    private long wakeUntil = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("kiosk", MODE_PRIVATE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        WebView.setWebContentsDebuggingEnabled(true);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        web.clearCache(true);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, int code, String desc, String url) {
                v.postDelayed(KioskActivity.this::loadHome, 15000);
            }
        });
        web.setWebChromeClient(new WebChromeClient());
        web.addJavascriptInterface(new Bridge(), "Kiosk");

        // screen sleep: black cover over everything + backlight at minimum; a tap wakes it
        sleepCover = new View(this);
        sleepCover.setBackgroundColor(Color.BLACK);
        sleepCover.setVisibility(View.GONE);
        sleepCover.setOnTouchListener((v, e) -> {
            if (e.getAction() == MotionEvent.ACTION_DOWN) { wakeUntil = System.currentTimeMillis() + WAKE_MS; wake(); }
            return true;
        });
        FrameLayout root = new FrameLayout(this);
        root.addView(web);
        root.addView(sleepCover);
        hideUi();
        setContentView(root);
        registerReceiver(new BroadcastReceiver() {
            @Override public void onReceive(Context c, Intent i) { hideUi(); }
        }, new IntentFilter(Intent.ACTION_CLOSE_SYSTEM_DIALOGS));
        saveExtras(getIntent());
        loadHome();
        ui.post(scheduler);
        writeSettingsFile();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (saveExtras(intent)) loadHome();
    }

    private boolean saveExtras(Intent i) {
        if (i == null || i.getExtras() == null) return false;
        SharedPreferences.Editor e = prefs.edit();
        boolean changed = false;
        for (String k : new String[]{"token", "gcal", "url"}) {
            if (i.hasExtra(k)) { e.putString(k, i.getStringExtra(k)); changed = true; }
        }
        e.apply();
        return changed;
    }

    private void loadHome() {
        String url = prefs.getString("url", "");
        if (url.isEmpty()) url = DEFAULT_URL;
        web.loadUrl(url + "#token=" + Uri.encode(prefs.getString("token", ""))
            + "&gcal=" + Uri.encode(prefs.getString("gcal", "")));
    }

    private void hideUi() {
        web.setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
    }

    @Override
    public void onBackPressed() { /* swallow */ }

    // ---------------------------------------------------------------- sleep

    private final Runnable scheduler = new Runnable() {
        @Override public void run() {
            boolean want = inSleepWindow() && System.currentTimeMillis() > wakeUntil;
            if (want && !asleep) sleep();
            else if (!want && asleep) wake();
            ui.postDelayed(this, 20_000);
        }
    };

    private boolean inSleepWindow() {
        if (!prefs.getBoolean("sleepOn", false)) return false;
        int from = mins(prefs.getString("sleepFrom", "22:00")), to = mins(prefs.getString("sleepTo", "06:30"));
        Calendar c = Calendar.getInstance();
        int now = c.get(Calendar.HOUR_OF_DAY) * 60 + c.get(Calendar.MINUTE);
        return from <= to ? now >= from && now < to : now >= from || now < to;
    }

    private static int mins(String hhmm) {
        try {
            String[] p = hhmm.split(":");
            return Integer.parseInt(p[0]) * 60 + Integer.parseInt(p[1]);
        } catch (RuntimeException e) {
            return 0;
        }
    }

    private void sleep() {
        asleep = true;
        sleepCover.setVisibility(View.VISIBLE);
        shellAsync("settings put system screen_brightness_mode 0; settings put system screen_brightness 1");
        js("window.onKioskSleep&&onKioskSleep(true)");
    }

    private void wake() {
        asleep = false;
        sleepCover.setVisibility(View.GONE);
        applyBrightness();
        js("window.onKioskSleep&&onKioskSleep(false)");
    }

    private void applyBrightness() {
        shellAsync("settings put system screen_brightness_mode 0; settings put system screen_brightness "
            + prefs.getInt("brightness", 200));
    }

    // ---------------------------------------------------------------- helpers

    private void shellAsync(String cmd) {
        bg.execute(() -> { try { LocalShell.run(cmd); } catch (Exception ignored) { /* retried next change */ } });
    }

    private void js(String code) { ui.post(() -> web.evaluateJavascript(code, null)); }

    private void reply(String id, Object result, String error) {
        try {
            JSONObject o = new JSONObject();
            o.put("ok", error == null);
            if (error != null) o.put("error", error); else o.put("result", result);
            js("window.__kioskCb&&__kioskCb(" + JSONObject.quote(id) + "," + o + ")");
        } catch (Exception ignored) { /* page will time out */ }
    }

    private JSONObject settingsJson() throws Exception {
        JSONObject o = new JSONObject();
        o.put("brightness", prefs.getInt("brightness", 200));
        o.put("sleepOn", prefs.getBoolean("sleepOn", false));
        o.put("sleepFrom", prefs.getString("sleepFrom", "22:00"));
        o.put("sleepTo", prefs.getString("sleepTo", "06:30"));
        o.put("timezone", java.util.TimeZone.getDefault().getID());
        o.put("asleep", asleep);
        o.put("appVersion", getPackageManager().getPackageInfo(getPackageName(), 0).versionName);
        return o;
    }

    /** Serial, MAC, wifi strength, build: read-only identity, for the settings page. */
    private JSONObject deviceInfo() throws Exception {
        JSONObject o = new JSONObject();
        o.put("Model", android.os.Build.MODEL);
        o.put("Device", android.os.Build.DEVICE);
        o.put("Android", "11 (build " + android.os.Build.DISPLAY + ")");
        o.put("App", getPackageManager().getPackageInfo(getPackageName(), 0).versionName);
        String sn = "", mac = "";
        try {
            java.util.Scanner sc = new java.util.Scanner(Runtime.getRuntime().exec("getprop ro.serialno").getInputStream()).useDelimiter("\\A");
            sn = sc.hasNext() ? sc.next().trim() : "";
        } catch (Exception ignored) { }
        try {
            java.util.Scanner sc = new java.util.Scanner(Runtime.getRuntime().exec("cat /sys/class/net/wlan0/address").getInputStream()).useDelimiter("\\A");
            mac = sc.hasNext() ? sc.next().trim() : "";
        } catch (Exception ignored) { }
        try {
            String sig = LocalShell.run("dumpsys wifi | grep -m1 'mWifiInfo SSID'").trim();
            java.util.regex.Matcher ss = java.util.regex.Pattern.compile("SSID: ([^,]+),").matcher(sig);
            if (ss.find()) o.put("Wi-Fi network", ss.group(1));
            java.util.regex.Matcher m = java.util.regex.Pattern.compile("RSSI: (-[0-9]+)").matcher(sig);
            if (m.find()) {
                int rssi = Integer.parseInt(m.group(1));
                o.put("Wi-Fi signal", (rssi > -55 ? "Excellent" : rssi > -67 ? "Good" : rssi > -78 ? "Fair" : "Weak") + " (" + rssi + " dBm)");
            }
        } catch (Exception ignored) { }
        o.put("Serial", sn.isEmpty() ? "n/a" : sn);
        o.put("Wi-Fi MAC", mac.isEmpty() ? "n/a" : mac);
        o.put("Uptime", android.text.format.DateUtils.formatElapsedTime(android.os.SystemClock.elapsedRealtime() / 1000));
        return o;
    }

    private void writeSettingsFile() {
        bg.execute(() -> {
            try {
                File dir = getExternalFilesDir(null);
                if (dir == null) return;
                try (FileOutputStream f = new FileOutputStream(new File(dir, "settings.json"))) {
                    f.write(settingsJson().toString(1).getBytes(StandardCharsets.UTF_8));
                }
            } catch (Exception ignored) { /* best effort */ }
        });
    }

    static JSONArray parseScan(String out) throws Exception {
        Map<String, JSONObject> best = new LinkedHashMap<>();
        for (String line : out.split("\n")) {
            String[] f = line.trim().split("\\s+", 5);
            if (f.length < 5 || !f[0].matches("([0-9a-f]{2}:){5}[0-9a-f]{2}")) continue;
            String rest = f[4];
            int b = rest.indexOf('[');
            String ssid = (b >= 0 ? rest.substring(0, b) : rest).trim();
            String flags = b >= 0 ? rest.substring(b) : "";
            if (ssid.isEmpty()) continue;
            int rssi = Integer.parseInt(f[2]);
            String sec = flags.contains("SAE") && !flags.contains("PSK") ? "wpa3"
                : flags.contains("PSK") || flags.contains("WPA") ? "wpa2" : "open";
            JSONObject cur = best.get(ssid);
            if (cur == null || cur.getInt("rssi") < rssi) {
                JSONObject n = new JSONObject();
                n.put("ssid", ssid); n.put("rssi", rssi); n.put("security", sec);
                n.put("band", Integer.parseInt(f[1]) > 4000 ? "5 GHz" : "2.4 GHz");
                best.put(ssid, n);
            }
        }
        JSONArray a = new JSONArray();
        best.values().stream().sorted((x, y) -> y.optInt("rssi") - x.optInt("rssi")).forEach(a::put);
        return a;
    }

    // ---------------------------------------------------------------- JS bridge

    /** Fixed actions only, no arbitrary shell from the page. */
    private final class Bridge {
        @JavascriptInterface
        public void call(String id, String action, String argsJson) {
            bg.execute(() -> {
                try {
                    JSONObject a = new JSONObject(argsJson == null || argsJson.isEmpty() ? "{}" : argsJson);
                    reply(id, handle(action, a), null);
                } catch (Exception e) {
                    reply(id, null, e.getMessage() == null ? e.toString() : e.getMessage());
                }
            });
        }

        private Object handle(String action, JSONObject a) throws Exception {
            switch (action) {
                case "getSettings":
                    return settingsJson();
                case "deviceInfo":
                    return deviceInfo();
                case "wifiStatus": {
                    String st = LocalShell.run("cmd wifi status");
                    JSONObject o = new JSONObject();
                    java.util.regex.Matcher m = java.util.regex.Pattern.compile("connected to \"([^\"]*)\"").matcher(st);
                    o.put("ssid", m.find() ? m.group(1) : "");
                    o.put("enabled", st.contains("Wifi is enabled"));
                    String ip = LocalShell.run("ip -4 -o addr show wlan0");
                    m = java.util.regex.Pattern.compile("inet (\\d+\\.\\d+\\.\\d+\\.\\d+)").matcher(ip);
                    o.put("ip", m.find() ? m.group(1) : "");
                    return o;
                }
                case "wifiScan":
                    LocalShell.run("cmd wifi start-scan");
                    Thread.sleep(4000);
                    return parseScan(LocalShell.run("cmd wifi list-scan-results"));
                case "wifiConnect": {
                    String ssid = a.getString("ssid"), sec = a.optString("security", "wpa2");
                    if (!sec.matches("open|owe|wpa2|wpa3")) throw new IllegalArgumentException("bad security");
                    String pass = a.optString("password", "");
                    String out = LocalShell.run("cmd wifi connect-network " + LocalShell.q(ssid) + " " + sec
                        + (sec.equals("open") || sec.equals("owe") ? "" : " " + LocalShell.q(pass)));
                    for (int i = 0; i < 20; i++) {
                        Thread.sleep(1000);
                        if (LocalShell.run("cmd wifi status").contains("connected to \"" + ssid + "\"")) return "connected";
                    }
                    throw new Exception("Couldn't join " + ssid + (out.trim().isEmpty() ? "" : ": " + out.trim()));
                }
                case "setTimezone": {
                    String tz = a.getString("timezone");
                    if (!java.util.Arrays.asList(java.util.TimeZone.getAvailableIDs()).contains(tz))
                        throw new IllegalArgumentException("unknown timezone");
                    LocalShell.run("settings put global auto_time_zone 0; service call alarm 3 s16 " + LocalShell.q(tz));
                    java.util.TimeZone.setDefault(java.util.TimeZone.getTimeZone(tz));
                    writeSettingsFile();
                    return tz;
                }
                case "setBrightness": {
                    int v = Math.max(5, Math.min(255, a.getInt("value")));
                    prefs.edit().putInt("brightness", v).apply();
                    if (!asleep) applyBrightness();
                    writeSettingsFile();
                    return v;
                }
                case "setSleep": {
                    SharedPreferences.Editor e = prefs.edit();
                    e.putBoolean("sleepOn", a.getBoolean("on"));
                    if (a.has("from")) e.putString("sleepFrom", a.getString("from"));
                    if (a.has("to")) e.putString("sleepTo", a.getString("to"));
                    e.apply();
                    wakeUntil = 0;
                    ui.post(scheduler);
                    writeSettingsFile();
                    return settingsJson();
                }
                case "sleepNow":
                    wakeUntil = 0;
                    ui.post(KioskActivity.this::sleep);
                    return true;
                case "reload":
                    ui.post(KioskActivity.this::loadHome);
                    return true;
                default:
                    throw new IllegalArgumentException("unknown action " + action);
            }
        }
    }
}

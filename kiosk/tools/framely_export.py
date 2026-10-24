"""Export events from the Whale Framely cloud to ICS and raw JSON.

Queries the Zeasn cloud API directly (without Home Assistant) so you can migrate
your existing events before retiring the stock app.

  python3 tools/framely_export.py [outdir]

Needs (both untracked in kiosk/.secrets/):
  .secrets/keys.json            {"access_key": "...", "hmac_key": "..."} (from the stock APK)
  .secrets/framely-device.json  {product_id, brand_id, device_set_id, mac, sn, terminal_id}

Writes to outdir (default .secrets/export-<date>/):
  framely-raw.json          every event as returned by listByPage, tombstones included
  framely-members.json      bound members (name, mobileId)
  framely-all.ics           live events, titles tagged "Riley, Casey: Swimming"
                            (the kiosk's Google tag format), RRULEs kept

Title tags use the full member names (config.js). Events for every member
are tagged "Family:".
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import http.client
import json
import pathlib
import sys
import time
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
SECRETS = ROOT / ".secrets"
TZ = ZoneInfo("Australia/Perth")
FAMILY = {"daddy", "sam", "robin", "jamie", "riley", "casey"}
SAAS_HOST = "saas.zeasn.tv"
CAL_HOST = "whalephoto.zeasn.tv"


class WhaleFramelyClient:
    """Minimal synchronous HTTP client for exporting from the Zeasn cloud API."""

    def __init__(
        self,
        access_key: str,
        hmac_key: str,
        product_id: str,
        brand_id: str,
        device_set_id: str,
        mac: str,
        sn: str,
        terminal_id: str | None = None,
    ):
        self._access_key = access_key
        self._hmac_key = hmac_key
        self._product_id = product_id
        self._brand_id = brand_id
        self._device_set_id = device_set_id
        self._mac = mac
        self._sn = sn
        self._terminal_id = terminal_id
        self._token: str | None = None

    def _sign(self, path: str, ts: str) -> str:
        digest = hmac.new(self._hmac_key.encode(), (path + ts).encode(), hashlib.sha1).digest()
        sig = base64.b64encode(digest).decode().strip()
        return f"{self._access_key}:{sig}:{ts}"

    def _headers(self, path: str) -> dict[str, str]:
        mac = self._mac.replace(":", "")
        client = mac[:6] + "fffe" + mac[6:] if len(mac) > 6 else mac
        h = {
            "User-Agent": f"DPClient/1.1(Client:{client})",
            "Authorization": self._sign(path, str(int(time.time() * 1000))),
            "countryCode": "au",
            "langCode": "en",
            "osType": "Android",
            "androidVersion": "11",
            "appVersion": "1.7.0",
        }
        if self._token:
            h["token"] = self._token
        return h

    def _request(self, host: str, method: str, path: str, payload=None, query: str = ""):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = self._headers(path)
        if body is not None:
            headers["Content-Type"] = "application/json;charset=UTF-8"
        conn = http.client.HTTPSConnection(host, timeout=20)
        try:
            conn.request(method, path + query, body, headers)
            raw = conn.getresponse().read().decode()
        finally:
            conn.close()
        try:
            data = json.loads(raw)
        except ValueError as err:
            raise RuntimeError(f"bad JSON from {path}: {raw[:200]}") from err
        if data.get("errorCode") not in ("0", 0, None):
            raise RuntimeError(f"{path}: {data.get('errorCode')} {data.get('errorMsg')}")
        return data.get("data")

    def ensure_token(self) -> None:
        if self._token:
            return
        form = {
            "productId": self._product_id,
            "brandId": self._brand_id,
            "deviceSetId": self._device_set_id,
            "mac": self._mac,
            "deviceType": "Zeasn_Android_Calendar",
            "functionType": "1",
            "ifGetTvDetail": "1",
            "iconResolution": "",
            "terminalType": "Calendar",
            "sn": self._sn,
            "osVersion": "11",
            "productType": "",
        }
        body = "&".join(f"{k}={v}" for k, v in form.items())
        headers = self._headers("/auth-api/api/v1/auth/deviceSign")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        conn = http.client.HTTPSConnection(SAAS_HOST, timeout=20)
        try:
            conn.request("POST", "/auth-api/api/v1/auth/deviceSign", body.encode(), headers)
            raw = conn.getresponse().read().decode()
        finally:
            conn.close()
        try:
            data = json.loads(raw)
        except ValueError as err:
            raise RuntimeError(f"deviceSign bad JSON: {raw[:200]}") from err
        if data.get("errorCode") != "0":
            raise RuntimeError(f"deviceSign: {data.get('errorMsg')}")
        self._token = data["data"]["token"]

    def startup(self) -> str:
        if self._terminal_id:
            return self._terminal_id
        self.ensure_token()
        payload = {
            "mac": self._mac,
            "sn": self._sn,
            "productId": self._product_id,
            "brandId": self._brand_id,
            "channelId": "1",
            "deviceSetId": self._device_set_id,
            "clientType": 5,
            "softwareVersion": 1070004,
            "softDisplayName": "touch",
            "availableSpace": 10000,
        }
        data = self._request(CAL_HOST, "POST", "/photo/api/v1/calendar/startup", payload, "?langCode=en&countryCode=au")
        self._terminal_id = str(data["terminalId"])
        return self._terminal_id

    def list_members(self) -> list[dict]:
        self.ensure_token()
        tid = self.startup()
        return (
            self._request(
                CAL_HOST, "GET", "/photo/api/v1/calendar/bindingList", None, f"?terminalId={tid}&includeVirtualUser=true&langCode=en"
            )
            or []
        )

    def get_events(self, updated_min: int = 0, size: int = 200) -> list[dict]:
        self.ensure_token()
        tid = self.startup()
        data = self._request(
            CAL_HOST,
            "GET",
            "/photo/api/v1/calendar/event/listByPage",
            None,
            f"?terminalId={tid}&updatedMin={updated_min}&size={size}&langCode=en",
        )
        return (data or {}).get("eventList") or []


def esc(text):
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def fold(line):
    out, raw = [], line.encode()
    while len(raw) > 75:
        cut = 75
        while (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(raw[:cut].decode())
        raw = b" " + raw[cut:]
    out.append(raw.decode())
    return out


def tag_title(summary: str, raw_keys: list) -> str:
    keys: list[str] = [k for k in raw_keys if k]
    if not keys:
        return summary
    if set(keys) >= FAMILY:
        return f"Family: {summary}"
    order = ["daddy", "sam", "robin", "jamie", "riley", "casey"]
    names = [k.capitalize() for k in sorted(set(keys), key=lambda k: order.index(k) if k in order else 99)]
    return f"{', '.join(names)}: {summary}"


def ms_local(ms):
    return datetime.datetime.fromtimestamp(int(ms) / 1000, TZ)


def to_ics(events, member_key):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//dp159k//framely-export//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Framely export",
        "X-WR-TIMEZONE:Australia/Perth",
        # Perth has no DST, so a single STANDARD block is a complete definition
        "BEGIN:VTIMEZONE",
        "TZID:Australia/Perth",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:AWST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    n = 0
    for ev in events:
        if str(ev.get("status")) == "-1" or not ev.get("summary"):
            continue
        mids = ev.get("invitationList") or ([str(ev["mobileId"])] if ev.get("mobileId") else [])
        keys = [member_key.get(str(m)) for m in mids]
        lines += ["BEGIN:VEVENT", f"UID:framely-{ev['eventId']}@dp159k", f"DTSTAMP:{stamp}"]
        if str(ev.get("isAllDay")) == "1":
            s = ev["startDate"].replace("-", "")
            e = (ev.get("endDate") or ev["startDate"]).replace("-", "")
            if e <= s:
                e = (datetime.date.fromisoformat(ev["startDate"]) + datetime.timedelta(days=1)).strftime("%Y%m%d")
            lines += [f"DTSTART;VALUE=DATE:{s}", f"DTEND;VALUE=DATE:{e}"]
        else:
            lines += [
                f"DTSTART;TZID=Australia/Perth:{ms_local(ev['startDateTime']):%Y%m%dT%H%M%S}",
                f"DTEND;TZID=Australia/Perth:{ms_local(ev['endDateTime']):%Y%m%dT%H%M%S}",
            ]
        rec = ev.get("recurrence")
        if rec:
            try:
                rules = json.loads(rec) if isinstance(rec, str) else rec
            except ValueError:
                rules = [rec]  # already a bare RRULE string
            lines += [r for r in rules if str(r).startswith("RRULE:")]
        lines.append(f"SUMMARY:{esc(tag_title(ev['summary'], keys))}")
        if ev.get("description"):
            lines.append(f"DESCRIPTION:{esc(ev['description'])}")
        if ev.get("location"):
            lines.append(f"LOCATION:{esc(ev['location'])}")
        lines.append("END:VEVENT")
        n += 1
    lines.append("END:VCALENDAR")
    return "\r\n".join(f for line in lines for f in fold(line)) + "\r\n", n


def main():
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else SECRETS / f"export-{datetime.date.today()}"
    out.mkdir(parents=True, exist_ok=True)
    try:
        keys = json.loads((SECRETS / "keys.json").read_text())
        dev = json.loads((SECRETS / "framely-device.json").read_text())
    except (OSError, ValueError) as err:
        sys.exit(f"need .secrets/keys.json and .secrets/framely-device.json (see docstring): {err}")
    client = WhaleFramelyClient(
        keys["access_key"],
        keys["hmac_key"],
        dev["product_id"],
        dev["brand_id"],
        dev["device_set_id"],
        dev["mac"],
        dev["sn"],
        dev.get("terminal_id"),
    )
    client.startup()
    members = client.list_members()
    events = client.get_events(0, 1000)
    member_key = {str(m["mobileId"]): str(m.get("name", "")).strip().lower() for m in members}
    (out / "framely-members.json").write_text(
        json.dumps([{"name": m.get("name"), "mobileId": str(m["mobileId"])} for m in members], indent=1)
    )
    (out / "framely-raw.json").write_text(json.dumps(events, indent=1))
    ics, n = to_ics(events, member_key)
    (out / "framely-all.ics").write_text(ics, newline="")
    print(f"{len(events)} raw events ({n} live) from {len(members)} members -> {out}")


if __name__ == "__main__":
    main()

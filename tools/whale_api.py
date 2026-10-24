#!/usr/bin/env python3
"""Whale Framely cloud API client (reverse-engineered).
Commands: token | login | help
Base: saas.zeasn.tv (auth+user), whalephoto.zeasn.tv (calendar).
Auth: Authorization: hmacKey:HMAC-SHA1(key, path+tsMs):tsMs (path WITH leading slash).
User-Agent: DPClient/1.1(Client:<mac-nosep+fffe+rest>)."""

import base64
import hashlib
import hmac
import http.client
import json
import sys
import time
import urllib.parse
from pathlib import Path

# credentials live outside git: kiosk/.secrets/whale.json (gitignored)
_SECRETS = Path(__file__).resolve().parent.parent / "kiosk/.secrets/whale.json"
try:
    _S = json.loads(_SECRETS.read_text())
except (OSError, ValueError) as e:
    raise SystemExit(f"whale_api: need {_SECRETS} with ACCESS_KEY, HMAC_KEY ... ({e})") from e

ACCESS_KEY = _S["ACCESS_KEY"]
HMAC_KEY = _S["HMAC_KEY"]
SAAS = "https://saas.zeasn.tv"
CAL = "https://whalephoto.zeasn.tv"
ACCOUNT_EMAIL = _S["ACCOUNT_EMAIL"]
ACCOUNT_CREDENTIAL = _S["ACCOUNT_CREDENTIAL"]
WALL_MAC = _S["WALL_MAC"]

BASIC = {
    "countryCode": "au",
    "langCode": "en",
    "osType": "Android",
    "androidVersion": "11",
    "appVersion": "1",
}


def ts_ms():
    return str(int(time.time() * 1000))


def sign(path, t=None):
    t = t or ts_ms()
    digest = hmac.new(HMAC_KEY.encode(), (path + t).encode(), hashlib.sha1).digest()
    sig = base64.b64encode(digest).decode().strip()
    return f"{ACCESS_KEY}:{sig}:{t}"


def ua(mac=WALL_MAC):
    m = mac.replace(":", "")
    client = m[:6] + "fffe" + m[6:] if len(m) > 6 else m
    return f"DPClient/1.1(Client:{client})"


def headers(path, extra=None):
    h = dict(BASIC)
    h["Authorization"] = sign(path)
    h["User-Agent"] = ua()
    if extra:
        h.update(extra)
    return h


def req(url, data=None, hdrs=None, form=False):
    h = {"User-Agent": ua()}
    if hdrs:
        h.update(hdrs)
    if form:
        body = urllib.parse.urlencode(data or {}).encode()
        h = dict(h)
        h["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        body = json.dumps(data).encode() if data is not None else None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"only https URLs are allowed, got: {parsed.scheme}")
    conn = http.client.HTTPSConnection(parsed.netloc, timeout=15)
    pathq = parsed.path + (("?" + parsed.query) if parsed.query else "")
    try:
        conn.request("POST" if body is not None else "GET", pathq, body, h)
        resp = conn.getresponse()
        return resp.status, resp.read().decode()
    finally:
        conn.close()


def device_sign(mac=WALL_MAC, sn=_S["WALL_SN"]):
    path = "/auth-api/api/v1/auth/deviceSign"
    form = {
        "productId": "888",
        "brandId": "7",
        "deviceSetId": "ec61ecc7ba7e11ee8b5b0adbcf44c73b",
        "mac": mac,
        "deviceType": "Zeasn_Android_Calendar",
        "functionType": "1",
        "ifGetTvDetail": "1",
        "iconResolution": "",
        "terminalType": "Calendar",
        "sn": sn,
        "osVersion": "11",
        "productType": "",
    }
    return req(SAAS + path, form, headers(path), form=True)


def login(email=ACCOUNT_EMAIL, credential=ACCOUNT_CREDENTIAL):
    path = "/user/device/login"
    form = {
        "productId": "888",
        "brandId": "7",
        "deviceSetId": "ec61ecc7ba7e11ee8b5b0adbcf44c73b",
        "mac": WALL_MAC,
        "deviceType": "Zeasn_Android_Calendar",
        "deviceName": "Calendar",
        "email": email,
        "pwd": credential,
        "appId": "",
    }
    st, b = req(SAAS + path, form, headers(path, {"user_auth": "1"}), form=True)
    try:
        return json.loads(b)
    except Exception:
        return {"http": st, "raw": b}


def get_token():
    d = login()
    return d.get("data", {}).get("userToken")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "token":
        st, b = device_sign()
        print(st)
        print(b[:2000])
    elif cmd == "login":
        print(json.dumps(login(), indent=1)[:2000])
    else:
        print(__doc__)

# pyright: reportMissingImports=false
# (homeassistant/aiohttp exist only in the HA runtime, not this repo)
"""Family kiosk backend: local calendar, Google feed cache, chore money chart.

Everything the wall calendar shows lives in Home Assistant, so the wall makes
no internet calls and keeps working when the internet is down:

- Events: a local store (imported Framely events + events made on the wall)
  plus a cached copy of the Google Calendar feed (Apps Script JSON, polled
  every 30 s by HA, the last good copy is kept and served when offline).
- Chores: per-kid chores with a cents value, one tick per chore per day,
  weekly totals booked into a running balance until a parent taps Paid.

Setup: add `family_kiosk:` to configuration.yaml (no options). Data is kept
in .storage/family_kiosk (HA's own storage helper, written atomically).

HTTP (HA auth unless noted):
  GET  /api/family_kiosk/state?since=<rev>   kiosk view; long-polls up to 25 s
                                             for a newer rev (instant updates)
  POST /api/family_kiosk/op                  {op:...} see logic.apply
  GET  /api/family_kiosk/ics?token=...       subscribable ICS (token or HA auth)
  GET  /api/family_kiosk/ics_url             full subscribe URL
"""

from __future__ import annotations

import asyncio
import copy
import datetime as dt
import logging
import secrets

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import logic

DOMAIN = "family_kiosk"
_LOGGER = logging.getLogger(__name__)
GOOGLE_EVERY = dt.timedelta(seconds=30)
LONG_POLL_S = 25


class Hub:
    """In-memory state + persistence + change notification."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.store = Store(hass, 1, DOMAIN)
        self.data = logic.empty()
        self.changed = asyncio.Condition()
        self.lock = asyncio.Lock()

    async def load(self):
        stored = await self.store.async_load()
        if stored:
            base = logic.empty()
            base.update(stored)
            base["google"] = {**logic.empty()["google"], **stored.get("google", {})}
            base["settings"] = {**logic.empty()["settings"], **stored.get("settings", {})}
            self.data = base
        if not self.data.get("ics_token"):
            self.data["ics_token"] = secrets.token_urlsafe(24)
            await self.store.async_save(self.data)

    async def commit(self, new: dict):
        self.data = new
        await self.store.async_save(new)
        async with self.changed:
            self.changed.notify_all()

    async def op(self, op: dict) -> dict:
        async with self.lock:
            new = logic.apply(self.data, op, dt_util.now())
            await self.commit(new)
        return new

    async def tick(self, _now=None):
        """Every 30 s: week rollover + Google refresh."""
        async with self.lock:
            d = copy.deepcopy(self.data)
            if logic.rollover(d, dt_util.now()):
                d["rev"] = self.data["rev"] + 1
                await self.commit(d)
        await self.refresh_google()

    async def refresh_google(self):
        g = self.data["google"]
        if not g.get("url"):
            return
        err, events = None, None
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(g["url"], timeout=20) as resp:
                body = await resp.json(content_type=None)
            if not isinstance(body, dict) or not isinstance(body.get("events"), list):
                err = str(body.get("error") if isinstance(body, dict) else "bad feed")[:200]
            else:
                events = [{"id": str(e.get("id")), "title": str(e.get("title", "")), "start": str(e.get("start")),
                           "end": str(e.get("end")), "allday": bool(e.get("allDay")),
                           "location": str(e.get("location") or "")} for e in body["events"]]
        except Exception as ex:  # noqa: BLE001 network/parse failures keep the cached copy
            err = f"{type(ex).__name__}: {ex}"[:200]
        async with self.lock:
            old = self.data["google"]
            new_g = {**old, "error": err}
            if events is not None:
                new_g.update(events=events, ok_at=dt_util.now().isoformat(timespec="seconds"), error=None)
            if new_g != old:
                d = {**self.data, "google": new_g}
                if events != old.get("events") or (err is None) != (old.get("error") is None):
                    d["rev"] = self.data["rev"] + 1
                await self.commit(d)


def _ok_token(hass, hub: Hub, request) -> bool:
    tok = request.query.get("token", "") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not tok:
        return False
    if secrets.compare_digest(tok, hub.data.get("ics_token", "")):
        return True
    return hass.auth.async_validate_access_token(tok) is not None


class StateView(HomeAssistantView):
    url = "/api/family_kiosk/state"
    name = "api:family_kiosk:state"

    async def get(self, request):
        hub: Hub = request.app[KEY_HASS].data[DOMAIN]
        since = request.query.get("since")
        if since is not None and since.isdigit() and int(since) >= hub.data["rev"]:
            try:
                async with hub.changed:
                    await asyncio.wait_for(hub.changed.wait_for(lambda: hub.data["rev"] > int(since)), LONG_POLL_S)
            except TimeoutError:
                pass
        return self.json(logic.kiosk_view(hub.data, dt_util.now()), headers={"Cache-Control": "no-store"})


class OpView(HomeAssistantView):
    url = "/api/family_kiosk/op"
    name = "api:family_kiosk:op"

    async def post(self, request):
        hub: Hub = request.app[KEY_HASS].data[DOMAIN]
        try:
            op = await request.json()
            await hub.op(op)
        except logic.OpError as err:
            return self.json_message(str(err), status_code=400)
        except ValueError:
            return self.json_message("bad JSON", status_code=400)
        if op.get("op") == "google_url":
            hub.hass.async_create_task(hub.refresh_google())
        return self.json(logic.kiosk_view(hub.data, dt_util.now()))


class IcsView(HomeAssistantView):
    url = "/api/family_kiosk/ics"
    name = "api:family_kiosk:ics"
    requires_auth = False

    async def get(self, request):
        hass = request.app[KEY_HASS]
        hub: Hub = hass.data[DOMAIN]
        if not _ok_token(hass, hub, request):
            return self.json_message("invalid token", status_code=403)
        which = request.query.get("events", "local")  # local | all
        events = list(hub.data["events"])
        if which == "all":
            events += [{**e, "id": "g-" + e["id"]} for e in hub.data["google"].get("events", [])]
        return web.Response(text=logic.to_ics(events, dt_util.now()), content_type="text/calendar",
                            charset="utf-8", headers={"Cache-Control": "max-age=300"})


class IcsUrlView(HomeAssistantView):
    url = "/api/family_kiosk/ics_url"
    name = "api:family_kiosk:ics_url"

    async def get(self, request):
        hub: Hub = request.app[KEY_HASS].data[DOMAIN]
        return self.json({"url": f"{request.url.origin()}/api/family_kiosk/ics?token={hub.data['ics_token']}"})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hub = Hub(hass)
    await hub.load()
    hass.data[DOMAIN] = hub
    for view in (StateView, OpView, IcsView, IcsUrlView):
        hass.http.register_view(view())
    async_track_time_interval(hass, hub.tick, GOOGLE_EVERY)
    hass.async_create_task(hub.tick())
    return True

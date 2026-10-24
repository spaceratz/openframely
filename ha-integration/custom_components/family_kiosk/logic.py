"""Pure data logic for family_kiosk (no Home Assistant imports, unit tested).

Money is integer cents. Days are ISO dates (YYYY-MM-DD). Weeks start Monday.

Chore chart: each kid has chores [{id, name, cents}] and ticks
{chore_id: [dates]}. Kids can tick a chore once per day for the current week
up to today, matching the paper chart. When a week ends, rollover() books
the week's ticks into the kid's owed balance, logs the entry in history, and
clears those ticks. Booking is idempotent and catches up after downtime.
"""

from __future__ import annotations

import copy
import datetime as dt
import re
import uuid

KID_RE = re.compile(r"^[a-z][a-z0-9_]{0,30}$")
HISTORY_MAX = 500
RRULE_RE = re.compile(r"[A-Z]+=[A-Za-z0-9,+-]+(;[A-Z]+=[A-Za-z0-9,+-]+)*")


class OpError(ValueError):
    """Invalid operation from the kiosk (reported back as a 400)."""


def empty() -> dict:
    return {
        "version": 1,
        "rev": 0,
        "kids": {},
        "history": [],
        "events": [],
        "google": {"url": "", "events": [], "ok_at": None, "error": None},
        "settings": {"hide_imported_when_google": True},
    }


def monday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def _date(s: object) -> dt.date:
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError as err:
        raise OpError(f"bad date {s!r}") from err


def _cents(v) -> int:
    try:
        c = int(round(float(v)))
    except (TypeError, ValueError) as err:
        raise OpError("bad amount") from err
    if not -1_000_000 <= c <= 1_000_000:
        raise OpError("amount out of range")
    return c


def _kid(data: dict, key: object) -> dict:
    if not isinstance(key, str) or not KID_RE.match(key):
        raise OpError("bad kid")
    return data["kids"].setdefault(key, {"chores": [], "ticks": {}, "balance": 0})


def _chore(kid: dict, cid: object) -> dict:
    for c in kid["chores"]:
        if c["id"] == cid:
            return c
    raise OpError("unknown chore")


def _log(data: dict, now: dt.datetime, **entry) -> None:
    data["history"].append({"at": now.isoformat(timespec="seconds"), **entry})
    del data["history"][:-HISTORY_MAX]


def week_total(kid: dict, week: dt.date) -> int:
    end = week + dt.timedelta(days=7)
    cents = {c["id"]: c["cents"] for c in kid["chores"]}
    return sum(cents.get(cid, 0) for cid, days in kid["ticks"].items() for d in days if week <= _date(d) < end)


def rollover(data: dict, now: dt.datetime) -> bool:
    """Book every tick from before this week. Returns True if anything changed."""
    this_week = monday(now.date())
    changed = False
    for key, kid in data["kids"].items():
        cents = {c["id"]: (c["cents"], c["name"]) for c in kid["chores"]}
        weeks: dict[dt.date, int] = {}
        for cid in list(kid["ticks"]):
            keep = []
            for d in kid["ticks"][cid]:
                day = _date(d)
                if day < this_week:
                    weeks[monday(day)] = weeks.get(monday(day), 0) + cents.get(cid, (0, ""))[0]
                else:
                    keep.append(d)
            if len(keep) != len(kid["ticks"][cid]):
                changed = True
            if keep:
                kid["ticks"][cid] = keep
            else:
                del kid["ticks"][cid]
        for week, total in sorted(weeks.items()):
            kid["balance"] += total
            _log(data, now, kid=key, type="week", week=week.isoformat(), cents=total, balance=kid["balance"])
            changed = True
    return changed


def apply(data: dict, op: dict, now: dt.datetime) -> dict:
    """Apply one kiosk operation to a copy of data and return it (raises OpError)."""
    d = copy.deepcopy(data)
    kind = op.get("op")
    today = now.date()

    if kind == "chore_add":
        kid = _kid(d, op.get("kid"))
        name = str(op.get("name", "")).strip()[:60]
        if not name:
            raise OpError("chore needs a name")
        kid["chores"].append({"id": uuid.uuid4().hex[:10], "name": name, "cents": max(0, _cents(op.get("cents", 0)))})
    elif kind == "chore_edit":
        kid = _kid(d, op.get("kid"))
        c = _chore(kid, op.get("id"))
        if "name" in op:
            c["name"] = str(op["name"]).strip()[:60] or c["name"]
        if "cents" in op:
            c["cents"] = max(0, _cents(op["cents"]))
    elif kind == "chore_delete":
        kid = _kid(d, op.get("kid"))
        _chore(kid, op.get("id"))
        kid["chores"] = [c for c in kid["chores"] if c["id"] != op["id"]]
        kid["ticks"].pop(op["id"], None)
    elif kind == "chore_move":
        kid = _kid(d, op.get("kid"))
        c = _chore(kid, op.get("id"))
        i = kid["chores"].index(c)
        j = max(0, min(len(kid["chores"]) - 1, i + (1 if op.get("dir", 1) > 0 else -1)))
        kid["chores"][i], kid["chores"][j] = kid["chores"][j], kid["chores"][i]
    elif kind == "tick":
        kid = _kid(d, op.get("kid"))
        chore = _chore(kid, op.get("id"))
        day = _date(op.get("day"))
        if day > today or day < monday(today):
            raise OpError("only days this week up to today can be ticked")
        days = set(kid["ticks"].get(op["id"], []))
        want = op.get("on")
        want = (day.isoformat() not in days) if want is None else bool(want)
        if want:
            days.add(day.isoformat())
        else:
            days.discard(day.isoformat())
        if days:
            kid["ticks"][op["id"]] = sorted(days)
        else:
            kid["ticks"].pop(op["id"], None)
        _log(
            d,
            now,
            kid=op.get("kid"),
            type="tick",
            day=day.isoformat(),
            chore=chore["name"],
            cents=chore["cents"],
            on=want,
            week_total=week_total(kid, monday(today)),
        )
    elif kind == "pay":
        kid = _kid(d, op.get("kid"))
        cents = kid["balance"] if op.get("cents") is None else _cents(op["cents"])
        if cents == 0:
            raise OpError("nothing owed")
        kid["balance"] -= cents
        _log(d, now, kid=op["kid"], type="paid", cents=cents, balance=kid["balance"])
    elif kind == "adjust":
        kid = _kid(d, op.get("kid"))
        cents = _cents(op.get("cents"))
        kid["balance"] += cents
        _log(d, now, kid=op["kid"], type="adjust", cents=cents, balance=kid["balance"], note=str(op.get("note", ""))[:80])
    elif kind in ("event_create", "event_update"):
        title = str(op.get("title", "")).strip()[:200]
        start, end = str(op.get("start", "")), str(op.get("end", ""))
        allday = bool(op.get("allday"))
        if not title or not start or not end:
            raise OpError("event needs a title, start and end")
        rrule = str(op.get("rrule") or "").removeprefix("RRULE:")
        if rrule and not RRULE_RE.fullmatch(rrule):
            raise OpError("bad repeat rule")
        ev = {"title": title, "start": start, "end": end, "allday": allday, "rrule": rrule}
        if kind == "event_create":
            d["events"].append({"id": uuid.uuid4().hex[:12], "source": "wall", **ev})
        else:
            hit = next((e for e in d["events"] if e["id"] == op.get("id")), None)
            if hit is None:
                raise OpError("unknown event")
            hit.update(ev)
    elif kind == "event_delete":
        before = len(d["events"])
        d["events"] = [e for e in d["events"] if e["id"] != op.get("id")]
        if len(d["events"]) == before:
            raise OpError("unknown event")
    elif kind == "import_events":
        src = str(op.get("source", "import"))[:20]
        keep = [e for e in d["events"] if e.get("source") != src]
        for e in op.get("events", []):
            keep.append(
                {
                    "id": str(e.get("id") or uuid.uuid4().hex[:12]),
                    "source": src,
                    "title": str(e["title"])[:200],
                    "start": str(e["start"]),
                    "end": str(e["end"]),
                    "allday": bool(e.get("allday")),
                    "location": str(e.get("location") or "")[:200],
                    "rrule": _rrule(e.get("rrule")),
                }
            )
        d["events"] = keep
    elif kind == "google_url":
        url = str(op.get("url", "")).strip()
        if url and not url.startswith("https://"):
            raise OpError("feed URL must be https")
        d["google"] = {"url": url, "events": [], "ok_at": None, "error": None}
    elif kind == "setting":
        if op.get("key") not in d["settings"]:
            raise OpError("unknown setting")
        d["settings"][op["key"]] = op.get("value")
    else:
        raise OpError(f"unknown op {kind!r}")

    rollover(d, now)
    d["rev"] = data.get("rev", 0) + 1
    return d


def _rrule(value) -> str:
    r = str(value or "").removeprefix("RRULE:")
    return r if RRULE_RE.fullmatch(r) else ""


def _esc(text) -> str:
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> list:
    out, raw = [], line.encode()
    while len(raw) > 75:
        cut = 75
        while (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(raw[:cut].decode())
        raw = b" " + raw[cut:]
    out.append(raw.decode())
    return out


def _ics_time(value: str) -> str:
    t = dt.datetime.fromisoformat(value)
    if t.tzinfo is None:
        return t.strftime("%Y%m%dT%H%M%S")
    return t.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def to_ics(events: list, now: dt.datetime, name: str = "Family") -> str:
    """RFC 5545 calendar of local events (titles keep their people tags)."""
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//dp159k//family_kiosk//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc(name)}",
        "X-WR-TIMEZONE:Australia/Perth",
        "REFRESH-INTERVAL;VALUE=DURATION:PT5M",
        "X-PUBLISHED-TTL:PT5M",
    ]
    for e in events:
        lines += ["BEGIN:VEVENT", f"UID:{_esc(e['id'])}@family-kiosk", f"DTSTAMP:{stamp}"]
        if e.get("allday"):
            lines += [f"DTSTART;VALUE=DATE:{e['start'][:10].replace('-', '')}", f"DTEND;VALUE=DATE:{e['end'][:10].replace('-', '')}"]
        else:
            lines += [f"DTSTART:{_ics_time(e['start'])}", f"DTEND:{_ics_time(e['end'])}"]
        if e.get("rrule"):
            lines.append("RRULE:" + e["rrule"])
        lines.append(f"SUMMARY:{_esc(e['title'])}")
        if e.get("location"):
            lines.append(f"LOCATION:{_esc(e['location'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(f for line in lines for f in _fold(line)) + "\r\n"


def kiosk_view(data: dict, now: dt.datetime) -> dict:
    """Build the wall state payload without secrets (strips the Google feed URL)."""
    week = monday(now.date())
    kids = {}
    for key, kid in data["kids"].items():
        kids[key] = {"chores": kid["chores"], "ticks": kid["ticks"], "balance": kid["balance"], "week": week_total(kid, week)}
    g = data["google"]
    google_live = bool(g.get("url") and g.get("ok_at"))
    hide = google_live and data["settings"].get("hide_imported_when_google")
    events = [e for e in data["events"] if not (hide and e.get("source") not in ("wall",))]
    return {
        "rev": data.get("rev", 0),
        "week": week.isoformat(),
        "today": now.date().isoformat(),
        "kids": kids,
        "history": data["history"][-60:],
        "events": events,
        "google": {"configured": bool(g.get("url")), "ok_at": g.get("ok_at"), "error": g.get("error"), "events": g.get("events", [])},
        "settings": data["settings"],
    }

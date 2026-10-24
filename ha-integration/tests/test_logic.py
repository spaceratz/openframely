"""python3 -m pytest ha-integration/tests -q"""

import contextlib
import datetime as dt
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "logic", pathlib.Path(__file__).parent.parent / "custom_components/family_kiosk/logic.py")
assert _spec and _spec.loader
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)

@contextlib.contextmanager
def raises(exc):
    try:
        yield
    except exc:
        return
    raise AssertionError(f"{exc.__name__} not raised")


WED = dt.datetime(2026, 10, 14, 9, 0)  # a Wednesday; week starts Mon 12 Oct


def setup_kid():
    d = L.apply(L.empty(), {"op": "chore_add", "kid": "kid1", "name": "Make bed", "cents": 50}, WED)
    d = L.apply(d, {"op": "chore_add", "kid": "kid1", "name": "Feed cat", "cents": 100}, WED)
    bed, cat = (c["id"] for c in d["kids"]["kid1"]["chores"])
    return d, bed, cat


def test_tick_once_per_day_and_week_total():
    d, bed, cat = setup_kid()
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-12", "on": True}, WED)
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-12", "on": True}, WED)  # same day again
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-13"}, WED)               # toggle on
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": cat, "day": "2026-10-14"}, WED)
    assert d["kids"]["kid1"]["ticks"][bed] == ["2026-10-12", "2026-10-13"]
    assert L.kiosk_view(d, WED)["kids"]["kid1"]["week"] == 200
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-13"}, WED)               # toggle off
    assert L.kiosk_view(d, WED)["kids"]["kid1"]["week"] == 150


def test_cannot_tick_future_or_last_week():
    d, bed, _ = setup_kid()
    for day in ("2026-10-15", "2026-10-11"):
        with raises(L.OpError):
            L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": day}, WED)


def test_rollover_books_balance_and_carries_over_until_paid():
    d, bed, cat = setup_kid()
    for day in ("2026-10-12", "2026-10-13", "2026-10-14"):
        d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": day}, WED)
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": cat, "day": "2026-10-14"}, WED)
    next_mon = dt.datetime(2026, 10, 19, 0, 1)
    assert L.rollover(d, next_mon)
    k = d["kids"]["kid1"]
    assert k["balance"] == 250 and k["ticks"] == {}
    assert d["history"][-1] == {"at": "2026-10-19T00:01:00", "kid": "kid1", "type": "week",
                                "week": "2026-10-12", "cents": 250, "balance": 250}
    assert not L.rollover(d, next_mon)  # idempotent
    # second week adds to the unpaid balance
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": cat, "day": "2026-10-19"}, next_mon)
    L.rollover(d, dt.datetime(2026, 10, 26, 8))
    assert d["kids"]["kid1"]["balance"] == 350
    d = L.apply(d, {"op": "pay", "kid": "kid1"}, dt.datetime(2026, 10, 26, 9))
    assert d["kids"]["kid1"]["balance"] == 0 and d["history"][-1]["type"] == "paid"
    with raises(L.OpError):
        L.apply(d, {"op": "pay", "kid": "kid1"}, dt.datetime(2026, 10, 26, 9))


def test_rollover_catches_up_multiple_missed_weeks():
    d, bed, _ = setup_kid()
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-12"}, WED)
    L.rollover(d, dt.datetime(2026, 11, 9))
    assert d["kids"]["kid1"]["balance"] == 50
    assert [h["week"] for h in d["history"] if h["type"] == "week"] == ["2026-10-12"]


def test_edit_price_applies_to_unbooked_week_and_delete_drops_ticks():
    d, bed, cat = setup_kid()
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-14"}, WED)
    d = L.apply(d, {"op": "chore_edit", "kid": "kid1", "id": bed, "cents": 75}, WED)
    assert L.kiosk_view(d, WED)["kids"]["kid1"]["week"] == 75
    d = L.apply(d, {"op": "chore_delete", "kid": "kid1", "id": bed}, WED)
    assert bed not in d["kids"]["kid1"]["ticks"] and len(d["kids"]["kid1"]["chores"]) == 1


def test_adjust_and_validation():
    d, _, _ = setup_kid()
    d = L.apply(d, {"op": "adjust", "kid": "kid1", "cents": -20, "note": "lost a book"}, WED)
    assert d["kids"]["kid1"]["balance"] == -20
    for bad in ({"op": "chore_add", "kid": "Casey!", "name": "x"}, {"op": "chore_add", "kid": "kid1", "name": " "},
                {"op": "nope"}, {"op": "google_url", "url": "http://insecure"}):
        with raises(L.OpError):
            L.apply(d, bad, WED)


def test_rev_increments_and_input_not_mutated():
    d, bed, _ = setup_kid()
    before = d["rev"]
    d2 = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-14"}, WED)
    assert d2["rev"] == before + 1 and d["kids"]["kid1"]["ticks"] == {}


def test_events_and_imported_hidden_once_google_live():
    d = L.apply(L.empty(), {"op": "import_events", "source": "framely", "events": [
        {"id": "f1", "title": "Riley: Martial arts", "start": "2026-10-13T16:00:00+08:00",
         "end": "2026-10-13T17:00:00+08:00"}]}, WED)
    d = L.apply(d, {"op": "event_create", "title": "Casey: Dentist", "start": "2026-10-15T09:00:00+08:00",
                    "end": "2026-10-15T10:00:00+08:00"}, WED)
    assert len(L.kiosk_view(d, WED)["events"]) == 2
    d["google"].update(url="https://example/exec?key=k", ok_at="2026-10-14T09:00:00")
    view = L.kiosk_view(d, WED)
    assert [e["source"] for e in view["events"]] == ["wall"]   # framely copy hidden, Google has it now
    assert "url" not in view["google"]                           # feed key never sent to the wall
    wid = view["events"][0]["id"]
    d = L.apply(d, {"op": "event_delete", "id": wid}, WED)
    assert all(e["source"] != "wall" for e in d["events"])


def test_ics_export_is_valid_and_keeps_tags_and_repeats():
    import icalendar
    d = L.apply(L.empty(), {"op": "import_events", "source": "framely", "events": [
        {"id": "f1", "title": "Riley: Martial arts, bring belt", "start": "2026-10-13T16:00:00+08:00",
         "end": "2026-10-13T17:00:00+08:00", "rrule": "RRULE:FREQ=WEEKLY;INTERVAL=2;WKST=SU"},
        {"id": "f2", "title": "Family: Camping", "start": "2026-10-23", "end": "2026-10-26", "allday": True}]}, WED)
    cal = icalendar.Calendar.from_ical(L.to_ics(d["events"], WED.astimezone()))
    ev = list(cal.walk("VEVENT"))
    assert [str(e["SUMMARY"]) for e in ev] == ["Riley: Martial arts, bring belt", "Family: Camping"]
    assert ev[0]["RRULE"]["INTERVAL"] == [2]
    assert ev[0].decoded("DTSTART") == dt.datetime(2026, 10, 13, 8, 0, tzinfo=dt.timezone.utc)
    assert str(ev[1].decoded("DTSTART")) == "2026-10-23"


def test_bad_rrule_rejected():
    with raises(L.OpError):
        L.apply(L.empty(), {"op": "event_create", "title": "x", "start": "2026-10-14T09:00:00+08:00",
                            "end": "2026-10-14T10:00:00+08:00", "rrule": "FREQ=WEEKLY\nX:evil"}, WED)


def test_tick_logged_with_chore_and_week_total():
    d, bed, _ = setup_kid()
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-13"}, WED)
    h = d["history"][-1]
    assert h["type"] == "tick" and h["chore"] == "Make bed" and h["cents"] == 50
    assert h["on"] is True and h["day"] == "2026-10-13" and h["week_total"] == 50
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-13", "on": False}, WED)
    h2 = [x for x in d["history"] if x["type"] == "tick"][-1]
    assert h2["on"] is False and h2["week_total"] == 0


# ---- payouts (HA-side only) ----

def test_pay_defaults_to_full_balance_and_partial_pay_works():
    d, *_ = setup_kid()
    d = L.apply(d, {"op": "adjust", "kid": "kid1", "cents": 500, "note": "birthday"}, WED)
    d = L.apply(d, {"op": "pay", "kid": "kid1", "cents": 200}, WED)
    assert d["kids"]["kid1"]["balance"] == 300
    d = L.apply(d, {"op": "pay", "kid": "kid1"}, WED)
    assert d["kids"]["kid1"]["balance"] == 0
    assert [h["type"] for h in d["history"]] == ["adjust", "paid", "paid"]
    with raises(L.OpError):
        L.apply(d, {"op": "pay", "kid": "kid1"}, WED)  # nothing owed


def test_adjust_note_is_truncated_and_amount_bounded():
    d, *_ = setup_kid()
    d = L.apply(d, {"op": "adjust", "kid": "kid1", "cents": -50, "note": "x" * 500}, WED)
    assert len(d["history"][-1]["note"]) == 80
    with raises(L.OpError):
        L.apply(d, {"op": "adjust", "kid": "kid1", "cents": 10**9}, WED)


def test_bad_kid_keys_rejected():
    for key in ["", "Kid", "1kid", "a" * 40, None, "../x"]:
        with raises(L.OpError):
            L.apply(L.empty(), {"op": "chore_add", "kid": key, "name": "x", "cents": 1}, WED)


def test_history_is_capped():
    d, bed, _ = setup_kid()
    for i in range(L.HISTORY_MAX + 25):
        d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-14", "on": i % 2 == 0}, WED)
    assert len(d["history"]) == L.HISTORY_MAX


def test_unknown_op_and_unknown_chore():
    d, *_ = setup_kid()
    with raises(L.OpError):
        L.apply(d, {"op": "nope"}, WED)
    with raises(L.OpError):
        L.apply(d, {"op": "tick", "kid": "kid1", "id": "missing", "day": "2026-10-14"}, WED)


# ---- events ----

def test_event_update_and_delete_unknown_ids():
    d = L.apply(L.empty(), {"op": "event_create", "title": "Swim", "start": "2026-10-15", "end": "2026-10-16", "allday": True}, WED)
    eid = d["events"][0]["id"]
    d = L.apply(d, {"op": "event_update", "id": eid, "title": "Swimming", "start": "2026-10-15", "end": "2026-10-16", "allday": True}, WED)
    assert d["events"][0]["title"] == "Swimming" and d["events"][0]["source"] == "wall"
    for op in ({"op": "event_update", "id": "nope", "title": "x", "start": "a", "end": "b"}, {"op": "event_delete", "id": "nope"}):
        with raises(L.OpError):
            L.apply(d, op, WED)
    with raises(L.OpError):
        L.apply(d, {"op": "event_create", "title": "  ", "start": "2026-10-15", "end": "2026-10-16"}, WED)


def test_import_replaces_only_same_source_and_sanitises():
    d = L.apply(L.empty(), {"op": "event_create", "title": "Wall one", "start": "2026-10-15", "end": "2026-10-16", "allday": True}, WED)
    imp = {"op": "import_events", "source": "framely", "events": [
        {"title": "A" * 300, "start": "2026-10-20", "end": "2026-10-21", "allday": True, "rrule": "FREQ=WEEKLY\nX:evil"},
        {"id": "keep-id", "title": "B", "start": "2026-10-22T09:00", "end": "2026-10-22T10:00"},
    ]}
    d = L.apply(d, imp, WED)
    d = L.apply(d, imp, WED)  # re-import doesn't duplicate
    by_src = [e["source"] for e in d["events"]]
    assert by_src.count("framely") == 2 and by_src.count("wall") == 1
    a = next(e for e in d["events"] if e["title"].startswith("A"))
    assert len(a["title"]) == 200 and a["rrule"] == ""
    assert any(e["id"] == "keep-id" for e in d["events"])


# ---- google + settings ----

def test_google_url_must_be_https_and_reset_clears_cache():
    with raises(L.OpError):
        L.apply(L.empty(), {"op": "google_url", "url": "http://example.com/feed"}, WED)
    d = L.apply(L.empty(), {"op": "google_url", "url": "https://script.google.com/x?key=s"}, WED)
    assert d["google"]["url"].startswith("https://") and d["google"]["events"] == []
    v = L.kiosk_view(d, WED)
    assert "url" not in v["google"], "feed URL (contains its key) must never reach the wall"
    d = L.apply(d, {"op": "google_url", "url": ""}, WED)
    assert L.kiosk_view(d, WED)["google"]["configured"] is False


def test_settings_only_known_keys():
    d = L.apply(L.empty(), {"op": "setting", "key": "hide_imported_when_google", "value": False}, WED)
    assert d["settings"]["hide_imported_when_google"] is False
    with raises(L.OpError):
        L.apply(d, {"op": "setting", "key": "evil", "value": 1}, WED)


# ---- ICS ----

def test_ics_escapes_and_folds_long_utf8_lines():
    title = "Riley: Swimming, then 🍦; " + "é" * 60
    ev = {"id": "x1", "title": title, "start": "2026-10-15T09:00:00+08:00", "end": "2026-10-15T10:00:00+08:00", "location": "Pool; lane 3"}
    ics = L.to_ics([ev], WED.replace(tzinfo=dt.timezone.utc))
    lines = ics.split("\r\n")
    assert all(len(line.encode()) <= 75 for line in lines)
    assert "DTSTART:20261015T010000Z" in lines
    unfolded = ics.replace("\r\n ", "")
    assert "Swimming\\, then 🍦\\; " in unfolded and "LOCATION:Pool\\; lane 3" in unfolded
    assert ics.endswith("END:VCALENDAR\r\n")


def test_kiosk_view_week_and_today():
    d, bed, _ = setup_kid()
    d = L.apply(d, {"op": "tick", "kid": "kid1", "id": bed, "day": "2026-10-14"}, WED)
    v = L.kiosk_view(d, WED)
    assert v["week"] == "2026-10-12" and v["today"] == "2026-10-14"
    assert v["kids"]["kid1"]["week"] == 50 and v["kids"]["kid1"]["balance"] == 0

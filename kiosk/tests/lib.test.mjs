// bun test tests/   (or: bun run test, which pins TZ=Australia/Perth)
// Runs with TZ=Australia/Perth (set in package.json) so local-date maths is deterministic.
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const L = createRequire(import.meta.url)("../web/lib.js");

describe("barGradient", () => {
  test("one person stays a solid colour", () => assert.equal(L.barGradient(["#e8344a"]), "#e8344a"));
  test("nobody gives nothing", () => assert.equal(L.barGradient([]), ""));
  test("two people blend top to bottom", () =>
    assert.equal(L.barGradient(["#e8344a", "#7c5cff"]), "linear-gradient(180deg, #e8344a 0%, #7c5cff 100%)"));
  test("three people get even stops", () =>
    assert.equal(L.barGradient(["#a", "#b", "#c"]), "linear-gradient(180deg, #a 0%, #b 50%, #c 100%)"));
  test("missing colours are skipped", () => assert.equal(L.barGradient([undefined, "#e8344a"]), "#e8344a"));
});
const d = s => new Date(s);

describe("dates", () => {
  test("ymd pads and uses local time", () => {
    assert.equal(L.ymd(d("2026-01-05T09:00")), "2026-01-05");
    assert.equal(L.ymd(d("2026-12-31T23:59")), "2026-12-31");
  });
  test("addDays crosses month and year boundaries", () => {
    assert.equal(L.ymd(L.addDays(d("2026-10-30T12:00"), 3)), "2026-11-02");
    assert.equal(L.ymd(L.addDays(d("2027-01-01T12:00"), -1)), "2026-12-31");
  });
  test("mondayOf: weeks start Monday, Sunday belongs to the week before", () => {
    assert.equal(L.ymd(L.mondayOf(d("2026-10-14T15:00"))), "2026-10-12"); // Wed
    assert.equal(L.ymd(L.mondayOf(d("2026-10-12T00:00"))), "2026-10-12"); // Mon
    assert.equal(L.ymd(L.mondayOf(d("2026-10-18T23:00"))), "2026-10-12"); // Sun
    assert.equal(L.mondayOf(d("2026-10-14T15:00")).getHours(), 0);
  });
  test("weekTitle: same month vs spanning months", () => {
    assert.equal(L.weekTitle(d("2026-10-12T00:00")), "12 to 18 October 2026");
    assert.equal(L.weekTitle(d("2026-10-26T00:00")), "26 Oct to 1 Nov 2026");
  });
});

describe("money", () => {
  test("whole dollars drop the cents", () => assert.equal(L.money(300), "$3"));
  test("cents keep two places", () => assert.equal(L.money(150), "$1.50"));
  test("negative", () => assert.equal(L.money(-50), "-$0.50"));
  test("zero", () => assert.equal(L.money(0), "$0"));
});

describe("evDays", () => {
  test("timed event shows on its start day only", () => {
    assert.deepEqual(L.evDays({allday: false, start: "2026-10-14T23:30:00+08:00", end: "2026-10-15T01:00:00+08:00"}), ["2026-10-14"]);
  });
  test("all-day end date is exclusive", () => {
    assert.deepEqual(L.evDays({allday: true, start: "2026-10-24", end: "2026-10-27"}), ["2026-10-24", "2026-10-25", "2026-10-26"]);
  });
  test("all-day with no end is one day", () => {
    assert.deepEqual(L.evDays({allday: true, start: "2026-10-24"}), ["2026-10-24"]);
  });
  test("runaway all-day ranges are capped at 60 days", () => {
    assert.equal(L.evDays({allday: true, start: "2026-01-01", end: "2027-01-01"}).length, 60);
  });
});

describe("expandRepeats", () => {
  const now = d("2026-10-14T09:00");
  const weekly = {uid: "a", allday: false, start: "2026-10-05T08:00:00.000Z", end: "2026-10-05T09:00:00.000Z"};
  test("non-repeating events pass through untouched", () => {
    const ev = {uid: "x", rrule: "", start: "2026-10-01", end: "2026-10-02", allday: true};
    assert.deepEqual(L.expandRepeats([ev], now), [ev]);
  });
  test("weekly COUNT gives that many occurrences, 7 days apart, same duration", () => {
    const out = L.expandRepeats([{...weekly, rrule: "FREQ=WEEKLY;COUNT=3"}], now);
    assert.equal(out.length, 3);
    assert.deepEqual(out.map(e => e.uid), ["a", "a#1", "a#2"]);
    assert.equal(new Date(out[1].start) - new Date(out[0].start), 7 * 864e5);
    assert.equal(new Date(out[2].end) - new Date(out[2].start), 36e5);
    assert.ok(out.every(e => e.seriesUid === "a"));
  });
  test("INTERVAL=2 skips alternate weeks", () => {
    const out = L.expandRepeats([{...weekly, rrule: "FREQ=WEEKLY;INTERVAL=2;COUNT=2"}], now);
    assert.equal(new Date(out[1].start) - new Date(out[0].start), 14 * 864e5);
  });
  test("UNTIL is inclusive of that day", () => {
    const out = L.expandRepeats([{...weekly, rrule: "FREQ=DAILY;UNTIL=20261007"}], now);
    assert.equal(out.length, 3); // 5th, 6th, 7th
  });
  test("open-ended repeats stop at the horizon", () => {
    const out = L.expandRepeats([{...weekly, rrule: "FREQ=DAILY"}], now, 10);
    assert.ok(out.length > 10 && out.length < 25);
  });
  test("all-day repeats keep date-only strings", () => {
    const out = L.expandRepeats([{uid: "b", allday: true, start: "2026-10-12", end: "2026-10-13", rrule: "FREQ=WEEKLY;COUNT=2"}], now);
    assert.deepEqual(out.map(e => [e.start, e.end]), [["2026-10-12", "2026-10-13"], ["2026-10-19", "2026-10-20"]]);
  });
  test("unsupported FREQ is kept as a single event", () => {
    assert.equal(L.expandRepeats([{...weekly, rrule: "FREQ=MONTHLY"}], now).length, 1);
  });
  test("INTERVAL=0 can't loop forever", () => {
    assert.equal(L.expandRepeats([{...weekly, rrule: "FREQ=DAILY;INTERVAL=0;COUNT=3"}], now).length, 3);
  });
});

describe("garageView", () => {
  const t0 = 1_000_000;
  test("plain states", () => {
    assert.deepEqual(L.garageView("closed", null, t0), {open: false, moving: null, label: "Closed", pending: null});
    assert.equal(L.garageView("open", null, t0).open, true);
  });
  test("HA reporting opening/closing wins", () => {
    assert.equal(L.garageView("opening", null, t0).label, "Opening...");
    assert.equal(L.garageView("closing", null, t0).open, false);
  });
  test("tap shows Opening... before HA catches up", () => {
    const v = L.garageView("closed", {target: "open", at: t0}, t0 + 2000);
    assert.equal(v.label, "Opening...");
    assert.equal(v.open, true);
    assert.ok(v.pending);
  });
  test("pending clears once HA reaches the target", () => {
    const v = L.garageView("open", {target: "open", at: t0}, t0 + 15000);
    assert.equal(v.label, "Open");
    assert.equal(v.pending, null);
  });
  test("pending gives up after 90 seconds", () => {
    const v = L.garageView("closed", {target: "open", at: t0}, t0 + 91000);
    assert.equal(v.label, "Closed");
    assert.equal(v.pending, null);
  });
  test("missing state reads Unknown", () => assert.equal(L.garageView(undefined, null, t0).label, "Unknown"));
});

describe("tileName", () => {
  test("drops a trailing Light/Lights", () => {
    assert.equal(L.tileName("Kitchen Bench Light", "light.x"), "Kitchen Bench");
    assert.equal(L.tileName("Deck Lights", "light.x"), "Deck");
  });
  test("falls back to a tidy entity id", () => assert.equal(L.tileName(undefined, "light.front_porch"), "Front Porch"));
  test("leaves other names alone", () => assert.equal(L.tileName("Lightning Bolt", "light.x"), "Lightning Bolt"));
});

describe("todayProgress", () => {
  test("counts chores ticked today", () => {
    const kid = {chores: [{id: "a"}, {id: "b"}, {id: "c"}], ticks: {a: ["2026-10-14"], b: ["2026-10-13"]}};
    assert.deepEqual(L.todayProgress(kid, "2026-10-14"), {done: 1, total: 3});
  });
  test("no chores", () => assert.deepEqual(L.todayProgress({chores: [], ticks: {}}, "2026-10-14"), {done: 0, total: 0}));
});

describe("12/24 hour time", () => {
  const t = s => new Date(`2026-10-14T${s}`);
  test("12h drops :00 and adds am/pm", () => {
    assert.equal(L.fmtTime(t("15:00")), "3pm");
    assert.equal(L.fmtTime(t("15:45")), "3:45pm");
    assert.equal(L.fmtTime(t("09:05")), "9:05am");
  });
  test("12h midnight and noon", () => {
    assert.equal(L.fmtTime(t("00:00")), "12am");
    assert.equal(L.fmtTime(t("12:30")), "12:30pm");
  });
  test("24h is zero-padded and always shows minutes", () => {
    assert.equal(L.fmtTime(t("15:00"), true), "15:00");
    assert.equal(L.fmtTime(t("09:05"), true), "09:05");
    assert.equal(L.fmtTime(t("00:00"), true), "00:00");
  });
  test("clock parts", () => {
    assert.deepEqual(L.clockParts(t("15:07")), {hm: "3:07", ap: "pm"});
    assert.deepEqual(L.clockParts(t("00:07")), {hm: "12:07", ap: "am"});
    assert.deepEqual(L.clockParts(t("15:07"), true), {hm: "15:07", ap: ""});
    assert.deepEqual(L.clockParts(t("07:07"), true), {hm: "07:07", ap: ""});
  });
});

/* Pure helpers shared by the kiosk and tests/lib.test.mjs. No DOM, no globals.
   Dates are local; days are "YYYY-MM-DD"; weeks start Monday; money is cents. */
(function (root) {
  const pad = n => String(n).padStart(2, "0");
  const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const dateOf = s => new Date(s + "T00:00");
  const mondayOf = d => { const x = addDays(d, -((d.getDay() + 6) % 7)); x.setHours(0, 0, 0, 0); return x; };
  const money = c => (c < 0 ? "-$" : "$") + (Math.abs(c) / 100).toFixed(2).replace(/\.00$/, "");

  /* times: "3:45pm" / "3pm" in 12h, "15:45" / "15:00" in 24h */
  function fmtTime(d, h24 = false) {
    const h = d.getHours(), m = d.getMinutes();
    if (h24) return `${pad(h)}:${pad(m)}`;
    return `${h % 12 || 12}${m ? ":" + pad(m) : ""}${h < 12 ? "am" : "pm"}`;
  }
  /* big clock: {hm: "3:07", ap: "pm"} or {hm: "15:07", ap: ""} */
  function clockParts(d, h24 = false) {
    const h = d.getHours();
    return h24 ? {hm: `${pad(h)}:${pad(d.getMinutes())}`, ap: ""}
      : {hm: `${h % 12 || 12}:${pad(d.getMinutes())}`, ap: h < 12 ? "am" : "pm"};
  }

  /* expand DAILY/WEEKLY repeats (INTERVAL, COUNT, UNTIL) up to `horizon` days from `now` */
  function expandRepeats(list, now = new Date(), horizon = 400) {
    const out = [];
    const winEnd = addDays(now, horizon);
    for (const ev of list) {
      if (!ev.rrule) { out.push(ev); continue; }
      const r = Object.fromEntries(ev.rrule.split(";").map(p => p.split("=")));
      const step = {DAILY: 1, WEEKLY: 7}[r.FREQ];
      if (!step) { out.push(ev); continue; }
      const every = step * Math.max(1, Number(r.INTERVAL || 1));
      const count = r.COUNT ? Number(r.COUNT) : Infinity;
      const until = r.UNTIL ? new Date(r.UNTIL.replace(/^(\d{4})(\d\d)(\d\d).*/, "$1-$2-$3T23:59:59")) : winEnd;
      const s0 = new Date(ev.allday ? ev.start + "T00:00" : ev.start);
      const dur = new Date(ev.allday ? ev.end + "T00:00" : ev.end) - s0;
      for (let n = 0; n < count && n < 500; n++) {
        const s = addDays(s0, n * every);
        if (s > until || s > winEnd) break;
        const e = new Date(+s + dur);
        out.push({...ev, uid: ev.uid + (n ? "#" + n : ""), seriesUid: ev.uid,
          start: ev.allday ? ymd(s) : s.toISOString(), end: ev.allday ? ymd(e) : e.toISOString()});
      }
    }
    return out;
  }

  /* local days an event covers: all-day end is exclusive, timed events show on their start day */
  function evDays(ev) {
    if (!ev.allday) return [ymd(new Date(ev.start))];
    const out = [];
    let d = dateOf(ev.start.slice(0, 10));
    const end = ev.end ? dateOf(ev.end.slice(0, 10)) : addDays(d, 1);
    do { out.push(ymd(d)); d = addDays(d, 1); } while (d < end && out.length < 60);
    return out;
  }

  /* "12 to 18 October 2026", "26 Oct to 1 Nov 2026" */
  function weekTitle(monday) {
    const end = addDays(monday, 6), same = end.getMonth() === monday.getMonth();
    return monday.toLocaleDateString("en-AU", same ? {day: "numeric"} : {day: "numeric", month: "short"}) + " to " +
      end.toLocaleDateString("en-AU", {day: "numeric", month: same ? "long" : "short", year: "numeric"});
  }

  /* garage label/state: HA can jump closed -> open, so a local "pending" bridges the gap (90s max) */
  function garageView(state, pending, now = Date.now()) {
    const live = pending && state !== pending.target && now - pending.at <= 90000 ? pending : null;
    const moving = state === "opening" || state === "closing" ? state
      : live ? (live.target === "open" ? "opening" : "closing") : null;
    const open = moving ? moving === "opening" : state === "open";
    const label = moving ? (moving === "opening" ? "Opening..." : "Closing...")
      : state ? state.charAt(0).toUpperCase() + state.slice(1) : "Unknown";
    return {open, moving, label, pending: live};
  }

  /* tidy HA friendly names for small tiles: "Kitchen Bench Light" -> "Kitchen Bench" */
  const tileName = (friendly, entityId) =>
    (friendly || entityId.split(".")[1].replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()))
      .replace(/\s+lights?$/i, "").trim();

  /* chores ticked today / total, for the kid tabs */
  /* The left bar of an event shared by several people: a top-to-bottom gradient through each
     person's colour, blending halfway between neighbours. One colour (or none) stays solid. */
  function barGradient(colours) {
    const cs = colours.filter(Boolean);
    if (cs.length < 2) return cs[0] || "";
    return `linear-gradient(180deg, ${cs.map((c, i) => `${c} ${Math.round((i / (cs.length - 1)) * 100)}%`).join(", ")})`;
  }

  function todayProgress(kid, today) {
    const done = kid.chores.filter(c => (kid.ticks[c.id] || []).includes(today)).length;
    return {done, total: kid.chores.length};
  }

  root.KioskLib = {pad, fmtTime, clockParts, ymd, addDays, dateOf, mondayOf, money, expandRepeats, evDays, weekTitle, garageView, tileName, todayProgress, barGradient};
  if (typeof module !== "undefined") module.exports = root.KioskLib;
})(typeof window !== "undefined" ? window : globalThis);

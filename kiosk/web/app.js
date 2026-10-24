/* Family Calendar kiosk.
   Data: HA only (works with no internet). family_kiosk long-poll state gives
   events (local + cached Google) and the chore money chart; the HA websocket
   gives lights, AC, weather and sun. The wall never calls the internet.
   Secrets arrive in the URL fragment from the APK (never sent to the server). */

const HASH = new URLSearchParams(location.hash.slice(1));
for (const k of ["token", "gcal"]) {
  if (HASH.has(k)) localStorage.setItem("kiosk_" + k, HASH.get(k)); // empty value clears it
  window.KIOSK_CONFIG[k] = localStorage.getItem("kiosk_" + k) || "";
}
if (location.hash) history.replaceState(null, "", location.pathname);
// APK re-sends settings as a fragment-only navigation (no page load): store and reload
addEventListener("hashchange", () => {
  const h = new URLSearchParams(location.hash.slice(1));
  for (const k of ["token", "gcal"]) if (h.has(k)) localStorage.setItem("kiosk_" + k, h.get(k));
  location.replace(location.pathname);
});

/* hot reload: deploy.sh bumps version.json, every open kiosk reloads within ~3s */
let BUILD = null;
setInterval(async () => {
  try {
    const v = (await (await fetch("version.json?_=" + Date.now(), {cache: "no-store"})).json()).v;
    if (BUILD === null) BUILD = v; else if (v !== BUILD) location.reload();
  } catch {}
}, 3000);

const CFG = window.KIOSK_CONFIG;
const MEMBERS = CFG.members;
const ALL_KEYS = MEMBERS.map(m => m.key);
const member = k => MEMBERS.find(m => m.key === k);
const HA = CFG.haUrl;
const $ = s => document.querySelector(s);
const {pad, clockParts, ymd, addDays, dateOf, mondayOf, money, expandRepeats, evDays, weekTitle, garageView, tileName, todayProgress} = KioskLib;
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
let h24 = localStorage.getItem("kiosk_h24") === "1";
const fmtTime = d => KioskLib.fmtTime(d, h24);
hydrateIcons();

/* member colour -> tint variables (WebView 109 has no color-mix) */
const hexRgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const tints = new Map();
function tint(node, hex) {
  if (!tints.has(hex)) {
    const [r, g, b] = hexRgb(hex.length === 4 ? "#" + [...hex.slice(1)].map(c => c + c).join("") : hex);
    const mix = (k, w) => Math.round(k + (255 - k) * w);
    tints.set(hex, `--mc:${hex};--mc-t1:rgba(${r},${g},${b},.16);--mc-t2:rgba(${r},${g},${b},.24);` +
      `--mc-l:rgb(${mix(r, .55)},${mix(g, .55)},${mix(b, .55)})`);
  }
  node.style.cssText += ";" + tints.get(hex);
}

function avatar(m) {
  const a = el("span", "avatar", m.name[0]);
  tint(a, m.color);
  return a;
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 2600);
}

/* ---------- connection status: banner after 20s without HA ---------- */
const link = {ws: false, poll: false, since: Date.now()};
function setLink(kind, ok) {
  const was = link.ws && link.poll;
  link[kind] = ok;
  const up = link.ws && link.poll;
  if (up !== was) link.since = Date.now();
  document.body.classList.toggle("offline", !up);
}
setInterval(() => {
  const down = !(link.ws && link.poll) && Date.now() - link.since > 20000;
  $("#offline-banner").hidden = !down;
}, 2000);

/* ---------- HA websocket ---------- */
let ws = null, msgId = 0, connecting = false;
const pending = new Map();
let booted = false; // HA traffic waits for boot (bottom of file), so every handler's state exists
setInterval(() => {
  if (!booted) return;
  if (ws && ws.readyState === 1) { try { ws.send(JSON.stringify({id: ++msgId, type: "ping"})); } catch {} }
  else if (!connecting) haConnect();
}, 10000);

function haConnect() {
  if (connecting) return;
  connecting = true;
  const sock = new WebSocket(HA.replace("http", "ws") + "/api/websocket");
  sock.onopen = () => sock.send(JSON.stringify({type: "auth", access_token: CFG.token}));
  sock.onmessage = e => {
    let m;
    try { m = JSON.parse(e.data); } catch { return; }
    if (m.type === "auth_ok") {
      setLink("ws", true);
      subscribed = false;
      refreshStates(); subscribeStates(); refreshForecast();
    } else if (m.type === "event" && m.event) onStateDelta(m.event);
    else if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  sock.onclose = () => {
    connecting = false;
    setLink("ws", false);
    if (ws === sock) setTimeout(haConnect, 3000);
  };
  sock.onerror = () => sock.close();
  ws = sock;
}
function haCall(type, data) {
  return new Promise((res, rej) => {
    const send = () => {
      const id = ++msgId;
      pending.set(id, res);
      try { ws.send(JSON.stringify({id, type, ...data})); } catch (e) { pending.delete(id); rej(e); }
    };
    if (ws && ws.readyState === 1) return send();
    const wait = setInterval(() => { if (ws && ws.readyState === 1) { clearInterval(wait); send(); } }, 200);
    setTimeout(() => { clearInterval(wait); rej(new Error("HA websocket not ready")); }, 15000);
  });
}
async function haService(domain, service, data, returnResponse = false) {
  const {entity_id, ...fields} = data || {};
  const payload = {domain, service, service_data: fields};
  if (entity_id) payload.target = {entity_id};
  if (returnResponse) payload.return_response = true;
  const r = await haCall("call_service", payload);
  if (!r.success) throw new Error((r.error && r.error.message) || "service failed");
  return returnResponse ? r.result.response : r.result;
}

/* ---------- family_kiosk state (events + chores), long-poll for instant updates ---------- */
let events = [], kstate = null;
const memberFilter = new Set(ALL_KEYS);

async function kfetch(path, opts = {}) {
  const r = await fetch(HA + "/api/family_kiosk/" + path, {
    ...opts, cache: "no-store",
    headers: {Authorization: `Bearer ${CFG.token}`, "Content-Type": "application/json", ...(opts.headers || {})},
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.message || `HTTP ${r.status}`);
  return body;
}
async function kop(op) {
  const st = await kfetch("op", {method: "POST", body: JSON.stringify(op)});
  applyKstate(st);
  return st;
}
function toEvent(e, source) {
  const t = parseTags(e.title, ALL_KEYS);
  return {uid: e.id, summary: t.title, rawTitle: e.title, source, location: e.location || "",
          start: e.start, end: e.end, allday: !!e.allday, rrule: e.rrule || "", members: t.members};
}
/* We redraw the active screen and mark hidden screens stale to redraw when opened.
   A full redraw takes ~0.3s on the wall's CPU, and taps queue behind it. */
const stale = new Set();
const RENDER = {calendar: () => renderCalendar(), day: () => renderDay(), chores: () => renderChores(), controls: () => renderControls()};
function refresh(...views) {
  for (const v of views) (v === currentView ? RENDER[v]() : stale.add(v));
}
function applyKstate(st) {
  if (!st || (kstate && st.rev <= kstate.rev)) return; // the op reply and the long-poll both deliver each rev
  const eventsChanged = !kstate || st.events !== kstate.events &&
    (JSON.stringify(st.events) !== JSON.stringify(kstate.events) || JSON.stringify(st.google.events) !== JSON.stringify(kstate.google.events));
  kstate = st;
  if (eventsChanged) {
    const local = st.events.map(e => toEvent(e, e.source === "wall" ? "wall" : "imported"));
    const google = (st.google.events || []).map(e => toEvent(e, "google"));
    events = expandRepeats([...local, ...google]).sort((a, b) => (b.allday - a.allday) || a.start.localeCompare(b.start));
    renderUpNext();
    refresh("calendar", "day");
  }
  refresh("chores");
}
let pollRunning = false;
async function pollState() {
  if (pollRunning) return;
  pollRunning = true;
  for (;;) {
    try {
      const st = await kfetch("state" + (kstate ? "?since=" + kstate.rev : ""));
      setLink("poll", true);
      applyKstate(st);
    } catch {
      setLink("poll", false);
      await new Promise(r => setTimeout(r, 5000));
    }
  }
}

const visible = ev => ev.members.some(k => memberFilter.has(k));
function eventsOn(dstr) {
  return events.filter(ev => visible(ev) && evDays(ev).includes(dstr));
}
/* bar colour(s) for an event: every shown person, unless it's the whole family (neutral) */
function barColours(ev) {
  const shown = ev.members.filter(k => memberFilter.has(k));
  if (shown.length < 2 || shown.length === ALL_KEYS.length) return [memberColour(ev)];
  return shown.map(k => (member(k) || {}).color);
}
function setBar(node, ev) {
  const g = KioskLib.barGradient(barColours(ev));
  if (g.startsWith("linear")) { node.style.setProperty("--bar", g); node.classList.add("multi"); }
}

function memberColour(ev) {
  const shown = ev.members.filter(k => memberFilter.has(k));
  return shown.length === ALL_KEYS.length && ALL_KEYS.length > 1 ? "#c8cfdb" : (member(shown[0] || ev.members[0]) || {}).color || "#888";
}

/* ---------- clock, weather, night ---------- */
function tickClock() {
  const now = new Date();
  const h = now.getHours();
  const c = clockParts(now, h24);
  $("#clock-hm").textContent = c.hm;
  $("#clock-ap").textContent = c.ap;
  $("#date").textContent = now.toLocaleDateString("en-AU", {weekday: "long", day: "numeric", month: "long"});
  if (now.getSeconds() === 0) {
    applyNight();
    renderUpNext();
    if (ymd(now) !== lastDay) { lastDay = ymd(now); refresh("calendar", "day", "chores"); renderUpNext(); refreshForecast(); }
    // nightly fresh start: frees WebView memory after days of uptime
    if (h === 3 && now.getMinutes() === 7 && Date.now() - lastTouch > 600000 && !document.querySelector("dialog[open]")) location.reload();
  }
}
let lastDay = ymd(new Date());

let weatherState = null, forecast = [];
function renderWeather() {
  if (!weatherState) return;
  const a = weatherState.a || {};
  $("#wx-icon").replaceChildren(wxIcon(weatherState.s));
  $("#wx-temp").textContent = `${Math.round(a.temperature ?? 0)}\u00b0`;
  $("#wx-cond").textContent = String(weatherState.s || "").replace(/-/g, " ").replace("partlycloudy", "partly cloudy");
  const today = forecast[0];
  const hilo = $("#wx-hilo");
  hilo.replaceChildren();
  if (today) {
    const hi = el("div"); hi.append("High ", el("b", "", `${Math.round(today.temperature)}\u00b0`));
    const lo = el("div"); lo.append("Low ", el("b", "", `${Math.round(today.templow)}\u00b0`));
    hilo.append(hi, lo);
  }
  const days = $("#wx-days");
  days.replaceChildren();
  for (const f of forecast.slice(1, 6)) {
    const d = el("div", "wxd");
    d.append(el("span", "d", new Date(f.datetime).toLocaleDateString("en-AU", {weekday: "short"})),
      wxIcon(f.condition), el("span", "hi", `${Math.round(f.temperature)}\u00b0`),
      el("span", "lo", `${Math.round(f.templow)}\u00b0`),
      el("span", "rain", f.precipitation_probability > 20 ? `${f.precipitation_probability}%` : (f.precipitation >= 1 ? `${Math.round(f.precipitation)}mm` : "")));
    days.appendChild(d);
  }
}
async function refreshForecast() {
  try {
    const r = await haService("weather", "get_forecasts", {entity_id: CFG.weather, type: "daily"}, true);
    forecast = (r[CFG.weather] || {}).forecast || [];
    renderWeather();
  } catch {}
}
setInterval(refreshForecast, 30 * 60000);

/* night mode: dim after sunset, dimmer late at night; a tap wakes it for 2 minutes */
let sunState = null, wakeUntil = 0;
function applyNight() {
  const h = new Date().getHours();
  const down = sunState ? sunState.s === "below_horizon" : (h >= 19 || h < 6);
  const late = h >= CFG.nightFrom || h < CFG.nightTo;
  const dim = (down || late) && Date.now() > wakeUntil;
  document.body.classList.toggle("dim", dim);
  document.body.style.setProperty("--dim-level", late ? ".68" : ".38");
}
document.addEventListener("pointerdown", () => {
  if (document.body.classList.contains("dim")) { wakeUntil = Date.now() + 120000; applyNight(); }
}, true);
setInterval(applyNight, 15000);

/* ---------- views ---------- */
let currentView = "calendar";
function switchView(name) {
  currentView = name;
  if (stale.delete(name)) RENDER[name]();
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  const navName = name === "day" ? "calendar" : name;
  $("#rail-settings").classList.toggle("on", name === "settings");
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("active", b.dataset.view === navName));
}
// switch on touch-down rather than on release: saves the ~100ms a finger takes to lift.
// The click that follows on release finds nothing to do (same view, same month).
function navTo(b) {
  if (b.dataset.view === "calendar") {
    const m = new Date(); m.setDate(1);
    const moved = ymd(m) !== ymd(monthCursor) || ymd(mondayOf(new Date())) !== ymd(weekCursor) || ymd(agendaFrom) !== ymd(new Date());
    monthCursor = m; weekCursor = mondayOf(new Date()); agendaFrom = new Date();
    if (moved) refresh("calendar");
  }
  if (currentView !== b.dataset.view) switchView(b.dataset.view);
}
document.querySelectorAll("#nav button").forEach(b => {
  b.addEventListener("pointerdown", () => navTo(b), {passive: true});
  b.onclick = () => navTo(b); // keyboard / tests
});
// after 3 idle minutes: close any dialog and go back to the calendar in its default view
let idleTimer, lastTouch = Date.now();
function goHome() {
  document.querySelectorAll("dialog[open]").forEach(d => d.close());
  calMode = localStorage.getItem("kiosk_cal_mode") || "month";
  monthCursor = new Date(); monthCursor.setDate(1); weekCursor = mondayOf(new Date()); agendaFrom = new Date();
  renderCalendar(); switchView("calendar");
}
document.addEventListener("pointerdown", () => {
  lastTouch = Date.now();
  clearTimeout(idleTimer);
  idleTimer = setTimeout(goHome, 180000);
});

/* ---------- member filter ---------- */
function renderFilter() {
  const f = $("#member-filter");
  f.replaceChildren();
  for (const m of MEMBERS) {
    const chip = el("button", "mchip" + (memberFilter.has(m.key) ? " on" : ""));
    tint(chip, m.color);
    chip.append(avatar(m), m.name);
    chip.onclick = () => {
      if (memberFilter.has(m.key) && memberFilter.size === ALL_KEYS.length) { memberFilter.clear(); memberFilter.add(m.key); }
      else if (memberFilter.has(m.key)) memberFilter.delete(m.key);
      else memberFilter.add(m.key);
      if (!memberFilter.size) ALL_KEYS.forEach(k => memberFilter.add(k));
      renderFilter(); renderUpNext(); refresh("calendar", "day");
    };
    f.appendChild(chip);
  }
}

/* ---------- month ---------- */
let monthCursor = new Date();
monthCursor.setDate(1);
let weekCursor = mondayOf(new Date());
let calMode = localStorage.getItem("kiosk_cal_mode") || "month";
let agendaFrom = new Date();
const dow = $("#cal-dow");
["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].forEach((d, i) => dow.appendChild(el("div", i > 4 ? "we" : "", d)));

function evChip(ev) {
  const c = el("div", "ev" + (ev.allday ? " allday" : ""));
  tint(c, memberColour(ev));
  setBar(c, ev);
  if (!ev.allday) c.appendChild(el("span", "t", fmtTime(new Date(ev.start))));
  c.appendChild(el("span", "what", ev.summary));
  const shown = ev.members.filter(k => memberFilter.has(k));
  if (shown.length > 1 && shown.length < ALL_KEYS.length) {
    const dots = el("span", "dots");
    for (const k of shown) { const i = el("i"); i.style.setProperty("--c", member(k).color); dots.appendChild(i); }
    c.appendChild(dots);
  }
  return c;
}

function renderCalendar(dir) {
  document.querySelectorAll("#cal-mode button").forEach(b => b.classList.toggle("active", b.dataset.mode === calMode));
  $("#cal-dow").hidden = calMode !== "month";
  $("#cal-grid").hidden = calMode !== "month";
  $("#cal-week").hidden = calMode !== "week";
  $("#cal-schedule").hidden = calMode !== "schedule";
  $("#cal-prev").disabled = false;
  if (calMode === "week") return renderWeek(dir);
  if (calMode === "schedule") return renderSchedule();
  renderMonth(dir);
}
function renderMonth(dir) {
  $("#cal-title").textContent = monthCursor.toLocaleDateString("en-AU", {month: "long", year: "numeric"});
  const grid = $("#cal-grid");
  grid.replaceChildren();
  const first = new Date(monthCursor.getFullYear(), monthCursor.getMonth(), 1);
  const start = addDays(first, -((first.getDay() + 6) % 7));
  const last = new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 0);
  const weeks = Math.ceil((((first.getDay() + 6) % 7) + last.getDate()) / 7);
  grid.style.gridTemplateRows = `repeat(${weeks}, 1fr)`;
  const cap = weeks > 5 ? 3 : 4;
  const today = ymd(new Date());
  for (let i = 0; i < weeks * 7; i++) {
    const date = addDays(start, i);
    const dstr = ymd(date);
    const cell = el("div", "day");
    if (date.getMonth() !== monthCursor.getMonth()) cell.classList.add("other");
    if (dstr === today) cell.classList.add("today");
    if (dstr < today) cell.classList.add("past");
    if (i % 7 > 4) cell.classList.add("we");
    cell.appendChild(el("div", "dnum", date.getDate()));
    const list = eventsOn(dstr);
    list.slice(0, list.length > cap ? cap - 1 : cap).forEach(ev => cell.appendChild(evChip(ev)));
    if (list.length > cap) cell.appendChild(el("div", "more", `+${list.length - cap + 1} more`));
    cell.onclick = () => showDay(dstr);
    grid.appendChild(cell);
  }
  if (dir) {
    grid.classList.remove("slide-l", "slide-r");
    void grid.offsetWidth;
    grid.classList.add(dir > 0 ? "slide-l" : "slide-r");
  }
}
function stepCal(n) {
  if (calMode === "schedule") {
    const next = addDays(agendaFrom, 14 * n);
    agendaFrom = ymd(next) < ymd(new Date()) ? new Date() : next;
    return renderSchedule();
  }
  if (calMode === "week") { weekCursor = addDays(weekCursor, 7 * n); return renderWeek(n); }
  monthCursor.setMonth(monthCursor.getMonth() + n); renderMonth(n);
}
$("#cal-prev").onclick = () => stepCal(-1);
$("#cal-next").onclick = () => stepCal(1);
$("#cal-today").onclick = () => {
  if (calMode === "week") { weekCursor = mondayOf(new Date()); return renderWeek(-1); }
  if (calMode === "schedule") { agendaFrom = new Date(); return renderSchedule(); }
  monthCursor = new Date(); monthCursor.setDate(1); renderMonth(-1);
};

// horizontal swipe on month/day
function swipe(target, fn) {
  let x0 = null;
  target.addEventListener("pointerdown", e => { x0 = e.clientX; });
  target.addEventListener("pointerup", e => {
    if (x0 !== null && Math.abs(e.clientX - x0) > 120) fn(e.clientX < x0 ? 1 : -1);
    x0 = null;
  });
}
document.querySelectorAll("#cal-mode button").forEach(b => (b.onclick = () => {
  calMode = b.dataset.mode; localStorage.setItem("kiosk_cal_mode", calMode); renderCalendar();
}));
swipe($("#cal-grid"), stepCal);
swipe($("#cal-week"), stepCal);

/* ---------- week + schedule views ---------- */
function renderWeek(dir) {
  $("#cal-title").textContent = weekTitle(weekCursor);
  const wk = $("#cal-week");
  wk.replaceChildren();
  const grid = el("div", "wgrid");
  for (let i = 0; i < 7; i++) {
    const date = addDays(weekCursor, i), dstr = ymd(date);
    const col = el("div", "wday");
    const head = el("div", "whead" + (dstr === ymd(new Date()) ? " today" : ""));
    head.append(el("b", "", date.toLocaleDateString("en-AU", {weekday: "short"})), el("span", "", String(date.getDate())));
    col.appendChild(head);
    for (const ev of eventsOn(dstr).sort((a, b) => a.start.localeCompare(b.start))) {
      const c = evChip(ev);
      c.classList.add("wev");
      c.onclick = e => { e.stopPropagation(); openEvent(ev); };
      col.appendChild(c);
    }
    if (!col.querySelector(".wev")) col.appendChild(el("div", "wempty", "Free"));
    col.onclick = () => showDay(dstr);
    grid.appendChild(col);
  }
  wk.appendChild(grid);
  wk.classList.remove("slide-l", "slide-r");
  void wk.offsetWidth;
  if (dir) wk.classList.add(dir > 0 ? "slide-l" : "slide-r");
}

function renderSchedule() {
  const from = ymd(agendaFrom), isNow = from === ymd(new Date());
  $("#cal-title").textContent = isNow ? "Coming up" : "From " + agendaFrom.toLocaleDateString("en-AU", {day: "numeric", month: "long"});
  $("#cal-prev").disabled = isNow;
  const list = $("#cal-schedule");
  list.replaceChildren();
  const byDay = new Map();
  for (const ev of events.filter(visible)) {
    for (const d of evDays(ev)) {
      if (d < from) continue;
      if (!byDay.has(d)) byDay.set(d, []);
      byDay.get(d).push(ev);
    }
  }
  const days = [...byDay.keys()].sort().slice(0, 45);
  if (!days.length) list.appendChild(el("div", "muted", "Nothing coming up."));
  for (const d of days) {
    list.appendChild(el("div", "shead", dateOf(d).toLocaleDateString("en-AU", {weekday: "long", day: "numeric", month: "long"})));
    for (const ev of byDay.get(d).sort((a, b) => a.start.localeCompare(b.start))) {
      const c = evChip(ev);
      c.classList.add("sev");
      c.onclick = () => openEvent(ev);
      list.appendChild(c);
    }
  }
}

/* ---------- up next ---------- */
function renderUpNext() {
  const box = $("#upnext-list");
  const now = new Date();
  const today = ymd(now), tomorrow = ymd(addDays(now, 1));
  const items = events.filter(ev => visible(ev) && (ev.allday
      ? evDays(ev).some(d => d === today || d === tomorrow)
      : new Date(ev.end) > now && ymd(new Date(ev.start)) <= tomorrow))
    .sort((a, b) => (a.allday ? a.start : a.start).localeCompare(b.start)).slice(0, 6);
  box.replaceChildren();
  if (!items.length) { box.appendChild(el("div", "empty-note", "Nothing on today or tomorrow")); return; }
  for (const ev of items) {
    const s = new Date(ev.start);
    const live = !ev.allday && s <= now;
    const day = ev.allday ? (evDays(ev).includes(today) ? "Today" : "Tomorrow") : (ymd(s) === today ? "Today" : "Tomorrow");
    const row = el("div", "un" + (live ? " now" : ""));
    tint(row, memberColour(ev));
    setBar(row, ev);
    const tx = el("div");
    tx.append(el("div", "when", live ? "On now" : `${day}${ev.allday ? ", all day" : " " + fmtTime(s)}`), el("div", "what", ev.summary));
    row.append(el("div", "bar"), tx);
    row.onclick = () => openEvent(ev);
    box.appendChild(row);
  }
}

/* ---------- day ---------- */
let currentDay = null;
function showDay(dstr) { currentDay = dstr; renderDay(); switchView("day"); }
function renderDay(anim) {
  const d = dateOf(currentDay);
  const rel = {[ymd(new Date())]: "Today", [ymd(addDays(new Date(), 1))]: "Tomorrow", [ymd(addDays(new Date(), -1))]: "Yesterday"}[currentDay];
  $("#day-title").textContent = (rel ? rel + ", " : "") + d.toLocaleDateString("en-AU", {weekday: rel ? undefined : "long", day: "numeric", month: "long"});
  const list = $("#day-list");
  list.replaceChildren();
  const now = new Date();
  const dayEvents = eventsOn(currentDay);
  dayEvents.forEach((ev, i) => {
    const card = el("div", "dev");
    tint(card, memberColour(ev));
    setBar(card, ev);
    card.style.animationDelay = `${i * 40}ms`;
    const s = new Date(ev.start), e = new Date(ev.end);
    if (!ev.allday && e < now) card.classList.add("past");
    if (!ev.allday && s <= now && e > now) card.classList.add("now");
    const tm = el("div", "tm");
    if (ev.allday) tm.append(el("b", "", "All day"));
    else tm.append(el("b", "", fmtTime(s)), el("span", "", "until " + fmtTime(e)));
    const tx = el("div", "tx");
    tx.appendChild(el("div", "s", ev.summary));
    if (ev.location) { const l = el("div", "loc"); l.append(icon("pin"), ev.location); tx.appendChild(l); }
    const who = el("div", "who");
    const ms = ev.members.length === ALL_KEYS.length ? [] : ev.members;
    ms.forEach(k => who.appendChild(avatar(member(k))));
    if (!ms.length) who.appendChild(el("span", "muted", "Everyone"));
    card.append(tm, tx, who);
    if (ev.source === "google") { const src = el("span", "src"); src.appendChild(icon("lock")); card.appendChild(src); }
    card.onclick = () => openEvent(ev);
    list.appendChild(card);
  });
  if (!dayEvents.length) {
    const e = el("div", "day-empty");
    e.append(el("b", "", "\u2600\ufe0f"), "Nothing planned. Tap New event to add one.");
    list.appendChild(e);
  }
  if (anim) { list.classList.remove("swap"); void list.offsetWidth; list.classList.add("swap"); }
}
const stepDay = n => { currentDay = ymd(addDays(dateOf(currentDay), n)); renderDay(true); };
$("#day-prev").onclick = () => stepDay(-1);
$("#day-next").onclick = () => stepDay(1);
swipe($("#day-list"), stepDay);
$("#day-back").onclick = () => {
  const d = dateOf(currentDay);
  monthCursor = new Date(d.getFullYear(), d.getMonth(), 1);
  weekCursor = mondayOf(d);
  renderCalendar(); switchView("calendar");
};
$("#day-add").onclick = () => openEditor(null, currentDay);

function openEvent(ev) {
  if (ev.source === "google") return openInfo(ev);
  openEditor(ev);
}

/* ---------- google event info (read-only) ---------- */
function openInfo(ev) {
  const who = $("#info-who");
  who.replaceChildren();
  const ms = ev.members.length === ALL_KEYS.length ? [] : ev.members;
  for (const k of ms) {
    const m = member(k);
    const c = el("span", "mchip on"); tint(c, m.color); c.append(avatar(m), m.name); who.appendChild(c);
  }
  if (!ms.length) who.appendChild(el("span", "mchip on", "Whole family"));
  $("#info-title").textContent = ev.summary;
  const s = new Date(ev.start), e = new Date(ev.end);
  $("#info-when").textContent = ev.allday
    ? dateOf(ev.start.slice(0, 10)).toLocaleDateString("en-AU", {weekday: "long", day: "numeric", month: "long"}) + ", all day"
    : `${s.toLocaleDateString("en-AU", {weekday: "long", day: "numeric", month: "long"})}, ${fmtTime(s)} to ${fmtTime(e)}`;
  $("#info-where").textContent = ev.location || "";
  $("#info-dialog").showModal();
}
$("#info-close").onclick = () => $("#info-dialog").close();

/* ---------- wall event editor (stored in Home Assistant) ---------- */
let editing = null;
const chosen = new Set();
function openEditor(ev, dstr) {
  editing = ev ? {...ev, uid: ev.seriesUid || ev.uid} : null;
  $("#ev-dialog-title").textContent = ev ? "Edit event" : "New event";
  $("#ev-del").hidden = !ev;
  $("#ev-date").value = ev ? evDays(ev)[0] : (dstr || ymd(new Date()));
  if (ev && !ev.allday) {
    $("#ev-start").value = `${pad(new Date(ev.start).getHours())}:${pad(new Date(ev.start).getMinutes())}`;
    $("#ev-end").value = `${pad(new Date(ev.end).getHours())}:${pad(new Date(ev.end).getMinutes())}`;
  } else { $("#ev-start").value = "09:00"; $("#ev-end").value = "10:00"; }
  $("#ev-allday").checked = !!(ev && ev.allday);
  $("#ev-repeat").value = ev && ev.rrule ? (/INTERVAL=2/.test(ev.rrule) ? "fortnightly" : /DAILY/.test(ev.rrule) ? "daily" : "weekly") : "";
  $("#ev-summary").value = ev ? ev.summary : "";
  chosen.clear();
  (ev && ev.members.length < ALL_KEYS.length ? ev.members : []).forEach(k => chosen.add(k));
  const who = $("#ev-who");
  who.replaceChildren();
  for (const m of MEMBERS) {
    const chip = el("button", "mchip" + (chosen.has(m.key) ? " on" : ""));
    tint(chip, m.color);
    chip.append(avatar(m), m.name);
    chip.onclick = () => { if (chosen.has(m.key)) chosen.delete(m.key); else chosen.add(m.key); chip.classList.toggle("on"); };
    who.appendChild(chip);
  }
  syncAllDay();
  $("#ev-dialog").showModal();
}
function syncAllDay() { document.querySelectorAll(".ev-time").forEach(e => { e.hidden = $("#ev-allday").checked; }); }
$("#ev-allday").onchange = syncAllDay;
$("#ev-cancel").onclick = () => $("#ev-dialog").close();

// title stored with people tags, same format as Google ("Riley, Casey: Swimming")
function taggedTitle(summary, keys) {
  if (!keys.length || keys.length === ALL_KEYS.length) return keys.length ? `Family: ${summary}` : summary;
  return `${ALL_KEYS.filter(k => keys.includes(k)).map(k => member(k).name).join(", ")}: ${summary}`;
}
const RRULES = {daily: "FREQ=DAILY", weekly: "FREQ=WEEKLY", fortnightly: "FREQ=WEEKLY;INTERVAL=2"};

$("#ev-save").onclick = async () => {
  const summary = $("#ev-summary").value.trim();
  if (!summary) return toast("Add a title first");
  const date = $("#ev-date").value, allday = $("#ev-allday").checked;
  const op = {
    op: editing ? "event_update" : "event_create", id: editing && editing.uid,
    title: taggedTitle(summary, [...chosen]), allday, rrule: RRULES[$("#ev-repeat").value] || "",
    start: allday ? date : new Date(`${date}T${$("#ev-start").value}:00`).toISOString(),
    end: allday ? ymd(addDays(dateOf(date), 1)) : new Date(`${date}T${$("#ev-end").value}:00`).toISOString(),
  };
  if (!allday && op.end <= op.start) return toast("End time must be after the start");
  $("#ev-dialog").close();
  try { await kop(op); toast(editing ? "Event updated" : "Event added"); }
  catch (e) { toast("Couldn't save: " + e.message); }
};
$("#ev-del").onclick = async () => {
  if (!editing) return;
  $("#ev-dialog").close();
  try { await kop({op: "event_delete", id: editing.uid}); toast("Event deleted"); }
  catch (e) { toast("Couldn't delete: " + e.message); }
};

/* ---------- chores: weekly money chart ---------- */
const KIDS = CFG.kids;
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
let choreKid = KIDS[0].key;

function renderChores() {
  if (!kstate) return;
  const week = dateOf(kstate.week), today = kstate.today;
  const f = d => d.toLocaleDateString("en-AU", {day: "numeric", month: "short"});
  $("#chore-week").textContent = `${f(week)} to ${f(addDays(week, 6))}, adds up Sunday night`;
  const tabs = $("#chore-tabs");
  tabs.replaceChildren();
  let weekAll = 0;
  for (const kid of KIDS) {
    const k = kstate.kids[kid.key] || {chores: [], ticks: {}, balance: 0, week: 0};
    weekAll += k.week;
    const t = el("button", "ktab" + (kid.key === choreKid ? " on" : ""));
    tint(t, kid.color);
    const tx = el("div");
    const prog = todayProgress(k, today);
    tx.append(el("b", "", kid.name), el("span", "", `${money(k.week)} this week \u00b7 ${prog.done}/${prog.total} today`));
    const ring = el("span", "ring" + (prog.total && prog.done === prog.total ? " done" : ""));
    ring.style.setProperty("--p", prog.total ? prog.done / prog.total : 0);
    ring.appendChild(avatar(kid));
    t.append(ring, tx);
    t.onclick = () => { choreKid = kid.key; renderChores(); };
    tabs.appendChild(t);
  }
  $("#chore-total").textContent = `${money(weekAll)} earned this week`;

  const kid = KIDS.find(k => k.key === choreKid);
  const k = kstate.kids[kid.key] || {chores: [], ticks: {}, balance: 0, week: 0};
  const sheet = $("#chore-sheet");
  sheet.replaceChildren();
  tint(sheet, kid.color);
  const grid = el("div", "cgrid");
  grid.appendChild(el("div", "ch corner", "Chore"));
  grid.appendChild(el("div", "ch amt", "$"));
  DAYS.forEach((d, i) => {
    const day = ymd(addDays(week, i));
    const h = el("div", "ch" + (day === today ? " today" : ""));
    h.append(el("b", "", d), el("span", "", String(addDays(week, i).getDate())));
    grid.appendChild(h);
  });
  grid.appendChild(el("div", "ch amt", "Week"));
  for (const c of k.chores) {
    const ticks = new Set(k.ticks[c.id] || []);
    const name = el("div", "cname", c.name);
    grid.append(name, el("div", "camt", money(c.cents)));
    DAYS.forEach((d, i) => {
      const day = ymd(addDays(week, i));
      const on = ticks.has(day);
      const b = el("button", "cbox" + (on ? " on" : "") + (day > today ? " future" : "") + (day === today ? " today" : ""));
      b.appendChild(icon("tick"));
      b.setAttribute("aria-label", `${c.name}, ${d} ${addDays(week, i).getDate()}`);
      b.setAttribute("aria-pressed", String(on));
      b.disabled = day > today;
      b.onclick = () => tick(kid, c, day, !b.classList.contains("on"), b);
      grid.appendChild(b);
    });
    grid.appendChild(el("div", "camt sum", money(ticks.size * c.cents)));
  }
  if (!k.chores.length) grid.appendChild(el("div", "cempty", `No chores for ${kid.name} yet. Tap Edit chores to add some.`));
  sheet.appendChild(grid);

  const foot = el("div", "cfoot");
  const wk = el("div", "stat"); wk.append(el("span", "", "This week so far"), el("b", "", money(k.week)));
  const owed = el("div", "stat"); owed.append(el("span", "", "Owed from past weeks"), el("b", "", money(k.balance)));
  foot.append(wk, owed);
  sheet.appendChild(foot);
}

async function tick(kid, chore, day, on, btn) {
  btn.classList.toggle("on", on);
  btn.setAttribute("aria-pressed", String(on));
  if (on) btn.classList.add("pop");
  try {
    const st = await kop({op: "tick", kid: kid.key, id: chore.id, day, on});
    const p = todayProgress(st.kids[kid.key], st.today);
    if (on && day === st.today && p.total && p.done === p.total) celebrate(`${kid.name} finished every chore today!`, kid.color);
  }
  catch (e) { toast("Couldn't save tick: " + e.message); btn.classList.toggle("on", !on); }
}
function celebrate(msg, colour) {
  toast(msg);
  const box = el("div", "confetti");
  const colours = [colour, "#ffd166", "#3ddc97", "#6cb8ff", "#ff8a3d"];
  for (let i = 0; i < 70; i++) {
    const c = el("i");
    c.style.left = Math.random() * 100 + "%";
    c.style.background = colours[i % colours.length];
    c.style.animationDelay = Math.random() * 0.5 + "s";
    c.style.setProperty("--x", (Math.random() * 300 - 150) + "px");
    c.style.setProperty("--r", (Math.random() * 720 - 360) + "deg");
    box.appendChild(c);
  }
  document.body.appendChild(box);
  setTimeout(() => box.remove(), 3200);
}

/* ---------- settings (applied by the kiosk app itself via the Kiosk bridge) ---------- */
const kioskCalls = {};
window.__kioskCb = (id, r) => { if (kioskCalls[id]) { kioskCalls[id](r); delete kioskCalls[id]; } };
function kiosk(action, args = {}, timeout = 40000) {
  if (!window.Kiosk) return Promise.reject(new Error("Only available on the wall"));
  return new Promise((res, rej) => {
    const id = Math.random().toString(36).slice(2);
    kioskCalls[id] = r => (r.ok ? res(r.result) : rej(new Error(r.error)));
    window.Kiosk.call(id, action, JSON.stringify(args));
    setTimeout(() => { if (kioskCalls[id]) { delete kioskCalls[id]; rej(new Error("No reply from the kiosk app")); } }, timeout);
  });
}
const TIMEZONES = ["Australia/Perth", "Australia/Darwin", "Australia/Adelaide", "Australia/Brisbane", "Australia/Sydney",
  "Australia/Melbourne", "Australia/Hobart", "Pacific/Auckland", "Asia/Singapore", "Asia/Bali", "Europe/London", "UTC"];
let dev = null;

async function openSettings() {
  switchView("settings");
  $("#set-status").textContent = "";
  try {
    dev = await kiosk("getSettings");
    $("#set-bright").value = dev.brightness;
    $("#set-bright-v").textContent = Math.round(dev.brightness / 2.55) + "%";
    $("#set-sleep-on").checked = dev.sleepOn;
    $("#set-sleep-from").value = dev.sleepFrom;
    $("#set-sleep-to").value = dev.sleepTo;
    const tz = $("#set-tz");
    tz.replaceChildren();
    for (const z of new Set([dev.timezone, ...TIMEZONES])) {
      const o = el("option", "", z.replace("_", " ")); o.value = z; o.selected = z === dev.timezone; tz.appendChild(o);
    }
    $("#set-version").textContent = `App ${dev.appVersion}, web build ${BUILD || "dev"}`;
    renderDeviceInfo();
    refreshWifiStatus();
  } catch (e) { $("#set-status").textContent = e.message; }
  renderGoogleStatus();
}
async function refreshWifiStatus() {
  try {
    const w = await kiosk("wifiStatus");
    $("#wifi-now").textContent = w.ssid ? `Connected to ${w.ssid} (${w.ip})` : "Not connected";
  } catch (e) { $("#wifi-now").textContent = e.message; }
}
async function renderDeviceInfo() {
  try {
    const info = await kiosk("deviceInfo");
    const kv = $("#device-info");
    kv.replaceChildren();
    for (const [k, v] of Object.entries(info)) {
      const row = el("div", "srow");
      row.append(el("span", "", k), el("b", "", String(v)));
      kv.appendChild(row);
    }
  } catch (e) { $("#device-info").replaceChildren(el("div", "muted", e.message)); }
}
function renderGoogleStatus() {
  const g = kstate && kstate.google;
  $("#g-status").textContent = !g || !g.configured ? "Not set up yet. Paste the Apps Script feed URL below."
    : g.error ? `Last sync failed: ${g.error}. Showing the last good copy.`
    : g.ok_at ? `Synced ${fmtTime(new Date(g.ok_at))}, ${g.events.length} events cached in Home Assistant.`
    : "Waiting for the first sync...";
}

$("#set-bright").oninput = e => { $("#set-bright-v").textContent = Math.round(e.target.value / 2.55) + "%"; };
$("#set-bright").onchange = e => kiosk("setBrightness", {value: Number(e.target.value)}).catch(err => toast(err.message));
$("#set-tz").onchange = e => kiosk("setTimezone", {timezone: e.target.value}).then(() => { toast("Timezone changed"); tickClock(); renderCalendar(); }).catch(err => toast(err.message));
function saveSleep() {
  kiosk("setSleep", {on: $("#set-sleep-on").checked, from: $("#set-sleep-from").value, to: $("#set-sleep-to").value})
    .then(() => toast($("#set-sleep-on").checked ? `Screen off ${$("#set-sleep-from").value} to ${$("#set-sleep-to").value}` : "Screen sleep off"))
    .catch(err => toast(err.message));
}
["#set-sleep-on", "#set-sleep-from", "#set-sleep-to"].forEach(id => ($(id).onchange = saveSleep));
$("#set-sleep-now").onclick = () => kiosk("sleepNow").catch(err => toast(err.message));
$("#set-reload").onclick = () => kiosk("reload").catch(() => location.reload());
$("#set-default-view").value = calMode;
$("#set-clock").value = h24 ? "24" : "12";
$("#set-clock").onchange = e => {
  h24 = e.target.value === "24";
  localStorage.setItem("kiosk_h24", h24 ? "1" : "0");
  tickClock(); renderCalendar(); renderUpNext();
  if (currentView === "day") renderDay();
  toast(h24 ? "Showing 24 hour time" : "Showing 12 hour time");
};
$("#set-default-view").onchange = e => {
  calMode = e.target.value;
  localStorage.setItem("kiosk_cal_mode", calMode);
  renderCalendar();
  toast("Default view saved");
};
$("#set-close").onclick = () => switchView("calendar");
$("#rail-settings").onclick = openSettings;

$("#wifi-scan").onclick = async () => {
  const list = $("#wifi-list");
  list.replaceChildren(el("div", "muted", "Scanning..."));
  try {
    const nets = await kiosk("wifiScan");
    list.replaceChildren();
    for (const n of nets) {
      const b = el("button", "wnet");
      const bars = n.rssi > -55 ? 4 : n.rssi > -67 ? 3 : n.rssi > -78 ? 2 : 1;
      b.append(el("b", "", n.ssid), el("span", "muted", `${n.band}${n.security === "open" ? ", open" : ""}`), el("span", "bars b" + bars));
      b.onclick = () => openWifi(n);
      list.appendChild(b);
    }
    if (!nets.length) list.appendChild(el("div", "muted", "No networks found"));
  } catch (e) { list.replaceChildren(el("div", "muted", e.message)); }
};
let wifiTarget = null;
function openWifi(n) {
  wifiTarget = n;
  $("#wifi-title").textContent = `Join ${n.ssid}`;
  $("#wifi-pass").value = "";
  $("#wifi-pass-row").hidden = n.security === "open";
  buildKeyboard();
  $("#wifi-dialog").showModal();
}
$("#wifi-cancel").onclick = () => $("#wifi-dialog").close();
$("#wifi-join").onclick = async () => {
  const n = wifiTarget;
  $("#wifi-join").disabled = true;
  $("#wifi-join").textContent = "Joining...";
  try {
    await kiosk("wifiConnect", {ssid: n.ssid, security: n.security, password: $("#wifi-pass").value}, 60000);
    $("#wifi-dialog").close();
    toast(`Connected to ${n.ssid}`);
  } catch (e) { toast(e.message); }
  finally { $("#wifi-join").disabled = false; $("#wifi-join").textContent = "Join"; refreshWifiStatus(); }
};

/* on-screen keyboard (the board has no reliable system keyboard in the WebView) */
const KB = {lower: ["1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm"], upper: ["!@#$%^&*()", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]};
let kbShift = false;
function buildKeyboard() {
  const kb = $("#kb");
  kb.replaceChildren();
  KB[kbShift ? "upper" : "lower"].forEach((row, i) => {
    const r = el("div", "kr");
    if (i === 3) { const sh = el("button", "k wide" + (kbShift ? " on" : ""), "Shift"); sh.onclick = () => { kbShift = !kbShift; buildKeyboard(); }; r.appendChild(sh); }
    for (const ch of row) { const k = el("button", "k", ch); k.onclick = () => { $("#wifi-pass").value += ch; }; r.appendChild(k); }
    if (i === 3) { const bk = el("button", "k wide", "Delete"); bk.onclick = () => { const p = $("#wifi-pass"); p.value = p.value.slice(0, -1); }; r.appendChild(bk); }
    kb.appendChild(r);
  });
  const last = el("div", "kr");
  for (const ch of ["-", "_", ".", "space", "'", "?"]) {
    const k = el("button", "k" + (ch === "space" ? " space" : ""), ch === "space" ? "Space" : ch);
    k.onclick = () => { $("#wifi-pass").value += ch === "space" ? " " : ch; };
    last.appendChild(k);
  }
  kb.appendChild(last);
}
$("#wifi-show").onclick = () => { const p = $("#wifi-pass"); p.type = p.type === "password" ? "text" : "password"; };

$("#g-save").onclick = async () => {
  try { await kop({op: "google_url", url: $("#g-url").value.trim()}); $("#g-url").value = ""; toast("Saved. Home Assistant will sync in a few seconds."); setTimeout(renderGoogleStatus, 4000); }
  catch (e) { toast(e.message); }
};

$("#zone-pos").oninput = e => { $("#zone-pct").textContent = e.target.value + "%"; };
document.querySelectorAll(".zstep").forEach(b => b.onclick = () => {
  const r = $("#zone-pos");
  r.value = Math.max(0, Math.min(100, Number(r.value) + Number(b.dataset.d)));
  $("#zone-pct").textContent = r.value + "%";
});
$("#zone-cancel").onclick = () => $("#zone-dialog").close();
$("#zone-save").onclick = async () => {
  const v = Number($("#zone-pos").value);
  $("#zone-dialog").close();
  try { await haService("cover", "set_cover_position", {entity_id: zoneTarget.cover, position: v}); toast(`${zoneTarget.name} damper ${v}%`); }
  catch (e) { toast("Couldn't set damper: " + e.message); }
};

/* ---------- controls + live states ---------- */
const LIGHTS = CFG.lights || [];
const ACS = [CFG.ac || "climate.ac"];
const ZONES = CFG.zones || [];
const GARAGE = CFG.garage || "cover.garage_door";
let garagePending = null;
const states = {};
let subscribed = false;

async function subscribeStates() {
  if (subscribed) return;
  subscribed = true;
  await haCall("subscribe_entities", {entity_ids: [...LIGHTS, ...ACS, ...ZONES.map(z => z.cover), GARAGE, CFG.weather, "sun.sun"]});
}
function applyState(eid) {
  const st = states[eid];
  if (eid === CFG.weather) { weatherState = st; renderWeather(); }
  else if (eid === "sun.sun") { sunState = st; applyNight(); }
  else return true;
}
function onStateDelta(data) {
  let ctl = false;
  for (const [eid, s] of Object.entries(data.a || {})) { states[eid] = {s: s.s, a: s.a || {}}; if (applyState(eid)) ctl = true; }
  for (const [eid, d] of Object.entries(data.c || {})) {
    const plus = d["+"] || {};
    const prev = states[eid] || {a: {}};
    states[eid] = {s: plus.s !== undefined ? plus.s : prev.s, a: Object.assign({}, prev.a, plus.a || {})};
    for (const k of (d["-"] && d["-"].a) || []) delete states[eid].a[k];
    if (applyState(eid)) ctl = true;
  }
  if (ctl) refresh("controls");
}
async function refreshStates() {
  try {
    const r = await haCall("get_states", {});
    for (const st of r.result || []) states[st.entity_id] = {s: st.state, a: st.attributes};
    [CFG.weather, "sun.sun"].forEach(e => states[e] && applyState(e));
    refresh("controls");
  } catch {}
}

const lightWant = new Map(); // eid -> {on, at}: last tap wins over a stale state for 4s
function lightTile(eid) {
  const st = states[eid];
  const na = !st || st.s === "unavailable";
  const want = lightWant.get(eid);
  if (want && (Date.now() - want.at > 4000 || (st && (st.s === "on") === want.on))) lightWant.delete(eid);
  const isOn = !na && (lightWant.has(eid) ? want.on : st.s === "on");
  const name = tileName(st && st.a.friendly_name, eid);
  const bri = isOn && st.a.brightness ? Math.round(st.a.brightness / 2.55) : null;
  const tile = el("button", "lt" + (isOn ? " on" : "") + (na ? " na" : ""));
  tile.setAttribute("aria-pressed", String(isOn));
  const info = el("div", "lt-info");
  info.append(el("div", "nm", name), el("div", "st", na ? "Offline" : isOn ? (bri ? bri + "%" : "On") : "Off"));
  tile.append(icon(/wled|strip/i.test(eid + name) ? "strip" : "bulb"), info);
  if (bri) { const bar = el("i", "lt-bar"); bar.style.width = bri + "%"; tile.appendChild(bar); }
  tile.onclick = () => {
    if (na) return toast(name + " is offline");
    const turnOn = !tile.classList.contains("on");
    lightWant.set(eid, {on: turnOn, at: Date.now()});
    tile.classList.toggle("on", turnOn);
    tile.setAttribute("aria-pressed", String(turnOn));
    tile.querySelector(".st").textContent = turnOn ? "On" : "Off";
    haService("light", turnOn ? "turn_on" : "turn_off", {entity_id: eid})
      .catch(() => { lightWant.delete(eid); tile.classList.toggle("on", !turnOn); toast("Couldn't reach " + name); });
  };
  return tile;
}

function acCard(eid) {
  const MODES = {off: "power", cool: "snow", heat: "flame", fan_only: "fan"};
  const LABEL = {off: "Off", cool: "Cooling", heat: "Heating", fan_only: "Fan only", dry: "Dry", auto: "Auto", heat_cool: "Auto"};
  const st = states[eid];
  const a = (st && st.a) || {};
  const mode = (st && st.s) || "off";
  const card = el("div", "ac " + mode);
  const head = el("div", "ac-head");
  const where = el("div", "ac-where");
  where.append(el("div", "nm", "Air conditioner"), el("div", "cur", LABEL[mode] || tileName(mode, "x." + mode)));
  const inside = el("div", "ac-inside");
  inside.append(el("b", "", a.current_temperature != null ? `${Math.round(a.current_temperature)}\u00b0` : "--"), el("span", "", "inside"));
  head.append(where, inside);
  const main = el("div", "ac-main");
  const minus = el("button", "rbtn"); minus.appendChild(icon("minus")); minus.setAttribute("aria-label", "Cooler");
  const plus = el("button", "rbtn"); plus.appendChild(icon("plus")); plus.setAttribute("aria-label", "Warmer");
  const t = el("div", "temp");
  t.append(a.temperature != null ? String(a.temperature) : "--", el("small", "", "\u00b0C"));
  const step = a.target_temp_step || 1;
  const setT = v => { t.firstChild.textContent = String(v); haService("climate", "set_temperature", {entity_id: eid, temperature: v}).catch(() => toast("Couldn't set temperature")); };
  minus.onclick = () => setT(Math.max(a.min_temp || 16, (a.temperature || 24) - step));
  plus.onclick = () => setT(Math.min(a.max_temp || 30, (a.temperature || 24) + step));
  main.append(minus, t, plus);
  if (mode === "off") main.classList.add("idle");
  const modes = el("div", "ac-modes");
  for (const m of ["off", "cool", "heat", "fan_only"]) { // dry/auto left to the HA app
    if (a.hvac_modes && !a.hvac_modes.includes(m)) continue;
    const b = el("button", "m-" + m + (m === mode ? " sel" : ""));
    b.append(icon(MODES[m]), el("span", "", LABEL[m]));
    b.onclick = () => haService("climate", "set_hvac_mode", {entity_id: eid, hvac_mode: m}).catch(() => toast("Couldn't change mode"));
    modes.appendChild(b);
  }
  card.append(head, main, modes);
  return card;
}

/* "Theatre Damper" -> "Theatre"; config name wins if set */
const zoneName = (z, st) => z.name || tileName(st.a.friendly_name, z.cover).replace(/\s+damper$/i, "");
function zoneRow(z) {
  const st = states[z.cover] || {s: "unavailable", a: {}};
  z = {...z, name: zoneName(z, st)};
  const na = st.s === "unavailable";
  const open = !na && st.s !== "closed";
  const pos = st.a.current_position;
  const row = el("div", "zone" + (open ? " open" : "") + (na ? " na" : ""));
  const tog = el("button", "ztoggle" + (open ? " on" : ""));
  tog.setAttribute("aria-label", `${z.name} ${open ? "close" : "open"}`);
  tog.appendChild(icon("fan"));
  tog.onclick = () => {
    tog.classList.toggle("on");
    haService("cover", open ? "close_cover" : "open_cover", {entity_id: z.cover}).catch(() => toast("Couldn't reach " + z.name));
  };
  const slide = el("button", "zslider");
  slide.setAttribute("aria-label", `${z.name} damper ${pos ?? 0}%`);
  const fill = el("i");
  fill.style.width = (open ? pos ?? 100 : 0) + "%";
  slide.appendChild(fill);
  slide.onclick = () => zoneDialog(z, pos);
  row.append(tog, el("div", "nm", z.name), slide, el("div", "zpct", na ? "--" : open ? (pos ?? 100) + "%" : "Off"));
  return row;
}

function garageCard() {
  const g = states[GARAGE];
  const box = $("#ctl-garage");
  box.replaceChildren();
  box.closest(".ctl-col").classList.toggle("no-garage", !g);
  if (!g) return;
  const v = garageView(g.s, garagePending);
  garagePending = v.pending;
  const card = el("button", "garage" + (v.open ? " open" : "") + (v.moving ? " moving" : ""));
  const txt = el("div", "g-txt");
  txt.append(el("div", "nm", "Garage door"), el("div", "cur", v.label));
  const hint = el("div", "g-hint", v.moving ? "" : v.open ? "Tap to close" : "Tap to open");
  card.append(icon("garage"), txt, hint);
  card.onclick = () => {
    if (v.moving) return;
    garagePending = {target: v.open ? "closed" : "open", at: Date.now()};
    renderControls();
    setTimeout(renderControls, 91000);
    haService("cover", v.open ? "close_cover" : "open_cover", {entity_id: GARAGE})
      .catch(() => { garagePending = null; renderControls(); toast("Couldn't reach the garage"); });
  };
  box.appendChild(card);
}

function renderControls() {
  const grid = $("#ctl-light-grid");
  grid.replaceChildren(...LIGHTS.map(lightTile));
  const on = LIGHTS.filter(e => states[e] && states[e].s === "on").length;
  $("#lights-on").textContent = on ? `${on} on` : "all off";
  $("#all-off").disabled = !on;
  $("#ctl-ac-list").replaceChildren(...ACS.map(acCard));
  $("#ctl-zone-list").replaceChildren(...ZONES.map(zoneRow));
  garageCard();
  const ac = states[ACS[0]];
  const sum = [];
  if (ac && ac.a.current_temperature != null) sum.push(`${Math.round(ac.a.current_temperature)}\u00b0 inside`);
  sum.push(on ? `${on} light${on > 1 ? "s" : ""} on` : "Lights off");
  const g = states[GARAGE];
  if (g) sum.push(`garage ${garageView(g.s, garagePending).label.toLowerCase().replace("...", "")}`);
  $("#home-sum").textContent = sum.join(" \u00b7 ");
}
$("#all-off").onclick = () => {
  const on = LIGHTS.filter(e => states[e] && states[e].s === "on");
  if (!on.length) return;
  document.querySelectorAll(".lt.on").forEach(t => t.classList.remove("on"));
  haService("light", "turn_off", {entity_id: on}).then(() => toast(`Turned off ${on.length} light${on.length > 1 ? "s" : ""}`))
    .catch(() => toast("Couldn't reach the lights"));
};

// zone damper % dialog (tap a slider to set open %)
let zoneTarget = null;
function zoneDialog(zone, pos) {
  zoneTarget = zone;
  $("#zone-title").textContent = `${zone.name} damper`; // zone already has its display name (from zoneRow)
  $("#zone-pos").value = pos != null ? pos : 50;
  $("#zone-pct").textContent = (pos != null ? pos : 50) + "%";
  $("#zone-dialog").showModal();
}

/* ---------- boot ----------
   Everything that runs on load lives here, after every top-level declaration,
   so no timer or handler can touch state before it exists. */
booted = true;
tickClock();
setInterval(tickClock, 1000);
renderFilter();
renderCalendar();
renderControls();
haConnect();
applyNight();
pollState();

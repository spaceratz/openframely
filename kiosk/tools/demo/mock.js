/* Demo mode for README screenshots: a fake Home Assistant, kiosk bridge and
   household. Loaded by demo.html in place of a real HA connection, so the
   screenshots contain no real names, entities, network or device details. */
(function () {
  const pad = n => String(n).padStart(2, "0");
  const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const day = n => { const d = new Date(today); d.setDate(d.getDate() + n); return d; };
  const at = (n, h, m = 0) => { const d = day(n); d.setHours(h, m); return d.toISOString(); };
  const allday = (n, len = 1) => ({start: ymd(day(n)), end: ymd(day(n + len)), allday: true});
  const timed = (n, h, m, mins) => ({start: at(n, h, m), end: new Date(new Date(at(n, h, m)).getTime() + mins * 60000).toISOString()});

  window.KIOSK_CONFIG = {
    haUrl: "http://demo.invalid", token: "demo", weather: "weather.home",
    nightFrom: 21, nightTo: 6,
    members: [
      {key: "alex", name: "Alex", color: "#ea6c2b"},
      {key: "sam", name: "Sam", color: "#2babea"},
      {key: "robin", name: "Robin", color: "#ead12b"},
      {key: "jamie", name: "Jamie", color: "#ea2b45"},
      {key: "riley", name: "Riley", color: "#7a5cff"},
      {key: "casey", name: "Casey", color: "#2bd48a"},
    ],
    aliases: {alex: "alex", sam: "sam"},
    lights: ["light.living_room", "light.dining_room", "light.kitchen", "light.kitchen_bench", "light.study",
             "light.main_bedroom", "light.robin_bedroom", "light.jamie_bedroom", "light.riley_bedroom",
             "light.casey_bedroom", "light.porch", "light.deck_strip"],
    ac: "climate.ac", garage: "cover.garage_door",
    zones: [
      {cover: "cover.living_damper"}, {name: "Main bed", cover: "cover.main_damper"},
      {cover: "cover.robin_damper"}, {cover: "cover.jamie_damper"},
      {cover: "cover.riley_damper"}, {cover: "cover.casey_damper"},
    ],
    kids: [
      {key: "casey", name: "Casey", color: "#2bd48a"}, {key: "riley", name: "Riley", color: "#7a5cff"},
      {key: "jamie", name: "Jamie", color: "#ea2b45"}, {key: "robin", name: "Robin", color: "#ead12b"},
    ],
  };

  // ---- calendar ----
  const wk = n => (7 + n - ((today.getDay() + 6) % 7)) % 7; // days until weekday n (0=Mon) this week
  let id = 0;
  const ev = (title, when, extra = {}) => ({id: "d" + ++id, title, source: "wall", location: "", rrule: "", ...when, ...extra});
  const events = [
    ev("Riley, Casey: Swimming", timed(wk(1) - 7, 16, 0, 60), {rrule: "FREQ=WEEKLY"}),
    ev("Jamie: Netball training", timed(wk(3) - 7, 17, 30, 90), {rrule: "FREQ=WEEKLY"}),
    ev("Robin: Piano lesson", timed(wk(2) - 7, 15, 45, 30), {rrule: "FREQ=WEEKLY"}),
    ev("Casey: Soccer", timed(wk(5) - 7, 9, 0, 60), {rrule: "FREQ=WEEKLY"}),
    ev("Family: Pancake breakfast", timed(wk(6) - 7, 8, 30, 60), {rrule: "FREQ=WEEKLY"}),
    ev("Sam: Book club", timed(2, 19, 30, 120)),
    ev("Alex: Dentist", timed(1, 10, 0, 45)),
    ev("Robin, Jamie: School disco", timed(4, 18, 0, 150)),
    ev("Family: Grandma's birthday lunch", timed(9, 12, 0, 180), {location: "Riverside Cafe"}),
    ev("Riley: Library books due", allday(3)),
    ev("Family: Camping weekend", allday(12, 3)),
    ev("Casey: Swimming carnival", timed(15, 9, 0, 300)),
    ev("Alex, Sam: Date night", timed(6, 18, 30, 180)),
    ev("Jamie: Science fair", timed(17, 13, 0, 120)),
    ev("Family: School holidays start", allday(20)),
    ev("Robin: Sleepover at Taylor's", allday(22)),
    ev("Bin night", timed(wk(0) - 7, 19, 0, 15), {rrule: "FREQ=WEEKLY"}),
    ev("Sam: Yoga", timed(-3, 6, 30, 60)),
    ev("Family: Beach day", allday(-6)),
  ];
  const google = [
    {id: "g1", title: "Sam: Work offsite", ...timed(8, 9, 0, 480), allday: false, rrule: ""},
    {id: "g2", title: "Alex: Flight to Melbourne", ...timed(11, 7, 15, 210), allday: false, rrule: ""},
  ];

  // ---- chores ----
  const chores = [["Make bed", 50], ["Feed the cat", 50], ["Unpack school bag", 100], ["Set the table", 50],
                  ["Empty dishwasher", 100], ["Take bins out", 150]];
  const kids = {};
  const todayIdx = (today.getDay() + 6) % 7;
  let seed = 7;
  const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
  for (const k of ["casey", "riley", "jamie", "robin"]) {
    const list = chores.map(([name, cents], i) => ({id: k + i, name, cents}));
    const ticks = {};
    let week = 0;
    for (const c of list) {
      const days = [];
      for (let d = 0; d <= todayIdx; d++) if (rnd() > 0.35) { const x = new Date(monday); x.setDate(x.getDate() + d); days.push(ymd(x)); }
      if (days.length) { ticks[c.id] = days; week += days.length * c.cents; }
    }
    kids[k] = {chores: list, ticks, balance: Math.round(rnd() * 8) * 50, week};
  }
  const kstate = {rev: 1, week: ymd(monday), today: ymd(today), kids, history: [], events,
                  google: {configured: true, ok_at: new Date().toISOString(), error: null, events: google}, settings: {}};

  // ---- HA entities ----
  const L = (s, name, bri) => ({s, a: {friendly_name: name, brightness: bri}});
  const states = {
    "light.living_room": L("on", "Living Room", 200), "light.dining_room": L("off", "Dining Room"),
    "light.kitchen": L("on", "Kitchen", 255), "light.kitchen_bench": L("off", "Kitchen Bench"),
    "light.study": L("off", "Study"), "light.main_bedroom": L("off", "Main Bedroom"),
    "light.robin_bedroom": L("on", "Robin's Room", 90), "light.jamie_bedroom": L("off", "Jamie's Room"),
    "light.riley_bedroom": L("off", "Riley's Room"), "light.casey_bedroom": L("off", "Casey's Room"),
    "light.porch": L("on", "Front Porch", 128), "light.deck_strip": L("off", "Deck Strip"),
    "climate.ac": {s: "cool", a: {friendly_name: "Air conditioner", temperature: 23, current_temperature: 25.4,
      hvac_modes: ["off", "cool", "heat", "fan_only"], min_temp: 16, max_temp: 30, target_temp_step: 1}},
    "cover.living_damper": {s: "open", a: {friendly_name: "Living Damper", current_position: 100}},
    "cover.main_damper": {s: "open", a: {friendly_name: "Main Damper", current_position: 70}},
    "cover.robin_damper": {s: "open", a: {friendly_name: "Robin Damper", current_position: 50}},
    "cover.jamie_damper": {s: "closed", a: {friendly_name: "Jamie Damper", current_position: 0}},
    "cover.riley_damper": {s: "open", a: {friendly_name: "Riley Damper", current_position: 40}},
    "cover.casey_damper": {s: "open", a: {friendly_name: "Casey Damper", current_position: 60}},
    "cover.garage_door": {s: "closed", a: {}},
    "weather.home": {s: "partlycloudy", a: {temperature: 24}},
    "sun.sun": {s: "above_horizon", a: {}},
  };
  const conds = ["sunny", "partlycloudy", "sunny", "rainy", "cloudy", "sunny"];
  const forecast = conds.map((c, i) => ({datetime: day(i).toISOString(), condition: c, temperature: 26 - i + (i % 2) * 2,
    templow: 14 + (i % 3), precipitation: c === "rainy" ? 6 : 0, precipitation_probability: c === "rainy" ? 70 : 5}));

  // ---- fake fetch for family_kiosk ----
  const realFetch = window.fetch.bind(window);
  window.fetch = (url, opts) => {
    const u = String(url);
    if (u.includes("/api/family_kiosk/state")) {
      if (u.includes("since=")) return new Promise(() => {}); // long-poll never returns in demo
      return Promise.resolve(new Response(JSON.stringify(kstate), {status: 200}));
    }
    if (u.includes("/api/family_kiosk/op")) {
      let op = {};
      try { op = JSON.parse(opts.body); } catch { /* keep {} */ }
      if (op.op === "tick") { // enough of the real logic for demos and tests
        const k = kstate.kids[op.kid], days = new Set(k.ticks[op.id] || []);
        op.on ? days.add(op.day) : days.delete(op.day);
        k.ticks[op.id] = [...days];
        const cents = Object.fromEntries(k.chores.map(c => [c.id, c.cents]));
        k.week = Object.entries(k.ticks).reduce((t, [id, ds]) => t + ds.length * cents[id], 0);
      }
      kstate.rev++;
      return Promise.resolve(new Response(JSON.stringify(kstate), {status: 200}));
    }
    if (u.includes("version.json")) return Promise.resolve(new Response('{"v":"demo"}'));
    return realFetch(url, opts);
  };

  // ---- fake HA websocket ----
  class FakeWS {
    constructor() { this.readyState = 0; setTimeout(() => { this.readyState = 1; this.onopen && this.onopen(); }, 20); }
    send(raw) {
      let m;
      try { m = JSON.parse(raw); } catch { return; }
      if (m.type === "call_service") (window.__calls ||= []).push(m); // read by tests/test_e2e.py
      const reply = r => setTimeout(() => this.onmessage && this.onmessage({data: JSON.stringify(r)}), 5);
      if (m.type === "auth") return reply({type: "auth_ok"});
      if (m.type === "get_states") return reply({id: m.id, type: "result", success: true,
        result: Object.entries(states).map(([entity_id, s]) => ({entity_id, state: s.s, attributes: s.a}))});
      if (m.type === "call_service" && m.service === "get_forecasts")
        return reply({id: m.id, type: "result", success: true, result: {response: {"weather.home": {forecast}}}});
      if (m.type === "subscribe_entities") {
        reply({id: m.id, type: "result", success: true});
        const a = Object.fromEntries(Object.entries(states).map(([k, s]) => [k, {s: s.s, a: s.a}]));
        return setTimeout(() => this.onmessage && this.onmessage({data: JSON.stringify({id: m.id, type: "event", event: {a}})}), 30);
      }
      reply({id: m.id, type: "result", success: true, result: {}});
    }
    close() {}
  }
  window.WebSocket = FakeWS;

  // ---- fake kiosk bridge (settings page) ----
  window.Kiosk = {
    call(id, action) {
      const R = {
        getSettings: {brightness: 170, sleepOn: true, sleepFrom: "22:00", sleepTo: "06:00", timezone: "Australia/Sydney", appVersion: "3.0"},
        deviceInfo: {"Model": "Wall calendar 15.6\"", "Android": "11", "App": "3.0", "Wi-Fi network": "HomeNetwork",
                     "Wi-Fi signal": "Good (-58 dBm)", "Serial": "0123456789abcdef", "Wi-Fi MAC": "02:00:00:00:00:01", "Uptime": "3 days"},
        wifiStatus: {ssid: "HomeNetwork", ip: "192.168.1.50"},
        wifiScan: [{ssid: "HomeNetwork", rssi: -50, band: "2.4 GHz", security: "wpa2"},
                   {ssid: "HomeNetwork-Guest", rssi: -62, band: "2.4 GHz", security: "wpa2"},
                   {ssid: "Neighbour", rssi: -80, band: "2.4 GHz", security: "wpa2"}],
      }[action] ?? {};
      setTimeout(() => window.__kioskCb(id, {ok: true, result: R}), 30);
    },
  };
})();

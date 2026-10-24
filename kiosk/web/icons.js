/* Inline SVG icon set (stroke icons, 24px grid). No external deps. */
(function (root) {
  const P = {
    calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    check: '<rect x="3" y="3" width="18" height="18" rx="5"/><path d="m8 12 3 3 5-6"/>',
    home: '<path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-5h4v5"/>',
    tick: '<path d="m5 12 5 5 9-10"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    wifi: '<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1" fill="currentColor"/>',
    pencil: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m14 6 4 4"/>',
    left: '<path d="m15 5-7 7 7 7"/>',
    right: '<path d="m9 5 7 7-7 7"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    minus: '<path d="M5 12h14"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z"/>',
    strip: '<rect x="2" y="9" width="20" height="6" rx="3"/><circle cx="7" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="17" cy="12" r="1"/>',
    garage: '<path d="M3 21V9l9-6 9 6v12"/><path d="M7 21v-9h10v9M7 15h10M7 18h10"/>',
    power: '<path d="M12 3v9"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>',
    snow: '<path d="M12 2v20M4 7l16 10M20 7 4 17"/>',
    flame: '<path d="M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-3 2-4 2-7 1.5 1 2.5 2 3-3z"/>',
    fan: '<circle cx="12" cy="12" r="2"/><path d="M12 10c0-4 1-7 4-7 2 0 2 3-1 5M14 12c4 0 7 1 7 4 0 2-3 2-5-1M12 14c0 4-1 7-4 7-2 0-2-3 1-5M10 12c-4 0-7-1-7-4 0-2 3-2 5 1"/>',
    drop: '<path d="M12 3s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11z"/>',
    auto: '<path d="M4 12a8 8 0 0 1 14-5l2-2v6h-6l2-2a5 5 0 1 0 1 5"/>',
    pin: '<path d="M12 21s7-6 7-12a7 7 0 0 0-14 0c0 6 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    google: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  };
  const W = {
    sun: '<circle cx="12" cy="12" r="4.5" fill="#ffc94d" stroke="#ffc94d"/><path stroke="#ffc94d" d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>',
    moon: '<path fill="#c9d4ff" stroke="#c9d4ff" d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
    cloud: '<path fill="#dfe6ee" stroke="#dfe6ee" d="M7 18h10a4 4 0 0 0 .5-8 5.5 5.5 0 0 0-10.6 1.5A3.3 3.3 0 0 0 7 18z"/>',
    partly: '<circle cx="8.5" cy="8.5" r="3.5" fill="#ffc94d" stroke="#ffc94d"/><path stroke="#ffc94d" d="M8.5 1.8v1.6M1.8 8.5h1.6M3.8 3.8l1.1 1.1M13.2 3.8l-1.1 1.1"/><path fill="#dfe6ee" stroke="#dfe6ee" d="M9 20h9a3.5 3.5 0 0 0 .4-7 5 5 0 0 0-9.6 1.4A2.9 2.9 0 0 0 9 20z"/>',
    rain: '<path fill="#dfe6ee" stroke="#dfe6ee" d="M7 15h10a4 4 0 0 0 .5-8 5.5 5.5 0 0 0-10.6 1.5A3.3 3.3 0 0 0 7 15z"/><path stroke="#6cb8ff" d="M8 18l-1 3M12 18l-1 3M16 18l-1 3"/>',
    storm: '<path fill="#c3ccd6" stroke="#c3ccd6" d="M7 14h10a4 4 0 0 0 .5-8 5.5 5.5 0 0 0-10.6 1.5A3.3 3.3 0 0 0 7 14z"/><path fill="#ffc94d" stroke="#ffc94d" d="m12 15-2 4h3l-1 3 3-5h-3l1-2z"/>',
    snow: '<path fill="#dfe6ee" stroke="#dfe6ee" d="M7 15h10a4 4 0 0 0 .5-8 5.5 5.5 0 0 0-10.6 1.5A3.3 3.3 0 0 0 7 15z"/><path stroke="#fff" d="M8 19h.01M12 21h.01M16 19h.01"/>',
    fog: '<path stroke="#dfe6ee" d="M4 9h16M3 13h18M5 17h14"/>',
    wind: '<path stroke="#dfe6ee" d="M3 9h11a3 3 0 1 0-3-3M3 15h15a3 3 0 1 1-3 3M3 12h8"/>',
  };
  const WMAP = {
    sunny: "sun", "clear-night": "moon", partlycloudy: "partly", cloudy: "cloud",
    rainy: "rain", pouring: "rain", "lightning-rainy": "storm", lightning: "storm",
    snowy: "snow", "snowy-rainy": "snow", hail: "snow", fog: "fog",
    windy: "wind", "windy-variant": "wind", exceptional: "storm",
  };
  // icon markup is constant (above), parsed as SVG XML into a DOM node
  const parser = new DOMParser();
  // parsing SVG is slow on the wall's CPU (~2ms each), so parse each icon once and clone it
  const cache = new Map();
  const svg = (body, cls) => {
    const key = cls + body;
    if (!cache.has(key)) cache.set(key, document.importNode(parser.parseFromString(
      `<svg xmlns="http://www.w3.org/2000/svg" class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`,
      "image/svg+xml").documentElement, true));
    return cache.get(key).cloneNode(true);
  };
  root.icon = name => svg(P[name] || P.star, "ic");
  root.wxIcon = cond => svg(W[WMAP[cond] || "cloud"], "wx");
  root.hydrateIcons = (scope = document) =>
    scope.querySelectorAll("[data-ic]").forEach(el => { if (!el.firstChild) el.appendChild(root.icon(el.dataset.ic)); });
})(window);

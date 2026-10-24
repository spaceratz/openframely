/* People tags in event titles. Shared by the kiosk and tests/tags.test.mjs.
   Formats (case-insensitive, combinable):
     "Riley, Casey: Swimming"   prefix list before a colon
     "Swimming [Riley Casey]"   bracket list
     "Swimming #riley #casey"   hashtags
   Aliases map spellings to member keys (config.example.js): Dad/Alex -> daddy,
   Sam/Mum -> sam, Robin -> robin, Jamie -> jamie, Riley -> riley, Casey -> casey.
   Per-install spellings come from KIOSK_CONFIG.aliases (config.js).
   Only recognised names are stripped; untagged events belong to everyone. */
(function (root) {
  const ALIASES = {
    daddy: "daddy", dad: "daddy", alex: "daddy",
    sam: "sam", mum: "sam", mummy: "sam", mom: "sam",
    robin: "robin", jamie: "jamie", riley: "riley", casey: "casey",
    // add your own spellings here, or per install in KIOSK_CONFIG.aliases
    family: "*", all: "*", everyone: "*",
  };
  if (root.KIOSK_CONFIG && root.KIOSK_CONFIG.aliases) {
    Object.assign(ALIASES, root.KIOSK_CONFIG.aliases);
  }

  // split "Riley, Casey & Mum" -> ["riley","casey","mum"]; null if any word isn't a person
  function names(list) {
    const words = list.toLowerCase().split(/\s*(?:,|&|\+|\/|\band\b|\s)\s*/).filter(Boolean);
    if (!words.length || !words.every(w => ALIASES[w])) return null;
    return words.map(w => ALIASES[w]);
  }

  function parseTags(title, allKeys) {
    let text = String(title || "");
    const found = [];
    text = text.replace(/(^|\s)#([a-z]+)\b/gi, (m, pre, w) => {
      const k = ALIASES[w.toLowerCase()];
      if (!k) return m;
      found.push(k);
      return pre;
    });
    text = text.replace(/\s*\[([^\]]*)\]\s*/g, (m, inner) => {
      const ks = names(inner);
      if (!ks) return m;
      found.push(...ks);
      return " ";
    });
    text = text.replace(/^\s*([^:]{1,60}?)\s*:\s*/, (m, inner) => {
      const ks = names(inner);
      if (!ks) return m;
      found.push(...ks);
      return "";
    });
    const keys = found.includes("*") || !found.length ? [...allKeys] : allKeys.filter(k => found.includes(k));
    return { title: text.replace(/\s{2,}/g, " ").trim() || String(title).trim(), members: keys, tagged: found.length > 0 };
  }

  root.parseTags = parseTags;
  if (typeof module !== "undefined") module.exports = { parseTags };
})(typeof window !== "undefined" ? window : globalThis);

/* Kiosk instance config: HA connection + members. Edit per install. */
window.KIOSK_CONFIG = {
  haUrl: "https://home.example.internal:8123",
  weather: "weather.home",
  nightFrom: 21, nightTo: 6, // extra-dim window (hours); sunset to sunrise is lightly dimmed
  members: [
    {key: "daddy",  name: "Alex",   color: "#ea6c2b"},
    {key: "sam",  name: "Sam",   color: "#2babea"},
    {key: "robin",   name: "Robin",     color: "#ead12b"},
    {key: "jamie",  name: "Jamie",   color: "#ea2b45"},
    {key: "riley", name: "Riley", color: "#7a5cff"},
    {key: "casey",   name: "Casey",     color: "#2bd48a"},
  ],
  lights: [
    "light.living_room", "light.dining_room", "light.kitchen", "light.kitchen_bench",
    "light.theatre", "light.master_bedroom", "light.casey", "light.riley",
    "light.jamie", "light.robin", "light.wled_casey", "light.wled_riley", "light.wled_jamie",
  ],
  // Master AC unit only: power + temperature. Zone "climates" aren't real ACs,
  // each room is a damper (cover) off the master unit.
  ac: "climate.ac",
  garage: "cover.garage_door",
  // name is optional: by default it's the HA friendly name minus "Damper"
  zones: [
    {name: "Living", cover: "cover.living_damper"},
    {name: "Master", cover: "cover.mstr_damper"},
    {name: "Riley",  cover: "cover.riley_damper"},
    {name: "Casey",  cover: "cover.casey_damper"},
    {name: "Robin",  cover: "cover.robin_damper"},
    {name: "Jamie",  cover: "cover.jamie_damper"},
  ],
  kids: [
    {key: "casey",   name: "Casey",   color: "#2bd48a"},
    {key: "riley", name: "Riley", color: "#7a5cff"},
    {key: "jamie",  name: "Jamie",  color: "#ea2b45"},
    {key: "robin",   name: "Robin",   color: "#ead12b"},
  ],
};

// Inspect the kiosk WebView on the board over Chrome DevTools (adb forward).
//   bun tools/board.mjs eval '<js expression>'
//   bun tools/board.mjs shot out.png
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";

const SERIAL = process.env.OPENFRAMELY_BOARD || "192.168.1.50:5555",
      PORT = Number(process.env.OPENFRAMELY_PORT || 9333);
const [cmd, arg] = process.argv.slice(2);

const unix = execFileSync("adb", ["-s", SERIAL, "shell", "cat", "/proc/net/unix"], { encoding: "utf8" });
const sock = unix.match(/@(webview_devtools_remote_\d+)/)[1];
execFileSync("adb", ["-s", SERIAL, "forward", `tcp:${PORT}`, `localabstract:${sock}`]);
const pages = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
const ws = new WebSocket(pages.find(p => p.type === "page").webSocketDebuggerUrl);

const call = (method, params) => new Promise(res => {
  ws.onmessage = e => {
    let m;
    try { m = JSON.parse(e.data); } catch { return; }
    if (m.id === 1) res(m.result ?? m);
  };
  ws.send(JSON.stringify({ id: 1, method, params }));
});
await new Promise(r => (ws.onopen = r));

if (cmd === "eval") {
  const r = await call("Runtime.evaluate", { expression: arg, returnByValue: true, awaitPromise: true });
  console.log(JSON.stringify(r.result?.value ?? r, null, 1));
} else if (cmd === "shot") {
  const r = await call("Page.captureScreenshot", { format: "png" });
  writeFileSync(arg, Buffer.from(r.data, "base64"));
  console.log("saved", arg);
}
ws.close();

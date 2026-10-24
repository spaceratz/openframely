"""Render README screenshots at 1920x1080 with made-up demo data.

Serves kiosk/web locally, swaps config.js for tools/demo/mock.js (fake Home
Assistant, kiosk bridge and household), so no real names, entities, network
or device details can end up in a screenshot. Output: kiosk/screenshots/.
  python3 tools/shots.py
"""

import functools
import http.server
import os
import pathlib
import threading

from playwright.sync_api import (
    sync_playwright,  # pyright: ignore[reportMissingImports]  (lives in the HA venv)
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB, OUT = ROOT / "web", ROOT / "screenshots"
MOCK = (ROOT / "tools/demo/mock.js").read_text()
CHROME = os.environ.get("OPENFRAMELY_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Cache-Control", "no-store")  # always test the files on disk
            super().end_headers()

        def log_message(self, format, *args):  # noqa: A002 (matches the base signature)
            pass

    handler = functools.partial(Quiet, directory=str(WEB))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    OUT.mkdir(exist_ok=True)
    srv = serve()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/config.js", lambda r: r.fulfill(content_type="text/javascript", body=MOCK))
        page.goto(f"http://127.0.0.1:{srv.server_port}/index.html")
        page.wait_for_timeout(2500)

        def shot(name, js=None, wait=900):
            if js:
                page.evaluate(js)
            page.wait_for_timeout(wait)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("saved", name)

        mode = "m => { document.querySelector(`#cal-mode button[data-mode=${m}]`).click(); }"
        shot("calendar-month", f"({mode})('month')")
        shot("calendar-week", f"({mode})('week')")
        shot("calendar-agenda", f"({mode})('schedule')")
        page.evaluate(f"({mode})('month')")
        shot("day-view", "showDay(ymd(new Date()))")
        shot("event-editor", "openEditor(null, currentDay)")
        shot("chores-view", "$('#ev-dialog').close(); switchView('chores')")
        shot("controls-view", "switchView('controls')")
        shot("settings-view", "openSettings()", 1500)
        print("page errors:", errors or "none")
        browser.close()
    srv.shutdown()


if __name__ == "__main__":
    main()

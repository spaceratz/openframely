"""Browser tests: the real kiosk page against the fake Home Assistant in tools/demo/mock.js.

Checks every view renders at the wall's 1920x1080 with no JS errors, nothing
spills off screen, no tile text is cut off, and the main interactions call the
right Home Assistant services.

  python -m pytest kiosk/tests/test_e2e.py -q     (needs playwright + Chrome/Chromium)
"""

import functools
import http.server
import json
import os
import pathlib
import threading

import pytest  # pyright: ignore[reportMissingImports]  (dev dependency, see requirements-dev.txt)

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
MOCK = (ROOT / "tools/demo/mock.js").read_text()
CHROME = os.environ.get("OPENFRAMELY_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

# elements anywhere in the active view that spill past the viewport, and
# single-line ellipsis / multi-line clamp text that's actually truncated
AUDIT = """(() => {
  const view = document.querySelector('.view.active');
  const off = [], cut = [];
  for (const e of view.querySelectorAll('*')) {
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height || e.closest('[hidden]')) continue;
    const scroller = e.closest('.slist, #ctl-zone-list, #ctl-light-grid, .scol, #wifi-list, .wday, .cgrid');
    if (!scroller && (r.right > innerWidth + 1 || r.bottom > innerHeight + 1)) off.push(e.className || e.tagName);
    const cs = getComputedStyle(e);
    const tile = e.closest('.lt, .zone, .garage, .ac, .ktab, .vhead');
    if (tile && cs.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1) cut.push(e.textContent.trim());
    if (cs.webkitLineClamp !== 'none' && cs.webkitLineClamp !== '') {
      const h = r.height;
      e.style.webkitLineClamp = 'unset'; e.style.display = 'block';
      const full = e.getBoundingClientRect().height;
      e.style.webkitLineClamp = ''; e.style.display = '';
      if (full > h + 2) cut.push(e.textContent.trim());
    }
  }
  return JSON.stringify({off: [...new Set(off)].slice(0, 10), cut});
})()"""


@pytest.fixture(scope="module")
def server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Cache-Control", "no-store")  # always test the files on disk
            super().end_headers()

        def log_message(self, format, *args):  # noqa: A002
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(WEB)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/index.html"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        kwargs = {"executable_path": CHROME} if CHROME and pathlib.Path(CHROME).exists() else {}
        b = p.chromium.launch(**kwargs)
        yield b
        b.close()


@pytest.fixture
def page(browser, server, request):
    # a fresh context per test: own cache and localStorage, so no test sees another's leftovers
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    pg = ctx.new_page()
    fake_clock = request.node.get_closest_marker("clock")
    if fake_clock:
        pg.clock.install()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/config.js", lambda r: r.fulfill(content_type="text/javascript", body=MOCK))
    pg.goto(server)
    # wait for HA states too, not just the first paint (tiles draw from config before HA answers)
    ready = (
        "document.querySelectorAll('.day .ev').length > 0 && states['cover.living_damper']"
        " && document.querySelector('.zone .nm').textContent === 'Living'"
    )
    if fake_clock:
        # the page's own timers (mock HA replies) only fire when the fake clock moves
        for _ in range(100):
            pg.clock.run_for(100)
            if pg.evaluate(ready):
                break
        assert pg.evaluate(ready), "page never finished loading under the fake clock"
    else:
        try:
            pg.wait_for_function(ready, timeout=15_000)
        except Exception:
            state = pg.evaluate("""JSON.stringify({scripts: performance.getEntriesByType('resource')
              .map(r => r.name.split('/').pop() + ':' + Math.round(r.duration) + 'ms:' + r.responseStatus),
              lib: typeof KioskLib, app: typeof renderCalendar})""")
            raise AssertionError(f"page not ready: {state} errors={errors}") from None
    yield pg
    assert errors == [], f"page errors: {errors}"
    ctx.close()


def audit(pg):
    pg.wait_for_timeout(600)
    return json.loads(pg.evaluate(AUDIT))


def calls(pg):
    js = "(window.__calls || []).map(c => [c.domain + '.' + c.service, c.target && c.target.entity_id, c.service_data])"
    return pg.evaluate(js)


@pytest.mark.parametrize("mode", ["month", "week", "schedule"])
def test_calendar_modes_fit(page, mode):
    page.click(f"#cal-mode button[data-mode={mode}]")
    assert page.is_visible({"month": "#cal-grid", "week": "#cal-week", "schedule": "#cal-schedule"}[mode])
    a = audit(page)
    assert a["off"] == [], a


@pytest.mark.parametrize("view", ["chores", "controls", "settings"])
def test_views_fit_without_clipping(page, view):
    page.evaluate("openSettings()" if view == "settings" else f"switchView('{view}')")
    a = audit(page)
    assert a == {"off": [], "cut": []}, a


def test_month_arrows_and_today(page):
    title = page.text_content("#cal-title")
    page.click("#cal-next")
    assert page.text_content("#cal-title") != title
    page.click("#cal-today")
    assert page.text_content("#cal-title") == title


def test_week_title_has_start_and_end(page):
    page.click("#cal-mode button[data-mode=week]")
    assert " to " in page.text_content("#cal-title")
    assert page.locator(".wday").count() == 7


def test_agenda_back_disabled_on_today(page):
    page.click("#cal-mode button[data-mode=schedule]")
    assert page.is_disabled("#cal-prev")
    page.click("#cal-next")
    assert page.is_enabled("#cal-prev")
    assert page.text_content("#cal-title").startswith("From ")


def test_member_filter_hides_events(page):
    before = page.locator(".day .ev").count()
    for chip in page.locator("#member-filter .mchip").all()[1:]:
        chip.click()  # leave only the first person
    assert page.locator(".day .ev").count() < before


def test_shared_event_bar_blends_each_persons_colour(page):
    # "Alex, Sam: Date night": the left bar runs Alex's colour into Sam's; a one-person event stays solid
    chip = page.locator(".day .ev.multi", has_text="Date night").first
    bar = chip.evaluate("e => e.style.getPropertyValue('--bar')")
    colours = page.evaluate("['alex','sam'].map(k => member(k).color)")
    assert bar == f"linear-gradient(180deg, {colours[0]} 0%, {colours[1]} 100%)"
    assert "linear-gradient" in chip.evaluate("e => getComputedStyle(e).backgroundImage")
    # one-person and whole-family events keep a solid bar
    assert page.locator(".day .ev:not(.multi)").count() > 0
    for e in page.locator(".day .ev:not(.multi)").all()[:5]:
        assert e.evaluate("e => e.style.getPropertyValue('--bar')") == ""


def test_light_tap_calls_toggle(page):
    page.evaluate("switchView('controls')")
    page.locator(".lt:not(.on)").first.click()
    assert any(c[0] == "light.turn_on" for c in calls(page))


def test_all_lights_off_targets_only_lights_that_are_on(page):
    page.evaluate("switchView('controls')")
    page.click("#all-off")
    off = [c for c in calls(page) if c[0] == "light.turn_off"]
    assert len(off) == 1 and len(off[0][1]) == 4  # demo has 4 lights on


def test_garage_shows_opening_immediately(page):
    page.evaluate("switchView('controls')")
    page.click(".garage")
    assert page.text_content(".garage .cur") == "Opening..."
    assert ["cover.open_cover", "cover.garage_door", {}] in calls(page)


def test_zone_damper_dialog_sets_position(page):
    page.evaluate("switchView('controls')")
    page.locator(".zone .zslider").first.click()
    page.fill("#zone-pos", "30")
    page.click("#zone-save")
    assert ["cover.set_cover_position", "cover.living_damper", {"position": 30}] in calls(page)


def test_ac_mode_and_temperature(page):
    page.evaluate("switchView('controls')")
    page.click(".ac-modes .m-heat")
    page.click(".ac [aria-label=Warmer]")
    got = calls(page)
    assert ["climate.set_hvac_mode", "climate.ac", {"hvac_mode": "heat"}] in got
    assert ["climate.set_temperature", "climate.ac", {"temperature": 24}] in got


def test_chores_have_no_pay_or_edit_on_wall(page):
    page.evaluate("switchView('chores')")
    assert page.locator("#chore-edit, .cfoot .pill, .cadd").count() == 0
    assert page.locator(".ktab").count() == 4


def test_settings_device_card_and_default_view(page):
    page.evaluate("openSettings()")
    page.wait_for_selector("#device-info .srow")
    assert "HomeNetwork" in page.text_content("#device-info")
    page.select_option("#set-default-view", "week")
    assert page.evaluate("localStorage.getItem('kiosk_cal_mode')") == "week"


@pytest.mark.clock
def test_idle_returns_to_calendar(page):
    page.evaluate("switchView('controls')")
    page.mouse.click(5, 1075)  # a tap starts the idle timer
    page.clock.fast_forward(181_000)
    assert page.evaluate("currentView") == "calendar"


@pytest.mark.clock
def test_idle_closes_dialogs_and_uses_default_view(page):
    page.evaluate("localStorage.setItem('kiosk_cal_mode', 'week')")
    page.evaluate("showDay(ymd(new Date())); openEditor(null, currentDay)")
    assert page.is_visible("#ev-dialog")
    page.mouse.click(960, 5)
    page.clock.fast_forward(181_000)
    assert page.evaluate("document.querySelectorAll('dialog[open]').length") == 0
    assert page.evaluate("currentView") == "calendar"
    assert page.is_visible("#cal-week")


@pytest.mark.clock
def test_offline_banner_after_20s_without_ha(page):
    assert page.is_hidden("#offline-banner")
    page.evaluate("setLink('ws', false)")
    page.clock.fast_forward(10_000)
    assert page.is_hidden("#offline-banner")
    page.clock.fast_forward(15_000)
    assert page.is_visible("#offline-banner")
    page.evaluate("setLink('ws', true)")
    page.clock.fast_forward(3_000)
    assert page.is_hidden("#offline-banner")


def test_kid_tabs_show_todays_progress(page):
    page.evaluate("switchView('chores')")
    text = page.text_content(".ktab.on")
    assert "today" in text and "/6" in text
    assert page.locator(".ktab .ring").count() == 4


def test_celebration_when_last_chore_of_today_is_ticked(page):
    page.evaluate("switchView('chores')")
    open_today = page.locator(".cbox.today:not(.on)")
    assert open_today.count() > 0
    while open_today.count():
        open_today.first.click()
        page.wait_for_timeout(80)  # each tick re-renders the sheet
    page.wait_for_selector(".confetti", timeout=2000)
    assert "finished every chore" in page.text_content("#toast")
    assert "6/6 today" in page.text_content(".ktab.on")


def test_24_hour_setting_changes_clock_and_events(page):
    assert page.text_content("#clock-ap") in ("am", "pm")
    page.evaluate("openSettings()")
    page.select_option("#set-clock", "24")
    assert page.text_content("#clock-ap") == ""
    assert page.evaluate("localStorage.getItem('kiosk_h24')") == "1"
    page.evaluate("switchView('calendar')")
    page.click("#cal-mode button[data-mode=month]")
    times = page.locator(".day .ev .t").all_text_contents()
    assert times and all(":" in t and "am" not in t and "pm" not in t for t in times), times
    page.reload()  # survives a reload
    page.wait_for_function("document.querySelectorAll('.day .ev').length > 0")
    assert page.text_content("#clock-ap") == ""
    assert page.input_value("#set-clock") == "24"


def test_quick_double_tap_on_a_light_turns_it_back_off(page):
    """Regression: the tile used its drawn state, so two quick taps sent turn_off twice."""
    page.evaluate("switchView('controls')")
    name = page.locator(".lt:not(.on) .nm").first.text_content()
    tile = page.locator(".lt", has_text=name)  # re-found each time: HA updates redraw the grid
    tile.click()
    page.evaluate("onStateDelta({c: {'light.dining_room': {'+': {s: 'off'}}}})")  # HA echo arrives between taps
    tile.click()
    got = [c[0] for c in calls(page) if c[0].startswith("light.")]
    assert got == ["light.turn_on", "light.turn_off"], got
    assert "on" not in (tile.get_attribute("class") or "").split()


def test_quick_double_tap_on_a_chore_unticks(page):
    page.evaluate("switchView('chores')")
    box = page.locator(".cbox.today:not(.on)").first
    box.click()
    box = page.locator(".cbox.today").first  # the sheet redraws after each save
    page.wait_for_timeout(150)
    before = "on" in box.get_attribute("class").split()
    box.click()
    page.wait_for_timeout(150)
    assert ("on" in page.locator(".cbox.today").first.get_attribute("class").split()) != before


def test_hidden_screens_are_not_redrawn_on_every_update(page):
    page.evaluate("switchView('controls')")
    page.evaluate("""() => {
      const original = RENDER.chores;
      window.__n = 0;
      RENDER.chores = () => { window.__n++; original(); };
    }""")
    page.evaluate("applyKstate({...kstate, rev: kstate.rev + 1})")
    assert page.evaluate("window.__n") == 0, "chores redrew while hidden"
    page.evaluate("switchView('chores')")
    assert page.evaluate("window.__n") == 1, "chores didn't redraw when opened"


@pytest.mark.parametrize("view", ["calendar", "day", "chores", "controls", "settings"])
def test_only_one_screen_is_ever_visible(page, view):
    """Regression: a stray display rule left the calendar showing behind Home."""
    page.evaluate(f"switchView('{view}')")
    shown = page.evaluate("[...document.querySelectorAll('.view')].filter(v => getComputedStyle(v).display !== 'none').map(v => v.id)")
    assert shown == [f"view-{view}"], shown


def test_zone_names_come_from_home_assistant(page):
    page.evaluate("switchView('controls')")
    assert page.locator(".zone .nm").all_text_contents() == ["Living", "Main bed", "Robin", "Jamie", "Riley", "Casey"]


def test_nav_switches_on_touch_down_and_calendar_tap_returns_to_this_month(page):
    page.dispatch_event("#nav button[data-view=chores]", "pointerdown")
    assert page.evaluate("currentView") == "chores", "should switch before the finger lifts"
    page.click("#nav button[data-view=calendar]")
    this_month = page.text_content("#cal-title")
    page.click("#cal-next")
    assert page.text_content("#cal-title") != this_month
    page.click("#nav button[data-view=calendar]")  # already on Calendar: back to this month
    assert page.text_content("#cal-title") == this_month

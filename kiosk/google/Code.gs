/**
 * Family calendar feed for the wall kiosk (read-only, one way: Google -> wall).
 *
 * Deploy (logged in as the family Google account):
 *   1. script.google.com -> New project -> paste this file as Code.gs
 *   2. Pick "setup" in the function dropdown, Run, authorise, copy the KEY from the log
 *   3. Deploy -> New deployment -> Web app
 *        Execute as: Me    Who has access: Anyone
 *   4. Authorise, copy the /exec URL. Kiosk feed URL = <exec URL>?key=<KEY>
 *
 * Returns {updated, events:[{id, title, start, end, allDay, calendar}]}
 * for every calendar the account has ticked (or CALENDARS property, comma
 * separated ids), from 35 days ago to 120 days ahead. Recurring events are
 * expanded by CalendarApp, so each occurrence is its own row.
 */
/** Run once from the editor: creates the secret KEY and prints it. */
function setup() {
  var props = PropertiesService.getScriptProperties();
  var key = props.getProperty('KEY');
  if (!key) {
    key = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
    props.setProperty('KEY', key);
  }
  CalendarApp.getAllCalendars(); // triggers the calendar permission prompt now
  Logger.log('KEY=' + key);
}

function doGet(e) {
  var props = PropertiesService.getScriptProperties();
  var key = props.getProperty('KEY');
  if (!key || !e || !e.parameter || e.parameter.key !== key) {
    return json({error: 'forbidden'});
  }
  var cache = CacheService.getScriptCache();
  var hit = cache.get('feed');
  if (hit) return ContentService.createTextOutput(hit).setMimeType(ContentService.MimeType.JSON);

  var ids = (props.getProperty('CALENDARS') || '').split(',').filter(String);
  var cals = ids.length
    ? ids.map(function (id) { return CalendarApp.getCalendarById(id.trim()); }).filter(Boolean)
    : CalendarApp.getAllCalendars().filter(function (c) { return c.isSelected() && !c.isHidden(); });

  var now = new Date();
  var from = new Date(now.getTime() - 35 * 864e5);
  var to = new Date(now.getTime() + 120 * 864e5);
  var out = [];
  cals.forEach(function (cal) {
    cal.getEvents(from, to).forEach(function (ev) {
      var allDay = ev.isAllDayEvent();
      out.push({
        id: ev.getId() + '@' + ev.getStartTime().getTime(),
        title: ev.getTitle(),
        start: allDay ? ymd(ev.getAllDayStartDate(), cal) : ev.getStartTime().toISOString(),
        end: allDay ? ymd(ev.getAllDayEndDate(), cal) : ev.getEndTime().toISOString(),
        allDay: allDay,
        location: ev.getLocation() || '',
        calendar: cal.getName()
      });
    });
  });
  var body = JSON.stringify({updated: now.toISOString(), events: out});
  // short cache so a burst of polls is cheap but edits still land in <20s
  try { cache.put('feed', body, 10); } catch (err) { /* >100KB, skip cache */ }
  return ContentService.createTextOutput(body).setMimeType(ContentService.MimeType.JSON);
}

function ymd(d, cal) {
  return Utilities.formatDate(d, cal.getTimeZone(), 'yyyy-MM-dd');
}

function json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

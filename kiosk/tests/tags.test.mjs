// bun test tests/   (or: bun run test)
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const { parseTags } = createRequire(import.meta.url)("../web/tags.js");
const ALL = ["daddy", "sam", "robin", "jamie", "riley", "casey"];
const p = t => parseTags(t, ALL);

test("prefix", () => {
  assert.deepEqual(p("Riley, Casey: Swimming"), { title: "Swimming", members: ["riley", "casey"], tagged: true });
  assert.deepEqual(p("Mum & Dad: Date night").members, ["daddy", "sam"]);
  assert.equal(p("Robin and Jamie: Dentist").title, "Dentist");
});

test("bracket", () => {
  assert.deepEqual(p("Swimming [Riley Casey]"), { title: "Swimming", members: ["riley", "casey"], tagged: true });
  assert.equal(p("Swimming [Riley, Casey] lessons").title, "Swimming lessons");
});

test("hashtags", () => {
  assert.deepEqual(p("Swimming #riley #casey"), { title: "Swimming", members: ["riley", "casey"], tagged: true });
  assert.deepEqual(p("#Jamie footy").members, ["jamie"]);
});

test("aliases are case-insensitive", () => {
  assert.deepEqual(p("ALEX: Gym").members, ["daddy"]);
  assert.deepEqual(p("Groceries #MUM").members, ["sam"]);
  assert.deepEqual(p("Family: BBQ at Nan's"), { title: "BBQ at Nan's", members: ALL, tagged: true });
  assert.deepEqual(p("Holiday [all]").members, ALL);
});

test("untagged = whole family, title untouched", () => {
  assert.deepEqual(p("School photos"), { title: "School photos", members: ALL, tagged: false });
});

test("non-name prefixes and brackets are left alone", () => {
  assert.deepEqual(p("Note: bins out"), { title: "Note: bins out", members: ALL, tagged: false });
  assert.equal(p("Meeting [Zoom]").title, "Meeting [Zoom]");
  assert.equal(p("Casey's party").title, "Casey's party");
  assert.equal(p("Call #42 office").title, "Call #42 office");
});

test("formats combine", () => {
  assert.deepEqual(p("Casey: Swimming #robin").members, ["robin", "casey"]);
});

test("tag-only title keeps original text", () => {
  assert.equal(p("#casey").title, "#casey");
});

test("Everyone: applies to all people, any case or spacing", () => {
  for (const t of ["Everyone: BBQ", "everyone:BBQ", "EVERYONE : BBQ", "BBQ [everyone]", "BBQ #everyone"]) {
    assert.deepEqual(p(t), { title: "BBQ", members: ALL, tagged: true }, t);
  }
});

test("Everyone mixed with a name still means everyone", () => {
  assert.deepEqual(p("Everyone, Riley: BBQ").members, ALL);
});

test("Everyone only counts as a tag before a colon", () => {
  assert.deepEqual(p("Everyone loves BBQ"), { title: "Everyone loves BBQ", members: ALL, tagged: false });
});

test("Everyone: covers every adult and every kid in the household config", async () => {
  const fs = await import("node:fs");
  globalThis.window = globalThis;
  new Function(fs.readFileSync(new URL("../tools/demo/mock.js", import.meta.url), "utf8").split("// ---- calendar ----")[0] + "})();")();
  const cfg = globalThis.KIOSK_CONFIG;
  const keys = cfg.members.map(m => m.key);
  const r = parseTags("Everyone: Beach day", keys);
  assert.equal(r.title, "Beach day");
  assert.deepEqual(r.members, keys);
  for (const kid of cfg.kids) assert.ok(r.members.includes(kid.key), kid.name);
  delete globalThis.KIOSK_CONFIG;
});

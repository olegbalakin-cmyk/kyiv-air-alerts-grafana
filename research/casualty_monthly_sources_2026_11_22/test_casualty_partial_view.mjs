import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { partialCasualtyPresentation } from "./casualty_partial_view.mjs";

const dir = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(dir, "october_2026_partial_preview.json"), "utf8"));

assert.equal(data.cities.length, 23);
assert.equal(data.confirmed_event_groups, 4);
assert.equal(data.known_civilian_fatalities_from_these_events, 11);
assert.equal(data.promotion, "OFF");
assert.equal(data.display_policy, "PREVIEW_ONLY_NO_SITE_MUTATION");
const values = { lutsk: 6, poltava: 1, "ivano-frankivsk": 1, khmelnytskyi: 3 };
for (const [city, count] of Object.entries(values)) {
  const uk = partialCasualtyPresentation(data, city, "uk");
  const en = partialCasualtyPresentation(data, city, "en");
  assert.equal(uk.lower_bound, count);
  assert.equal(uk.chart_value, count);
  assert.equal(uk.exact_deaths, null);
  assert.equal(uk.annual_exact_addition, null);
  assert.match(uk.label, /щонайменше/);
  assert.match(en.label, /at least/);
  assert.equal(en.lower_bound, count);
  assert.equal(uk.is_partial, true);
  assert.equal(uk.unknown, false);
}
for (const row of data.cities) {
  if (Object.hasOwn(values, row.city_slug)) continue;
  const uk = partialCasualtyPresentation(data, row.city_slug);
  assert.equal(uk.lower_bound, null);
  assert.equal(uk.chart_value, null);
  assert.equal(uk.exact_deaths, null);
  assert.equal(uk.annual_exact_addition, null);
  assert.equal(uk.unknown, true);
  assert.match(uk.label, /дані уточнюються/);
}
assert.equal(data.cities.filter(x => x.confirmed_event_lower_bound === null).length, 19);
assert.equal(data.cities.filter(x => x.monthly_exact_total !== null).length, 0);
assert.throws(() => partialCasualtyPresentation(data, "unknown-city"));
assert.throws(() => partialCasualtyPresentation({ ...data, promotion: "ON" }, "lutsk"));
assert.throws(() => partialCasualtyPresentation({
  ...data, cities: data.cities.map(x =>
    x.city_slug === "kyiv" ? { ...x, confirmed_event_lower_bound: 0 } : x)
}, "kyiv"));
assert.throws(() => partialCasualtyPresentation({
  ...data, cities: data.cities.map(x =>
    x.city_slug === "lutsk" ? { ...x, monthly_exact_total: 6 } : x)
}, "lutsk"));
assert.throws(() => partialCasualtyPresentation({ ...data, is_month_complete: true }, "lutsk"));
console.log("CASUALTY_PARTIAL_BILINGUAL_VIEW_PASS 23_CITIES 4_LOWER_BOUNDS 19_UNKNOWN NO_YEAR_EXACT SUM_11");

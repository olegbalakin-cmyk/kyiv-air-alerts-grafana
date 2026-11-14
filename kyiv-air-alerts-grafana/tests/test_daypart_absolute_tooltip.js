// Regression guard for daypart hover duration: absolute source minutes, not percent estimates.
// Tests inspect only the isolated browser-code fragment, with no network calls.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/app.js", "utf8");
const start = source.indexOf("function daypartBreakdown(rows, mode) {");
const end = source.indexOf("\nfunction renderDaypart(key) {", start);
assert(start >= 0 && end > start, "daypartBreakdown must exist");
const sandbox = { TIME_PROFILE_COLORS: ["#000", "#111", "#222", "#333", "#444"], tr: (uk) => uk };
vm.createContext(sandbox);
vm.runInContext(source.slice(start, end), sandbox);
const rows = [{
  time_band_shares: { "00_06": 24.5, "06_12": 0, "12_18": 75.5, "18_24": 0 },
  time_band_minutes: { "00_06": 2180, "06_12": 0, "12_18": 6710, "18_24": null },
  time_day_night_shares: { day: 70, evening_night: 30 },
  time_day_night_minutes: { day: 6223, evening_night: 2667 }
}];
let bands = sandbox.daypartBreakdown(rows, "four");
assert.equal(bands.length, 4);
assert.equal(bands[0].data[0], 24.5);
assert.equal(bands[0].durationMinutes[0], 2180);
assert.equal(bands[1].durationMinutes[0], 0);
assert.equal(bands[2].durationMinutes[0], 6710);
assert.equal(bands[3].durationMinutes[0], null);
bands = sandbox.daypartBreakdown(rows, "daynight");
assert.equal(bands.length, 2);
assert.equal(bands[0].durationMinutes[0], 6223);
assert.equal(bands[1].durationMinutes[0], 2667);
assert.equal(bands[0].data[0], 70);
const missing = sandbox.daypartBreakdown([{time_band_shares: {"00_06":10},time_band_minutes:{"00_06": "garbage"}}], "four");
assert.equal(missing[0].durationMinutes[0], null);
assert.equal(missing[1].durationMinutes[0], null);
const chartsStart = source.indexOf('state.charts.daypartChart = new Chart(');
const chartsEnd = source.indexOf('\nfunction renderTimeOfDay(key) {',chartsStart);
const chartPart = source.slice(chartsStart,chartsEnd);
assert(chartPart.includes('durationMinutes: band.durationMinutes'));
assert(chartPart.includes('context.dataset.durationMinutes?.[context.dataIndex]'));
assert(chartPart.includes('formatDurationMinutes(minutes)'));
assert(chartPart.includes('fmt(context.parsed.y,1)}%'));
assert(!chartPart.includes('context.parsed.y *'),"must not reconstruct time from percent");
console.log("PASS daypart absolute tooltip: four/two bands, exact minutes, zero, missing, invalid, and UI wiring");

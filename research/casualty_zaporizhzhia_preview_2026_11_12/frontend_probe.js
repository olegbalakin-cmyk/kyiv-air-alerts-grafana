#!/usr/bin/env node
"use strict";
/*
 * Isolated exact-function frontend probe: invoke pinned renderCasualties()
 * and its three dependency functions in a controlled fake DOM, without
 * changing app.js or accessing the site's production URL.
 */
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const script = fs.readFileSync(process.argv[3], "utf8");

function extractFunction(name) {
  const needle = "function " + name + "(";
  const start = script.indexOf(needle);
  assert(start >= 0, "Pinned app.js missing " + name);
  const brace = script.indexOf("{", start + needle.length);
  let depth = 0, end = brace;
  for (; end < script.length; end++) {
    if (script[end] === "{") depth++;
    else if (script[end] === "}" && --depth === 0) {
      end++;
      break;
    }
  }
  assert(depth === 0);
  return script.slice(start, end);
}

const ids = {};
function element(id) {
  return ids[id] ||= {
    dataset: {}, value: "", innerHTML: "", textContent: "",
    classList: { add() {}, remove() {} },
  };
}
element("casualtyInterval").value = "monthly";
element("casualtyYear").value = "all";
const charts = [];
const ctx = {
  state: { data, charts: {} },
  $: element,
  labelFor: () => "Запоріжжя",
  tr: uk => uk,
  setChart: (...args) => charts.push(args),
  assert,
  console,
};
vm.createContext(ctx);
const funcs = [
  "syncCasualtyYearOptions", "casualtyRowsForYear",
  "aggregateCasualtiesByYear", "renderCasualties",
];
vm.runInContext(funcs.map(extractFunction).join("\n"), ctx);
vm.runInContext('renderCasualties("zaporizhzhia")', ctx);
assert(charts.length === 1);
const chart = charts[0];
const labels = chart[1], values = chart[2][0].data;
const idx = labels.indexOf("2026-10");
assert(idx >= 0, "October must appear in the monthly chart");
assert.strictEqual(values[idx], 23);
assert.strictEqual(element("casualtySourceNote").textContent.includes("339 загиблих"), true);
const sorted = [...labels].sort();
assert.strictEqual(JSON.stringify(labels), JSON.stringify(sorted), "All month labels must be chronological");
element("casualtyInterval").value = "yearly";
vm.runInContext('renderCasualties("zaporizhzhia")', ctx);
assert(charts.length === 2);
const annual = charts[1], yearLabels = annual[1], yearValues = annual[2][0].data;
const yearIndex = yearLabels.indexOf("2026");
assert(yearIndex >= 0 && yearValues[yearIndex] >= 23);
const originalRows = data.casualties_by_city.zaporizhzhia.monthly;
const expectedYear = originalRows.filter(r => r.month.startsWith("2026-"))
    .reduce((s, r) => s + Number(r.deaths), 0);
assert.strictEqual(yearValues[yearIndex], expectedYear);
console.log(JSON.stringify({
  pinned_function: "renderCasualties",
  monthly_october: values[idx],
  monthly_labels_sorted: true,
  visible_total: 339,
  yearly_2026: yearValues[yearIndex],
  verdict: "FUNCTION_PROBE_PASS",
  limitation: "Node vm and fake DOM, not full browser rendering"
}, null, 2));

/* Local-only intercepted fixture. Load between app.js and coverage-preview.js. */
(function (root) {
  "use strict";
  const params = new URLSearchParams(root.location.search);
  if (!["localhost","127.0.0.1","[::1]"].includes(root.location.hostname) ||
      params.get("coverage_fixture") !== "1") {
    throw new Error("Fixture may be loaded only on localhost with coverage_fixture=1");
  }
  const originalFetch = root.fetch.bind(root);
  root.fetch = async function (input, init) {
    const url = String(typeof input === "string" ? input : input.url);
    const response = await originalFetch(input, init);
    if (!/\/dashboard_data\.json(?:\?|$)/.test(url)) return response;
    if (!response.ok) return response;
    const json = await response.json();
    const series = json.casualties_by_city && json.casualties_by_city.zaporizhzhia;
    if (!series || !Array.isArray(series.monthly)) {
      throw new Error("No Zaporizhzhia casualty series in actual source snapshot");
    }
    const originalRows = series.monthly;
    const existing = originalRows.findIndex(function (item) {
      return String(item.month || item.time || "").slice(0,7) === "2026-10";
    });
    const row = Object.assign({}, existing < 0 ? {month:"2026-10"} : originalRows[existing], {
      month:"2026-10", deaths:null, coverage_status:"INCOMPLETE",
      confirmed_minimum:23, complete_total:null
    });
    if (existing < 0) originalRows.push(row);
    else originalRows[existing] = row;
    originalRows.sort(function (a,b) {return String(a.month).localeCompare(String(b.month));});
    // All alert city records, auxiliary fields and other casualty cities are preserved.
    root.__coverageFixtureLoaded = true;
    return new Response(JSON.stringify(json), { status:200, headers:{"Content-Type":"application/json"} });
  };
})(window);

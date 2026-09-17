const state = { data: null, charts: {} };

const COLORS = ["#62a0ea", "#8ff0a4", "#f8e45c"];
const GRID = "rgba(148,163,184,.16)";
const TEXT = "#b8c4cf";

function $(id) { return document.getElementById(id); }
function fmt(v, digits = 1) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(digits);
}
function labelFor(key) {
  const mm = state.data.multicity_meta?.cities?.[key];
  return mm?.label || state.data.cities?.[key]?.meta?.city_label || key;
}
function cityKeys() {
  return state.data.multicity_meta?.production_city_keys || Object.keys(state.data.cities || {});
}
function sourceType(key) {
  return state.data.multicity_meta?.cities?.[key]?.source_type || state.data.cities?.[key]?.meta?.source_type || "unknown";
}
function coverageStart(key) {
  return state.data.multicity_meta?.cities?.[key]?.coverage_start || state.data.cities?.[key]?.meta?.coverage_start || state.data.cities?.[key]?.meta?.first_city_level_date || null;
}
function proxyRaion(key) {
  return state.data.multicity_meta?.cities?.[key]?.proxy_raion || state.data.cities?.[key]?.meta?.proxy_raion || null;
}
function typeText(key) { return sourceType(key) === "raion_proxy" ? "Районний proxy" : "Exact-city"; }

function fillSelect(select, keys, current, allowEmpty = false) {
  select.innerHTML = "";
  if (allowEmpty) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "— не обирати —";
    empty.selected = current === "";
    select.appendChild(empty);
  }
  for (const key of keys) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = labelFor(key);
    opt.selected = key === current;
    select.appendChild(opt);
  }
}

function chartOptions(yTitle, extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
      tooltip: { mode: "index", intersect: false }
    },
    scales: {
      x: { ticks: { color: TEXT, maxRotation: 0, autoSkip: true }, grid: { color: GRID } },
      y: { beginAtZero: true, ticks: { color: TEXT }, grid: { color: GRID }, title: { display: true, text: yTitle, color: TEXT } }
    },
    ...extra
  };
}

function setChart(id, labels, datasets, yTitle, type = "line", extra = {}) {
  if (state.charts[id]) state.charts[id].destroy();
  state.charts[id] = new Chart($(id), {
    type,
    data: { labels, datasets },
    options: chartOptions(yTitle, extra)
  });
}

function seriesDataset(label, values, color, dashed = false) {
  return {
    label,
    data: values,
    borderColor: color,
    backgroundColor: color + "22",
    pointRadius: 2,
    pointHoverRadius: 4,
    borderWidth: 2,
    borderDash: dashed ? [7, 5] : [],
    tension: 0.12,
    spanGaps: true
  };
}

function rowTime(row, period) {
  if (period === "monthly") return row.month || String(row.time || "").slice(0, 7);
  return row.week_start || String(row.time || "").slice(0, 10);
}

function getParams() {
  return new URLSearchParams(location.search);
}
function validParam(name, values, fallback) {
  const value = getParams().get(name);
  return values.includes(value) ? value : fallback;
}
function validOptionalParam(name, values, fallback) {
  const value = getParams().get(name);
  if (value === "none") return "";
  return values.includes(value) ? value : fallback;
}
function updateUrl() {
  const params = new URLSearchParams();
  params.set("city", $("citySelect").value);
  params.set("period", $("cityPeriod").value);
  params.set("a", $("compareA").value);
  params.set("b", $("compareB").value);
  params.set("c", $("compareC").value || "none");
  params.set("compare", $("comparePeriod").value);
  history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
}

function renderFreshness() {
  const banner = $("freshnessBanner");
  const fresh = state.data.multicity_meta?.effective_freshness || state.data.multicity_meta?.upstream_freshness;
  if (!fresh?.warning) {
    banner.classList.add("hidden");
    return;
  }
  const last = fresh.latest_proxy_event_end || fresh.last_successful_fetch_at;
  banner.textContent = `⚠ Дані біля правого краю можуть бути неповними. Останній підтверджений update: ${last ? String(last).slice(0, 10) : "невідомо"}. Нулі після цієї точки не слід трактувати як гарантовану відсутність тривог.`;
  banner.classList.remove("hidden");
}

function renderDatasetSummary() {
  const keys = cityKeys();
  const exact = keys.filter(k => sourceType(k) === "exact_city").length;
  const proxy = keys.filter(k => sourceType(k) === "raion_proxy").length;
  $("datasetSummary").innerHTML = [
    `${keys.length} ряди`,
    `${exact} exact-city`,
    `${proxy} районних proxy`,
    "Донецьк і Луганськ поки не включені"
  ].map(x => `<span class="summary-pill">${x}</span>`).join("");
}

function renderCity() {
  const key = $("citySelect").value;
  const period = $("cityPeriod").value;
  const city = state.data.cities[key];
  if (!city) return;

  $("cityTitle").textContent = labelFor(key);
  const type = sourceType(key);
  const coverage = coverageStart(key);
  const badgeClass = type === "raion_proxy" ? "proxy" : "exact";
  const raion = proxyRaion(key);
  $("cityMeta").innerHTML = [
    `<span class="badge ${badgeClass}">${typeText(key)}</span>`,
    coverage ? `<span class="badge">Покриття з ${coverage}</span>` : "",
    raion ? `<span class="badge">${raion}</span>` : ""
  ].join("");

  const kpi = city.kpis?.[0] || {};
  $("kpiAlerts").textContent = fmt(kpi.alerts_28d, 0);
  $("kpiHours").textContent = `${fmt(kpi.alert_hours_28d, 1)} год`;
  $("kpiDuration").textContent = `${fmt(kpi.avg_alert_duration_min_28d, 1)} хв`;
  $("kpiMaxDay").textContent = fmt(kpi.max_alerts_day, 0);
  $("kpiMaxDayDate").textContent = kpi.max_alerts_day_date || "";

  const rows = city[period] || [];
  const labels = rows.map(r => rowTime(r, period));
  const dashed = type === "raion_proxy";

  if (state.charts.cityIntensityChart) state.charts.cityIntensityChart.destroy();
  state.charts.cityIntensityChart = new Chart($("cityIntensityChart"), {
    data: {
      labels,
      datasets: [
        {
          type: "bar",
          label: "Годин під тривогою / добу",
          data: rows.map(r => r.avg_daily_alert_hours),
          yAxisID: "yHours",
          backgroundColor: COLORS[0] + "77",
          borderColor: COLORS[0],
          borderWidth: 1
        },
        {
          type: "line",
          label: "Тривог / день",
          data: rows.map(r => r.alerts_per_day),
          yAxisID: "yAlerts",
          borderColor: COLORS[1],
          backgroundColor: COLORS[1] + "22",
          pointRadius: 2,
          pointHoverRadius: 4,
          borderWidth: 2,
          borderDash: dashed ? [7, 5] : [],
          tension: 0.12,
          spanGaps: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: { mode: "index", intersect: false }
      },
      scales: {
        x: { ticks: { color: TEXT, maxRotation: 0, autoSkip: true }, grid: { color: GRID } },
        yHours: {
          position: "left",
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { color: GRID },
          title: { display: true, text: "Годин / добу", color: TEXT }
        },
        yAlerts: {
          position: "right",
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { drawOnChartArea: false },
          title: { display: true, text: "Тривог / день", color: TEXT }
        }
      }
    }
  });

  setChart("cityDurationChart", labels, [seriesDataset(labelFor(key), rows.map(r => r.avg_alert_duration_min), COLORS[2], dashed)], "Хвилин");

  renderCasualties(key);
  updateUrl();
}

function renderCasualties(key) {
  const section = $("casualtySection");
  const rows = state.data.casualties?.monthly || [];
  if (key !== "kyiv" || !rows.length) {
    section.classList.add("hidden");
    if (state.charts.casualtyChart) {
      state.charts.casualtyChart.destroy();
      delete state.charts.casualtyChart;
    }
    return;
  }
  section.classList.remove("hidden");
  const labels = rows.map(r => r.month || String(r.time || "").slice(0, 7));
  setChart(
    "casualtyChart",
    labels,
    [{ label: "Загиблих", data: rows.map(r => r.deaths), backgroundColor: "#62a0ea99", borderColor: "#62a0ea", borderWidth: 1 }],
    "Кількість загиблих",
    "bar",
    { plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } } }
  );
}

function sharedRows(keys, period) {
  const maps = keys.map(key => {
    const m = new Map();
    for (const row of state.data.cities[key]?.[period] || []) m.set(rowTime(row, period), row);
    return m;
  });
  if (!maps.length) return [];
  let shared = new Set(maps[0].keys());
  for (const map of maps.slice(1)) shared = new Set([...shared].filter(x => map.has(x)));
  return [...shared].sort().map(t => ({ time: t, rows: maps.map(m => m.get(t)) }));
}

function renderComparison() {
  const keys = [$("compareA").value, $("compareB").value, $("compareC").value].filter(Boolean);
  const period = $("comparePeriod").value;
  const shared = sharedRows(keys, period);
  const labels = shared.map(x => x.time);
  const note = shared.length
    ? `Спільний ряд для ${keys.length} міст: ${labels[0]} — ${labels[labels.length - 1]} (${shared.length} ${period === "monthly" ? "міс." : "тиж."}).`
    : "Немає спільних повних періодів для цієї комбінації.";
  $("comparisonNote").textContent = note;

  const metricChart = (id, metric, yTitle) => {
    const datasets = keys.map((key, idx) => seriesDataset(
      labelFor(key),
      shared.map(x => x.rows[idx]?.[metric] ?? null),
      COLORS[idx],
      sourceType(key) === "raion_proxy"
    ));
    setChart(id, labels, datasets, yTitle);
  };

  metricChart("compareAlertsChart", "alerts_per_day", "Тривог/день");
  metricChart("compareHoursChart", "avg_daily_alert_hours", "Годин/добу");
  metricChart("compareDurationChart", "avg_alert_duration_min", "Хвилин");
  updateUrl();
}

function renderAllCitiesTable() {
  const rows = cityKeys().map(key => {
    const kpi = state.data.cities[key]?.kpis?.[0] || {};
    return { key, label: labelFor(key), alerts: kpi.alerts_28d, hours: kpi.alert_hours_28d, duration: kpi.avg_alert_duration_min_28d, coverage: coverageStart(key) };
  });
  rows.sort((a, b) => (Number(b.alerts) || -1) - (Number(a.alerts) || -1));
  $("allCitiesTable").innerHTML = rows.map(r => `
    <tr>
      <td><button class="table-city-link" data-city="${r.key}" type="button">${r.label}</button></td>
      <td>${fmt(r.alerts, 0)}</td>
      <td>${fmt(r.hours, 1)}</td>
      <td>${fmt(r.duration, 1)} хв</td>
      <td>${r.coverage || "—"}</td>
    </tr>`).join("");
  document.querySelectorAll(".table-city-link").forEach(btn => btn.addEventListener("click", () => {
    $("citySelect").value = btn.dataset.city;
    renderCity();
    window.scrollTo({ top: $("cityTitle").offsetTop - 24, behavior: "smooth" });
  }));
}

function renderMethodology() {
  const tolerance = state.data.multicity_meta?.proxy_cross_source_match_tolerance_seconds || 15;
  const deferred = Object.keys(state.data.multicity_meta?.deferred || {});
  $("methodologyDynamic").textContent = `Cross-source continuity перевіряється по конкретних подіях; технічний допуск збігу timestamp — ${tolerance} с. ${deferred.length ? `Не включені: ${deferred.join(", ")}.` : ""}`;
}

function bind() {
  $("citySelect").addEventListener("change", renderCity);
  $("cityPeriod").addEventListener("change", renderCity);
  for (const id of ["compareA", "compareB", "compareC", "comparePeriod"]) $(id).addEventListener("change", renderComparison);
  $("copyLink").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      $("copyLink").textContent = "Скопійовано";
      setTimeout(() => { $("copyLink").textContent = "Скопіювати посилання"; }, 1200);
    } catch {
      $("copyLink").textContent = "Не вдалося";
    }
  });
}

async function init() {
  const response = await fetch("data.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed to load data.json: ${response.status}`);
  state.data = await response.json();
  const keys = cityKeys();

  const defaults = ["kyiv", "kharkiv", "zaporizhzhia"].filter(k => keys.includes(k));
  while (defaults.length < 3 && keys[defaults.length]) defaults.push(keys[defaults.length]);

  const cityDefault = validParam("city", keys, defaults[0] || keys[0]);
  const periodDefault = validParam("period", ["monthly", "weekly"], "monthly");
  const aDefault = validParam("a", keys, defaults[0] || keys[0]);
  const bDefault = validParam("b", keys, defaults[1] || keys[0]);
  const cDefault = validOptionalParam("c", keys, defaults[2] || "");
  const compareDefault = validParam("compare", ["monthly", "weekly"], "monthly");

  fillSelect($("citySelect"), keys, cityDefault);
  fillSelect($("compareA"), keys, aDefault);
  fillSelect($("compareB"), keys, bDefault);
  fillSelect($("compareC"), keys, cDefault, true);
  $("cityPeriod").value = periodDefault;
  $("comparePeriod").value = compareDefault;

  const generated = state.data.meta?.generated_at || state.data.cities?.kyiv?.meta?.generated_at;
  $("updatedAt").textContent = generated ? `Дані згенеровано ${String(generated).replace("T", " ").slice(0, 19)}` : "";

  renderDatasetSummary();
  renderFreshness();
  renderMethodology();
  bind();
  renderCity();
  renderComparison();
  renderAllCitiesTable();
}

init().catch(err => {
  console.error(err);
  $("freshnessBanner").textContent = `Не вдалося завантажити сайт: ${err.message}`;
  $("freshnessBanner").classList.remove("hidden");
});

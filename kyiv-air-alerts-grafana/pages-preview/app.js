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
function periodLabel(value) { return value === "weekly" ? "тижні" : "місяці"; }

function fillSelect(select, keys, current) {
  select.innerHTML = "";
  for (const key of keys) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = labelFor(key);
    opt.selected = key === current;
    select.appendChild(opt);
  }
}

function chartOptions(yTitle) {
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
    }
  };
}

function setChart(id, labels, datasets, yTitle) {
  if (state.charts[id]) state.charts[id].destroy();
  state.charts[id] = new Chart($(id), {
    type: "line",
    data: { labels, datasets },
    options: chartOptions(yTitle)
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

function renderFreshness() {
  const banner = $("freshnessBanner");
  const fresh = state.data.multicity_meta?.effective_freshness || state.data.multicity_meta?.upstream_freshness;
  if (!fresh?.warning) {
    banner.classList.add("hidden");
    return;
  }
  const last = fresh.latest_proxy_event_end || fresh.last_successful_fetch_at;
  banner.textContent = `⚠ Районні/city-level дані біля правого краю можуть бути неповними. Остання підтверджена дата upstream: ${last ? String(last).slice(0, 10) : "невідомо"}. Нулі після неї не слід трактувати як гарантовану відсутність тривог.`;
  banner.classList.remove("hidden");
}

function renderCity() {
  const key = $("citySelect").value;
  const period = $("cityPeriod").value;
  const city = state.data.cities[key];
  if (!city) return;

  $("cityTitle").textContent = labelFor(key);
  const type = sourceType(key);
  const coverage = coverageStart(key);
  const typeText = type === "raion_proxy" ? "Районний proxy" : "Exact-city";
  const badgeClass = type === "raion_proxy" ? "proxy" : "exact";
  $("cityMeta").innerHTML = `<span class="badge ${badgeClass}">${typeText}</span>${coverage ? `<span class="badge">Покриття з ${coverage}</span>` : ""}`;

  const kpi = city.kpis?.[0] || {};
  $("kpiAlerts").textContent = fmt(kpi.alerts_28d, 0);
  $("kpiHours").textContent = `${fmt(kpi.alert_hours_28d, 1)} год`;
  $("kpiDuration").textContent = `${fmt(kpi.avg_alert_duration_min_28d, 1)} хв`;

  const rows = city[period] || [];
  const labels = rows.map(r => rowTime(r, period));
  const dashed = type === "raion_proxy";
  setChart("cityAlertsChart", labels, [seriesDataset(labelFor(key), rows.map(r => r.alerts_per_day), COLORS[0], dashed)], "Тривог/день");
  setChart("cityHoursChart", labels, [seriesDataset(labelFor(key), rows.map(r => r.avg_daily_alert_hours), COLORS[1], dashed)], "Годин/добу");
  setChart("cityDurationChart", labels, [seriesDataset(labelFor(key), rows.map(r => r.avg_alert_duration_min), COLORS[2], dashed)], "Хвилин");
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
  const keys = [$("compareA").value, $("compareB").value, $("compareC").value];
  const period = $("comparePeriod").value;
  const shared = sharedRows(keys, period);
  const labels = shared.map(x => x.time);
  const note = shared.length ? `Спільний ряд: ${labels[0]} — ${labels[labels.length - 1]} (${shared.length} ${period === "monthly" ? "міс." : "тиж."}).` : "Немає спільних повних періодів для цієї комбінації.";
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
}

function bind() {
  $("citySelect").addEventListener("change", renderCity);
  $("cityPeriod").addEventListener("change", renderCity);
  for (const id of ["compareA", "compareB", "compareC", "comparePeriod"]) $(id).addEventListener("change", renderComparison);
}

async function init() {
  const response = await fetch("data.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed to load data.json: ${response.status}`);
  state.data = await response.json();
  const keys = cityKeys();

  const defaults = ["kyiv", "kharkiv", "zaporizhzhia"].filter(k => keys.includes(k));
  while (defaults.length < 3 && keys[defaults.length]) defaults.push(keys[defaults.length]);

  fillSelect($("citySelect"), keys, defaults[0] || keys[0]);
  fillSelect($("compareA"), keys, defaults[0] || keys[0]);
  fillSelect($("compareB"), keys, defaults[1] || keys[0]);
  fillSelect($("compareC"), keys, defaults[2] || keys[0]);

  const generated = state.data.meta?.generated_at || state.data.cities?.kyiv?.meta?.generated_at;
  $("updatedAt").textContent = generated ? `Дані згенеровано ${String(generated).replace("T", " ").slice(0, 19)}` : "";

  renderFreshness();
  bind();
  renderCity();
  renderComparison();
}

init().catch(err => {
  console.error(err);
  $("freshnessBanner").textContent = `Не вдалося завантажити preview: ${err.message}`;
  $("freshnessBanner").classList.remove("hidden");
});

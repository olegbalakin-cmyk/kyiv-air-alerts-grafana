const state = {
  data: null,
  charts: {},
  tableSort: { key: "alerts", direction: "desc" }
};

const DATA_URL = "data.json";
const EXPLOSION_LIVE_URL = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/multicity-wip-2026-09-16/kyiv-air-alerts-grafana/data/explosions_test.json";
const COLORS = ["#62a0ea", "#8ff0a4", "#f8e45c"];
const EXPLOSION_COLOR = "#ff9f43";
const GRID = "rgba(148,163,184,.16)";
const TEXT = "#b8c4cf";
const TABLE_SORT_COLUMNS = [
  { key: "label", label: "Місто / ряд", defaultDirection: "asc" },
  { key: "alerts", label: "Тривог", defaultDirection: "desc" },
  { key: "hours", label: "Годин", defaultDirection: "desc" },
  { key: "duration", label: "Сер. тривалість", defaultDirection: "desc" },
  { key: "coverage", label: "Покриття", defaultDirection: "asc" }
];

function $(id) { return document.getElementById(id); }
function fmt(v, digits = 1) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(digits);
}
function labelFor(key) {
  const mm = state.data.multicity_meta?.cities?.[key];
  return mm?.label || state.data.cities?.[key]?.meta?.city_label || key;
}
function cityKeys() {
  const keys = [...(state.data.multicity_meta?.production_city_keys || Object.keys(state.data.cities || {}))];
  return keys.sort((a, b) => {
    if (a === "kyiv") return -1;
    if (b === "kyiv") return 1;
    return labelFor(a).localeCompare(labelFor(b), "uk", { sensitivity: "base" });
  });
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
function typeText(key) { return sourceType(key) === "raion_proxy" ? "Дані по району" : "Дані по місту"; }
function rolling7dEnabled() {
  return state.data.multicity_meta?.weekly_mode === "rolling_7d";
}
function explosionCity(key) {
  const explosionKey = key === "ivano-frankivsk" ? "ivano_frankivsk" : key;
  return state.data.explosion_metric_test?.cities?.[explosionKey] || null;
}
function explosionEstimate(explosion) {
  if (!explosion) return null;
  const strict = Number(explosion.strict_pct);
  const sensitivity = Number(explosion.sensitivity_pct);
  if (!Number.isFinite(strict)) return null;
  const high = Number.isFinite(sensitivity) ? Math.max(strict, sensitivity) : strict;
  return { low: strict, high, mid: (strict + high) / 2 };
}

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
  if (rolling7dEnabled()) return row.week_end || String(row.time || "").slice(0, 10);
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
  if ($("rolling7dYear")?.value) params.set("year", $("rolling7dYear").value);
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
  banner.textContent = `⚠ Дані біля правого краю можуть бути неповними. Останнє підтверджене оновлення: ${last ? String(last).slice(0, 10) : "невідомо"}. Нулі після цієї точки не слід трактувати як гарантовану відсутність тривог.`;
  banner.classList.remove("hidden");
}

function renderDatasetSummary() {
  const keys = cityKeys();
  const exact = keys.filter(k => sourceType(k) === "exact_city").length;
  const proxy = keys.filter(k => sourceType(k) === "raion_proxy").length;
  $("datasetSummary").innerHTML = [
    `${keys.length} ряди`,
    `${exact} ряди з даними по місту`,
    `${proxy} рядів за даними районів`,
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

  const explosion = explosionCity(key);
  const explosionCard = $("kpiExplosionsCard");
  const explosionEstimateValue = explosionEstimate(explosion);
  if (explosion && explosionEstimateValue) {
    const sensitivityN = Number.isFinite(Number(explosion.sensitivity_n))
      ? Number(explosion.sensitivity_n)
      : Number(explosion.strict_n);
    explosionCard.classList.remove("hidden");
    $("kpiExplosionsPct").textContent = `≈${fmt(explosionEstimateValue.mid, 1)}%`;
    $("kpiExplosionsRange").textContent = `Оцінюваний діапазон: ${fmt(explosionEstimateValue.low, 1)}–${fmt(explosionEstimateValue.high, 1)}%`;
    $("kpiExplosionsCount").textContent = `Консервативно ${explosion.strict_n}; розширено ${sensitivityN} із ${explosion.total_alerts} тривог · весь доступний період`;
    explosionCard.title = "Орієнтовне значення — середина між консервативною та розширеною оцінкою. Діапазон відображає класифікаційну невизначеність і не є статистичним довірчим інтервалом.";
  } else {
    explosionCard.classList.add("hidden");
    explosionCard.removeAttribute("title");
  }

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

  renderRolling7d(key);
  renderShortHorizon(key);
  renderCasualties(key);
  updateUrl();
}

function renderRolling7d(key) {
  const section = $("rolling7dSection");
  const allRows = state.data.cities[key]?.weekly || [];
  if (!rolling7dEnabled() || !allRows.length) {
    section?.classList.add("hidden");
    for (const id of ["rolling7dIntensityChart", "rolling7dDurationChart"]) {
      if (state.charts[id]) {
        state.charts[id].destroy();
        delete state.charts[id];
      }
    }
    return;
  }

  section?.classList.remove("hidden");

  const yearSelect = $("rolling7dYear");
  const availableYears = [...new Set(
    allRows
      .map(r => String(rowTime(r, "weekly")).slice(0, 4))
      .filter(year => /^\d{4}$/.test(year))
  )].sort((a, b) => Number(b) - Number(a));
  const currentCalendarYear = String(new Date().getFullYear());
  const requestedYear = yearSelect?.value || getParams().get("year") || "";
  const selectedYear = availableYears.includes(requestedYear)
    ? requestedYear
    : (availableYears.includes(currentCalendarYear) ? currentCalendarYear : availableYears[0]);

  if (yearSelect) {
    yearSelect.innerHTML = availableYears
      .map(year => `<option value="${year}">${year}</option>`)
      .join("");
    yearSelect.value = selectedYear;
  }

  const rows = allRows.filter(r => String(rowTime(r, "weekly")).slice(0, 4) === selectedYear);
  const labels = rows.map(r => rowTime(r, "weekly"));
  const dashed = sourceType(key) === "raion_proxy";

  if (state.charts.rolling7dIntensityChart) state.charts.rolling7dIntensityChart.destroy();
  state.charts.rolling7dIntensityChart = new Chart($("rolling7dIntensityChart"), {
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

  setChart(
    "rolling7dDurationChart",
    labels,
    [seriesDataset(labelFor(key), rows.map(r => r.avg_alert_duration_min), COLORS[2], dashed)],
    "Хвилин"
  );
}

function renderShortHorizon(key) {
  const rows = state.data.cities[key]?.daily28 || [];
  const labels = rows.map(r => r.date || String(r.time || "").slice(0, 10));
  const range = $("daily28Range");
  if (range) {
    range.textContent = labels.length
      ? `Щоденний розріз для ${labelFor(key)}: ${labels[0]} — ${labels[labels.length - 1]}. Сьогоднішній день не включається.`
      : `Для ${labelFor(key)} немає доступного 28-денного ряду.`;
  }

  setChart(
    "daily28HoursChart",
    labels,
    [{
      label: "Годин під тривогою",
      data: rows.map(r => r.total_alert_duration_hours),
      backgroundColor: COLORS[0] + "88",
      borderColor: COLORS[0],
      borderWidth: 1
    }],
    "Годин",
    "bar",
    { plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } } }
  );

  const explosion = explosionCity(key);
  const strictDaily = explosion?.strict_daily || {};
  const regularAlerts = rows.map(r => Math.max(0, Number(r.alerts_started || 0) - Number(strictDaily[r.date] || 0)));
  const explosionAlerts = rows.map(r => Number(strictDaily[r.date] || 0));
  const alertBarDatasets = explosion ? [
    {
      type: "bar",
      label: "Інші тривоги",
      data: regularAlerts,
      yAxisID: "yAlerts",
      stack: "alerts",
      backgroundColor: COLORS[1] + "77",
      borderColor: COLORS[1],
      borderWidth: 1
    },
    {
      type: "bar",
      label: "З повідомленням про вибухи",
      data: explosionAlerts,
      yAxisID: "yAlerts",
      stack: "alerts",
      backgroundColor: EXPLOSION_COLOR + "cc",
      borderColor: EXPLOSION_COLOR,
      borderWidth: 1
    }
  ] : [{
    type: "bar",
    label: "Тривог, що почалися",
    data: rows.map(r => r.alerts_started),
    yAxisID: "yAlerts",
    backgroundColor: COLORS[1] + "77",
    borderColor: COLORS[1],
    borderWidth: 1
  }];

  if (state.charts.daily28AlertsDurationChart) state.charts.daily28AlertsDurationChart.destroy();
  state.charts.daily28AlertsDurationChart = new Chart($("daily28AlertsDurationChart"), {
    data: {
      labels,
      datasets: [
        ...alertBarDatasets,
        {
          type: "line",
          label: "Середня тривалість, хв",
          data: rows.map(r => r.avg_alert_duration_minutes),
          yAxisID: "yDuration",
          borderColor: COLORS[2],
          backgroundColor: COLORS[2] + "22",
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          borderDash: sourceType(key) === "raion_proxy" ? [7, 5] : [],
          tension: 0.12,
          spanGaps: false
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
        yAlerts: {
          position: "left",
          beginAtZero: true,
          stacked: true,
          ticks: { color: TEXT, precision: 0 },
          grid: { color: GRID },
          title: { display: true, text: "Кількість тривог", color: TEXT }
        },
        yDuration: {
          position: "right",
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { drawOnChartArea: false },
          title: { display: true, text: "Середня тривалість, хв", color: TEXT }
        }
      }
    }
  });
}

function renderCasualties(key) {
  const section = $("casualtySection");
  const series = state.data.casualties_by_city?.[key] || (key === "kyiv" ? state.data.casualties : null);
  const rows = series?.monthly || [];
  if (!rows.length) {
    section.classList.add("hidden");
    if (state.charts.casualtyChart) {
      state.charts.casualtyChart.destroy();
      delete state.charts.casualtyChart;
    }
    return;
  }
  section.classList.remove("hidden");
  $("casualtyCityEyebrow").textContent = labelFor(key);
  const meta = series?.meta || {};
  const total = rows.reduce((sum, r) => sum + (Number(r.deaths) || 0), 0);
  const unresolved = Number(meta.unresolved_review_cases || 0);
  $("casualtySourceNote").textContent = unresolved
    ? `Підтверджений ряд: ${total} смертей. ${unresolved} невирішених review-кейсів не включено. Реконструкція за публічно доступними повідомленнями офіційних органів і медіа.`
    : `Підтверджений ряд: ${total} смертей. Реконструкція за публічно доступними повідомленнями офіційних органів і медіа.`;
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

function renderExplosionComparison(keys) {
  const card = $("compareExplosionsCard");
  const note = $("compareExplosionsNote");
  const availableKeys = keys.filter(key => (explosionCity(key)?.rolling90 || []).length);
  const missingKeys = keys.filter(key => !availableKeys.includes(key));

  if (!availableKeys.length) {
    card.classList.add("hidden");
    if (state.charts.compareExplosionsChart) {
      state.charts.compareExplosionsChart.destroy();
      delete state.charts.compareExplosionsChart;
    }
    return;
  }

  card.classList.remove("hidden");
  const maps = new Map();
  const allDates = new Set();
  for (const key of availableKeys) {
    const m = new Map();
    for (const row of explosionCity(key).rolling90) {
      m.set(row.date, row);
      allDates.add(row.date);
    }
    maps.set(key, m);
  }
  const labels = [...allDates].sort();
  const datasets = availableKeys.map((key, idx) => {
    const m = maps.get(key);
    const ds = seriesDataset(
      labelFor(key),
      labels.map(date => m.get(date)?.pct ?? null),
      COLORS[idx],
      false
    );
    ds.spanGaps = false;
    ds.cityKey = key;
    ds.explosionRows = labels.map(date => m.get(date) || null);
    return ds;
  });

  setChart(
    "compareExplosionsChart",
    labels,
    datasets,
    "%",
    "line",
    {
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            label: context => {
              const row = context.dataset.explosionRows?.[context.dataIndex];
              if (!row) return null;
              return `${context.dataset.label}: ${fmt(row.pct, 1)}% · ${row.strict_n}/${row.alerts_n}`;
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: TEXT, maxRotation: 0, autoSkip: true }, grid: { color: GRID } },
        y: {
          beginAtZero: true,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: "% тривог із повідомленнями про вибухи", color: TEXT }
        }
      }
    }
  );

  const rangeNote = "Лінії показують консервативну strict-оцінку; агрегований KPI для міста вище подається як орієнтовне midpoint-значення з діапазоном strict–sensitivity. Це класифікаційна невизначеність, не довірчий інтервал.";
  note.textContent = missingKeys.length
    ? `Ковзні 90 днів, strict; повне 90-денне вікно. Поки немає завершеного explosion-ряду: ${missingKeys.map(labelFor).join(", ")}. ${rangeNote}`
    : `Ковзні 90 днів, strict; кожна точка = n/N за останні 90 завершених днів. Перемикач «Період» вище на цей графік не впливає. ${rangeNote}`;
}

function renderComparison() {
  const keys = [$("compareA").value, $("compareB").value, $("compareC").value].filter(Boolean);
  const period = $("comparePeriod").value;
  const shared = sharedRows(keys, period);
  const labels = shared.map(x => x.time);
  let countLabel = "міс.";
  if (period === "weekly") countLabel = rolling7dEnabled() ? "7-денних вікон" : "тиж.";
  const note = shared.length
    ? `Спільний ряд для ${keys.length} міст: ${labels[0]} — ${labels[labels.length - 1]} (${shared.length} ${countLabel}).`
    : "Немає спільних періодів для цієї комбінації.";
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
  renderExplosionComparison(keys);

  const casualtyCard = $("compareCasualtiesCard");
  const casualtyNote = $("compareCasualtiesNote");
  const casualtyKeys = keys.filter(key => (state.data.casualties_by_city?.[key]?.monthly || []).length);
  const missingCasualtyKeys = keys.filter(key => !casualtyKeys.includes(key));

  if (!casualtyKeys.length) {
    casualtyCard.classList.add("hidden");
    if (state.charts.compareCasualtiesChart) {
      state.charts.compareCasualtiesChart.destroy();
      delete state.charts.compareCasualtiesChart;
    }
  } else {
    casualtyCard.classList.remove("hidden");
    const casualtyMaps = casualtyKeys.map(key => new Map(
      state.data.casualties_by_city[key].monthly.map(row => [
        row.month || String(row.time || "").slice(0, 7),
        Number(row.deaths) || 0
      ])
    ));
    let casualtyMonths = new Set(casualtyMaps[0].keys());
    for (const map of casualtyMaps.slice(1)) {
      casualtyMonths = new Set([...casualtyMonths].filter(month => map.has(month)));
    }
    const casualtyLabels = [...casualtyMonths].sort();
    const casualtyDatasets = casualtyKeys.map((key, idx) => ({
      label: labelFor(key),
      data: casualtyLabels.map(month => casualtyMaps[idx].get(month) ?? null),
      backgroundColor: COLORS[idx] + "77",
      borderColor: COLORS[idx],
      borderWidth: 1
    }));
    setChart(
      "compareCasualtiesChart",
      casualtyLabels,
      casualtyDatasets,
      "Кількість загиблих",
      "bar",
      { plugins: { legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } }, tooltip: { mode: "index", intersect: false } } }
    );
    casualtyNote.textContent = missingCasualtyKeys.length
      ? `Помісячний confirmed-ряд. Немає готового casualty-ряду: ${missingCasualtyKeys.map(labelFor).join(", ")}.`
      : "Помісячний confirmed-ряд для всіх обраних міст. Перемикач «Період» вище впливає лише на графіки тривог.";
  }

  updateUrl();
}

function isMissingSortValue(value) {
  return value === null || value === undefined || value === "" || (typeof value === "number" && Number.isNaN(value));
}

function compareTableRows(a, b) {
  const { key, direction } = state.tableSort;
  const av = a[key];
  const bv = b[key];
  const aMissing = isMissingSortValue(av);
  const bMissing = isMissingSortValue(bv);

  if (aMissing && bMissing) return a.label.localeCompare(b.label, "uk");
  if (aMissing) return 1;
  if (bMissing) return -1;

  let cmp;
  if (key === "label" || key === "coverage") {
    cmp = String(av).localeCompare(String(bv), "uk", { numeric: true, sensitivity: "base" });
  } else {
    cmp = Number(av) - Number(bv);
  }
  if (cmp === 0) cmp = a.label.localeCompare(b.label, "uk");
  return direction === "asc" ? cmp : -cmp;
}

function updateTableSortHeaders() {
  const headers = document.querySelectorAll(".table-panel thead th");
  TABLE_SORT_COLUMNS.forEach((column, idx) => {
    const th = headers[idx];
    if (!th) return;
    const active = state.tableSort.key === column.key;
    const arrow = active ? (state.tableSort.direction === "asc" ? " ↑" : " ↓") : " ↕";
    th.textContent = column.label + arrow;
    th.dataset.sortKey = column.key;
    th.setAttribute("aria-sort", active ? (state.tableSort.direction === "asc" ? "ascending" : "descending") : "none");
    th.setAttribute("role", "button");
    th.tabIndex = 0;
    th.title = active
      ? `Сортування: ${state.tableSort.direction === "asc" ? "за зростанням" : "за спаданням"}. Натисніть, щоб змінити напрямок.`
      : `Сортувати за колонкою «${column.label}»`;
    th.style.cursor = "pointer";
    th.style.userSelect = "none";
  });
}

function changeTableSort(column) {
  if (state.tableSort.key === column.key) {
    state.tableSort.direction = state.tableSort.direction === "asc" ? "desc" : "asc";
  } else {
    state.tableSort = { key: column.key, direction: column.defaultDirection };
  }
  renderAllCitiesTable();
}

function setupTableSorting() {
  const headers = document.querySelectorAll(".table-panel thead th");
  TABLE_SORT_COLUMNS.forEach((column, idx) => {
    const th = headers[idx];
    if (!th) return;
    const activate = () => changeTableSort(column);
    th.addEventListener("click", activate);
    th.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate();
      }
    });
  });
  updateTableSortHeaders();
}

function renderAllCitiesTable() {
  const rows = cityKeys().map(key => {
    const kpi = state.data.cities[key]?.kpis?.[0] || {};
    return {
      key,
      label: labelFor(key),
      alerts: kpi.alerts_28d,
      hours: kpi.alert_hours_28d,
      duration: kpi.avg_alert_duration_min_28d,
      coverage: coverageStart(key)
    };
  });
  rows.sort(compareTableRows);
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
  updateTableSortHeaders();
}

function renderMethodology() {
  const rolling = rolling7dEnabled();
  const cityWeeklyOption = $("cityWeeklyOption");
  const compareWeeklyOption = $("compareWeeklyOption");
  if (cityWeeklyOption) cityWeeklyOption.textContent = rolling ? "Ковзні 7 днів" : "Тижні";
  if (compareWeeklyOption) compareWeeklyOption.textContent = rolling ? "Ковзні 7 днів" : "Тижні";

  const periodMethodology = $("periodMethodology");
  if (periodMethodology) {
    periodMethodology.innerHTML = rolling
      ? "<strong>Які дні потрапляють у розрахунки.</strong> Усі показники рахуються лише по завершених календарних днях. Сьогоднішній день не враховується. Картки вгорі і блок «Останні 28 завершених днів» охоплюють рівно останні 28 завершених днів — до вчора включно; у короткому горизонті кожен день показаний окремо. На місячному графіку показуються лише повні календарні місяці. У режимі «Ковзні 7 днів» кожна точка охоплює 7 завершених календарних днів і датована останнім днем цього вікна; сусідні точки перекриваються на 6 днів. Перше вікно, яке могло б включати неповний стартовий день покриття, не показується."
      : "<strong>Які дні потрапляють у розрахунки.</strong> Усі показники рахуються лише по завершених календарних днях. Сьогоднішній день не враховується. Картки вгорі і блок «Останні 28 завершених днів» охоплюють рівно останні 28 завершених днів — до вчора включно; у короткому горизонті кожен день показаний окремо. На місячному графіку показуються лише повні календарні місяці, а на тижневому — лише повні тижні з понеділка до неділі. Якщо дані для міста починаються посеред місяця або тижня, цей перший неповний період не показується.";
  }

  const tolerance = state.data.multicity_meta?.proxy_cross_source_match_tolerance_seconds || 15;
  const deferred = Object.keys(state.data.multicity_meta?.deferred || {});
  $("methodologyDynamic").textContent = `Cross-source continuity перевіряється по конкретних подіях; технічний допуск збігу timestamp — ${tolerance} с. ${deferred.length ? `Не включені: ${deferred.join(", ")}.` : ""}`;
}

function bind() {
  $("citySelect").addEventListener("change", renderCity);
  $("cityPeriod").addEventListener("change", renderCity);
  $("rolling7dYear")?.addEventListener("change", () => {
    renderRolling7d($("citySelect").value);
    updateUrl();
  });
  for (const id of ["compareA", "compareB", "compareC", "comparePeriod"]) $(id).addEventListener("change", renderComparison);
  setupTableSorting();
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
  const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed to load live dashboard data: ${response.status}`);
  state.data = await response.json();

  try {
    const explosionResponse = await fetch(`${EXPLOSION_LIVE_URL}?v=${Date.now()}`, { cache: "no-store" });
    if (explosionResponse.ok) {
      const explosionLive = await explosionResponse.json();
      if (explosionLive?.meta?.test_only && explosionLive?.cities) {
        state.data.explosion_metric_test = explosionLive;
      }
    }
  } catch (err) {
    console.warn("Explosion live data unavailable; using embedded preview snapshot", err);
  }

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

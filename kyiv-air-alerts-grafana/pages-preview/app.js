const state = {
  data: null,
  charts: {},
  tableSort: { key: "alerts", direction: "desc" }
};

const DATA_URL = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/dashboard_data.json";
const COLORS = ["#62a0ea", "#8ff0a4", "#f8e45c"];
const TIME_PROFILE_COLOR = "#ef4444";
const PARTIAL_PERIOD_DASH = [3, 4];
const TOUR_STORAGE_KEY = "air-alerts-intro-tour-v2";
const TOUR_STEPS = [
  {
    selector: ".controls-panel",
    title: "Оберіть місто і період",
    text: "Тут можна змінити місто та масштаб графіків. За замовчуванням показуються місяці; також доступні ковзні 7, 30 і 90 днів."
  },
  {
    selector: "#cityIntensityChart",
    closest: ".chart-card",
    title: "Як читати головний графік",
    text: "Стовпчики показують середній час під тривогою на добу, лінія — середню кількість тривог на день. Пунктиром позначений поточний неповний зріз."
  },
  {
    selector: "#cityIntensityChart",
    closest: ".chart-card",
    title: "Легенда — це перемикач",
    text: "Натисніть на назву показника в легенді графіка, щоб тимчасово приховати його. Натисніть ще раз — і показник повернеться. Можете спробувати прямо зараз."
  },
  {
    selector: "#timeOfDaySection",
    title: "Добовий профіль",
    text: "Цей графік показує, у які години тривога відносно частіше активна. 100% — власний максимум вибраного міста й періоду, а не 100% часу під тривогою."
  },
  {
    selector: ".comparison-controls",
    title: "Порівнюйте міста",
    text: "Оберіть два або три міста. Порівняльні графіки використовують лише спільні для вибраних рядів періоди."
  },
  {
    selector: "#allCitiesSection",
    title: "Огляд усіх міст",
    text: "У нижній таблиці можна швидко порівняти всі 23 ряди та змінити горизонт: 7, 30, 90 днів, рік або від початку спільних даних."
  }
];
const GRID = "rgba(148,163,184,.16)";
const TEXT = "#b8c4cf";
const HEATMAP_RANGES = ["7d", "30d", "90d", "year", "all"];
const TABLE_RANGES = ["7d", "30d", "90d", "year", "common"];
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

function isPartialPeriod(row) {
  return Boolean(row?.is_partial_period);
}

function partialSegment(rows, color) {
  return {
    borderDash(ctx) {
      return isPartialPeriod(rows?.[ctx.p1DataIndex]) ? PARTIAL_PERIOD_DASH : undefined;
    },
    borderColor(ctx) {
      return isPartialPeriod(rows?.[ctx.p1DataIndex]) ? color + "99" : undefined;
    }
  };
}

const partialPeriodBarPlugin = {
  id: "partialPeriodBar",
  afterDatasetsDraw(chart, _args, options) {
    const rows = options?.rows || [];
    const datasetIndices = options?.datasetIndices || [];
    const partialIndices = rows
      .map((row, index) => isPartialPeriod(row) ? index : -1)
      .filter(index => index >= 0);
    if (!partialIndices.length || !datasetIndices.length) return;

    const ctx = chart.ctx;
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 2;

    for (const datasetIndex of datasetIndices) {
      const meta = chart.getDatasetMeta(datasetIndex);
      const dataset = chart.data.datasets[datasetIndex];
      for (const dataIndex of partialIndices) {
        const element = meta.data?.[dataIndex];
        if (!element) continue;
        const props = element.getProps(["x", "y", "base", "width"], true);
        const left = props.x - props.width / 2 + 1;
        const top = Math.min(props.y, props.base) + 1;
        const width = Math.max(0, props.width - 2);
        const height = Math.max(1, Math.abs(props.base - props.y) - 2);
        const border = Array.isArray(dataset.borderColor)
          ? dataset.borderColor[dataIndex]
          : dataset.borderColor;
        ctx.strokeStyle = border || TEXT;
        ctx.strokeRect(left, top, width, height);
      }
    }
    ctx.restore();
  }
};

function seriesDataset(label, values, color, dashed = false, rows = null) {
  return {
    label,
    data: values,
    borderColor: color,
    backgroundColor: color + "22",
    pointRadius: 0,
    pointHoverRadius: 0,
    borderWidth: 2,
    borderDash: dashed ? [7, 5] : [],
    segment: rows ? partialSegment(rows, color) : undefined,
    tension: 0,
    spanGaps: true
  };
}

function rowTime(row, period) {
  if (period === "monthly") return row.month || String(row.time || "").slice(0, 7);
  if (period === "rolling30" || period === "rolling90") {
    return row.window_end || String(row.time || "").slice(0, 10);
  }
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
  if ($("timeOfDayRange")?.value) params.set("tod", $("timeOfDayRange").value);
  if ($("compareTimeOfDayRange")?.value) params.set("ctod", $("compareTimeOfDayRange").value);
  if ($("allCitiesRange")?.value) params.set("table", $("allCitiesRange").value);
  history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
}


function renderTimeOfDay(key) {
  const section = $("timeOfDaySection");
  const root = state.data.time_of_day_profile;
  const city = root?.cities?.[key];
  const select = $("timeOfDayRange");
  if (!section || !select || !city?.periods) {
    section?.classList.add("hidden");
    return;
  }

  const range = HEATMAP_RANGES.includes(select.value) ? select.value : "30d";
  const period = city.periods[range];
  if (!period?.slots?.length) {
    section.classList.add("hidden");
    return;
  }
  section.classList.remove("hidden");

  const peakText = period.peak_slot
    ? `Пік: ${period.peak_slot} · ${fmt(period.peak_alert_share_pct, 1)}% фактичного часу під тривогою.`
    : "У цьому діапазоні немає часу під тривогою.";
  $("timeOfDayMeta").textContent =
    `${period.range_start} — ${period.range_end} · ${period.days} завершених днів. ${peakText}`;

  if (state.charts.timeOfDayChart) state.charts.timeOfDayChart.destroy();
  const labels = period.slots.map(slot => slot.start);
  const values = period.slots.map(slot => Number(slot.relative_intensity) || 0);
  const shares = period.slots.map(slot => Number(slot.alert_share_pct) || 0);
  const intervalLabels = period.slots.map(slot => slot.label);

  state.charts.timeOfDayChart = new Chart($("timeOfDayChart"), {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Відносна інтенсивність",
        data: values,
        alertShares: shares,
        intervalLabels,
        borderColor: TIME_PROFILE_COLOR,
        backgroundColor: "rgba(239,68,68,.16)",
        fill: true,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 0,
        pointHitRadius: 10,
        tension: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            title(items) {
              const i = items?.[0]?.dataIndex ?? 0;
              return intervalLabels[i] || labels[i] || "";
            },
            label(context) {
              const i = context.dataIndex;
              return `Відносна інтенсивність: ${fmt(values[i], 0)}% · фактично під тривогою ${fmt(shares[i], 1)}% часу`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: TEXT, autoSkip: true, maxTicksLimit: 9, maxRotation: 0 },
          grid: { color: GRID },
          title: { display: true, text: "Час доби", color: TEXT }
        },
        y: {
          min: 0,
          max: 100,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: "Відносна інтенсивність", color: TEXT }
        }
      }
    }
  });
}

function renderTimeOfDayComparison(keys) {
  const root = state.data.time_of_day_profile;
  const select = $("compareTimeOfDayRange");
  const note = $("compareTimeOfDayNote");
  const canvas = $("compareTimeOfDayChart");
  if (!root?.cities || !select || !canvas) return;

  const range = HEATMAP_RANGES.includes(select.value) ? select.value : "30d";
  const usable = keys
    .map(key => ({ key, period: root.cities?.[key]?.periods?.[range] }))
    .filter(item => item.period?.slots?.length);

  if (state.charts.compareTimeOfDayChart) {
    state.charts.compareTimeOfDayChart.destroy();
    delete state.charts.compareTimeOfDayChart;
  }

  if (!usable.length) {
    if (note) note.textContent = "Немає добового профілю для обраних міст.";
    return;
  }

  const labels = usable[0].period.slots.map(slot => slot.start);
  const intervalLabels = usable[0].period.slots.map(slot => slot.label);
  const datasets = usable.map((item, idx) => ({
    label: labelFor(item.key),
    data: item.period.slots.map(slot => Number(slot.relative_intensity) || 0),
    alertShares: item.period.slots.map(slot => Number(slot.alert_share_pct) || 0),
    borderColor: COLORS[idx % COLORS.length],
    backgroundColor: COLORS[idx % COLORS.length] + "18",
    borderWidth: 2,
    pointRadius: 0,
    pointHoverRadius: 0,
    pointHitRadius: 10,
    tension: 0,
    fill: false
  }));

  if (note) {
    const ranges = usable
      .map(item => `${labelFor(item.key)}: ${item.period.range_start} — ${item.period.range_end}`)
      .join(" · ");
    note.textContent =
      `Кожен ряд нормалізовано окремо: власний найчастіший 15-хвилинний слот = 100%. ${ranges}`;
  }

  state.charts.compareTimeOfDayChart = new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            title(items) {
              const i = items?.[0]?.dataIndex ?? 0;
              return intervalLabels[i] || labels[i] || "";
            },
            label(context) {
              const share = context.dataset.alertShares?.[context.dataIndex];
              return `${context.dataset.label}: ${fmt(context.parsed.y, 0)}% від власного піку · фактично ${fmt(share, 1)}% часу`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: TEXT, autoSkip: true, maxTicksLimit: 9, maxRotation: 0 },
          grid: { color: GRID },
          title: { display: true, text: "Час доби", color: TEXT }
        },
        y: {
          min: 0,
          max: 100,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: "Відносна інтенсивність", color: TEXT }
        }
      }
    }
  });
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
          backgroundColor: rows.map(r => isPartialPeriod(r) ? COLORS[0] + "22" : COLORS[0] + "77"),
          borderColor: rows.map(() => COLORS[0]),
          borderWidth: rows.map(r => isPartialPeriod(r) ? 0 : 1)
        },
        {
          type: "line",
          label: "Тривог / день",
          data: rows.map(r => r.alerts_per_day),
          yAxisID: "yAlerts",
          borderColor: COLORS[1],
          backgroundColor: COLORS[1] + "22",
          pointRadius: 0,
          pointHoverRadius: 0,
          borderWidth: 2,
          borderDash: dashed ? [7, 5] : [],
          segment: partialSegment(rows, COLORS[1]),
          tension: 0,
          spanGaps: true
        }
      ]
    },
    plugins: [partialPeriodBarPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            footer(items) {
              const i = items?.[0]?.dataIndex ?? -1;
              return isPartialPeriod(rows[i]) ? "Поточний неповний період" : "";
            }
          }
        },
        partialPeriodBar: { rows, datasetIndices: [0] }
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

  setChart("cityDurationChart", labels, [seriesDataset(labelFor(key), rows.map(r => r.avg_alert_duration_min), COLORS[2], dashed, rows)], "Хвилин");

  renderTimeOfDay(key);
  renderShortHorizon(key);
  renderCasualties(key);
  updateUrl();
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
    {
      layout: { padding: { right: 70 } },
      plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
      scales: {
        x: {
          offset: true,
          ticks: { color: TEXT, maxRotation: 0, autoSkip: true },
          grid: { color: GRID }
        },
        y: {
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { color: GRID },
          title: { display: true, text: "Годин", color: TEXT },
          afterFit: scale => { scale.width = 62; }
        }
      }
    }
  );

  const alertBarDatasets = [{
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
          pointRadius: 0,
          pointHoverRadius: 0,
          borderWidth: 2,
          borderDash: sourceType(key) === "raion_proxy" ? [7, 5] : [],
          tension: 0,
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
        x: {
          offset: true,
          ticks: { color: TEXT, maxRotation: 0, autoSkip: true },
          grid: { color: GRID }
        },
        yAlerts: {
          position: "left",
          beginAtZero: true,
          stacked: true,
          ticks: { color: TEXT, precision: 0 },
          grid: { color: GRID },
          title: { display: true, text: "Кількість тривог", color: TEXT },
          afterFit: scale => { scale.width = 62; }
        },
        yDuration: {
          position: "right",
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { drawOnChartArea: false },
          title: { display: true, text: "Середня тривалість, хв", color: TEXT },
          afterFit: scale => { scale.width = 70; }
        }
      }
    }
  });
}

function currentKyivMonth() {
  try {
    return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Kyiv", year: "numeric", month: "2-digit" }).format(new Date());
  } catch {
    return new Date().toISOString().slice(0, 7);
  }
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
  const currentMonth = currentKyivMonth();
  const displayRows = rows.map(r => ({
    ...r,
    is_partial_period: (r.month || String(r.time || "").slice(0, 7)) === currentMonth
  }));
  const labels = displayRows.map(r => r.month || String(r.time || "").slice(0, 7));
  if (state.charts.casualtyChart) state.charts.casualtyChart.destroy();
  state.charts.casualtyChart = new Chart($("casualtyChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Загиблих",
        data: displayRows.map(r => r.deaths),
        backgroundColor: displayRows.map(r => isPartialPeriod(r) ? "#62a0ea22" : "#62a0ea99"),
        borderColor: displayRows.map(() => "#62a0ea"),
        borderWidth: displayRows.map(r => isPartialPeriod(r) ? 0 : 1)
      }]
    },
    plugins: [partialPeriodBarPlugin],
    options: chartOptions("Кількість загиблих", {
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            footer(items) {
              const i = items?.[0]?.dataIndex ?? -1;
              return isPartialPeriod(displayRows[i]) ? "Поточний неповний місяць · дані можуть доповнюватися" : "";
            }
          }
        },
        partialPeriodBar: { rows: displayRows, datasetIndices: [0] }
      }
    })
  });
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
      sourceType(key) === "raion_proxy",
      shared.map(x => x.rows[idx])
    ));
    setChart(id, labels, datasets, yTitle);
  };

  metricChart("compareAlertsChart", "alerts_per_day", "Тривог/день");
  metricChart("compareHoursChart", "avg_daily_alert_hours", "Годин/добу");
  metricChart("compareDurationChart", "avg_alert_duration_min", "Хвилин");
  renderTimeOfDayComparison(keys);
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
  const range = TABLE_RANGES.includes($("allCitiesRange")?.value)
    ? $("allCitiesRange").value
    : "30d";
  const periodLabels = {
    "7d": "7 днів",
    "30d": "30 днів",
    "90d": "90 днів",
    "year": "Рік",
    "common": "Від початку спільних даних"
  };
  const root = state.data.all_cities_table;
  const cities = root?.cities || {};

  const rows = cityKeys().map(key => {
    const period = cities?.[key]?.periods?.[range];
    const fallback = state.data.cities[key]?.kpis?.[0] || {};
    return {
      key,
      label: labelFor(key),
      alerts: period?.alerts_started ?? fallback.alerts_28d,
      hours: period?.alert_hours ?? fallback.alert_hours_28d,
      duration: period?.avg_alert_duration_min ?? fallback.avg_alert_duration_min_28d,
      coverage: coverageStart(key),
      rangeStart: period?.range_start || fallback.period_start || null,
      rangeEnd: period?.range_end || fallback.period_end || null
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

  const note = $("allCitiesRangeNote");
  if (note) {
    const sample = rows.find(r => r.rangeStart && r.rangeEnd);
    const dates = sample ? `${sample.rangeStart} — ${sample.rangeEnd}` : "—";
    note.textContent =
      `${periodLabels[range]} · ${dates}. Усі 23 ряди рахуються на одному спільному часовому вікні.`;
  }

  document.querySelectorAll(".table-city-link").forEach(btn => btn.addEventListener("click", () => {
    $("citySelect").value = btn.dataset.city;
    renderCity();
    window.scrollTo({ top: $("cityTitle").offsetTop - 24, behavior: "smooth" });
  }));
  updateTableSortHeaders();
}

let tourStepIndex = 0;
let activeTourTarget = null;

function tourWasSeen() {
  try {
    return localStorage.getItem(TOUR_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function markTourSeen() {
  try {
    localStorage.setItem(TOUR_STORAGE_KEY, "1");
  } catch {
    // Tour remains usable without browser storage.
  }
}

function resolveTourTarget(step) {
  let target = document.querySelector(step.selector);
  if (target && step.closest) target = target.closest(step.closest);
  return target;
}

function clearTourTarget() {
  if (activeTourTarget) activeTourTarget.classList.remove("tour-target");
  activeTourTarget = null;
}

function showTourStep(index) {
  const root = $("introTour");
  if (!root) return;

  const direction = index >= tourStepIndex ? 1 : -1;
  let nextIndex = index;
  let target = null;
  while (nextIndex >= 0 && nextIndex < TOUR_STEPS.length) {
    target = resolveTourTarget(TOUR_STEPS[nextIndex]);
    if (target && target.getClientRects().length) break;
    nextIndex += direction;
  }
  if (!target || nextIndex < 0 || nextIndex >= TOUR_STEPS.length) {
    finishIntroTour();
    return;
  }

  tourStepIndex = nextIndex;
  const step = TOUR_STEPS[tourStepIndex];
  clearTourTarget();
  activeTourTarget = target;
  activeTourTarget.classList.add("tour-target");

  $("tourTitle").textContent = step.title;
  $("tourText").textContent = step.text;
  $("tourProgress").textContent = String(tourStepIndex + 1) + " / " + String(TOUR_STEPS.length);
  $("tourPrev").disabled = tourStepIndex === 0;
  $("tourNext").textContent = tourStepIndex === TOUR_STEPS.length - 1 ? "Готово" : "Далі";

  root.classList.remove("hidden");
  root.setAttribute("aria-hidden", "false");
  document.body.classList.add("tour-open");

  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  target.scrollIntoView({
    behavior: reduceMotion ? "auto" : "smooth",
    block: "center",
    inline: "nearest"
  });
}

function startIntroTour() {
  tourStepIndex = 0;
  showTourStep(0);
}

function finishIntroTour() {
  const root = $("introTour");
  clearTourTarget();
  if (root) {
    root.classList.add("hidden");
    root.setAttribute("aria-hidden", "true");
  }
  document.body.classList.remove("tour-open");
  markTourSeen();
}

function bindIntroTour() {
  $("showTour")?.addEventListener("click", startIntroTour);
  $("tourNext")?.addEventListener("click", () => {
    if (tourStepIndex >= TOUR_STEPS.length - 1) finishIntroTour();
    else showTourStep(tourStepIndex + 1);
  });
  $("tourPrev")?.addEventListener("click", () => {
    if (tourStepIndex > 0) showTourStep(tourStepIndex - 1);
  });
  $("tourSkip")?.addEventListener("click", finishIntroTour);
  $("tourClose")?.addEventListener("click", finishIntroTour);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !$("introTour")?.classList.contains("hidden")) finishIntroTour();
  });
}

function maybeStartIntroTour() {
  if (tourWasSeen()) return;
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      if ($("introTour")?.classList.contains("hidden")) startIntroTour();
    });
  });
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
      ? "<strong>Які дні потрапляють у розрахунки.</strong> Усі показники рахуються лише по завершених календарних днях. Сьогоднішній день не враховується. Картки вгорі і блок «Останні 28 завершених днів» охоплюють рівно останні 28 завершених днів — до вчора включно; у короткому горизонті кожен день показаний окремо. Завершені періоди показуються суцільно. Поточний неповний календарний місяць додається окремо до останнього завершеного дня і позначається пунктиром. Для «Ковзних 7/30/90 днів» регулярні точки мають тижневий крок; якщо після останньої регулярної точки вже є нові завершені дні, додається поточний зріз до останнього завершеного дня і він також позначається пунктиром. Перше вікно, яке могло б включати неповний стартовий день покриття, не показується."
      : "<strong>Які дні потрапляють у розрахунки.</strong> Усі показники рахуються лише по завершених календарних днях. Сьогоднішній день не враховується. Картки вгорі і блок «Останні 28 завершених днів» охоплюють рівно останні 28 завершених днів — до вчора включно; у короткому горизонті кожен день показаний окремо. На місячному графіку показуються лише повні календарні місяці, а на тижневому — лише повні тижні з понеділка до неділі. Якщо дані для міста починаються посеред місяця або тижня, цей перший неповний період не показується.";
  }

  const tolerance = state.data.multicity_meta?.proxy_cross_source_match_tolerance_seconds || 15;
  const deferred = Object.keys(state.data.multicity_meta?.deferred || {});
  $("methodologyDynamic").textContent = `Cross-source continuity перевіряється по конкретних подіях; технічний допуск збігу timestamp — ${tolerance} с. ${deferred.length ? `Не включені: ${deferred.join(", ")}.` : ""}`;
}

function bind() {
  $("citySelect").addEventListener("change", renderCity);
  $("cityPeriod").addEventListener("change", renderCity);
  $("timeOfDayRange")?.addEventListener("change", () => {
    renderTimeOfDay($("citySelect").value);
    updateUrl();
  });
  $("allCitiesRange")?.addEventListener("change", () => {
    renderAllCitiesTable();
    updateUrl();
  });
  for (const id of ["compareA", "compareB", "compareC", "comparePeriod", "compareTimeOfDayRange"]) $(id).addEventListener("change", renderComparison);
  setupTableSorting();
  bindIntroTour();
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


  const keys = cityKeys();

  const defaults = ["kyiv", "kharkiv", "zaporizhzhia"].filter(k => keys.includes(k));
  while (defaults.length < 3 && keys[defaults.length]) defaults.push(keys[defaults.length]);

  const cityDefault = validParam("city", keys, defaults[0] || keys[0]);
  const periodDefault = validParam("period", ["monthly", "weekly", "rolling30", "rolling90"], "monthly");
  const aDefault = validParam("a", keys, defaults[0] || keys[0]);
  const bDefault = validParam("b", keys, defaults[1] || keys[0]);
  const cDefault = validOptionalParam("c", keys, defaults[2] || "");
  const compareDefault = validParam("compare", ["monthly", "weekly"], "monthly");
  const heatmapDefault = validParam("tod", HEATMAP_RANGES, "30d");
  const compareTimeOfDayDefault = validParam("ctod", HEATMAP_RANGES, "30d");
  const allCitiesRangeDefault = validParam("table", TABLE_RANGES, "30d");

  fillSelect($("citySelect"), keys, cityDefault);
  fillSelect($("compareA"), keys, aDefault);
  fillSelect($("compareB"), keys, bDefault);
  fillSelect($("compareC"), keys, cDefault, true);
  $("cityPeriod").value = periodDefault;
  $("comparePeriod").value = compareDefault;
  $("timeOfDayRange").value = heatmapDefault;
  $("compareTimeOfDayRange").value = compareTimeOfDayDefault;
  $("allCitiesRange").value = allCitiesRangeDefault;

  const generated = state.data.meta?.generated_at || state.data.cities?.kyiv?.meta?.generated_at;
  $("updatedAt").textContent = generated ? `Дані згенеровано ${String(generated).replace("T", " ").slice(0, 19)}` : "";

  renderDatasetSummary();
  renderFreshness();
  renderMethodology();
  bind();
  renderCity();
  renderComparison();
  renderAllCitiesTable();
  maybeStartIntroTour();
}

init().catch(err => {
  console.error(err);
  $("freshnessBanner").textContent = `Не вдалося завантажити сайт: ${err.message}`;
  $("freshnessBanner").classList.remove("hidden");
});

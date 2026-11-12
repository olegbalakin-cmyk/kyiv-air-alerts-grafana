/* Isolated overlay for the EXACT site-prod frontend. Never ship as production code.
 * Inject after app.js, while the asynchronous init() is loading local data.
 * No changes to the real casualty JSON, reviewer, generator, or alert charts.
 */
(function (root) {
  "use strict";
  const INCOMPLETE = "INCOMPLETE";
  const COMPLETE = "COMPLETE";
  const UNKNOWN = "UNKNOWN";
  const LEGACY = "LEGACY_UNVERIFIED";
  const MONTHS_UK = ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"];
  const MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function monthKey(row) {
    return String(row && (row.month || row.time) || "").slice(0, 7);
  }
  function integer(value) {
    return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
  }
  function normalize(row) {
    const month = monthKey(row);
    const status = row && row.coverage_status;
    if (status === INCOMPLETE) {
      if (!integer(row.confirmed_minimum) || row.confirmed_minimum === 0 || row.deaths != null) {
        throw new Error("INCOMPLETE requires a positive confirmed_minimum and deaths:null");
      }
      return { month: month, status: INCOMPLETE, value: row.confirmed_minimum,
        minimum: row.confirmed_minimum, value_kind: "confirmed_lower_bound_not_final",
        sourceMonths: [month] };
    }
    if (status === UNKNOWN) {
      if (row.deaths != null || row.confirmed_minimum != null) {
        throw new Error("UNKNOWN requires deaths:null and no confirmed minimum");
      }
      return { month: month, status: UNKNOWN, value: null, minimum: null,
        value_kind: "unknown_not_zero", sourceMonths: [month] };
    }
    if (status === COMPLETE) {
      if (!integer(row.deaths) || row.confirmed_minimum != null) {
        throw new Error("COMPLETE requires an explicitly verified integer");
      }
      return { month: month, status: COMPLETE, value: row.deaths, minimum: null,
        value_kind: "verified_final", sourceMonths: [month] };
    }
    if (status !== undefined && status !== null && status !== "") {
      throw new Error("Unknown casualty coverage status: " + status);
    }
    // Existing production rows have no coverage classification. Preserve the
    // published numeric chart, but never silently certify these rows COMPLETE.
    if (!row || row.deaths == null || !integer(row.deaths)) {
      return { month: month, status: UNKNOWN, value: null, minimum: null,
        value_kind: "unknown_not_zero", sourceMonths: [month] };
    }
    return { month: month, status: LEGACY, value: row.deaths, minimum: null,
      value_kind: "reconstructed_ungraded", sourceMonths: [month] };
  }
  function aggregateYear(rows, year) {
    const source = rows.filter(function (r) { return monthKey(r).slice(0, 4) === year; }).map(normalize);
    if (!source.length) return { year: year, status: UNKNOWN, value: null,
      minimum: null, value_kind: "unknown_not_zero", sourceMonths: [] };
    const known = source.filter(function (r) { return r.value !== null; });
    if (!known.length) return { year: year, status: UNKNOWN, value: null,
      minimum: null, value_kind: "unknown_not_zero", sourceMonths: source.map(function (r) { return r.month; }) };
    const sum = known.reduce(function (n, r) { return n + r.value; }, 0);
    const months = new Set(source.map(function (r) { return r.month; }));
    // A final annual total is allowed only with twelve distinct explicitly COMPLETE months.
    const allComplete = months.size === 12 && source.length === 12 &&
      source.every(function (r) { return r.status === COMPLETE; });
    const allLegacy = source.every(function (r) { return r.status === LEGACY; });
    const status = allComplete ? COMPLETE : allLegacy ? LEGACY : INCOMPLETE;
    const valueKind = status === COMPLETE ? "verified_final" :
      status === LEGACY ? "reconstructed_ungraded" : "confirmed_lower_bound_not_final";
    return { year: year, status: status, value: sum,
      minimum: status === INCOMPLETE ? sum : null, value_kind: valueKind,
      sourceMonths: source.filter(function (r) { return r.status === INCOMPLETE || r.status === UNKNOWN; })
        .map(function (r) { return r.month; }) };
  }
  function monthLabel(month, english) {
    const parts = String(month || "").split("-");
    const n = Number(parts[1]);
    if (!/^\d{4}-\d{2}$/.test(month) || n < 1 || n > 12) return month;
    return (english ? MONTHS_EN[n - 1] : MONTHS_UK[n - 1]) + " " + parts[0];
  }
  const api = { INCOMPLETE: INCOMPLETE, COMPLETE: COMPLETE, UNKNOWN: UNKNOWN, LEGACY: LEGACY,
    normalize: normalize, aggregateYear: aggregateYear, monthKey: monthKey, monthLabel: monthLabel };
  root.CasualtyCoveragePreview = api;
  if (typeof module === "object" && module.exports) module.exports = api;

  if (!root.document) return; // Node pure-function tests
  if (typeof root.setChart !== "function" || typeof root.renderCasualties !== "function" ||
      typeof root.renderComparison !== "function" || typeof root.exportChartCsv !== "function") {
    throw new Error("site-prod chart functions are missing: preview is deliberately fail-closed");
  }

  function localized(uk, en) { return root.document.documentElement.lang === "en" || currentLanguage === "en" ? en : uk; }
  function selectedKeys(chartId) {
    if (chartId === "casualtyChart") return [root.document.getElementById("citySelect").value];
    return ["compareA", "compareB", "compareC"].map(function (id) {
      return root.document.getElementById(id).value;
    }).filter(Boolean);
  }
  function metadataFor(chartId, labels, dataset, position) {
    const keys = selectedKeys(chartId).filter(function (key) {
      return Boolean(state.data.casualties_by_city && state.data.casualties_by_city[key] &&
        state.data.casualties_by_city[key].monthly);
    });
    let key = keys.find(function (k) { return labelFor(k) === dataset.label; });
    if (!key) key = keys[position];
    if (chartId === "casualtyChart") key = selectedKeys(chartId)[0];
    const series = (state.data.casualties_by_city || {})[key] ||
      (key === "kyiv" ? state.data.casualties : null);
    const all = (series && series.monthly) || [];
    const yearly = root.document.getElementById(
      chartId === "casualtyChart" ? "casualtyInterval" : "compareCasualtyInterval"
    ).value === "yearly";
    const byMonth = new Map(all.map(function (r) { return [monthKey(r), r]; }));
    return labels.map(function (label) {
      if (yearly) return aggregateYear(all, String(label));
      const row = byMonth.get(String(label));
      return row ? normalize(row) : normalize({ month: String(label), coverage_status: UNKNOWN, deaths: null });
    });
  }
  const hatchPlugin = {
    id: "casualtyConfirmedMinimumOverlay",
    afterDatasetsDraw: function (chart) {
      const ctx = chart.ctx;
      if (!chart.chartArea) return;
      const parts = [];
      chart.data.datasets.forEach(function (dataset, idx) {
        const meta = chart.getDatasetMeta(idx);
        (dataset._coverageRows || []).forEach(function (info, i) {
          if (info.status !== INCOMPLETE || info.value === null) return;
          const element = meta.data[i];
          if (!element) return;
          const p = element.getProps(["x", "y", "base", "width"], true);
          if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) return;
          const left = p.x - p.width / 2;
          const top = Math.min(p.y, p.base);
          const bottom = Math.max(p.y, p.base);
          const width = p.width;
          ctx.save();
          ctx.beginPath();
          ctx.rect(left, top, width, Math.max(1, bottom - top));
          ctx.clip();
          ctx.strokeStyle = "#f8e45c";
          ctx.lineWidth = 1.4;
          for (let x = left - (bottom - top); x < left + width + (bottom - top); x += 9) {
            ctx.beginPath(); ctx.moveTo(x, bottom); ctx.lineTo(x + bottom - top, top); ctx.stroke();
          }
          ctx.restore();
          ctx.save();
          ctx.textAlign = "center";
          ctx.fillStyle = "#f8e45c";
          ctx.font = "bold 13px system-ui, sans-serif";
          ctx.fillText("≥" + info.value, p.x, Math.max(chart.chartArea.top + 35, top - 7));
          ctx.restore();
          parts.push(info);
        });
      });
      if (parts.length) {
        ctx.save();
        ctx.fillStyle = "#f8e45c";
        ctx.font = "12px system-ui, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(localized("≥ — підтверджений мінімум; дані неповні",
          "≥ — confirmed minimum; incomplete data"), chart.chartArea.left + 6,
          chart.chartArea.top + 14);
        ctx.restore();
      }
    }
  };
  function coverageTooltip(extra) {
    const options = Object.assign({}, extra || {});
    const plugins = Object.assign({}, options.plugins || {});
    const tooltip = Object.assign({}, plugins.tooltip || {});
    const callbacks = Object.assign({}, tooltip.callbacks || {});
    callbacks.label = function (ctx) {
      const item = ctx.dataset._coverageRows && ctx.dataset._coverageRows[ctx.dataIndex];
      const name = ctx.dataset.label || localized("Загиблих", "Deaths");
      if (!item) return name + ": " + ctx.formattedValue;
      if (item.status === INCOMPLETE) return name + ": " +
        localized("щонайменше ", "at least ") + item.value +
        localized(" загиблих (дані неповні)", " deaths (incomplete data)");
      if (item.status === UNKNOWN) return name + ": " + localized("невідомо", "unknown");
      return name + ": " + ctx.formattedValue;
    };
    callbacks.footer = function (items) {
      const partial = items.map(function (entry) {
        return entry.dataset._coverageRows && entry.dataset._coverageRows[entry.dataIndex];
      }).find(function (v) { return v && v.status === INCOMPLETE; });
      if (!partial) return "";
      const m = partial.sourceMonths && partial.sourceMonths.find(function (value) {
        return /^\d{4}-\d{2}$/.test(value);
      });
      return (m ? monthLabel(m, currentLanguage === "en") + ". " : "") +
        localized("Це нижня межа, а не остаточний підсумок.",
          "This is a lower bound, not a final total.");
    };
    tooltip.callbacks = callbacks;
    plugins.tooltip = tooltip;
    options.plugins = plugins;
    options.chartPlugins = (options.chartPlugins || []).concat(hatchPlugin);
    return options;
  }
  const priorSetChart = root.setChart;
  root.setChart = function (id, labels, datasets, yTitle, type, extra) {
    if (id !== "casualtyChart" && id !== "compareCasualtiesChart") {
      return priorSetChart.apply(this, arguments);
    }
    const decorated = datasets.map(function (dataset, index) {
      const rows = metadataFor(id, labels, dataset, index);
      const originalColor = dataset.backgroundColor;
      const originalBorder = dataset.borderColor;
      return Object.assign({}, dataset, {
        data: rows.map(function (r) { return r.value; }),
        backgroundColor: rows.map(function (r) {
          return r.status === INCOMPLETE ? "rgba(248, 229, 92, .23)" : originalColor;
        }),
        borderColor: rows.map(function (r) {
          return r.status === INCOMPLETE ? "#f8e45c" : originalBorder;
        }),
        _coverageRows: rows
      });
    });
    return priorSetChart.call(this, id, labels, decorated, yTitle, type, coverageTooltip(extra));
  };

  function noteText(info, label) {
    const english = currentLanguage === "en";
    if (info.status === INCOMPLETE) {
      const m = (info.sourceMonths || []).find(function (v) { return /^\d{4}-\d{2}$/.test(v); });
      const caption = m ? monthLabel(m, english) :
        (/^\d{4}-\d{2}$/.test(label) ? monthLabel(label, english) : label);
      return english ? caption + " — at least " + info.value + " deaths. Incomplete data." :
        caption + " — щонайменше " + info.value + " загиблих. Дані неповні.";
    }
    if (info.status === UNKNOWN) {
      return english ? label + " — unknown: insufficient evidence even for a minimum." :
        label + " — невідомо: немає підтвердженого мінімуму.";
    }
    return "";
  }
  function refreshNote(id) {
    const chart = state.charts[id];
    const card = root.document.getElementById(id).closest(".chart-card");
    let node = card.querySelector(".casualty-coverage-note");
    const messages = [];
    if (chart) chart.data.datasets.forEach(function (dataset) {
      (dataset._coverageRows || []).forEach(function (info, index) {
        const msg = noteText(info, chart.data.labels[index]);
        if (msg && !messages.includes(msg)) messages.push(msg);
      });
    });
    if (!messages.length) { if (node) node.remove(); return; }
    if (!node) {
      node = root.document.createElement("p");
      node.className = "casualty-coverage-note";
      node.setAttribute("aria-live", "polite");
      node.style.cssText = "margin:8px 0 2px;font-size:12px;line-height:1.55;color:#f8e45c;";
      card.appendChild(node); // Moves with the existing card in embed.
    }
    const shown = messages.slice(0, 2);
    node.textContent = shown.join(" ") + (messages.length > 2 ?
      localized(" Є й інші неповні/невідомі періоди.", " Other incomplete/unknown periods exist.") : "");
  }
  const priorRenderCasualties = root.renderCasualties;
  root.renderCasualties = function (key) {
    const result = priorRenderCasualties.call(this, key);
    const chart = state.charts.casualtyChart;
    if (chart && chart.data.datasets.some(function (d) {
      return (d._coverageRows || []).some(function (r) { return r.status === INCOMPLETE || r.status === UNKNOWN; });
    })) {
      const source = root.document.getElementById("casualtySourceNote");
      source.textContent = localized(
        "Є підтверджені мінімуми або невідомі місяці. Остаточний підсумок загиблих за весь період невідомий; окремі реконструйовані значення не підтверджують повноту.",
        "Some months have confirmed minima or unknown coverage. The final overall total is unknown; reconstructed figures do not establish complete coverage."
      );
    }
    refreshNote("casualtyChart");
    return result;
  };
  const priorRenderComparison = root.renderComparison;
  root.renderComparison = function () {
    const result = priorRenderComparison.apply(this, arguments);
    refreshNote("compareCasualtiesChart");
    const chart = state.charts.compareCasualtiesChart;
    if (chart && chart.data.datasets.some(function (d) {
      return (d._coverageRows || []).some(function (r) { return r.status === INCOMPLETE; });
    })) {
      root.document.getElementById("compareCasualtiesNote").textContent += localized(
        " Позначка ≥ — підтверджений мінімум, не фінальна місячна чи річна сума.",
        " ≥ indicates a confirmed minimum, not a final monthly or yearly total."
      );
    }
    return result;
  };

  const priorCsv = root.exportChartCsv;
  root.exportChartCsv = function (id) {
    if (id !== "casualtyChart" && id !== "compareCasualtiesChart") {
      return priorCsv.call(this, id);
    }
    const chart = state.charts[id];
    if (!chart) return;
    const visible = visibleChartDatasets(chart);
    const classified = visible.some(function (entry) {
      return (entry.dataset._coverageRows || []).some(function (r) {
        return r.status === INCOMPLETE || r.status === UNKNOWN || r.status === COMPLETE;
      });
    });
    if (!classified) return priorCsv.call(this, id); // Original CSV byte semantics for legacy-only rows
    const columns = [CSV_CHART_CONFIG[id].labelHeader || "period"];
    visible.forEach(function (entry) {
      const label = entry.dataset.label || "deaths";
      columns.push(label, label + " [coverage_status]", label + " [value_kind]",
        label + " [confirmed_minimum]");
    });
    const rows = chart.data.labels.map(function (label, index) {
      const result = [label];
      visible.forEach(function (entry) {
        const info = entry.dataset._coverageRows[index];
        result.push(info.value == null ? "" : info.value, info.status,
          info.value_kind, info.minimum == null ? "" : info.minimum);
      });
      return result;
    });
    triggerCsvDownload(exportContextParts(id, CSV_CHART_CONFIG[id].slug), columns, rows);
  };
})(typeof window === "undefined" ? globalThis : window);

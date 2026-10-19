/* Chart-level share links for the isolated site preview. No data or images are uploaded. */
(function (root) {
  "use strict";

  const HASH_PATTERN = /^#chart-([A-Za-z][A-Za-z0-9]*Chart)(?:\.([01]{1,64}))?$/;
  let settings = null;

  function parseSharedView(hash, allowedChartIds) {
    const match = HASH_PATTERN.exec(String(hash || ""));
    if (!match || !allowedChartIds.includes(match[1])) return null;
    return { chartId: match[1], visibility: match[2] || "" };
  }

  function visibilityBits(chart) {
    const datasets = chart && chart.data && chart.data.datasets;
    if (!Array.isArray(datasets) || datasets.length > 64) return "";
    return datasets.map((dataset, index) => chart.isDatasetVisible(index) ? "1" : "0").join("");
  }

  function makeShareUrl(currentHref, chartId, chart) {
    if (!/^[A-Za-z][A-Za-z0-9]*Chart$/.test(chartId)) {
      throw new Error("Invalid chart ID");
    }
    const url = new URL(currentHref);
    const bits = visibilityBits(chart);
    url.hash = "chart-" + chartId + (bits.includes("0") ? "." + bits : "");
    return url.toString();
  }

  function restoreVisibility(chart, bits) {
    const datasets = chart && chart.data && chart.data.datasets;
    if (!bits || !/^[01]{1,64}$/.test(bits) ||
        !Array.isArray(datasets) || bits.length !== datasets.length ||
        typeof chart.setDatasetVisibility !== "function" ||
        typeof chart.update !== "function") return false;
    for (let index = 0; index < bits.length; index += 1) {
      chart.setDatasetVisibility(index, bits[index] === "1");
    }
    chart.update("none");
    return true;
  }

  function translated(uk, en) {
    return settings && settings.language() === "en" ? en : uk;
  }

  function showStatus(button, uk, en) {
    const label = button.querySelector(".chart-share-label");
    if (!label) return;
    const original = translated("Поділитися", "Share");
    label.textContent = translated(uk, en);
    root.setTimeout(function () { label.textContent = original; }, 1800);
  }

  function makeButton(chartId, card) {
    const button = root.document.createElement("button");
    button.type = "button";
    button.className = "csv-export-button chart-share-button";
    button.dataset.shareChart = chartId;
    button.setAttribute("aria-label", translated("Поділитися поточним виглядом графіка", "Share this chart's current view"));
    button.title = translated(
      "Скопіювати посилання або поділитися графіком з поточними фільтрами й видимими серіями",
      "Share a link with the current filters and visible chart series"
    );
    button.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.1 0l2.1-2.1a5 5 0 0 0-7.1-7.1L10.7 5.2"/><path d="M14 11a5 5 0 0 0-7.1 0l-2.1 2.1a5 5 0 0 0 7.1 7.1l1.4-1.4"/></svg><span class="chart-share-label"></span>';
    button.querySelector(".chart-share-label").textContent = translated("Поділитися", "Share");

    button.addEventListener("click", async function () {
      const chart = settings.getChart(chartId);
      if (!chart) {
        showStatus(button, "Немає графіка", "Unavailable");
        return;
      }
      settings.syncUrl();
      const url = makeShareUrl(root.location.href, chartId, chart);
      const title = card.querySelector("h3")?.textContent ||
        card.closest(".comparison-section")?.querySelector("h2")?.textContent ||
        translated("Повітряні тривоги", "Air alerts");

      if (typeof root.navigator.share === "function") {
        try {
          await root.navigator.share({ title, url });
          return;
        } catch (error) {
          if (error && error.name === "AbortError") return;
        }
      }
      try {
        if (!root.navigator.clipboard ||
            typeof root.navigator.clipboard.writeText !== "function") {
          throw new Error("Clipboard unavailable");
        }
        await root.navigator.clipboard.writeText(url);
        showStatus(button, "Скопійовано", "Copied");
      } catch (error) {
        if (typeof root.prompt === "function") {
          root.prompt(translated("Скопіюйте посилання на графік:", "Copy this chart link:"), url);
        } else {
          showStatus(button, "Не вдалося", "Failed");
        }
      }
    });
    return button;
  }

  function setup(options) {
    settings = options;
    for (const chartId of options.chartIds) {
      const canvas = root.document.getElementById(chartId);
      const card = canvas?.closest(".chart-card");
      const wrap = canvas?.closest(".chart-wrap");
      if (!card || !wrap) continue;
      wrap.id = "chart-" + chartId;
      let row = card.querySelector('[data-csv-chart="' + chartId + '"]');
      if (!row) {
        row = root.document.createElement("div");
        row.className = "chart-export-row";
        card.insertBefore(row, wrap);
      }
      if (!row.querySelector('[data-share-chart="' + chartId + '"]')) {
        row.appendChild(makeButton(chartId, card));
      }
    }
  }

  function restore() {
    if (!settings) return false;
    const requested = parseSharedView(root.location.hash, settings.chartIds);
    if (!requested) return false;
    const chart = settings.getChart(requested.chartId);
    const card = root.document.getElementById(requested.chartId)?.closest(".chart-card");
    if (!chart || !card || card.closest(".hidden")) return false;
    restoreVisibility(chart, requested.visibility);
    card.classList.add("shared-chart-target");
    root.requestAnimationFrame(function () {
      card.scrollIntoView({ behavior: "auto", block: "center", inline: "nearest" });
    });
    return true;
  }

  const api = { parseSharedView, visibilityBits, makeShareUrl, restoreVisibility, setup, restore };
  root.ChartShare = api;
  if (typeof module === "object" && module.exports) module.exports = api;
}(typeof window === "undefined" ? globalThis : window));

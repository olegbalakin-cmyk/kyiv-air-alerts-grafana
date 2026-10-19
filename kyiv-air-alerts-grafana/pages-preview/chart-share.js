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


  function selectedText(id) {
    const input = root.document.getElementById(id);
    if (!input || !input.value) return "";
    if (input.tagName === "SELECT") {
      return (input.selectedOptions && input.selectedOptions[0]?.textContent || input.value).trim();
    }
    return String(input.value).trim();
  }

  function chartContext(chartId) {
    const compared = chartId.startsWith("compare");
    const ids = compared ? ["compareA", "compareB", "compareC"] : ["citySelect"];
    const cities = ids.map(selectedText).filter(Boolean);
    const options = [];
    if (["heavyDaysChart", "extremesChart"].includes(chartId)) {
      options.push(selectedText("burdenYear"));
      if (chartId === "heavyDaysChart" && root.document.getElementById("heavyDaysExcludeZero")?.checked) {
        options.push(translated("Лише дні з тривогою", "Alert days only"));
      }
    } else if (chartId === "daypartChart") {
      options.push(selectedText("daypartMode"), selectedText("daypartYear"));
    } else if (chartId === "timeOfDayChart") {
      options.push([...root.document.querySelectorAll(".time-of-day-range-option:checked")]
        .map(el => el.nextElementSibling?.textContent?.trim() || el.value).join(", "));
      options.push(selectedText("timeOfDayBin"));
    } else if (chartId === "casualtyChart" || chartId === "compareCasualtiesChart") {
      const prefix = compared ? "compareCasualty" : "casualty";
      options.push(selectedText(prefix + "Interval"), selectedText(prefix + "Year"));
    } else if (chartId === "compareTimeOfDayChart") {
      options.push(selectedText("compareTimeOfDayRange"), selectedText("compareTimeOfDayBin"));
    } else if (chartId === "kyivThreatCausesChart") {
      options.push(translated("Причини тривог", "Alert causes"));
    } else {
      options.push(selectedText(compared ? "comparePeriod" : "cityPeriod"));
      const from = selectedText(compared ? "compareDateFrom" : "cityDateFrom");
      const to = selectedText(compared ? "compareDateTo" : "cityDateTo");
      if (from || to) options.push([from || "…", to || "…"].join(" — "));
    }
    return [...cities, ...options].filter(Boolean).join(" · ");
  }

  function fitCanvasText(ctx, value, width) {
    let text = String(value || "");
    if (ctx.measureText(text).width <= width) return text;
    while (text && ctx.measureText(text + "…").width > width) text = text.slice(0, -1);
    return text + "…";
  }

  function renderChartPng(chartId, card) {
    const source = root.document.getElementById(chartId);
    if (!source || source.width < 1 || source.height < 1) {
      throw new Error("Chart canvas unavailable");
    }
    const title = card.querySelector("h3")?.textContent?.trim() ||
      card.closest(".comparison-section")?.querySelector("h2")?.textContent?.trim() ||
      translated("Повітряні тривоги", "Air alerts");
    const caption = chartContext(chartId);
    const size = { width: 1440, inset: 64, maxChartHeight: 820, chartTop: 222 };
    const usableWidth = size.width - 2 * size.inset;
    const factor = Math.min(usableWidth / source.width, size.maxChartHeight / source.height);
    const drawnWidth = Math.round(source.width * factor);
    const drawnHeight = Math.round(source.height * factor);
    const output = root.document.createElement("canvas");
    output.width = size.width;
    output.height = size.chartTop + drawnHeight + 142;
    const ctx = output.getContext("2d", { alpha: false });
    if (!ctx) throw new Error("PNG canvas context unavailable");

    ctx.fillStyle = "#0b0f14";
    ctx.fillRect(0, 0, output.width, output.height);
    ctx.fillStyle = "#62a0ea";
    ctx.font = "700 20px Inter, system-ui, sans-serif";
    ctx.fillText(translated("ПОВІТРЯНІ ТРИВОГИ · ГРАФІК", "AIR ALERTS · CHART"), size.inset, 55);
    ctx.fillStyle = "#e7edf3";
    ctx.font = "700 43px Inter, system-ui, sans-serif";
    ctx.fillText(fitCanvasText(ctx, title, usableWidth), size.inset, 118);
    ctx.fillStyle = "#aabcca";
    ctx.font = "25px Inter, system-ui, sans-serif";
    ctx.fillText(fitCanvasText(ctx, caption, usableWidth), size.inset, 168);

    ctx.drawImage(source,
      size.inset + Math.round((usableWidth - drawnWidth) / 2), size.chartTop,
      drawnWidth, drawnHeight);
    const footerY = size.chartTop + drawnHeight + 65;
    ctx.fillStyle = "#7592a5";
    ctx.fillRect(size.inset, footerY - 24, usableWidth, 1);
    ctx.fillStyle = "#b8c4cf";
    ctx.font = "20px Inter, system-ui, sans-serif";
    const stamp = new Intl.DateTimeFormat(
      translated("uk-UA", "en-GB"), {
        timeZone: "Europe/Kyiv", dateStyle: "medium", timeStyle: "short"
      }
    ).format(new Date());
    ctx.fillText(
      fitCanvasText(ctx, translated("Знімок: ", "Snapshot: ") + stamp +
        " · Europe/Kyiv", usableWidth), size.inset, footerY + 12);
    ctx.fillStyle = "#7592a5";
    ctx.font = "18px Inter, system-ui, sans-serif";
    ctx.fillText(root.location.hostname, size.inset, footerY + 47);
    const dataUrl = output.toDataURL("image/png");
    if (!dataUrl.startsWith("data:image/png;base64,")) {
      throw new Error("Browser did not produce PNG");
    }
    const filename = "air-alerts_" + chartId.replace(/Chart$/, "").toLowerCase() +
      "_" + new Date().toISOString().slice(0, 10) + ".png";
    return { dataUrl, filename, title, caption, width: output.width, height: output.height };
  }

  function pngFile(dataUrl, filename) {
    if (!/^data:image\/png;base64,/.test(dataUrl)) throw new Error("Invalid PNG URL");
    const data = root.atob(dataUrl.slice("data:image/png;base64,".length));
    const bytes = new Uint8Array(data.length);
    for (let i = 0; i < data.length; i++) bytes[i] = data.charCodeAt(i);
    return new root.File([bytes], filename, { type: "image/png" });
  }

  function downloadPng(file) {
    const url = root.URL.createObjectURL(file);
    const a = root.document.createElement("a");
    a.href = url;
    a.download = file.name;
    root.document.body.appendChild(a);
    a.click();
    a.remove();
    root.setTimeout(() => root.URL.revokeObjectURL(url), 30000);
  }

  function makeImageButton(chartId, card) {
    const button = root.document.createElement("button");
    button.type = "button";
    button.className = "csv-export-button chart-image-button";
    button.dataset.shareImage = chartId;
    button.setAttribute("aria-label", translated(
      "Поділитися зображенням поточного графіка", "Share a PNG image of this chart"));
    button.title = translated(
      "Надіслати PNG або скопіювати зображення для вставлення в чат",
      "Send the PNG or copy the image to paste into a chat");
    button.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="m3 17 5-5 4 4 3-3 6 5"/></svg><span class="chart-share-label"></span>';
    button.querySelector(".chart-share-label").textContent = translated("Картинка", "Image");

    button.addEventListener("click", async function () {
      const chart = settings.getChart(chartId);
      if (!chart || card.closest(".hidden")) {
        showStatus(button, "Немає графіка", "Unavailable", "Картинка", "Image");
        return;
      }
      let image, file, shareUrl;
      try {
        settings.syncUrl();
        shareUrl = makeShareUrl(root.location.href, chartId, chart);
        image = renderChartPng(chartId, card);
        file = pngFile(image.dataUrl, image.filename);
      } catch (error) {
        root.console?.warn("PNG chart share unavailable", error);
        showStatus(button, "Помилка PNG", "PNG failed", "Картинка", "Image");
        return;
      }

      const navigator = root.navigator;
      if (typeof navigator.share === "function" && typeof navigator.canShare === "function" &&
          navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({
            files: [file], title: image.title, text: shareUrl
          });
          return;
        } catch (error) {
          if (error?.name === "AbortError") return;
        }
      }
      if (typeof navigator.clipboard?.write === "function" &&
          typeof root.ClipboardItem === "function") {
        try {
          await navigator.clipboard.write([new root.ClipboardItem({ "image/png": file })]);
          showStatus(button, "PNG скопійовано", "PNG copied", "Картинка", "Image");
          return;
        } catch (error) {
          // Browser denied image clipboard; let the user download instead.
        }
      }
      try {
        downloadPng(file);
        showStatus(button, "PNG завантажено", "PNG downloaded", "Картинка", "Image");
      } catch (error) {
        root.console?.warn("PNG download failed", error);
        showStatus(button, "Не вдалося", "Failed", "Картинка", "Image");
      }
    });
    return button;
  }

  function translated(uk, en) {
    return settings && settings.language() === "en" ? en : uk;
  }

  function showStatus(button, uk, en, defaultUk = "Поділитися", defaultEn = "Share") {
    const label = button.querySelector(".chart-share-label");
    if (!label) return;
    const original = translated(defaultUk, defaultEn);
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
      if (!row.querySelector('[data-share-image="' + chartId + '"]')) {
        row.appendChild(makeImageButton(chartId, card));
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

  const api = { parseSharedView, visibilityBits, makeShareUrl, restoreVisibility, chartContext, renderChartPng, pngFile, setup, restore };
  root.ChartShare = api;
  if (typeof module === "object" && module.exports) module.exports = api;
}(typeof window === "undefined" ? globalThis : window));

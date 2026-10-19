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


  // Approved logo #12: navy tile, white bell, inner yellow and outer blue waves.
  // The same vector geometry and palette are shipped as brand-mark.svg.
  function drawBrandMark(ctx, x, y, size) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(size / 256, size / 256);
    ctx.fillStyle = "#0B1E3A";
    ctx.beginPath();
    if (typeof ctx.roundRect === "function") ctx.roundRect(0, 0, 256, 256, 52);
    else ctx.rect(0, 0, 256, 256);
    ctx.fill();
    ctx.translate(8, 8);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#F6F8FC";
    ctx.lineWidth = 13;
    ctx.beginPath();
    ctx.moveTo(67, 175);
    ctx.bezierCurveTo(60, 175, 59, 168, 65, 161);
    ctx.lineTo(72, 151);
    ctx.bezierCurveTo(82, 136, 83, 121, 83, 109);
    ctx.lineTo(83, 94);
    ctx.bezierCurveTo(83, 68, 99, 51, 120, 51);
    ctx.bezierCurveTo(143, 51, 156, 68, 156, 94);
    ctx.lineTo(156, 109);
    ctx.bezierCurveTo(156, 126, 159, 141, 170, 155);
    ctx.lineTo(178, 165);
    ctx.bezierCurveTo(182, 170, 179, 175, 172, 175);
    ctx.closePath();
    ctx.moveTo(110, 184);
    ctx.bezierCurveTo(115, 195, 126, 195, 131, 184);
    ctx.stroke();
    ctx.fillStyle = "#F6F8FC";
    ctx.beginPath(); ctx.arc(120, 50, 9, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#FFD000";
    ctx.lineWidth = 15;
    ctx.beginPath(); ctx.moveTo(177, 59); ctx.bezierCurveTo(190, 71, 198, 89, 197, 109); ctx.stroke();
    ctx.strokeStyle = "#007BFF";
    ctx.lineWidth = 16;
    ctx.beginPath(); ctx.moveTo(185, 27); ctx.bezierCurveTo(213, 44, 225, 71, 226, 109); ctx.stroke();
    ctx.restore();
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
    const size = { width: 1440, inset: 64, maxChartHeight: 820, chartTop: 260 };
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
    drawBrandMark(ctx, size.inset, 30, 62);
    ctx.fillStyle = "#62a0ea";
    ctx.font = "700 20px Inter, system-ui, sans-serif";
    ctx.fillText(translated("ПОВІТРЯНІ ТРИВОГИ · ГРАФІК", "AIR ALERTS · CHART"), size.inset + 84, 65);
    ctx.fillStyle = "#e7edf3";
    ctx.font = "700 43px Inter, system-ui, sans-serif";
    ctx.fillText(fitCanvasText(ctx, title, usableWidth), size.inset, 157);
    ctx.fillStyle = "#aabcca";
    ctx.font = "25px Inter, system-ui, sans-serif";
    ctx.fillText(fitCanvasText(ctx, caption, usableWidth), size.inset, 209);

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
    ctx.fillText("https://" + root.location.hostname + "/", size.inset, footerY + 47);
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
    button.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/></svg><span class="chart-share-label"></span>';
    button.querySelector(".chart-share-label").textContent = translated("Поділитися", "Share");

    button.addEventListener("click", async function () {
      const chart = settings.getChart(chartId);
      if (!chart || card.closest(".hidden")) {
        showStatus(button, "Немає графіка", "Unavailable");
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
        showStatus(button, "Помилка PNG", "PNG failed");
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
          showStatus(button, "PNG скопійовано", "PNG copied");
          return;
        } catch (error) {
          // Browser denied image clipboard; let the user download instead.
        }
      }
      try {
        downloadPng(file);
        showStatus(button, "PNG завантажено", "PNG downloaded");
      } catch (error) {
        root.console?.warn("PNG download failed", error);
        showStatus(button, "Не вдалося", "Failed");
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


  // An embed is a live, read-only view of one configured Chart.js panel.
  // The full URL contains the same filters and series visibility as chart sharing.
  function makeEmbedUrl(currentHref, chartId, chart) {
    const url = new URL(makeShareUrl(currentHref, chartId, chart));
    url.searchParams.set("embed", chartId);
    return url.toString();
  }

  function escapeAttribute(value) {
    return String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function makeEmbedHtml(currentHref, chartId, chart, title) {
    const src = escapeAttribute(makeEmbedUrl(currentHref, chartId, chart));
    const caption = escapeAttribute(title ||
      translated("Графік повітряних тривог", "Air alert chart"));
    return '<iframe src="' + src + '" title="' + caption +
      '" loading="lazy" width="100%" height="700" ' +
      'style="display:block;width:100%;max-width:100%;height:700px;border:0;border-radius:12px" ' +
      'referrerpolicy="strict-origin-when-cross-origin"></iframe>';
  }

  function makeEmbedButton(chartId, card) {
    const button = root.document.createElement("button");
    button.type = "button";
    button.className = "csv-export-button chart-embed-button";
    button.dataset.embedChart = chartId;
    button.setAttribute("aria-label", translated(
      "Скопіювати HTML-код для вбудовування цього графіка",
      "Copy the HTML embed code for this chart"));
    button.title = translated(
      "Скопіювати iframe-код графіка з поточними фільтрами",
      "Copy iframe code with current chart filters");
    button.innerHTML =
      '<svg aria-hidden="true" viewBox="0 0 24 24">' +
      '<path d="m8 5-7 7 7 7m8-14 7 7-7 7M14 3l-4 18"/></svg>' +
      '<span class="chart-share-label"></span>';
    button.querySelector(".chart-share-label").textContent =
      translated("Вбудувати", "Embed");

    button.addEventListener("click", async function () {
      const chart = settings.getChart(chartId);
      if (!chart || card.closest(".hidden")) {
        showStatus(button, "Немає графіка", "Unavailable", "Вбудувати", "Embed");
        return;
      }
      settings.syncUrl();
      const title = card.querySelector("h3")?.textContent ||
        card.closest(".comparison-section")?.querySelector("h2")?.textContent ||
        translated("Повітряні тривоги", "Air alerts");
      let code;
      try {
        code = makeEmbedHtml(root.location.href, chartId, chart, title);
      } catch (error) {
        showStatus(button, "Помилка", "Failed", "Вбудувати", "Embed");
        return;
      }
      try {
        await root.navigator.clipboard.writeText(code);
        showStatus(button, "Код скопійовано", "Code copied", "Вбудувати", "Embed");
      } catch (error) {
        if (typeof root.prompt === "function") {
          root.prompt(translated(
            "Скопіюйте iframe-код:", "Copy this iframe code:"), code);
        } else {
          showStatus(button, "Не вдалося", "Failed", "Вбудувати", "Embed");
        }
      }
    });
    return button;
  }

  function currentEmbedId() {
    if (!settings) return null;
    const value = new URL(root.location.href).searchParams.get("embed");
    return settings.chartIds.includes(value) ? value : null;
  }

  function activateEmbed() {
    const chartId = currentEmbedId();
    if (!chartId) return false;
    const main = root.document.querySelector("main");
    if (!main) return false;
    const canvas = root.document.getElementById(chartId);
    const card = canvas?.closest(".chart-card");
    const chart = settings.getChart(chartId);
    const oldTitle = card?.querySelector("h3")?.textContent ||
      card?.closest(".comparison-section")?.querySelector("h2")?.textContent ||
      translated("Повітряні тривоги", "Air alerts");

    const rootSection = root.document.createElement("section");
    rootSection.className = "embed-container";
    rootSection.setAttribute("aria-label", translated(
      "Вбудований графік повітряних тривог", "Embedded air alert chart"));

    if (!card || !chart || card.classList.contains("hidden") ||
        card.closest(".hidden")) {
      const unavailable = root.document.createElement("p");
      unavailable.className = "embed-unavailable";
      unavailable.textContent = translated(
        "Графік зараз недоступний. Відкрийте повну сторінку.",
        "Chart currently unavailable. Open the full dashboard.");
      rootSection.appendChild(unavailable);
    } else {
      const requested = parseSharedView(root.location.hash, settings.chartIds);
      if (requested && requested.chartId === chartId) {
        restoreVisibility(chart, requested.visibility);
      }
      const h = root.document.createElement("header");
      h.className = "embed-heading";
      const title = root.document.createElement("h2");
      title.textContent = oldTitle;
      const context = root.document.createElement("p");
      context.className = "embed-context";
      context.textContent = chartContext(chartId);
      h.appendChild(title);
      h.appendChild(context);
      rootSection.appendChild(h);
      rootSection.appendChild(card); // Move the original chart; do not copy its canvas.
      root.requestAnimationFrame(function () {
        chart.resize();
        chart.update("none");
      });
    }

    const footer = root.document.createElement("footer");
    footer.className = "embed-footer";
    const full = new URL(root.location.href);
    full.searchParams.delete("embed");

    const brandLink = root.document.createElement("a");
    brandLink.className = "embed-brand-link";
    brandLink.href = full.toString();
    brandLink.target = "_blank";
    brandLink.rel = "noopener noreferrer";
    brandLink.setAttribute("aria-label", translated(
      "Повітряні тривоги — відкрити джерело графіка",
      "Air alerts — open chart source"));

    const brandIcon = root.document.createElement("img");
    brandIcon.className = "embed-brand-icon";
    brandIcon.src = "brand-mark.svg?v=20261019-logo12-1";
    brandIcon.width = 40;
    brandIcon.height = 40;
    brandIcon.alt = "";
    brandIcon.setAttribute("aria-hidden", "true");
    const identity = root.document.createElement("span");
    identity.className = "embed-brand-identity";
    const brandName = root.document.createElement("strong");
    brandName.textContent = translated("Повітряні тривоги", "Air alerts");
    const sourceUrl = root.document.createElement("span");
    sourceUrl.className = "embed-brand-domain";
    sourceUrl.textContent = full.hostname;
    identity.appendChild(brandName);
    identity.appendChild(sourceUrl);
    brandLink.appendChild(brandIcon);
    brandLink.appendChild(identity);

    const link = root.document.createElement("a");
    link.className = "embed-open-chart";
    link.href = full.toString();
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = translated("Відкрити графік ↗", "Open full chart ↗");
    footer.appendChild(brandLink);
    footer.appendChild(link);
    rootSection.appendChild(footer);
    main.appendChild(rootSection);
    root.document.body.classList.add("embed-mode");
    return true;
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
      if (!row.querySelector('[data-share-image="' + chartId + '"]')) {
        row.appendChild(makeImageButton(chartId, card));
      }
      if (!row.querySelector('[data-embed-chart="' + chartId + '"]')) {
        row.appendChild(makeEmbedButton(chartId, card));
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

  const api = { parseSharedView, visibilityBits, makeShareUrl, restoreVisibility, chartContext, renderChartPng, pngFile, makeEmbedUrl, makeEmbedHtml, currentEmbedId, activateEmbed, setup, restore };
  root.ChartShare = api;
  if (typeof module === "object" && module.exports) module.exports = api;
}(typeof window === "undefined" ? globalThis : window));

/* October 2026: separate read-only incident minimum from existing monthly reconstruction.
   Research preview only; never writes to any casualty baseline or site-prod. */
(function(root) {
  "use strict";
  const MONTH = "2026-10";
  const SOURCES = Object.freeze({
    lutsk: "https://www.lutskrada.gov.ua/publications/u-lutsku-vnaslidok-vorozhoi-ataky-zahynuly-shestero-liudei-shche-12-travmovani",
    poltava: "https://rada-poltava.gov.ua/ua/news/u-poltavi-likviduvali-naslidki-vorozhoyi-ataki-17-zhovtnya",
    "ivano-frankivsk": "https://suspilne.media/ivano-frankivsk/1422981-vnaslidok-ataki-rosijskogo-reaktivnogo-bpla-po-ivano-frankivsku-zaginuv-colovik-marcinkiv/",
    khmelnytskyi: "https://www.khm.gov.ua/uk/all-news/tragichna-zvistka-dlya-gromadi-u-likarni-pomerla-zhinka-poranena-pid-chas-ataki-na"
  });
  function reject(reason) { throw new Error("Unsafe casualty partial preview: " + reason); }
  function validate(payload, originalSeries) {
    if (!payload || payload.schema !== "casualty-october-partial-review-v1" ||
        payload.month !== MONTH || payload.promotion !== "OFF" ||
        payload.display_policy !== "PREVIEW_ONLY_NO_SITE_MUTATION" ||
        payload.is_month_complete !== false || payload.no_automatic_credits !== true ||
        payload.no_production_changes !== true ||
        payload.NOT_an_October_23city_monthly_total !== true ||
        payload.confirmed_event_groups !== 4 ||
        payload.known_civilian_fatalities_from_these_events !== 11) reject("top-level contract");
    const keys = Object.keys(originalSeries || {}).sort();
    if (keys.length !== 23 || !Array.isArray(payload.cities) ||
        payload.cities.length !== 23 ||
        !Array.isArray(payload.incident_ids) ||
        new Set(payload.incident_ids).size !== 4 ||
        payload.incident_ids.length !== 4) reject("23-city/event coverage");
    const cities = {};
    let minSum = 0, verifiedGroups = 0, unknown = 0;
    for (const rec of payload.cities) {
      const slug = rec?.city_slug;
      if (!keys.includes(slug) || Object.hasOwn(cities, slug) ||
          rec.month !== MONTH || rec.monthly_exact_total !== null ||
          rec.published_monthly_total !== null || rec.is_final !== false ||
          rec.ready_for_monthly_data_publishing !== false) reject("city identity or exact-month fields");
      const baseline = originalSeries[slug]?.monthly;
      if (!Array.isArray(baseline) || !baseline.length ||
          baseline[baseline.length - 1]?.month !== "2026-09" ||
          baseline.some(row => row.month >= MONTH || row.is_partial_period === true))
        reject("baseline drift or an existing October entry: " + slug);
      if (rec.confirmed_event_lower_bound === null) {
        if (rec.coverage !== "NO_VERIFIED_EVENTS_UNKNOWN" || rec.event_count_verified !== 0)
          reject("unknown cannot be zero/verified");
        unknown++;
      } else {
        if (!Number.isSafeInteger(rec.confirmed_event_lower_bound) ||
            rec.confirmed_event_lower_bound <= 0 ||
            rec.event_count_verified !== 1 ||
            rec.coverage !== "PARTIAL_VERIFIED_EVENTS" || !SOURCES[slug])
          reject("invalid event lower bound");
        minSum += rec.confirmed_event_lower_bound;
        verifiedGroups++;
      }
      cities[slug] = Object.freeze({
        city_slug: slug, month: MONTH, lower_bound: rec.confirmed_event_lower_bound
      });
    }
    if (Object.keys(cities).length !== 23 || verifiedGroups !== 4 ||
        unknown !== 19 || minSum !== 11) reject("minimum or unknown count");
    for (const slug of keys) if (!Object.hasOwn(cities, slug)) reject("missing city " + slug);
    return Object.freeze({ month: MONTH, cities: Object.freeze(cities),
      verified_event_groups: verifiedGroups, verified_minimum: minSum });
  }
  function rows(originalMonthly, city, view) {
    if (!view) return originalMonthly || [];
    if (!Array.isArray(originalMonthly) || !view.cities[city]) reject("unknown series");
    const rec = view.cities[city];
    // No change to historic observations: an additional display-only row has deaths=null.
    return [...originalMonthly, {
      time: MONTH + "-01T00:00:00", month: MONTH,
      deaths: null, is_partial_period: true,
      confirmed_event_lower_bound: rec.lower_bound,
      _casualty_status: rec.lower_bound === null ?
        "unknown_not_zero" : "verified_incident_lower_bound_not_monthly_total"
    }];
  }
  function description(city, view, en) {
    const rec = view?.cities?.[city];
    if (!rec) return "";
    if (rec.lower_bound === null) {
      return en ? "October 2026 — data under review (not zero)."
                : "Жовтень 2026 — дані уточнюються (це не нуль).";
    }
    return en ? "October 2026 — at least " + rec.lower_bound + " confirmed. Not a full monthly total."
              : "Жовтень 2026 — щонайменше " + rec.lower_bound + " підтверджених. Не повний місячний підсумок.";
  }
  const api = Object.freeze({ validate, rows, description, sourceFor: city => SOURCES[city] || null });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CasualtyPartialPreview = api;
})(typeof window !== "undefined" ? window : globalThis);

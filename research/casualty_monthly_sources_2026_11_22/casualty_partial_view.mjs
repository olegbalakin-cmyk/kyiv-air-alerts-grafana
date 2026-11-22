/**
 * Presentation adapter for verified-but-incomplete casualty-month rows.
 * Does not modify existing exact monthly series. Research-only.
 */
export function partialCasualtyPresentation(preview, citySlug, language = "uk") {
  const en = language === "en";
  if (!preview || preview.schema !== "casualty-october-partial-review-v1" ||
      preview.promotion !== "OFF" || preview.is_month_complete !== false ||
      preview.no_automatic_credits !== true ||
      !Array.isArray(preview.cities) || preview.cities.length !== 23) {
    throw new Error("Invalid or unsafe partial preview schema");
  }
  const rec = preview.cities.find(c => c.city_slug === citySlug);
  if (!rec) throw new Error("Unknown city");
  if (rec.monthly_exact_total !== null || rec.published_monthly_total !== null ||
      rec.ready_for_monthly_data_publishing !== false || rec.is_final !== false) {
    throw new Error("Partial data cannot carry exact/publication-ready deaths");
  }
  const min = rec.confirmed_event_lower_bound;
  if (min === null) {
    if (rec.event_count_verified !== 0 || rec.coverage !== "NO_VERIFIED_EVENTS_UNKNOWN")
      throw new Error("Unknown month must be UNKNOWN, not zero");
    return {
      city: citySlug, month: rec.month, exact_deaths: null,
      lower_bound: null, chart_value: null, annual_exact_addition: null,
      is_partial: true, unknown: true,
      label: en ? "October 2026 — data under review" : "Жовтень 2026 — дані уточнюються",
      tooltip: en ? "No verified October value yet; this does not mean zero deaths."
                  : "За жовтень ще немає перевіреного значення; це не означає нуль загиблих.",
    };
  }
  if (!Number.isSafeInteger(min) || min <= 0 ||
      rec.event_count_verified < 1 || rec.coverage !== "PARTIAL_VERIFIED_EVENTS")
    throw new Error("Invalid lower bound");
  return {
    city: citySlug, month: rec.month, exact_deaths: null,
    lower_bound: min, chart_value: min, annual_exact_addition: null,
    is_partial: true, unknown: false,
    label: en ? "October 2026 — at least " + min + " confirmed"
              : "Жовтень 2026 — щонайменше " + min + " підтверджених",
    tooltip: en ? "Civilian deaths in verified aerial attacks only. October is incomplete; more cases may be found."
                : "Загиблі цивільні у перевірених повітряних атаках. Жовтень неповний; можливі інші випадки.",
  };
}

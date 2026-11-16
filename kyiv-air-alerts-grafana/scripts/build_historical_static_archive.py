#!/usr/bin/env python3
"""Generate static bilingual historical statistics from verified Git JSON.

Offline build step only. It never calls the source API, Neon, or Netlify.
Newly verified complete months appear at the NEXT explicitly approved frontend
build; regular four-hour Git-only data publishing does not trigger Netlify.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

SITE = "https://ukraine-air-alerts.netlify.app"
GIT_SOURCE = "https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/site-prod/historical-daily-kpi.json"

# Ukrainian/English city names, followed by the exact administrative raion
# used when the source row is a raion proxy. City series must have no raion.
CITIES = {
    "kyiv": ("Київ", "Kyiv", None, None),
    "kharkiv": ("Харків", "Kharkiv", None, None),
    "zaporizhzhia": ("Запоріжжя", "Zaporizhzhia", None, None),
    "cherkasy": ("Черкаси", "Cherkasy", "Черкаський район", "Cherkasy Raion"),
    "zhytomyr": ("Житомир", "Zhytomyr", "Житомирський район", "Zhytomyr Raion"),
    "dnipro": ("Дніпро", "Dnipro", "Дніпровський район", "Dnipro Raion"),
    "khmelnytskyi": ("Хмельницький", "Khmelnytskyi", "Хмельницький район", "Khmelnytskyi Raion"),
    "poltava": ("Полтава", "Poltava", "Полтавський район", "Poltava Raion"),
    "rivne": ("Рівне", "Rivne", "Рівненський район", "Rivne Raion"),
    "sumy": ("Суми", "Sumy", "Сумський район", "Sumy Raion"),
    "vinnytsia": ("Вінниця", "Vinnytsia", "Вінницький район", "Vinnytsia Raion"),
    "kropyvnytskyi": ("Кропивницький", "Kropyvnytskyi", "Кропивницький район", "Kropyvnytskyi Raion"),
    "lviv": ("Львів", "Lviv", "Львівський район", "Lviv Raion"),
    "chernihiv": ("Чернігів", "Chernihiv", "Чернігівський район", "Chernihiv Raion"),
    "odesa": ("Одеса", "Odesa", "Одеський район", "Odesa Raion"),
    "kherson": ("Херсон", "Kherson", "Херсонський район", "Kherson Raion"),
    "mykolaiv": ("Миколаїв", "Mykolaiv", "Миколаївський район", "Mykolaiv Raion"),
    "lutsk": ("Луцьк", "Lutsk", "Луцький район", "Lutsk Raion"),
    "uzhhorod": ("Ужгород", "Uzhhorod", "Ужгородський район", "Uzhhorod Raion"),
    "ivano_frankivsk": ("Івано-Франківськ", "Ivano-Frankivsk", "Івано-Франківський район", "Ivano-Frankivsk Raion"),
    "ternopil": ("Тернопіль", "Ternopil", "Тернопільський район", "Ternopil Raion"),
    "chernivtsi": ("Чернівці", "Chernivtsi", "Чернівецький район", "Chernivtsi Raion"),
    "sevastopol": ("Севастополь", "Sevastopol", None, None),
}
MONTHS_UK = ("", "січень", "лютий", "березень", "квітень", "травень", "червень",
             "липень", "серпень", "вересень", "жовтень", "листопад", "грудень")
MONTHS_EN = ("", "January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December")

CSS = """
:root{color-scheme:dark}
*{box-sizing:border-box}
html,body{margin:0;background:#0b0f14;color:#e9f0f7;font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
header,main,footer{max-width:1080px;padding:20px 22px;margin:0 auto}
header,footer{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;align-items:center}
header{border-bottom:1px solid #304153}
footer{border-top:1px solid #304153;margin-top:24px;color:#9db0c1;font-size:13px}
a{color:#92ccff}
a:hover{text-decoration:none}
a:focus-visible{outline:2px solid white;outline-offset:3px}
h1{font-size:clamp(1.6rem,4vw,2.2rem);line-height:1.23}
h2{font-size:1.35rem;margin-top:2rem}
h3{font-size:1.08rem}
p{max-width:86ch}
small,.muted{color:#aab9c7}
.notice{border-left:3px solid #ab9d70;background:#16222d;padding:8px 13px}
.summary{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
.stat{border:1px solid #384b60;border-radius:9px;padding:11px 16px;min-width:155px}
.stat strong{display:block;font-size:1.45rem}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:9px 12px;border-bottom:1px solid #354759;text-align:left}
th{color:#c8d6e4}
th[scope=row]{font-weight:500}
tbody tr:hover{background:#152434}
.yearlinks{display:flex;gap:12px;flex-wrap:wrap}
.monthlinks{display:flex;gap:12px;flex-wrap:wrap;padding-left:0;list-style:none}
.monthlinks li{border:1px solid #34495b;padding:5px 10px;border-radius:6px}
footer a{white-space:normal}
code{overflow-wrap:anywhere}
@media(max-width:480px){header,main,footer{padding:14px}td,th{padding:7px 6px;font-size:14px}}
""".strip()


def html(s: object) -> str:
    return escape(str(s), quote=True)


def metric_seconds(value: object) -> float:
    if not isinstance(value, (float, int)) or isinstance(value, bool):
        raise ValueError("Expected a real number")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Negative / nonfinite duration")
    return value


def fmt_time(seconds: float, lang: str) -> str:
    mins = int(math.floor(seconds / 60 + 0.5))
    hours, remainder = divmod(mins, 60)
    return f"{hours} год {remainder:02d} хв" if lang == "uk" else f"{hours} h {remainder:02d} min"


def geographic(slug: str, lang: str, source_type: str) -> str:
    city_uk, city_en, raion_uk, raion_en = CITIES[slug]
    if source_type == "exact_city":
        return city_uk if lang == "uk" else city_en
    if source_type == "raion_proxy":
        if not raion_uk or not raion_en:
            raise ValueError("Missing source district name: " + slug)
        return f"{city_uk} ({raion_uk})" if lang == "uk" else f"{city_en} ({raion_en})"
    raise ValueError("Unexpected source type: " + source_type)


def scope_notice(slug: str, lang: str, source_type: str) -> str:
    if source_type == "exact_city":
        return "Окремий ряд міських тривог." if lang == "uk" else "Separate city-level alert series."
    raion = CITIES[slug][2 if lang == "uk" else 3]
    return (f"Дані для {raion}, а не лише міста. Районна тривога може стосуватися інших населених пунктів."
            if lang == "uk" else
            f"Data for {raion}, not the city alone. District alerts can affect other settlements.")


def month_dates(year_month: str) -> list[date]:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", year_month):
        raise ValueError("Bad ISO month: " + year_month)
    year, month = (int(x) for x in year_month.split("-"))
    return [date(year, month, day) for day in range(1, calendar.monthrange(year, month)[1] + 1)]


def verified_series(source: dict) -> dict:
    meta = source.get("meta", {})
    if (source.get("schema") != "verified-historical-daily-start-counts-v1" or
        meta.get("timezone") != "Europe/Kyiv" or
        meta.get("expected_cities") != 23 or meta.get("verified_count") != 23):
        raise ValueError("Historical source contract not accepted")
    verified = meta.get("verified_cities", [])
    if set(verified) != set(CITIES) or set(source.get("cities", {})) != set(CITIES):
        raise ValueError("Missing/unexpected cities")
    verified_snapshot = date.fromisoformat(meta["generated_at"][:10])
    result = {}
    for slug in verified:
        series = source["cities"][slug]
        if series.get("status") != "verified":
            raise ValueError(f"City not verified: {slug}")
        scope = series.get("source_type")
        if (scope == "exact_city") != (CITIES[slug][2] is None):
            raise ValueError(f"Wrong city/raion provenance: {slug}")
        start, end = date.fromisoformat(series["start"]), date.fromisoformat(series["end"])
        length = (end - start).days + 1
        keys = ("counts", "daily_total_alert_duration_seconds", "daily_started_alert_duration_seconds")
        if length <= 0 or any(len(series.get(key, [])) != length for key in keys):
            raise ValueError(f"Bad daily array shape: {slug}")
        months = series.get("verified_metric_months", [])
        if not months or months != sorted(set(months)):
            raise ValueError(f"Missing, duplicate or unordered verified months: {slug}")
        rows = []
        for ym in months:
            days = month_dates(ym)
            if days[0] < start or days[-1] > end or days[-1] >= verified_snapshot:
                raise ValueError(f"Incomplete or future month: {slug} {ym}")
            day_rows = []
            for day in days:
                idx = (day - start).days
                n = series["counts"][idx]
                seconds = metric_seconds(series["daily_total_alert_duration_seconds"][idx])
                started = metric_seconds(series["daily_started_alert_duration_seconds"][idx])
                if not isinstance(n, int) or isinstance(n, bool) or n < 0 or seconds > 90000.01:
                    raise ValueError(f"Impossible verified day: {slug} {day}")
                day_rows.append({"day": day.isoformat(), "count": n, "seconds": seconds, "started": started})
            count = sum(row["count"] for row in day_rows)
            seconds = math.fsum(row["seconds"] for row in day_rows)
            started = math.fsum(row["started"] for row in day_rows)
            baseline = series.get("monthly_total_alert_duration_seconds", {}).get(ym)
            if (not isinstance(baseline, dict) or baseline.get("alerts_started") != count or
                abs(metric_seconds(baseline.get("seconds")) - seconds) > 0.01):
                raise ValueError(f"Monthly KPI parity failure: {slug} {ym}")
            rows.append({"ym": ym, "year": int(ym[:4]), "days": day_rows,
                         "count": count, "seconds": seconds, "started": started})
        result[slug] = {"type": scope, "start": series["start"], "end": series["end"], "months": rows}
    if sum(len(r["months"]) for r in result.values()) != meta["verified_full_metric_months"]:
        raise ValueError("23-city month total differs from release contract")
    return result


def routes(lang: str, slug: str = "", fragment: str = "") -> str:
    parts = [("en", "stats") if lang == "en" else ("stats",)]
    path = "/" + "/".join(parts[0])
    if slug:
        path += "/" + slug
    if fragment:
        path += "/" + fragment
    return path + "/"


def page(lang: str, route: str, title: str, description: str,
         body: str, source_time: str, schema: dict | None = None) -> str:
    counterpart = route.replace("/en/stats/", "/stats/", 1) if lang == "en" else route.replace("/stats/", "/en/stats/", 1)
    uk, en = (route, counterpart) if lang == "uk" else (counterpart, route)
    metadata = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{html(title)}</title>",
        f'<meta name="description" content="{html(description)}">',
        '<meta name="robots" content="index,follow">',
        f'<link rel="canonical" href="{SITE + route}">',
        f'<link rel="alternate" hreflang="uk" href="{SITE + uk}">',
        f'<link rel="alternate" hreflang="en" href="{SITE + en}">',
        f'<link rel="alternate" hreflang="x-default" href="{SITE + uk}">',
        f"<style>{CSS}</style>",
    ]
    if schema is not None:
        metadata.append('<script type="application/ld+json">' +
                        json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c") +
                        "</script>")
    back = "Інтерактивний дашборд" if lang == "uk" else "Interactive dashboard"
    archive = "Статистика у таблицях" if lang == "uk" else "Data tables"
    archive_route = routes(lang)
    source = "Дані та код" if lang == "uk" else "Data and code"
    note = ("Історичні завершені місяці, не поточний статус тривоги."
            if lang == "uk" else "Completed historical months, not live alert status.")
    head = (f'<header><a href="/">{html(back)}</a><nav>'
            f'<a href="/stats/">UA</a> · <a href="/en/stats/">EN</a></nav></header>')
    foot = (f'<footer><span>{html(source)}: <a href="{GIT_SOURCE}">Git JSON</a></span>'
            f'<span>{html(note)}</span></footer>')
    crumb = f'<p class="muted"><a href="{archive_route}">{html(archive)}</a></p>'
    return ('<!doctype html>\n<html lang="' + lang + '"><head>\n' +
            "\n".join(metadata) + '\n</head><body>\n' + head +
            '\n<main>' + crumb + body + '</main>\n' + foot + '\n</body></html>\n')


def table(columns: list[str], rows: list[str]) -> str:
    header = "".join(f'<th scope="col">{html(col)}</th>' for col in columns)
    return '<div class="scroll"><table><thead><tr>' + header + '</tr></thead><tbody>\n' + \
           "\n".join(rows) + '</tbody></table></div>'


def stats(months: list[dict]) -> tuple[int, float]:
    return sum(m["count"] for m in months), math.fsum(m["seconds"] for m in months)


def source_info(slug: str, lang: str) -> str:
    if slug == "kyiv":
        links = ('<a href="https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/">'
                 'Kyiv Open Data</a> · <a href="https://kyiv.digital/storage/air-alert/stats.html">Kyiv Digital</a>')
    elif slug == "sevastopol":
        links = '<a href="https://t.me/s/razvozhaev">Telegram @razvozhaev</a>'
    else:
        links = ('<a href="https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset">'
                 'Historical air-alert dataset</a> · '
                 '<a href="https://api.ukrainealarm.com/api/v3">UkraineAlarm API</a>')
    qualifier = ""
    if slug == "sevastopol":
        qualifier = ('<p>Джерело повідомлень пов’язане з окупаційною адміністрацією. '
                     'Посилання описує походження даних і не означає її визнання.</p>'
                     if lang == "uk" else
                     '<p>The messages originate from an occupation authority. '
                     'Citing their provenance does not imply recognition.</p>')
    statement = ("Історичні дані сформовано з перевіреного Git JSON, побудованого на наведених джерелах."
                 if lang == "uk" else
                 "Historical figures come from the verified Git JSON built from these sources.")
    return f'<p>{html(statement)} {links}</p>' + qualifier


def methods(lang: str) -> str:
    if lang == "uk":
        return ("<h2>Методологія</h2><p>Початки тривог зараховано до дати їх початку. "
                "Час під тривогою — фактичне об'єднання інтервалів у межах календарних діб "
                "Europe/Kyiv: перекриття не подвоюються, тривоги через північ розрізаються. "
                "Середня повна тривалість обчислюється для тривог, що почалися в періоді, "
                "навіть якщо вони завершилися пізніше. Значення часу округлено лише для показу; "
                "підсумки рахуються з неокруглених секунд.</p>")
    return ("<h2>Methodology</h2><p>Alert starts are assigned to the calendar date when the alert began. "
            "Time under alert is the union of alert intervals within Europe/Kyiv calendar days; "
            "overlaps are not double-counted and intervals crossing midnight are split by day. "
            "Mean full duration uses alerts that started in the period, including their full duration "
            "if they ended later. Times are rounded for display only; totals use unrounded seconds.</p>")


def dataset_schema(title: str, desc: str, url: str, slug: str, lang: str, first: str,
                   last: str, source_date: str, source_type: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": title, "description": desc, "url": SITE + url,
        "inLanguage": lang,
        "dateModified": source_date,
        "temporalCoverage": first + "/" + last,
        "spatialCoverage": {"@type": "Place", "name": geographic(slug, lang, source_type)},
        "variableMeasured": (["Кількість початків тривог", "Час під тривогою", "Середня повна тривалість"]
                             if lang == "uk" else
                             ["Number of alert starts", "Time under alert", "Mean full duration"]),
        "isBasedOn": GIT_SOURCE
    }


def write_site(out: Path, entries: list[dict], lang: str, route: str,
               title: str, desc: str, body: str, modified: str, schema: dict | None = None) -> None:
    dest = out / route.lstrip("/") / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page(lang, route, title, desc, body, modified, schema), encoding="utf-8")
    entries.append({"loc": SITE + route, "lastmod": modified})


def generate(source_path: Path, output_dir: Path) -> dict:
    raw = source_path.read_bytes()
    git_sha = hashlib.sha1((f"blob {len(raw)}\0").encode("ascii") + raw).hexdigest()
    source = json.loads(raw)
    city_data = verified_series(source)
    generated_at = source["meta"]["generated_at"]
    source_date = generated_at[:10]
    entries = [{"loc": SITE + "/", "lastmod": source_date},
               {"loc": SITE + "/en/", "lastmod": source_date}]
    count_months = sum(len(row["months"]) for row in city_data.values())
    count_years = 0
    for lang in ("uk", "en"):
        # Sitewide archive index, with 23 verified series.
        index_rows = []
        for slug in source["meta"]["verified_cities"]:
            item = city_data[slug]
            label = geographic(slug, lang, item["type"])
            months = item["months"]
            number, seconds = stats(months)
            index_rows.append(
                f'<tr><th scope="row"><a href="{routes(lang, slug)}">{html(label)}</a></th>'
                f'<td>{len(months)}</td><td>{number}</td><td>{html(fmt_time(seconds, lang))}</td>'
                f'<td>{html(months[0]["ym"])}–{html(months[-1]["ym"])}</td></tr>')
        title = ("Історична статистика повітряних тривог у 23 містах — таблиці"
                 if lang == "uk" else "Historical air-alert statistics in 23 Ukrainian cities — tables")
        intro = ("Перевірені завершені місяці для 23 міських і районних рядів."
                 if lang == "uk" else "Verified completed months for 23 city and district series.")
        note = ("У таблиці наведено підсумки лише підтверджених повних місяців. "
                "Районні ряди охоплюють не лише місто. Поточний незавершений місяць не включено."
                if lang == "uk" else "Totals include verified full months only. "
                "District series extend beyond the city. The current incomplete month is excluded.")
        cols = (["Місто / ряд", "Підтверджених місяців", "Тривог почалося", "Час під тривогою", "Період"]
                if lang == "uk" else
                ["City / series", "Verified months", "Alert starts", "Time under alert", "Period"])
        body = (f"<h1>{html(title)}</h1><p>{html(intro)}</p><p class=\"notice\">{html(note)}</p>" +
                table(cols, index_rows) +
                f"<p class=\"muted\">{'Зріз даних' if lang == 'uk' else 'Data snapshot'}: "
                f"<time datetime=\"{html(generated_at)}\">{html(generated_at)}</time>.</p>")
        write_site(output_dir, entries, lang, routes(lang), title, intro, body, source_date)
        for slug in source["meta"]["verified_cities"]:
            item = city_data[slug]
            scope = item["type"]
            label = geographic(slug, lang, scope)
            months = item["months"]
            available_years = defaultdict(list)
            for record in months:
                available_years[record["year"]].append(record)
            earliest, latest = months[0]["ym"], months[-1]["ym"]
            scope_note = scope_notice(slug, lang, scope)
            count, seconds = stats(months)
            total_caption = (f"Підсумок лише за {len(months)} підтверджених місяців; "
                             "це не оцінка пропущених періодів." if lang == "uk" else
                             f"Total across {len(months)} verified months only; "
                             "missing periods are not estimated.")
            city_title = (f"{label}: статистика повітряних тривог за роками та місяцями"
                          if lang == "uk" else f"{label}: air alerts by year and month")
            city_desc = (f"Перевірені завершені місяці {earliest}–{latest}; початки тривог і час під тривогою."
                         if lang == "uk" else f"Verified full months {earliest}–{latest}: alert starts and time under alert.")
            coverage = (f"Завершені місяці {earliest}–{latest}" if lang == "uk"
                        else f"Completed months {earliest}–{latest}")
            blocks = [f"<h1>{html(city_title)}</h1><p class=\"notice\">{html(scope_note)}</p>",
                      f"<p>{html(coverage)}. {html(total_caption)}</p>",
                      f'<div class="summary"><div class="stat">{html("Місяців" if lang=="uk" else "Months")}<strong>{len(months)}</strong></div>'
                      f'<div class="stat">{html("Тривог почалося" if lang=="uk" else "Alert starts")}<strong>{count}</strong></div>'
                      f'<div class="stat">{html("Час під тривогою" if lang=="uk" else "Time under alert")}<strong>{html(fmt_time(seconds,lang))}</strong></div></div>']
            for year in sorted(available_years, reverse=True):
                year_route = routes(lang, slug, str(year))
                blocks.append(f'<h2><a href="{year_route}">{year}</a></h2>')
                blocks.append('<ul class="monthlinks">' + "".join(
                    f'<li><a href="{routes(lang,slug,m["ym"])}">{html(MONTHS_UK[int(m["ym"][-2:])] if lang=="uk" else MONTHS_EN[int(m["ym"][-2:])])}</a></li>'
                    for m in available_years[year]) + "</ul>")
            blocks.extend([methods(lang), "<h2>" + ("Джерела" if lang == "uk" else "Sources") + "</h2>",
                           source_info(slug, lang),
                           f'<p class="muted">{html("Зріз даних" if lang=="uk" else "Data snapshot")}: '
                           f'<time datetime="{html(generated_at)}">{html(generated_at)}</time>. '
                           f'Git blob: <code>{html(git_sha)}</code></p>'])
            schema = dataset_schema(city_title, city_desc, routes(lang, slug), slug, lang,
                                    months[0]["days"][0]["day"], months[-1]["days"][-1]["day"],
                                    source_date, scope)
            write_site(output_dir, entries, lang, routes(lang, slug), city_title, city_desc,
                       "\n".join(blocks), source_date, schema)
            for year in sorted(available_years, reverse=True):
                year_months = available_years[year]
                year_count, year_seconds = stats(year_months)
                is_full = len(year_months) == 12
                title = (f"{label}: повітряні тривоги у {year} році" if lang == "uk"
                         else f"{label}: air alerts in {year}")
                status_text = ((f"Усі 12 місяців {year} року перевірені." if is_full
                                else f"Частковий рік: {len(year_months)} із 12 місяців підтверджено. "
                                     "Підсумки не стосуються відсутніх місяців.") if lang == "uk" else
                               (f"All 12 months of {year} are verified." if is_full
                                else f"Partial year: {len(year_months)} of 12 months verified. "
                                     "Totals exclude missing months."))
                lines = []
                for record in year_months:
                    m = int(record["ym"][-2:])
                    month_title = MONTHS_UK[m] if lang == "uk" else MONTHS_EN[m]
                    lines.append(f'<tr><th scope="row"><a href="{routes(lang,slug,record["ym"])}">{html(month_title)}</a></th>'
                                 f'<td>{record["count"]}</td><td>{html(fmt_time(record["seconds"],lang))}</td></tr>')
                cols = (["Місяць", "Тривог почалося", "Час під тривогою"] if lang == "uk"
                        else ["Month", "Alert starts", "Time under alert"])
                year_body = (f'<h1>{html(title)}</h1><p class="notice">{html(scope_note)} {html(status_text)}</p>' +
                             f'<div class="summary"><div class="stat">{html("Початків за підтверджені місяці" if lang=="uk" else "Starts in verified months")}<strong>{year_count}</strong></div>'
                             f'<div class="stat">{html("Час під тривогою" if lang=="uk" else "Time under alert")}<strong>{html(fmt_time(year_seconds,lang))}</strong></div></div>' +
                             table(cols, lines) +
                             f'<p><a href="{routes(lang,slug)}">{html("Усі роки" if lang=="uk" else "All years")}</a></p>' +
                             methods(lang) + source_info(slug,lang))
                write_site(output_dir, entries, lang, routes(lang, slug, str(year)), title, status_text,
                           year_body, source_date,
                           dataset_schema(title, status_text, routes(lang, slug, str(year)), slug,lang,
                                          year_months[0]["days"][0]["day"], year_months[-1]["days"][-1]["day"],
                                          source_date,scope))
                count_years += 1
            for record in months:
                ym = record["ym"]
                calendar_month = int(ym[-2:])
                date_label = ((f"{MONTHS_UK[calendar_month]} {record['year']}" if lang == "uk" else
                               f"{MONTHS_EN[calendar_month]} {record['year']}"))
                title = (f"Повітряні тривоги: {label}, {date_label}" if lang == "uk"
                         else f"Air alerts: {label}, {date_label}")
                description = (f"Тривоги та час під тривогою в {label} за {ym}. "
                               "Лише підтверджений повний календарний місяць."
                               if lang == "uk" else
                               f"Alert starts and time under alert in {label}, {ym}. "
                               "Verified full calendar month only.")
                count_text = ("Тривог почалося" if lang == "uk" else "Alert starts")
                time_text = ("Час під тривогою" if lang == "uk" else "Time under alert")
                avg_text = ("Середня повна тривалість" if lang == "uk" else "Mean full duration")
                avg = fmt_time(record["started"] / record["count"], lang) if record["count"] else ("Немає тривог" if lang=="uk" else "No alerts")
                summary = ('<div class="summary">' +
                           f'<div class="stat">{html(count_text)}<strong data-month-count="{record["count"]}">{record["count"]}</strong></div>' +
                           f'<div class="stat">{html(time_text)}<strong data-month-seconds="{record["seconds"]:.6f}">{html(fmt_time(record["seconds"], lang))}</strong></div>' +
                           f'<div class="stat">{html(avg_text)}<strong>{html(avg)}</strong></div></div>')
                daily = []
                for d in record["days"]:
                    daily.append(f'<tr><th scope="row"><time datetime="{d["day"]}">{d["day"]}</time></th>'
                                 f'<td>{d["count"]}</td><td data-seconds="{d["seconds"]:.6f}">{html(fmt_time(d["seconds"],lang))}</td></tr>')
                cols = (["Дата", "Початків тривог", "Час під тривогою"] if lang == "uk"
                        else ["Date", "Alert starts", "Time under alert"])
                body = (f"<h1>{html(title)}</h1><p class=\"notice\">{html(scope_note)}</p>" +
                        summary + "<h2>" + ("Денні значення" if lang=="uk" else "Daily figures") + "</h2>" +
                        table(cols, daily) + methods(lang) +
                        f'<p><a href="{routes(lang,slug,str(record["year"]))}">{html("Повернутися до року" if lang=="uk" else "Back to year")}</a>'
                        f' · <a href="/">{html("Інтерактивні графіки" if lang=="uk" else "Interactive charts")}</a></p>' +
                        "<h2>" + ("Джерела і зріз" if lang=="uk" else "Sources and snapshot") + "</h2>" +
                        source_info(slug,lang) +
                        f'<p>{html("Зріз даних" if lang=="uk" else "Data snapshot")}: '
                        f'<time datetime="{html(generated_at)}">{html(generated_at)}</time>. '
                        f'Git blob: <code>{html(git_sha)}</code>.</p>')
                write_site(output_dir, entries,lang,routes(lang,slug,ym),title,description,body,
                           source_date,dataset_schema(title,description,routes(lang,slug,ym),slug,lang,
                                                      record["days"][0]["day"],record["days"][-1]["day"],
                                                      source_date,scope))
    # Discoverable production URLs. Netlify draft deploys are unlisted and carry noindex headers.
    url_rows = [f'<url><loc>{xml_escape(row["loc"])}</loc><lastmod>{row["lastmod"]}</lastmod></url>'
                for row in entries]
    sitemap = '<?xml version="1.0" encoding="utf-8"?>\n' + \
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
              "\n".join(url_rows) + '\n</urlset>\n'
    (output_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (output_dir / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + SITE +
                                           "/sitemap.xml\n", encoding="utf-8")
    if len(entries) != 2 + 2 + 2 * len(CITIES) + count_years + 2 * count_months - 2:
        # Simpler expected inventory: home locales (2), archive indices (2),
        # city pages (46), year pages (count_years both languages), month pages (784).
        expected = 4 + 2 * len(CITIES) + count_years + 2 * count_months
        if len(entries) != expected:
            raise ValueError(f"Unexpected URL inventory: {len(entries)} != {expected}")
    manifest = {
        "schema": "verified-air-alert-html-archive-v1",
        "source_git_blob": git_sha,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_generated_at": generated_at,
        "source_timezone": "Europe/Kyiv",
        "cities": len(CITIES),
        "verified_full_months": count_months,
        "year_pages_both_languages": count_years,
        "month_pages_both_languages": 2 * count_months,
        "city_pages_both_languages": 2 * len(CITIES),
        "archive_index_pages": 2,
        "sitemap_url_count": len(entries),
        "per_city_months": {slug: len(item["months"]) for slug, item in city_data.items()},
        "generated_only_from_verified_full_months": True,
        "not_a_live_alert_feed": True,
    }
    (output_dir / "static-archive-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SEO_FULL_HISTORY_BUILD_PASS: {len(CITIES)}/23 cities, {count_months} unique verified months, "
          f"{2 * count_months} bilingual monthly pages, {len(entries)} sitemap URLs, blob={git_sha}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    generate(args.source, args.output_dir)


if __name__ == "__main__":
    main()

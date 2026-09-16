#!/usr/bin/env python3
from __future__ import annotations

import expand_multicity_production as base

# Nationwide district-specific alerting was officially rolled out across Ukraine
# on 2025-12-15, except Donetsk and Luhansk oblasts. For cities where we do not
# have an earlier externally validated rollout date, use that date conservatively.
#
# Mykolaiv is a special fallback: a separate exact-city alerting regime exists,
# but we do not have a complete reproducible city-level event history. Therefore
# production uses the eponymous raion explicitly labelled as a proxy, starting
# only from the stable raion segment observed in the upstream source.
ADDITIONAL_PROXIES = {
    "mykolaiv": {"label": "Миколаїв", "oblast": "Миколаївська область", "raion": "Миколаївський район", "coverage_start": "2025-11-05", "coverage_basis": "stable_raion_source_fallback_exact_city_unavailable"},
    "kherson": {"label": "Херсон", "oblast": "Херсонська область", "raion": "Херсонський район", "coverage_start": "2025-12-15", "coverage_basis": "official_nationwide_rollout"},
    "lutsk": {"label": "Луцьк", "oblast": "Волинська область", "raion": "Луцький район", "coverage_start": "2025-12-15", "coverage_basis": "official_nationwide_rollout"},
    "uzhhorod": {"label": "Ужгород", "oblast": "Закарпатська область", "raion": "Ужгородський район", "coverage_start": "2025-12-15", "coverage_basis": "official_nationwide_rollout"},
    "ivano_frankivsk": {"label": "Івано-Франківськ", "oblast": "Івано-Франківська область", "raion": "Івано-Франківський район", "coverage_start": "2025-12-15", "coverage_basis": "official_nationwide_rollout"},
    "chernivtsi": {"label": "Чернівці", "oblast": "Чернівецька область", "raion": "Чернівецький район", "coverage_start": "2025-12-15", "coverage_basis": "official_nationwide_rollout"},
    "ternopil": {"label": "Тернопіль", "oblast": "Тернопільська область", "raion": "Тернопільський район", "coverage_start": "2025-12-15", "coverage_basis": "official_nationwide_rollout"},
}


def explicit_proxy_label(city: str, raion: str) -> str:
    return f"{city} ({raion})"


def methodology_content(data: dict) -> str:
    lines = []
    for key in base.PROXY_KEYS:
        meta = data["cities"][key]["meta"]
        lines.append(
            f"- **{meta['city_label']}**: районний proxy; coverage з {meta['coverage_start']}."
        )

    return (
        "**Географія та джерела.** Київ, Харків і Запоріжжя мають exact-city ряди. "
        "Усі назви з районом у дужках є **районними proxy**, а не даними міста в чистому вигляді. "
        "Для proxy після validated coverage-start використовується union відповідного району та "
        "explicit `oblast` сигналів. У 2026 році explicit `oblast` записи в upstream фактично не "
        "додають часу, тому ряд дорівнює районному. До coverage-start старі обласні дані не backfill-яться.  \n\n"
        + "\n".join(lines)
        + "  \n\n"
        "**Миколаїв.** Для самого міста існує окремий city-level режим оповіщення, але у відкритих "
        "джерелах не вдалося відновити достатньо повну послідовність стартів і відбоїв для надійного "
        "розрахунку тривалості. Тому в dashboard використовується явно підписаний районний proxy "
        "**Миколаїв (Миколаївський район)** зі стабільного сегмента upstream з 05.11.2025.  \n\n"
        "**Консервативний rollout 15.12.2025.** Для Херсона, Луцька, Ужгорода, Івано-Франківська, "
        "Чернівців і Тернополя використовується 15.12.2025 — дата офіційного загальнонаціонального "
        "переходу на порайонне оповіщення (крім Донецької та Луганської областей).  \n\n"
        "**Поза поточним scope.** Донецьк і Луганськ свідомо не включені. Севастополь додається "
        "окремим exact-city adapter із явним маркуванням джерела окупаційної адміністрації.  \n\n"
        "**Агрегація.** Поточний календарний день виключено. Перекривні інтервали зливаються до "
        "підрахунку тривалості та кількості alert episodes. Перший неповний місяць і тиждень після "
        "coverage-start виключаються. Порівняння використовує лише спільні повні календарні періоди.  \n\n"
        "Пропозиції надсилати @olbalakin в телеграм"
    )


def main() -> None:
    base.PROXY_CONFIG.update(ADDITIONAL_PROXIES)

    # Make every proxy visually explicit in rows and comparison legends.
    for cfg in base.PROXY_CONFIG.values():
        cfg["label"] = explicit_proxy_label(cfg["label"], cfg["raion"])

    base.PROXY_KEYS = list(base.PROXY_CONFIG)
    base.CITY_KEYS = base.EXACT_KEYS + base.PROXY_KEYS
    base.CITY_LABELS = {
        "kyiv": "Київ",
        "kharkiv": "Харків",
        "zaporizhzhia": "Запоріжжя",
        **{key: cfg["label"] for key, cfg in base.PROXY_CONFIG.items()},
    }
    base.DEFERRED = {
        "donetsk": "out of current scope",
        "luhansk": "out of current scope",
        "sevastopol": "separate exact-city adapter; occupation-administration source must be labeled explicitly",
    }
    base.methodology_content = methodology_content
    base.main()


if __name__ == "__main__":
    main()

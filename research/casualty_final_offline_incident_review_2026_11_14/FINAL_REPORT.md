# CASUALTY — FINAL OFFLINE INCIDENT REVIEW (T03/T04/T05)

**Дата перевірки:** 2026-11-14. **Рішення:** `INCIDENT_LIKELY_RECONCILIATION_UNVERIFIED`. **Gate:** `BLOCKED_PENDING_EVIDENCE`.

Найімовірніше, повідомлення стосуються однієї атаки з послідовним повідомленням про 2, а потім 3 загиблих. Проте **точна дата самої атаки й незалежний зв'язок усіх трьох повідомлень не доведені**. Три — це підсумок в окремому поліцейському повідомленні, не затверджений підсумок для ідентифікованої атаки 22 жовтня. Автоматичне зіставлення, корекція статистики й публікація заборонені.

## 1. Збережені свідчення (час публікації ≠ час атаки)

| Джерело | Що безпосередньо збережено | Дата/час та межа доказу |
|---|---|---|
| **T03, Укрінформ** | Початкове повідомлення ОВА про **двох** загиблих; згодом описане подружжя віком **37/38**. Зазначено удар по приватному об'єкту в Запоріжжі. | `publication_date=2026-10-22T15:26:00Z`, `attack_date_explicit=null`, `claim_deaths=null`, `fatal_total_diagnostic=CONFLICTING_FATAL_TOTALS`. Два — локальне повідомлення, не перевірений остаточний підсумок статті. |
| **T04, MIG** | Прямо описана зміна повідомленої кількості: спочатку **2**, згодом **3**; додатково повідомлено про смерть **69-річної жінки**. Є згадка про вечірній ракетний удар. | `publication_date=2026-10-22T19:39:52Z`, `attack_date_explicit=null`, `claim_deaths=null`, `fatal_total_diagnostic=ADDITIONAL_DEATH_REPORTED`. Вік 69 не є кількістю смертей. |
| **T05, поліція Запорізької області** | Повідомлено про **3** загиблих: подружжя **37/38** та жінку **69**; згадано вечірню атаку на обласний центр і ракетне влучання поблизу приватного сектору. | `claim_deaths=3`, `count_kind=single_report_total`, але `publication_date=null`, `attack_date_explicit=null`, `attack_slot_hint_not_identity=09:56` — не підтверджений час атаки. У тексті також описано багато ударів по області, тому немає унікального event anchor. |

**Точні покажчики на докази.** Архів Work R: [Actions #43574791160, artifact #14105343291](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43574791160/artifacts/14105343291), ZIP SHA-256 `8248b426baa23d822b0ba92332137ab59c63146b648b22271c41af7ff0a3177b`. `minimal_capture_facts.json` SHA-256 `3e6c1b325344b66cb0da45476ff5140915e00d220cb8771e38bc182f481cb4d6`: `facts[0..2].excerpts`, `facts[0..2].incident_review.evidence_mentions`, `publication_date`, `attack_date_explicit`, `claim_deaths`. `capture_receipts.json` SHA-256 `785404f240281b8020273e8f0a2653378481e3f47167a113eee2321da7b8f1f8`: `targets[].target_id/requested_url/response_sha256`. Це **3/3 HTTP 200** попереднього дозволеного збору; в цьому review нових HTTP-запитів не було.

Короткі текстові якорі й SHA-256 уривків: T03 «Загинули двоє людей» (`bc6de2ef...e3ff1`) та подружжя 37/38 (`001c1188...b801a`); T04 «Спочатку було відомо про двох жертв» (`0a6281d2...763a`) і «загинула також 69-річна жінка» (`24357205...a238b`); T05 опис трьох загиблих віком 37/38/69 (`f2d17394...c846b`), вечірньої атаки (`4e4461c4...ce1`) та ракети біля приватного сектору (`fa7d17e4...1a53`). Посилання на джерела зафіксовані в `capture_receipts.json.targets[].receipt.requested_url`; case label `oct22` — тільки маршрутизація, не доказ дати.

## 2. Попарне зіставлення

| Пара | Збіги й розбіжності; provenance Work R | Рівень / формальний висновок |
|---|---|---|
| **T03 ↔ T04** | Обидві публікації 22.10, посилання на ОВА, Запоріжжя, початкові 2; T04 окремо фіксує зміну 2→3. T03: `facts[0].excerpts[0]` + `incident_review.evidence_mentions[1]`; T04: `facts[1].incident_review.evidence_mentions[0..3]`. Немає доведеної спільної дати/часу самої атаки й точно тотожного об'єкта. | **Сильна гіпотеза**, `INSUFFICIENT_EVIDENCE`. |
| **T03 ↔ T05** | Спільні вік і родинний зв'язок подружжя 37/38; приватний будинок проти приватного сектору, обидва контексти стосуються Запоріжжя. T03: `facts[0].excerpts[1]`; T05: `facts[2].excerpts[0]` + `incident_review.evidence_mentions[2..3]`. У T05 відсутній незалежний датований зв'язок із T03 та унікальний об'єкт. | **Сильна гіпотеза**, `INSUFFICIENT_EVIDENCE`. |
| **T04 ↔ T05** | T04 описує 69-річну третю загиблу й послідовність 2→3; T05 повідомляє остаточне для свого тексту число 3 і той самий вік третьої загиблої, вечірній ракетний контекст. T04: `facts[1].excerpts[0]` + `incident_review.evidence_mentions[1..3]`; T05: `facts[2].excerpts[0]` + `incident_review.evidence_mentions[1..3]`. Немає прямого підтвердження зв'язку офіційного повідомлення саме з ударом у T04. | **Сильна гіпотеза**, `INSUFFICIENT_EVIDENCE`. |

Жоден запис не підтримує `DIFFERENT_INCIDENTS_SUPPORTED`. Водночас **збіг віку не є самодостатнім доказом**, а послідовність речень у витягах не дорівнює незалежно доведеній часовій шкалі події. Докази підтримують **ймовірну одну атаку та кумулятивне 2→3**, але не `INCIDENT_CONFIRMED_RECONCILED`.

## 3. Перевірка фактично зарахованих загиблих (read-only)

| Контур | Перевірений стан і висновок | Git provenance |
|---|---|---|
| **`site-prod`, реальний casualty JSON** | У `dashboard_data.json → casualties_by_city.zaporizhzhia` є **316** підтверджених смертей за історичний зріз до **2026-09-18**; останній рядок — **2026-09**, **4** смерті. **Жовтня 2026 немає**. Отже, 22–23 жовтня не внесені до цієї production Git-серії ані як 2, ані як 3 загиблих. | `site-prod@54079326ae2b4e691e2bfcf7cd1a51c9705404eb`; JSON Git blob `4eaf5b9f8d9352b06fed393532cc36ddfa5c4027`; поля `casualties_by_city.zaporizhzhia.meta.validated_through`, `monthly[-1]`, відсутність `month=2026-10`. |
| **`site-prod`, CSV/manifest** | Місячна таблиця Запоріжжя закінчується вереснем 2026; маніфест фіксує валідований зріз до 18.09. Джерело не містить incident-level запису 22–23.10. | `.../cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv` blob `1b32d8808069b4499fda35b092fd56f51c64583f`; `manifest.json` blob `4dcfb6a14949820b4934a100063f549e22799e8b`. |
| **`site-prod`, revisions** | Є лише **одна** confirmed revision: **Суми, +1 за 2026-09-20**. **0** Zaporizhzhia revisions; немає incident ID або credited delta для T03/T04/T05. Подвійного врахування цих кандидатів у чинному revision ledger немає. | `kyiv-air-alerts-grafana/data/casualties/revisions.csv` blob `8d7a2e2540bf4bf0f8c6227023821390bf82ce13`; єдиний `record_id=casualty:sumy:2026-09-20:fpv-double-strike-zarichnyi-apartment-entrance`. |
| **`main` (окремо від `site-prod`)** | `revisions.csv` має лише заголовок. Це не production-серія і не доказ кредитування або відсутності смертей поза її власним станом. | `main@5c9684c2f953eeb71b4e273906ba8bc6d5f9cdb1`, revisions blob `3b2b04438a12a55a0e42ed3b38a3b3a6ba5135c1`. |
| **WIP / дослідження** | Кластер `oct_22_23_two_vs_three` має **три окремі news candidate ID**: T03 `7c3ac3280ba7ad4b9c10f3b1`, T04 `dcdd2fe28fd1464e7fbabdc1`, додатковий RSS `24654383bd30cc0f4e29c95f`. Вони **needs_review**, не production incidents і не death credits. Окремо доведена в research атака **10.10 (+23)** не опублікована і не має стосунку до цього автоматичного обліку. | [PR #88, `verification_matrix.json`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/34bc539d0c7abb8af4f699b2e2c9ecec4b668397/research/casualty_zaporizhzhia_additional_events_2026_11_12/verification_matrix.json), blob `12e9f43a41469d5916c918a11b5d5c7fdb4e8320`, `groups[cluster_id=oct_22_23_two_vs_three]`; [PR #105](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/105) research shadow +23, publication OFF. |

**Висновок з обліку:** у перевіреному Git-контурі `site-prod` попередніх зарахувань за цією атакою **0**. Це підтверджено **окремо** dashboard JSON, місячним CSV/маніфестом і revisions; висновок не побудований лише на місячній сумі. Точний production `incident_id` для цієї події **не існує** в доступному revision ledger; кластер та candidate IDs не можна ним підміняти. Фактичний Netlify-served JSON окремим мережевим запитом у рамках OFFLINE review не перевірявся.

## 4. Рішення про кількість і корекцію

- **Доказовий source-level підсумок T05:** 3; **T04:** повідомлена еволюція 2→3. **Перевірена кількість для однозначно ідентифікованої атаки:** поки **не встановлена**.
- **Рекомендована production-корекція:** **немає / `null`**; `proposed_deaths_delta=null`, `approved_incident_id=null`. Ні +2, ні +3 зараз не санкціоновані.
- Якщо тотожність пізніше буде доведена, три смерті є **одним кумулятивним підсумком**, а не 2+3 і не двома інцидентами. Потрібен окремий повторний read-only reconciliation перед пропозицією власнику, щоб не дублювати вже внесене пізніше.
- Ризики: T03 і T04 мають різні candidate IDs; T05 не має прив'язаного candidate ID; третя RSS-картка про трьох загиблих може дублювати їх. Інші удари 22–23.10 і загальнообласні дані T05 не можна механічно зливати з цим кластером.

## 5. Конкретні прогалини та відтворюваність

1. **Датований первинний зв'язок:** у всіх `facts[].attack_date_explicit=null`; T05 не має навіть `publication_date`. Потрібно незалежно встановити дату атаки, а не лише дати матеріалів 22.10.
2. **Тотожність удару:** немає спільного підтвердженого часу, конкретного об'єкта/ділянки або офіційного інцидентного ідентифікатора, що прямо об'єднує T03, T04 і T05. Згадки «приватний будинок», «приватний сектор», «вечірній ракетний обстріл» ще не дають унікального збігу.
3. **Наявні матеріали:** Work P/R зберегли тільки короткі витяги, хеші й діагностику, а повні HTML не зберігали. З них можна перевірити кількість, вік, послідовність повідомлень та контрольні суми, **але не відновити відсутній календарний і просторовий anchor**. Перш ніж обговорювати будь-яке нове джерело, перевірити інші вже наявні офіційні архіви; цього review недостатньо для нових HTTP-дозволів.

**Інтегриті-перевірка:** Work P [artifact #14082589637](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43521321878/artifacts/14082589637), ZIP SHA-256 `67133a7b2e94fdcdf8c1a4bf3871788b691e35b3666430b976e082355675b99f`, 4/4 внутрішніх SHA-256 PASS; Work R ZIP вище, 4/4 PASS. Чотири початкові deidentified excerpts Work P збережені в Work R із тими самими `excerpt_sha256`. Work Q [PR #135](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/135), exact `858e255ebea543383a9ca95d07847a40e22742e6`; Work R pre-launch `f2f3a922bfe193a66680d8bf64f29a80be17dc9a`, [offline CI #43573408615](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43573408615) **153 PASS, 0 FAIL, 1 expected SKIP**. Це документальна manual offline-перевірка; нового коду, розрахункового алгоритму, workflow або тестового запуску не додано.

**Підсумок:** `INCIDENT_LIKELY_RECONCILIATION_UNVERIFIED`; **`BLOCKED_PENDING_EVIDENCE`**. Зберегти `NEEDS_REVIEW`, 0 автоматичних death credits і заборону publication. Без merge, deployment, PROMOTE, змін casualty JSON/CSV, revisions, WIP, C2, Neon, production або координаційних PR #71/#117.

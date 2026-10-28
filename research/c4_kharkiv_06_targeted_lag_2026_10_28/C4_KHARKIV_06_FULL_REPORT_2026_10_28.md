# C4-KH-06. Повний звіт щодо тривалості повітряної тривоги Харкова 5–6 березня 2025 року

Дата звіту: 28 жовтня 2026 року. Статус: **UNRESOLVED / BLOCKED_SOURCE_CONFLICT**. Research-only, no correction authorization.

## 1. Рішення для власника

Сукупність наявних джерел **краще підтримує тривалу нічну тривогу** в самому Харкові (5 березня 21:08 — 6 березня 05:03 за Києвом), ніж версію єдиної короткої тривоги до 21:47:55. Проте безперервність міського сигналу протягом усього проміжку та точний час відбою **не сертифіковані** первинним журналом переходів стану.

Немає автентифікованого міського OFF о 21:47:55 і повторного міського ON після нього. Також немає перевіреного первинного OFF о 05:03:45 чи 05:28:53. Тому наразі не виконуються достатні критерії ані **LONG_INTERVAL_SUPPORTED**, ані **SPLIT_SUPPORTED**. Обов'язковий висновок: **UNRESOLVED**.

Користувач **відкликав графік air-alarms.in.ua як свідчення вечірнього завершення**. З нього не виводиться жоден стан AIR ON/OFF для міської громади. Це не є відкликанням окремого раніше поданого **Alerts.in.ua owner CSV**: схожі назви сайтів позначають різні джерела та різні форми даних.

**Рекомендація:** не змінювати canonical parent, historical classification, ACTIVE event або production JSON. Добути один хронологічний первинний журнал станів AIR для точної географії «м. Харків та Харківська територіальна громада» за 2025-03-05 19:08:24Z — 2025-03-06 03:28:53Z.

## 2. Preflight та межі виконання

Прочитані актуальні main:PROJECT_STATE.md та main:CHANGELOG.md. Перевірений current main HEAD при підготовці: 3b43a588f31bf806514ee11cf8c153c039256905. Найновіші координаційні записи описують C3-RC2, C6-R1 та C4 як незалежні часткові дослідження, без дозволу на cutover.

Підстави C4-KH-06:
- попередній затверджений research decision: [2a11a637](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/2a11a637a76ab3f9c862e9a62177848ff0dfafa0) / C4_KHARKIV_06_DECISION.md (blob 5bcb71b6);
- contemporary corroboration: [a60121cf](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/a60121cf3acbc3874d0dbc85098f22649e8365ec);
- C4-E1 [48e25ad](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/48e25ad158317728639c9305171ccbf251bec523) / c4_binding_exception_validation.json (blob e8715c3f);
- попередній bounded research [ded2e251](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/ded2e251b2150549af128c9ff09d4e73742da0cc), source timeline та lag JSON;
- чинна географічна конфігурація main:kyiv-air-alerts-grafana/scripts/audit_city_sources.py: Kharkiv preferred_source_type=exact_city, hromada «м. Харків та Харківська територіальна громада», known_coverage_start=2025-02-17.

Не здійснювалися нові SELECT до Neon, Neon DML/DDL, перевірка оригінальних CSV на рівні байтів, запуск GitHub Actions, зміни в main, site-prod, WIP чи historical verdict. Авторські щоденні CSV 2025-03-05/06 та повний Telegram messages.html у цьому виконанні не були змонтовані: їхній зміст і хеші нижче наведено **за раніше збереженими доказовими матеріалами**, не як щойно відтворений byte-level proof. Раніше підготовлені kharkiv6_suspilne_evidence_2025-03-05_06.md/.csv тут не прочитані повторно.

## 3. Джерела та межі їхньої доказовості

| Джерело | Що засвідчує | Що не доведено |
| --- | --- | --- |
| **Vadimkin**, original official_data_uk.csv / поточний Neon parent | Запис інтервалу 21:08:24–21:47:55; для Neon це поточна межа canonical parent | Чи відповідає 21:47:55 автентичному реальному city-hromada OFF; upstream state/message ID, географічний кросвок |
| **Alerts.in.ua**, owner CSV 5–6 березня | Збережений раніше інтервал 21:08:24–05:03:45, точність у CSV до секунд | Оригінальні байти та географічна клітинка не перечитані під час цього виконання; API/публікаційний lag не відомий |
| [ZN.UA, публікація 6.03.2025](https://zn.ua/ukr/war/shakhed-vluchiv-u-kharkivsku-bahatopoverkhivku-terekhoa.html) | Повідомляє саме про **місто**, початок 21:08, продовження тривоги після 05:00 та відбій о 05:03; точність **хвилина** | Не первинний signed AIR state log; джерело точного часу та незалежність upstream від інших агрегаторів невідомі |
| **«Суспільне Харків» Telegram**, попередній витяг messages.html | Раніше повідомлено про city ON 21:08:32 та city OFF 05:28:53 і три message IDs; це **часи публікацій** | Не встановлено час upstream події, механізм автоматизації й 25-хвилинну затримку; raw html тут не reread |
| [Харківська ОВА, 12.03.2025](https://kharkivoda.gov.ua/news/130659) та [Суспільне, 22.02.2025](https://suspilne.media/kharkiv/954963-u-harkovi-zapracuvala-sistema-okremih-povitranih-trivog/) | Система розрізняла тривогу Харкова і решти області з 22.02.2025; ОВА описує передачу команд через обласного й міського чергових | Жоден із матеріалів не містить журналу подій саме 5–6.03 |
| [air-alarms.in.ua, статистика](https://air-alarms.in.ua/region/kharkiv?from=2025-03-05&to=2025-03-06#statistic) | Графік **фактів оголошення** за годинами, 14 агрегованих обласних/районних тривог для двох діб | Не відображає стан міської тривоги впродовж кожної години; **вилучений із доказів часу OFF** |

Документація [Vadimkin](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/blob/main/datasets/README.md) розрізняє official і volunteer datasets та каже, що timestamps у датасеті UTC. Позначка official у назві датасету, однак, не замінює автентифікований upstream message/state trace конкретної події.

У згаданому раніше owner manifest 5 березня: 122 рядки, SHA-256 3113253b860c5678927b40353308ed51b435b07b16a00cb9bcc88529f9417062. За 6 березня: 131 рядок, SHA-256 b5a4c7a8b64f44dec66a0313b346120e98d154b0c78fb2f99ff5ed1815b96349. Це **попередні записи**, не повторно обчислені контрольні суми. CSV не вказує timezone у клітинках; прийнята інтерпретація Europe/Kyiv (+02:00 у березні).

## 4. Зіставлена хронологія

| Дата, Київ | UTC | Подія / запис | Рівень доказу |
| --- | --- | --- | --- |
| **05.03 21:08:24** | 05.03 19:08:24Z | AIR ON, однаковий початок Alerts.in.ua та Vadimkin/Neon | Попередні джерельні дані |
| **05.03 21:08:32** | 05.03 19:08:32Z | «Суспільне» city AIR ON, попередній витяг message55081 | Попередній архівний витяг, повторно не засвідчено |
| **05.03 21:47:55** | 05.03 19:47:55Z | Vadimkin / Neon end для parent a556ee0d-4a90-40b4-adf1-db55646cd05b | **Dataset boundary; official OFF not proven** |
| **06.03 близько 05:01** | 06.03 близько 03:01Z | ZN.UA публікує новину (згодом доповнену), стверджує, що тривога у місті почалася о 21:08 і триває понад 7 годин | Журналістське свідчення, без точного upstream |
| **06.03 05:03** | 06.03 03:03Z (лише хвилина) | ZN.UA повідомляє про скасування міської тривоги | Незалежна публікація, точність хвилина |
| **06.03 05:03:45** | 06.03 03:03:45Z | Alerts.in.ua owner CSV: кінець довгого інтервалу | Попередній CSV, точність секунди |
| **06.03 05:28:46** | 06.03 03:28:46Z | За попереднім архівним витягом message55096 ще вказує, що тривога міста триває | Публікаційна мітка, зміст повторно не прочитаний |
| **06.03 05:28:53** | 06.03 03:28:53Z | За попереднім витягом message55097: міський AIR OFF | Публікаційна мітка, не official upstream OFF |

Точність ZN.UA лише до хвилини. Не можна з цього джерела вивести секунди «:45» або вважати, що час доповнення статті збігається з її первинною датою публікації 05:01.

Тривалість **довгого** інтервалу: 7 год 55 хв 21 с. Тривалість **короткого**: 39 хв 31 с. Розходження кінців: **7 год 15 хв 50 с**. Різниця Telegram публікації ON від Alerts.in.ua ON, якщо обидва відображають ту саму подію: **8 с**. Різниця Telegram публікації OFF від Alerts.in.ua OFF: **25 хв 08 с**. Затримка Telegram (publication lag) дорівнює цій різниці **лише якщо** первинна подія відбулась о 05:03:45 за тією ж географією, а Telegram запізнився. Ця умова не доведена.

## 5. Результат перевірки робочих гіпотез

### A. Ранній OFF Vadimkin о 21:47:55

На користь короткого інтервалу наразі є конкретна dataset boundary та відповідний canonical Neon parent. Звідси не випливає, що офіційний міський диспетчер справді передав OFF саме о 21:47:55. Немає окремого authenticated city OFF та немає прив'язаного до нього повторного city ON в інтервалі до 05:03. Тому **SPLIT_SUPPORTED не доведено**.

Водночас назва «official» у Vadimkin означає, що його раннє закриття не варто списувати на помилку без аналізу каналу-джерела, ідентифікатора території, механізму групування та обробки завершення.

### B. Нічне продовження до 05:03

ZN.UA пише про **місто Харків**, що на момент новини тривога тривала понад сім годин від 21:08 5 березня, а в доповненні вказує відбій о 05:03. Це є **сильним contemporaneous свідченням** довгої тривоги (до хвилини), яке узгоджується з owner CSV. Стаття не надає первинної city-hromada ON/OFF послідовності. Отже, коротка окрема тривога після 21:47 чи неточна журналістська агрегація формально не спростовані.

Офіційна OVA інформація від 12 березня пояснює, чому географія критична: місто й решта області вже мали роздільне оповіщення. Чинне production-правило також використовує точну міську громаду, а не обласний чи районний proxy. Із самого збігу назв «Харків» у різних агрегаторах не випливає тотожність coverage.

### C. «Суспільне»: 25 хвилин publication lag?

За попереднім аналізом архіву messages.html було відібрано **18 релевантних повідомлень**. Це **не** 18 незалежних однозначно зіставлених пар із первинними API подіями. Попередній витяг повідомляв IDs message55081, message55096, message55097 та зазначені вище часові мітки. Оскільки raw export не доступний у цьому виконанні, дослівний текст, повторний SHA-256 і повну послідовність тижня тут **не сертифіковано**.

Різниця 8 секунд на ON означає, що канал міг публікувати сигнал майже одразу після події. Різниця 25 хв 08 с на OFF **не відповідає гіпотезі однакової постійної затримки** для обох напрямів. Це однак не виключає черги, збою polling, різниці апстримів, відмінної географії або реального пізнішого OFF.

У поточному доступному наборі **0 заново автентифікованих paired primary-to-Telegram подій**. Тому окремі median, p90, max, IQR, outlier rate для ON і OFF **NOT ESTIMABLE**. Відсутнє пряме підтвердження того, чи повідомлення були автоматичними, редакційними чи змішаними. Шаблонність і семисекундна послідовність двох повідомлень — лише індикатори, а не атрибуція системи публікації.

### D. Відкликаний графік air-alarms.in.ua

На наданому скриншоті: інтервал 05–06.03.2025; «Райони»; Харківська область; **14** «рівня області (в т. ч. об'єднаних з р-нів)»; погодинні значення за кількістю. Сума ненульових годин дорівнює **14**. Опис сайту визначає одиницю обліку як **факт оголошення**, а обласний ряд може включати неперервні проміжки, об'єднані з районних.

Тож нуль о 22:00–23:00 означає відсутність нового оголошення, а не відсутність активної раніше оголошеної тривоги. Більше того, цей обласний графік не є журналом станів міської громади. За рішенням користувача він має статус **WITHDRAWN / EXCLUDED FROM END-TIME ADJUDICATION** і не підвищує доказову вагу жодної версії. Збережені раніше owner Alerts.in.ua CSV — окреме джерело, яке не зачіпає відкликання.

## 6. Вплив на canonical дані та міграцію Neon

| Об'єкт | Раніше прийнятий стан | Дозволене рішення зараз |
| --- | --- | --- |
| Canonical parent a556ee0d-4a90-40b4-adf1-db55646cd05b | Кінець 05.03.2025 19:47:55Z (21:47:55 Kyiv) | **KEEP**, без retimestamp та forced identity |
| Historical classification 8c01721e-b4e8-4b63-b789-9801efbd63f8 | STRICT_EVENT_POSITIVE / UNBOUND / parent UID NULL, один source membership | **KEEP** verdict, evidence, source; не переводити в BOUND |
| Attack event dc3a63ec-d9f8-412c-b0a1-09dd9398b27b | ACTIVE, пов'язаний із historical classification, один source membership за раніше прийнятим readback | **KEEP** event та асоціації |

Навіть після майбутньої сертифікації довгого інтервалу потрібен окремий owner-approved producer/identity/parity correction design; пряме редагування одного end timestamp без перевірки downstream та deterministic identity може спричинити нові неконсистентності. Статус C4 загалом не змінюється. Інші **24 UNBOUND** залишаються незалежними від Kharkiv #6. C3/C6 та production/casualty/backfill треки не змінювалися.

## 7. Мінімальний доказ для закриття питання

Отримати **первинний незмінний журнал станів AIR** саме для «м. Харків та Харківська територіальна громада» за 05.03.2025 21:08–06.03.2025 05:29 (Europe/Kyiv), від міської автоматизованої системи оповіщення, диспетчерської ОВА або документованого official upstream. Для кожного transition потрібні: `territory_id`, тип AIR, стан ON/OFF, `event_at` з TZ, за наявності `received_at` / `published_at`, source event ID, provenance/журнал цілісності.

Перевірити чотири вузли: 21:08 ON; чи був 21:47:55 OFF; чи був наступний city ON; офіційний OFF поблизу 05:03 чи 05:28. Потім окремо звірити оригінальні city-hromada поля owner Alerts.in.ua CSV та первинні Vadimkin upstream messages, а для publication lag — повний Telegram messages.html із message ID/timezone і однозначно відповідними первинними переходами щонайменше за тиждень. Обчислити ON і OFF розподіли, різницю в затримках, оцінку 25-хвилинного OFF, визначити документований механізм доставки.

Рішення після надходження доказу:
- **LONG_INTERVAL_SUPPORTED**: підтверджена відсутність міського OFF між 21:08 та ранковим відбоєм і незалежно встановлено його час, або є достатня реконструкція нічного primary стану з поясненням Telegram publication lag. Секунди OFF допускаються тільки за секундним primary source.
- **SPLIT_SUPPORTED**: засвідчено фактичний city OFF близько 21:47:55, потім той самий city ON і OFF; надано точну послідовність і ID.
- **UNRESOLVED**: primary chronology не отримано або залишилися непорівнювані географії/часові поля. Це поточний статус.

### Конкретний owner action

**KEEP CURRENT DATA; obtain primary same-city transition log.** Не виконувати Neon DML/DDL, не переписувати production JSON, не змінювати historical verdict, event associations, main/site-prod/WIP workflows. Цей звіт — research-only evidence із зафіксованим відкликанням одного непридатного графіка, **не accepted checkpoint**. PROJECT_STATE.md і CHANGELOG.md не змінювати до окремої координаційної згоди.

## 8. Посилання для відтворення

1. [Попередній C4-KH-06 decision](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/2a11a637a76ab3f9c862e9a62177848ff0dfafa0/research/c4_25_individual_boundaries_2026_10_27/C4_KHARKIV_06_DECISION.md).
2. [Додаток contemporaneous corroboration](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/a60121cf3acbc3874d0dbc85098f22649e8365ec/research/c4_25_individual_boundaries_2026_10_27/C4_KHARKIV_06_CONTEMPORANEOUS_CORROBORATION_2026_10_28.md).
3. [C4-E1 historical binding validation](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/48e25ad158317728639c9305171ccbf251bec523/research/c4_25_individual_boundaries_2026_10_27/c4_binding_exception_validation.json).
4. [Раніше оформлена KH-06 bounded adjudication](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/ded2e251b2150549af128c9ff09d4e73742da0cc/research/c4_kharkiv_06_targeted_lag_2026_10_28/C4_KHARKIV_06_FINAL_ADJUDICATION.md).
5. [ZN.UA, 06.03.2025, 05:01 (доповнено)](https://zn.ua/ukr/war/shakhed-vluchiv-u-kharkivsku-bahatopoverkhivku-terekhoa.html).
6. [ОВА, 12.03.2025 — city/oblast диференціація](https://kharkivoda.gov.ua/news/130659).
7. [Суспільне, запуск окремих міських тривог](https://suspilne.media/kharkiv/954963-u-harkovi-zapracuvala-sistema-okremih-povitranih-trivog/).
8. [air-alarms.in.ua, опис методології та сторінка за 5–6.03](https://air-alarms.in.ua/region/kharkiv?from=2025-03-05&to=2025-03-06#statistic): **використовується тільки для пояснення непридатності відкликаного графіка**.
9. [Vadimkin dataset README](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/blob/main/datasets/README.md).

No CI or newly independent Neon readback is claimed for this document.

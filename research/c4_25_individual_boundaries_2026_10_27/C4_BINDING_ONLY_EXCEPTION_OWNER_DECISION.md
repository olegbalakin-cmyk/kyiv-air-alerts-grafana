# C4: вузькі винятки зі зв'язування historical→canonical, рішення для власника (ПРОПОЗИЦІЯ)

**Рішення запропоноване, не прийняте. ЖОДНОГО production/Neon запису або cutover.**

## Що говорить наявний контракт

- Frozen contract [`e9dcbdf2...`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/2a11a637a76ab3f9c862e9a62177848ff0dfafa0/research/c4_25_individual_boundaries_2026_10_27/C4_FINAL_OWNER_REVIEW.md) прямо допускає `attack_event_classifications.binding_state = UNBOUND` з `alert_episode_uid = NULL`. `BOUND` вимагає повного збігу city/AIR/closed, exact microsecond start/end, deterministic identity і єдиного батька; nearest-time заборонений.
- Прийнятий [Neon migration closure audit](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/4cc20029466795f16b0c648d84acbf6d50e75c66/research/neon_migration_closure_audit_2026-10-10.json), критерій `C4`: ID/hash parity **або explicit accepted bounded exclusions**. Це дозволяє прийняти **обмежені винятки лише зі збігу parent**, не оголосити втрату 25 історичних класифікацій нормою і не знизити поріг звичайного авто-binding.
- [C4 owner plan `2a11a637`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/2a11a637a76ab3f9c862e9a62177848ff0dfafa0) підтверджує 25 різних classification UID і 25 поточних часових canonical-кандидатів; 18/18 Kyiv official_json = Neon exact source bounds; 3 Lviv physical UUID lineage; 24 identity-contract blockers + 1 Kharkiv source conflict. **Ні одна стара класифікація не має дозволу на BOUND**.

## Рекомендований підхід

**Не перезаписувати canonical alerts або старі класифікації. Не додавати зараз нову lineage-таблицю.** Запропонувати власнику прийняти реєстр `c4_parent_binding_only_exception_proposal.json` на **25 точних `classification_uid`** із категорією `EXCEPTION_FROM_EXACT_PARENT_BINDING_PARITY_ONLY`.

Це не зміна поля `binding_state` у БД. Старі 25 лишаються `UNBOUND`, а в реєстрі незалежно вказані old historical identity, source proof, offline candidate UID, scope і current status. Не використовувати candidate UID у продакшен-запитах без окремого доказу й дозволу.

**Винятки стосуються тільки точного збігу parent/FK.** Усі 25 класифікацій залишаються в історичному denominator та повинні пройти семантичну перевірку verdict/evidence/source/event. Нічого не виключати з JSON / поточних метрик. Із них 16 `NO_CONFIRMED_EVENT`, 7 `NEEDS_REVIEW`, 1 `STRICT_EVENT_POSITIVE`, 1 `SENSITIVITY_EVENT_POSITIVE`; два ACTIVE `attack_events` (Запоріжжя №5, Харків №6) зберігаються без зміни. Якщо якийсь майбутній Neon-читач робить `INNER JOIN` тільки по `alert_episode_uid`, він **не має права непомітно втратити** ці historical outcome/event rows або змінити опубліковані цифри. До parity output diff поточний Git JSON залишається авторитетним для публікації.

**Харків №6**: окремий `SOURCE_CONFLICT` (час завершення відрізняється на 7 год 15 хв 50 с), тимчасово `UNBOUND`; історичний positive event збережений. Не вибирати джерело без доказу.

## Чому це рух уперед

Для решти історичного корпусу **можна продовжувати доказ C4 без очікування на новий lineage-механізм**: source/verdict/classification-key/source-link/event-key/identity parity, а для 25 записів явний виняток **лише з parent-link parity**. Умовою C4 PASS буде доказ інших потрібних історичних інваріантів плюс окреме прийняття винятків. Цей реєстр сам по собі C4 PASS не встановлює.

**Не плутати C4 з усією міграцією**: інші C1–C3/C5–C10 потрібно закривати незалежно (writer/due completeness/reader cutover/recovery). Зокрема, `main:.github/workflows/explosion-monitor-wip.yml` на 2026-10-28 містить `if: false` на WIP monitor job; це окремий operational hold, який не виправляється цими 25 cases.

### Мінімальна наступна перевірка

1. Протестувати partition `frozen historical corpus = exact UID set 25 + all remaining` без пропуску або дубля, з повною semantic parity за всіма полями, крім явно вилученого parent FK.
2. Порівняти будь-які результати майбутніх Neon-читацьких запитів з нинішнім `site-prod` JSON; не втратити 2 positive events і не змінити міські історичні показники. 
3. Якщо тести PASS, повернути реєстр і **окреме owner-approval рішення** щодо прийняття цих 25 `BINDING_ONLY` винятків, не просити зараз дозволу на Neon DML/DDL або масовий перезапис.

**Заборонено**: оголошувати 25 `BOUND`, виключати 25 зі статистики/семантичного паритету, робити 25 INSERT canonical parents, переписувати нинішні межі, змінювати historic verdict/source/event, запускати production updater або cutover. Повернення до lineage repair допустиме пізніше, не як блокер цього рішення.

JSON manifest має 25 rows, 25 unique classifications, 25 unique parent candidates, 18 source-verified Kyiv equality, 2 active events, 0 пропонованих записів. Проєктний статус: `C4=NOT_PROVEN`, `NEON_AUTHORITY_ACTIVE=NO`.

# Повітряні тривоги у Києві — Grafana dashboard

Публічний dashboard для статистики повітряних тривог у Києві. Дані оновлюються автоматично через GitHub Actions.

## Джерела

1. Основне: офіційний JSON Порталу відкритих даних Києва  
   https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/data/download
2. Fallback для завершених подій, яких ще немає в JSON: офіційна live-історія Kyiv Digital  
   https://kyiv.digital/storage/air-alert/stats.html

Поточний календарний день завжди виключено.

## Що рахується

Dashboard містить ті самі шість рядів, що й щотижневий пакет:

- середня кількість тривог на день у кожному завершеному місяці;
- середня кількість тривог на день у кожному повному тижні понеділок–неділя;
- середній сумарний час під тривогою на одну календарну добу в кожному завершеному місяці;
- середня тривалість однієї тривоги за місяцем її старту;
- сумарний час під тривогою щодня за останні 28 завершених днів;
- кількість тривог за днем старту + середня тривалість тривоги за останні 28 завершених днів.

Для добової тривалості інтервали, що переходять через північ, діляться по календарних добах у `Europe/Kyiv`. Перекриття тривог зливаються, щоб той самий час не рахувався двічі.

## Автооновлення

`.github/workflows/update.yml` запускається двічі на день і вручну через **Actions → Update Kyiv air-alert data → Run workflow**. Він:

1. завантажує офіційний JSON;
2. читає live-історію Kyiv Digital;
3. додає лише завершені live-події після останньої події офіційного JSON;
4. виключає поточний день;
5. перераховує `data/dashboard_data.json` та CSV;
6. генерує `grafana/dashboard.json` з правильною raw-URL саме цього GitHub repo;
7. комітить зміни назад у repo.

## Перший запуск у GitHub

Створи **public repository** з назвою `kyiv-air-alerts-grafana` і завантаж в корінь увесь вміст цього пакета. Після першого push workflow має стартувати автоматично. Якщо ні, відкрий **Actions → Update Kyiv air-alert data → Run workflow**.

Після успішного run у repo з'явиться/оновиться `grafana/dashboard.json`.

## Налаштування Grafana Cloud Free

1. Створи безкоштовний Grafana Cloud stack.
2. У Grafana відкрий **Connections → Data sources → Add new data source**.
3. Знайди **Infinity** і створи data source з назвою `Infinity`. У Grafana Cloud Infinity уже встановлений.
4. Для нашого публічного GitHub JSON автентифікація не потрібна. `Base URL` можна залишити порожнім. Якщо Grafana просить allowlist, додай `https://raw.githubusercontent.com` у **Allowed hosts**.
5. Відкрий **Dashboards → New → Import** та завантаж `grafana/dashboard.json` із repo.
6. На екрані імпорту вибери створений data source `Infinity` для `DS_INFINITY` і натисни **Import**.

Усі запити в dashboard використовують backend parser Infinity, щоб dashboard був сумісний із зовнішнім public sharing.

## Зробити dashboard публічним

Відкрий dashboard → **Share → Share externally**. Якщо цього пункту немає у твоєму Grafana Cloud stack, функцію треба ввімкнути для stack через Grafana; після ввімкнення зовнішній URL відкривається без Grafana-акаунта.

## Файли

- `scripts/update_data.py` — отримання, злиття та агрегація даних;
- `scripts/render_dashboard.py` — підставляє raw GitHub URL у dashboard;
- `data/dashboard_data.json` — єдиний JSON, який читає Grafana;
- `data/short_28d.csv` — короткий горизонт;
- `data/monthly.csv`, `data/weekly.csv` — агрегати для перевірки;
- `data/alerts_combined.json` — аудитний event-level файл після першого live run;
- `grafana/dashboard.template.json` — шаблон;
- `grafana/dashboard.json` — генерується GitHub Actions;
- `.github/workflows/update.yml` — автоматичне оновлення.

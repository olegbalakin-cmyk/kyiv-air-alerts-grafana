# Відтворення перевірки

Це діагностичні файли. Жоден із них не запускає REVIEW/PROMOTE, production workflow чи deployment.

- REPORT_UA.md — висновок, контрольні події, статуси гіпотез і план.
- cases.json — джерела, дати, основні та умовні контролі; strict_primary_control визначає сувору вибірку.
- input_manifest.json — незмінні refs, шляхи та Git blob SHA використаних входів.
- first_appearance_proof.json — 12 незмінних Git-знімків, absent/present для шести контролів.
- offline_results.json — локальне відтворення 23 міських рядів, фільтри, повтори та контроль незмінності входів.
- actions_observations.json — обмежені перевірені результати Actions; UNKNOWN збережено явно.
- site_observations.json — прочитані браузером підсумки й прив'язка живого frontend до даних.
- read_only_probe.py — локальний аналіз; без мережевих викликів і запису вхідних файлів.

Для повторення offline-перевірки в окремій scratch-директорії відтворіть входи manifest за їхніми незмінними URL, використовуючи local як відносний шлях. Перевірте кожний Git blob SHA:

```python
hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
```

Покладіть цей research-каталог у research/casualty_root_cause_2026_11_10 під тією самою scratch-директорією. Запустіть:

```bash
python research/casualty_root_cause_2026_11_10/read_only_probe.py
```

Скрипт виконує тільки loader/pure-функції вихідних модулів. Недоступні мережеві imports і виклик __main__ вилучаються через AST; тіла функцій залишаються без змін. Він не викликає основний генератор та не модифікує реальні кандидатські статуси. Єдиний запис — локальний offline_results.json. Для наочного тесту об'єднання тригерів створюється порожня синтетична черга з example.invalid; вона не містить реальних кандидатів.

Для first_appearance_proof можна повторно отримати before.url та after.url і перевірити bytes, git_blob_sha, sha256 та absent_then_present_candidate_ids. Поява в Git не встановлює часу історичної індексації Google або зміни тексту статті.

Великі вхідні JSON не дублюються в research-гілці: вони вже збережені в історії репозиторію за незмінними SHA. Не підміняйте ці входи поточними HEAD під час відтворення.

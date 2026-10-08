const state = {
  data: null,
  features: { attack_events: false },
  kyivThreatMix: null,
  explorations: null,
  charts: {},
  tableSort: { key: "alerts", direction: "desc" },
  lastAllCitiesRows: []
};

const DATA_URL = "data.json";
const FEATURES_URL = "features.json";
const KYIV_THREAT_MIX_URL = "kyiv-threat-mix-data.json";
const EXPLORATIONS_URL = "explorations-test-data.json";
const EXPLOSION_LIVE_URL = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/multicity-wip-2026-09-16/kyiv-air-alerts-grafana/data/explosions_test.json";
const COLORS = ["#62a0ea", "#8ff0a4", "#f8e45c"];
const EXPLOSION_COLOR = "#ff9f43";
const TIME_PROFILE_COLOR = "#ef4444";
const TIME_PROFILE_COLORS = ["#ef4444", "#62a0ea", "#8ff0a4", "#f8e45c", "#c061cb", "#ff9f43"];
const KYIV_THREAT_CAUSE_ORDER = ["drone", "massive-drone", "missile", "ballistic", "mig", "combined", "unknown"];
const KYIV_THREAT_CAUSE_COLORS = {
  "drone": "#62a0ea",
  "massive-drone": "#3dd6b5",
  "missile": "#ff7b72",
  "ballistic": "#ff9b54",
  "mig": "#c061cb",
  "combined": "#f8e45c",
  "unknown": "#7f8c99"
};
const PARTIAL_PERIOD_DASH = [3, 4];
const TOUR_STORAGE_KEY = "air-alerts-intro-tour-v4";
const TOUR_STEPS = [
  {
    selector:".controls-panel",
    titleUk:"Оберіть місто і масштаб",
    titleEn:"Choose a city and time scale",
    textUk:"Тут можна змінити місто та спосіб групування часу: від останніх 28 днів до місяців і довших ковзних вікон. За замовчуванням відкривається помісячний ряд.",
    textEn:"Choose the city and how time is grouped, from the last 28 days to months and longer rolling windows. The default view is monthly."
  },
  {
    selector:"#cityIntensityChart",
    closest:".chart-card",
    titleUk:"Інтенсивність тривог",
    titleEn:"Alert intensity",
    textUk:"Стовпчики показують середній час під тривогою на добу, лінія — середню кількість тривог на день. У режимі «Останні 28 днів» поточний неповний день позначений пунктиром. Показники в легенді можна вмикати й вимикати.",
    textEn:"Bars show average time under alert per day; the line shows average alerts per day. In the Last 28 days view, the current incomplete day is dashed. Legend items can be toggled on and off."
  },
  {
    selector:"#alertBurdenSection",
    titleUk:"Тривалість і навантаження",
    titleEn:"Duration and burden",
    textUk:"Тут видно те, що губиться в середніх: яку частку місяця становили дні з різним навантаженням, а також найдовшу тривогу й найдовший безперервний період без тривог. Дні без тривог можна виключити з першого графіка.",
    textEn:"This section shows what averages hide: how the month was split among days with different alert burdens, plus the longest alert and the longest continuous alert-free spell. Days without alerts can be excluded from the first chart."
  },
  {
    selector:"#timeOfDaySection",
    titleUk:"Два погляди на час доби",
    titleEn:"Two views of time of day",
    textUk:"Перший графік показує форму добового профілю: 100% — власний пік вибраного періоду. Деталізацію можна перемикати між 15 хв, 30 хв і 1 годиною. Другий показує, яка частка всього фактичного часу під тривогою припала на 00–06, 06–12, 12–18 і 18–24.",
    textEn:"The first chart shows the shape of the daily profile: 100% is the selected period's own peak. You can switch the interval between 15 minutes, 30 minutes and 1 hour. The second shows what share of all actual alert time fell in 00–06, 06–12, 12–18 and 18–24."
  },
  {
    selector:"#kyivThreatCausesSection",
    titleUk:"Причини тривог у Києві",
    titleEn:"Alert causes in Kyiv",
    textUk:"Для Києва окремо показано, з яких причин складався час під тривогою за даними Kyiv Digital. Цей блок доступний лише для Києва, бо для інших міст таких даних поки немає.",
    textEn:"For Kyiv, this section shows which causes made up the time under alert using Kyiv Digital data. It is Kyiv-only because comparable data are not yet available for the other cities."
  },
  {
    selector:"#casualtySection",
    titleUk:"Наслідки атак",
    titleEn:"Attack consequences",
    textUk:"Окремий графік показує загиблих унаслідок повітряних атак. Для нього можна перемикатися між місячним і річним представленням та обирати рік.",
    textEn:"A separate chart shows deaths caused by aerial attacks. It can be viewed by month or year, with a year selector."
  },
  {
    selector:".comparison-controls",
    titleUk:"Порівнюйте міста",
    titleEn:"Compare cities",
    textUk:"Оберіть два або три міста. Порівняльні графіки використовують лише періоди, доступні для всіх вибраних рядів, тому межі можуть відрізнятися від графіка одного міста.",
    textEn:"Choose two or three cities. Comparison charts use only periods available for every selected series, so their date bounds may differ from a single-city chart."
  },
  {
    selector:"#allCitiesSection",
    titleUk:"Огляд усіх міст",
    titleEn:"All-city overview",
    textUk:"У таблиці можна швидко порівняти всі 23 ряди, змінити горизонт або задати власний діапазон дат. Майже кожен графік також можна вивантажити у CSV у поточному представленні.",
    textEn:"The table provides a quick comparison of all 23 series, with preset horizons or a custom date range. Almost every chart can also be exported to CSV in its current view."
  }
];
const GRID = "rgba(148,163,184,.16)";
const TEXT = "#b8c4cf";
const HEATMAP_RANGES = ["7d", "30d", "90d", "180d", "year", "all"];
const TIME_OF_DAY_BIN_MINUTES = [15, 30, 60];
const TABLE_RANGES = ["7d", "30d", "90d", "year", "common", "custom"];
const TABLE_SORT_COLUMNS = [
  { key:"label", labelUk:"Місто / ряд", labelEn:"City / series", defaultDirection:"asc" },
  { key:"alerts", labelUk:"Тривог", labelEn:"Alerts", defaultDirection:"desc" },
  { key:"hours", labelUk:"Годин", labelEn:"Hours", defaultDirection:"desc" },
  { key:"duration", labelUk:"Сер. тривалість", labelEn:"Avg. duration", defaultDirection:"desc" },
  { key:"coverage", labelUk:"Покриття", labelEn:"Coverage", defaultDirection:"asc" }
];


const LANGUAGE_STORAGE_KEY="air-alerts-language-v1";
const CITY_LABELS_EN={kyiv:"Kyiv",kharkiv:"Kharkiv",zaporizhzhia:"Zaporizhzhia",cherkasy:"Cherkasy (Cherkasy District)",zhytomyr:"Zhytomyr (Zhytomyr District)",dnipro:"Dnipro (Dnipro District)",khmelnytskyi:"Khmelnytskyi (Khmelnytskyi District)",poltava:"Poltava (Poltava District)",rivne:"Rivne (Rivne District)",sumy:"Sumy (Sumy District)",vinnytsia:"Vinnytsia (Vinnytsia District)",kropyvnytskyi:"Kropyvnytskyi (Kropyvnytskyi District)",lviv:"Lviv (Lviv District)",chernihiv:"Chernihiv (Chernihiv District)",odesa:"Odesa (Odesa District)",kherson:"Kherson (Kherson District)",mykolaiv:"Mykolaiv (Mykolaiv District)",lutsk:"Lutsk (Lutsk District)",uzhhorod:"Uzhhorod (Uzhhorod District)",ivano_frankivsk:"Ivano-Frankivsk (Ivano-Frankivsk District)","ivano-frankivsk":"Ivano-Frankivsk (Ivano-Frankivsk District)",ternopil:"Ternopil (Ternopil District)",chernivtsi:"Chernivtsi (Chernivtsi District)",sevastopol:"Sevastopol (signals from the occupation administration)"};
const DISTRICT_LABELS_EN={cherkasy:"Cherkasy District",zhytomyr:"Zhytomyr District",dnipro:"Dnipro District",khmelnytskyi:"Khmelnytskyi District",poltava:"Poltava District",rivne:"Rivne District",sumy:"Sumy District",vinnytsia:"Vinnytsia District",kropyvnytskyi:"Kropyvnytskyi District",lviv:"Lviv District",chernihiv:"Chernihiv District",odesa:"Odesa District",kherson:"Kherson District",mykolaiv:"Mykolaiv District",lutsk:"Lutsk District",uzhhorod:"Uzhhorod District",ivano_frankivsk:"Ivano-Frankivsk District","ivano-frankivsk":"Ivano-Frankivsk District",ternopil:"Ternopil District",chernivtsi:"Chernivtsi District"};
function initialLanguage(){const q=new URLSearchParams(location.search).get("lang");if(q==="en"||q==="uk")return q;try{const s=localStorage.getItem(LANGUAGE_STORAGE_KEY);if(s==="en"||s==="uk")return s;}catch{}return"uk";}
let currentLanguage=initialLanguage();
function tr(uk,en){return currentLanguage==="en"?en:uk;}
function localeCode(){return currentLanguage==="en"?"en":"uk";}
function tableColumnLabel(c){return tr(c.labelUk,c.labelEn);}
function setLocalizedText(s,uk,en){const e=document.querySelector(s);if(e)e.textContent=tr(uk,en);}
function setLocalizedAttr(s,a,uk,en){const e=document.querySelector(s);if(e)e.setAttribute(a,tr(uk,en));}
function setOptionText(id,v,uk,en){const e=document.querySelector(`#${id} option[value="${v}"]`);if(e)e.textContent=tr(uk,en);}
function setKpiLabel(id,uk,en){const e=$(id)?.closest(".kpi-card")?.querySelector(".kpi-label");if(e)e.textContent=tr(uk,en);}
function setCardCopy(id,tu,te,su,se){const c=$(id)?.closest(".chart-card");if(!c)return;const h=c.querySelector("h3"),p=c.querySelector(".chart-subtitle");if(h)h.textContent=tr(tu,te);if(p)p.textContent=tr(su,se);}
function setSectionHeading(id,eu,ee,tu,te,du,de){const h=$(id)?.querySelector(".section-heading");if(!h)return;const e=h.querySelector(".eyebrow"),t=h.querySelector("h2"),p=h.querySelector("p");if(e&&eu)e.textContent=tr(eu,ee);if(t)t.textContent=tr(tu,te);if(p)p.textContent=tr(du,de);}

function methodologyHtml(){
 if(currentLanguage!=="en")return null;
 return `
  <div class="eyebrow">Methodology</div><h2>How to read the data</h2>
  <h3>What does the site show?</h3><p>The site shows the history of air alerts for 23 Ukrainian cities and monthly data on deaths caused by aerial attacks in those cities.</p><p>Kyiv, Kharkiv, Zaporizhzhia and Sevastopol use separate city-level alert series. The other 19 cities use the corresponding administrative district series. This is shown directly in the label, for example, “Lviv (Lviv District)”.</p><p>A district series is not a precise measure of alerts within the city alone: it may include signals that apply to other settlements in the district.</p>
  <h3>Where does the data come from?</h3><p>For Kyiv, the main alert sources are <a href="https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/" target="_blank" rel="noopener noreferrer">Kyiv Open Data Portal</a> and <a href="https://kyiv.digital/storage/air-alert/stats.html" target="_blank" rel="noopener noreferrer">Kyiv Digital</a>. For Kharkiv, Zaporizhzhia and district-level series, the historical base is <a href="https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset" target="_blank" rel="noopener noreferrer">ukrainian-air-raid-sirens-dataset</a>, with newer data supplied by the official <a href="https://api.ukrainealarm.com/api/v3" target="_blank" rel="noopener noreferrer">UkraineAlarm API</a>.</p><p>For Sevastopol, the site uses public city-level alert and all-clear signals posted by the occupation administration’s Telegram channel <a href="https://t.me/s/razvozhaev" target="_blank" rel="noopener noreferrer">@razvozhaev</a>. Naming the source describes data provenance and does not imply recognition of the occupation administration.</p><p>The death series are reconstructed from public reports by official bodies and media. For ongoing monitoring of Kyiv, sources include <a href="https://suspilne.media/kyiv/" target="_blank" rel="noopener noreferrer">Suspilne Kyiv</a>, <a href="https://hromadske.ua/kyyiv" target="_blank" rel="noopener noreferrer">hromadske Kyiv</a> and <a href="https://www.pravda.com.ua/" target="_blank" rel="noopener noreferrer">Ukrainska Pravda</a>.</p>
  <h3>How are the indicators calculated?</h3><p id="periodMethodology">Calculations use completed calendar days in the Europe/Kyiv time zone. Today is excluded. The 28-day indicators cover exactly the 28 completed days through yesterday.</p><ul class="methodology-metrics"><li><strong>Alerts per day</strong> — alerts that started in the selected period divided by calendar days.</li><li><strong>Hours under alert per day</strong> — total time under alert divided by days. Overlapping intervals are not counted twice. If an alert crosses midnight, its duration is split between the relevant calendar days.</li><li><strong>Average full alert duration</strong> — the average full duration of alerts that started in the selected period. If an alert ends in the next period, its full duration remains attributed to the period in which it started.</li></ul><p>City comparisons use only time periods available in all selected series.</p>
  <h3>How are deaths counted?</h3><p>For all 23 cities, the site shows a reconstructed monthly series of deaths within the city’s administrative boundaries. This remains a city-level measure even where the alert series is district-level.</p><p>The series includes deaths causally linked to missile, drone and other aerial attacks. Ground combat and artillery shelling are excluded. If a person later dies from injuries sustained in an attack, the death is attributed to the month of that attack.</p><p>Unresolved cases that still require review are excluded from confirmed totals. The current month is incomplete and may be updated. Because the historical series is reconstructed from public reporting, it should not be read as a guaranteed complete registry of all deaths.</p>
  <h3>What should be kept in mind?</h3><p>Different series begin on different dates. The start date is shown next to the selected city. The first incomplete period is not shown.</p><p>Donetsk and Luhansk are not yet included: they require a separate methodology, and oblast-level data are not substituted for city-level data.</p>
  <details class="methodology-details"><summary>Series start dates</summary><div class="methodology-detail-grid"><div><strong>City-level data</strong><ul><li>Kyiv — 28.02.2022</li><li>Sevastopol — 25.09.2023</li><li>Kharkiv — 17.02.2025</li><li>Zaporizhzhia — 19.03.2025</li></ul></div><div><strong>District series: date confirmed by the transition to district-level alerts</strong><ul><li>Cherkasy — 10.01.2025</li><li>Zhytomyr — 23.01.2025</li><li>Dnipro — 01.05.2025</li><li>Khmelnytskyi — 07.07.2025</li><li>Poltava — 01.08.2025</li><li>Rivne — 01.08.2025</li><li>Sumy — 06.08.2025</li><li>Vinnytsia — 21.08.2025</li><li>Kropyvnytskyi — 01.09.2025</li><li>Lviv — 01.09.2025</li><li>Chernihiv — 03.09.2025</li><li>Odesa — 04.11.2025</li></ul></div><div><strong>District series: date derived from the appearance of a stable district series</strong><ul><li>Kherson — 30.08.2025</li><li>Mykolaiv — 05.11.2025</li><li>Lutsk — 06.11.2025</li><li>Uzhhorod — 06.11.2025</li><li>Ivano-Frankivsk — 06.11.2025</li><li>Ternopil — 06.11.2025</li><li>Chernivtsi — 06.11.2025</li></ul></div></div></details>
  <details class="methodology-details"><summary>Technical source notes</summary><p>When continuity between adjacent sources is checked, two records may be treated as the same event if their timestamps differ by no more than 15 seconds. This tolerance is used only to validate the handoff between sources; event times themselves are neither shifted nor rounded.</p><p>Auxiliary sources used to verify source handoffs or close short gaps are not listed in the main description.</p><p>For Sevastopol, only complete “alert → all-clear” pairs are used. Incomplete episodes are not interpolated; a separate time correction is allowed only when there is direct external confirmation.</p></details>
  <details class="methodology-details"><summary>Test features</summary><p><strong>Alerts with reported explosions.</strong> This is a test-only strict metric for cities with a completed manual audit. The numerator counts alert episodes with a confirmed report specifically of explosions in the city that can be matched to that alert. Trends use a rolling 90-day window, with one chart point every 7 days.</p><p><strong>Time-of-day alert profile.</strong> The day is divided into 96 15-minute intervals. For each interval, the share of actual time under alert is calculated and then normalized to that series’ own peak.</p></details>`;
}
function applyStaticLanguage(){
 document.documentElement.lang=currentLanguage==="en"?"en":"uk";
 document.title=tr("Статистика повітряних тривог у містах України — графіки та порівняння","Air alerts in Ukrainian cities — charts and comparisons");
 const md=tr("Статистика повітряних тривог у Києві та обласних центрах України: кількість тривог, години під тривогою, середня тривалість, порівняння міст і дані про загиблих від повітряних атак.","Air-alert statistics for Kyiv and Ukrainian regional centres: alert counts, hours under alert, average duration, city comparisons and deaths from aerial attacks.");
 document.querySelector('meta[name="description"]')?.setAttribute("content",md);document.querySelector('meta[property="og:locale"]')?.setAttribute("content",currentLanguage==="en"?"en_US":"uk_UA");document.querySelector('meta[property="og:site_name"]')?.setAttribute("content",tr("Повітряні тривоги — міста України","Air alerts — Ukrainian cities"));document.querySelector('meta[property="og:title"]')?.setAttribute("content",tr("Статистика повітряних тривог у містах України","Air-alert statistics in Ukrainian cities"));document.querySelector('meta[property="og:description"]')?.setAttribute("content",md);document.querySelector('meta[name="twitter:title"]')?.setAttribute("content",tr("Статистика повітряних тривог у містах України","Air-alert statistics in Ukrainian cities"));document.querySelector('meta[name="twitter:description"]')?.setAttribute("content",md);
 setLocalizedText(".header-copy .eyebrow","Відкриті дані · міста України","Open data · Ukrainian cities");setLocalizedText(".header-copy h1","Повітряні тривоги","Air alerts");setLocalizedText(".header-copy .subtitle","Історичні дані про повітряні тривоги в обласних центрах України. Там, де тривога не оголошується окремо для міста, використовуються дані відповідного адміністративного району — це завжди явно позначено.","Historical air-alert data for Ukrainian regional centres. Where alerts are not issued separately for a city, the corresponding administrative district is used and clearly labelled.");
 setLocalizedAttr("#languageSwitch","aria-label","Мова","Language");$("langUk")?.setAttribute("aria-pressed",currentLanguage==="uk"?"true":"false");$("langEn")?.setAttribute("aria-pressed",currentLanguage==="en"?"true":"false");setLocalizedText("#showTour","Показати тур","Show tour");setLocalizedText("#copyLink","Скопіювати посилання","Copy link");
 setLocalizedAttr(".controls-panel","aria-label","Вибір міста і періоду","City and period selection");setLocalizedText('label[for="citySelect"]',"Місто","City");setLocalizedText('label[for="cityPeriod"]',"Інтервал","Interval");setOptionText("cityPeriod","daily28","Останні 28 днів","Last 28 days");setOptionText("cityPeriod","monthly","Місяці","Months");setOptionText("cityPeriod","calendarWeekly","Тижні","Weeks");setOptionText("cityPeriod","rolling30","Ковзні 30 днів","Rolling 30 days");setOptionText("cityPeriod","rolling90","Ковзні 90 днів","Rolling 90 days");setOptionText("cityPeriod","rolling180","Ковзні 180 днів","Rolling 180 days");
 for(const id of ["cityDateFrom","rolling7dDateFrom","shortDateFrom","compareDateFrom","tableDateFrom"])setLocalizedText(`label[for="${id}"]`,"Від","From");
 for(const id of ["cityDateTo","rolling7dDateTo","shortDateTo","compareDateTo","tableDateTo"])setLocalizedText(`label[for="${id}"]`,"До","To");
 setKpiLabel("kpiAlerts","Тривог за останні 28 завершених днів","Alerts in the last 28 completed days");setKpiLabel("kpiHours","Годин під тривогою за останні 28 завершених днів","Hours under alert in the last 28 completed days");setKpiLabel("kpiDuration","Середня тривалість тривог, що почалися за останні 28 завершених днів","Average duration of alerts that started in the last 28 completed days");setKpiLabel("kpiMaxDay","Найбільше тривог за день у цьому 28-денному вікні","Most alerts in one day within this 28-day window");setKpiLabel("kpiExplosionsPct","Тривог, під час яких повідомлялось про вибухи","Alerts with reported explosions");
 setCardCopy("cityIntensityChart","Інтенсивність тривог","Alert intensity","Стовпчики: сумарний час під тривогою в обраному періоді ÷ кількість календарних днів. Лінія: кількість тривог, що почалися в періоді ÷ кількість днів.","Bars: total time under alert in the selected period ÷ calendar days. Line: alerts that started in the period ÷ days.");setCardCopy("cityDurationChart","Середня тривалість однієї тривоги","Average duration of one alert","Середня тривалість усіх тривог, що почалися в обраному періоді. Якщо тривога закінчилася вже після завершення періоду, вся її тривалість відноситься до періоду старту.","Average full duration of alerts that started in the selected period. If an alert ends after the period, its full duration is attributed to the period in which it started.");
 setSectionHeading("timeOfDaySection","Час доби","Time of day","Як тривоги розподіляються протягом доби","How alerts are distributed through the day","Два взаємодоповнювальні погляди: детальний нормалізований профіль і фактичний розподіл усього часу під тривогою за частинами доби.","Two complementary views: a detailed normalized profile and the actual distribution of all alert time across parts of the day.");setSectionHeading("alertBurdenSection","Структура навантаження","Burden structure","Тривалість і навантаження","Duration and burden","Як розподілялися дні за часом під тривогою та як змінювалися найдовші епізоди.","How days were distributed by time under alert and how the longest episodes changed.");setSectionHeading("kyivThreatCausesSection","Київ","Kyiv","Причини повітряних тривог","Air-alert causes","Розподіл часу під тривогою за причиною, яку Kyiv Digital вказує для завершеної тривоги.","Distribution of time under alert by the cause assigned to a completed alert by Kyiv Digital.");setCardCopy("kyivThreatCausesChart","З чого складався час під тривогою","What time under alert consisted of","Кожен стовпчик — один завершений день. 100% = увесь класифікований час повітряної тривоги цього дня.","Each bar is one completed day. 100% = all classified air-alert time during that day.");setLocalizedText("#timeOfDayRangeLabel","Діапазони","Ranges");for(const [v,u,e] of [["7d","7 днів","7 days"],["30d","30 днів","30 days"],["90d","90 днів","90 days"],["180d","180 днів","180 days"],["year","Рік","Year"],["all","Від початку даних","From start of data"]]){const el=document.querySelector(`[data-time-range-label="${v}"]`);if(el)el.textContent=tr(u,e);}setLocalizedText('label[for="timeOfDayBin"]',"Інтервал","Interval");setLocalizedAttr("#timeOfDayBin","aria-label","Інтервал добового профілю","Time-of-day profile interval");for(const [v,u,e] of [["15","15 хв","15 min"],["30","30 хв","30 min"],["60","1 година","1 hour"]])setOptionText("timeOfDayBin",v,u,e);setLocalizedText("#timeOfDaySection .time-profile-note","100% — не частка часу під тривогою, а відносний максимум окремого профілю. У підказці показано також фактичну частку часу під тривогою.","100% is not the share of time under alert; it is each profile's own relative peak. The tooltip also shows the actual share of time under alert.");setLocalizedText('label[for="burdenYear"]',"Рік","Year");setLocalizedText('label[for="daypartYear"]',"Рік","Year");setLocalizedText("#heavyDaysExcludeZeroLabel","Не враховувати дні без тривог","Exclude days without alerts");setCardCopy("heavyDaysChart","Розподіл днів за часом під тривогою","Distribution of days by time under alert","100% кожного місяця розкладено за часткою днів без тривоги, до 1 год, 1–3, 3–6, 6–12 та 12+ годин під тривогою.","Each month is normalized to 100% and split by days with no alert, under 1 hour, 1–3, 3–6, 6–12, and 12+ hours under alert.");setCardCopy("extremesChart","Найдовша тривога і найдовша тиша","Longest alert and longest quiet spell","Ліва вісь — найдовша тривога, що почалася в місяці. Права вісь — найдовший безперервний проміжок без тривоги всередині місяця.","Left axis: the longest alert that started in the month. Right axis: the longest continuous alert-free spell within the month.");setCardCopy("daypartChart","Розподіл часу під тривогою за частинами доби","Distribution of alert time by part of day","100% фактичного часу під тривогою в кожному місяці розкладено на 00–06, 06–12, 12–18 та 18–24 за Europe/Kyiv.","100% of actual alert time in each month is split into 00–06, 06–12, 12–18 and 18–24 in Europe/Kyiv time.");setLocalizedText("#timeOfDaySection .daypart-note","На відміну від профілю вище, тут показана частка всього фактичного часу під тривогою, що припала на кожну частину доби.","Unlike the profile above, this shows the share of all actual alert time that fell in each part of the day.");
 setSectionHeading("rolling7dSection","Ковзні 7 днів","Rolling 7 days","Динаміка за 7-денним вікном","7-day rolling trend","Кожна точка охоплює 7 завершених календарних днів і датована останнім днем вікна; сусідні точки перекриваються на 6 днів. За замовчуванням показано поточний календарний рік.","Each point covers 7 completed calendar days and is dated by the window’s final day; adjacent points overlap by 6 days. The current calendar year is shown by default.");setLocalizedText('label[for="rolling7dYear"]',"Швидкий вибір","Quick range");setLocalizedAttr("#rolling7dYear","aria-label","Швидкий вибір періоду для 7-денного вікна","Quick range for the 7-day window");setCardCopy("rolling7dIntensityChart","Інтенсивність тривог","Alert intensity","Стовпчики: середній час під тривогою на добу за 7 днів. Лінія: середня кількість тривог на день за ті самі 7 днів.","Bars: average hours under alert per day across 7 days. Line: average alerts per day across the same 7 days.");setCardCopy("rolling7dDurationChart","Середня тривалість однієї тривоги","Average duration of one alert","Середня тривалість тривог, що почалися у відповідному 7-денному вікні.","Average duration of alerts that started within the corresponding 7-day window.");
 setSectionHeading("shortHorizonSection","Короткий горизонт","Short horizon","Щоденний розріз","Daily view","Доступні останні 28 завершених днів для обраного міста. Сьогоднішній день не включається.","The last 28 completed days are available for the selected city. Today is excluded.");setCardCopy("daily28HoursChart","Сумарний час під тривогою за день","Total time under alert per day","Скільки годин кожної календарної доби припало на повітряну тривогу. Якщо інтервали перекриваються, час не рахується двічі; тривога через північ розподіляється між відповідними днями.","Hours of each calendar day spent under air alert. Overlapping intervals are not counted twice; an alert crossing midnight is split between the relevant days.");setCardCopy("daily28AlertsDurationChart","Кількість тривог і середня тривалість за день","Alert count and average duration per day","Стовпчики — кількість тривог, що почалися цього дня. Лінія — середня тривалість тривог, що почалися цього дня.","Bars show alerts that started that day. The line shows the average duration of alerts that started that day.");
 setSectionHeading("casualtySection","","","Загиблі від повітряних атак РФ","Deaths from Russian aerial attacks","Пізні смерті від поранень віднесені до місяця самої атаки. Наземні бої та артилерійські обстріли не включені.","Deaths occurring later from attack-related injuries are attributed to the month of the attack. Ground combat and artillery shelling are excluded.");setLocalizedText('label[for="casualtyInterval"]',"Інтервал","Interval");setOptionText("casualtyInterval","monthly","Місяці","Months");setOptionText("casualtyInterval","yearly","Роки","Years");setLocalizedAttr("#casualtyInterval","aria-label","Інтервал для графіка загиблих","Interval for the deaths chart");setLocalizedText('label[for="casualtyYear"]',"Рік","Year");setLocalizedAttr("#casualtyYear","aria-label","Рік для графіка загиблих","Year for the deaths chart");
 setSectionHeading("comparisonSection","Порівняння","Comparison","Порівняння обраних міст","Compare selected cities","Для коректності графіки показують лише періоди, які одночасно є в усіх обраних рядах.","Charts use only periods that are available in all selected series.");for(const [id,u,e] of [["compareA","Місто A","City A"],["compareB","Місто B","City B"],["compareC","Місто C (необов’язково)","City C (optional)"],["comparePeriod","Інтервал","Interval"]])setLocalizedText(`label[for="${id}"]`,u,e);setOptionText("comparePeriod","daily28","Останні 28 днів","Last 28 days");setOptionText("comparePeriod","monthly","Місяці","Months");setOptionText("comparePeriod","calendarWeekly","Тижні","Weeks");setOptionText("comparePeriod","rolling30","Ковзні 30 днів","Rolling 30 days");setOptionText("comparePeriod","rolling90","Ковзні 90 днів","Rolling 90 days");setOptionText("comparePeriod","rolling180","Ковзні 180 днів","Rolling 180 days");
 setCardCopy("compareAlertsChart","Середня кількість тривог на день","Average alerts per day","Кількість тривог, що почалися в обраному періоді ÷ кількість календарних днів.","Alerts that started in the selected period ÷ calendar days.");setCardCopy("compareHoursChart","Середній час під тривогою на добу","Average time under alert per day","Сумарний час під тривогою в обраному періоді ÷ кількість календарних днів.","Total time under alert in the selected period ÷ calendar days.");setCardCopy("compareDurationChart","Середня тривалість однієї тривоги","Average duration of one alert","Середня тривалість тривог, що почалися в обраному періоді; тривалість відноситься до періоду старту.","Average duration of alerts that started in the selected period; duration is attributed to the period in which the alert started.");setCardCopy("compareTimeOfDayChart","Добовий профіль тривог","Time-of-day alert profile","Порівняння форми добового патерну. Кожне місто/район нормалізовано окремо: його власний найактивніший інтервал = 100%.","Comparison of the daily pattern. Each city/district is normalized separately: its own most active interval = 100%.");setLocalizedText('label[for="compareTimeOfDayRange"]',"Діапазон","Range");setLocalizedAttr("#compareTimeOfDayRange","aria-label","Діапазон добового профілю для порівняння","Time-of-day comparison range");for(const [v,u,e] of [["7d","7 днів","7 days"],["30d","30 днів","30 days"],["90d","90 днів","90 days"],["180d","180 днів","180 days"],["year","Рік","Year"],["all","Від початку даних","From start of data"]])setOptionText("compareTimeOfDayRange",v,u,e);setLocalizedText('label[for="compareTimeOfDayBin"]',"Інтервал","Interval");setLocalizedAttr("#compareTimeOfDayBin","aria-label","Інтервал добового профілю для порівняння","Time-of-day comparison interval");for(const [v,u,e] of [["15","15 хв","15 min"],["30","30 хв","30 min"],["60","1 година","1 hour"]])setOptionText("compareTimeOfDayBin",v,u,e);setCardCopy("compareExplosionsChart","Частка тривог із повідомленнями про вибухи","Share of alerts with reported explosions","Ковзне 90-денне вікно з кроком відображення 7 днів. Strict-метрика: підтверджене повідомлення саме про вибухи в місті, зіставлене з конкретною тривогою.","Rolling 90-day window, displayed every 7 days. Strict metric: a confirmed report specifically of explosions in the city, matched to a particular alert.");setCardCopy("compareCasualtiesChart","Загиблі від повітряних атак РФ","Deaths from Russian aerial attacks","Підтверджені смерті за місяцем атаки. Наземні бої та артилерійські обстріли не включені.","Confirmed deaths by month of attack. Ground combat and artillery shelling are excluded.");setLocalizedText('label[for="compareCasualtyInterval"]',"Інтервал","Interval");setOptionText("compareCasualtyInterval","monthly","Місяці","Months");setOptionText("compareCasualtyInterval","yearly","Роки","Years");setLocalizedAttr("#compareCasualtyInterval","aria-label","Інтервал для порівняння загиблих","Interval for death comparison");setLocalizedText('label[for="compareCasualtyYear"]',"Рік","Year");setLocalizedAttr("#compareCasualtyYear","aria-label","Рік для порівняння загиблих","Year for death comparison");
 setSectionHeading("allCitiesSection","Огляд","Overview","Усі міста","All cities","Порівняння ключових показників за спільний часовий діапазон.","Comparison of key indicators over a common time range.");setLocalizedText('label[for="allCitiesRange"]',"Швидкий вибір","Quick range");setLocalizedAttr("#allCitiesRange","aria-label","Швидкий вибір діапазону для таблиці всіх міст","Quick range for the all-cities table");for(const [v,u,e] of [["7d","7 днів","7 days"],["30d","30 днів","30 days"],["90d","90 днів","90 days"],["year","Рік","Year"],["common","Від початку спільних даних","From start of common data"],["custom","Довільно","Custom"]])setOptionText("allCitiesRange",v,u,e);
 const meth=$("methodologySection")||document.querySelector(".methodology");if(meth&&currentLanguage==="en")meth.innerHTML=methodologyHtml();
 const fs=document.querySelectorAll("footer span");if(fs[0])fs[0].innerHTML=tr('Дані та код: <a href="https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana">GitHub</a>','Data and code: <a href="https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana">GitHub</a>');if(fs[1])fs[1].textContent=tr("Зауваження до даних: @olbalakin у Telegram","Data corrections: @olbalakin on Telegram");setLocalizedAttr("#tourClose","aria-label","Закрити тур","Close tour");setLocalizedText("#tourPrev","Назад","Back");setLocalizedText("#tourSkip","Пропустити","Skip");setLocalizedText("#tourNext","Далі","Next");
}
function renderGeneratedAt(){if(!state.data)return;const g=state.data.meta?.generated_at||state.data.cities?.kyiv?.meta?.generated_at;$("updatedAt").textContent=g?tr(`Дані згенеровано ${String(g).replace("T"," ").slice(0,19)}`,`Data generated ${String(g).replace("T"," ").slice(0,19)}`):"";}
function setLanguage(lang,persist=true){const next=lang==="en"?"en":"uk";if(next!==currentLanguage){const p=new URLSearchParams(location.search);p.set("lang",next);location.search=p.toString();return;}if(persist){try{localStorage.setItem(LANGUAGE_STORAGE_KEY,next);}catch{}}}
function bindLanguageSwitch(){$("langUk")?.addEventListener("click",()=>setLanguage("uk"));$("langEn")?.addEventListener("click",()=>setLanguage("en"));}

function $(id) { return document.getElementById(id); }
function fmt(v, digits = 1) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(digits);
}
function formatDurationMinutes(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const total = Math.max(0, Math.round(n));
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  return tr(
    `${hours} год ${String(minutes).padStart(2, "0")} хв`,
    `${hours} hr ${String(minutes).padStart(2, "0")} min`
  );
}
function formatDurationHours(value) {
  const n = Number(value);
  return Number.isFinite(n) ? formatDurationMinutes(n * 60) : "—";
}
function setDurationChart(id, labels, datasets, unit = "minutes") {
  if (state.charts[id]) state.charts[id].destroy();
  const formatter = unit === "hours" ? formatDurationHours : formatDurationMinutes;
  const yTitle = tr("Тривалість","Duration");
  const options = chartOptions(yTitle);
  options.scales.y.ticks.callback = value => formatter(value);
  options.plugins.tooltip.callbacks = {
    label(context) {
      const prefix = context.dataset.label ? `${context.dataset.label}: ` : "";
      return prefix + formatter(context.parsed.y);
    }
  };
  state.charts[id] = new Chart($(id), {
    type: "line",
    data: { labels, datasets },
    options
  });
}
function labelFor(key) {
  if(currentLanguage==="en"&&CITY_LABELS_EN[key])return CITY_LABELS_EN[key];
  const mm=state.data.multicity_meta?.cities?.[key];
  return mm?.label||state.data.cities?.[key]?.meta?.city_label||key;
}
function cityKeys() {
  const keys = [...(state.data.multicity_meta?.production_city_keys || Object.keys(state.data.cities || {}))];
  return keys.sort((a, b) => {
    if (a === "kyiv") return -1;
    if (b === "kyiv") return 1;
    return labelFor(a).localeCompare(labelFor(b), localeCode(), { sensitivity: "base" });
  });
}
function sourceType(key) {
  return state.data.multicity_meta?.cities?.[key]?.source_type || state.data.cities?.[key]?.meta?.source_type || "unknown";
}
function coverageStart(key) {
  return state.data.multicity_meta?.cities?.[key]?.coverage_start || state.data.cities?.[key]?.meta?.coverage_start || state.data.cities?.[key]?.meta?.first_city_level_date || null;
}
function proxyRaion(key) {
  return state.data.multicity_meta?.cities?.[key]?.proxy_raion || state.data.cities?.[key]?.meta?.proxy_raion || null;
}
function typeText(key){return sourceType(key)==="raion_proxy"?tr("Дані по району","District data"):tr("Дані по місту","City data");}
function districtText(key){const raw=proxyRaion(key);return currentLanguage==="en"?(DISTRICT_LABELS_EN[key]||raw):raw;}
function rolling7dEnabled() {
  return state.data.multicity_meta?.weekly_mode === "rolling_7d";
}
function attackEventFeaturesEnabled() {
  return state.features?.attack_events === true;
}
async function loadPreviewFeatures() {
  try {
    const response = await fetch(FEATURES_URL + "?v=" + Date.now(), { cache: "no-store" });
    if (!response.ok) throw new Error("feature config HTTP " + response.status);
    const parsed = await response.json();
    return { attack_events: parsed?.attack_events === true };
  } catch (err) {
    console.warn("Preview feature config unavailable; attack-event features stay disabled", err);
    return { attack_events: false };
  }
}
function applyPreviewFeatureVisibility() {
  const enabled = attackEventFeaturesEnabled();
  document.querySelectorAll('[data-preview-feature="attack-events"]').forEach(el => {
    if (!enabled) el.classList.add("hidden");
  });
}
function explosionCity(key) {
  if (!attackEventFeaturesEnabled()) return null;
  const explosionKey = key === "ivano-frankivsk" ? "ivano_frankivsk" : key;
  return state.data.explosion_metric_test?.cities?.[explosionKey] || null;
}
function explosionEstimate(explosion) {
  if (!explosion) return null;
  const strict = Number(explosion.strict_pct);
  const sensitivity = Number(explosion.sensitivity_pct);
  if (!Number.isFinite(strict)) return null;
  const high = Number.isFinite(sensitivity) ? Math.max(strict, sensitivity) : strict;
  return { low: strict, high, mid: (strict + high) / 2 };
}

function fillSelect(select, keys, current, allowEmpty = false) {
  select.innerHTML = "";
  if (allowEmpty) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = tr("— не обирати —","— none —");
    empty.selected = current === "";
    select.appendChild(empty);
  }
  for (const key of keys) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = labelFor(key);
    opt.selected = key === current;
    select.appendChild(opt);
  }
}

function chartOptions(yTitle, extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
      tooltip: { mode: "index", intersect: false }
    },
    scales: {
      x: { ticks: { color: TEXT, maxRotation: 0, autoSkip: true }, grid: { color: GRID } },
      y: { beginAtZero: true, ticks: { color: TEXT }, grid: { color: GRID }, title: { display: true, text: yTitle, color: TEXT } }
    },
    ...extra
  };
}

function setChart(id, labels, datasets, yTitle, type = "line", extra = {}) {
  if (state.charts[id]) state.charts[id].destroy();
  state.charts[id] = new Chart($(id), {
    type,
    data: { labels, datasets },
    options: chartOptions(yTitle, extra)
  });
}

const CSV_CHART_CONFIG = {
  cityIntensityChart: { slug: "city-intensity", labelHeader: "period" },
  cityDurationChart: { slug: "city-duration", labelHeader: "period", defaultUnit: "minutes" },
  timeOfDayChart: { slug: "time-of-day", labelHeader: "time_of_day", profile: true },
  heavyDaysChart: { slug: "day-burden", labelHeader: "month", heavyDay: true },
  extremesChart: { slug: "alert-extremes", labelHeader: "month" },
  daypartChart: { slug: "daypart-share", labelHeader: "month", defaultUnit: "percent" },
  kyivThreatCausesChart: { slug: "kyiv-alert-causes", labelHeader: "date", threatMix: true },
  casualtyChart: { slug: "deaths", labelHeader: "period" },
  compareAlertsChart: { slug: "compare-alerts", labelHeader: "period" },
  compareHoursChart: { slug: "compare-alert-hours", labelHeader: "period", defaultUnit: "hours" },
  compareDurationChart: { slug: "compare-duration", labelHeader: "period", defaultUnit: "minutes" },
  compareTimeOfDayChart: { slug: "compare-time-of-day", labelHeader: "time_of_day", profile: true },
  compareExplosionsChart: { slug: "compare-events", labelHeader: "period", defaultUnit: "percent" },
  compareCasualtiesChart: { slug: "compare-deaths", labelHeader: "period" }
};

function csvEscape(value) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function numericCsvValue(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "object" && value !== null) {
    if (Number.isFinite(Number(value.y))) return Number(value.y);
    if (Number.isFinite(Number(value.x))) return Number(value.x);
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : "";
}

function safeFilePart(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function csvDownloadIcon() {
  return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12"></path><path d="m7 10 5 5 5-5"></path><path d="M5 20h14"></path></svg><span>CSV</span>';
}

function triggerCsvDownload(filename, headers, rows) {
  const lines = [
    headers.map(csvEscape).join(","),
    ...rows.map(row => row.map(csvEscape).join(","))
  ];
  const blob = new Blob(["\ufeff" + lines.join("\r\n") + "\r\n"], {
    type: "text/csv;charset=utf-8"
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function datasetExportUnit(chartId, dataset, config) {
  if (config?.profile) return "profile";
  if (config?.heavyDay) return "heavy_day";
  if (config?.threatMix) return "threat_mix";
  if (chartId === "cityIntensityChart" && dataset.yAxisID === "yHours") return "hours";
  return config?.defaultUnit || "number";
}

function exportContextParts(chartId, slug) {
  const parts = ["air-alerts"];
  if (chartId.startsWith("compare")) {
    const selected = [$("compareA")?.value, $("compareB")?.value, $("compareC")?.value]
      .filter(Boolean)
      .map(safeFilePart);
    parts.push("compare", ...selected, slug);
    if (chartId === "compareCasualtiesChart") {
      parts.push(safeFilePart($("compareCasualtyInterval")?.value || "monthly"));
      parts.push(safeFilePart($("compareCasualtyYear")?.value || "all"));
    } else if (chartId === "compareTimeOfDayChart") {
      parts.push(safeFilePart($("compareTimeOfDayRange")?.value || "30d"));
      parts.push(`${safeFilePart($("compareTimeOfDayBin")?.value || "15")}min`);
    } else {
      parts.push(safeFilePart($("comparePeriod")?.value || ""));
      if ($("compareDateFrom")?.value) parts.push(safeFilePart($("compareDateFrom").value));
      if ($("compareDateTo")?.value) parts.push(safeFilePart($("compareDateTo").value));
    }
  } else {
    parts.push(safeFilePart($("citySelect")?.value || "city"), slug);
    if (chartId === "casualtyChart") {
      parts.push(safeFilePart($("casualtyInterval")?.value || "monthly"));
      parts.push(safeFilePart($("casualtyYear")?.value || "all"));
    } else if (chartId === "heavyDaysChart" || chartId === "extremesChart") {
      parts.push(safeFilePart($("burdenYear")?.value || "all"));
      if (chartId === "heavyDaysChart" && $("heavyDaysExcludeZero")?.checked) parts.push("alert-days-only");
    } else if (chartId === "daypartChart") {
      parts.push(safeFilePart($("daypartYear")?.value || "all"));
    } else if (chartId === "timeOfDayChart") {
      parts.push(...selectedTimeOfDayRanges().map(safeFilePart));
      parts.push(`${safeFilePart($("timeOfDayBin")?.value || "15")}min`);
    } else {
      parts.push(safeFilePart($("cityPeriod")?.value || ""));
      if ($("cityDateFrom")?.value) parts.push(safeFilePart($("cityDateFrom").value));
      if ($("cityDateTo")?.value) parts.push(safeFilePart($("cityDateTo").value));
    }
  }
  return parts.filter(Boolean).join("_") + ".csv";
}

function visibleChartDatasets(chart) {
  return (chart?.data?.datasets || [])
    .map((dataset, index) => ({ dataset, index }))
    .filter(({ dataset, index }) => dataset.hidden !== true && chart.isDatasetVisible(index));
}

function exportChartCsv(chartId) {
  const chart = state.charts[chartId];
  const config = CSV_CHART_CONFIG[chartId];
  if (!chart || !config) return;

  const labels = chart.data?.labels || [];
  const visible = visibleChartDatasets(chart);
  if (!labels.length || !visible.length) return;

  const headers = [config.labelHeader || "period"];
  const columnBuilders = [];

  for (const { dataset } of visible) {
    const label = dataset.label || "series";
    const unit = datasetExportUnit(chartId, dataset, config);

    if (unit === "hours") {
      headers.push(`${label} [hours]`, `${label} [display]`);
      columnBuilders.push(index => {
        const raw = numericCsvValue(dataset.data?.[index]);
        return [raw, raw === "" ? "" : formatDurationHours(raw)];
      });
    } else if (unit === "minutes") {
      headers.push(`${label} [minutes]`, `${label} [display]`);
      columnBuilders.push(index => {
        const raw = numericCsvValue(dataset.data?.[index]);
        return [raw, raw === "" ? "" : formatDurationMinutes(raw)];
      });
    } else if (unit === "profile") {
      headers.push(`${label} [relative_peak_pct]`, `${label} [alert_time_pct]`);
      columnBuilders.push(index => [
        numericCsvValue(dataset.data?.[index]),
        numericCsvValue(dataset.alertShares?.[index])
      ]);
    } else if (unit === "threat_mix") {
      headers.push(`${label} [%]`, `${label} [minutes]`);
      columnBuilders.push(index => [
        numericCsvValue(dataset.data?.[index]),
        numericCsvValue(dataset.alertMinutes?.[index])
      ]);
    } else if (unit === "heavy_day") {
      headers.push(`${label} [%]`, `${label} [days]`);
      columnBuilders.push(index => [
        numericCsvValue(dataset.data?.[index]),
        numericCsvValue(dataset.dayCounts?.[index])
      ]);
    } else if (unit === "percent") {
      headers.push(`${label} [%]`);
      columnBuilders.push(index => [numericCsvValue(dataset.data?.[index])]);
    } else {
      headers.push(label);
      columnBuilders.push(index => [numericCsvValue(dataset.data?.[index])]);
    }
  }

  const exportRows = visible
    .map(({ dataset }) => dataset._exportRows)
    .filter(Array.isArray);
  const hasPartial = labels.some((_, index) =>
    exportRows.some(rows => Boolean(rows?.[index]?.is_partial_period))
  );

  if (hasPartial) headers.push("partial_period", "partial_through");

  const rows = labels.map((label, index) => {
    const row = [label];
    for (const build of columnBuilders) row.push(...build(index));
    if (hasPartial) {
      const source = exportRows.map(rows => rows?.[index]).find(Boolean);
      row.push(source?.is_partial_period ? "true" : "false", source?.partial_through || "");
    }
    return row;
  });

  triggerCsvDownload(exportContextParts(chartId, config.slug), headers, rows);
}

function exportAllCitiesCsv() {
  const rows = state.lastAllCitiesRows || [];
  if (!rows.length) return;
  const headers = [
    "city",
    "alerts",
    "alert_hours",
    "alert_hours_display",
    "avg_duration_minutes",
    "avg_duration_display",
    "coverage_start",
    "range_start",
    "range_end"
  ];
  const data = rows.map(row => [
    row.label,
    row.alerts ?? "",
    row.hours ?? "",
    row.hours == null ? "" : formatDurationHours(row.hours),
    row.duration ?? "",
    row.duration == null ? "" : formatDurationMinutes(row.duration),
    row.coverage || "",
    row.rangeStart || "",
    row.rangeEnd || ""
  ]);
  const range = safeFilePart($("allCitiesRange")?.value || "current");
  const from = safeFilePart($("tableDateFrom")?.value || "");
  const to = safeFilePart($("tableDateTo")?.value || "");
  triggerCsvDownload(
    ["air-alerts", "all-cities", range, from, to].filter(Boolean).join("_") + ".csv",
    headers,
    data
  );
}

function exportKpisCsv() {
  const key = $("citySelect")?.value;
  const city = state.data?.cities?.[key];
  const kpi = city?.kpis?.[0];
  if (!key || !kpi) return;
  const headers = [
    "city",
    "period_start",
    "period_end",
    "alerts_28d",
    "alert_hours_28d",
    "alert_hours_display",
    "avg_duration_minutes_28d",
    "avg_duration_display",
    "max_alerts_day",
    "max_alerts_day_date"
  ];
  const rows = [[
    labelFor(key),
    kpi.period_start || "",
    kpi.period_end || "",
    kpi.alerts_28d ?? "",
    kpi.alert_hours_28d ?? "",
    kpi.alert_hours_28d == null ? "" : formatDurationHours(kpi.alert_hours_28d),
    kpi.avg_alert_duration_min_28d ?? "",
    kpi.avg_alert_duration_min_28d == null ? "" : formatDurationMinutes(kpi.avg_alert_duration_min_28d),
    kpi.max_alerts_day ?? "",
    kpi.max_alerts_day_date || ""
  ]];
  triggerCsvDownload(`air-alerts_${safeFilePart(key)}_kpi-28d.csv`, headers, rows);
}

function makeCsvButton(handler, id = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "csv-export-button";
  if (id) button.id = id;
  button.innerHTML = csvDownloadIcon();
  button.setAttribute("aria-label", tr("Завантажити поточне представлення у CSV","Download current view as CSV"));
  button.title = tr(
    "CSV містить поточний зріз і лише видимі серії графіка",
    "CSV contains the current view and only visible chart series"
  );
  button.addEventListener("click", handler);
  return button;
}

function setupCsvExports() {
  for (const chartId of Object.keys(CSV_CHART_CONFIG)) {
    const canvas = $(chartId);
    const card = canvas?.closest(".chart-card");
    const wrap = canvas?.closest(".chart-wrap");
    if (!canvas || !card || !wrap || card.querySelector(`[data-csv-chart="${chartId}"]`)) continue;
    const row = document.createElement("div");
    row.className = "chart-export-row";
    row.dataset.csvChart = chartId;
    row.appendChild(makeCsvButton(() => exportChartCsv(chartId)));
    card.insertBefore(row, wrap);
  }

  const tablePanel = $("allCitiesTable")?.closest(".table-panel");
  const tableScroll = tablePanel?.querySelector(".table-scroll");
  if (tablePanel && tableScroll && !tablePanel.querySelector("[data-csv-table]")) {
    const row = document.createElement("div");
    row.className = "table-export-row";
    row.dataset.csvTable = "all-cities";
    row.appendChild(makeCsvButton(exportAllCitiesCsv));
    tablePanel.insertBefore(row, tableScroll);
  }

  const kpiGrid = document.querySelector(".kpi-grid");
  if (kpiGrid && !document.querySelector("[data-csv-kpis]")) {
    const row = document.createElement("div");
    row.className = "kpi-export-row";
    row.dataset.csvKpis = "28d";
    row.appendChild(makeCsvButton(exportKpisCsv));
    kpiGrid.parentNode.insertBefore(row, kpiGrid);
  }
}

function isPartialPeriod(row) {
  return Boolean(row?.is_partial_period);
}

function partialSegment(rows, color) {
  return {
    borderDash(ctx) {
      return isPartialPeriod(rows?.[ctx.p1DataIndex]) ? PARTIAL_PERIOD_DASH : undefined;
    },
    borderColor(ctx) {
      return isPartialPeriod(rows?.[ctx.p1DataIndex]) ? color + "99" : undefined;
    }
  };
}

const partialPeriodBarPlugin = {
  id: "partialPeriodBar",
  afterDatasetsDraw(chart, _args, options) {
    const rows = options?.rows || [];
    const datasetIndices = options?.datasetIndices || [];
    const partialIndices = rows
      .map((row, index) => isPartialPeriod(row) ? index : -1)
      .filter(index => index >= 0);
    if (!partialIndices.length || !datasetIndices.length) return;

    const ctx = chart.ctx;
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 2;

    for (const datasetIndex of datasetIndices) {
      const meta = chart.getDatasetMeta(datasetIndex);
      const dataset = chart.data.datasets[datasetIndex];
      for (const dataIndex of partialIndices) {
        const element = meta.data?.[dataIndex];
        if (!element) continue;
        const props = element.getProps(["x", "y", "base", "width"], true);
        const left = props.x - props.width / 2 + 1;
        const top = Math.min(props.y, props.base) + 1;
        const width = Math.max(0, props.width - 2);
        const height = Math.max(1, Math.abs(props.base - props.y) - 2);
        const border = Array.isArray(dataset.borderColor)
          ? dataset.borderColor[dataIndex]
          : dataset.borderColor;
        ctx.strokeStyle = border || TEXT;
        ctx.strokeRect(left, top, width, height);
      }
    }
    ctx.restore();
  }
};

function seriesDataset(label, values, color, dashed = false, rows = null) {
  return {
    label,
    data: values,
    borderColor: color,
    backgroundColor: color + "22",
    pointRadius: 0,
    pointHoverRadius: 0,
    borderWidth: 2,
    borderDash: dashed ? [7, 5] : [],
    segment: rows ? partialSegment(rows, color) : undefined,
    _exportRows: rows || null,
    tension: 0,
    spanGaps: true
  };
}

function rowTime(row, period) {
  if (period === "monthly") return row.month || String(row.time || "").slice(0, 7);
  if (period === "daily" || period === "daily28") return row.date || String(row.time || "").slice(0, 10);
  if (period === "rolling30" || period === "rolling90" || period === "rolling180") {
    return row.window_end || String(row.time || "").slice(0, 10);
  }
  if (period === "calendarWeekly") return row.week_end || String(row.time || "").slice(0, 10);
  if (rolling7dEnabled()) return row.week_end || String(row.time || "").slice(0, 10);
  return row.week_start || String(row.time || "").slice(0, 10);
}


function addIsoDays(value, days) {
  const d = new Date(`${String(value).slice(0,10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return "";
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0,10);
}

function mondayIndex(value) {
  const d = new Date(`${String(value).slice(0,10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  return (d.getUTCDay() + 6) % 7;
}

function derivedDaily28Rows(city) {
  return (city?.daily28 || []).map(row => ({
    ...row,
    time: row.time || `${row.date}T00:00:00`,
    alerts_per_day: Number(row.alerts_started) || 0,
    avg_daily_alert_hours: Number(row.total_alert_duration_hours) || 0,
    avg_alert_duration_min: (() => {
      const exact = Number(row.avg_active_alert_duration_minutes);
      if (Number.isFinite(exact)) return exact;
      const active = Number(row.active_alerts);
      const total = Number(row.total_alert_duration_minutes);
      if (active > 0 && Number.isFinite(total)) return total / active;
      const legacy = Number(row.avg_alert_duration_minutes);
      return Number.isFinite(legacy) ? legacy : null;
    })()
  }));
}

function derivedCalendarWeeks(city) {
  const complete = (city?.weekly || [])
    .filter(row => mondayIndex(row.week_start) === 0 && mondayIndex(row.week_end) === 6)
    .map(row => ({ ...row, interval_mode: "calendar_week" }));

  const daily = derivedDaily28Rows(city);
  if (!daily.length) return complete;

  const latest = daily[daily.length - 1]?.date;
  const offset = mondayIndex(latest);
  if (offset == null || offset === 6) return complete;

  const monday = addIsoDays(latest, -offset);
  const partialDays = daily.filter(row => row.date >= monday && row.date <= latest);
  if (!partialDays.length || partialDays[0].date !== monday) return complete;

  const alertsStarted = partialDays.reduce((sum, row) => sum + (Number(row.alerts_started) || 0), 0);
  const alertHours = partialDays.reduce((sum, row) => sum + (Number(row.total_alert_duration_hours) || 0), 0);
  let durationWeighted = 0;
  let durationWeight = 0;
  for (const row of partialDays) {
    const n = Number(row.alerts_started) || 0;
    const avg = Number(row.avg_alert_duration_minutes);
    if (n > 0 && Number.isFinite(avg)) {
      durationWeighted += n * avg;
      durationWeight += n;
    }
  }

  complete.push({
    time: `${latest}T00:00:00`,
    week_start: monday,
    week_end: latest,
    alerts_per_day: alertsStarted / partialDays.length,
    avg_daily_alert_hours: alertHours / partialDays.length,
    avg_alert_duration_min: durationWeight ? durationWeighted / durationWeight : null,
    alerts_started: alertsStarted,
    is_partial_period: true,
    partial_through: latest,
    interval_mode: "calendar_week"
  });
  return complete;
}

function derivedRolling180Rows(city) {
  const rows90 = city?.rolling90 || [];
  const byEnd = new Map(rows90.map(row => [row.window_end || String(row.time || "").slice(0,10), row]));
  const out = [];

  for (const second of rows90) {
    const secondEnd = second.window_end || String(second.time || "").slice(0,10);
    const firstEnd = addIsoDays(secondEnd, -90);
    const first = byEnd.get(firstEnd);
    if (!first) continue;

    const n1 = Number(first.alerts_started) || 0;
    const n2 = Number(second.alerts_started) || 0;
    const totalAlerts = n1 + n2;
    const h1 = (Number(first.avg_daily_alert_hours) || 0) * 90;
    const h2 = (Number(second.avg_daily_alert_hours) || 0) * 90;
    const d1 = Number(first.avg_alert_duration_min);
    const d2 = Number(second.avg_alert_duration_min);
    let weighted = 0;
    let weight = 0;
    if (n1 > 0 && Number.isFinite(d1)) { weighted += n1 * d1; weight += n1; }
    if (n2 > 0 && Number.isFinite(d2)) { weighted += n2 * d2; weight += n2; }

    out.push({
      time: second.time,
      window_start: first.window_start || addIsoDays(secondEnd, -179),
      window_end: secondEnd,
      window_days: 180,
      alerts_per_day: totalAlerts / 180,
      avg_daily_alert_hours: (h1 + h2) / 180,
      avg_alert_duration_min: weight ? weighted / weight : null,
      alerts_started: totalAlerts
    });
  }
  return out;
}

function periodRows(city, period) {
  if (period === "daily28") return derivedDaily28Rows(city);
  if (period === "calendarWeekly") return derivedCalendarWeeks(city);
  if (period === "rolling180") return derivedRolling180Rows(city);
  return city?.[period] || [];
}

function resetCityDisplayRange() {
  const key = $("citySelect")?.value;
  const period = $("cityPeriod")?.value;
  const city = state.data.cities?.[key];
  const rows = periodRows(city, period);
  const range = syncDateRange(
    "cityDateFrom",
    "cityDateTo",
    rows.map(row => rowTime(row, period))
  );
  if (range.min && range.max) {
    setDateRangeValues("cityDateFrom", "cityDateTo", range.min, range.max);
  }
}

function commonPeriodTimes(keys, period) {
  const maps = keys.map(key => {
    const m = new Map();
    for (const row of periodRows(state.data.cities[key], period)) {
      m.set(rowTime(row, period), row);
    }
    return m;
  });
  if (!maps.length) return [];
  let shared = new Set(maps[0].keys());
  for (const map of maps.slice(1)) {
    shared = new Set([...shared].filter(value => map.has(value)));
  }
  return [...shared].sort();
}

function resetComparisonDisplayRange() {
  const keys = [$("compareA")?.value, $("compareB")?.value, $("compareC")?.value].filter(Boolean);
  const period = $("comparePeriod")?.value;
  const times = commonPeriodTimes(keys, period);
  const range = syncDateRange("compareDateFrom", "compareDateTo", times);
  if (range.min && range.max) {
    setDateRangeValues("compareDateFrom", "compareDateTo", range.min, range.max);
  }
}

function getParams() {
  return new URLSearchParams(location.search);
}
function validParam(name, values, fallback) {
  const value = getParams().get(name);
  return values.includes(value) ? value : fallback;
}
function validOptionalParam(name, values, fallback) {
  const value = getParams().get(name);
  if (value === "none") return "";
  return values.includes(value) ? value : fallback;
}

function normalizeTypedDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";

  let year, month, day;
  let match = /^(\d{4})[-./](\d{1,2})[-./](\d{1,2})$/.exec(raw);
  if (match) {
    year = Number(match[1]);
    month = Number(match[2]);
    day = Number(match[3]);
  } else {
    match = /^(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{4})$/.exec(raw);
    if (!match) return null;
    day = Number(match[1]);
    month = Number(match[2]);
    year = Number(match[3]);
  }

  const d = new Date(Date.UTC(year, month - 1, day));
  if (
    d.getUTCFullYear() !== year ||
    d.getUTCMonth() !== month - 1 ||
    d.getUTCDate() !== day
  ) return null;

  return `${String(year).padStart(4,"0")}-${String(month).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
}

function normalizeDateInputElement(el) {
  if (!el) return true;
  const normalized = normalizeTypedDate(el.value);
  if (normalized === null) {
    el.classList.add("invalid");
    el.title = tr(
      "Введіть дату як YYYY-MM-DD або DD.MM.YYYY",
      "Enter the date as YYYY-MM-DD or DD.MM.YYYY"
    );
    return false;
  }
  el.classList.remove("invalid");
  el.removeAttribute("title");
  el.value = normalized;
  return true;
}

function validDateParam(name) {
  const normalized = normalizeTypedDate(getParams().get(name) || "");
  return normalized || "";
}

function setDateInputFromParam(id, name) {
  const el = $(id);
  if (el) el.value = validDateParam(name);
}

function monthEndDate(month) {
  const match = /^(\d{4})-(\d{2})$/.exec(String(month || "").slice(0, 7));
  if (!match) return "";
  const year = Number(match[1]);
  const monthNumber = Number(match[2]);
  const day = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
  return `${match[1]}-${match[2]}-${String(day).padStart(2, "0")}`;
}

function dateKeyBounds(value) {
  const raw = String(value || "");
  if (/^\d{4}-\d{2}$/.test(raw)) {
    return { start: `${raw}-01`, end: monthEndDate(raw) };
  }
  const day = raw.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(day)) {
    return { start: day, end: day };
  }
  return null;
}

function syncDateRange(fromId, toId, values) {
  const fromEl = $(fromId);
  const toEl = $(toId);
  if (!fromEl || !toEl) return { from: "", to: "", min: "", max: "" };

  normalizeDateInputElement(fromEl);
  normalizeDateInputElement(toEl);

  const bounds = (values || []).map(dateKeyBounds).filter(Boolean);
  if (!bounds.length) {
    for (const el of [fromEl, toEl]) {
      el.value = "";
      el.removeAttribute("min");
      el.removeAttribute("max");
    }
    return { from: "", to: "", min: "", max: "" };
  }

  const min = bounds.reduce((a, b) => a < b.start ? a : b.start, bounds[0].start);
  const max = bounds.reduce((a, b) => a > b.end ? a : b.end, bounds[0].end);
  for (const el of [fromEl, toEl]) {
    el.min = min;
    el.max = max;
  }

  if (!fromEl.value || fromEl.value < min || fromEl.value > max) fromEl.value = min;
  if (!toEl.value || toEl.value < min || toEl.value > max) toEl.value = max;
  if (fromEl.value > toEl.value) toEl.value = fromEl.value;

  return { from: fromEl.value, to: toEl.value, min, max };
}

function syncFixedDateRange(fromId, toId, min, max) {
  if (!min || !max) return { from: "", to: "", min: "", max: "" };
  return syncDateRange(fromId, toId, [min, max]);
}

function normalizeDatePair(fromId, toId, changedId) {
  const fromEl = $(fromId);
  const toEl = $(toId);
  if (!fromEl || !toEl || !fromEl.value || !toEl.value || fromEl.value <= toEl.value) return;
  if (changedId === fromId) toEl.value = fromEl.value;
  else fromEl.value = toEl.value;
}

function dateKeyInRange(value, from, to) {
  const bounds = dateKeyBounds(value);
  if (!bounds) return true;
  return (!from || bounds.end >= from) && (!to || bounds.start <= to);
}

function fullPeriodInsideRange(value, from, to) {
  const bounds = dateKeyBounds(value);
  if (!bounds) return false;
  return (!from || bounds.start >= from) && (!to || bounds.end <= to);
}

function filterRowsByDateRange(rows, period, fromId, toId) {
  const allRows = rows || [];
  const range = syncDateRange(fromId, toId, allRows.map(row => rowTime(row, period)));
  return allRows.filter(row => dateKeyInRange(rowTime(row, period), range.from, range.to));
}

function setDateRangeValues(fromId, toId, from, to) {
  const fromEl = $(fromId);
  const toEl = $(toId);
  if (!fromEl || !toEl) return;
  if (from) fromEl.value = from < (fromEl.min || from) ? fromEl.min : (from > (fromEl.max || from) ? fromEl.max : from);
  if (to) toEl.value = to < (toEl.min || to) ? toEl.min : (to > (toEl.max || to) ? toEl.max : to);
  if (fromEl.value && toEl.value && fromEl.value > toEl.value) toEl.value = fromEl.value;
}

function applyRolling7dQuickRange(key, presetValue = null) {
  const rows = state.data.cities[key]?.weekly || [];
  if (!rows.length) return;
  const range = syncDateRange("rolling7dDateFrom", "rolling7dDateTo", rows.map(row => rowTime(row, "weekly")));
  const select = $("rolling7dYear");
  const preset = presetValue || select?.value || "all";
  if (preset === "all") {
    setDateRangeValues("rolling7dDateFrom", "rolling7dDateTo", range.min, range.max);
  } else if (/^\d{4}$/.test(preset)) {
    setDateRangeValues("rolling7dDateFrom", "rolling7dDateTo", `${preset}-01-01`, `${preset}-12-31`);
  }
}

function monthDaysFromKey(month) {
  const end = monthEndDate(month);
  return end ? Number(end.slice(-2)) : 0;
}

function commonMonthlyDateBounds() {
  const firsts = [];
  const lasts = [];
  for (const key of cityKeys()) {
    const rows = (state.data.cities[key]?.monthly || []).filter(row => !isPartialPeriod(row));
    if (!rows.length) return null;
    const first = dateKeyBounds(rowTime(rows[0], "monthly"));
    const last = dateKeyBounds(rowTime(rows[rows.length - 1], "monthly"));
    if (!first || !last) return null;
    firsts.push(first.start);
    lasts.push(last.end);
  }
  return { min: firsts.sort().slice(-1)[0], max: lasts.sort()[0] };
}

function aggregateMonthlyRange(key, from, to) {
  const rows = (state.data.cities[key]?.monthly || [])
    .filter(row => !isPartialPeriod(row))
    .filter(row => fullPeriodInsideRange(rowTime(row, "monthly"), from, to));
  if (!rows.length) return null;

  let alerts = 0;
  let hours = 0;
  let durationWeighted = 0;
  let durationWeight = 0;

  for (const row of rows) {
    const month = rowTime(row, "monthly");
    const days = monthDaysFromKey(month);
    const explicitAlerts = Number(row.alerts_started);
    const alertsStarted = Number.isFinite(explicitAlerts)
      ? explicitAlerts
      : (Number(row.alerts_per_day) || 0) * days;
    const alertHours = (Number(row.avg_daily_alert_hours) || 0) * days;
    const avgDuration = Number(row.avg_alert_duration_min);

    alerts += alertsStarted;
    hours += alertHours;
    if (Number.isFinite(avgDuration) && alertsStarted > 0) {
      durationWeighted += avgDuration * alertsStarted;
      durationWeight += alertsStarted;
    }
  }

  return {
    alerts: Math.round(alerts),
    hours,
    duration: durationWeight > 0 ? durationWeighted / durationWeight : null,
    rangeStart: rowTime(rows[0], "monthly") + "-01",
    rangeEnd: monthEndDate(rowTime(rows[rows.length - 1], "monthly"))
  };
}


function heatmapRangeLabel(range) {
  const labels = {
    "7d": tr("7 днів","7 days"),
    "30d": tr("30 днів","30 days"),
    "90d": tr("90 днів","90 days"),
    "180d": tr("180 днів","180 days"),
    "year": tr("Рік","Year"),
    "all": tr("Від початку даних","From start of data")
  };
  return labels[range] || range;
}

function timeOfDayBinLabel(minutes) {
  const value = Number(minutes);
  if (value === 60) return tr("1 година","1 hour");
  return tr(`${value} хв`,`${value} min`);
}

function selectedTimeOfDayBin(controlId) {
  const value = Number($(controlId)?.value || 15);
  return TIME_OF_DAY_BIN_MINUTES.includes(value) ? value : 15;
}

function timeOfDayClockLabel(totalMinutes) {
  const value = Math.max(0, Math.min(1440, Math.round(Number(totalMinutes) || 0)));
  if (value === 1440) return "24:00";
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  return `${String(hours).padStart(2,"0")}:${String(minutes).padStart(2,"0")}`;
}

function aggregateTimeOfDayPeriod(period, binMinutes) {
  const slots = Array.isArray(period?.slots) ? period.slots : [];
  const targetMinutes = TIME_OF_DAY_BIN_MINUTES.includes(Number(binMinutes)) ? Number(binMinutes) : 15;
  if (!slots.length) return period;

  const baseMinutes = 1440 / slots.length;
  const factor = targetMinutes / baseMinutes;
  if (!Number.isInteger(factor) || factor < 1) return period;

  const grouped = [];
  for (let i = 0; i < slots.length; i += factor) {
    const group = slots.slice(i, i + factor);
    const alertMinutes = group.reduce((sum, slot) => sum + (Number(slot.alert_minutes) || 0), 0);
    const possibleMinutes = group.reduce((sum, slot) => sum + (Number(slot.possible_minutes) || 0), 0);
    const alertShare = possibleMinutes > 0 ? alertMinutes / possibleMinutes * 100 : 0;
    const startMinutes = i * baseMinutes;
    const endMinutes = Math.min(1440, startMinutes + targetMinutes);
    const start = timeOfDayClockLabel(startMinutes);
    const label = `${start}–${timeOfDayClockLabel(endMinutes)}`;
    grouped.push({
      index: grouped.length,
      start,
      label,
      alert_share_pct: Number(alertShare.toFixed(3)),
      alert_minutes: Number(alertMinutes.toFixed(2)),
      possible_minutes: Number(possibleMinutes.toFixed(2)),
      relative_intensity: 0
    });
  }

  const peak = grouped.reduce((max, slot) => Math.max(max, Number(slot.alert_share_pct) || 0), 0);
  grouped.forEach(slot => {
    slot.relative_intensity = Number((peak > 0 ? slot.alert_share_pct / peak * 100 : 0).toFixed(2));
  });
  const peakSlot = peak > 0 ? grouped.find(slot => Number(slot.alert_share_pct) === peak) : null;

  return {
    ...period,
    peak_slot: peakSlot?.label || null,
    peak_alert_share_pct: Number(peak.toFixed(3)),
    slots: grouped
  };
}

function selectedTimeOfDayRanges() {
  return [...document.querySelectorAll(".time-of-day-range-option:checked")]
    .map(el => el.value)
    .filter(value => HEATMAP_RANGES.includes(value));
}

function setSelectedTimeOfDayRanges(ranges) {
  const selected = new Set((ranges || []).filter(value => HEATMAP_RANGES.includes(value)));
  if (!selected.size) selected.add("30d");
  document.querySelectorAll(".time-of-day-range-option").forEach(el => {
    el.checked = selected.has(el.value);
  });
  updateTimeOfDayRangeSummary();
}

function updateTimeOfDayRangeSummary() {
  const summary = $("timeOfDayRangeSummary");
  if (!summary) return;
  const ranges = selectedTimeOfDayRanges();
  summary.textContent = ranges.map(heatmapRangeLabel).join(", ");
}

function validMultiParam(name, allowed, fallback) {
  const raw = getParams().get(name);
  if (!raw) return fallback;
  const values = raw.split(",").map(x => x.trim()).filter(x => allowed.includes(x));
  return values.length ? [...new Set(values)] : fallback;
}

function syncCasualtyYearOptions(allRows) {
  const select = $("casualtyYear");
  if (!select) return "all";
  const years = [...new Set(
    allRows.map(row => String(row.month || row.time || "").slice(0,4)).filter(y => /^\d{4}$/.test(y))
  )].sort((a,b) => Number(b) - Number(a));
  const requested = select.dataset.requested || select.value || "all";
  select.innerHTML = [
    `<option value="all">${tr("Усі роки","All years")}</option>`,
    ...years.map(year => `<option value="${year}">${year}</option>`)
  ].join("");
  const selected = ["all",...years].includes(requested) ? requested : "all";
  select.value = selected;
  delete select.dataset.requested;
  return selected;
}

function casualtyRowsForYear(allRows, selectedYear) {
  return selectedYear === "all"
    ? [...allRows]
    : allRows.filter(row => String(row.month || row.time || "").slice(0,4) === selectedYear);
}

function aggregateCasualtiesByYear(rows) {
  const totals = new Map();
  for (const row of rows) {
    const year = String(row.month || row.time || "").slice(0,4);
    if (!/^\d{4}$/.test(year)) continue;
    totals.set(year, (totals.get(year) || 0) + (Number(row.deaths) || 0));
  }
  return [...totals.entries()]
    .sort((a,b) => a[0].localeCompare(b[0]))
    .map(([year, deaths]) => ({ year, deaths }));
}

function syncCompareCasualtyYearOptions(keys) {
  const select = $("compareCasualtyYear");
  if (!select) return "all";
  const yearSets = keys.map(key => new Set(
    (state.data.casualties_by_city?.[key]?.monthly || [])
      .map(row => String(row.month || row.time || "").slice(0,4))
      .filter(year => /^\d{4}$/.test(year))
  ));
  let years = yearSets.length ? new Set(yearSets[0]) : new Set();
  for (const set of yearSets.slice(1)) {
    years = new Set([...years].filter(year => set.has(year)));
  }
  const available = [...years].sort((a,b) => Number(b) - Number(a));
  const requested = select.dataset.requested || select.value || "all";
  select.innerHTML = [
    `<option value="all">${tr("Усі роки","All years")}</option>`,
    ...available.map(year => `<option value="${year}">${year}</option>`)
  ].join("");
  select.value = ["all", ...available].includes(requested) ? requested : "all";
  delete select.dataset.requested;
  return select.value;
}

function updateUrl() {
  const params = new URLSearchParams();
  params.set("lang", currentLanguage);
  params.set("city", $("citySelect").value);
  params.set("period", $("cityPeriod").value);
  params.set("a", $("compareA").value);
  params.set("b", $("compareB").value);
  params.set("c", $("compareC").value || "none");
  params.set("compare", $("comparePeriod").value);
  if ($("rolling7dYear")?.value) params.set("year", $("rolling7dYear").value);
  const todRanges = selectedTimeOfDayRanges();
  if (todRanges.length) params.set("tod", todRanges.join(","));
  if ($("timeOfDayBin")?.value) params.set("todbin", $("timeOfDayBin").value);
  if ($("compareTimeOfDayRange")?.value) params.set("ctod", $("compareTimeOfDayRange").value);
  if ($("compareTimeOfDayBin")?.value) params.set("ctodbin", $("compareTimeOfDayBin").value);
  if ($("burdenYear")?.value) params.set("burdenyear", $("burdenYear").value);
  if ($("heavyDaysExcludeZero")?.checked) params.set("heavyexclude", "1");
  if ($("daypartYear")?.value) params.set("daypartyear", $("daypartYear").value);
  if ($("casualtyYear")?.value) params.set("casyear", $("casualtyYear").value);
  if ($("casualtyInterval")?.value) params.set("casint", $("casualtyInterval").value);
  if ($("compareCasualtyYear")?.value) params.set("ccasyear", $("compareCasualtyYear").value);
  if ($("compareCasualtyInterval")?.value) params.set("ccasint", $("compareCasualtyInterval").value);
  if ($("allCitiesRange")?.value) params.set("table", $("allCitiesRange").value);
  for (const [id, param] of [
    ["cityDateFrom","cityfrom"],["cityDateTo","cityto"],
    ["rolling7dDateFrom","r7from"],["rolling7dDateTo","r7to"],
    ["compareDateFrom","cmpfrom"],["compareDateTo","cmpto"],
    ["tableDateFrom","tablefrom"],["tableDateTo","tableto"]
  ]) {
    if ($(id)?.value) params.set(param, $(id).value);
  }
  history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
}



function explorationCity(key) {
  return state.explorations?.cities?.[key] || null;
}

function explorationYearOptions(selectId, key) {
  const select = $(selectId);
  const city = explorationCity(key);
  if (!select || !city) return null;
  const years = [...(city.years || [])].sort((a, b) => Number(b) - Number(a));
  const requested = select.dataset.requested || "";
  const current = select.value;
  const desired = years.includes(current)
    ? current
    : (years.includes(requested) ? requested : (years[0] || ""));
  select.innerHTML = years.map(year => `<option value="${year}">${year}</option>`).join("");
  if (desired) select.value = desired;
  delete select.dataset.requested;
  return select.value || null;
}

function explorationMonthlyRows(key, year) {
  const city = explorationCity(key);
  return (city?.monthly || []).filter(row => String(row.month || "").startsWith(String(year || "")));
}

function renderAlertBurden(key) {
  const section = $("alertBurdenSection");
  const city = explorationCity(key);
  if (!section || !city?.monthly?.length) {
    section?.classList.add("hidden");
    for (const id of ["heavyDaysChart", "extremesChart"]) {
      if (state.charts[id]) { state.charts[id].destroy(); delete state.charts[id]; }
    }
    return;
  }

  section.classList.remove("hidden");
  const year = explorationYearOptions("burdenYear", key);
  const rows = explorationMonthlyRows(key, year);
  if (!rows.length) return;

  const labels = rows.map(row => row.month);
  const excludeZero = Boolean($("heavyDaysExcludeZero")?.checked);
  const allKeys = [
    ["zero", tr("Без тривоги","No alert")],
    ["lt1", tr("<1 год","<1 hr")],
    ["h1_3", tr("1–3 год","1–3 hr")],
    ["h3_6", tr("3–6 год","3–6 hr")],
    ["h6_12", tr("6–12 год","6–12 hr")],
    ["h12plus", tr("12+ год","12+ hr")]
  ];
  const keys = excludeZero ? allKeys.filter(([bucket]) => bucket !== "zero") : allKeys;
  const burdenColors = ["#7f8c99", "#62a0ea", "#8ff0a4", "#f8e45c", "#ff9f43", "#ef4444"];

  if (state.charts.heavyDaysChart) state.charts.heavyDaysChart.destroy();
  state.charts.heavyDaysChart = new Chart($("heavyDaysChart"), {
    type: "bar",
    data: {
      labels,
      datasets: keys.map(([bucket, label], index) => ({
        label,
        data: rows.map(row => {
          const covered = Number(row.days_covered) || 0;
          const zero = Number(row.burden_day_counts?.zero || 0);
          const denominator = excludeZero ? Math.max(0, covered - zero) : covered;
          const count = Number(row.burden_day_counts?.[bucket] || 0);
          return denominator > 0 ? count / denominator * 100 : 0;
        }),
        dayCounts: rows.map(row => Number(row.burden_day_counts?.[bucket] || 0)),
        denominatorDays: rows.map(row => {
          const covered = Number(row.days_covered) || 0;
          const zero = Number(row.burden_day_counts?.zero || 0);
          return excludeZero ? Math.max(0, covered - zero) : covered;
        }),
        backgroundColor: burdenColors[allKeys.findIndex(([value]) => value === bucket)] + "bb",
        borderWidth: 0,
        stack: "days"
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label(context) {
              const index = context.dataIndex;
              const count = context.dataset.dayCounts?.[index] || 0;
              const total = context.dataset.denominatorDays?.[index] || 0;
              return tr(
                `${context.dataset.label}: ${fmt(context.parsed.y,1)}% · ${count} із ${total} днів`,
                `${context.dataset.label}: ${fmt(context.parsed.y,1)}% · ${count} of ${total} days`
              );
            },
            footer(items) {
              if (!excludeZero || !items.length) return "";
              const row = rows[items[0].dataIndex];
              const zero = Number(row.burden_day_counts?.zero || 0);
              return tr(`Не враховано днів без тривоги: ${zero}`, `Days without alerts excluded: ${zero}`);
            }
          }
        }
      },
      scales: {
        x: { stacked: true, ticks: { color: TEXT, maxRotation: 0 }, grid: { color: GRID } },
        y: {
          stacked: true, min: 0, max: 100,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: excludeZero ? tr("Частка днів із тривогою","Share of alert days") : tr("Частка днів у місяці","Share of days in month"), color: TEXT }
        }
      }
    }
  });

  if (state.charts.extremesChart) state.charts.extremesChart.destroy();
  state.charts.extremesChart = new Chart($("extremesChart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: tr("Найдовша тривога","Longest alert"),
          data: rows.map(row => row.longest_alert_min == null ? null : Number(row.longest_alert_min) / 60),
          borderColor: TIME_PROFILE_COLORS[1],
          backgroundColor: TIME_PROFILE_COLORS[1] + "22",
          yAxisID: "yAlert",
          pointRadius: 2,
          tension: .15
        },
        {
          label: tr("Найдовша тиша","Longest quiet spell"),
          data: rows.map(row => Number(row.longest_quiet_gap_min || 0) / 1440),
          borderColor: TIME_PROFILE_COLORS[2],
          backgroundColor: TIME_PROFILE_COLORS[2] + "22",
          yAxisID: "yQuiet",
          pointRadius: 2,
          tension: .15
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label(context) {
              return context.dataset.yAxisID === "yAlert"
                ? `${context.dataset.label}: ${fmt(context.parsed.y,1)} ${tr("год","hr")}`
                : `${context.dataset.label}: ${fmt(context.parsed.y,1)} ${tr("діб","days")}`;
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: TEXT, maxRotation: 0 }, grid: { color: GRID } },
        yAlert: {
          position: "left", beginAtZero: true,
          ticks: { color: TEXT, callback: value => `${value} ${tr("год","hr")}` },
          grid: { color: GRID },
          title: { display: true, text: tr("Найдовша тривога, год","Longest alert, hours"), color: TEXT }
        },
        yQuiet: {
          position: "right", beginAtZero: true,
          ticks: { color: TEXT, callback: value => `${value} ${tr("д","d")}` },
          grid: { drawOnChartArea: false },
          title: { display: true, text: tr("Найдовша тиша, діб","Longest quiet spell, days"), color: TEXT }
        }
      }
    }
  });
}

function renderDaypart(key) {
  const card = $("daypartChart")?.closest(".daypart-card");
  const city = explorationCity(key);
  if (!card || !city?.monthly?.length) {
    card?.classList.add("hidden");
    if (state.charts.daypartChart) { state.charts.daypartChart.destroy(); delete state.charts.daypartChart; }
    return;
  }
  card.classList.remove("hidden");
  const year = explorationYearOptions("daypartYear", key);
  const rows = explorationMonthlyRows(key, year);
  const labels = rows.map(row => row.month);
  const bands = [
    ["00_06","00–06"],
    ["06_12","06–12"],
    ["12_18","12–18"],
    ["18_24","18–24"]
  ];

  if (state.charts.daypartChart) state.charts.daypartChart.destroy();
  state.charts.daypartChart = new Chart($("daypartChart"), {
    type: "bar",
    data: {
      labels,
      datasets: bands.map(([bucket, label], index) => ({
        label,
        data: rows.map(row => Number(row.time_band_shares?.[bucket] || 0)),
        backgroundColor: TIME_PROFILE_COLORS[index + 1] + "bb",
        borderWidth: 0,
        stack: "time"
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label(context) { return `${context.dataset.label}: ${fmt(context.parsed.y,1)}%`; }
          }
        }
      },
      scales: {
        x: { stacked: true, ticks: { color: TEXT, maxRotation: 0 }, grid: { color: GRID } },
        y: {
          stacked: true, min: 0, max: 100,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: tr("Частка часу під тривогою","Share of alert time"), color: TEXT }
        }
      }
    }
  });
}

function renderTimeOfDay(key) {
  const section = $("timeOfDaySection");
  const root = state.data.time_of_day_heatmap_test || state.data.time_of_day_profile;
  const city = root?.cities?.[key];
  if (!section || !city?.periods) {
    section?.classList.add("hidden");
    return;
  }

  const requested = selectedTimeOfDayRanges();
  const binMinutes = selectedTimeOfDayBin("timeOfDayBin");
  const usable = requested
    .map(range => ({ range, period: city.periods?.[range] }))
    .filter(item => item.period?.slots?.length)
    .map(item => ({ ...item, period: aggregateTimeOfDayPeriod(item.period, binMinutes) }));

  section.classList.remove("hidden");
  updateTimeOfDayRangeSummary();

  if (state.charts.timeOfDayChart) {
    state.charts.timeOfDayChart.destroy();
    delete state.charts.timeOfDayChart;
  }

  if (!usable.length) {
    $("timeOfDayMeta").textContent = tr(
      "Немає даних для обраних діапазонів.",
      "No data are available for the selected ranges."
    );
    return;
  }

  const labels = usable[0].period.slots.map(slot => slot.start);
  const intervalLabels = usable[0].period.slots.map(slot => slot.label);
  const datasets = usable.map((item, idx) => ({
    label: heatmapRangeLabel(item.range),
    data: item.period.slots.map(slot => Number(slot.relative_intensity) || 0),
    alertShares: item.period.slots.map(slot => Number(slot.alert_share_pct) || 0),
    borderColor: TIME_PROFILE_COLORS[idx % TIME_PROFILE_COLORS.length],
    backgroundColor: TIME_PROFILE_COLORS[idx % TIME_PROFILE_COLORS.length] + "18",
    borderWidth: 2,
    pointRadius: 0,
    pointHoverRadius: 0,
    pointHitRadius: 10,
    tension: 0,
    fill: false
  }));

  $("timeOfDayMeta").textContent = usable.map(item => {
    const p = item.period;
    const peak = p.peak_slot
      ? tr(
          `пік ${p.peak_slot}, ${fmt(p.peak_alert_share_pct,1)}% фактичного часу`,
          `peak ${p.peak_slot}, ${fmt(p.peak_alert_share_pct,1)}% of actual time`
        )
      : tr("без часу під тривогою","no time under alert");
    return `${heatmapRangeLabel(item.range)}: ${p.range_start} — ${p.range_end} · ${peak}`;
  }).join(" · ");

  state.charts.timeOfDayChart = new Chart($("timeOfDayChart"), {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            title(items) {
              const i = items?.[0]?.dataIndex ?? 0;
              return intervalLabels[i] || labels[i] || "";
            },
            label(context) {
              const share = context.dataset.alertShares?.[context.dataIndex];
              return tr(
                `${context.dataset.label}: ${fmt(context.parsed.y,0)}% від власного піку · фактично ${fmt(share,1)}% часу`,
                `${context.dataset.label}: ${fmt(context.parsed.y,0)}% of its own peak · actually ${fmt(share,1)}% of the time`
              );
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: TEXT, autoSkip: true, maxTicksLimit: 9, maxRotation: 0 },
          grid: { color: GRID },
          title: { display: true, text: tr("Час доби","Time of day"), color: TEXT }
        },
        y: {
          min: 0,
          max: 100,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: tr("Відносна інтенсивність","Relative intensity"), color: TEXT }
        }
      }
    }
  });
}

function renderTimeOfDayComparison(keys) {
  const root = state.data.time_of_day_heatmap_test || state.data.time_of_day_profile;
  const select = $("compareTimeOfDayRange");
  const note = $("compareTimeOfDayNote");
  const canvas = $("compareTimeOfDayChart");
  if (!root?.cities || !select || !canvas) return;

  const range = HEATMAP_RANGES.includes(select.value) ? select.value : "30d";
  const binMinutes = selectedTimeOfDayBin("compareTimeOfDayBin");
  const usable = keys
    .map(key => ({ key, period: root.cities?.[key]?.periods?.[range] }))
    .filter(item => item.period?.slots?.length)
    .map(item => ({ ...item, period: aggregateTimeOfDayPeriod(item.period, binMinutes) }));

  if (state.charts.compareTimeOfDayChart) {
    state.charts.compareTimeOfDayChart.destroy();
    delete state.charts.compareTimeOfDayChart;
  }

  if (!usable.length) {
    if(note)note.textContent=tr("Немає добового профілю для обраних міст.","No time-of-day profile is available for the selected cities.");
    return;
  }

  const labels = usable[0].period.slots.map(slot => slot.start);
  const intervalLabels = usable[0].period.slots.map(slot => slot.label);
  const datasets = usable.map((item, idx) => ({
    label: labelFor(item.key),
    data: item.period.slots.map(slot => Number(slot.relative_intensity) || 0),
    alertShares: item.period.slots.map(slot => Number(slot.alert_share_pct) || 0),
    borderColor: COLORS[idx % COLORS.length],
    backgroundColor: COLORS[idx % COLORS.length] + "18",
    borderWidth: 2,
    pointRadius: 0,
    pointHoverRadius: 0,
    pointHitRadius: 10,
    tension: 0,
    fill: false
  }));

  if (note) {
    const ranges = usable
      .map(item => `${labelFor(item.key)}: ${item.period.range_start} — ${item.period.range_end}`)
      .join(" · ");
    note.textContent =
      tr(`Кожен ряд нормалізовано окремо: власний найактивніший інтервал (${timeOfDayBinLabel(binMinutes)}) = 100%. ${ranges}`,`Each series is normalized separately: its own most active interval (${timeOfDayBinLabel(binMinutes)}) = 100%. ${ranges}`);
  }

  state.charts.compareTimeOfDayChart = new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            title(items) {
              const i = items?.[0]?.dataIndex ?? 0;
              return intervalLabels[i] || labels[i] || "";
            },
            label(context) {
              const share = context.dataset.alertShares?.[context.dataIndex];
              return tr(`${context.dataset.label}: ${fmt(context.parsed.y,0)}% від власного піку · фактично ${fmt(share,1)}% часу`,`${context.dataset.label}: ${fmt(context.parsed.y,0)}% of its own peak · actually ${fmt(share,1)}% of the time`);
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: TEXT, autoSkip: true, maxTicksLimit: 9, maxRotation: 0 },
          grid: { color: GRID },
          title: { display: true, text: tr("Час доби","Time of day"), color: TEXT }
        },
        y: {
          min: 0,
          max: 100,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: tr("Відносна інтенсивність","Relative intensity"), color: TEXT }
        }
      }
    }
  });
}


function kyivThreatCauseLabel(key) {
  const labels = currentLanguage === "en"
    ? {
        "drone": "UAV",
        "massive-drone": "Mass UAV attack",
        "missile": "Missile",
        "ballistic": "Ballistic",
        "mig": "MiG-31K",
        "combined": "Combined",
        "unknown": "Other / unknown"
      }
    : {
        "drone": "БпЛА",
        "massive-drone": "Масована атака БпЛА",
        "missile": "Ракетна",
        "ballistic": "Балістична",
        "mig": "МіГ-31К",
        "combined": "Комбінована",
        "unknown": "Інше / невизначене"
      };
  return labels[key] || key;
}

function shortDateLabel(iso) {
  const parts = String(iso || "").split("-");
  return parts.length === 3 ? `${parts[2]}.${parts[1]}` : iso;
}

function renderKyivThreatCauses(key) {
  const section = $("kyivThreatCausesSection");
  const note = $("kyivThreatCausesNote");
  const data = state.kyivThreatMix;
  const rows = Array.isArray(data?.rows) ? data.rows : [];

  if (!section || key !== "kyiv" || !rows.length) {
    section?.classList.add("hidden");
    if (state.charts.kyivThreatCausesChart) {
      state.charts.kyivThreatCausesChart.destroy();
      delete state.charts.kyivThreatCausesChart;
    }
    return;
  }

  section.classList.remove("hidden");
  const used = KYIV_THREAT_CAUSE_ORDER.filter(cause =>
    rows.some(row => Number(row.minutes?.[cause] || 0) > 0)
  );
  const labels = rows.map(row => row.date);
  const datasets = used.map(cause => ({
    cause,
    label: kyivThreatCauseLabel(cause),
    data: rows.map(row => Number(row.shares?.[cause] || 0)),
    alertMinutes: rows.map(row => Number(row.minutes?.[cause] || 0)),
    backgroundColor: KYIV_THREAT_CAUSE_COLORS[cause],
    borderColor: KYIV_THREAT_CAUSE_COLORS[cause],
    borderWidth: 0,
    stack: "alert-time"
  }));

  if (state.charts.kyivThreatCausesChart) state.charts.kyivThreatCausesChart.destroy();
  state.charts.kyivThreatCausesChart = new Chart($("kyivThreatCausesChart"), {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          filter(context) {
            const total = Number(rows[context.dataIndex]?.total_minutes || 0);
            return total > 0 && Number(context.raw) > 0;
          },
          callbacks: {
            title(items) {
              if (!items.length) return "";
              return labels[items[0].dataIndex] || "";
            },
            label(context) {
              const row = rows[context.dataIndex];
              const cause = context.dataset.cause;
              const pct = Number(context.raw || 0);
              const mins = Number(row.minutes?.[cause] || 0);
              return ` ${context.dataset.label}: ${pct.toFixed(1)}% · ${mins.toFixed(0)} ${tr("хв","min")}`;
            },
            footer(items) {
              if (!items.length) return "";
              const total = Number(rows[items[0].dataIndex]?.total_minutes || 0);
              return total > 0
                ? `${tr("Усього під тривогою","Total time under alert")}: ${formatDurationMinutes(total)}`
                : tr("Тривог не було","No alerts");
            }
          }
        }
      },
      scales: {
        x: {
          stacked: true,
          ticks: {
            color: TEXT,
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 14,
            callback(value) {
              return shortDateLabel(this.getLabelForValue(value));
            }
          },
          grid: { color: GRID }
        },
        y: {
          stacked: true,
          min: 0,
          max: 100,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: tr("% часу тривог","% of alert time"), color: TEXT }
        }
      }
    }
  });

  const meta = data.meta || {};
  const first = meta.first_differentiated_date || rows[0]?.date || "";
  const start = meta.visible_start || rows[0]?.date || "";
  const end = meta.visible_end || rows[rows.length - 1]?.date || "";
  if (note) {
    note.textContent = tr(
      `Kyiv Digital · показано ${start} — ${end}. Диференційовані причини доступні з ${first}. Причина задається на рівні всієї завершеної тривоги; зміни причини всередині однієї тривоги історичний API не відновлює. Якщо в тривоги кілька причин, її час віднесено до «Комбінованої».`,
      `Kyiv Digital · shown ${start} — ${end}. Differentiated causes are available from ${first}. A cause is assigned to the whole completed alert; the historical API does not reconstruct changes within one alert. Alerts with multiple causes are assigned to “Combined”.`
    );
  }
}

function renderFreshness() {
  const banner = $("freshnessBanner");
  const fresh = state.data.multicity_meta?.effective_freshness || state.data.multicity_meta?.upstream_freshness;
  if (!fresh?.warning) {
    banner.classList.add("hidden");
    return;
  }
  const last = fresh.latest_proxy_event_end || fresh.last_successful_fetch_at;
  banner.textContent=tr(`⚠ Дані біля правого краю можуть бути неповними. Останнє підтверджене оновлення: ${last?String(last).slice(0,10):"невідомо"}. Нулі після цієї точки не слід трактувати як гарантовану відсутність тривог.`,`⚠ Data near the right edge may be incomplete. Last confirmed update: ${last?String(last).slice(0,10):"unknown"}. Zeros after that point should not be read as guaranteed absence of alerts.`);
  banner.classList.remove("hidden");
}

function renderDatasetSummary() {
  applyStaticLanguage();
  const keys = cityKeys();
  const exact = keys.filter(k => sourceType(k) === "exact_city").length;
  const proxy = keys.filter(k => sourceType(k) === "raion_proxy").length;
  $("datasetSummary").innerHTML=[
    tr(`${keys.length} ряди`,`${keys.length} series`),
    tr(`${exact} ряди з даними по місту`,`${exact} city-level series`),
    tr(`${proxy} рядів за даними районів`,`${proxy} district-level series`),
    tr("Донецьк і Луганськ поки не включені","Donetsk and Luhansk are not yet included")
  ].map(x=>`<span class="summary-pill">${x}</span>`).join("");
}

function renderCity() {
  const key = $("citySelect").value;
  const period = $("cityPeriod").value;
  const city = state.data.cities[key];
  if (!city) return;

  $("cityTitle").textContent = labelFor(key);
  const type = sourceType(key);
  const coverage = coverageStart(key);
  const badgeClass = type === "raion_proxy" ? "proxy" : "exact";
  const raion = districtText(key);
  $("cityMeta").innerHTML = [
    `<span class="badge ${badgeClass}">${typeText(key)}</span>`,
    coverage ? `<span class="badge">${tr("Покриття з","Coverage from")} ${coverage}</span>` : "",
    raion ? `<span class="badge">${raion}</span>` : ""
  ].join("");

  const kpi = city.kpis?.[0] || {};
  $("kpiAlerts").textContent = fmt(kpi.alerts_28d, 0);
  $("kpiHours").textContent = formatDurationHours(kpi.alert_hours_28d);
  $("kpiDuration").textContent = formatDurationMinutes(kpi.avg_alert_duration_min_28d);
  $("kpiMaxDay").textContent = fmt(kpi.max_alerts_day, 0);
  $("kpiMaxDayDate").textContent = kpi.max_alerts_day_date || "";

  const explosion = explosionCity(key);
  const explosionCard = $("kpiExplosionsCard");
  const explosionEstimateValue = explosionEstimate(explosion);
  if (explosion && explosionEstimateValue) {
    const sensitivityN = Number.isFinite(Number(explosion.sensitivity_n))
      ? Number(explosion.sensitivity_n)
      : Number(explosion.strict_n);
    explosionCard.classList.remove("hidden");
    $("kpiExplosionsPct").textContent = `≈${fmt(explosionEstimateValue.mid, 1)}%`;
    $("kpiExplosionsRange").textContent=tr(`Оцінюваний діапазон: ${fmt(explosionEstimateValue.low,1)}–${fmt(explosionEstimateValue.high,1)}%`,`Estimated range: ${fmt(explosionEstimateValue.low,1)}–${fmt(explosionEstimateValue.high,1)}%`);
    $("kpiExplosionsCount").textContent=tr(`Консервативно ${explosion.strict_n}; розширено ${sensitivityN} із ${explosion.total_alerts} тривог · весь доступний період`,`Conservative ${explosion.strict_n}; expanded ${sensitivityN} of ${explosion.total_alerts} alerts · full available period`);
    explosionCard.title=tr("Орієнтовне значення — середина між консервативною та розширеною оцінкою. Діапазон відображає класифікаційну невизначеність і не є статистичним довірчим інтервалом.","The indicative value is the midpoint between the conservative and expanded estimates. The range reflects classification uncertainty and is not a statistical confidence interval.");
  } else {
    explosionCard.classList.add("hidden");
    explosionCard.removeAttribute("title");
  }

  const allRows = periodRows(city, period);
  const rows = filterRowsByDateRange(allRows, period, "cityDateFrom", "cityDateTo");
  const labels = rows.map(r => rowTime(r, period));
  const dashed = type === "raion_proxy";

  const intensityDatasets = [
    {
      type: "bar",
      label: tr("Годин під тривогою / добу","Hours under alert / day"),
      data: rows.map(r => r.avg_daily_alert_hours),
      yAxisID: "yHours",
      backgroundColor: rows.map(r => isPartialPeriod(r) ? COLORS[0] + "22" : COLORS[0] + "77"),
      borderColor: rows.map(() => COLORS[0]),
      borderWidth: rows.map(r => isPartialPeriod(r) ? 0 : 1),
      _exportRows: rows
    },
    {
      type: "line",
      label: tr("Тривог / день","Alerts / day"),
      data: rows.map(r => r.alerts_per_day),
      yAxisID: "yAlerts",
      borderColor: COLORS[1],
      backgroundColor: COLORS[1] + "22",
      pointRadius: 0,
      pointHoverRadius: 0,
      borderWidth: 2,
      borderDash: dashed ? [7, 5] : [],
      segment: partialSegment(rows, COLORS[1]),
      _exportRows: rows,
      tension: 0,
      spanGaps: true
    }
  ];

  if (period === "daily28" && explosion?.strict_daily) {
    intensityDatasets.push({
      type: "line",
      label: tr("З повідомленням про вибухи / день","With reported explosions / day"),
      data: rows.map(row => (
        isPartialPeriod(row) && !Object.prototype.hasOwnProperty.call(explosion.strict_daily, row.date)
          ? null
          : Number(explosion.strict_daily[row.date] || 0)
      )),
      yAxisID: "yAlerts",
      borderColor: EXPLOSION_COLOR,
      backgroundColor: EXPLOSION_COLOR + "22",
      pointRadius: 2,
      pointHoverRadius: 4,
      borderWidth: 2,
      tension: 0,
      spanGaps: false
    });
  }

  const intensitySubtitle = $("cityIntensityChart")?.closest(".chart-card")?.querySelector(".chart-subtitle");
  if (intensitySubtitle) {
    intensitySubtitle.textContent = period === "daily28" && explosion?.strict_daily
      ? tr(
          "Стовпчики: години під тривогою за день. Зелена лінія: кількість тривог за день. Помаранчева: тривоги з підтвердженим повідомленням про вибухи. Останній пунктирний день — поточний неповний день станом на останнє оновлення.",
          "Bars: hours under alert per day. Green line: alerts per day. Orange: alerts with a confirmed report of explosions. The final dashed day is the current incomplete day as of the latest update."
        )
      : tr(
          "Стовпчики: сумарний час під тривогою в обраному періоді ÷ кількість календарних днів. Лінія: кількість тривог, що почалися в періоді ÷ кількість днів.",
          "Bars: total time under alert in the selected period ÷ calendar days. Line: alerts that started in the period ÷ days."
        );
  }

  if (state.charts.cityIntensityChart) state.charts.cityIntensityChart.destroy();
  state.charts.cityIntensityChart = new Chart($("cityIntensityChart"), {
    data: {
      labels,
      datasets: intensityDatasets
    },
    plugins: [partialPeriodBarPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            label(context) {
              if (context.dataset.yAxisID === "yHours") {
                return `${context.dataset.label}: ${formatDurationHours(context.parsed.y)}`;
              }
              return `${context.dataset.label}: ${fmt(context.parsed.y, 2)}`;
            },
            footer(items) {
              const i = items?.[0]?.dataIndex ?? -1;
              return isPartialPeriod(rows[i])?tr("Поточний неповний період","Current incomplete period"):"";
            }
          }
        },
        partialPeriodBar: { rows, datasetIndices: [0] }
      },
      scales: {
        x: { ticks: { color: TEXT, maxRotation: 0, autoSkip: true }, grid: { color: GRID } },
        yHours: {
          position: "left",
          beginAtZero: true,
          ticks: { color: TEXT, callback: value => formatDurationHours(value) },
          grid: { color: GRID },
          title: { display: true, text: tr("Час / добу","Time / day"), color: TEXT }
        },
        yAlerts: {
          position: "right",
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { drawOnChartArea: false },
          title: { display: true, text: tr("Тривог / день","Alerts / day"), color: TEXT }
        }
      }
    }
  });

  const durationCard = $("cityDurationChart")?.closest(".chart-card");
  const durationTitle = durationCard?.querySelector("h3");
  const durationSubtitle = durationCard?.querySelector(".chart-subtitle");
  if (period === "daily28") {
    if (durationTitle) durationTitle.textContent = tr(
      "Середня тривалість тривоги в межах доби",
      "Average within-day alert duration"
    );
    if (durationSubtitle) durationSubtitle.textContent = tr(
      "Для кожного календарного дня тривоги розрізаються на межі опівночі. Показано середню тривалість відрізків тривог, що припали на цей день. Кількість тривог при цьому й далі рахується лише в день початку. Останній пунктирний день — поточний неповний.",
      "For each calendar day, alerts are split at midnight. The chart shows the average duration of alert segments that fall within that day. Alert counts still belong only to the day on which the alert started. The final dashed day is the current incomplete day."
    );
  } else {
    if (durationTitle) durationTitle.textContent = tr(
      "Середня тривалість однієї тривоги",
      "Average duration of one alert"
    );
    if (durationSubtitle) durationSubtitle.textContent = tr(
      "Середня тривалість усіх тривог, що почалися в обраному періоді. Якщо тривога закінчилася вже після завершення періоду, вся її тривалість відноситься до періоду старту.",
      "Average full duration of alerts that started in the selected period. If an alert ends after the period, its full duration is attributed to the period in which it started."
    );
  }

  setDurationChart("cityDurationChart", labels, [seriesDataset(labelFor(key), rows.map(r => r.avg_alert_duration_min), COLORS[2], dashed, rows)], "minutes");

  renderAlertBurden(key);
  renderTimeOfDay(key);
  renderDaypart(key);
  renderKyivThreatCauses(key);
  renderCasualties(key);
  updateUrl();
}

function renderRolling7d(key) {
  const section = $("rolling7dSection");
  const allRows = state.data.cities[key]?.weekly || [];
  if (!rolling7dEnabled() || !allRows.length) {
    section?.classList.add("hidden");
    for (const id of ["rolling7dIntensityChart", "rolling7dDurationChart"]) {
      if (state.charts[id]) {
        state.charts[id].destroy();
        delete state.charts[id];
      }
    }
    return;
  }

  section?.classList.remove("hidden");

  const yearSelect = $("rolling7dYear");
  const availableYears = [...new Set(
    allRows
      .map(r => String(rowTime(r, "weekly")).slice(0, 4))
      .filter(year => /^\d{4}$/.test(year))
  )].sort((a, b) => Number(b) - Number(a));
  const currentCalendarYear = String(new Date().getFullYear());
  const requestedPreset = yearSelect?.value || getParams().get("year") || "";
  const hadExplicitRange = Boolean($("rolling7dDateFrom")?.value || $("rolling7dDateTo")?.value);
  const selectedPreset = hadExplicitRange && !requestedPreset
    ? "custom"
    : (["custom", "all", ...availableYears].includes(requestedPreset)
      ? requestedPreset
      : (availableYears.includes(currentCalendarYear) ? currentCalendarYear : (availableYears[0] || "all")));

  if (yearSelect) {
    yearSelect.innerHTML = [
      `<option value="custom">${tr("Довільно","Custom")}</option>`,
      `<option value="all">${tr("Увесь період","Full range")}</option>`,
      ...availableYears.map(year => `<option value="${year}">${year}</option>`)
    ].join("");
    yearSelect.value = selectedPreset;
  }

  syncDateRange("rolling7dDateFrom", "rolling7dDateTo", allRows.map(r => rowTime(r, "weekly")));
  if (!hadExplicitRange) applyRolling7dQuickRange(key, selectedPreset);
  const rollingRange = {
    from: $("rolling7dDateFrom")?.value || "",
    to: $("rolling7dDateTo")?.value || ""
  };
  const rows = allRows.filter(r => dateKeyInRange(rowTime(r, "weekly"), rollingRange.from, rollingRange.to));
  const labels = rows.map(r => rowTime(r, "weekly"));
  const dashed = sourceType(key) === "raion_proxy";

  if (state.charts.rolling7dIntensityChart) state.charts.rolling7dIntensityChart.destroy();
  state.charts.rolling7dIntensityChart = new Chart($("rolling7dIntensityChart"), {
    data: {
      labels,
      datasets: [
        {
          type: "bar",
          label: tr("Годин під тривогою / добу","Hours under alert / day"),
          data: rows.map(r => r.avg_daily_alert_hours),
          yAxisID: "yHours",
          backgroundColor: rows.map(r => isPartialPeriod(r) ? COLORS[0] + "22" : COLORS[0] + "77"),
          borderColor: rows.map(() => COLORS[0]),
          borderWidth: rows.map(r => isPartialPeriod(r) ? 0 : 1)
        },
        {
          type: "line",
          label: tr("Тривог / день","Alerts / day"),
          data: rows.map(r => r.alerts_per_day),
          yAxisID: "yAlerts",
          borderColor: COLORS[1],
          backgroundColor: COLORS[1] + "22",
          pointRadius: 0,
          pointHoverRadius: 0,
          borderWidth: 2,
          borderDash: dashed ? [7, 5] : [],
          segment: partialSegment(rows, COLORS[1]),
          tension: 0,
          spanGaps: true
        }
      ]
    },
    plugins: [partialPeriodBarPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            label(context) {
              if (context.dataset.yAxisID === "yHours") {
                return `${context.dataset.label}: ${formatDurationHours(context.parsed.y)}`;
              }
              return `${context.dataset.label}: ${fmt(context.parsed.y, 2)}`;
            },
            footer(items) {
              const i = items?.[0]?.dataIndex ?? -1;
              return isPartialPeriod(rows[i])?tr("Поточний неповний період","Current incomplete period"):"";
            }
          }
        },
        partialPeriodBar: { rows, datasetIndices: [0] }
      },
      scales: {
        x: { ticks: { color: TEXT, maxRotation: 0, autoSkip: true }, grid: { color: GRID } },
        yHours: {
          position: "left",
          beginAtZero: true,
          ticks: { color: TEXT, callback: value => formatDurationHours(value) },
          grid: { color: GRID },
          title: { display: true, text: tr("Час / добу","Time / day"), color: TEXT }
        },
        yAlerts: {
          position: "right",
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { drawOnChartArea: false },
          title: { display: true, text: tr("Тривог / день","Alerts / day"), color: TEXT }
        }
      }
    }
  });

  setDurationChart(
    "rolling7dDurationChart",
    labels,
    [seriesDataset(labelFor(key), rows.map(r => r.avg_alert_duration_min), COLORS[2], dashed, rows)],
    "minutes"
  );
}

function renderShortHorizon(key) {
  const allRows = state.data.cities[key]?.daily28 || [];
  const rows = filterRowsByDateRange(allRows, "daily", "shortDateFrom", "shortDateTo");
  const labels = rows.map(r => r.date || String(r.time || "").slice(0, 10));
  const range = $("daily28Range");
  if (range) {
    range.textContent = labels.length
      ? tr(`Щоденний розріз для ${labelFor(key)}: ${labels[0]} — ${labels[labels.length-1]}. Сьогоднішній день не включається.`,`Daily view for ${labelFor(key)}: ${labels[0]} — ${labels[labels.length-1]}. Today is excluded.`)
      : tr(`Для ${labelFor(key)} немає доступного 28-денного ряду.`,`No 28-day series is available for ${labelFor(key)}.`);
  }

  setChart(
    "daily28HoursChart",
    labels,
    [{
      label: tr("Годин під тривогою","Hours under alert"),
      data: rows.map(r => r.total_alert_duration_hours),
      backgroundColor: COLORS[0] + "88",
      borderColor: COLORS[0],
      borderWidth: 1
    }],
    "Годин",
    "bar",
    {
      layout: { padding: { right: 70 } },
      plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
      scales: {
        x: {
          offset: true,
          ticks: { color: TEXT, maxRotation: 0, autoSkip: true },
          grid: { color: GRID }
        },
        y: {
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { color: GRID },
          title: { display: true, text: "Годин", color: TEXT },
          afterFit: scale => { scale.width = 62; }
        }
      }
    }
  );

  const explosion = explosionCity(key);
  const strictDaily = explosion?.strict_daily || {};
  const regularAlerts = rows.map(r => Math.max(0, Number(r.alerts_started || 0) - Number(strictDaily[r.date] || 0)));
  const explosionAlerts = rows.map(r => Number(strictDaily[r.date] || 0));
  const alertBarDatasets = explosion ? [
    {
      type: "bar",
      label: tr("Інші тривоги","Other alerts"),
      data: regularAlerts,
      yAxisID: "yAlerts",
      stack: "alerts",
      backgroundColor: COLORS[1] + "77",
      borderColor: COLORS[1],
      borderWidth: 1
    },
    {
      type: "bar",
      label: tr("З повідомленням про вибухи","With reported explosions"),
      data: explosionAlerts,
      yAxisID: "yAlerts",
      stack: "alerts",
      backgroundColor: EXPLOSION_COLOR + "cc",
      borderColor: EXPLOSION_COLOR,
      borderWidth: 1
    }
  ] : [{
    type: "bar",
    label: tr("Тривог, що почалися","Alerts started"),
    data: rows.map(r => r.alerts_started),
    yAxisID: "yAlerts",
    backgroundColor: COLORS[1] + "77",
    borderColor: COLORS[1],
    borderWidth: 1
  }];

  if (state.charts.daily28AlertsDurationChart) state.charts.daily28AlertsDurationChart.destroy();
  state.charts.daily28AlertsDurationChart = new Chart($("daily28AlertsDurationChart"), {
    data: {
      labels,
      datasets: [
        ...alertBarDatasets,
        {
          type: "line",
          label: tr("Середня тривалість, хв","Average duration, min"),
          data: rows.map(r => r.avg_alert_duration_minutes),
          yAxisID: "yDuration",
          borderColor: COLORS[2],
          backgroundColor: COLORS[2] + "22",
          pointRadius: 0,
          pointHoverRadius: 0,
          borderWidth: 2,
          borderDash: sourceType(key) === "raion_proxy" ? [7, 5] : [],
          tension: 0,
          spanGaps: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: { mode: "index", intersect: false }
      },
      scales: {
        x: {
          offset: true,
          ticks: { color: TEXT, maxRotation: 0, autoSkip: true },
          grid: { color: GRID }
        },
        yAlerts: {
          position: "left",
          beginAtZero: true,
          stacked: true,
          ticks: { color: TEXT, precision: 0 },
          grid: { color: GRID },
          title: { display: true, text: tr("Кількість тривог","Number of alerts"), color: TEXT },
          afterFit: scale => { scale.width = 62; }
        },
        yDuration: {
          position: "right",
          beginAtZero: true,
          ticks: { color: TEXT },
          grid: { drawOnChartArea: false },
          title: { display: true, text: tr("Середня тривалість, хв","Average duration, min"), color: TEXT },
          afterFit: scale => { scale.width = 70; }
        }
      }
    }
  });
}

function renderCasualties(key) {
  const section = $("casualtySection");
  const series = state.data.casualties_by_city?.[key] || (key === "kyiv" ? state.data.casualties : null);
  const allRows = series?.monthly || [];
  if (!allRows.length) {
    section.classList.add("hidden");
    if (state.charts.casualtyChart) {
      state.charts.casualtyChart.destroy();
      delete state.charts.casualtyChart;
    }
    return;
  }

  section.classList.remove("hidden");
  $("casualtyCityEyebrow").textContent = labelFor(key);

  const selectedYear = syncCasualtyYearOptions(allRows);
  const interval = $("casualtyInterval")?.value === "yearly" ? "yearly" : "monthly";
  const filteredRows = casualtyRowsForYear(allRows, selectedYear);

  const meta = series?.meta || {};
  const total = allRows.reduce((sum, r) => sum + (Number(r.deaths) || 0), 0);
  const unresolved = Number(meta.unresolved_review_cases || 0);
  $("casualtySourceNote").textContent=unresolved
    ?tr(`Підтверджений ряд: ${total} загиблих. Невирішених випадків, що потребують перевірки: ${unresolved}; їх не включено. Реконструкція за публічно доступними повідомленнями офіційних органів і медіа.`,`Confirmed series: ${total} deaths. Unresolved cases requiring review: ${unresolved}; they are excluded. Reconstructed from publicly available reports by official bodies and media.`)
    :tr(`Підтверджений ряд: ${total} загиблих. Реконструкція за публічно доступними повідомленнями офіційних органів і медіа.`,`Confirmed series: ${total} deaths. Reconstructed from publicly available reports by official bodies and media.`);

  const chartRows = interval === "yearly" ? aggregateCasualtiesByYear(filteredRows) : filteredRows;
  const labels = interval === "yearly"
    ? chartRows.map(r => r.year)
    : chartRows.map(r => r.month || String(r.time || "").slice(0, 7));
  const values = chartRows.map(r => Number(r.deaths) || 0);

  setChart(
    "casualtyChart",
    labels,
    [{ label: tr("Загиблих","Deaths"), data: values, backgroundColor: "#62a0ea99", borderColor: "#62a0ea", borderWidth: 1 }],
    tr("Кількість загиблих","Number of deaths"),
    "bar",
    { plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } } }
  );
}

function sharedRows(keys, period) {
  const maps = keys.map(key => {
    const m = new Map();
    for (const row of periodRows(state.data.cities[key], period)) m.set(rowTime(row, period), row);
    return m;
  });
  if (!maps.length) return [];
  const times = commonPeriodTimes(keys, period);
  const range = syncDateRange("compareDateFrom", "compareDateTo", times);
  return times
    .filter(t => dateKeyInRange(t, range.from, range.to))
    .map(t => ({ time: t, rows: maps.map(m => m.get(t)) }));
}

function renderExplosionComparison(keys) {
  const card = $("compareExplosionsCard");
  const note = $("compareExplosionsNote");
  if (!attackEventFeaturesEnabled()) {
    card?.classList.add("hidden");
    if (state.charts.compareExplosionsChart) {
      state.charts.compareExplosionsChart.destroy();
      delete state.charts.compareExplosionsChart;
    }
    return;
  }
  const availableKeys = keys.filter(key => (explosionCity(key)?.rolling90 || []).length);
  const missingKeys = keys.filter(key => !availableKeys.includes(key));

  if (!availableKeys.length) {
    card.classList.add("hidden");
    if (state.charts.compareExplosionsChart) {
      state.charts.compareExplosionsChart.destroy();
      delete state.charts.compareExplosionsChart;
    }
    return;
  }

  card.classList.remove("hidden");
  const maps = new Map();
  const allDates = new Set();
  for (const key of availableKeys) {
    const m = new Map();
    for (const row of explosionCity(key).rolling90) {
      m.set(row.date, row);
      allDates.add(row.date);
    }
    maps.set(key, m);
  }
  const allLabels = [...allDates].sort();
  const latestDate = allLabels[allLabels.length - 1];
  const latestDay = Math.floor(Date.parse(`${latestDate}T00:00:00Z`) / 86400000);
  const labels = allLabels.filter(date => {
    const day = Math.floor(Date.parse(`${date}T00:00:00Z`) / 86400000);
    return Number.isFinite(day) && (latestDay - day) % 7 === 0;
  }).filter(date => dateKeyInRange(
    date,
    $("compareDateFrom")?.value || "",
    $("compareDateTo")?.value || ""
  ));
  const datasets = availableKeys.map((key, idx) => {
    const m = maps.get(key);
    const ds = seriesDataset(
      labelFor(key),
      labels.map(date => m.get(date)?.pct ?? null),
      COLORS[idx],
      false
    );
    ds.pointRadius = 0;
    ds.pointHoverRadius = 0;
    ds.spanGaps = false;
    ds.cityKey = key;
    ds.explosionRows = labels.map(date => m.get(date) || null);
    return ds;
  });

  setChart(
    "compareExplosionsChart",
    labels,
    datasets,
    "%",
    "line",
    {
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            label: context => {
              const row = context.dataset.explosionRows?.[context.dataIndex];
              if (!row) return null;
              return `${context.dataset.label}: ${fmt(row.pct, 1)}% · ${row.strict_n}/${row.alerts_n}`;
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: TEXT, maxRotation: 0, autoSkip: true }, grid: { color: GRID } },
        y: {
          beginAtZero: true,
          ticks: { color: TEXT, callback: value => `${value}%` },
          grid: { color: GRID },
          title: { display: true, text: tr("% тривог із повідомленнями про вибухи","% of alerts with reported explosions"), color: TEXT }
        }
      }
    }
  );

  const rangeNote=tr("Лінії показують консервативну strict-оцінку; агрегований KPI для міста вище подається як орієнтовне midpoint-значення з діапазоном strict–sensitivity. Це класифікаційна невизначеність, не довірчий інтервал.","Lines show the conservative strict estimate; the city KPI above is an indicative midpoint with a strict–sensitivity range. This is classification uncertainty, not a confidence interval.");
  note.textContent=missingKeys.length
    ?tr(`Ковзні 90 днів, strict; на графіку показано одну точку кожні 7 днів, і кожна точка = n/N за попередні 90 завершених днів. Поки немає завершеного explosion-ряду: ${missingKeys.map(labelFor).join(", ")}. ${rangeNote}`,`Rolling 90 days, strict; one point every 7 days, each equal to n/N over the previous 90 completed days. No completed explosion series yet for: ${missingKeys.map(labelFor).join(", ")}. ${rangeNote}`)
    :tr(`Ковзні 90 днів, strict; на графіку показано одну точку кожні 7 днів, і кожна точка = n/N за попередні 90 завершених днів. Перемикач «Період» вище на цей графік не впливає. ${rangeNote}`,`Rolling 90 days, strict; one point every 7 days, each equal to n/N over the previous 90 completed days. The Period control above does not affect this chart. ${rangeNote}`);
}

function renderComparison() {
  const keys = [$("compareA").value, $("compareB").value, $("compareC").value].filter(Boolean);
  const period = $("comparePeriod").value;
  const shared = sharedRows(keys, period);
  const labels = shared.map(x => x.time);
  let countLabel=tr("періодів","periods");
  if(period==="monthly")countLabel=tr("міс.","months");
  if(period==="calendarWeekly")countLabel=tr("тиж.","weeks");
  if(period==="weekly")countLabel=tr("7-денних вікон","7-day windows");
  if(period==="rolling30")countLabel=tr("30-денних вікон","30-day windows");
  if(period==="rolling90")countLabel=tr("90-денних вікон","90-day windows");
  if(period==="rolling180")countLabel=tr("180-денних вікон","180-day windows");
  if(period==="daily28")countLabel=tr("днів","days");
  const note=shared.length?tr(`Спільний ряд для ${keys.length} міст: ${labels[0]} — ${labels[labels.length-1]} (${shared.length} ${countLabel}).`,`Common series for ${keys.length} cities: ${labels[0]} — ${labels[labels.length-1]} (${shared.length} ${countLabel}).`):tr("Немає спільних періодів для цієї комбінації.","No common periods are available for this combination.");
  $("comparisonNote").textContent = note;

  const metricChart = (id, metric, yTitle) => {
    const datasets = keys.map((key, idx) => seriesDataset(
      labelFor(key),
      shared.map(x => x.rows[idx]?.[metric] ?? null),
      COLORS[idx],
      sourceType(key) === "raion_proxy",
      shared.map(x => x.rows[idx])
    ));
    if (metric === "avg_daily_alert_hours") setDurationChart(id, labels, datasets, "hours");
    else if (metric === "avg_alert_duration_min") setDurationChart(id, labels, datasets, "minutes");
    else setChart(id, labels, datasets, yTitle);
  };

  metricChart("compareAlertsChart","alerts_per_day",tr("Тривог/день","Alerts/day"));
  metricChart("compareHoursChart","avg_daily_alert_hours",tr("Годин/добу","Hours/day"));
  metricChart("compareDurationChart","avg_alert_duration_min",tr("Хвилин","Minutes"));
  renderTimeOfDayComparison(keys);
  renderExplosionComparison(keys);

  const casualtyCard = $("compareCasualtiesCard");
  const casualtyNote = $("compareCasualtiesNote");
  const casualtyKeys = keys.filter(key => (state.data.casualties_by_city?.[key]?.monthly || []).length);
  const missingCasualtyKeys = keys.filter(key => !casualtyKeys.includes(key));

  if (!casualtyKeys.length) {
    casualtyCard.classList.add("hidden");
    if (state.charts.compareCasualtiesChart) {
      state.charts.compareCasualtiesChart.destroy();
      delete state.charts.compareCasualtiesChart;
    }
  } else {
    casualtyCard.classList.remove("hidden");
    const selectedYear = syncCompareCasualtyYearOptions(casualtyKeys);
    const casualtyInterval = $("compareCasualtyInterval")?.value === "yearly" ? "yearly" : "monthly";

    const maps = casualtyKeys.map(key => {
      const filtered = casualtyRowsForYear(
        state.data.casualties_by_city[key].monthly,
        selectedYear
      );
      const rows = casualtyInterval === "yearly"
        ? aggregateCasualtiesByYear(filtered).map(row => ({ key: row.year, deaths: row.deaths }))
        : filtered.map(row => ({
            key: row.month || String(row.time || "").slice(0, 7),
            deaths: Number(row.deaths) || 0
          }));
      return new Map(rows.map(row => [row.key, row.deaths]));
    });

    let commonLabels = new Set(maps[0].keys());
    for (const map of maps.slice(1)) {
      commonLabels = new Set([...commonLabels].filter(label => map.has(label)));
    }
    const casualtyLabels = [...commonLabels].sort();
    const casualtyDatasets = casualtyKeys.map((key, idx) => ({
      label: labelFor(key),
      data: casualtyLabels.map(label => maps[idx].get(label) ?? null),
      backgroundColor: COLORS[idx] + "77",
      borderColor: COLORS[idx],
      borderWidth: 1
    }));

    setChart(
      "compareCasualtiesChart",
      casualtyLabels,
      casualtyDatasets,
      tr("Кількість загиблих","Number of deaths"),
      "bar",
      { plugins: { legend: { labels: { color: TEXT, boxWidth: 14, usePointStyle: true } }, tooltip: { mode: "index", intersect: false } } }
    );

    const intervalText = casualtyInterval === "yearly"
      ? tr("Річний ряд","Annual series")
      : tr("Помісячний ряд","Monthly series");
    const yearText = selectedYear === "all"
      ? tr("усі спільні роки","all common years")
      : selectedYear;
    const missingText = missingCasualtyKeys.length
      ? tr(` Немає готового ряду загиблих: ${missingCasualtyKeys.map(labelFor).join(", ")}.`, ` No completed death series for: ${missingCasualtyKeys.map(labelFor).join(", ")}.`)
      : "";
    casualtyNote.textContent = tr(
      `${intervalText}, ${yearText}. Показано лише періоди, спільні для міст із доступним рядом.${missingText}`,
      `${intervalText}, ${yearText}. Only periods common to cities with an available series are shown.${missingText}`
    );
  }

  updateUrl();
}

function isMissingSortValue(value) {
  return value === null || value === undefined || value === "" || (typeof value === "number" && Number.isNaN(value));
}

function compareTableRows(a, b) {
  const { key, direction } = state.tableSort;
  const av = a[key];
  const bv = b[key];
  const aMissing = isMissingSortValue(av);
  const bMissing = isMissingSortValue(bv);

  if (aMissing && bMissing) return a.label.localeCompare(b.label,localeCode());
  if (aMissing) return 1;
  if (bMissing) return -1;

  let cmp;
  if (key === "label" || key === "coverage") {
    cmp=String(av).localeCompare(String(bv),localeCode(),{numeric:true,sensitivity:"base"});
  } else {
    cmp = Number(av) - Number(bv);
  }
  if (cmp === 0) cmp = a.label.localeCompare(b.label,localeCode());
  return direction === "asc" ? cmp : -cmp;
}

function updateTableSortHeaders() {
  const headers = document.querySelectorAll(".table-panel thead th");
  TABLE_SORT_COLUMNS.forEach((column, idx) => {
    const th = headers[idx];
    if (!th) return;
    const active = state.tableSort.key === column.key;
    const arrow = active ? (state.tableSort.direction === "asc" ? " ↑" : " ↓") : " ↕";
    const columnLabel=tableColumnLabel(column);
    th.textContent=columnLabel+arrow;
    th.dataset.sortKey = column.key;
    th.setAttribute("aria-sort", active ? (state.tableSort.direction === "asc" ? "ascending" : "descending") : "none");
    th.setAttribute("role", "button");
    th.tabIndex = 0;
    th.title=active?tr(`Сортування: ${state.tableSort.direction==="asc"?"за зростанням":"за спаданням"}. Натисніть, щоб змінити напрямок.`,`Sorted ${state.tableSort.direction==="asc"?"ascending":"descending"}. Click to change direction.`):tr(`Сортувати за колонкою «${columnLabel}»`,`Sort by “${columnLabel}”`);
    th.style.cursor = "pointer";
    th.style.userSelect = "none";
  });
}

function changeTableSort(column) {
  if (state.tableSort.key === column.key) {
    state.tableSort.direction = state.tableSort.direction === "asc" ? "desc" : "asc";
  } else {
    state.tableSort = { key: column.key, direction: column.defaultDirection };
  }
  renderAllCitiesTable();
}

function setupTableSorting() {
  const headers = document.querySelectorAll(".table-panel thead th");
  TABLE_SORT_COLUMNS.forEach((column, idx) => {
    const th = headers[idx];
    if (!th) return;
    const activate = () => changeTableSort(column);
    th.addEventListener("click", activate);
    th.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate();
      }
    });
  });
  updateTableSortHeaders();
}

function renderAllCitiesTable() {
  const selected = $("allCitiesRange")?.value || "30d";
  const range = TABLE_RANGES.includes(selected) ? selected : "30d";
  const periodLabels = {
    "7d":tr("7 днів","7 days"),
    "30d":tr("30 днів","30 days"),
    "90d":tr("90 днів","90 days"),
    "year":tr("Рік","Year"),
    "common":tr("Від початку спільних даних","From start of common data"),
    "custom":tr("Довільний період","Custom period")
  };
  const root = state.data.all_cities_table_test;
  const cities = root?.cities || {};
  const commonBounds = commonMonthlyDateBounds();

  let customFrom = $("tableDateFrom")?.value || "";
  let customTo = $("tableDateTo")?.value || "";
  if (range === "custom" && commonBounds) {
    const customRange = syncFixedDateRange("tableDateFrom", "tableDateTo", commonBounds.min, commonBounds.max);
    customFrom = customRange.from;
    customTo = customRange.to;
  }

  const rows = cityKeys().map(key => {
    if (range === "custom") {
      const aggregate = aggregateMonthlyRange(key, customFrom, customTo);
      return {
        key,
        label: labelFor(key),
        alerts: aggregate?.alerts ?? null,
        hours: aggregate?.hours ?? null,
        duration: aggregate?.duration ?? null,
        coverage: coverageStart(key),
        rangeStart: aggregate?.rangeStart || null,
        rangeEnd: aggregate?.rangeEnd || null
      };
    }

    const period = cities?.[key]?.periods?.[range];
    const fallback = state.data.cities[key]?.kpis?.[0] || {};
    return {
      key,
      label: labelFor(key),
      alerts: period?.alerts_started ?? fallback.alerts_28d,
      hours: period?.alert_hours ?? fallback.alert_hours_28d,
      duration: period?.avg_alert_duration_min ?? fallback.avg_alert_duration_min_28d,
      coverage: coverageStart(key),
      rangeStart: period?.range_start || fallback.period_start || null,
      rangeEnd: period?.range_end || fallback.period_end || null
    };
  });

  if (range !== "custom") {
    const sample = rows.find(r => r.rangeStart && r.rangeEnd);
    if (sample) {
      for (const id of ["tableDateFrom", "tableDateTo"]) {
        $(id)?.removeAttribute("min");
        $(id)?.removeAttribute("max");
      }
      if ($("tableDateFrom")) $("tableDateFrom").value = sample.rangeStart;
      if ($("tableDateTo")) $("tableDateTo").value = sample.rangeEnd;
    }
  }

  rows.sort(compareTableRows);
  state.lastAllCitiesRows = rows.map(row => ({ ...row }));
  $("allCitiesTable").innerHTML = rows.map(r => `
    <tr>
      <td><button class="table-city-link" data-city="${r.key}" type="button">${r.label}</button></td>
      <td>${fmt(r.alerts, 0)}</td>
      <td>${formatDurationHours(r.hours)}</td>
      <td>${formatDurationMinutes(r.duration)}</td>
      <td>${r.coverage || "—"}</td>
    </tr>`).join("");

  const note = $("allCitiesRangeNote");
  if (note) {
    if (range === "custom") {
      const actual = rows.find(r => r.rangeStart && r.rangeEnd);
      const actualDates = actual ? `${actual.rangeStart} — ${actual.rangeEnd}` : "—";
      note.textContent = tr(
        `Довільний діапазон: ${customFrom || "—"} — ${customTo || "—"}. Для зіставності рахуються лише повні календарні місяці всередині діапазону; фактично використано ${actualDates}.`,
        `Custom range: ${customFrom || "—"} — ${customTo || "—"}. For comparability, only complete calendar months fully inside the range are used; effective range ${actualDates}.`
      );
    } else {
      const sample = rows.find(r => r.rangeStart && r.rangeEnd);
      const dates = sample ? `${sample.rangeStart} — ${sample.rangeEnd}` : "—";
      note.textContent = tr(
        `${periodLabels[range]} · ${dates}. Усі 23 ряди рахуються на одному спільному часовому вікні.`,
        `${periodLabels[range]} · ${dates}. All 23 series use the same common time window.`
      );
    }
  }

  document.querySelectorAll(".table-city-link").forEach(btn => btn.addEventListener("click", () => {
    $("citySelect").value = btn.dataset.city;
    renderCity();
    window.scrollTo({ top: $("cityTitle").offsetTop - 24, behavior: "smooth" });
  }));
  updateTableSortHeaders();
}

let tourStepIndex = 0;
let activeTourTarget = null;

function tourWasSeen() {
  try {
    return localStorage.getItem(TOUR_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function markTourSeen() {
  try {
    localStorage.setItem(TOUR_STORAGE_KEY, "1");
  } catch {
    // Tour remains usable without browser storage.
  }
}

function resolveTourTarget(step) {
  let target = document.querySelector(step.selector);
  if (target && step.closest) target = target.closest(step.closest);
  return target;
}

function visibleTourStepIndices() {
  return TOUR_STEPS
    .map((step, index) => ({ index, target: resolveTourTarget(step) }))
    .filter(item => item.target && item.target.getClientRects().length)
    .map(item => item.index);
}

function clearTourTarget() {
  if (activeTourTarget) activeTourTarget.classList.remove("tour-target");
  activeTourTarget = null;
}

function showTourStep(index) {
  const root = $("introTour");
  if (!root) return;

  const visible = visibleTourStepIndices();
  if (!visible.length) {
    finishIntroTour();
    return;
  }

  let nextIndex = index;
  if (!visible.includes(nextIndex)) {
    const direction = index >= tourStepIndex ? 1 : -1;
    nextIndex = direction > 0
      ? visible.find(value => value >= index)
      : [...visible].reverse().find(value => value <= index);
  }
  if (nextIndex == null || !visible.includes(nextIndex)) {
    finishIntroTour();
    return;
  }

  const target = resolveTourTarget(TOUR_STEPS[nextIndex]);
  if (!target) {
    finishIntroTour();
    return;
  }

  tourStepIndex = nextIndex;
  const step = TOUR_STEPS[tourStepIndex];
  const position = visible.indexOf(tourStepIndex);

  clearTourTarget();
  activeTourTarget = target;
  activeTourTarget.classList.add("tour-target");

  $("tourTitle").textContent=tr(step.titleUk,step.titleEn);
  $("tourText").textContent=tr(step.textUk,step.textEn);
  $("tourProgress").textContent = String(position + 1) + " / " + String(visible.length);
  $("tourPrev").disabled = position === 0;
  $("tourNext").textContent=position===visible.length-1?tr("Готово","Done"):tr("Далі","Next");

  root.classList.remove("hidden");
  root.setAttribute("aria-hidden", "false");
  document.body.classList.add("tour-open");

  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  target.scrollIntoView({
    behavior: reduceMotion ? "auto" : "smooth",
    block: "center",
    inline: "nearest"
  });
}

function startIntroTour() {
  tourStepIndex = 0;
  showTourStep(0);
}

function finishIntroTour() {
  const root = $("introTour");
  clearTourTarget();
  if (root) {
    root.classList.add("hidden");
    root.setAttribute("aria-hidden", "true");
  }
  document.body.classList.remove("tour-open");
  markTourSeen();
}

function bindIntroTour() {
  $("showTour")?.addEventListener("click", startIntroTour);
  $("tourNext")?.addEventListener("click", () => {
    const visible = visibleTourStepIndices();
    const position = visible.indexOf(tourStepIndex);
    if (position < 0 || position >= visible.length - 1) finishIntroTour();
    else showTourStep(visible[position + 1]);
  });
  $("tourPrev")?.addEventListener("click", () => {
    const visible = visibleTourStepIndices();
    const position = visible.indexOf(tourStepIndex);
    if (position > 0) showTourStep(visible[position - 1]);
  });
  $("tourSkip")?.addEventListener("click", finishIntroTour);
  $("tourClose")?.addEventListener("click", finishIntroTour);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !$("introTour")?.classList.contains("hidden")) finishIntroTour();
  });
}

function maybeStartIntroTour() {
  if (tourWasSeen()) return;
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      if ($("introTour")?.classList.contains("hidden")) startIntroTour();
    });
  });
}

function renderMethodology(){
 const rolling=rolling7dEnabled(),cw=$("cityWeeklyOption"),pw=$("compareWeeklyOption");
 if(cw)cw.textContent=rolling?tr("Ковзні 7 днів","Rolling 7 days"):tr("Тижні","Weeks");
 if(pw)pw.textContent=rolling?tr("Ковзні 7 днів","Rolling 7 days"):tr("Тижні","Weeks");
 const p=$("periodMethodology");if(p)p.textContent=rolling?tr("У розрахунках використовуються лише завершені календарні дні за часовою зоною Europe/Kyiv. Сьогоднішній день не враховується. Показники за останні 28 днів охоплюють рівно 28 завершених днів до вчора включно. Ковзні 7-, 30- і 90-денні показники будуються лише тоді, коли для всього вікна вже є дані. Поточний неповний зріз, якщо він показаний, позначається пунктиром.","Calculations use completed calendar days in the Europe/Kyiv time zone. Today is excluded. The 28-day indicators cover exactly the 28 completed days through yesterday. Rolling 7-, 30- and 90-day indicators are calculated only when data are available for the full window. A current incomplete period, where shown, is marked with a dashed segment."):tr("Базові показники та KPI використовують завершені календарні дні за часовою зоною Europe/Kyiv. KPI за 28 днів охоплюють рівно 28 завершених днів до вчора включно. У графіках з інтервалом «Останні 28 днів» показано 27 завершених днів і поточний неповний день пунктиром. На місячних і тижневих графіках перший неповний період не показується.","Base metrics and KPI cards use completed calendar days in the Europe/Kyiv time zone. The 28-day KPI cards cover exactly 28 completed days through yesterday. Charts using the Last 28 days interval show 27 completed days plus the current incomplete day as a dashed point. On monthly and weekly charts, the first incomplete period is not shown.");
}

function bind() {
  $("citySelect").addEventListener("change", renderCity);
  $("burdenYear")?.addEventListener("change", () => { renderAlertBurden($("citySelect").value); updateUrl(); });
  $("heavyDaysExcludeZero")?.addEventListener("change", () => { renderAlertBurden($("citySelect").value); updateUrl(); });
  $("daypartYear")?.addEventListener("change", () => { renderDaypart($("citySelect").value); updateUrl(); });
  $("cityPeriod").addEventListener("change", () => {
    resetCityDisplayRange();
    renderCity();
  });
  document.querySelectorAll(".time-of-day-range-option").forEach(option => {
    option.addEventListener("change", () => {
      if (!selectedTimeOfDayRanges().length) option.checked = true;
      updateTimeOfDayRangeSummary();
      renderTimeOfDay($("citySelect").value);
      updateUrl();
    });
  });
  $("timeOfDayBin")?.addEventListener("change", () => {
    renderTimeOfDay($("citySelect").value);
    updateUrl();
  });
  $("rolling7dYear")?.addEventListener("change", () => {
    applyRolling7dQuickRange($("citySelect").value);
    renderRolling7d($("citySelect").value);
    updateUrl();
  });
  $("allCitiesRange")?.addEventListener("change", () => {
    renderAllCitiesTable();
    updateUrl();
  });
  for (const id of ["casualtyYear", "casualtyInterval"]) {
    $(id)?.addEventListener("change", () => {
      renderCasualties($("citySelect").value);
      updateUrl();
    });
  }
  for (const id of ["compareA", "compareB", "compareC", "compareTimeOfDayRange", "compareTimeOfDayBin", "compareCasualtyInterval", "compareCasualtyYear"]) $(id).addEventListener("change", renderComparison);
  $("comparePeriod")?.addEventListener("change", () => {
    resetComparisonDisplayRange();
    renderComparison();
  });

  const bindRange = (fromId, toId, render, onEdit = null) => {
    for (const id of [fromId, toId]) {
      $(id)?.addEventListener("change", () => {
        const el = $(id);
        if (!normalizeDateInputElement(el)) return;
        normalizeDatePair(fromId, toId, id);
        if (onEdit) onEdit();
        render();
        updateUrl();
      });
      $(id)?.addEventListener("keydown", event => {
        if (event.key === "Enter") {
          event.preventDefault();
          event.currentTarget.blur();
        }
      });
    }
  };
  bindRange("cityDateFrom", "cityDateTo", renderCity);
  bindRange("rolling7dDateFrom", "rolling7dDateTo", () => renderRolling7d($("citySelect").value), () => {
    if ($("rolling7dYear")) $("rolling7dYear").value = "custom";
  });
  bindRange("compareDateFrom", "compareDateTo", renderComparison);
  bindRange("tableDateFrom", "tableDateTo", renderAllCitiesTable, () => {
    if ($("allCitiesRange")) $("allCitiesRange").value = "custom";
  });

  setupTableSorting();
  bindIntroTour();
  bindLanguageSwitch();
  $("copyLink").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      $("copyLink").textContent=tr("Скопійовано","Copied");
      setTimeout(()=>{$("copyLink").textContent=tr("Скопіювати посилання","Copy link");},1200);
    }catch{
      $("copyLink").textContent=tr("Не вдалося","Failed");
    }
  });
}

async function init() {
  state.features = await loadPreviewFeatures();
  applyPreviewFeatureVisibility();

  const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed to load live dashboard data: ${response.status}`);
  state.data = await response.json();

  try {
    const explorationResponse = await fetch(`${EXPLORATIONS_URL}?v=${Date.now()}`, { cache: "no-store" });
    if (explorationResponse.ok) {
      const explorationData = await explorationResponse.json();
      if (explorationData?.meta?.test_only && explorationData?.cities) state.explorations = explorationData;
    }
  } catch (err) {
    console.warn("Preview exploration data unavailable", err);
  }

  try {
    const threatResponse = await fetch(`${KYIV_THREAT_MIX_URL}?v=${Date.now()}`, { cache: "no-store" });
    if (threatResponse.ok) {
      const threatData = await threatResponse.json();
      if (Array.isArray(threatData?.rows)) state.kyivThreatMix = threatData;
    }
  } catch (err) {
    console.warn("Kyiv alert-cause data unavailable", err);
  }

  if (attackEventFeaturesEnabled()) {
    try {
      const explosionResponse = await fetch(`${EXPLOSION_LIVE_URL}?v=${Date.now()}`, { cache: "no-store" });
      if (explosionResponse.ok) {
        const explosionLive = await explosionResponse.json();
        if (explosionLive?.meta?.test_only && explosionLive?.cities) {
          state.data.explosion_metric_test = explosionLive;
        }
      }
    } catch (err) {
      console.warn("Explosion live data unavailable; using embedded preview snapshot", err);
    }
  } else {
    delete state.data.explosion_metric_test;
  }

  const keys = cityKeys();

  const defaults = ["kyiv", "kharkiv", "zaporizhzhia"].filter(k => keys.includes(k));
  while (defaults.length < 3 && keys[defaults.length]) defaults.push(keys[defaults.length]);

  const cityDefault = validParam("city", keys, defaults[0] || keys[0]);
  const periodDefault = validParam("period", ["daily28", "weekly", "rolling30", "rolling90", "rolling180", "calendarWeekly", "monthly"], "monthly");
  const aDefault = validParam("a", keys, defaults[0] || keys[0]);
  const bDefault = validParam("b", keys, defaults[1] || keys[0]);
  const cDefault = validOptionalParam("c", keys, defaults[2] || "");
  const compareDefault = validParam("compare", ["daily28", "weekly", "rolling30", "rolling90", "rolling180", "calendarWeekly", "monthly"], "monthly");
  const heatmapDefault = validMultiParam("tod", HEATMAP_RANGES, ["30d"]);
  const timeOfDayBinDefault = validParam("todbin", TIME_OF_DAY_BIN_MINUTES.map(String), "15");
  const compareTimeOfDayDefault = validParam("ctod", HEATMAP_RANGES, "30d");
  const compareTimeOfDayBinDefault = validParam("ctodbin", TIME_OF_DAY_BIN_MINUTES.map(String), "15");
  const casualtyIntervalDefault = validParam("casint", ["monthly", "yearly"], "monthly");
  const compareCasualtyIntervalDefault = validParam("ccasint", ["monthly", "yearly"], "monthly");
  const allCitiesRangeDefault = validParam("table", TABLE_RANGES, "30d");

  if ($("burdenYear")) $("burdenYear").dataset.requested = getParams().get("burdenyear") || "";
  if ($("daypartYear")) $("daypartYear").dataset.requested = getParams().get("daypartyear") || "";
  if ($("heavyDaysExcludeZero")) $("heavyDaysExcludeZero").checked = getParams().get("heavyexclude") === "1";

  fillSelect($("citySelect"), keys, cityDefault);
  fillSelect($("compareA"), keys, aDefault);
  fillSelect($("compareB"), keys, bDefault);
  fillSelect($("compareC"), keys, cDefault, true);
  $("cityPeriod").value = periodDefault;
  $("comparePeriod").value = compareDefault;
  setSelectedTimeOfDayRanges(heatmapDefault);
  if ($("timeOfDayBin")) $("timeOfDayBin").value = timeOfDayBinDefault;
  $("compareTimeOfDayRange").value = compareTimeOfDayDefault;
  if ($("compareTimeOfDayBin")) $("compareTimeOfDayBin").value = compareTimeOfDayBinDefault;
  if ($("casualtyInterval")) $("casualtyInterval").value = casualtyIntervalDefault;
  if ($("casualtyYear")) {
    $("casualtyYear").dataset.requested = getParams().get("casyear") || "all";
  }
  if ($("compareCasualtyInterval")) $("compareCasualtyInterval").value = compareCasualtyIntervalDefault;
  if ($("compareCasualtyYear")) {
    $("compareCasualtyYear").dataset.requested = getParams().get("ccasyear") || "all";
  }
  $("allCitiesRange").value = allCitiesRangeDefault;

  for (const [id, param] of [
    ["cityDateFrom","cityfrom"],["cityDateTo","cityto"],
    ["rolling7dDateFrom","r7from"],["rolling7dDateTo","r7to"],
    ["compareDateFrom","cmpfrom"],["compareDateTo","cmpto"],
    ["tableDateFrom","tablefrom"],["tableDateTo","tableto"]
  ]) setDateInputFromParam(id, param);
  if (($("tableDateFrom")?.value || $("tableDateTo")?.value) && !getParams().has("table")) {
    $("allCitiesRange").value = "custom";
  }

  renderGeneratedAt();

  renderDatasetSummary();
  renderFreshness();
  renderMethodology();
  bind();
  renderCity();
  renderComparison();
  renderAllCitiesTable();
  setupCsvExports();
  updateUrl();
  maybeStartIntroTour();
}

applyStaticLanguage();

init().catch(err=>{
  console.error(err);
  $("freshnessBanner").textContent=tr(`Не вдалося завантажити сайт: ${err.message}`,`Failed to load the site: ${err.message}`);
  $("freshnessBanner").classList.remove("hidden");
});

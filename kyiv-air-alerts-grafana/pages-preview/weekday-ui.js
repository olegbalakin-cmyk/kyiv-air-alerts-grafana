/* Weekday charts, read-only: uses the current verified historical_daily_kpi. */
(function (root) {
  "use strict";
  let activeIndex=null, activeKey="", activeLanguage="uk", initialized=false;
  let dayparts=null,daypartsLoadStarted=false,daypartsLoadFailed=false;
  let currentDerived=null;
  const $=id=>document.getElementById(id);
  const tr=(uk,en)=>activeLanguage==="en"?en:uk;
  const dayNames={
    uk:["Понеділок","Вівторок","Середа","Четвер","П’ятниця","Субота","Неділя"],
    en:["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
  };
  let charts={};
  const fmt=(n,decimals=1)=>Number(n).toLocaleString(activeLanguage==="en"?"en-GB":"uk-UA",{maximumFractionDigits:decimals,minimumFractionDigits:decimals});

  function dateValue(value) {
    const raw=String(value||"").trim();
    const ymd=/^\d{4}-\d{2}-\d{2}$/.test(raw)?raw:null;
    const local=/^(\d{2})\.(\d{2})\.(\d{4})$/.exec(raw);
    const date=ymd||(local?local[3]+"-"+local[2]+"-"+local[1]:null);
    if(!date)return "";
    const parsed=Date.parse(date+"T00:00:00Z");
    return Number.isFinite(parsed)&&new Date(parsed).toISOString().slice(0,10)===date?date:"";
  }
  function clamp(value,min,max){return value<min?min:value>max?max:value;}
  function syncPicker(id){
    const input=$(id),native=input?.parentElement?.querySelector(".date-picker-native");
    if(!input||!native)return;
    native.min=activeIndex.start;
    native.max=activeIndex.end;
    native.value=dateValue(input.value);
  }
  function setInput(id,value){
    $(id).value=value;
    syncPicker(id);
  }
  function clearCharts(){
    for(const id of Object.keys(charts)){charts[id].destroy();delete charts[id];}
  }
  function syncLinks(){
    const url=new URL(location.href);
    url.searchParams.set("weekrange",$("weekdayRange").value);
    if($("weekdayDateFrom").value)url.searchParams.set("weekfrom",$("weekdayDateFrom").value);
    if($("weekdayDateTo").value)url.searchParams.set("weekto",$("weekdayDateTo").value);
    url.searchParams.set("weeksplit",$("weekdaySplitEnabled").checked?"1":"0");
    url.searchParams.set("weekmode",$("weekdaySplitMode").value);
    history.replaceState(null,"",url.pathname+url.search+url.hash);
  }
  function draw(id,values,label,color,stats,isHours){
    charts[id]?.destroy();
    const bins=stats.weekdays;
    charts[id]=new Chart($(id),{
      type:"bar",
      data:{
        labels:dayNames[activeLanguage],
        datasets:[{label,data:values,backgroundColor:color+"bb",borderColor:color,borderWidth:1}]
      },
      options:{
        responsive:true,maintainAspectRatio:false,animation:false,
        plugins:{
          legend:{display:false},
          tooltip:{callbacks:{
            label:ctx=>{
              if(ctx.parsed.y===null)return tr("Немає днів у вибірці","No observed days");
              return label+": "+fmt(ctx.parsed.y,2);
            },
            afterLabel:ctx=>{
              const b=bins[ctx.dataIndex];
              return isHours
                ? [tr("Усього годин","Total hours")+": "+fmt(b.seconds/3600,2),tr("Днів","Days")+": "+b.days]
                : [tr("Почалося тривог","Alerts started")+": "+b.starts,tr("Днів","Days")+": "+b.days];
            }
          }}
        },
        scales:{
          x:{ticks:{color:"#b8c4cf",autoSkip:false,maxRotation:35},grid:{color:"rgba(148,163,184,.16)"}},
          y:{beginAtZero:true,ticks:{color:"#b8c4cf"},grid:{color:"rgba(148,163,184,.16)"},
            title:{display:true,text:label,color:"#b8c4cf"}}
        }
      }
    });
  }

  function selectedSplit(stats){
    if(!$("weekdaySplitEnabled").checked||!activeIndex)return null;
    // Live data arrive in the existing four-hour Git-only site_derived.json
    // update, not in the immutable Netlify deployment. Reject other generations.
    const ctx=currentDerived;
    const verified=root.WeekdayDistribution.splitDerivedHours(activeIndex,ctx,
      stats.from,stats.to,$("weekdaySplitMode").value);
    if(verified)return verified;
    // Do not fall back to an old static snapshot after a verified dynamic
    // release has loaded: a failed parity/release check must remain blocked.
    if(ctx?.city?.daily)return null;
    // Temporary preview-proven initial fallback. Never use an older static
    // snapshot beyond its last complete day (splitHours enforces this).
    const fallback=dayparts?.cities?.[activeKey];
    return root.WeekdayDistribution.splitHours(activeIndex,
      fallback?{...fallback,meta:dayparts.meta,schema:dayparts.schema,
        max_day:dayparts.meta.max_complete_day}:null,
      stats.from,stats.to,$("weekdaySplitMode").value);
  }
  // Color key identifies the bands only. Each bar's actual breakdown is
  // available on hover/tap; showing global shares here confuses users.
  function updateShareLegend(split,labels,colors){
    const legend=$("weekdayShareLegend");
    if(!legend)return;
    legend.replaceChildren();
    legend.hidden=!split;
    if(!split)return;
    labels.forEach((name,i)=>{
      const item=document.createElement("span");
      item.className="weekday-share-item";
      const swatch=document.createElement("span");
      swatch.className="weekday-share-swatch";
      swatch.style.backgroundColor=colors[i];
      swatch.setAttribute("aria-hidden","true");
      const label=document.createElement("span");
      label.textContent=name;
      item.append(swatch,label);
      legend.append(item);
    });
  }
  function drawSplitHours(stats,split){
    const id="weekdayHoursChart";
    charts[id]?.destroy();
    const four=split.mode==="four";
    const labels=four?["00–06","06–12","12–18","18–24"]:
      [tr("День (09–18)","Day (09–18)"),tr("Вечір і ніч (18–09)","Evening & night (18–09)")];
    const colors=four?["#62a0ea","#8ff0a4","#f8e45c","#ff9f43"]:["#f8e45c","#62a0ea"];
    updateShareLegend(split,labels,colors);
    charts[id]=new Chart($(id),{
      type:"bar",
      data:{labels:dayNames[activeLanguage],datasets:labels.map((label,i)=>({
        label,data:split.weekdays.map(day=>day.averageParts[i]),
        backgroundColor:colors[i]+"bb",borderColor:colors[i],borderWidth:1,stack:"time"
      }))},
      options:{
        responsive:true,maintainAspectRatio:false,animation:false,
        interaction:{mode:"index",intersect:false},
        plugins:{
          legend:{display:false},
          tooltip:{callbacks:{
            title:items=>items.length?dayNames[activeLanguage][items[0].dataIndex]:"",
            label:ctx=>{
              const bar=root.WeekdayDistribution.weekdayBarShares(split,ctx.dataIndex);
              const part=bar?.parts[ctx.datasetIndex];
              return ctx.dataset.label+": "+fmt(part?.averageHours||0,2)+
                tr(" год/день"," hr/day")+" · "+fmt(part?.percent||0,1)+"%";
            },
            footer:items=>{
              if(!items.length)return "";
              const bar=root.WeekdayDistribution.weekdayBarShares(split,items[0].dataIndex);
              if(!bar)return "";
              return [
                tr("Разом у стовпчику","Bar total")+": "+fmt(bar.averageHours,2)+
                  tr(" год/день"," hr/day")+" · "+(bar.seconds>0?"100%":"0%"),
                tr("Днів у вибірці","Observed days")+": "+bar.days
              ];
            }
          }}
        },
        scales:{
          x:{stacked:true,ticks:{color:"#b8c4cf",autoSkip:false,maxRotation:35},grid:{color:"rgba(148,163,184,.16)"}},
          y:{stacked:true,beginAtZero:true,ticks:{color:"#b8c4cf"},grid:{color:"rgba(148,163,184,.16)"},
            title:{display:true,text:tr("Годин/день","Hours/day"),color:"#b8c4cf"}}
        }
      }
    });
  }
  async function loadDayparts(){
    if(daypartsLoadStarted)return;
    daypartsLoadStarted=true;
    try{
      const response=await fetch("weekday-dayparts.json?v=20261119-bands-test2",{cache:"no-store"});
      if(!response.ok)throw Error("weekday snapshot HTTP "+response.status);
      const value=await response.json();
      if(value?.schema!=="weekday-dayparts-test-v1" ||
         value?.meta?.timezone!=="Europe/Kyiv" ||
         value?.meta?.test_only!==true ||
         value?.meta?.city_count!==23 ||
         !value?.cities || Object.keys(value.cities).length!==23)throw Error("Invalid weekday snapshot contract");
      dayparts=value;
    }catch(error){daypartsLoadFailed=true;console.warn("Weekday daypart preview not available",error);}
    paint();
  }
  function downloadCsv(stats){
    const lines=[["weekday","days","alerts_started","actual_alert_hours","avg_alerts_per_day","avg_actual_hours_per_day"].join(",")];
    stats.weekdays.forEach((bin,i)=>{
      lines.push([dayNames.en[i],bin.days,bin.starts,(bin.seconds/3600).toFixed(6),
        bin.averageStarts===null?"":bin.averageStarts.toFixed(6),
        bin.averageHours===null?"":bin.averageHours.toFixed(6)].join(","));
    });
    const blob=new Blob(["\ufeff"+lines.join("\r\n")+"\r\n"],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=url;
    a.download="air-alerts_"+activeKey+"_weekdays_"+stats.from+"_"+stats.to+".csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  function localize(){
    const section=$("weekdaySection"),heading=section.querySelector(".section-heading");
    const head=heading.querySelectorAll(".eyebrow,h2,p");
    head[0].textContent=tr("Дні тижня","Weekdays");
    head[1].textContent=tr("Тривоги за днями тижня","Air alerts by weekday");
    head[2].textContent=tr(
      "Кількість — за днем початку тривоги; час — тільки фактична частина в межах календарного дня Europe/Kyiv.",
      "Counts use the alert start date; hours include only time within each Europe/Kyiv calendar day."
    );
    section.querySelector('label[for="weekdayRange"]').textContent=tr("Період","Period");
    section.querySelector(".weekday-split-check span").textContent=tr("Розподілити за частинами доби","Split by time of day");
    $("weekdayShareLegend")?.setAttribute("aria-label",tr("Кольори частин доби","Time-band colors"));
    section.querySelector('label[for="weekdaySplitMode"]').textContent=tr("Розподіл","Grouping");
    $("weekdaySplitMode").querySelector('option[value="four"]').textContent=tr("4 частини доби","Four time bands");
    $("weekdaySplitMode").querySelector('option[value="daynight"]').textContent=tr("День / вечір і ніч","Day / evening & night");
    $("weekdaySplitMode").setAttribute("aria-label",tr("Розподіл часу за частинами доби","Time of day grouping"));
    const options=[
      ["28d","Останні 28 днів","Last 28 days"],
      ["90d","Останні 90 днів","Last 90 days"],
      ["180d","Останні 180 днів","Last 180 days"],
      ["year","Поточний рік","Current year"],
      ["all","За весь час","All time"],
      ["custom","Довільний","Custom"]
    ];
    options.forEach(([value,uk,en])=>{$("weekdayRange").querySelector('option[value="'+value+'"]').textContent=tr(uk,en);});
    for(const [id,uk,en] of [["weekdayDateFrom","Від","From"],["weekdayDateTo","До","To"]]){
      section.querySelector('label[for="'+id+'"]').textContent=tr(uk,en);
    }
    for(const native of section.querySelectorAll(".date-picker-native")){
      native.setAttribute("aria-label",native.dataset.dateFor.endsWith("From")
        ?tr("Обрати початкову дату","Choose start date")
        :tr("Обрати кінцеву дату","Choose end date"));
    }
    const cards=section.querySelectorAll(".chart-card");
    cards[0].querySelector("h3").textContent=tr("Кількість тривог за днем початку","Alerts by start weekday");
    cards[0].querySelector(".chart-subtitle").textContent=tr(
      "Середня кількість нових тривог за один відповідний день тижня.",
      "Average alerts started per occurrence of each weekday."
    );
    cards[1].querySelector("h3").textContent=tr("Фактичний час під тривогою","Actual time under alert");
    cards[1].querySelector(".chart-subtitle").textContent=tr(
      "Середній час за календарний день тижня. Переходи через північ розрізані.",
      "Average hours per calendar weekday; midnight-crossing alerts are split."
    );
  }
  function paint(){
    if(!activeIndex||!root.WeekdayDistribution?.validIndex(activeIndex)){
      clearCharts();
      updateShareLegend(null,[],[]);
      $("weekdayMeta").textContent=tr(
        "Перевірені щоденні дані для цього міста наразі недоступні.",
        "Verified daily data for this city are currently unavailable."
      );
      return;
    }
    const api=root.WeekdayDistribution, range=$("weekdayRange").value;
    const preset=api.preset(activeIndex,range);
    let from=range==="custom"?dateValue($("weekdayDateFrom").value):preset.from;
    let to=range==="custom"?dateValue($("weekdayDateTo").value):preset.to;
    if(!from)from=preset.from;
    if(!to)to=preset.to;
    from=clamp(from,activeIndex.start,activeIndex.end);
    to=clamp(to,activeIndex.start,activeIndex.end);
    if(from>to)to=from;
    setInput("weekdayDateFrom",from);
    setInput("weekdayDateTo",to);
    const stats=api.summarize(activeIndex,from,to);
    if(!stats){clearCharts();$("weekdayMeta").textContent=tr("Немає даних.","No data.");return;}
    const sums=stats.weekdays.reduce((acc,bin)=>({
      starts:acc.starts+bin.starts,seconds:acc.seconds+bin.seconds
    }),{starts:0,seconds:0});
    $("weekdayMeta").textContent=tr(
      stats.from+" — "+stats.to+" · "+stats.calendarDays+" завершених днів · "+sums.starts+" нових тривог · "+fmt(sums.seconds/3600,1)+" год фактично під тривогою. Стовпчики — середнє на один відповідний день тижня.",
      stats.from+" — "+stats.to+" · "+stats.calendarDays+" completed days · "+sums.starts+" alerts started · "+fmt(sums.seconds/3600,1)+" actual hours under alert. Bars show averages per weekday occurrence."
    );
    draw("weekdayStartsChart",stats.weekdays.map(x=>x.averageStarts),tr("Тривог/день","Alerts/day"),"#62a0ea",stats,false);

    const enabled=$("weekdaySplitEnabled").checked;
    $("weekdaySplitMode").disabled=!enabled;
    const split=selectedSplit(stats);
    if(enabled && split){
      drawSplitHours(stats,split);
      $("weekdaySplitStatus").textContent=tr(
        "Точний розподіл (Europe/Kyiv). Наведіть або натисніть на стовпчик: години та частки саме цього дня тижня.",
        "Exact time bands (Europe/Kyiv). Hover or tap a bar to see hours and shares for that weekday.");
    }else{
      updateShareLegend(null,[],[]);
      draw("weekdayHoursChart",stats.weekdays.map(x=>x.averageHours),tr("Годин/день","Hours/day"),"#8ff0a4",stats,true);
      $("weekdaySplitStatus").textContent=!enabled?"":daypartsLoadFailed
        ?tr("Розподіл недоступний: немає перевірених часових інтервалів для цього зрізу.","Split unavailable: no verified time-band intervals for this data generation.")
        :!dayparts
          ?tr("Завантаження точного розподілу…","Loading exact time bands…")
          :tr("Розподіл недоступний для цього періоду: недостатньо підтверджених або узгоджених інтервалів. Показано загальний час.",
            "Time-band split unavailable for this range: interval data are missing or do not match verified totals. Showing total hours.");
    }

    const download=$("weekdayCsv");
    if(download)download.onclick=()=>downloadCsv(stats);
  }
  function install(){
    if(initialized)return;
    initialized=true;
    const params=new URLSearchParams(location.search);
    const selected=params.get("weekrange")||"28d";
    $("weekdayRange").value=["28d","90d","180d","year","all","custom"].includes(selected)?selected:"28d";
    if(params.get("weekfrom"))$("weekdayDateFrom").value=params.get("weekfrom");
    if(params.get("weekto"))$("weekdayDateTo").value=params.get("weekto");
    $("weekdayRange").addEventListener("change",()=>{paint();syncLinks();});
    $("weekdaySplitEnabled").checked=params.get("weeksplit")==="1";
    $("weekdaySplitMode").value=params.get("weekmode")==="daynight"?"daynight":"four";
    $("weekdaySplitEnabled").addEventListener("change",()=>{paint();syncLinks();});
    $("weekdaySplitMode").addEventListener("change",()=>{paint();syncLinks();});
    loadDayparts();
    for(const id of ["weekdayDateFrom","weekdayDateTo"]){
      const el=$(id);
      el.addEventListener("change",()=>{
        const normalized=dateValue(el.value);
        if(!normalized){el.setCustomValidity(tr("Некоректна дата","Invalid date"));el.reportValidity();return;}
        el.setCustomValidity("");
        el.value=normalized;
        const first=dateValue($("weekdayDateFrom").value),last=dateValue($("weekdayDateTo").value);
        if(first&&last&&first>last){
          if(id==="weekdayDateFrom")$("weekdayDateTo").value=first;
          else $("weekdayDateFrom").value=last;
        }
        $("weekdayRange").value="custom";
        paint();syncLinks();
      });
      el.addEventListener("keydown",event=>{
        if(event.key==="Enter"){event.preventDefault();el.blur();}
      });
      const native=el.parentElement.querySelector(".date-picker-native");
      native.addEventListener("change",()=>{
        if(!native.value)return;
        el.value=native.value;
        el.dispatchEvent(new Event("change",{bubbles:true}));
      });
    }
    const firstCard=$("weekdayStartsChart").closest(".chart-card");
    const row=document.createElement("div");
    row.className="chart-export-row weekday-export-row";
    const button=document.createElement("button");
    button.id="weekdayCsv";
    button.type="button";
    button.className="csv-export-button";
    button.innerHTML='<span>CSV</span>';
    button.title=tr("Завантажити статистику за днями тижня","Download weekday statistics");
    row.appendChild(button);
    firstCard.insertBefore(row,firstCard.querySelector(".chart-wrap"));
  }
  root.WeekdayUI={
    render(index,key,language,derived){
      activeIndex=index;
      activeKey=key;
      activeLanguage=language==="en"?"en":"uk";
      currentDerived=derived||null;
      install();
      localize();
      paint();
    }
  };
})(window);

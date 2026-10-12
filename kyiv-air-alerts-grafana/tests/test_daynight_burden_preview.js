#!/usr/bin/env node
"use strict";
const assert=require("node:assert/strict"), fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const script=fs.readFileSync(path.join(__dirname,"../pages-preview/app.js"),"utf8");
const html=fs.readFileSync(path.join(__dirname,"../pages-preview/index.html"),"utf8");
const a=script.indexOf("function daypartBreakdown("), b=script.indexOf("\nfunction renderDaypart(",a);
assert(a>=0&&b>a,"Helper missing");
const breakdown=vm.runInNewContext(script.slice(a,b)+"\ndaypartBreakdown;",{
 TIME_PROFILE_COLORS:["#111","#222","#333","#444","#555"],tr:(uk,en)=>uk
});
const row={time_band_shares:{"00_06":10,"06_12":20,"12_18":30,"18_24":40},time_day_night_shares:{day:55.5,evening_night:44.5}};
const n=x=>JSON.parse(JSON.stringify(x));
assert.deepEqual(n(breakdown([row],"four")).map(x=>x.data[0]),[10,20,30,40]);
assert.deepEqual(n(breakdown([row],"daynight")).map(x=>x.data[0]),[55.5,44.5]);
assert.deepEqual(n(breakdown([row],"daynight")).map(x=>x.label),["День (09–18)","Вечір і ніч (18–09)"]);
assert.deepEqual(n(breakdown([{}],"daynight")).map(x=>x.data[0]),[null,null],"Missing is not zero");
assert(html.includes('id="daypartMode"'),"Missing switch");
assert(script.includes('const year = explorationYearOptions("burdenYear", key, true);'),"All time unwired");
assert(script.includes('value="all">${tr("За весь час","All time")}'),"All time option missing");
assert(script.includes('params.set("daypartmode"'),"Day/night state not shared in URL");
console.log("PASS: frontend 09-18 mode, source data not approximated, all-time selection");

const assert=require("node:assert/strict"),s=require("../pages-preview/chart-share.js");
const ids=["cityIntensityChart","compareCumulativeHoursChart"];
const c={data:{datasets:[{},{},{}]},hidden:[false,true,false],isDatasetVisible(i){return !this.hidden[i]},setDatasetVisibility(i,v){this.hidden[i]=!v},update(m){this.updated=m}};
const original="https://example.test/?lang=uk&city=kyiv&compare=monthly&a=kyiv&b=kharkiv";
const url=s.makeShareUrl(original,ids[1],c);
assert.equal(new URL(url).search,new URL(original).search);
assert.equal(new URL(url).hash,"#chart-compareCumulativeHoursChart.101");
assert.deepEqual(s.parseSharedView(new URL(url).hash,ids),{chartId:ids[1],visibility:"101"});
assert.equal(s.parseSharedView("#chart-otherChart",ids),null);
assert.equal(s.restoreVisibility(c,"110"),true);
assert.deepEqual(c.hidden,[false,false,true]);
assert.equal(s.restoreVisibility(c,"01"),false);
assert.equal(s.visibilityBits(c),"110");
assert.throws(()=>s.makeShareUrl(original,"bad/id",c));
console.log("chart share unit checks PASS");



const calls = { text: [], drawn: 0, saves: [], strokes: [] };
const sourceCanvas = { width: 1200, height: 560 };
const mockSelections = {
  citySelect: "Київ", cityPeriod: "Місяці",
  compareA: "Київ", compareB: "Харків", compareC: "",
  comparePeriod: "Місяці", compareDateFrom: "2025-01-01", compareDateTo: "2025-12-31"
};
const drawContext = {
  fillRect(){}, fillText(v){calls.text.push(v)},
  save(){},restore(){},translate(){},scale(){},beginPath(){},roundRect(){},rect(){},fill(){},arc(){},moveTo(){},lineTo(){},bezierCurveTo(){},closePath(){},stroke(){calls.strokes.push(this.strokeStyle)},
  drawImage(source, x, y, w, h){
    assert.equal(source, sourceCanvas);
    assert.ok(w > 0 && h > 0);
    calls.drawn++;
  },
  measureText(v){ return { width: v.length * 15 } }
};
const encoded = "data:image/png;base64," + Buffer.from([137,80,78,71,13,10,26,10]).toString("base64");
global.document = {
  getElementById(id) {
    if (id === "compareCumulativeHoursChart") return sourceCanvas;
    if (Object.hasOwn(mockSelections,id)) {
      const v=mockSelections[id];
      return { value:v, tagName:"SELECT", selectedOptions:[{textContent:v}] };
    }
    return null;
  },
  querySelectorAll(){return []},
  createElement(tag) {
    assert.equal(tag,"canvas");
    const canvas={width:0,height:0};
    canvas.getContext=()=>drawContext;
    canvas.toDataURL=(mime)=>{
      assert.equal(mime,"image/png");
      return encoded;
    };
    return canvas;
  }
};
global.location={hostname:"test-preview.example"};
global.File=class {
  constructor(chunks,name,metadata){
    this.chunks=chunks;this.name=name;this.type=metadata.type;
  }
};
global.atob=(raw)=>Buffer.from(raw,"base64").toString("binary");
const card={
  querySelector(){return {textContent:"Накопичений час під тривогою"}},
  closest(){return null}
};
const image=s.renderChartPng("compareCumulativeHoursChart",card);
assert.equal(image.width,1440);
assert.ok(image.height > 400);
assert.match(image.title,/Накопичений час/);
assert.match(image.caption,/Київ/);
assert.match(image.caption,/Харків/);
assert.match(image.caption,/2025-01-01/);
assert.equal(image.dataUrl,encoded);
assert.equal(calls.drawn,1);
assert.deepEqual(calls.strokes.slice(0,3),["#F6F8FC","#FFD000","#007BFF"],"approved bell + exactly two colored waves");
assert.ok(calls.text.some(t=>t.includes("Накопичений час")));
assert.ok(calls.text.some(t=>t.includes("Знімок")));
const file=s.pngFile(image.dataUrl,image.filename);
assert.equal(file.type,"image/png");
assert.match(file.name,/air-alerts_comparecumulativehours_/);
assert.deepEqual([...file.chunks[0]],[137,80,78,71,13,10,26,10]);
assert.throws(()=>s.pngFile("data:text/plain;base64,YQ==","wrong.png"));
console.log("chart image render and PNG packaging checks PASS");


// One visible per-chart share button: image sharing, not a duplicate link action.
const actionButtons = [];
const createElementOriginal = global.document.createElement;
global.document.createElement = function(tag) {
  if (tag !== "button") return createElementOriginal(tag);
  const label = { textContent: "" };
  const button = {
    dataset: {}, attributes: {}, title: "",
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(name, handler) { this.handler = handler; },
    querySelector(selector) { return selector === ".chart-share-label" ? label : null; },
    set innerHTML(value) { this.markup = value; }
  };
  actionButtons.push(button);
  return button;
};
const exportRow = {
  children: [],
  appendChild(button) { this.children.push(button); },
  querySelector(selector) {
    if (selector === '[data-share-image="compareCumulativeHoursChart"]')
      return this.children.find(b => b.dataset.shareImage === "compareCumulativeHoursChart") || null;
    if (selector === '[data-embed-chart="compareCumulativeHoursChart"]')
      return this.children.find(b => b.dataset.embedChart === "compareCumulativeHoursChart") || null;
    return null;
  }
};
const chartCard = {
  classList: { contains: () => false },
  closest() { return null; },
  querySelector(selector) {
    if (selector === '[data-csv-chart="compareCumulativeHoursChart"]') return exportRow;
    if (selector === "h3") return { textContent: "Накопичений час під тривогою" };
    return null;
  }
};
const chartWrap = {};
sourceCanvas.closest = (selector) =>
  selector === ".chart-card" ? chartCard :
  selector === ".chart-wrap" ? chartWrap : null;
s.setup({
  chartIds: ["compareCumulativeHoursChart"],
  getChart: () => c,
  language: () => "uk",
  syncUrl: () => {}
});
assert.equal(exportRow.children.length, 2);
assert.equal(exportRow.children[0].className, "csv-export-button chart-image-button");
assert.equal(exportRow.children[0].dataset.shareImage, "compareCumulativeHoursChart");
assert.equal(exportRow.children[0].querySelector(".chart-share-label").textContent, "Поділитися");
const shareIcon = exportRow.children[0].markup;
assert.match(shareIcon, /<svg aria-hidden="true" viewBox="0 0 24 24">/);
assert.equal((shareIcon.match(/<circle\b/g) || []).length, 3, "share icon must have three connected points");
assert.equal((shareIcon.match(/<line\b/g) || []).length, 2, "share icon must have two connections");
assert.ok(!shareIcon.includes("<rect"), "old image icon must be absent");
assert.match(exportRow.children[0].attributes["aria-label"], /зображенням/);
assert.equal(typeof exportRow.children[0].handler, "function");
s.setup({
  chartIds: ["compareCumulativeHoursChart"],
  getChart: () => c,
  language: () => "uk",
  syncUrl: () => {}
});
assert.equal(exportRow.children.length, 2, "Repeated setup must not add duplicate share/embed buttons");
assert.equal(actionButtons.length, 2);
assert.equal(exportRow.children[1].className, "csv-export-button chart-embed-button");
assert.equal(exportRow.children[1].dataset.embedChart, "compareCumulativeHoursChart");
assert.equal(exportRow.children[1].querySelector(".chart-share-label").textContent, "Вбудувати");
assert.equal(typeof exportRow.children[1].handler, "function");
console.log("single PNG share action + embed code action UI contract PASS");


// Embed URLs preserve the complete filter query and visible-series hash.
const exampleHref = "https://chart-share-test-20261019--ukraine-air-alerts.netlify.app/?" +
  "lang=uk&city=kyiv&period=monthly&a=kyiv&b=kharkiv&compare=monthly" +
  "&cmpfrom=2025-01-01&cmpto=2025-12-31";
const embedUrl = s.makeEmbedUrl(exampleHref, "compareCumulativeHoursChart", c);
const embedParsed = new URL(embedUrl);
assert.equal(embedParsed.searchParams.get("embed"), "compareCumulativeHoursChart");
assert.equal(embedParsed.searchParams.get("cmpfrom"), "2025-01-01");
assert.equal(embedParsed.searchParams.get("cmpto"), "2025-12-31");
assert.equal(embedParsed.searchParams.get("a"), "kyiv");
assert.equal(embedParsed.searchParams.get("b"), "kharkiv");
assert.equal(embedParsed.hash, "#chart-compareCumulativeHoursChart.110");

const embedHtml = s.makeEmbedHtml(exampleHref, "compareCumulativeHoursChart", c,
  'Час під тривогою <Kyiv> "2025"');
assert.match(embedHtml, /^<iframe src="https:\/\//);
assert.match(embedHtml, /&amp;embed=compareCumulativeHoursChart/);
assert.match(embedHtml, /title="Час під тривогою &lt;Kyiv&gt; &quot;2025&quot;"/);
assert.match(embedHtml, /width="100%" height="700"/);
assert.match(embedHtml, /referrerpolicy="strict-origin-when-cross-origin"/);
assert.ok(!embedHtml.includes('title="Час під тривогою <Kyiv>'));
assert.throws(() => s.makeEmbedUrl(exampleHref, "invalid/id", c));
assert.equal(embedHtml.match(/<iframe/g).length, 1);

// Embedded mode uses the actual chart card, not a clone or screenshot.
const created = [];
function makeNode(tag) {
  const node = {
    tag, children: [], attributes: {}, className: "", textContent: "",
    appendChild(child) { this.children.push(child); return child; },
    setAttribute(key,val) { this.attributes[key]=val; },
    classList: { contains(){return false;} }
  };
  created.push(node);
  return node;
}
const mainNode = makeNode("main");
const bodyClasses = [];
global.document.querySelector = selector => selector === "main" ? mainNode : null;
global.document.body = { classList: { add(cls) { bodyClasses.push(cls); } } };
global.document.createElement = tag => ["section","header","h2","p","footer","a","span","img","strong"].includes(tag)
  ? makeNode(tag) : createElementOriginal(tag);
global.location = { hostname: "chart-share-test-20261019--ukraine-air-alerts.netlify.app",
  href: embedUrl, hash: embedParsed.hash };
let resized=0;
c.resize = function() { resized++; };
global.requestAnimationFrame = function(callback) {callback();};
assert.equal(s.currentEmbedId(), "compareCumulativeHoursChart");
assert.equal(s.activateEmbed(), true);
assert.deepEqual(bodyClasses, ["embed-mode"]);
assert.equal(mainNode.children.length, 1);
const section = mainNode.children[0];
assert.equal(section.className, "embed-container");
assert.equal(section.children[1], chartCard, "Must move existing chart card");
assert.equal(resized, 1, "Chart must resize after relocation");
assert.equal(section.children[0].children[0].textContent, "Накопичений час під тривогою");
assert.match(section.children[0].children[1].textContent, /Київ/);
const footer = section.children[2];
assert.equal(footer.children[0].tag, "a");
assert.equal(footer.children[0].className, "embed-brand-link");
assert.match(footer.children[0].children[0].src, /^brand-mark\.svg\?v=20261019-logo12-1$/);
assert.equal(footer.children[0].children[1].children[0].textContent, "Повітряні тривоги");
assert.match(footer.children[0].children[1].children[1].textContent, /netlify\.app/);
assert.equal(footer.children[1].target, "_blank");
assert.equal(new URL(footer.children[1].href).searchParams.has("embed"), false);
assert.equal(new URL(footer.children[1].href).hash, embedParsed.hash);

global.location.href = "https://example.test/?embed=notAllowedChart";
assert.equal(s.currentEmbedId(), null);
console.log("embed URL HTML escaping, exact-state restoration, iframe DOM relocation checks PASS");
assert.ok(calls.text.some(v => String(v).includes("https://test-preview.example/")), "PNG must display readable source URL");
assert.ok(drawContext.stroke, "logo vector support must be present");
console.log("logo branding/source URL PNG and linked embed assertions PASS");

assert.ok(calls.text.some(t=>t.includes("https://test-preview.example/")), "PNG needs readable source link");
console.log("brand mark and source URL contract PASS");

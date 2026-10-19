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



const calls = { text: [], drawn: 0, saves: [] };
const sourceCanvas = { width: 1200, height: 560 };
const mockSelections = {
  citySelect: "Київ", cityPeriod: "Місяці",
  compareA: "Київ", compareB: "Харків", compareC: "",
  comparePeriod: "Місяці", compareDateFrom: "2025-01-01", compareDateTo: "2025-12-31"
};
const drawContext = {
  fillRect(){}, fillText(v){calls.text.push(v)},
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
    return selector === '[data-share-image="compareCumulativeHoursChart"]'
      ? this.children.find(b => b.dataset.shareImage === "compareCumulativeHoursChart") || null
      : null;
  }
};
const chartCard = { querySelector(selector) {
  return selector === '[data-csv-chart="compareCumulativeHoursChart"]' ? exportRow : null;
}};
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
assert.equal(exportRow.children.length, 1);
assert.equal(exportRow.children[0].className, "csv-export-button chart-image-button");
assert.equal(exportRow.children[0].dataset.shareImage, "compareCumulativeHoursChart");
assert.equal(exportRow.children[0].querySelector(".chart-share-label").textContent, "Поділитися");
assert.match(exportRow.children[0].attributes["aria-label"], /зображенням/);
assert.equal(typeof exportRow.children[0].handler, "function");
s.setup({
  chartIds: ["compareCumulativeHoursChart"],
  getChart: () => c,
  language: () => "uk",
  syncUrl: () => {}
});
assert.equal(exportRow.children.length, 1, "Repeated setup must not add another share button");
assert.equal(actionButtons.length, 1);
console.log("single PNG share button UI contract PASS");

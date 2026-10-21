const assert=require("node:assert/strict");
const api=require("../pages-preview/kpi-range.js");
const idx={status:"verified",start:"2026-10-01",end:"2026-10-05",counts:[3,13,0,13,2]};
assert.deepEqual(api.historicalMax(idx,"2026-10-01","2026-10-05"),{max:13,dates:["2026-10-02","2026-10-04"]});
assert.deepEqual(api.historicalMax(idx,"2026-10-03","2026-10-03"),{max:0,dates:["2026-10-03"]});
for(const a of [
[{...idx,status:"unverified"},"2026-10-01","2026-10-05"],
[idx,"2026-09-30","2026-10-05"],[idx,"2026-10-01","2026-10-06"],
[{...idx,counts:[3,13,0,13]},"2026-10-01","2026-10-05"],
[{...idx,counts:[3,13,-1,13,2]},"2026-10-01","2026-10-05"]
])assert.equal(api.historicalMax(...a),null);
console.log("PASS history window, tie dates, zero dates and strict coverage");

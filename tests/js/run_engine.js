// Runs DentIndices browser-engine calls for the Python parity tests.
// Usage: node run_engine.js < cases.json   (cases: [{fn, args}] -> prints [{ok, result} | {ok:false, error}])
"use strict";
const path = require("path");
const fs = require("fs");
require(path.join(__dirname, "..", "..", "docs", "indices-data.js"));
const DI = require(path.join(__dirname, "..", "..", "docs", "dentindices.js"));
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
const out = cases.map((c) => {
  try {
    const fn = DI[c.fn];
    if (typeof fn !== "function") throw new Error("no function " + c.fn);
    let r = fn(c.args);
    if (c.fn === "caries_experience") r = { permanent: r.permanent, primary: r.primary };
    return { ok: true, result: r };
  } catch (e) {
    return { ok: false, error: e.message, name: e.name };
  }
});
process.stdout.write(JSON.stringify(out));

/*! DentIndices browser engine — mirrors the Python package (dentindices) rule for rule.
 *  Rules and thresholds come from the shared registry (indices-data.js, generated from
 *  dentindices/data/indices.json). Parity with Python is checked by tests/test_web_engine.py.
 *  MIT licence. Research and education tool; not a diagnosis. */
(function (root) {
  "use strict";

  const REG = root.DENTINDICES_REGISTRY || (typeof require !== "undefined" ? require("./indices-data.json") : null);
  if (!REG) throw new Error("DentIndices: registry not loaded");

  class InputError extends Error { constructor(m) { super(m); this.name = "InputError"; } }
  class ToothError extends InputError { constructor(m) { super(m); this.name = "ToothError"; } }

  // ------------------------------------------------------------------ helpers
  const codes = (name) => { const c = REG.codes[name]; if (!c) throw new Error("No code table " + name); return c; };
  function requireVerified(id) {
    const st = REG.indices[id].verification.status;
    if (st !== "primary" && st !== "secondary") throw new Error(id + " is not verified against its source; it is switched off.");
  }
  function roundHalfUp(v, d) {
    const s = String(v);
    if (/e/i.test(s)) return Number(Number(v).toFixed(d));
    return Number(Math.round(Number(s + "e" + d)) + "e-" + d);
  }
  function band(value, bands, roundTo) {
    if (value === null || value === undefined) return null;
    const v = roundTo === null || roundTo === undefined ? value : roundHalfUp(value, roundTo);
    for (const b of bands) if (b.upto === null || v <= b.upto + 1e-12) return b.label;
    return bands[bands.length - 1].label;
  }
  function bandEntry(value, bands, roundTo) {
    const v = roundTo === null || roundTo === undefined ? value : roundHalfUp(value, roundTo);
    for (const b of bands) if (b.upto === null || v <= b.upto + 1e-12) return b;
    return bands[bands.length - 1];
  }
  const r10 = (x) => (x === null || x === undefined ? null : Math.round(x * 1e10) / 1e10);
  const NUMBER_RE = /^[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?$/;
  // Text that means "not recorded" in survey files (same list as the Python engine).
  const BLANKS = ["", "-", ".", "NA", "N/A", "NAN"];
  const isBlank = (v) => v === null || v === undefined || (typeof v === "number" && Number.isNaN(v)) || (typeof v === "string" && BLANKS.includes(v.trim().toUpperCase()));
  function normCode(v) {
    if (typeof v === "boolean") throw new InputError("Not a valid code: " + v);
    if (typeof v === "number") { if (!Number.isInteger(v)) throw new InputError("Not a valid code: " + v); return String(v); }
    return String(v).trim().toUpperCase();
  }
  function entries(data) {
    if (data === null || data === undefined) return [];
    if (Array.isArray(data)) return data.map((p) => { if (!Array.isArray(p) || p.length !== 2) throw new InputError("Expected (tooth, value) pairs"); return p; });
    if (data instanceof Map) return Array.from(data.entries());
    if (typeof data === "object") return Object.entries(data);
    throw new InputError("Expected a mapping of tooth -> value");
  }
  function intScore(v, lo, hi, what) {
    if (typeof v === "boolean") throw new InputError(what + ": " + v + " is not a score");
    let n = v;
    if (typeof v === "string") { const s = v.trim(); if (!/^-?\d+$/.test(s)) throw new InputError(what + ": " + JSON.stringify(v) + " is not a whole number"); n = parseInt(s, 10); }
    if (typeof n !== "number" || !Number.isInteger(n) || n < lo || n > hi) throw new InputError(what + ": " + JSON.stringify(v) + " must be a whole number from " + lo + " to " + hi);
    return n;
  }
  function num(v, what, lo, hi) {
    if (typeof v === "boolean" || v === null || v === undefined || (typeof v === "string" && v.trim() === "")) throw new InputError(what + ": " + JSON.stringify(v) + " is not a number");
    if (typeof v !== "number" && typeof v !== "string") throw new InputError(what + ": " + JSON.stringify(v) + " is not a number");
    if (typeof v === "string" && !NUMBER_RE.test(v.trim())) throw new InputError(what + ": " + JSON.stringify(v) + " is not a number");
    const x = typeof v === "number" ? v : Number(v.trim());
    if (!Number.isFinite(x)) throw new InputError(what + ": " + JSON.stringify(v) + " is not a finite number");
    if (lo !== undefined && lo !== null && x < lo) throw new InputError(what + ": " + v + " must be at least " + lo);
    if (hi !== undefined && hi !== null && x > hi) throw new InputError(what + ": " + v + " must be at most " + hi);
    return x;
  }
  const ageValue = (a) => (a === null || a === undefined || (typeof a === "string" && !a.trim()) ? null : num(a, "age", 0, 130));
  function teethSet(tp, what) {
    if (tp === null || typeof tp !== "object" || (!Array.isArray(tp) && !(tp instanceof Set))) throw new InputError((what || "teeth_present") + " must be a list of tooth numbers, for example [11, 12, 16]");
    return new Set(Array.from(tp).map(parseTooth));
  }
  const teethList = (ts) => { const a = Array.from(ts).sort((x, y) => x - y); return a.length ? a.join(", ") : "none"; };
  const fmtG = (x) => (Number.isInteger(x) ? String(x) : String(Number(x.toPrecision(4))));
  function result(index, value, components, category, guidance, trace, warnings, sources) {
    return { index, value, components: components || {}, category: category ?? null, guidance: guidance ?? null,
      trace: trace || [], warnings: warnings || [], sources: sources || [] };
  }

  // ------------------------------------------------------------------ teeth
  const PERMANENT = []; for (const q of [1, 2, 3, 4]) for (let p = 1; p <= 8; p++) PERMANENT.push(q * 10 + p);
  const PRIMARY = []; for (const q of [5, 6, 7, 8]) for (let p = 1; p <= 5; p++) PRIMARY.push(q * 10 + p);
  const THIRD = [18, 28, 38, 48], SECOND = [17, 27, 37, 47];
  const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
  const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
  const SEXTANTS = { S1: [18, 17, 16, 15, 14], S2: [13, 12, 11, 21, 22, 23], S3: [24, 25, 26, 27, 28], S4: [38, 37, 36, 35, 34], S5: [33, 32, 31, 41, 42, 43], S6: [44, 45, 46, 47, 48] };
  const SEXTANT_ORDER = ["S1", "S2", "S3", "S4", "S5", "S6"];
  const SEXTANT_ALIASES = { UR: "S1", UA: "S2", UL: "S3", LL: "S4", LA: "S5", LR: "S6", 1: "S1", 2: "S2", 3: "S3", 4: "S4", 5: "S5", 6: "S6" };
  const isPerm = (t) => PERMANENT.includes(t), isPrim = (t) => PRIMARY.includes(t);
  const position = (t) => t % 10, quadrant = (t) => Math.floor(t / 10);
  const isUpper = (t) => [1, 2, 5, 6].includes(quadrant(t));
  const isAnterior = (t) => position(t) <= 3;
  const isThird = (t) => THIRD.includes(t);
  function parseTooth(tooth) {
    let n;
    if (typeof tooth === "boolean" || tooth === null || tooth === undefined) throw new ToothError("Not a tooth number: " + tooth);
    if (typeof tooth === "number") { if (!Number.isInteger(tooth)) throw new ToothError("Not a tooth number: " + tooth); n = tooth; }
    else if (typeof tooth === "string") {
      let s = tooth.trim().replace(/\./g, "");
      if (s.toLowerCase().startsWith("t")) s = s.slice(1);
      if (!/^\d+$/.test(s)) throw new ToothError("Not an FDI tooth number: " + JSON.stringify(tooth) + " (use two digits such as 16 or 55)");
      n = parseInt(s, 10);
    } else throw new ToothError("Not a tooth number: " + tooth);
    if (!isPerm(n) && !isPrim(n)) throw new ToothError(JSON.stringify(tooth) + " is not a valid FDI tooth (11-48 permanent, 51-85 primary)");
    return n;
  }
  const primaryAt = (t) => (isPerm(t) && position(t) <= 5 ? (quadrant(t) + 4) * 10 + position(t) : null);
  const permanentAt = (t) => (quadrant(t) - 4) * 10 + position(t);
  function parseSextant(k) {
    const s = String(k).trim().toUpperCase();
    if (SEXTANTS[s]) return s;
    if (SEXTANT_ALIASES[s]) return SEXTANT_ALIASES[s];
    throw new InputError("Unknown sextant " + JSON.stringify(k) + "; use S1-S6 or UR, UA, UL, LL, LA, LR");
  }
  function adjacent(a, b) {
    for (const arch of [UPPER, LOWER]) if (arch.includes(a) && arch.includes(b)) return Math.abs(arch.indexOf(a) - arch.indexOf(b)) === 1;
    return false;
  }
  function hasNonAdjacentPair(teeth) {
    const ts = Array.from(new Set(teeth)).sort((x, y) => x - y);
    for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) if (!adjacent(ts[i], ts[j])) return true;
    return false;
  }
  const antagonist = (t) => ({ 1: 4, 4: 1, 2: 3, 3: 2 }[quadrant(t)] * 10 + position(t));
  function opposingPairs(present) {
    const s = new Set(Array.from(present).filter((t) => isPerm(t) && !isThird(t)));
    let n = 0; for (const t of s) if (isUpper(t) && s.has(antagonist(t))) n++;
    return n;
  }

  // ------------------------------------------------------------------ stats
  const LANCZOS = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  function lgamma(x) {
    if (x < 0.5) return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgamma(1 - x);
    x -= 1; let a = LANCZOS[0]; const t = x + 7.5;
    for (let i = 1; i < 9; i++) a += LANCZOS[i] / (x + i);
    return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
  }
  function betacf(a, b, x) {
    const tiny = 1e-300; const qab = a + b, qap = a + 1, qam = a - 1;
    let c = 1, d = 1 - qab * x / qap; if (Math.abs(d) < tiny) d = tiny; d = 1 / d; let h = d;
    for (let m = 1; m <= 300; m++) {
      const m2 = 2 * m; let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
      d = 1 + aa * d; if (Math.abs(d) < tiny) d = tiny; c = 1 + aa / c; if (Math.abs(c) < tiny) c = tiny; d = 1 / d; h *= d * c;
      aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
      d = 1 + aa * d; if (Math.abs(d) < tiny) d = tiny; c = 1 + aa / c; if (Math.abs(c) < tiny) c = tiny; d = 1 / d;
      const del = d * c; h *= del; if (Math.abs(del - 1) < 3e-16) break;
    }
    return h;
  }
  function betainc(a, b, x) {
    if (x <= 0) return 0; if (x >= 1) return 1;
    const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
    return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
  }
  function tCdf(t, df) { const p = 0.5 * betainc(df / 2, 0.5, df / (df + t * t)); return t > 0 ? 1 - p : p; }
  function tQuantile(p, df) {
    if (p === 0.5) return 0; let lo = -1e3, hi = 1e3;
    for (let i = 0; i < 200; i++) { const mid = (lo + hi) / 2; if (tCdf(mid, df) < p) lo = mid; else hi = mid; if (hi - lo < 1e-13) break; }
    return (lo + hi) / 2;
  }
  function normalQuantile(p) {
    const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
    const b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
    const c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
    const d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
    const plow = 0.02425; let q, r;
    if (p < plow) { q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    if (p > 1 - plow) { q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    q = p - 0.5; r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }
  function wilson(k, n, conf) {
    const z = normalQuantile(1 - (1 - conf) / 2), p = k / n, den = 1 + z * z / n;
    const centre = (p + z * z / (2 * n)) / den, half = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den;
    return [Math.max(0, centre - half), Math.min(1, centre + half)];
  }

  // ------------------------------------------------------------------ caries
  const DENT = () => codes("who2013_dentition");
  function splitDentition(input) {
    const tab = DENT(); const permCodes = Object.keys(tab.permanent), primCodes = Object.keys(tab.primary);
    const permanent = new Map(), primary = new Map(), warnings = [], seen = new Set();
    for (const [key, raw] of entries(input)) {
      const t = parseTooth(key);
      if (seen.has(t)) throw new InputError("Tooth " + t + " appears more than once");
      seen.add(t);
      if (isBlank(raw)) continue;
      const c = normCode(raw);
      if (isPerm(t)) {
        if (permCodes.includes(c)) permanent.set(t, c);
        else if (primCodes.includes(c)) {
          const p = primaryAt(t);
          if (p === null) throw new InputError("Tooth " + t + ": letter code " + JSON.stringify(c) + " means a primary tooth, but no primary tooth occupies the space of a permanent molar");
          if (primary.has(p)) throw new InputError("Primary tooth " + p + " is coded twice (as " + p + " and via space " + t + ")");
          primary.set(p, c);
        } else throw new InputError("Tooth " + t + ": " + JSON.stringify(raw) + " is not a WHO 2013 dentition code (0-9, or A-G for primary teeth)");
      } else {
        if (primCodes.includes(c)) { if (primary.has(t)) throw new InputError("Primary tooth " + t + " is coded twice"); primary.set(t, c); }
        else if (permCodes.includes(c)) throw new InputError("Tooth " + t + " is a primary tooth: WHO 2013 codes primary teeth with letters A-G, not " + JSON.stringify(c));
        else throw new InputError("Tooth " + t + ": " + JSON.stringify(raw) + " is not a WHO 2013 primary-tooth code (A-G)");
      }
    }
    for (const p of Array.from(primary.keys()).sort((a, b) => a - b)) {
      const s = permanentAt(p);
      if (permanent.has(s)) {
        if (permanent.get(s) === "8") { warnings.push("Space " + s + ": code 8 (unerupted) is only for spaces without a primary tooth; primary tooth " + p + " was kept and the code 8 ignored."); permanent.delete(s); }
        else { warnings.push("Space " + s + ": both the permanent and primary tooth " + p + " were coded; WHO records the permanent tooth only, so " + p + " was ignored."); primary.delete(p); }
      }
    }
    return { permanent, primary, warnings };
  }
  function mCodes(age, mRule, hasCode5, warnings, trace) {
    const tab = DENT(), th = tab.m_age_threshold, comp = tab.permanent_components;
    if (!["who2013", "caries_only", "any_reason"].includes(mRule)) throw new InputError("m_rule must be one of who2013, caries_only, any_reason");
    if (mRule === "caries_only") { trace.push("M rule: only code 4 (missing due to caries) counts (m_rule='caries_only')."); return comp.M_under_threshold; }
    if (mRule === "any_reason") { trace.push("M rule: codes 4 and 5 (missing for any reason) count (m_rule='any_reason')."); return comp.M_at_or_over_threshold; }
    if (age === null) {
      if (hasCode5) warnings.push("Age not given: teeth coded 5 (missing for another reason) were not counted in M. WHO 2013 counts them from age 30; give the age to apply the rule.");
      trace.push("M rule (WHO 2013): age not given, so only code 4 counts."); return comp.M_under_threshold;
    }
    if (age >= th) { trace.push("M rule (WHO 2013): age " + fmtG(age) + " is " + th + " or over, so codes 4 and 5 count (missing due to caries or any other reason)."); return comp.M_at_or_over_threshold; }
    trace.push("M rule (WHO 2013): age " + fmtG(age) + " is under " + th + ", so only code 4 counts."); return comp.M_under_threshold;
  }
  const sortedKeys = (m, pred) => Array.from(m.entries()).filter(([t, c]) => pred(t, c)).map(([t]) => t).sort((a, b) => a - b);

  function dmft_permanent(o) {
    o = o || {}; requireVerified("dmft_permanent");
    const tab = DENT(), comp = tab.permanent_components, a = ageValue(o.age);
    const incl = o.include_third_molars === undefined ? true : !!o.include_third_molars;
    let { permanent, warnings } = splitDentition(o.codes);
    const trace = [];
    if (!incl) {
      const dropped = sortedKeys(permanent, (t) => isThird(t));
      permanent = new Map(Array.from(permanent).filter(([t]) => !isThird(t)));
      trace.push("Third molars excluded (basis 28 teeth); dropped: " + teethList(dropped) + ".");
    } else trace.push("Basis 32 teeth, third molars included (WHO 2013).");
    const mc = mCodes(a, o.m_rule || "who2013", Array.from(permanent.values()).includes("5"), warnings, trace);
    const dT = sortedKeys(permanent, (t, c) => comp.D.includes(c)), mT = sortedKeys(permanent, (t, c) => mc.includes(c)), fT = sortedKeys(permanent, (t, c) => comp.F.includes(c));
    const present = sortedKeys(permanent, (t, c) => comp.present.includes(c));
    trace.push("D = teeth coded 1 or 2: " + teethList(dT) + " -> " + dT.length + ".");
    trace.push("M = teeth coded " + mc.join(" or ") + ": " + teethList(mT) + " -> " + mT.length + ".");
    trace.push("F = teeth coded 3: " + teethList(fT) + " -> " + fT.length + ".");
    const sealed = sortedKeys(permanent, (t, c) => c === "6"), special = sortedKeys(permanent, (t, c) => c === "7");
    if (sealed.length || special.length) trace.push("Codes 6 (sealant: " + teethList(sealed) + ") and 7 (abutment/crown/veneer/implant: " + teethList(special) + ") are not counted in DMFT.");
    const unerupted = sortedKeys(permanent, (t, c) => c === "8"), notRec = sortedKeys(permanent, (t, c) => c === "9");
    if (notRec.length) warnings.push("Teeth coded 9 (present but not examined) are excluded from caries counts: " + teethList(notRec) + ".");
    if (!permanent.size) warnings.push("No permanent teeth were recorded: DMFT is undefined (left out of group summaries).");
    const missingOther = sortedKeys(permanent, (t, c) => c === "5" && !mT.includes(t));
    const d = dT.length, m = mT.length, f = fT.length; let total = d + m + f;
    const nMissing = Array.from(permanent.values()).filter((c) => comp.missing.includes(c)).length;
    const components = { DT: d, MT: m, FT: f, DMFT: total, DFT: d + f, teeth_present: present.length, teeth_missing: nMissing, unerupted: unerupted.length,
      not_recorded: notRec.length, sealed: sealed.length, abutment_crown_veneer: special.length, missing_other_reason_not_counted: missingOther.length,
      caries_free: total === 0, untreated_caries: d > 0, edentulous: present.length === 0 && nMissing > 0, D_teeth: dT, M_teeth: mT, F_teeth: fT, age: a, third_molars_included: incl };
    trace.push("DMFT = " + d + " + " + m + " + " + f + " = " + total + ".");
    if (!permanent.size) { components.DMFT = null; components.caries_free = null; components.untreated_caries = null; total = null; }
    return result("dmft_permanent", total, components, null, null, trace, warnings, ["who2013"]);
  }
  function dmft_primary(o) {
    o = o || {}; requireVerified("dmft_primary");
    const comp = DENT().primary_components; const { primary, warnings } = splitDentition(o.codes);
    const trace = ["Primary teeth use letter codes A-G (WHO 2013)."];
    const dT = sortedKeys(primary, (t, c) => comp.d.includes(c)), mT = sortedKeys(primary, (t, c) => comp.m.includes(c)), fT = sortedKeys(primary, (t, c) => comp.f.includes(c));
    const present = sortedKeys(primary, (t, c) => comp.present.includes(c));
    trace.push("d = teeth coded B or C: " + teethList(dT) + " -> " + dT.length + ".");
    trace.push("m = teeth coded E: " + teethList(mT) + " -> " + mT.length + ".");
    trace.push("f = teeth coded D: " + teethList(fT) + " -> " + fT.length + ".");
    if (!primary.size) warnings.push("No primary teeth were recorded: dmft is undefined (left out of group summaries).");
    const d = dT.length, m = mT.length, f = fT.length; let total = d + m + f;
    trace.push("dmft = " + d + " + " + m + " + " + f + " = " + total + ".");
    const components = { dt: d, mt: m, ft: f, dmft: total, dft: d + f, teeth_present: present.length, sealed: Array.from(primary.values()).filter((c) => c === "F").length,
      caries_free: total === 0, untreated_caries: d > 0, d_teeth: dT, m_teeth: mT, f_teeth: fT };
    if (!primary.size) { components.dmft = null; components.caries_free = null; components.untreated_caries = null; total = null; }
    return result("dmft_primary", total, components, null, null, trace, warnings, ["who2013"]);
  }
  function caries_experience(o) {
    o = o || {};
    return { permanent: dmft_permanent(o), primary: dmft_primary({ codes: o.codes }) };
  }
  const SURF_ALIASES = { O: "O", OCC: "O", OCCLUSAL: "O", M: "M", MES: "M", MESIAL: "M", D: "D", DIS: "D", DISTAL: "D", B: "B", BUC: "B", BUCCAL: "B", F: "B", FAC: "B", FACIAL: "B", LAB: "B", LABIAL: "B",
    L: "L", LI: "L", LING: "L", LINGUAL: "L", P: "L", PAL: "L", PALATAL: "L", ORAL: "L" };
  const surfacesFor = (t) => (isAnterior(t) ? DENT().surfaces.anterior : DENT().surfaces.posterior).slice();
  function surfaceCodes(data, dentition) {
    const tab = DENT(); const valid = Object.keys(dentition === "permanent" ? tab.permanent : tab.primary);
    const whole = dentition === "permanent" ? ["4", "5", "8"] : ["E"];
    const out = new Map(), warnings = [], seen = new Set();
    const sk = (k) => { try { return parseTooth(k); } catch (e) { return 0; } };
    for (const [key, raw] of entries(data).slice().sort((a, b) => sk(a[0]) - sk(b[0]))) {
      const t0 = parseTooth(key);
      if (seen.has(t0)) throw new InputError("Tooth " + t0 + " appears more than once");
      seen.add(t0);
      const isMap = raw !== null && typeof raw === "object";
      const rawVals = (isMap ? Object.values(raw) : [raw]).filter((v) => !isBlank(v));
      if (!rawVals.length) continue;
      const kinds = new Set(rawVals.map((v) => { const c = normCode(v); return /^[A-Z]+$/.test(c) && c !== "X" ? "primary" : "permanent"; }));
      if (kinds.size > 1) throw new InputError("Tooth " + t0 + ": mixes permanent (digit) and primary (letter) codes");
      const kind = Array.from(kinds)[0];
      if (kind !== dentition) continue;
      let t = t0;
      if (dentition === "primary" && isPerm(t0)) { const p = primaryAt(t0); if (p === null) throw new InputError("Tooth " + t0 + ": letter codes mean a primary tooth, but no primary tooth occupies a permanent molar space"); t = p; }
      if (dentition === "permanent" && isPrim(t0)) throw new InputError("Tooth " + t0 + " is a primary tooth: use letter codes A-G");
      if (out.has(t)) throw new InputError("Tooth " + t + " appears more than once");
      const allowed = surfacesFor(t);
      if (isMap) {
        let surf = {};
        for (const [sk, sv] of Object.entries(raw)) {
          if (isBlank(sv)) continue;
          const key2 = String(sk).trim().toUpperCase();
          if (!SURF_ALIASES[key2]) throw new InputError("Unknown surface " + JSON.stringify(sk) + "; use O, M, D, B (buccal/labial) or L (lingual/palatal)");
          const s = SURF_ALIASES[key2];
          if (!allowed.includes(s)) throw new InputError("Tooth " + t + ": WHO 2013 surface forms record " + allowed.join(", ") + " for this tooth, not " + JSON.stringify(sk));
          const c = normCode(sv);
          if (!valid.includes(c)) throw new InputError("Tooth " + t + " surface " + s + ": " + JSON.stringify(sv) + " is not a valid " + dentition + " code");
          if (s in surf) throw new InputError("Tooth " + t + ": surface " + s + " is given twice");
          surf[s] = c;
        }
        if (!Object.keys(surf).length) continue;
        const vals = Object.values(surf); const tl = Array.from(new Set(vals.filter((c) => whole.includes(c))));
        if (tl.length && new Set(vals).size > 1) throw new InputError("Tooth " + t + ": codes " + tl.sort().join(", ") + " describe the whole tooth and cannot be mixed with other surface codes");
        if (tl.length && Object.keys(surf).length < allowed.length) { const w = tl[0]; surf = {}; for (const s of allowed) surf[s] = w; }
        const missing = allowed.filter((s) => !(s in surf));
        if (missing.length) warnings.push("Tooth " + t + ": surface(s) " + missing.join(", ") + " not recorded and not counted.");
        const off = Object.entries(surf).filter(([s, c]) => (c === "6" || c === "F") && s !== "O").map(([s]) => s);
        if (off.length) warnings.push("Tooth " + t + ": sealant code on non-occlusal surface(s) " + off.join(", ") + ".");
        out.set(t, surf);
      } else {
        const c = normCode(raw);
        if (!valid.includes(c)) throw new InputError("Tooth " + t + ": " + JSON.stringify(raw) + " is not a valid " + dentition + " code");
        const surf = {}; for (const s of allowed) surf[s] = c; out.set(t, surf);
      }
    }
    return { data: out, warnings };
  }
  function dmfs_permanent(o) {
    o = o || {}; requireVerified("dmfs_permanent");
    const a = ageValue(o.age); let { data, warnings } = surfaceCodes(o.surfaces, "permanent"); const trace = [];
    if (o.include_third_molars === false) { data = new Map(Array.from(data).filter(([t]) => !isThird(t))); trace.push("Third molars excluded."); }
    const comp = DENT().permanent_components;
    const mc = mCodes(a, o.m_rule || "who2013", Array.from(data.values()).some((s) => Object.values(s).includes("5")), warnings, trace);
    let ds = 0, fs = 0, ms = 0;
    for (const t of Array.from(data.keys()).sort((x, y) => x - y)) {
      const vals = Object.values(data.get(t));
      if (vals.every((c) => mc.includes(c))) { ms += vals.length; continue; }
      ds += vals.filter((c) => comp.D.includes(c)).length; fs += vals.filter((c) => comp.F.includes(c)).length;
    }
    const total = ds + ms + fs;
    trace.push("DS (surfaces coded 1 or 2) = " + ds + "; MS (surfaces of teeth coded " + mc.join(" or ") + ": 5 per posterior, 4 per anterior tooth) = " + ms + "; FS (surfaces coded 3) = " + fs + ".");
    trace.push("DMFS = " + ds + " + " + ms + " + " + fs + " = " + total + ".");
    let nS = 0; for (const s of data.values()) nS += Object.keys(s).length;
    return result("dmfs_permanent", total, { DS: ds, MS: ms, FS: fs, DMFS: total, DFS: ds + fs, surfaces_recorded: nS, teeth_recorded: data.size, age: a }, null, null, trace, warnings, ["who2013", "broadbent2005"]);
  }
  function dmfs_primary(o) {
    o = o || {}; requireVerified("dmfs_primary");
    const { data, warnings } = surfaceCodes(o.surfaces, "primary"); const comp = DENT().primary_components;
    let ds = 0, fs = 0, ms = 0;
    for (const t of Array.from(data.keys()).sort((x, y) => x - y)) {
      const vals = Object.values(data.get(t));
      if (vals.every((c) => comp.m.includes(c))) { ms += vals.length; continue; }
      ds += vals.filter((c) => comp.d.includes(c)).length; fs += vals.filter((c) => comp.f.includes(c)).length;
    }
    const total = ds + ms + fs; let nS = 0; for (const s of data.values()) nS += Object.keys(s).length;
    const trace = ["ds (B or C) = " + ds + "; ms (surfaces of teeth coded E) = " + ms + "; fs (D) = " + fs + ".", "dmfs = " + ds + " + " + ms + " + " + fs + " = " + total + "."];
    return result("dmfs_primary", total, { ds, ms, fs, dmfs: total, dfs: ds + fs, surfaces_recorded: nS, teeth_recorded: data.size }, null, null, trace, warnings, ["who2013"]);
  }
  function pufa(o) {
    o = o || {}; requireVerified("pufa");
    const letters = ["P", "U", "F", "A"]; const perm = new Map(), prim = new Map();
    for (const [key, raw] of entries(o.codes)) {
      const t = parseTooth(key);
      if (perm.has(t) || prim.has(t)) throw new InputError("Tooth " + t + " appears more than once");
      if (isBlank(raw) || ["0", "N", "NONE"].includes(normCode(raw))) continue;
      const c = normCode(raw);
      if (c.length !== 1 || !letters.includes(c)) throw new InputError("Tooth " + t + ": " + JSON.stringify(raw) + " is not a PUFA code; give one of P, U, F, A per tooth (PUFA assigns one score per tooth)");
      (isPerm(t) ? perm : prim).set(t, c);
    }
    const comps = { PUFA: perm.size, pufa: prim.size, PUFA_pufa: perm.size + prim.size };
    for (const k of letters) comps[k] = Array.from(perm.values()).filter((c) => c === k).length;
    for (const k of letters) comps[k.toLowerCase()] = Array.from(prim.values()).filter((c) => c === k).length;
    const total = perm.size + prim.size; const warnings = [];
    const trace = ["PUFA (permanent teeth with P, U, F or A) = " + perm.size + ": " + teethList(perm.keys()) + ".", "pufa (primary teeth) = " + prim.size + ": " + teethList(prim.keys()) + ".", "PUFA/pufa (both dentitions) = " + total + "."];
    if (o.decayed_teeth !== undefined && o.decayed_teeth !== null) {
      const dt = o.decayed_teeth;
      if (typeof dt !== "number" || !Number.isInteger(dt) || dt < 0) throw new InputError("decayed_teeth must be a whole number >= 0");
      let ratio = null;
      if (dt === 0) { if (total) warnings.push("PUFA teeth are also decayed teeth (D/d); decayed_teeth = 0 is inconsistent."); }
      else { if (total > dt) warnings.push("More PUFA teeth than decayed teeth: check the D/d count."); ratio = r10(100 * total / dt); }
      comps.decayed_teeth = dt; comps.percent_decayed_progressed = ratio;
      trace.push("Share of decayed teeth that progressed to PUFA = " + total + "/" + dt + " x 100" + (ratio !== null ? " = " + ratio.toFixed(1) + "%." : " (undefined)."));
    }
    return result("pufa", total, comps, null, null, trace, warnings, ["monse2010"]);
  }

  // ------------------------------------------------------------------ population
  function seq(x, what) {
    if (!Array.isArray(x) && !(x instanceof Set)) throw new InputError(what + " must be a list (got " + (x === null ? "None" : typeof x) + ")");
    return Array.from(x);
  }
  function values(vs, what) {
    const out = [];
    for (let v of seq(vs, what || "values")) {
      if (v && typeof v === "object" && "value" in v && "index" in v) v = v.value;
      if (isBlank(v)) continue;
      out.push(num(v, what || "values"));
    }
    return out;
  }
  function summarize(o) {
    o = o || {}; const conf = o.confidence === undefined ? 0.95 : num(o.confidence, "confidence");
    if (!(conf > 0 && conf < 1)) throw new InputError("confidence must be between 0 and 1");
    let vals = seq(o.values, "values"); let x, wv = null;
    if (o.weights !== undefined && o.weights !== null) {
      const w = seq(o.weights, "weights"); if (w.length !== vals.length) throw new InputError("weights must have the same length as values");
      vals = vals.map((v) => (v && typeof v === "object" && "value" in v && "index" in v ? v.value : v));
      const pairs = vals.map((v, i) => [v, w[i]]).filter(([v]) => !isBlank(v));
      x = values(pairs.map((p) => p[0])); wv = pairs.map((p) => num(p[1], "weight", 0));
    } else x = values(vals);
    const n = x.length; const out = { label: o.label || "value", n };
    if (!n) return Object.assign(out, { mean: null, sd: null, se: null, ci_low: null, ci_high: null, median: null, min: null, max: null, n_positive: 0, prevalence: null, prevalence_ci_low: null, prevalence_ci_high: null });
    const mean = x.reduce((a, b) => a + b, 0) / n;
    const sd = n > 1 ? Math.sqrt(x.reduce((a, v) => a + (v - mean) ** 2, 0) / (n - 1)) : null;
    const se = sd !== null ? sd / Math.sqrt(n) : null;
    let lo = null, hi = null; if (se !== null) { const tq = tQuantile(1 - (1 - conf) / 2, n - 1); lo = mean - tq * se; hi = mean + tq * se; }
    const s = x.slice().sort((a, b) => a - b); const median = n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
    const pos = x.filter((v) => v > 0).length; const [plo, phi] = wilson(pos, n, conf);
    Object.assign(out, { mean: r10(mean), sd: r10(sd), se: r10(se), ci_low: r10(lo), ci_high: r10(hi), median, min: s[0], max: s[n - 1], n_positive: pos,
      prevalence: r10(100 * pos / n), prevalence_ci_low: r10(100 * plo), prevalence_ci_high: r10(100 * phi), confidence: conf });
    if (wv) {
      const tw = wv.reduce((a, b) => a + b, 0); if (tw <= 0) throw new InputError("weights must not all be zero");
      out.weighted_mean = r10(x.reduce((a, v, i) => a + v * wv[i], 0) / tw);
      out.weighted_prevalence = r10(100 * x.reduce((a, v, i) => a + (v > 0 ? wv[i] : 0), 0) / tw);
      out.weights_note = "Weighted point estimates only; use design-based methods for standard errors of complex survey samples.";
    }
    return out;
  }
  function sic(o) {
    o = o || {}; requireVerified("sic");
    const x = values(o.values, "DMFT"); const fraction = o.fraction === undefined ? 1 / 3 : num(o.fraction, "fraction"); const rounding = o.rounding || "nearest";
    if (!(fraction > 0 && fraction <= 1)) throw new InputError("fraction must be in (0, 1]");
    if (!["nearest", "ceil", "floor", "fractional"].includes(rounding)) throw new InputError("rounding must be 'nearest', 'ceil', 'floor' or 'fractional'");
    const n = x.length; if (!n) throw new InputError("SiC needs at least one value");
    const s = x.slice().sort((a, b) => b - a); const exact = n * fraction; const warnings = [];
    const trace = [n + " values sorted from highest to lowest; " + fmtG(fraction) + " of the group = " + fmtG(exact) + " people."];
    let value, k, group;
    if (rounding === "fractional") {
      const whole = Math.floor(exact + 1e-12), part = exact - whole;
      const total = s.slice(0, whole).reduce((a, b) => a + b, 0) + (part > 1e-12 && whole < n ? part * s[whole] : 0);
      value = total / exact; k = exact; group = s.slice(0, whole + (part > 1e-12 ? 1 : 0));
      trace.push("Top " + whole + " values plus " + fmtG(part) + " of the next one, divided by " + fmtG(exact) + ".");
    } else {
      if (rounding === "nearest") k = Math.floor(exact + 0.5 + 1e-12); else if (rounding === "ceil") k = Math.ceil(exact - 1e-12); else k = Math.floor(exact + 1e-12);
      k = Math.max(1, Math.min(n, k)); group = s.slice(0, k); value = group.reduce((a, b) => a + b, 0) / k;
      trace.push("Group size " + k + " (" + rounding + "); SiC = mean of the top " + k + " = " + fmtG(value) + ".");
    }
    const zeros = group.filter((v) => v === 0).length;
    if (zeros) warnings.push("The top group includes " + zeros + " caries-free people (DMFT = 0): caries prevalence is below " + Math.round(fraction * 100) + "%. Report the SaC as well (Schmoeckel 2019).");
    return result("sic", r10(value), { SiC: r10(value), n, group_size: k, fraction, rounding, group_min: Math.min(...group), caries_free_in_group: zeros }, null, null, trace, warnings, ["bratthall2000", "nishi2002"]);
  }
  function sac(o) {
    o = o || {}; requireVerified("sac");
    const x = values(o.values, "DMFT"); if (!x.length) throw new InputError("SaC needs at least one value");
    const aff = x.filter((v) => v > 0), n = x.length; const value = aff.length ? aff.reduce((a, b) => a + b, 0) / aff.length : null;
    const trace = [aff.length + " of " + n + " people have DMFT > 0 (" + (100 * aff.length / n).toFixed(1) + "%).", value !== null ? "SaC = mean DMFT of the affected = " + fmtG(value) + "." : "SaC is undefined: nobody has caries experience."];
    return result("sac", r10(value), { SaC: r10(value), n, n_affected: aff.length, prevalence: r10(100 * aff.length / n) }, null, null, trace, [], ["schmoeckel2019"]);
  }
  function dmfParts(records) {
    let sd = 0, sm = 0, sf = 0, n = 0, kind = null;
    for (let rec of seq(records, "records")) {
      if (rec && typeof rec === "object" && "components" in rec && "index" in rec) rec = rec.components;
      if (!rec || typeof rec !== "object") throw new InputError("Give DMFT results (from dmft_permanent/dmft_primary) or mappings with DT, MT, FT");
      let keys, k2;
      if (["DT", "MT", "FT"].every((k) => k in rec)) { keys = ["DT", "MT", "FT"]; k2 = "permanent"; }
      else if (["dt", "mt", "ft"].every((k) => k in rec)) { keys = ["dt", "mt", "ft"]; k2 = "primary"; }
      else if (["D", "M", "F"].every((k) => k in rec)) { keys = ["D", "M", "F"]; k2 = "permanent"; }
      else throw new InputError("Each record needs DT, MT and FT (or dt, mt, ft)");
      if (kind === null) kind = k2; else if (kind !== k2) throw new InputError("Do not mix permanent and primary records");
      sd += num(rec[keys[0]], keys[0], 0); sm += num(rec[keys[1]], keys[1], 0); sf += num(rec[keys[2]], keys[2], 0); n++;
    }
    if (!n) throw new InputError("No records given");
    return { d: sd, m: sm, f: sf, n, kind: kind || "permanent" };
  }
  function care_index(o) {
    requireVerified("care_index"); const { d, m, f, n, kind } = dmfParts((o || {}).records); const total = d + m + f;
    const value = total ? r10(100 * f / total) : null; const lbl = kind === "primary" ? "ft/dmft" : "FT/DMFT";
    const trace = [n + " records: sum D = " + fmtG(d) + ", M = " + fmtG(m) + ", F = " + fmtG(f) + ".", value !== null ? "Care Index = " + lbl + " x 100 = " + fmtG(f) + "/" + fmtG(total) + " x 100 = " + value.toFixed(1) + "%." : "Care Index is undefined (no caries experience)."];
    return result("care_index", value, { care_index: value, n, F: f, DMF: total, dentition: kind }, null, null, trace, [], ["walsh1970", "gupta2017"]);
  }
  function restorative_index(o) {
    requireVerified("restorative_index"); const { d, f, n, kind } = dmfParts((o || {}).records); const den = d + f;
    const value = den ? r10(100 * f / den) : null;
    const trace = [n + " records: sum D = " + fmtG(d) + ", F = " + fmtG(f) + ".", value !== null ? "Restorative Index = F/(D+F) x 100 = " + fmtG(f) + "/" + fmtG(den) + " x 100 = " + value.toFixed(1) + "%." : "Restorative Index is undefined (no decayed or filled teeth)."];
    return result("restorative_index", value, { restorative_index: value, n, D: d, F: f, dentition: kind }, null, null, trace, [], ["jackson1973", "gupta2017"]);
  }
  function component_percentages(o) {
    const { d, m, f, n, kind } = dmfParts((o || {}).records); const total = d + m + f;
    if (!total) return { n, dentition: kind, percent_D: null, percent_M: null, percent_F: null };
    return { n, dentition: kind, percent_D: r10(100 * d / total), percent_M: r10(100 * m / total), percent_F: r10(100 * f / total) };
  }
  const printedBand = (b) => ("below" in b ? "< " + b.below.toFixed(1) : ("above" in b ? "> " + b.above.toFixed(1) : b.from.toFixed(1) + "-" + b.upto.toFixed(1)));
  function whoLevel(x, bands) {
    for (const b of bands) if (("below" in b && x < b.below) || ("above" in b && x > b.above) || ("from" in b && b.from - 1e-12 <= x && x <= b.upto + 1e-12)) return b;
    return null;
  }
  function who_caries_level(o) {
    o = o || {}; requireVerified("who_caries_level"); const tab = codes("who_caries_levels");
    const key = String(o.age_group === undefined ? "12" : o.age_group).replace("\u2013", "-").trim();
    if (key !== "12" && key !== "35-44") throw new InputError("age_group must be '12' or '35-44' (the WHO indicator ages with published levels)");
    const v = num(o.mean_dmft, "mean DMFT", 0); let b = whoLevel(v, tab[key]); let trace;
    if (b === null) { const rv = roundHalfUp(v, tab.gap_round_to); b = whoLevel(rv, tab[key]); trace = ["Mean DMFT " + fmtG(v) + " falls between two printed WHO 2013 bands, so it is read to one decimal as " + rv.toFixed(1) + ": " + printedBand(b) + " -> " + b.label + " (age " + key + ")."]; }
    else trace = ["Mean DMFT " + fmtG(v) + " is in the WHO 2013 band " + printedBand(b) + " -> " + b.label + " (age " + key + ")."];
    return result("who_caries_level", b.label, { mean_dmft: v, age_group: key }, b.label, null, trace, [], ["who2013"]);
  }

  // ------------------------------------------------------------------ periodontal screening
  const EXCL = ["X", "-", "/", "EXCLUDED"];
  function sextantValues(sx, what) {
    if (sx && !Array.isArray(sx) && typeof sx === "object") {
      const out = {};
      for (const [k, v] of Object.entries(sx)) { const s = parseSextant(k); if (s in out) throw new InputError(what + ": sextant " + s + " given twice"); out[s] = v; }
      const r = {}; for (const s of SEXTANT_ORDER) r[s] = s in out ? out[s] : null; return r;
    }
    const vals = Array.from(sx || []);
    if (vals.length !== 6) throw new InputError(what + ": give six sextant values in the order UR, UA, UL, LL, LA, LR (upper right 18-14, upper anterior 13-23, upper left 24-28, lower left 38-34, lower anterior 33-43, lower right 44-48)");
    const r = {}; SEXTANT_ORDER.forEach((s, i) => { r[s] = vals[i]; }); return r;
  }
  function bpeCode(v, what) {
    if (isBlank(v) || EXCL.includes(normCode(v))) return null;
    const s = normCode(v); const fur = s.endsWith("*"); const core = s.replace(/\*+$/, "").trim();
    if (!["0", "1", "2", "3", "4"].includes(core)) throw new InputError(what + ": " + JSON.stringify(v) + " is not a BPE code (0-4, with * for furcation involvement, e.g. '3*')");
    return [parseInt(core, 10), fur];
  }
  function bpe(o) {
    o = o || {}; requireVerified("bpe"); const tab = codes("bpe");
    const vals = sextantValues(o.sextants, "BPE"); const parsed = {};
    for (const s of SEXTANT_ORDER) parsed[s] = bpeCode(vals[s], "BPE sextant " + s);
    const scored = SEXTANT_ORDER.filter((s) => parsed[s] !== null);
    if (!scored.length) throw new InputError("BPE: no sextant was scored");
    const maxCode = Math.max(...scored.map((s) => parsed[s][0])); const fur = scored.some((s) => parsed[s][1]);
    const furS = scored.filter((s) => parsed[s][1]), c3 = scored.filter((s) => parsed[s][0] === 3), c4 = scored.filter((s) => parsed[s][0] === 4);
    const excluded = SEXTANT_ORDER.filter((s) => parsed[s] === null);
    const grid = {}; for (const s of SEXTANT_ORDER) grid[s] = parsed[s] === null ? null : parsed[s][0] + (parsed[s][1] ? "*" : "");
    const trace = ["Highest code per sextant: " + SEXTANT_ORDER.map((s) => s + " " + (grid[s] || "-")).join(", ") + ".", "Highest code overall: " + maxCode + (fur ? " with furcation involvement" : "") + "."];
    let guidance = tab.guidance[String(maxCode)]; if (fur) guidance += " Furcation involvement (*): " + tab.guidance["*"]; guidance += " " + tab.recording;
    if (c4.length) trace.push("A code 4 is present, so a 6-point pocket chart of the entire dentition is indicated.");
    else if (c3.length) trace.push("Code 3 sextant(s) " + c3.join(", ") + ": after initial therapy, record a 6-point chart in those sextants.");
    if (excluded.length) trace.push("Sextants not scored (fewer than two teeth): " + excluded.join(", ") + ".");
    return result("bpe", maxCode, { max_code: maxCode, furcation: fur, furcation_sextants: furS, sextants: grid, code3_sextants: c3, code4_sextants: c4, excluded_sextants: excluded,
      full_chart_indicated: c4.length > 0, radiographs_indicated_sextants: c3.concat(c4) }, "Code " + maxCode + (fur ? "*" : ""), guidance, trace, [], ["bsp2019"]);
  }
  function bpe_from_teeth(o) {
    o = o || {}; requireVerified("bpe"); const tab = codes("bpe"); const tc = new Map();
    for (const [k, v] of entries(o.tooth_codes)) {
      const t = parseTooth(k); if (!isPerm(t)) throw new InputError("BPE is recorded on permanent teeth; " + t + " is a primary tooth");
      const p = bpeCode(v, "BPE tooth " + t); if (p !== null) { if (tc.has(t)) throw new InputError("Tooth " + t + " appears more than once"); tc.set(t, p); }
    }
    const present = o.teeth_present !== undefined && o.teeth_present !== null ? teethSet(o.teeth_present) : new Set(tc.keys());
    const miss = Array.from(tc.keys()).filter((t) => !present.has(t));
    if (miss.length) throw new InputError("Teeth " + teethList(miss) + " have codes but are not in teeth_present");
    const names = { UR: "S1", UA: "S2", UL: "S3", LL: "S4", LA: "S5", LR: "S6" }; const third = { S1: 18, S3: 28, S4: 38, S6: 48 };
    const grid = {}, trace = [];
    for (const [name, teeth] of Object.entries(tab.sextants)) {
      const s = names[name]; const members = teeth.filter((t) => present.has(t));
      if (s in third) { const molars = teeth.filter((t) => [6, 7].includes(t % 10)); if (molars.some((m) => !present.has(m)) && present.has(third[s])) { members.push(third[s]); trace.push(s + ": third molar " + third[s] + " included because a first/second molar is missing."); } }
      if (members.length < tab.min_teeth_per_sextant) { grid[s] = null; continue; }
      const sc = members.filter((t) => tc.has(t)).map((t) => tc.get(t));
      if (!sc.length) { grid[s] = null; trace.push(s + ": teeth present but none scored."); continue; }
      grid[s] = Math.max(...sc.map((x) => x[0])) + (sc.some((x) => x[1]) ? "*" : "");
    }
    const r = bpe({ sextants: grid }); r.trace = trace.concat(r.trace); return r;
  }
  function sbpe(o) {
    o = o || {}; requireVerified("sbpe"); const tab = codes("sbpe"); const a = ageValue(o.age);
    if (a === null) throw new InputError("sBPE needs the age (7-17 years)");
    if (a < 7 || a >= 18) throw new InputError("The simplified BPE is for ages 7 to 17; use bpe() from age 18");
    const allowed = tab.codes_by_age[a < 12 ? "7-11" : "12-17"]; const tm = new Map();
    for (const [k, v] of entries(o.index_teeth)) {
      const t = parseTooth(k); if (!tab.index_teeth.includes(t)) throw new InputError("Tooth " + t + " is not an sBPE index tooth (16, 11, 26, 36, 31, 46)");
      if (tm.has(t)) throw new InputError("Tooth " + t + " appears more than once"); tm.set(t, bpeCode(v, "sBPE tooth " + t));
    }
    const scored = Array.from(tm.entries()).filter(([, p]) => p !== null);
    if (!scored.length) throw new InputError("sBPE: no index tooth was scored");
    for (const [t, [c, f]] of scored) if (!allowed.includes(String(c)) || (f && !allowed.includes("*"))) throw new InputError("Tooth " + t + ": at age " + fmtG(a) + " the sBPE uses codes " + allowed.join(", ") + " only (7- to 11-year-olds: 0-2)");
    const mx = Math.max(...scored.map(([, p]) => p[0])), fur = scored.some(([, p]) => p[1]);
    const sc = new Set(scored.map(([t]) => t)); const uns = tab.index_teeth.filter((t) => !sc.has(t));
    const warnings = uns.length ? ["Index teeth not scored: " + teethList(uns) + "."] : [];
    const guidance = fur ? tab.guidance["*"] : tab.guidance[String(mx)];
    const teethObj = {}; scored.sort((x, y) => x[0] - y[0]).forEach(([t, [c, f]]) => { teethObj[t] = c + (f ? "*" : ""); });
    const trace = ["Age " + fmtG(a) + ": codes allowed " + allowed.join(", ") + ".", "Index teeth: " + scored.map(([t, [c, f]]) => t + " " + c + (f ? "*" : "")).join(", ") + ".", "Highest code: " + mx + (fur ? "*" : "") + "."];
    return result("sbpe", mx, { max_code: mx, furcation: fur, teeth: teethObj, age_band: a < 12 ? "7-11" : "12-17", unscored_index_teeth: uns }, "Code " + mx + (fur ? "*" : ""), guidance, trace, warnings, ["bsp2021"]);
  }
  function score(v, allowed, what) {
    if (isBlank(v)) return null; let c = normCode(v); if (c === "-") c = "X";
    if (!allowed.includes(c)) throw new InputError(what + ": " + JSON.stringify(v) + " is not one of " + allowed.join(", "));
    return c;
  }
  function cpitn(o) {
    o = o || {}; requireVerified("cpitn"); const tab = codes("cpitn"); const a = ageValue(o.age);
    const vals = sextantValues(o.sextants, "CPITN"); const parsed = {};
    for (const s of SEXTANT_ORDER) parsed[s] = score(vals[s], ["0", "1", "2", "3", "4", "X", "9"], "CPITN sextant " + s);
    const scored = SEXTANT_ORDER.filter((s) => parsed[s] !== null && parsed[s] !== "X" && parsed[s] !== "9").map((s) => parseInt(parsed[s], 10));
    if (!scored.length) throw new InputError("CPITN: no sextant was scored");
    const warnings = [];
    if (a !== null && a < tab.pockets_not_recorded_under_age && scored.some((c) => c >= 3)) warnings.push("Pockets (codes 3 and 4) are not recorded in children under 15 (WHO 1997); only bleeding and calculus should be scored.");
    const mx = Math.max(...scored); const tn = tab.treatment_need[String(mx)];
    const comps = { max_code: mx, treatment_need: tn };
    for (let k = 0; k < 5; k++) comps["sextants_code" + k] = scored.filter((c) => c === k).length;
    Object.assign(comps, { sextants_scored: scored.length, sextants_excluded: SEXTANT_ORDER.filter((s) => parsed[s] === "X").length, sextants_not_recorded: SEXTANT_ORDER.filter((s) => parsed[s] === "9").length,
      index_teeth: tab.index_teeth[a === null || a >= 20 ? "20_and_over" : "under_20"], sextants: parsed });
    const trace = ["Sextant codes: " + SEXTANT_ORDER.map((s) => s + " " + (parsed[s] || "-")).join(", ") + ".", "Highest code " + mx + " -> treatment need " + tn + " (" + tab.treatment_need_labels[tn] + ")."];
    return result("cpitn", mx, comps, tn, tab.treatment_need_labels[tn], trace, warnings, ["ainamo1982", "who1997"]);
  }
  function cpi_modified(o) {
    o = o || {}; requireVerified("cpi_modified"); const tab = codes("cpi_modified"); const a = ageValue(o.age);
    const b = new Map();
    for (const [k, v] of entries(o.bleeding)) { const t = parseTooth(k); if (b.has(t)) throw new InputError("Tooth " + t + " appears more than once (bleeding)"); const c = score(v, Object.keys(tab.bleeding), "bleeding tooth " + t); if (c !== null) b.set(t, c); }
    const p = new Map(); const warnings = [];
    if (o.pockets !== undefined && o.pockets !== null) {
      if (a !== null && a < tab.pockets_not_recorded_under_age) warnings.push("Pockets are not recorded under age 15 (WHO 2013); pocket scores were ignored.");
      else for (const [k, v] of entries(o.pockets)) { const t = parseTooth(k); if (p.has(t)) throw new InputError("Tooth " + t + " appears more than once (pockets)"); const c = score(v, Object.keys(tab.pocket), "pocket tooth " + t); if (c !== null) p.set(t, c); }
    }
    const presB = sortedKeys(b, (t, c) => c !== "X"), bleed = sortedKeys(b, (t, c) => c === "1"), noB = sortedKeys(b, (t, c) => c === "0"), exB = sortedKeys(b, (t, c) => c === "9");
    const examined = bleed.length + noB.length;
    const comps = { teeth_present: presB.length, teeth_examined: examined, teeth_excluded: exB.length, bleeding_teeth: bleed.length, bleeding: bleed.length > 0,
      bleeding_percent_of_present: presB.length ? r10(100 * bleed.length / presB.length) : null, bleeding_percent_of_examined: examined ? r10(100 * bleed.length / examined) : null };
    const trace = ["Bleeding: " + bleed.length + " of " + presB.length + " teeth present (" + teethList(bleed) + ")."];
    let category = bleed.length ? "Bleeding" : (examined ? "No bleeding" : null);
    if (p.size) {
      const presP = sortedKeys(p, (t, c) => c !== "X"), sh = sortedKeys(p, (t, c) => c === "1"), dp = sortedKeys(p, (t, c) => c === "2"), no = sortedKeys(p, (t, c) => c === "0");
      const mx = dp.length ? 2 : (sh.length ? 1 : (no.length ? 0 : null));
      Object.assign(comps, { pocket_max_score: mx, shallow_pocket_teeth: sh.length, deep_pocket_teeth: dp.length,
        shallow_pocket_percent_of_present: presP.length ? r10(100 * sh.length / presP.length) : null, deep_pocket_percent_of_present: presP.length ? r10(100 * dp.length / presP.length) : null,
        pocket_teeth_excluded: Array.from(p.values()).filter((c) => c === "9").length });
      trace.push("Pockets 4-5 mm: " + teethList(sh) + "; 6 mm or more: " + teethList(dp) + ".");
      if (mx !== null) { category = { 0: "No pockets", 1: "Shallow pockets (4-5 mm)", 2: "Deep pockets (6 mm or more)" }[mx]; trace.push("Highest pocket score: " + mx + "."); }
    }
    return result("cpi_modified", bleed.length, comps, category, null, trace, warnings, ["who2013"]);
  }
  function loss_of_attachment(o) {
    o = o || {}; requireVerified("loss_of_attachment"); const tab = codes("loa"); const a = ageValue(o.age);
    if (a !== null && a < tab.not_recorded_under_age) throw new InputError("Loss of attachment is not recorded under age 15 (WHO 2013)");
    const vals = sextantValues(o.sextants, "Loss of attachment"); const parsed = {};
    for (const s of SEXTANT_ORDER) parsed[s] = score(vals[s], Object.keys(tab.codes), "LOA sextant " + s);
    const scored = SEXTANT_ORDER.filter((s) => parsed[s] !== null && parsed[s] !== "X" && parsed[s] !== "9").map((s) => parseInt(parsed[s], 10));
    if (!scored.length) throw new InputError("Loss of attachment: no sextant was scored");
    const mx = Math.max(...scored); const comps = { max_score: mx };
    for (let k = 0; k < 5; k++) comps["sextants_score" + k] = scored.filter((c) => c === k).length;
    Object.assign(comps, { sextants_excluded: SEXTANT_ORDER.filter((s) => parsed[s] === "X").length, sextants_not_recorded: SEXTANT_ORDER.filter((s) => parsed[s] === "9").length, sextants: parsed });
    const trace = ["Sextant scores: " + SEXTANT_ORDER.map((s) => s + " " + (parsed[s] || "-")).join(", ") + ".", "Highest score " + mx + " (" + tab.codes[String(mx)] + ")."];
    return result("loss_of_attachment", mx, comps, tab.codes[String(mx)], null, trace, [], ["who2013"]);
  }

  // ------------------------------------------------------------------ hygiene
  const FOUR = { D: "D", DB: "D", DF: "D", DISTAL: "D", DISTOFACIAL: "D", DISTOBUCCAL: "D", B: "B", F: "B", BUCCAL: "B", FACIAL: "B", LABIAL: "B", V: "B", VESTIBULAR: "B",
    M: "M", MB: "M", MF: "M", MESIAL: "M", MESIOFACIAL: "M", MESIOBUCCAL: "M", L: "L", P: "L", O: "L", LINGUAL: "L", PALATAL: "L", ORAL: "L" };
  function fourArea(data, what) {
    const out = new Map();
    for (const [k, v] of entries(data)) {
      const t = parseTooth(k); if (out.has(t)) throw new InputError(what + ": tooth " + t + " appears more than once");
      let areas = {};
      if (Array.isArray(v)) {
        if (v.length !== 4) throw new InputError(what + ": tooth " + t + ": give four scores in the order D, B, M, L");
        ["D", "B", "M", "L"].forEach((a, i) => { if (!isBlank(v[i])) areas[a] = intScore(v[i], 0, 3, what + " tooth " + t + " area " + a); });
      } else if (v !== null && typeof v === "object") {
        for (const [ak, av] of Object.entries(v)) {
          if (isBlank(av)) continue; const key = String(ak).trim().toUpperCase();
          if (!FOUR[key]) throw new InputError("Unknown area " + JSON.stringify(ak) + ": use D (distofacial), B (facial), M (mesiofacial) or L (lingual)");
          const a = FOUR[key]; if (a in areas) throw new InputError(what + ": tooth " + t + " area " + a + " given twice");
          areas[a] = intScore(av, 0, 3, what + " tooth " + t + " area " + a);
        }
      } else if (isBlank(v)) continue;
      else throw new InputError(what + ": tooth " + t + ": give a mapping of areas or four scores (D, B, M, L)");
      if (Object.keys(areas).length) out.set(t, areas);
    }
    if (!out.size) throw new InputError(what + ": no scores given");
    return out;
  }
  function areaIndex(id, data, what, table, srcs) {
    requireVerified(id); const tab = codes(table); const sc = fourArea(data, what);
    const toothMeans = {}; let num12 = 0, nAreas = 0, sumAll = 0;
    for (const [t, a] of sc) { const vs = Object.values(a); const s = vs.reduce((x, y) => x + y, 0); toothMeans[t] = s / vs.length; num12 += s * (12 / vs.length); nAreas += vs.length; sumAll += s; }
    const person = num12 / (12 * sc.size); const warnings = [];  // exact: integer numerator, one division
    const inc = Array.from(sc.entries()).filter(([, a]) => Object.keys(a).length < 4).map(([t]) => t);
    if (inc.length) warnings.push("Teeth with fewer than four areas scored: " + teethList(inc) + " (tooth score = mean of the areas scored).");
    const ram = new Set(tab.ramfjord_teeth);
    const trace = [sc.size + " teeth, " + nAreas + " areas scored; tooth score = mean of its areas (0-3).", what + " = mean of tooth scores = " + fmtG(person) + " (read as " + roundHalfUp(person, tab.round_to).toFixed(1) + ")."];
    const ts = {}; for (const t of Object.keys(toothMeans)) ts[t] = r10(toothMeans[t]);
    const comps = { [what]: r10(person), mean_of_all_areas: r10(sumAll / nAreas), teeth_scored: sc.size, areas_scored: nAreas, tooth_scores: ts, ramfjord_teeth_only: Array.from(sc.keys()).every((t) => ram.has(t)) };
    return result(id, r10(person), comps, band(person, tab.bands, tab.round_to), null, trace, warnings, srcs);
  }
  function plaque_index(o) {
    const r = areaIndex("plaque_index", (o || {}).scores, "PlI", "plaque_index", ["silness1964", "loe1967", "delia2023"]);
    r.warnings = r.warnings.concat(["Interpretation bands are a textbook convention, not part of the original index."]); return r;
  }
  function gingival_index(o) { return areaIndex("gingival_index", (o || {}).scores, "GI", "gingival_index", ["loe1963", "loe1967"]); }
  const PCR = { M: "M", MESIAL: "M", D: "D", DISTAL: "D", B: "B", F: "B", FACIAL: "B", BUCCAL: "B", LABIAL: "B", L: "L", P: "L", LINGUAL: "L", PALATAL: "L", ORAL: "L" };
  function plaque_control_record(o) {
    o = o || {}; requireVerified("plaque_control_record"); const tab = codes("plaque_control_record"); const marked = new Map();
    for (const [k, v] of entries(o.plaque)) {
      const t = parseTooth(k); if (marked.has(t)) throw new InputError("Tooth " + t + " appears more than once");
      const s = new Set();
      if (typeof v === "string") { for (const ch of v.replace(/[, ]/g, "").toUpperCase()) { if (!PCR[ch]) throw new InputError("Tooth " + t + ": unknown surface " + JSON.stringify(ch) + " (use M, D, B/F, L)"); s.add(PCR[ch]); } }
      else if (Array.isArray(v)) { for (const a of v) { const key = String(a).trim().toUpperCase(); if (!PCR[key]) throw new InputError("Tooth " + t + ": unknown surface " + JSON.stringify(a) + " (use M, D, B/F, L)"); s.add(PCR[key]); } }
      else if (v !== null && typeof v === "object") {
        for (const [a, flag] of Object.entries(v)) {
          const key = String(a).trim().toUpperCase(); if (!PCR[key]) throw new InputError("Tooth " + t + ": unknown surface " + JSON.stringify(a) + " (use M, D, B/F, L)");
          if ([true, 1, "1", "yes", "Y", "y", "true", "True"].includes(flag)) s.add(PCR[key]);
          else if (![false, 0, "0", "no", "N", "n", "false", "False", null, ""].includes(flag)) throw new InputError("Tooth " + t + " surface " + a + ": " + JSON.stringify(flag) + " is not yes/no");
        }
      } else if (v === null || v === undefined) { /* none */ } else throw new InputError("Tooth " + t + ": give the surfaces with plaque");
      marked.set(t, s);
    }
    const present = o.teeth_present !== undefined && o.teeth_present !== null ? teethSet(o.teeth_present) : new Set(marked.keys());
    const extra = Array.from(marked.keys()).filter((t) => !present.has(t));
    if (extra.length) throw new InputError("Teeth " + teethList(extra) + " have plaque recorded but are not in teeth_present");
    if (!present.size) throw new InputError("No teeth present");
    const nS = 4 * present.size; let nP = 0; for (const s of marked.values()) nP += s.size;
    const pct = r10(100 * nP / nS);
    const trace = [present.size + " teeth present x 4 surfaces = " + nS + " surfaces.", "Surfaces with plaque = " + nP + "; PCR = " + nP + "/" + nS + " x 100 = " + pct.toFixed(1) + "%."];
    return result("plaque_control_record", pct, { PCR_percent: pct, surfaces_with_plaque: nP, surfaces_examined: nS, teeth_present: present.size, at_or_below_10_percent: pct <= 10 },
      null, tab.reference_points.map((r) => r.note).join(" "), trace, [], ["oleary1972", "delia2023"]);
  }
  function ohiComponent(data, what, sites) {
    const toothToSite = {}; for (const [s, d] of Object.entries(sites)) for (const t of d.teeth) toothToSite[t] = s;
    const out = {};
    for (const [k, v] of entries(data)) {
      const key = String(k).trim().toUpperCase(); let site, tooth;
      if (sites[key]) { site = key; tooth = sites[key].teeth[0]; }
      else { tooth = parseTooth(k); if (!(tooth in toothToSite)) throw new InputError(what + ": tooth " + tooth + " is not an OHI-S tooth (16/17/18, 11/21, 26/27/28, 36/37/38, 31/41, 46/47/48)"); site = toothToSite[tooth]; }
      if (isBlank(v)) continue;
      if (site in out) throw new InputError(what + ": two scores for the " + site + " site (teeth " + out[site][0] + " and " + tooth + "); score one tooth per site");
      out[site] = [tooth, intScore(v, 0, 3, what + " " + site)];
    }
    return out;
  }
  function ohi_s(o) {
    o = o || {}; requireVerified("ohi_s"); const tab = codes("ohi_s"); const sites = tab.sites;
    const deb = ohiComponent(o.debris, "Debris", sites); const cal = o.calculus !== undefined && o.calculus !== null ? ohiComponent(o.calculus, "Calculus", sites) : {};
    const trace = [], warnings = [], comps = {};
    const comp = (name, d) => {
      const ks = Object.keys(d); if (!ks.length) return null;
      if (ks.length < tab.min_surfaces) throw new InputError(name + ": at least two of the six surfaces must be scored (Greene & Vermillion 1964)");
      const sum = ks.reduce((a, k) => a + d[k][1], 0); const val = sum / ks.length;
      trace.push(name + " = " + sum + "/" + ks.length + " surfaces = " + fmtG(val) + " (teeth: " + ks.map((k) => d[k][0]).join(", ") + ").");
      return val;
    };
    const dis = comp("DI-S", deb); if (dis === null) throw new InputError("OHI-S needs debris scores for at least two surfaces");
    const cis = comp("CI-S", cal);
    comps.DI_S = r10(dis); comps.DI_S_category = band(dis, tab.component_bands, tab.round_to); comps.surfaces_debris = Object.keys(deb).length;
    const subs = Object.keys(sites).filter((s) => s in deb && deb[s][0] !== sites[s].teeth[0]).map((s) => s + "->" + deb[s][0]);
    if (subs.length) trace.push("Substituted teeth: " + subs.join(", ") + ".");
    if (cis === null) { warnings.push("Calculus scores not given: only DI-S is reported."); return result("ohi_s", r10(dis), comps, comps.DI_S_category, null, trace, warnings, ["greene1964"]); }
    comps.CI_S = r10(cis); comps.CI_S_category = band(cis, tab.component_bands, tab.round_to); comps.surfaces_calculus = Object.keys(cal).length;
    const sd = Object.values(deb).reduce((a, v) => a + v[1], 0), nd = Object.keys(deb).length;
    const sc = Object.values(cal).reduce((a, v) => a + v[1], 0), nc = Object.keys(cal).length;
    const total = (sd * nc + sc * nd) / (nd * nc); comps.OHI_S = r10(total);
    trace.push("OHI-S = DI-S + CI-S = " + fmtG(total) + " (read as " + roundHalfUp(total, 1).toFixed(1) + ").");
    warnings.push("Interpretation bands (good/fair/poor) are a textbook convention, not part of the original index.");
    return result("ohi_s", r10(total), comps, band(total, tab.bands, tab.round_to), null, trace, warnings, ["greene1964"]);
  }

  // ------------------------------------------------------------------ wear
  const WSURF = { B: "B", F: "B", BUCCAL: "B", FACIAL: "B", LABIAL: "B", O: "O", I: "O", OCCLUSAL: "O", INCISAL: "O", L: "L", P: "L", LINGUAL: "L", PALATAL: "L", ORAL: "L" };
  function bewe(o) {
    o = o || {}; requireVerified("bewe"); const tab = codes("bewe"); const sx = o.sextants; let vals = {};
    if (sx && !Array.isArray(sx) && typeof sx === "object") { for (const [k, v] of Object.entries(sx)) { const s = parseSextant(k); if (s in vals) throw new InputError("BEWE: sextant " + s + " given twice"); vals[s] = v; } }
    else { const lst = Array.from(sx || []); if (lst.length !== 6) throw new InputError("BEWE: give six sextant scores (17-14, 13-23, 24-27, 37-34, 33-43, 44-47)"); SEXTANT_ORDER.forEach((s, i) => { vals[s] = lst[i]; }); }
    const scores = {};
    for (const s of SEXTANT_ORDER) { const v = vals[s]; scores[s] = isBlank(v) || ["X", "-"].includes(normCode(v)) ? null : intScore(v, 0, 3, "BEWE sextant " + s); }
    const scored = SEXTANT_ORDER.filter((s) => scores[s] !== null);
    if (!scored.length) throw new InputError("BEWE: no sextant was scored");
    const total = scored.reduce((a, s) => a + scores[s], 0); const level = bandEntry(total, tab.risk_levels);
    const warnings = [tab.cutoff_caveat]; if (scored.length < 6) warnings.push("Only " + scored.length + " of 6 sextants were scored; the risk levels assume all six.");
    const trace = ["Sextant scores: " + SEXTANT_ORDER.map((s) => s + " " + (scores[s] !== null ? scores[s] : "-")).join(", ") + ".", "Cumulative BEWE = " + total + " -> risk level " + level.label + "."];
    return result("bewe", total, { BEWE: total, risk_level: level.label, sextants: scores, sextants_scored: scored.length, max_sextant_score: Math.max(...scored.map((s) => scores[s])), repeat: level.repeat },
      level.label, level.management + " " + level.repeat, trace, warnings, ["bartlett2008", "aranguiz2020"]);
  }
  function bewe_from_teeth(o) {
    o = o || {}; requireVerified("bewe"); const tab = codes("bewe"); const toothMax = new Map(), seen = new Set();
    for (const [k, v] of entries(o.scores)) {
      const t = parseTooth(k); if (seen.has(t)) throw new InputError("Tooth " + t + " appears more than once"); seen.add(t);
      if (t > 48) throw new InputError("BEWE is scored on permanent teeth here; " + t + " is a primary tooth");
      if (v !== null && typeof v === "object") {
        const vs = [];
        for (const [sk, sv] of Object.entries(v)) { const key = String(sk).trim().toUpperCase(); if (!WSURF[key]) throw new InputError("Tooth " + t + ": unknown surface " + JSON.stringify(sk) + " (use B, O, L)"); if (!isBlank(sv)) vs.push(intScore(sv, 0, 3, "BEWE tooth " + t + " " + WSURF[key])); }
        if (vs.length) toothMax.set(t, Math.max(...vs));
      } else if (!isBlank(v)) toothMax.set(t, intScore(v, 0, 3, "BEWE tooth " + t));
    }
    const present = o.teeth_present !== undefined && o.teeth_present !== null ? teethSet(o.teeth_present) : new Set(seen);
    const trace = [], members = {}; const third = { S1: [18, 17], S3: [28, 27], S4: [38, 37], S6: [48, 47] };
    for (const [s, teeth] of Object.entries(tab.sextants)) {
      const ts = teeth.filter((t) => toothMax.has(t));
      if (s in third) { const [m3, m2] = third[s]; if (toothMax.has(m3) && !present.has(m2)) { ts.push(m3); trace.push(s + ": third molar " + m3 + " scored because it replaces the missing second molar " + m2 + "."); } }
      members[s] = ts;
    }
    // teeth present per sextant (scored or not) decide the single-tooth rule
    const inSext = {};
    for (const [s, teeth] of Object.entries(tab.sextants)) { const ps = teeth.filter((t) => present.has(t)); if (s in third && present.has(third[s][0]) && !present.has(third[s][1])) ps.push(third[s][0]); inSext[s] = ps; }
    const ign = [18, 28, 38, 48].filter((t) => toothMax.has(t) && !Object.values(members).some((m) => m.includes(t)));
    if (ign.length) trace.push("Third molars not scored (second molar present): " + teethList(ign) + ".");
    const target = { S1: "S2", S3: "S2", S4: "S5", S6: "S5" };
    for (const s of SEXTANT_ORDER) {
      if (inSext[s].length === 1 && members[s].includes(inSext[s][0])) {
        const t = inSext[s][0]; const dest = target[s] || { 1: "S1", 2: "S3", 3: "S4", 4: "S6" }[quadrant(t)];
        if (inSext[dest].length >= 2) { members[dest] = members[dest].concat([t]); members[s] = []; trace.push(s + " has a single tooth (" + t + "); its score is added to " + dest + "."); }
        else trace.push(s + " has a single tooth (" + t + ") and the adjacent sextant " + dest + " has fewer than two teeth, so " + s + " is scored on that tooth.");
      }
    }
    const sext = {}; for (const s of SEXTANT_ORDER) sext[s] = members[s].length ? Math.max(...members[s].map((t) => toothMax.get(t))) : null;
    const r = bewe({ sextants: sext }); r.trace = trace.concat(r.trace); return r;
  }

  // ------------------------------------------------------------------ fluorosis
  const LABEL_TO_WHO = { NORMAL: "0", QUESTIONABLE: "1", "VERY MILD": "2", VERYMILD: "2", MILD: "3", MODERATE: "4", SEVERE: "5" };
  const DEAN_TO_WHO = { 0: "0", 0.5: "1", 1: "2", 2: "3", 3: "4", 4: "5" };
  function whoCode(v, scale, what) {
    if (isBlank(v)) return null;
    if (v && typeof v === "object" && "components" in v) return v.components.who_code;
    if (scale === "dean" && typeof v === "number") { if (String(v) in DEAN_TO_WHO) return DEAN_TO_WHO[String(v)]; throw new InputError(what + ": " + v + " is not a Dean weight (0, 0.5, 1, 2, 3, 4)"); }
    const s = normCode(v);
    if (LABEL_TO_WHO[s]) return LABEL_TO_WHO[s];
    if (scale === "who") { if (s === "8" || s === "9") return null; if (["0", "1", "2", "3", "4", "5"].includes(s)) return s; throw new InputError(what + ": " + JSON.stringify(v) + " is not a WHO 2013 fluorosis code (0-5, 8, 9)"); }
    if (scale === "dean") { const k = Number(s); if (s !== "" && String(k) in DEAN_TO_WHO) return DEAN_TO_WHO[String(k)]; throw new InputError(what + ": " + JSON.stringify(v) + " is not a Dean weight (0, 0.5, 1, 2, 3, 4)"); }
    throw new InputError("scale must be 'who' (codes 0-5) or 'dean' (weights 0, 0.5, 1, 2, 3, 4)");
  }
  function dean_index(o) {
    o = o || {}; requireVerified("dean_index"); const tab = codes("dean"); const scale = o.scale || "who"; const scored = new Map();
    for (const [k, v] of entries(o.teeth)) { const t = parseTooth(k); if (scored.has(t)) throw new InputError("Tooth " + t + " appears more than once"); const c = whoCode(v, scale, "tooth " + t); if (c !== null) scored.set(t, c); }
    if (!scored.size) throw new InputError("Dean's index: no tooth was scored");
    const ranked = Array.from(scored.entries()).sort((a, b) => (parseInt(b[1], 10) - parseInt(a[1], 10)) || (a[0] - b[0]));
    const warnings = []; let code, trace;
    if (ranked.length === 1) { code = ranked[0][1]; warnings.push("Only one tooth was scored; Dean's index is based on the two most affected teeth."); trace = ["Single tooth scored: " + ranked[0][0] + " = " + code + "."]; }
    else { const [[t1, c1], [t2, c2]] = ranked; code = c2; trace = ["Two most affected teeth: " + t1 + " (" + tab.who_codes[c1] + ") and " + t2 + " (" + tab.who_codes[c2] + ").", "Person score = the less affected of the two = " + code + " (" + tab.who_codes[code] + ")."]; }
    return result("dean_index", parseInt(code, 10), { who_code: code, dean_weight: tab.dean_weights[code], label: tab.who_codes[code], teeth_scored: scored.size, fluorosis_present: parseInt(code, 10) >= 2 },
      tab.who_codes[code], null, trace, warnings, ["who2013", "dean1934", "dean1942"]);
  }
  function community_fluorosis_index(o) {
    o = o || {}; requireVerified("community_fluorosis_index"); const tab = codes("cfi"), w = codes("dean").dean_weights, labels = codes("dean").who_codes;
    const cs = seq(o.person_scores, "person_scores").map((v) => whoCode(v, o.scale || "who", "person score")).filter((c) => c !== null);
    if (!cs.length) throw new InputError("CFI: no person scores");
    const n = cs.length, total = cs.reduce((a, c) => a + w[c], 0), cfi = total / n; const cat = band(cfi, tab.bands);
    const dist = {}; for (const c of ["0", "1", "2", "3", "4", "5"]) dist[labels[c]] = cs.filter((x) => x === c).length;
    const trace = ["Counts: " + Object.entries(dist).map(([k, v]) => k + " " + v).join(", ") + ".", "CFI = sum of weights / n = " + fmtG(total) + "/" + n + " = " + fmtG(cfi) + " -> " + cat + "."];
    return result("community_fluorosis_index", r10(cfi), { CFI: r10(cfi), n, distribution: dist, public_health_problem: cfi > tab.public_health_problem_above }, cat, null, trace, [], ["dean1942", "who2013"]);
  }

  // ------------------------------------------------------------------ occlusion
  function dai(o) {
    o = o || {}; requireVerified("dai"); const tab = codes("dai"), w = tab.weights;
    const mm = (v, what) => intScore(v, 0, 30, what + " (whole millimetres)");
    const comp = { missing_visible_teeth: intScore(o.missing_visible_teeth, 0, 20, "missing visible teeth"), crowding: intScore(o.crowding, 0, 2, "crowding (segments)"),
      spacing: intScore(o.spacing, 0, 2, "spacing (segments)"), diastema: mm(o.diastema_mm, "midline diastema"),
      max_anterior_irregularity: mm(o.max_anterior_irregularity_mm, "largest anterior maxillary irregularity"), mand_anterior_irregularity: mm(o.mand_anterior_irregularity_mm, "largest anterior mandibular irregularity"),
      max_overjet: mm(o.max_overjet_mm, "anterior maxillary overjet"), mand_overjet: mm(o.mand_overjet_mm, "anterior mandibular overjet"), openbite: mm(o.openbite_mm, "vertical anterior openbite"),
      molar_relation: intScore(o.molar_relation, 0, 2, "antero-posterior molar relation") };
    const weighted = {}; let sum = 0; for (const k of Object.keys(comp)) { weighted[k] = comp[k] * w[k]; sum += weighted[k]; }
    const sc = sum + tab.constant; const level = bandEntry(sc, tab.bands); const warnings = []; const a = ageValue(o.age);
    if (a !== null && a < 12) warnings.push("WHO recommends the DAI from about age 12, when no primary teeth remain.");
    if (comp.max_overjet && comp.mand_overjet) warnings.push("Both maxillary and mandibular overjet are recorded; check the incisor relationship.");
    const trace = ["Weighted components: " + Object.keys(comp).map((k) => k + " " + comp[k] + " x " + w[k] + " = " + weighted[k]).join(", ") + ".", "DAI = " + sum + " + " + tab.constant + " = " + sc + " -> " + level.label + " (treatment: " + level.treatment + ")."];
    return result("dai", sc, Object.assign({ DAI: sc }, comp, { treatment_indication: level.treatment }), level.label, "Treatment indication: " + level.treatment + ".", trace, warnings, ["cons1986", "jenny1996", "who1997"]);
  }

  // ------------------------------------------------------------------ periodontal charts
  const SITES = ["MB", "B", "DB", "ML", "L", "DL"];
  const SITE_ALIASES = { MB: "MB", MF: "MB", MESIOBUCCAL: "MB", MESIOFACIAL: "MB", B: "B", F: "B", MB_MID: "B", BUCCAL: "B", FACIAL: "B", MIDBUCCAL: "B", MIDFACIAL: "B",
    DB: "DB", DF: "DB", DISTOBUCCAL: "DB", DISTOFACIAL: "DB", ML: "ML", MP: "ML", MO: "ML", MESIOLINGUAL: "ML", MESIOPALATAL: "ML", "MESIO-ORAL": "ML",
    L: "L", P: "L", O: "L", LINGUAL: "L", PALATAL: "L", ORAL: "L", MIDLINGUAL: "L", MIDORAL: "L", DL: "DL", DP: "DL", DO: "DL", DISTOLINGUAL: "DL", DISTOPALATAL: "DL", "DISTO-ORAL": "DL" };
  function site(s) { const k = String(s).trim().toUpperCase().replace(/ /g, ""); if (!SITE_ALIASES[k]) throw new InputError("Unknown probing site " + JSON.stringify(s) + "; use MB, B, DB, ML, L, DL"); return SITE_ALIASES[k]; }
  function toBool(v, what) {
    if (isBlank(v)) return null; if (typeof v === "boolean") return v;
    const s = String(v).trim().toLowerCase();
    if (["1", "true", "yes", "y", "+"].includes(s)) return true; if (["0", "false", "no", "n"].includes(s)) return false;
    throw new InputError(what + ": " + JSON.stringify(v) + " is not yes/no (use True/False or 1/0)");
  }
  class PerioChart {
    constructor() { this.pd = new Map(); this.cal = new Map(); this.bop = new Map(); }
    get teeth() { return Array.from(new Set([...this.pd.keys(), ...this.cal.keys(), ...this.bop.keys()])).sort((a, b) => a - b); }
    _put(store, t, s, v) { if (!store.has(t)) store.set(t, {}); const d = store.get(t); if (s in d) throw new InputError("Tooth " + t + " site " + s + " is recorded twice"); d[s] = v; }
    add(tooth, st, pd, cal, bop) {
      const t = parseTooth(tooth); if (!isPerm(t)) throw new InputError("Periodontal charts here use permanent teeth; " + t + " is a primary tooth");
      const s = site(st);
      if (!isBlank(pd)) this._put(this.pd, t, s, num(pd, "PD tooth " + t + " " + s, 0, 20));
      if (!isBlank(cal)) { const c = num(cal, "CAL tooth " + t + " " + s, null, 25); if (c < 0) throw new InputError("CAL tooth " + t + " " + s + ": " + JSON.stringify(cal) + " is negative; record attachment loss as 0 when the CEJ is not exposed (as NHANES does)"); this._put(this.cal, t, s, c); }
      const b = toBool(bop, "BOP tooth " + t + " " + s); if (b !== null) this._put(this.bop, t, s, b);
    }
    withoutThirdMolars() { const c = new PerioChart(); for (const k of ["pd", "cal", "bop"]) for (const [t, d] of this[k]) if (!isThird(t)) c[k].set(t, Object.assign({}, d)); return c; }
  }
  function perio_chart(data) {
    if (data instanceof PerioChart) return data;
    const ch = new PerioChart();
    if (Array.isArray(data)) {
      for (const row of data) {
        if (!row || typeof row !== "object") throw new InputError("Each row must be a mapping with tooth, site, pd, cal, bop");
        const r = {}; for (const [k, v] of Object.entries(row)) r[String(k).trim().toLowerCase()] = v;
        if (!("tooth" in r) || !("site" in r)) throw new InputError("Each row needs 'tooth' and 'site'");
        ch.add(r.tooth, r.site, r.pd, r.cal, r.bop);
      }
      return ch;
    }
    if (data && typeof data === "object") {
      for (const [k, v] of Object.entries(data)) {
        if (!v || typeof v !== "object" || Array.isArray(v)) throw new InputError("Tooth " + k + ": expected {'pd': {site: mm}, 'cal': {...}, 'bop': {...}}");
        const keys = {}; for (const x of Object.keys(v)) keys[x.toLowerCase()] = x;
        const unknown = Object.keys(keys).filter((x) => !["pd", "cal", "bop"].includes(x));
        if (unknown.length) throw new InputError("Tooth " + k + ": unknown measures " + JSON.stringify(unknown) + "; use pd, cal, bop");
        const sites = new Set(), per = {};
        for (const m of ["pd", "cal", "bop"]) {
          if (!(m in keys)) continue; const block = v[keys[m]];
          if (!block || typeof block !== "object" || Array.isArray(block)) throw new InputError("Tooth " + k + " " + m + ": expected a mapping of site -> value");
          for (const [sk, sv] of Object.entries(block)) { const s = site(sk); per[m] = per[m] || {}; if (s in per[m]) throw new InputError("Tooth " + k + " " + m + ": site " + s + " given twice"); per[m][s] = sv; sites.add(s); }
        }
        for (const s of sites) ch.add(k, s, (per.pd || {})[s], (per.cal || {})[s], (per.bop || {})[s]);
      }
      return ch;
    }
    throw new InputError("Give the chart as a mapping per tooth or as a list of rows");
  }
  function presentSet(ch, tp) {
    if (tp === undefined || tp === null) return new Set(ch.teeth);
    const out = new Set(Array.from(teethSet(tp)).filter(isPerm));
    const miss = ch.teeth.filter((t) => !out.has(t));
    if (miss.length) throw new InputError("Teeth " + teethList(miss) + " have measurements but are not in teeth_present");
    return out;
  }
  function sitesOver(store, sites, th, strict) {
    const out = [];
    for (const [t, d] of store) for (const s of sites) if (s in d && (strict ? d[s] > th : d[s] >= th - 1e-9)) out.push([t, s]);
    return out;
  }
  const teethOf = (sites) => new Set(sites.map(([t]) => t));
  function perio_summary(o) {
    o = o || {}; requireVerified("perio_summary"); let ch = perio_chart(o.chart); const incl = !!o.include_third_molars;
    if (!incl) ch = ch.withoutThirdMolars();
    const flat = (store) => { const a = []; for (const d of store.values()) a.push(...Object.values(d)); return a; };
    const pds = flat(ch.pd), cals = flat(ch.cal), bops = flat(ch.bop);
    const pct = (xs, th) => (xs.length ? r10(100 * xs.filter((x) => x >= th - 1e-9).length / xs.length) : null);
    const mean = (xs) => (xs.length ? r10(xs.reduce((a, b) => a + b, 0) / xs.length) : null);
    const comps = { teeth: ch.teeth.length, sites_pd: pds.length, sites_cal: cals.length, sites_bop: bops.length, mean_pd: mean(pds), max_pd: pds.length ? Math.max(...pds) : null,
      mean_cal: mean(cals), max_cal: cals.length ? Math.max(...cals) : null, percent_sites_pd_4plus: pct(pds, 4), percent_sites_pd_6plus: pct(pds, 6),
      percent_sites_cal_3plus: pct(cals, 3), percent_sites_cal_5plus: pct(cals, 5), percent_sites_bop: bops.length ? r10(100 * bops.filter(Boolean).length / bops.length) : null, third_molars_included: incl };
    return result("perio_summary", comps.mean_cal, comps, null, null, [ch.teeth.length + " teeth; " + pds.length + " PD, " + cals.length + " CAL and " + bops.length + " BOP site measurements" + (incl ? "" : " (third molars excluded)") + "."], [], ["holtfreter2015", "holtfreter2024"]);
  }
  function cdc_aap(o) {
    o = o || {}; requireVerified("cdc_aap"); const tab = codes("cdc_aap"); const ch0 = perio_chart(o.chart);
    const distinct = o.mild_cal_distinct_teeth === undefined || o.mild_cal_distinct_teeth === null ? true : !!o.mild_cal_distinct_teeth;
    const pd5Any = !!o.mild_pd5_any_site;
    const present = new Set(Array.from(presentSet(ch0, o.teeth_present)).filter((t) => !isThird(t))); const ch = ch0.withoutThirdMolars();
    const ip = tab.interproximal_sites; const trace = ["Interproximal sites only (MB, DB, ML, DL); third molars excluded."];
    const teethCal = new Set(Array.from(ch.cal.entries()).filter(([, d]) => ip.some((s) => s in d)).map(([t]) => t));
    const res = (value, cat, comps, warn) => {
      if (!("total_periodontitis" in comps)) comps.total_periodontitis = ["mild", "moderate", "severe"].includes(value);
      if (!("moderate_or_severe" in comps)) comps.moderate_or_severe = ["moderate", "severe"].includes(value);
      return result("cdc_aap", value, comps, cat, null, trace, warn || [], ["page2007", "eke2012"]);
    };
    if (!present.size) { trace.push("No natural teeth (third molars aside): edentulous."); return res("edentulous", "Edentulous", { teeth_with_interproximal_cal: 0 }); }
    if (teethCal.size < 2) { trace.push("Only " + teethCal.size + " tooth/teeth with interproximal CAL: non-classified."); return res("non-classified", "Non-classified", { teeth_with_interproximal_cal: teethCal.size }); }
    const sv = tab.severe, md = tab.moderate, ml = tab.mild;
    const cal6 = sitesOver(ch.cal, ip, sv.cal_mm), pd5 = sitesOver(ch.pd, ip, sv.pd_mm), cal4 = sitesOver(ch.cal, ip, md.cal_mm), cal3 = sitesOver(ch.cal, ip, ml.cal_mm), pd4 = sitesOver(ch.pd, ip, ml.pd_mm);
    const severe = teethOf(cal6).size >= sv.cal_teeth && pd5.length >= sv.pd_sites;
    const moderate = teethOf(cal4).size >= md.cal_teeth || teethOf(pd5).size >= md.pd_teeth;
    const cal3ok = (distinct ? teethOf(cal3).size : cal3.length) >= ml.cal_sites;
    const pd5Mild = pd5Any ? sitesOver(ch.pd, SITES, sv.pd_mm) : pd5;
    const mild = cal3ok && (teethOf(pd4).size >= ml.pd_teeth || pd5Mild.length >= 1);
    trace.push("Teeth with interproximal CAL >= 6: " + teethList(teethOf(cal6)) + "; sites with PD >= 5: " + pd5.length + ".");
    trace.push("Teeth with interproximal CAL >= 4: " + teethList(teethOf(cal4)) + "; teeth with PD >= 5: " + teethList(teethOf(pd5)) + ".");
    trace.push("CAL >= 3: " + cal3.length + " sites on " + teethOf(cal3).size + " teeth; teeth with PD >= 4: " + teethList(teethOf(pd4)) + ".");
    let value, cat;
    if (severe) { value = "severe"; cat = "Severe periodontitis"; } else if (moderate) { value = "moderate"; cat = "Moderate periodontitis"; }
    else if (mild) { value = "mild"; cat = "Mild periodontitis"; } else { value = "no periodontitis"; cat = "No periodontitis"; }
    trace.push("Classification: " + cat + " (severe " + (severe ? "True" : "False") + ", moderate " + (moderate ? "True" : "False") + ", mild " + (mild ? "True" : "False") + ").");
    const comps = { severe_criteria: severe, moderate_criteria: moderate, mild_criteria: mild, teeth_with_interproximal_cal: teethCal.size, teeth_cal6: teethOf(cal6).size, sites_pd5: pd5.length,
      teeth_cal4: teethOf(cal4).size, teeth_pd5: teethOf(pd5).size, sites_cal3: cal3.length, teeth_cal3: teethOf(cal3).size, teeth_pd4: teethOf(pd4).size, mild_cal_distinct_teeth: distinct, mild_pd5_any_site: pd5Any };
    const spt = Array.from(ch.cal.values()).map((d) => ip.filter((s) => s in d).length);
    const warn = spt.length && Math.min(...spt) < 4 ? ["Some teeth have fewer than four interproximal sites recorded (partial recording lowers CDC/AAP prevalence)."] : [];
    return res(value, cat, comps, warn);
  }
  const LOSS = { "0": 0, NONE: 0, "1-4": 1, "1–4": 1, ">=5": 5, "≥5": 5, "5+": 5, UNKNOWN: null };
  function teethLost(v) {
    if (v === null || v === undefined) return null;
    if (typeof v === "boolean") throw new InputError("teeth_lost_to_periodontitis must be a number or '0', '1-4', '>=5', 'unknown'");
    if (typeof v === "number") { if (!Number.isInteger(v) || v < 0 || v > 28) throw new InputError("teeth_lost_to_periodontitis must be 0-28"); return v === 0 ? 0 : (v <= 4 ? 1 : 5); }
    const s = String(v).trim().toUpperCase().replace(/ /g, "");
    if (s in LOSS) return LOSS[s];
    if (/^\d+$/.test(s)) return teethLost(parseInt(s, 10));
    throw new InputError("teeth_lost_to_periodontitis: " + JSON.stringify(v) + "; use a number or '0', '1-4', '>=5', 'unknown'");
  }
  function grade(baseRatio, cig, smoker, diabetes, hba1c, trace, warnings) {
    const g = codes("grade"); const order = "ABC"; let gr, basis, assumed;
    if (baseRatio === null) { gr = g.default; basis = "assumed grade B (no evidence of progression available)"; assumed = true; trace.push("Grade: no bone-loss/age evidence, so grade B is assumed (Tonetti 2018)."); }
    else {
      const r = g.bone_loss_age_ratio; gr = baseRatio < r.A_below ? "A" : (baseRatio <= r.B_upto + 1e-12 ? "B" : "C");
      basis = "bone loss/age ratio " + baseRatio.toFixed(3); assumed = false;
      trace.push("Grade from indirect evidence: %bone loss / age = " + baseRatio.toFixed(3) + " -> grade " + gr + " (A < " + r.A_below + ", B " + r.A_below + "-" + r.B_upto + ", C > " + r.B_upto + ").");
    }
    let c = null; if (cig !== null && cig !== undefined && !isBlank(cig)) c = num(cig, "cigarettes per day", 0, 200);
    const sm = smoker !== null && smoker !== undefined ? toBool(smoker, "smoker") : null; let mod = null;
    if (c === null && sm === true) { warnings.push("Smoker without cigarettes per day: the smoking modifier needs the daily amount; grade B is the minimum applied."); mod = "B"; }
    else if (c !== null) mod = c === 0 ? "A" : (c < g.smoking_cigarettes_per_day_C ? "B" : "C");
    if (mod && order.indexOf(mod) > order.indexOf(gr)) { trace.push("Smoking (" + (c === null ? "unknown amount" : fmtG(c) + "/day") + ") raises the grade to " + mod + "."); gr = mod; }
    const dm = diabetes !== null && diabetes !== undefined ? toBool(diabetes, "diabetes") : null;
    const hb = hba1c !== null && hba1c !== undefined && !isBlank(hba1c) ? num(hba1c, "HbA1c (%)", 3, 20) : null;
    if (dm) {
      let dmod; if (hb === null) { warnings.push("Diabetes without HbA1c: grade B is the minimum applied; give HbA1c to apply the full modifier."); dmod = "B"; } else dmod = hb < g.hba1c_percent_C ? "B" : "C";
      if (order.indexOf(dmod) > order.indexOf(gr)) { trace.push("Diabetes (HbA1c " + (hb === null ? "unknown" : fmtG(hb) + "%") + ") raises the grade to " + dmod + "."); gr = dmod; }
    }
    return [gr, basis, assumed];
  }
  function aces(o) {
    o = o || {}; requireVerified("aces"); const tab = codes("aces"); const survey = o.survey || "completed";
    if (!["completed", "planned"].includes(survey)) throw new InputError("survey must be 'completed' or 'planned'");
    const ch0 = perio_chart(o.chart); const present = new Set(Array.from(presentSet(ch0, o.teeth_present)).filter((t) => !isThird(t))); const ch = ch0.withoutThirdMolars();
    const ids = tab.interdental_sites, mids = tab.mid_sites; const trace = ["Six-site chart, third molars excluded (ACES 2024)."]; const warnings = [];
    const src = ["holtfreter2024", "tonetti2018", "papapanou2018", "chapple2018"];
    const out = (status, cat, comps) => { if (!("status" in comps)) comps.status = status; return result("aces", status, comps, cat, null, trace, warnings, src); };
    if (!present.size) { trace.push("No natural teeth: edentulous (ACES asks that edentulism always be reported)."); return out("edentulous", "Edentulous", { stage: null, grade: null }); }
    const interdental = Array.from(ch.cal.entries()).filter(([, d]) => ids.some((s) => s in d)).map(([t]) => t);
    const midTeeth = ch.teeth.filter((t) => mids.some((s) => ch.cal.has(t) && s in ch.cal.get(t) && ch.pd.has(t) && s in ch.pd.get(t)));
    const canInterdental = hasNonAdjacentPair(interdental), canMid = midTeeth.length >= tab.case.min_teeth_mid;
    const c = tab.case; const idcal = teethOf(sitesOver(ch.cal, ids, c.interdental_cal_mm)); const critA = hasNonAdjacentPair(idcal);
    const midHits = new Set();
    for (const t of ch.teeth) for (const s of mids) { const cv = ch.cal.has(t) ? ch.cal.get(t)[s] : undefined, pv = ch.pd.has(t) ? ch.pd.get(t)[s] : undefined; if (cv !== undefined && pv !== undefined && cv >= c.mid_cal_mm - 1e-9 && pv > c.mid_pd_over_mm) midHits.add(t); }
    const critB = midHits.size >= c.min_teeth_mid;
    trace.push("Interdental CAL >= 1 mm at " + teethList(idcal) + " -> non-adjacent pair: " + (critA ? "True" : "False") + ".");
    trace.push("Buccal/oral CAL >= 3 mm with PD > 3 mm at the same site: " + teethList(midHits) + " -> >= 2 teeth: " + (critB ? "True" : "False") + ".");
    if (!(critA || critB) && !(canInterdental && canMid)) { trace.push("No case criterion met, and fewer than two non-adjacent teeth with interdental CAL or fewer than two teeth with buccal/oral CAL and PD: non-classified."); return out("non-classified", "Non-classified", { stage: null, grade: null, non_classified_reason: "too few qualifying teeth" }); }
    let bp = null, bsrc = "";
    if (o.bleeding_percent !== undefined && o.bleeding_percent !== null && !isBlank(o.bleeding_percent)) { bp = num(o.bleeding_percent, "bleeding_percent", 0, 100); bsrc = "given"; }
    else { const bops = []; for (const d of ch.bop.values()) bops.push(...Object.values(d)); if (bops.length) { const k = bops.filter(Boolean).length; bp = 100 * k / bops.length; bsrc = k + " of " + bops.length + " sites"; } }
    const pds = []; for (const d of ch.pd.values()) pds.push(...Object.values(d)); const maxPd = pds.length ? Math.max(...pds) : null;
    if (!(critA || critB)) {
      const hb = tab.bleeding_bands_percent;
      const comps = { stage: null, grade: null, bleeding_percent: bp === null ? null : r10(bp), max_pd: maxPd, pseudo_pockets: maxPd !== null && maxPd >= 4 };
      if (maxPd !== null && maxPd >= 4) trace.push("PD >= 4 mm without attachment loss (pseudo-pockets): classified by gingival inflammation.");
      if (bp === null) { trace.push("Not a periodontitis case; no bleeding data, so health and gingivitis cannot be separated."); return out("health or gingivitis", "Periodontal health or gingivitis (no bleeding data)", comps); }
      let st, cat;
      if (bp < hb.health_below) { st = "health"; cat = "Periodontal health"; } else if (bp <= hb.localized_upto + 1e-9) { st = "localized gingivitis"; cat = "Localized gingivitis"; } else { st = "generalized gingivitis"; cat = "Generalized gingivitis"; }
      trace.push("Not a periodontitis case; bleeding at " + bp.toFixed(1) + "% of sites (" + bsrc + ") -> " + cat + " (<10% health, 10-30% localized, >30% generalized).");
      return out(st, cat, comps);
    }
    const idVals = []; for (const d of ch.cal.values()) for (const [s, v] of Object.entries(d)) if (ids.includes(s)) idVals.push(v);
    const maxId = idVals.length ? Math.max(...idVals) : 0; const bands = tab.stage_cal_bands_mm; let bandStage;
    if (maxId >= bands.III[0] - 1e-9) bandStage = "III"; else if (maxId >= bands.II[0] - 1e-9) bandStage = "II";
    else { bandStage = "I"; if (maxId < bands.I[0] - 1e-9) warnings.push("Case met through the buccal/oral criterion while maximum interdental CAL is below 1 mm; stage I assigned (interpretation)."); }
    trace.push("Maximum interdental CAL " + fmtG(maxId) + " mm -> initial stage " + bandStage + " (1-2 mm I, 3-4 mm II, >= 5 mm III).");
    const cx = tab.complexity; const pd6Sites = [];
    for (const [t, d] of ch.pd) for (const [s, v] of Object.entries(d)) { if (SECOND.includes(t) && (s === "DB" || s === "DL")) continue; if (v >= cx.pd_mm - 1e-9) pd6Sites.push([t, s]); }
    const pd6 = hasNonAdjacentPair(teethOf(pd6Sites)); const opp = opposingPairs(present);
    const fi = o.furcation_class_2_3 !== undefined && o.furcation_class_2_3 !== null ? toBool(o.furcation_class_2_3, "furcation_class_2_3") : null;
    const vbl = o.vertical_bone_loss_3mm !== undefined && o.vertical_bone_loss_3mm !== null ? toBool(o.vertical_bone_loss_3mm, "vertical_bone_loss_3mm") : null;
    const s3 = !!(pd6 || fi || vbl); const pyb = (b) => (b === null ? "None" : (b ? "True" : "False"));
    trace.push("PD >= 6 mm at non-adjacent teeth (third molars, distal sites of second molars disregarded): " + pyb(pd6) + " (" + teethList(teethOf(pd6Sites)) + "); furcation II/III: " + pyb(fi) + "; vertical bone loss >= 3 mm: " + pyb(vbl) + ".");
    trace.push("Opposing pairs of natural teeth: " + opp + " (" + (opp < cx.min_opposing_pairs ? "< 10" : ">= 10") + ").");
    const few = opp < cx.min_opposing_pairs; let lost = null, stage, pairsDecided = false;
    if (survey === "completed") {
      if (o.teeth_lost_to_periodontitis !== undefined && o.teeth_lost_to_periodontitis !== null) warnings.push("Teeth lost to periodontitis are not used for completed surveys (ACES Figure 2); use survey='planned' if this was collected with validated questions.");
      stage = bandStage === "I" ? "I" : (bandStage === "II" ? (s3 ? "III" : "II") : (few ? "IV" : "III"));
      if (bandStage === "III") pairsDecided = few;
    } else {
      lost = teethLost(o.teeth_lost_to_periodontitis);
      const mob = o.mobility_degree2_at_2_teeth !== undefined && o.mobility_degree2_at_2_teeth !== null ? toBool(o.mobility_degree2_at_2_teeth, "mobility_degree2_at_2_teeth") : null;
      const bite = o.bite_collapse_drifting_flaring !== undefined && o.bite_collapse_drifting_flaring !== null ? toBool(o.bite_collapse_drifting_flaring, "bite_collapse_drifting_flaring") : null;
      trace.push("Teeth lost to periodontitis: " + ({ null: "unknown", 0: "none", 1: "1-4", 5: "5 or more" })[String(lost)] + "; mobility >= 2 at >= 2 teeth: " + pyb(mob) + "; bite collapse/drifting/flaring: " + pyb(bite) + ".");
      if (bandStage === "I") {
        if (lost === 1) stage = "III";
        else if (lost === 5) { stage = "IV"; warnings.push("Interdental CAL 1-2 mm with 5 or more teeth lost to periodontitis is not covered by ACES Figure 3; stage IV assigned from the tooth-loss criterion (Tonetti 2018)."); }
        else stage = "I";
      } else if (bandStage === "II") stage = lost === 5 ? "IV" : ((lost === 1 || s3) ? "III" : "II");
      else stage = lost === 5 ? "IV" : "III";
      if (stage === "III" && (mob || bite || few)) { pairsDecided = !!(few && !(mob || bite)); stage = "IV"; trace.push("Stage IV complexity (mobility, bite collapse/drifting/flaring or < 10 opposing pairs) applied to stage III."); }
    }
    trace.push("Stage " + stage + " (" + survey + " survey).");
    if (pairsDecided && (o.teeth_present === undefined || o.teeth_present === null)) warnings.push("Opposing pairs were counted from the charted teeth because teeth_present was not given. For a partial-mouth recording, give teeth_present (every natural tooth present); otherwise the fewer-than-10-pairs rule can wrongly raise the stage to IV.");
    const thr = tab.extent_severity_cal_mm[bandStage]; const toothMax = new Map();
    for (const [t, d] of ch.cal) { const v = ids.filter((s) => s in d).map((s) => d[s]); if (v.length) toothMax.set(t, Math.max(...v)); }
    const affected = Array.from(toothMax.entries()).filter(([, m]) => m >= thr - 1e-9).map(([t]) => t).sort((a, b) => a - b);
    const extPct = toothMax.size ? 100 * affected.length / toothMax.size : null;
    const extent = extPct === null ? null : (extPct >= tab.extent_generalized_percent - 1e-9 ? "generalized" : "localized");
    const mip = affected.length > 0 && affected.every((t) => [1, 2, 6].includes(position(t)));
    trace.push(extPct !== null ? "Extent: " + affected.length + " of " + toothMax.size + " teeth with interdental CAL >= " + thr + " mm (" + extPct.toFixed(1) + "%) -> " + extent + " (< 30% localized)." : "Extent: no data.");
    const a = ageValue(o.age); let ratio = null, ev = null;
    if (o.bone_loss_percent !== undefined && o.bone_loss_percent !== null && !isBlank(o.bone_loss_percent)) {
      const blp = num(o.bone_loss_percent, "bone_loss_percent", 0, 100);
      if (a === null || a <= 0) warnings.push("bone_loss_percent needs the age to compute bone loss / age."); else { ratio = blp / a; ev = "radiographic bone loss " + fmtG(blp) + "% at the worst tooth"; }
    } else if (o.root_length_mm !== undefined && o.root_length_mm !== null) {
      if (typeof o.root_length_mm !== "object" || Array.isArray(o.root_length_mm)) throw new InputError("root_length_mm must map teeth to root lengths in mm");
      const rl = new Map(); for (const [k, v] of Object.entries(o.root_length_mm)) { const t = parseTooth(k); if (rl.has(t)) throw new InputError("Tooth " + t + " appears more than once in the root_length_mm input"); rl.set(t, num(v, "root length " + t, 1, 40)); }
      const rel = new Map(); for (const [t, L] of rl) { if (!ch.cal.has(t)) continue; const v = ids.filter((s) => s in ch.cal.get(t)).map((s) => ch.cal.get(t)[s]); if (v.length) rel.set(t, 100 * Math.max(...v) / L); }
      if (rel.size && a !== null && a > 0) { let worst = null; for (const [t, v] of rel) if (worst === null || v > rel.get(worst) || (v === rel.get(worst) && t < worst)) worst = t; ratio = rel.get(worst) / a; ev = "worst interdental CAL is " + rel.get(worst).toFixed(1) + "% of the root length at tooth " + worst; }
      else if (rel.size) warnings.push("Relative CAL needs the age to compute the bone loss / age ratio.");
    }
    if (ev) trace.push("Indirect evidence: " + ev + ".");
    const [gr, basis, assumed] = grade(ratio, o.cigarettes_per_day, o.smoker, o.diabetes, o.hba1c, trace, warnings);
    let cat = "Stage " + stage + (extent ? ", " + extent : "") + ", grade " + gr;
    if (mip) warnings.push("All affected teeth are incisors or first molars: consider the molar-incisor pattern (Papapanou 2018).");
    const comps = { stage, stage_cal_only: bandStage !== "III" ? bandStage : "III/IV", extent, extent_percent: extPct === null ? null : r10(extPct), affected_teeth: affected,
      molar_incisor_pattern_possible: mip, grade: gr, grade_basis: basis, grade_assumed: assumed, bone_loss_age_ratio: ratio === null ? null : r10(ratio), max_interdental_cal: maxId,
      case_interdental: critA, case_buccal_oral: critB, pd6_non_adjacent: pd6, furcation_class_2_3: fi, vertical_bone_loss_3mm: vbl, opposing_pairs: opp, survey,
      teeth_lost_to_periodontitis: survey === "completed" ? null : ({ null: "unknown", 0: "0", 1: "1-4", 5: ">=5" })[String(lost)], bleeding_percent: bp === null ? null : r10(bp), max_pd: maxPd };
    return out("periodontitis", cat, comps);
  }

  // ------------------------------------------------------------------ CSV + survey processing (browser)
  function parseCSV(text) {
    text = String(text).replace(/^﻿/, "");
    const first = text.split(/\r?\n/, 1)[0] || "";
    const delim = [",", ";", "\t"].map((d) => [d, first.split(d).length]).sort((a, b) => b[1] - a[1])[0][0];
    const rows = []; let row = [], field = "", inQ = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (inQ) { if (ch === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else inQ = false; } else field += ch; }
      else if (ch === '"' && field === "") inQ = true;  // a quote only opens a quoted field at its start
      else if (ch === delim) { row.push(field); field = ""; }
      else if (ch === "\n" || ch === "\r") { if (ch === "\r" && text[i + 1] === "\n") i++; row.push(field); rows.push(row); row = []; field = ""; }
      else field += ch;
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    const nonEmpty = rows.filter((r) => r.some((c) => c.trim() !== ""));
    if (!nonEmpty.length) return [];
    const head = nonEmpty[0].map((h) => h.trim());
    const dup = Array.from(new Set(head.filter((h, i) => h && head.indexOf(h) !== i))).sort();
    if (dup.length) throw new InputError("The header names these columns more than once: " + dup.join(", "));
    const out = nonEmpty.slice(1).map((r) => { const o = {}; head.forEach((h, i) => { o[h] = (r[i] === undefined ? "" : r[i]).trim(); }); return o; });
    // JavaScript objects list integer-like keys (tooth columns) first; keep the file's column order here.
    Object.defineProperty(out, "columns", { value: head.slice(), enumerable: false });
    return out;
  }
  // File bytes -> text: UTF-8, else Windows-1252, or Windows-1254 when the text is evidently Turkish
  // (the same rule as the Python engine's decode_text()).
  function decodeText(buffer) {
    try { return new TextDecoder("utf-8", { fatal: true }).decode(buffer); }
    catch (e) {
      const text = new TextDecoder("windows-1252").decode(buffer);
      return /[ÐÝÞðýþ]/.test(text) ? new TextDecoder("windows-1254").decode(buffer) : text;
    }
  }
  function columnOrder(rows, first) {
    const cols = []; for (const k of first || []) if (!cols.includes(k) && rows.some((r) => k in r)) cols.push(k);
    for (const r of rows) for (const k of Object.keys(r)) if (!cols.includes(k)) cols.push(k);
    return cols;
  }
  function toCSV(rows, first) {
    const cols = columnOrder(rows, first);
    const fmt = (v) => { if (v === true) return "TRUE"; if (v === false) return "FALSE"; if (v === null || v === undefined) return ""; if (typeof v === "number" && !Number.isInteger(v)) return String(Number(v.toPrecision(6))); if (typeof v === "object") return ""; const t = String(v); return /^[=+@\t\r]/.test(t) || (t.length > 1 && t[0] === "-" && !NUMBER_RE.test(t)) ? "'" + t : t; };
    const esc = (s) => (/[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s);
    return [cols.join(",")].concat(rows.map((r) => cols.map((c) => esc(fmt(r[c]))).join(","))).join("\n") + "\n";
  }
  function row(r) {
    const out = { [r.index]: r.value }; if (r.category !== null) out[r.index + "_category"] = r.category;
    for (const [k, v] of Object.entries(r.components)) if (v === null || ["number", "string", "boolean"].includes(typeof v)) out[k] = v;
    return out;
  }
  const TOOTH_INDICES = ["dmft_permanent", "dmft_primary", "caries_experience", "pufa", "dean_index"];
  const SEXTANT_INDICES = ["bpe", "bewe", "cpitn", "loss_of_attachment"];
  function isToothCol(k) { try { parseTooth(k); return true; } catch (e) { return false; } }
  function isSextCol(k) { try { parseSextant(k); return true; } catch (e) { return false; } }
  function checkDuplicates(cols, parse, what) {
    const seen = new Map();
    for (const k of cols) { const v = parse(k); if (seen.has(v)) throw new InputError("Columns " + JSON.stringify(seen.get(v)) + " and " + JSON.stringify(k) + " are the same " + what + " (" + v + ")"); seen.set(v, k); }
  }
  function rowsOf(rows) {
    const out = seq(rows, "rows");
    out.forEach((r, i) => { if (r === null || typeof r !== "object" || Array.isArray(r)) throw new InputError("Row " + (i + 1) + " is not a mapping of column -> value (use parseCSV() to read a file)"); });
    return out;
  }
  function batch(o) {
    o = o || {}; const index = o.index; const ageCol = o.age_col === undefined ? "age" : o.age_col; const options = o.options || {};
    if (!TOOTH_INDICES.includes(index) && !SEXTANT_INDICES.includes(index) && index !== "dai") throw new InputError("batch() does not handle " + JSON.stringify(index) + "; for periodontal charts use batch_perio()");
    return rowsOf(o.rows).map((r) => {
      const tcols = TOOTH_INDICES.includes(index) ? Object.keys(r).filter(isToothCol) : [];
      const scols = SEXTANT_INDICES.includes(index) ? Object.keys(r).filter(isSextCol) : [];
      const res = {}; for (const k of Object.keys(r)) if (!tcols.includes(k) && !scols.includes(k)) res[k] = r[k];
      try {
        checkDuplicates(tcols, parseTooth, "tooth"); checkDuplicates(scols, parseSextant, "sextant");
        const age = ageCol && !isBlank(r[ageCol]) ? r[ageCol] : null; let x;
        if (TOOTH_INDICES.includes(index)) {
          const teeth = {}; for (const k of tcols) if (!isBlank(r[k])) teeth[parseTooth(k)] = r[k];
          if (index === "dmft_permanent") x = dmft_permanent(Object.assign({ codes: teeth, age }, options));
          else if (index === "dmft_primary") x = dmft_primary({ codes: teeth });
          else if (index === "pufa") x = pufa(Object.assign({ codes: teeth }, options));
          else if (index === "dean_index") x = dean_index(Object.assign({ teeth }, options));
          else { const both = caries_experience(Object.assign({ codes: teeth, age }, options)); Object.assign(res, row(both.permanent), row(both.primary)); res.warnings = both.permanent.warnings.concat(both.primary.warnings).join(" | "); return res; }
        } else if (SEXTANT_INDICES.includes(index)) {
          const sext = {}; for (const k of scols) sext[parseSextant(k)] = r[k];
          if (index === "bpe") x = bpe({ sextants: sext }); else if (index === "bewe") x = bewe({ sextants: sext });
          else if (index === "cpitn") x = cpitn({ sextants: sext, age }); else x = loss_of_attachment({ sextants: sext, age });
        } else {
          const names = ["missing_visible_teeth", "crowding", "spacing", "diastema_mm", "max_anterior_irregularity_mm", "mand_anterior_irregularity_mm", "max_overjet_mm", "mand_overjet_mm", "openbite_mm", "molar_relation"];
          const lower = {}; for (const [k, v] of Object.entries(r)) lower[String(k).trim().toLowerCase()] = v;
          const miss = names.filter((n) => !(n in lower)); if (miss.length) throw new InputError("DAI columns missing: " + miss.join(", "));
          const args = { age }; for (const n of names) args[n] = lower[n]; x = dai(args);
        }
        Object.assign(res, row(x)); res.warnings = x.warnings.join(" | ");
      } catch (e) { if (o.on_error === "raise") throw e; res.error = e.message; }
      return res;
    });
  }
  const CDC_OPTIONS = ["mild_cal_distinct_teeth", "mild_pd5_any_site"];
  const ACES_OPTIONS = ["survey", "age", "bleeding_percent", "furcation_class_2_3", "vertical_bone_loss_3mm", "teeth_lost_to_periodontitis", "mobility_degree2_at_2_teeth", "bite_collapse_drifting_flaring", "bone_loss_percent", "root_length_mm", "cigarettes_per_day", "smoker", "diabetes", "hba1c"];
  function batch_perio(o) {
    o = o || {}; const idCol = o.id_col || "id"; const indices = o.indices || ["cdc_aap", "aces", "perio_summary"]; const groups = new Map();
    const acesOpts = o.aces_options || {}, cdcOpts = o.cdc_options || {};
    const badA = Object.keys(acesOpts).filter((k) => !ACES_OPTIONS.includes(k)).sort();
    if (badA.length) throw new InputError("Unknown ACES option(s): " + badA.join(", ") + (badA.includes("teeth_present") ? " (teeth_present comes from the 'teeth_present' column)" : ""));
    const badC = Object.keys(cdcOpts).filter((k) => !CDC_OPTIONS.includes(k)).sort();
    if (badC.length) throw new InputError("Unknown CDC/AAP option(s): " + badC.join(", ") + "; use " + CDC_OPTIONS.join(", "));
    const allRows = rowsOf(o.rows);
    const cols = new Set(); for (const r of allRows) for (const k of Object.keys(r)) cols.add(String(k).trim().toLowerCase());
    if (allRows.length && !(cols.has("tooth") && cols.has("site"))) throw new InputError("A periodontal chart needs 'tooth' and 'site' columns (one row per tooth and site), plus 'pd', 'cal' and optionally 'bop'");
    for (const r of allRows) { const key = String(r[idCol] === undefined ? "" : r[idCol]).trim(); if (!key) throw new InputError("Every row needs a value in the " + JSON.stringify(idCol) + " column"); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(r); }
    const pf = ["age", "cigarettes_per_day", "smoker", "diabetes", "hba1c", "bleeding_percent", "bone_loss_percent", "furcation_class_2_3", "vertical_bone_loss_3mm", "teeth_lost_to_periodontitis", "mobility_degree2_at_2_teeth", "bite_collapse_drifting_flaring"];
    const out = [];
    for (const [key, rws] of groups) {
      const res = { [idCol]: key };
      try {
        const low = rws.map((r) => { const x = {}; for (const [k, v] of Object.entries(r)) x[String(k).trim().toLowerCase()] = v; return x; });
        const chart = perio_chart(low.filter((r) => !isBlank(r.tooth) && !isBlank(r.site)));
        const person = {}; for (const f of pf) for (const r of low) if (!isBlank(r[f])) { person[f] = r[f]; break; }
        let present = null; for (const r of low) if (!isBlank(r.teeth_present)) { present = String(r.teeth_present).replace(/[;,]/g, " ").split(/\s+/).filter(Boolean); break; }
        if ("teeth_lost_to_periodontitis" in person && /^\d+$/.test(String(person.teeth_lost_to_periodontitis))) person.teeth_lost_to_periodontitis = parseInt(person.teeth_lost_to_periodontitis, 10);
        if (indices.includes("cdc_aap")) res.cdc_aap = cdc_aap(Object.assign({ chart, teeth_present: present }, cdcOpts)).value;
        if (indices.includes("aces")) {
          const r = aces(Object.assign({ chart, teeth_present: present }, person, acesOpts));
          res.aces_status = r.value;
          for (const k of ["stage", "extent", "extent_percent", "grade", "grade_assumed", "max_interdental_cal", "opposing_pairs", "bleeding_percent"]) res["aces_" + k] = k in r.components ? r.components[k] : null;
          res.aces_warnings = r.warnings.join(" | ");
        }
        if (indices.includes("perio_summary")) { const r = perio_summary({ chart }); for (const [k, v] of Object.entries(r.components)) if (k !== "third_molars_included") res[k] = v; }
      } catch (e) { if (o.on_error === "raise") throw e; res.error = e.message; }
      out.push(res);
    }
    return out;
  }
  function summary_table(o) {
    o = o || {}; const rows = rowsOf(o.rows); const column = o.column; const keys = o.by ? (Array.isArray(o.by) ? o.by : [o.by]) : [];
    if (!keys.every((k) => typeof k === "string")) throw new InputError("by must name one column or a list of column names");
    const incl = o.include_sic === undefined || o.include_sic === null ? /^(dmft|dmfs)(_permanent|_primary)?$/i.test(String(column)) : !!o.include_sic;
    const conf = o.confidence === undefined ? 0.95 : num(o.confidence, "confidence");
    if (rows.length && !(column in rows[0])) throw new InputError("Column " + JSON.stringify(column) + " not found");
    for (const k of keys) if (rows.length && !rows.some((r) => k in r)) throw new InputError("Grouping column " + JSON.stringify(k) + " not found");
    const groups = new Map();
    for (const r of rows) { if (r.error) continue; const g = JSON.stringify(keys.map((k) => (r[k] === undefined ? "" : r[k]))); if (!groups.has(g)) groups.set(g, []); groups.get(g).push(r[column]); }
    const rowFor = (label, vals) => {
      const s = summarize({ values: vals, confidence: conf, label: column }); const rec = Object.assign({}, label); for (const [k, v] of Object.entries(s)) if (k !== "label") rec[k] = v;
      const vv = vals.filter((v) => !isBlank(v));
      if (incl && vv.length) { rec.SiC = sic({ values: vv }).value; rec.SaC = sac({ values: vv }).value; }
      return rec;
    };
    const out = [];
    if (keys.length) for (const [g, vals] of groups) { const lab = {}; JSON.parse(g).forEach((v, i) => { lab[keys[i]] = v; }); out.push(rowFor(lab, vals)); }
    const all = []; for (const vs of groups.values()) all.push(...vs);
    const lab = {}; if (keys.length) keys.forEach((k) => { lab[k] = "All"; }); else lab.group = "All";
    out.push(rowFor(lab, all));
    return out;
  }

  const api = {
    version: REG.package_version || "1.0.0", registry: REG, InputError, ToothError,
    dmft_permanent, dmft_primary, dmfs_permanent, dmfs_primary, caries_experience, pufa,
    summarize, sic, sac, care_index, restorative_index, component_percentages, who_caries_level,
    bpe, bpe_from_teeth, sbpe, cpitn, cpi_modified, loss_of_attachment,
    plaque_index, gingival_index, plaque_control_record, ohi_s, bewe, bewe_from_teeth, dean_index, community_fluorosis_index, dai,
    perio_chart, cdc_aap, aces, perio_summary, batch, batch_perio, summary_table, parseCSV, toCSV, columnOrder, decodeText, row,
    _internal: { tQuantile, normalQuantile, wilson, roundHalfUp, band, hasNonAdjacentPair, opposingPairs, parseTooth }
  };
  root.DentIndices = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

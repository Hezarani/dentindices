/* DentIndices web app — UI only; every number comes from dentindices.js (the shared engine). */
(function () {
  "use strict";
  const DI = window.DentIndices;
  const REG = DI.registry;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const CONCEPT_DOI = null; // set after the first Zenodo release

  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) n.append(k.nodeType ? k : document.createTextNode(String(k)));
    return n;
  }
  const fmt = (v, d) => {
    if (v === null || v === undefined || v === "") return "–";
    if (typeof v === "boolean") return v ? "yes" : "no";
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(d === undefined ? 2 : d);
    return String(v);
  };
  function shortAuthors(a) {
    const base = a.replace(/\(.*?\)/g, "").trim();
    const parts = base.split(",").map((x) => x.trim()).filter((x) => x && x !== "et al.");
    const surname = (x) => { const t = x.split(/\s+/); return t.length > 1 && /^[A-Z\u00C0-\u017F]{1,4}$/.test(t[t.length - 1]) ? t.slice(0, -1).join(" ") : null; };
    if (parts.length === 1 && !surname(parts[0])) return parts[0].split(/\s+/).filter((w) => /^[A-Z]/.test(w)).map((w) => w[0]).join("");
    const names = parts.map((x) => surname(x) || x);
    if (names.length === 1 && !/et al/.test(base)) return names[0];
    if (names.length === 2 && !/et al/.test(base)) return names[0] + " & " + names[1];
    return names[0] + " et al.";
  }
  function sourceLink(id) {
    const s = REG.sources[id];
    if (!s) return el("span", { text: id });
    const label = shortAuthors(s.authors) + " " + s.year;
    const href = s.doi ? "https://doi.org/" + s.doi : (s.url || (s.pmid ? "https://pubmed.ncbi.nlm.nih.gov/" + s.pmid + "/" : null));
    return href ? el("a", { href, rel: "noopener", title: s.title }, label) : el("span", { title: s.title }, label);
  }
  function sourcesLine(ids) {
    const p = el("p", { class: "srcs" }, "Sources: ");
    ids.forEach((id, i) => { if (i) p.append(" · "); p.append(sourceLink(id)); });
    return p;
  }
  function pillClass(cat) {
    const c = String(cat || "").toLowerCase();
    if (/(very severe|severe|high|poor|stage iv|stage iii|code 4|tn3|marked|very high|deep|generalized gingivitis|mandatory)/.test(c)) return "pill bad";
    if (/(moderate|medium|fair|stage ii|code 3|tn2|definite|borderline|slight|localized gingivitis|shallow|mild gingivitis|low)/.test(c)) return "pill warn";
    if (/(none|excellent|good|normal|health|no |negative|code 0|tn0|very low|minor|no abnormality)/.test(c)) return "pill ok";
    return "pill";
  }
  function traceBlock(r, title) {
    const d = el("details", { class: "trace" }, el("summary", null, title || "How this was calculated"));
    const ol = el("ol"); r.trace.forEach((t) => ol.append(el("li", null, t))); d.append(ol);
    return d;
  }
  function warnList(ws) {
    if (!ws || !ws.length) return null;
    return el("ul", { class: "warns" }, ws.map((w) => el("li", null, w)));
  }
  function kv(pairs) {
    return el("dl", { class: "kv" }, pairs.filter((p) => p).map(([k, v]) => el("div", null, el("dt", null, k), el("dd", null, v))));
  }
  function showError(box, e) {
    box.replaceChildren(el("h2", null, "Result"), el("p", { class: "err", role: "alert" }, e.message || String(e)));
  }
  function render(box, title, r, opts) {
    opts = opts || {};
    const head = el("div", { class: "big" }, el("span", { class: "val" }, opts.value !== undefined ? opts.value : fmt(r.value)), el("span", { class: "lab" }, opts.label || title));
    const parts = [el("h2", { class: "sr-only" }, title), head];
    if (r.category) parts.push(el("p", { style: "margin:10px 0 0" }, el("span", { class: pillClass(r.category) }, r.category)));
    if (opts.extra) parts.push(...[].concat(opts.extra));
    if (opts.kv) parts.push(kv(opts.kv));
    if (r.guidance) parts.push(el("p", { class: "guidance" }, r.guidance));
    const w = warnList(r.warnings); if (w) parts.push(w);
    parts.push(traceBlock(r), sourcesLine(r.sources));
    box.replaceChildren(...parts);
    box.classList.remove("fade-in"); void box.offsetWidth; box.classList.add("fade-in");
  }
  function select(id, options, value, aria) {
    const s = el("select", { id, "aria-label": aria || null });
    for (const o of options) { const [v, t] = Array.isArray(o) ? o : [o, o]; const opt = el("option", { value: v }, t); if (String(v) === String(value)) opt.selected = true; s.append(opt); }
    return s;
  }
  const numOrNull = (v) => (v === "" || v === null || v === undefined ? null : Number(v));

  // ------------------------------------------------------------------ tabs
  const tabs = $$('[role="tab"]');
  function activate(tab, focus) {
    tabs.forEach((t) => { const on = t === tab; t.setAttribute("aria-selected", on); t.tabIndex = on ? 0 : -1; $("#" + t.getAttribute("aria-controls")).hidden = !on; });
    if (focus) tab.focus();
    tab.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => activate(t));
    t.addEventListener("keydown", (e) => {
      let n = null;
      if (e.key === "ArrowRight") n = tabs[(i + 1) % tabs.length];
      else if (e.key === "ArrowLeft") n = tabs[(i + tabs.length - 1) % tabs.length];
      else if (e.key === "Home") n = tabs[0];
      else if (e.key === "End") n = tabs[tabs.length - 1];
      if (n) { e.preventDefault(); activate(n, true); }
    });
  });

  // ------------------------------------------------------------------ caries
  const STATUSES = [
    { key: "0", label: "Sound", perm: "0", prim: "A" }, { key: "1", label: "Caries", perm: "1", prim: "B" },
    { key: "2", label: "Filled, with caries", perm: "2", prim: "C" }, { key: "3", label: "Filled, no caries", perm: "3", prim: "D" },
    { key: "4", label: "Missing, caries", perm: "4", prim: "E" }, { key: "5", label: "Missing, other reason", perm: "5", prim: null },
    { key: "6", label: "Fissure sealant", perm: "6", prim: "F" }, { key: "7", label: "Crown, abutment, implant", perm: "7", prim: "G" },
    { key: "8", label: "Unerupted", perm: "8", prim: null }, { key: "9", label: "Not recorded", perm: "9", prim: null },
    { key: "clear", label: "Clear", perm: null, prim: null },
  ];
  const LETTER_TO_DIGIT = { A: "0", B: "1", C: "2", D: "3", E: "4", F: "6", G: "7" };
  const PUFAS = [{ key: "P", label: "Pulpal involvement" }, { key: "U", label: "Ulceration" }, { key: "F", label: "Fistula" }, { key: "A", label: "Abscess" }, { key: "clear", label: "Clear" }];
  const UP = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
  const LO = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
  const UPP = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65];
  const LOP = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75];
  const caries = { codes: {}, pufa: {}, mode: "who", brush: "1" };

  function swatchClass(code) {
    if (code === undefined || code === null) return "c empty";
    const d = /[A-G]/.test(code) ? LETTER_TO_DIGIT[code] : code;
    return "c sw-" + d;
  }
  function buildPalette() {
    const pal = $("#palette"); pal.replaceChildren();
    const list = caries.mode === "who" ? STATUSES : PUFAS;
    if (!list.some((s) => s.key === caries.brush)) caries.brush = list[0].key;
    list.forEach((s) => {
      const sw = caries.mode === "who"
        ? el("span", { class: "swatch " + (s.key === "clear" ? "sw-clear" : "sw-" + s.key) }, s.key === "clear" ? "×" : (s.prim ? s.perm + "/" + s.prim : s.perm))
        : el("span", { class: "swatch " + (s.key === "clear" ? "sw-pufa-none" : "sw-pufa") }, s.key === "clear" ? "×" : s.key);
      const b = el("button", { type: "button", role: "radio", "aria-checked": String(s.key === caries.brush), tabindex: s.key === caries.brush ? "0" : "-1", "data-k": s.key }, sw, s.label);
      b.addEventListener("click", () => selectBrush(b));
      b.addEventListener("keydown", (e) => {
        const all = $$("#palette button"); const i = all.indexOf(b); let n = null;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") n = all[(i + 1) % all.length];
        else if (e.key === "ArrowLeft" || e.key === "ArrowUp") n = all[(i + all.length - 1) % all.length];
        else if (e.key === "Home") n = all[0];
        else if (e.key === "End") n = all[all.length - 1];
        if (n) { e.preventDefault(); selectBrush(n); n.focus(); }
      });
      pal.append(b);
    });
  }
  function selectBrush(b) {
    caries.brush = b.dataset.k;
    $$("#palette button").forEach((x) => { const on = x === b; x.setAttribute("aria-checked", String(on)); x.tabIndex = on ? 0 : -1; });
  }
  function toothButton(t) {
    const prim = t > 48;
    const code = caries.codes[t];
    const pf = caries.pufa[t];
    const b = el("button", { type: "button", class: "tooth" + ([18, 28, 38, 48].includes(t) ? " third" : ""), "data-t": t },
      el("span", { class: "n" }, String(t)), el("span", { class: swatchClass(code) }, code || ""), pf ? el("span", { class: "pf" }, prim ? pf.toLowerCase() : pf) : null);
    const st = code ? (STATUSES.find((s) => s.perm === code || s.prim === code) || {}).label : "not coded";
    b.setAttribute("aria-label", "Tooth " + t + ", " + (code ? code + " " + st : st) + (pf ? ", PUFA " + pf : ""));
    b.addEventListener("click", () => paint(t));
    return b;
  }
  function paint(t) {
    const prim = t > 48;
    if (caries.mode === "who") {
      const s = STATUSES.find((x) => x.key === caries.brush);
      const v = s.key === "clear" ? null : (prim ? s.prim : s.perm);
      if (s.key !== "clear" && v === null) { flash("“" + s.label + "” has no primary-tooth code in WHO 2013."); return; }
      if (caries.codes[t] === v || v === null) delete caries.codes[t]; else caries.codes[t] = v;
    } else {
      const v = caries.brush === "clear" ? null : caries.brush;
      if (caries.pufa[t] === v || v === null) delete caries.pufa[t]; else caries.pufa[t] = v;
    }
    drawOdonto(t); computeCaries();
  }
  let flashTimer;
  function flash(msg) {
    let f = $("#flash");
    if (!f) { f = el("p", { id: "flash", class: "err", role: "status" }); $("#odonto").after(f); }
    f.textContent = msg; clearTimeout(flashTimer); flashTimer = setTimeout(() => f.remove(), 2600);
  }
  function drawOdonto(focusTooth) {
    const od = $("#odonto"); od.replaceChildren();
    const lab = (a, b, cls) => el("div", { class: "arch-label" + (cls ? " " + cls : "") }, el("span", null, a), el("span", null, b));
    od.append(lab("Upper right", "Upper left"), el("div", { class: "arch" }, UP.map(toothButton)), el("div", { class: "midline" }),
      el("div", { class: "arch" }, LO.map(toothButton)), lab("Lower right", "Lower left"));
    if ($("#c-prim").checked) {
      od.append(lab("Primary upper right", "Primary upper left", "prim"), el("div", { class: "arch prim" }, UPP.map(toothButton)),
        el("div", { class: "midline", style: "min-width:330px;max-width:470px;margin-left:auto;margin-right:auto" }),
        el("div", { class: "arch prim" }, LOP.map(toothButton)), lab("Primary lower right", "Primary lower left", "prim"));
    }
    if (focusTooth) { const b = od.querySelector('[data-t="' + focusTooth + '"]'); if (b) b.focus({ preventScroll: true }); }
  }
  function computeCaries() {
    const box = $("#r-caries");
    try {
      const age = numOrNull($("#c-age").value);
      const both = DI.caries_experience({ codes: caries.codes, age, include_third_molars: $("#c-third").checked });
      const P = both.permanent, Q = both.primary;
      const parts = [];
      const bar = (d, m, f) => {
        const tot = d + m + f || 1;
        return el("div", { class: "bars", "aria-hidden": "true" }, el("span", { style: "flex-grow:" + d / tot + ";background:var(--c-caries)" }),
          el("span", { style: "flex-grow:" + m / tot + ";background:var(--c-miss)" }), el("span", { style: "flex-grow:" + f / tot + ";background:var(--c-filled)" }));
      };
      parts.push(el("h2", { class: "sr-only" }, "Caries result"));
      parts.push(el("div", { class: "big" }, el("span", { class: "val" }, fmt(P.value)), el("span", { class: "lab" }, "DMFT (permanent teeth)")));
      if (P.value !== null) {
        parts.push(bar(P.components.DT, P.components.MT, P.components.FT));
        parts.push(kv([["D decayed", P.components.DT], ["M missing", P.components.MT], ["F filled", P.components.FT], ["Teeth present", P.components.teeth_present],
          ["Sealed", P.components.sealed], ["Caries-free", fmt(P.components.caries_free)]]));
      }
      if (Q.value !== null) {
        parts.push(el("div", { class: "big", style: "margin-top:18px" }, el("span", { class: "val", style: "font-size:2.2rem" }, fmt(Q.value)), el("span", { class: "lab" }, "dmft (primary teeth)")));
        parts.push(bar(Q.components.dt, Q.components.mt, Q.components.ft));
        parts.push(kv([["d decayed", Q.components.dt], ["m missing", Q.components.mt], ["f filled", Q.components.ft], ["Teeth present", Q.components.teeth_present]]));
      }
      const decayed = (P.value !== null ? P.components.DT : 0) + (Q.value !== null ? Q.components.dt : 0);
      if (Object.keys(caries.pufa).length) {
        const pf = DI.pufa({ codes: caries.pufa, decayed_teeth: decayed });
        parts.push(el("h3", null, "PUFA/pufa (Monse 2010)"));
        parts.push(kv([["PUFA permanent", pf.components.PUFA], ["pufa primary", pf.components.pufa], ["P / U / F / A", [pf.components.P + pf.components.p, pf.components.U + pf.components.u, pf.components.F + pf.components.f, pf.components.A + pf.components.a].join(" / ")],
          ["Decayed teeth progressed", pf.components.percent_decayed_progressed === null ? "–" : fmt(pf.components.percent_decayed_progressed, 0) + "%"]]));
        const w = warnList(pf.warnings); if (w) parts.push(w);
        parts.push(traceBlock(pf, "How PUFA was calculated"));
      }
      const anyPrim = Object.keys(caries.codes).some((t) => Number(t) > 48);
      const w = warnList(P.warnings.concat(anyPrim ? Q.warnings : [])); if (w && Object.keys(caries.codes).length) parts.push(w);
      if (!Object.keys(caries.codes).length) parts.push(el("p", { class: "sub", style: "margin-top:12px" }, "Code the teeth on the chart to see DMFT and dmft."));
      else { parts.push(traceBlock(P, "How DMFT was calculated")); if (Q.value !== null) parts.push(traceBlock(Q, "How dmft was calculated")); }
      parts.push(sourcesLine(["who2013", "klein1938"].concat(Object.keys(caries.pufa).length ? ["monse2010"] : [])));
      box.replaceChildren(...parts);
      box.classList.remove("fade-in"); void box.offsetWidth; box.classList.add("fade-in");
    } catch (e) { showError(box, e); }
  }
  function initCaries() {
    buildPalette(); drawOdonto(); computeCaries();
    $("#pal-who").addEventListener("click", () => { caries.mode = "who"; caries.brush = "1"; $("#pal-who").setAttribute("aria-pressed", "true"); $("#pal-pufa").setAttribute("aria-pressed", "false"); buildPalette(); });
    $("#pal-pufa").addEventListener("click", () => { caries.mode = "pufa"; caries.brush = "P"; $("#pal-pufa").setAttribute("aria-pressed", "true"); $("#pal-who").setAttribute("aria-pressed", "false"); buildPalette(); });
    ["#c-age", "#c-third"].forEach((s) => $(s).addEventListener("input", computeCaries));
    $("#c-prim").addEventListener("change", () => drawOdonto());
    $("#c-sound").addEventListener("click", () => { UP.concat(LO).forEach((t) => { if (!caries.codes[t]) caries.codes[t] = [18, 28, 38, 48].includes(t) && $("#c-age").value && Number($("#c-age").value) < 18 ? "8" : "0"; }); drawOdonto(); computeCaries(); });
    $("#c-clear").addEventListener("click", () => { caries.codes = {}; caries.pufa = {}; drawOdonto(); computeCaries(); });
    $("#c-example").addEventListener("click", () => {
      caries.codes = {}; caries.pufa = {};
      UP.concat(LO).forEach((t) => { caries.codes[t] = "0"; });
      Object.assign(caries.codes, { 18: "8", 28: "8", 38: "8", 48: "8", 16: "1", 26: "3", 36: "2", 46: "4", 37: "6", 47: "6", 11: "3" });
      caries.pufa = { 36: "P" }; $("#c-age").value = 15; drawOdonto(); computeCaries();
    });
  }

  // ------------------------------------------------------------------ periodontal screening
  const SEXT_LAYOUT = [["UR", "S1", "17–14"], ["UA", "S2", "13–23"], ["UL", "S3", "24–27"], ["LR", "S6", "47–44"], ["LA", "S5", "43–33"], ["LL", "S4", "34–37"]];
  const scr = { kind: "bpe", bpe: {}, fur: {}, sbpe: {}, sfur: {}, cpitn: {} };
  function drawScreening() {
    const g = $("#scr-grid"); g.replaceChildren();
    const sub = $("#scr-sub");
    $("#scr-age-row").hidden = scr.kind === "bpe";
    if (scr.kind === "bpe") {
      sub.textContent = "Highest code per sextant (BSP 2019): 0 healthy · 1 bleeding · 2 calculus or overhang · 3 pocket 4–5 mm · 4 pocket ≥ 6 mm; tick * for furcation involvement; “–” when a sextant has fewer than two teeth.";
      const grid = el("div", { class: "sext" });
      SEXT_LAYOUT.forEach(([name, s, teeth], i) => {
        if (i === 3) grid.append(el("div", { class: "divider" }));
        const sel = select("bpe-" + s, [["", "–"], "0", "1", "2", "3", "4"], scr.bpe[s] === undefined ? "0" : scr.bpe[s], "BPE " + name);
        sel.addEventListener("change", () => { scr.bpe[s] = sel.value; computeScreening(); });
        const cb = el("input", { type: "checkbox", id: "fur-" + s }); cb.checked = !!scr.fur[s];
        cb.addEventListener("change", () => { scr.fur[s] = cb.checked; computeScreening(); });
        grid.append(el("div", { class: "cell" }, el("b", null, name + " ", el("small", null, teeth)), sel, el("label", { class: "check", style: "min-height:28px;font-size:.84rem" }, cb, "Furcation *")));
      });
      g.append(grid);
    } else if (scr.kind === "sbpe") {
      sub.textContent = "Six index teeth (16, 11, 26, 36, 31, 46). Ages 7–11 use codes 0–2 only; ages 12–17 the full range with *.";
      if (!$("#scr-age").value) $("#scr-age").value = 10;
      const age = Number($("#scr-age").value); const full = age >= 12;
      const grid = el("div", { class: "sext" });
      [[16, "UR6"], [11, "UR1"], [26, "UL6"], [46, "LR6"], [31, "LL1"], [36, "LL6"]].forEach(([t, nm], i) => {
        if (i === 3) grid.append(el("div", { class: "divider" }));
        const opts = full ? [["", "–"], "0", "1", "2", "3", "4"] : [["", "–"], "0", "1", "2"];
        let cur = scr.sbpe[t] === undefined ? "0" : scr.sbpe[t]; if (!full && ["3", "4"].includes(cur)) cur = "2";
        scr.sbpe[t] = cur;
        const sel = select("sbpe-" + t, opts, cur, "sBPE tooth " + t);
        sel.addEventListener("change", () => { scr.sbpe[t] = sel.value; computeScreening(); });
        const cell = el("div", { class: "cell" }, el("b", null, String(t) + " ", el("small", null, nm)), sel);
        if (full) { const cb = el("input", { type: "checkbox" }); cb.checked = !!scr.sfur[t]; cb.addEventListener("change", () => { scr.sfur[t] = cb.checked; computeScreening(); }); cell.append(el("label", { class: "check", style: "min-height:28px;font-size:.84rem" }, cb, "Furcation *")); }
        else scr.sfur[t] = false;
        grid.append(cell);
      });
      g.append(grid);
    } else {
      sub.textContent = "One code per sextant (Ainamo et al. 1982; WHO 1997): 0 healthy · 1 bleeding · 2 calculus · 3 pocket 4–5 mm · 4 pocket ≥ 6 mm · X excluded (fewer than two functional teeth) · 9 not recorded. Index teeth from age 20: 17/16, 11, 26/27, 36/37, 31, 46/47.";
      const grid = el("div", { class: "sext" });
      SEXT_LAYOUT.forEach(([name, s, teeth], i) => {
        if (i === 3) grid.append(el("div", { class: "divider" }));
        const sel = select("cpitn-" + s, ["0", "1", "2", "3", "4", "X", "9"], scr.cpitn[s] === undefined ? "0" : scr.cpitn[s], "CPITN " + name);
        sel.addEventListener("change", () => { scr.cpitn[s] = sel.value; computeScreening(); });
        grid.append(el("div", { class: "cell" }, el("b", null, name + " ", el("small", null, teeth.replace("27", "28").replace("37", "38").replace("47", "48"))), sel));
      });
      g.append(grid);
    }
    computeScreening();
  }
  function computeScreening() {
    const box = $("#r-screen");
    try {
      let r;
      if (scr.kind === "bpe") {
        const sx = {}; SEXT_LAYOUT.forEach(([, s]) => { const v = scr.bpe[s] === undefined ? "0" : scr.bpe[s]; sx[s] = v === "" ? null : v + (scr.fur[s] ? "*" : ""); });
        r = DI.bpe({ sextants: sx });
        render(box, "BPE", r, { label: "highest BPE code", value: r.value + (r.components.furcation ? "*" : ""),
          kv: [["Code 3 sextants", r.components.code3_sextants.length], ["Code 4 sextants", r.components.code4_sextants.length], ["Furcation", fmt(r.components.furcation)], ["Full 6-point chart", fmt(r.components.full_chart_indicated)]] });
      } else if (scr.kind === "sbpe") {
        const it = {}; Object.entries(scr.sbpe).forEach(([t, v]) => { it[t] = v === "" ? null : v + (scr.sfur[t] ? "*" : ""); });
        r = DI.sbpe({ index_teeth: it, age: numOrNull($("#scr-age").value) });
        render(box, "sBPE", r, { label: "highest sBPE code", value: r.value + (r.components.furcation ? "*" : ""), kv: [["Age band", r.components.age_band]] });
      } else {
        r = DI.cpitn({ sextants: Object.assign({ S1: "0", S2: "0", S3: "0", S4: "0", S5: "0", S6: "0" }, scr.cpitn), age: numOrNull($("#scr-age").value) });
        render(box, "CPITN", r, { label: "highest CPITN code", kv: [["Treatment need", r.components.treatment_need], ["Sextants scored", r.components.sextants_scored], ["Code 3", r.components.sextants_code3], ["Code 4", r.components.sextants_code4]] });
      }
    } catch (e) { showError(box, e); }
  }
  function initScreening() {
    $$("[data-scr]").forEach((b) => b.addEventListener("click", () => { scr.kind = b.dataset.scr; $$("[data-scr]").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); drawScreening(); }));
    $("#scr-age").addEventListener("input", () => (scr.kind === "sbpe" ? drawScreening() : computeScreening()));
    drawScreening();
  }

  // ------------------------------------------------------------------ periodontitis cases
  const PERIO_TEETH = [17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37];
  const PSITES = ["MB", "B", "DB", "ML", "L", "DL"];
  let perio = {}; let survey = "completed";
  function perioDefaults() { perio = {}; PERIO_TEETH.forEach((t) => { perio[t] = { missing: false, pd: [2, 2, 2, 2, 2, 2], cal: [0, 0, 0, 0, 0, 0], bop: [false, false, false, false, false, false] }; }); }
  function drawPerioTable() {
    const tb = $("#perio-table"); tb.replaceChildren();
    const h1 = el("tr", null, el("th", { rowspan: 2 }, "Tooth"), el("th", { rowspan: 2 }, "Missing"), el("th", { colspan: 6 }, "PD (mm)"), el("th", { colspan: 6 }, "CAL (mm)"), el("th", { colspan: 6 }, "BOP"));
    const h2 = el("tr", null, ...[0, 1, 2].flatMap(() => PSITES.map((s) => el("th", null, s))));
    tb.append(el("thead", null, h1, h2));
    const body = el("tbody");
    PERIO_TEETH.forEach((t) => {
      const st = perio[t]; const tr = el("tr", { class: st.missing ? "missing" : "" });
      const miss = el("input", { type: "checkbox", "aria-label": "Tooth " + t + " missing" }); miss.checked = st.missing;
      miss.addEventListener("change", () => { st.missing = miss.checked; tr.className = st.missing ? "missing" : ""; computePerio(); });
      tr.append(el("td", { class: "tn" }, String(t)), el("td", { class: "miss" }, miss));
      ["pd", "cal"].forEach((m) => PSITES.forEach((s, i) => {
        const inp = el("input", { type: "number", min: 0, max: m === "pd" ? 20 : 25, step: 1, value: st[m][i], "aria-label": "Tooth " + t + " " + m.toUpperCase() + " " + s });
        inp.addEventListener("input", () => { st[m][i] = inp.value === "" ? null : Number(inp.value); computePerio(); });
        tr.append(el("td", null, inp));
      }));
      PSITES.forEach((s, i) => { const cb = el("input", { type: "checkbox", class: "bopbox", "aria-label": "Tooth " + t + " bleeding " + s }); cb.checked = st.bop[i]; cb.addEventListener("change", () => { st.bop[i] = cb.checked; computePerio(); }); tr.append(el("td", { style: "text-align:center" }, cb)); });
      body.append(tr);
    });
    tb.append(body);
  }
  function perioChart() {
    const chart = {}; const present = [];
    PERIO_TEETH.forEach((t) => {
      const st = perio[t]; if (st.missing) return; present.push(t);
      const pd = {}, cal = {}, bop = {};
      PSITES.forEach((s, i) => { if (st.pd[i] !== null && !isNaN(st.pd[i])) pd[s] = st.pd[i]; if (st.cal[i] !== null && !isNaN(st.cal[i])) cal[s] = st.cal[i]; bop[s] = st.bop[i]; });
      chart[t] = { pd, cal, bop };
    });
    return { chart, present };
  }
  function computePerio() {
    const box = $("#r-perio");
    try {
      const { chart, present } = perioChart();
      const dm = $("#a-dm").value;
      const opts = { chart, teeth_present: present, survey, age: numOrNull($("#a-age").value), cigarettes_per_day: numOrNull($("#a-cig").value),
        diabetes: dm === "" ? null : dm === "yes", hba1c: numOrNull($("#a-hb").value), bone_loss_percent: numOrNull($("#a-bl").value),
        furcation_class_2_3: $("#a-fi").checked || null, vertical_bone_loss_3mm: $("#a-vbl").checked || null };
      if (survey === "planned") Object.assign(opts, { teeth_lost_to_periodontitis: $("#a-lost").value, mobility_degree2_at_2_teeth: $("#a-mob").checked || null, bite_collapse_drifting_flaring: $("#a-bite").checked || null });
      const A = DI.aces(opts); const S = DI.perio_summary({ chart });
      const C = DI.cdc_aap({ chart, teeth_present: present, mild_cal_distinct_teeth: !$("#c-mild-same").checked, mild_pd5_any_site: $("#c-mild-any").checked });
      const parts = [el("h2", { class: "sr-only" }, "Periodontitis result")];
      parts.push(el("div", { class: "big" }, el("span", { class: "val", style: "font-size:clamp(1.8rem,4vw,2.4rem)" }, A.components.stage ? "Stage " + A.components.stage : A.category), el("span", { class: "lab" }, "2018 classification (ACES)")));
      if (A.components.stage) {
        const cut = A.category.indexOf(" (");
        parts.push(el("p", { style: "margin:10px 0 0" }, el("span", { class: pillClass("stage " + A.components.stage.toLowerCase()) }, cut > 0 ? A.category.slice(0, cut) : A.category)));
        if (cut > 0) parts.push(el("p", { class: "sub", style: "margin:8px 0 0" }, A.category.slice(cut + 2, -1).replace(/^./, (c) => c.toUpperCase()) + "."));
      }
      parts.push(kv(A.components.stage ? [["Extent", A.components.extent ? A.components.extent + " (" + fmt(A.components.extent_percent, 0) + "%)" : "–"], ["Grade", A.components.grade + (A.components.grade_assumed ? " (base assumed)" : "")],
        ["Max interdental CAL", fmt(A.components.max_interdental_cal) + " mm"], ["Opposing pairs", A.components.opposing_pairs], ["Bleeding sites", A.components.bleeding_percent === null ? "–" : fmt(A.components.bleeding_percent, 1) + "%"]]
        : [["Bleeding sites", A.components.bleeding_percent === null || A.components.bleeding_percent === undefined ? "–" : fmt(A.components.bleeding_percent, 1) + "%"], ["Max PD", fmt(A.components.max_pd) + " mm"]]));
      const w = warnList(A.warnings); if (w) parts.push(w);
      parts.push(traceBlock(A, "How ACES classified this chart"));
      parts.push(el("h3", null, "CDC/AAP case definition (Eke 2012)"));
      parts.push(el("p", { style: "margin:4px 0 0" }, el("span", { class: pillClass(C.category) }, C.category)));
      const w2 = warnList(C.warnings); if (w2) parts.push(w2);
      parts.push(traceBlock(C, "How CDC/AAP classified this chart"));
      parts.push(el("h3", null, "Summary measures"));
      parts.push(kv([["Mean PD", fmt(S.components.mean_pd) + " mm"], ["Mean CAL", fmt(S.components.mean_cal) + " mm"], ["Sites PD ≥ 4", fmt(S.components.percent_sites_pd_4plus, 1) + "%"],
        ["Sites PD ≥ 6", fmt(S.components.percent_sites_pd_6plus, 1) + "%"], ["Sites CAL ≥ 3", fmt(S.components.percent_sites_cal_3plus, 1) + "%"], ["Sites CAL ≥ 5", fmt(S.components.percent_sites_cal_5plus, 1) + "%"]]));
      parts.push(sourcesLine(["holtfreter2024", "tonetti2018", "chapple2018", "eke2012", "holtfreter2015"]));
      box.replaceChildren(...parts); box.classList.remove("fade-in"); void box.offsetWidth; box.classList.add("fade-in");
    } catch (e) { showError(box, e); }
  }
  function perioExample(kind) {
    perioDefaults();
    const set = (t, i, pd, cal, bop) => { perio[t].pd[i] = pd; perio[t].cal[i] = cal; if (bop !== undefined) perio[t].bop[i] = bop; };
    if (kind === "healthy") { [11, 12].forEach((t) => { perio[t].bop[1] = true; }); $("#a-age").value = 30; $("#a-cig").value = 0; }
    if (kind === "stage3") {
      [16, 26, 36, 46, 14, 24].forEach((t) => [0, 2, 3, 5].forEach((i) => set(t, i, 5, 4, true)));
      set(16, 0, 7, 6, true); set(36, 2, 6, 6, true); set(26, 0, 6, 5, true); set(14, 0, 6, 5, true); set(46, 3, 6, 5, true);
      $("#a-age").value = 52; $("#a-cig").value = 12; $("#a-dm").value = "no"; $("#a-bl").value = 35;
    }
    if (kind === "stage4") {
      [17, 16, 15, 25, 26, 27, 37, 36, 46, 47, 45, 35].forEach((t) => { perio[t].missing = true; });
      [14, 13, 24, 34, 44, 11, 21, 31, 41].forEach((t) => [0, 2, 3, 5].forEach((i) => set(t, i, 6, 7, true)));
      $("#a-age").value = 66; $("#a-cig").value = 0; $("#a-dm").value = "yes"; $("#a-hb").value = 8.2; $("#a-bl").value = 60;
    }
    drawPerioTable(); computePerio();
  }
  function initPerio() {
    perioDefaults(); drawPerioTable();
    $$("[data-pex]").forEach((b) => b.addEventListener("click", () => perioExample(b.dataset.pex)));
    $("#p-reset").addEventListener("click", () => { perioDefaults(); drawPerioTable(); computePerio(); });
    $$("[data-survey]").forEach((b) => b.addEventListener("click", () => { survey = b.dataset.survey; $$("[data-survey]").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); $("#a-planned").hidden = survey !== "planned"; computePerio(); }));
    ["#a-age", "#a-cig", "#a-dm", "#a-hb", "#a-bl", "#a-fi", "#a-vbl", "#a-lost", "#a-mob", "#a-bite", "#c-mild-same", "#c-mild-any"].forEach((s) => $(s).addEventListener("input", computePerio));
    computePerio();
  }

  // ------------------------------------------------------------------ hygiene
  const hyg = { kind: "ohis", ohis: {}, pli: {}, gi: {}, pcr: {}, pcrMissing: {} };
  const OHIS_SITES = [["UR", [16, 17, 18], "buccal"], ["UA", [11, 21], "labial"], ["UL", [26, 27, 28], "buccal"], ["LL", [36, 37, 38], "lingual"], ["LA", [31, 41], "labial"], ["LR", [46, 47, 48], "lingual"]];
  const RAMF = [16, 21, 24, 36, 41, 44];
  const PCR_TEETH = [17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37];
  function drawHygiene() {
    const body = $("#hyg-body"); body.replaceChildren(); const sub = $("#hyg-sub");
    if (hyg.kind === "ohis") {
      sub.textContent = "Greene & Vermillion 1964: debris and calculus (0–3) on six surfaces. If a first molar is not fully erupted or is crowned, score the next molar; 21 and 41 replace 11 and 31. At least two surfaces are needed.";
      const t = el("table"); t.append(el("thead", null, el("tr", null, el("th", null, "Site"), el("th", null, "Tooth"), el("th", null, "Surface"), el("th", null, "Debris"), el("th", null, "Calculus"))));
      const tb = el("tbody");
      OHIS_SITES.forEach(([site, teeth, surf]) => {
        const st = hyg.ohis[site] || (hyg.ohis[site] = { tooth: teeth[0], d: "0", c: "0" });
        const ts = select("ohis-t-" + site, teeth.map(String), st.tooth, site + " tooth"); ts.addEventListener("change", () => { st.tooth = Number(ts.value); computeHygiene(); });
        const ds = select("ohis-d-" + site, [["", "–"], "0", "1", "2", "3"], st.d, site + " debris"); ds.addEventListener("change", () => { st.d = ds.value; computeHygiene(); });
        const cs = select("ohis-c-" + site, [["", "–"], "0", "1", "2", "3"], st.c, site + " calculus"); cs.addEventListener("change", () => { st.c = cs.value; computeHygiene(); });
        tb.append(el("tr", null, el("td", null, site), el("td", null, ts), el("td", null, surf), el("td", null, ds), el("td", null, cs)));
      });
      t.append(tb); body.append(el("div", { class: "table-wrap", style: "max-height:none" }, t));
    } else if (hyg.kind === "pli" || hyg.kind === "gi") {
      const isP = hyg.kind === "pli";
      sub.textContent = isP ? "Silness & Löe 1964: plaque at the gingival margin (0–3) on the distofacial, facial, mesiofacial and lingual areas of the six Ramfjord teeth." :
        "Löe & Silness 1963: gingival inflammation (0 normal, 1 mild, 2 moderate with bleeding on probing, 3 severe) on four areas of the six Ramfjord teeth.";
      const store = hyg[hyg.kind];
      const t = el("table"); t.append(el("thead", null, el("tr", null, el("th", null, "Tooth"), ...["D", "B", "M", "L"].map((a) => el("th", null, a)))));
      const tb = el("tbody");
      RAMF.forEach((tooth) => {
        const st = store[tooth] || (store[tooth] = ["0", "0", "0", "0"]);
        const tr = el("tr", null, el("td", null, String(tooth)));
        st.forEach((v, i) => { const s = select(hyg.kind + "-" + tooth + "-" + i, [["", "–"], "0", "1", "2", "3"], v, "Tooth " + tooth + " area " + "DBML"[i]); s.addEventListener("change", () => { st[i] = s.value; computeHygiene(); }); tr.append(el("td", null, s)); });
        tb.append(tr);
      });
      t.append(tb); body.append(el("div", { class: "table-wrap", style: "max-height:none" }, t));
    } else {
      sub.textContent = "O'Leary, Drake & Naylor 1972: tap the surfaces with disclosed plaque (M, D, B, L) on every tooth present; mark missing teeth.";
      const grid = el("div", { style: "display:grid;grid-template-columns:repeat(auto-fill,minmax(84px,1fr));gap:6px" });
      PCR_TEETH.forEach((tooth) => {
        const st = hyg.pcr[tooth] || (hyg.pcr[tooth] = { M: false, D: false, B: false, L: false });
        const cell = el("div", { class: "cell", style: "background:var(--fill);border-radius:10px;padding:6px;display:grid;gap:4px;justify-items:center" + (hyg.pcrMissing[tooth] ? ";opacity:.35" : "") });
        const miss = el("input", { type: "checkbox", "aria-label": "Tooth " + tooth + " missing" }); miss.checked = !!hyg.pcrMissing[tooth];
        miss.addEventListener("change", () => { hyg.pcrMissing[tooth] = miss.checked; drawHygiene(); });
        const row = el("div", { style: "display:grid;grid-template-columns:repeat(4,18px);gap:3px" });
        ["M", "D", "B", "L"].forEach((s) => {
          const b = el("button", { type: "button", "aria-pressed": String(st[s]), "aria-label": "Tooth " + tooth + " " + s + " plaque", title: s,
            style: "width:18px;height:18px;border-radius:5px;border:0;padding:0;font-size:.6rem;font-weight:700;cursor:pointer;" + (st[s] ? "background:var(--bad);color:#fff" : "background:var(--surface);color:var(--text-3);box-shadow:inset 0 0 0 1px var(--hairline-2)") }, s);
          b.addEventListener("click", () => { st[s] = !st[s]; drawHygiene(); });
          row.append(b);
        });
        cell.append(el("span", { style: "font-size:.74rem;font-weight:650" }, String(tooth)), row, el("label", { style: "font-size:.68rem;color:var(--text-3);display:flex;gap:3px;align-items:center" }, miss, "missing"));
        grid.append(cell);
      });
      body.append(grid);
    }
    computeHygiene();
  }
  function computeHygiene() {
    const box = $("#r-hyg");
    try {
      let r;
      if (hyg.kind === "ohis") {
        const deb = {}, cal = {};
        OHIS_SITES.forEach(([site]) => { const st = hyg.ohis[site]; if (st.d !== "") deb[st.tooth] = st.d; if (st.c !== "") cal[st.tooth] = st.c; });
        r = DI.ohi_s({ debris: deb, calculus: Object.keys(cal).length ? cal : null });
        render(box, "OHI-S", r, { label: r.components.OHI_S !== undefined ? "OHI-S (0–6)" : "DI-S (0–3)",
          kv: [["DI-S", fmt(r.components.DI_S) + " · " + r.components.DI_S_category], r.components.CI_S !== undefined ? ["CI-S", fmt(r.components.CI_S) + " · " + r.components.CI_S_category] : null] });
      } else if (hyg.kind === "pli" || hyg.kind === "gi") {
        const sc = {}; Object.entries(hyg[hyg.kind]).forEach(([t, a]) => { sc[t] = a.map((v) => (v === "" ? null : Number(v))); });
        r = hyg.kind === "pli" ? DI.plaque_index({ scores: sc }) : DI.gingival_index({ scores: sc });
        render(box, hyg.kind === "pli" ? "Plaque Index" : "Gingival Index", r, { value: fmt(r.value), label: hyg.kind === "pli" ? "Plaque Index (0–3)" : "Gingival Index (0–3)",
          kv: [["Teeth scored", r.components.teeth_scored], ["Areas scored", r.components.areas_scored]] });
      } else {
        const plaque = {}, present = [];
        PCR_TEETH.forEach((t) => { if (hyg.pcrMissing[t]) return; present.push(t); const st = hyg.pcr[t]; plaque[t] = ["M", "D", "B", "L"].filter((s) => st[s]); });
        r = DI.plaque_control_record({ plaque, teeth_present: present });
        render(box, "Plaque Control Record", r, { value: fmt(r.value, 1) + "%", label: "surfaces with plaque", kv: [["Surfaces with plaque", r.components.surfaces_with_plaque], ["Surfaces examined", r.components.surfaces_examined]] });
      }
    } catch (e) { showError(box, e); }
  }
  function initHygiene() {
    $$("[data-hyg]").forEach((b) => b.addEventListener("click", () => { hyg.kind = b.dataset.hyg; $$("[data-hyg]").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); drawHygiene(); }));
    drawHygiene();
  }

  // ------------------------------------------------------------------ wear
  const bewe = {};
  const BEWE_LAYOUT = [["S1", "17–14"], ["S2", "13–23"], ["S3", "24–27"], ["S6", "47–44"], ["S5", "43–33"], ["S4", "34–37"]];
  function initWear() {
    const g = el("div", { class: "sext" });
    BEWE_LAYOUT.forEach(([s, teeth], i) => {
      if (i === 3) g.append(el("div", { class: "divider" }));
      bewe[s] = "0";
      const sel = select("bewe-" + s, [["", "–"], "0", "1", "2", "3"], "0", "BEWE sextant " + s);
      sel.addEventListener("change", () => { bewe[s] = sel.value; computeWear(); });
      g.append(el("div", { class: "cell" }, el("b", null, s + " ", el("small", null, teeth)), sel));
    });
    $("#bewe-grid").append(g); computeWear();
  }
  function computeWear() {
    const box = $("#r-wear");
    try {
      const r = DI.bewe({ sextants: Object.fromEntries(Object.entries(bewe).map(([k, v]) => [k, v === "" ? null : v])) });
      render(box, "BEWE", r, { label: "cumulative BEWE (0–18)", kv: [["Risk level", r.components.risk_level], ["Highest sextant", r.components.max_sextant_score], ["Sextants scored", r.components.sextants_scored]] });
    } catch (e) { showError(box, e); }
  }

  // ------------------------------------------------------------------ fluorosis
  const DEAN = [["0", "0 Normal"], ["1", "1 Questionable"], ["2", "2 Very mild"], ["3", "3 Mild"], ["4", "4 Moderate"], ["5", "5 Severe"]];
  function initFluor() {
    const p = $("#dean-person");
    const a = select("dean-a", DEAN, "3", "Most affected tooth"), b = select("dean-b", DEAN, "2", "Second most affected tooth");
    p.append(el("label", { class: "field" }, el("span", null, "Most affected tooth"), a), el("label", { class: "field" }, el("span", null, "Second most affected tooth"), b));
    const counts = $("#cfi-counts");
    const defaults = [40, 12, 8, 4, 1, 0];
    DEAN.forEach(([c, label], i) => {
      const inp = el("input", { type: "number", min: 0, max: 100000, step: 1, value: defaults[i], id: "cfi-" + c, style: "width:100%", "aria-label": "Number of people scored " + label });
      inp.addEventListener("input", computeFluor);
      counts.append(el("div", null, el("dt", null, label), el("dd", null, inp)));
    });
    [a, b].forEach((s) => s.addEventListener("change", computeFluor));
    computeFluor();
  }
  function computeFluor() {
    const box = $("#r-fluor");
    try {
      const d = DI.dean_index({ teeth: { 11: $("#dean-a").value, 21: $("#dean-b").value } });
      const persons = []; DEAN.forEach(([c]) => { const n = Math.min(100000, Math.max(0, Math.floor(Number($("#cfi-" + c).value) || 0))); for (let i = 0; i < n; i++) persons.push(c); });
      const parts = [];
      parts.push(el("h2", { class: "sr-only" }, "Fluorosis result"));
      parts.push(el("div", { class: "big" }, el("span", { class: "val", style: "font-size:2.2rem" }, d.category), el("span", { class: "lab" }, "person score (Dean weight " + d.components.dean_weight + ")")));
      parts.push(traceBlock(d, "How the person score was chosen"));
      if (persons.length) {
        const c = DI.community_fluorosis_index({ person_scores: persons });
        parts.push(el("div", { class: "big", style: "margin-top:18px" }, el("span", { class: "val" }, fmt(c.value)), el("span", { class: "lab" }, "Community Fluorosis Index (n = " + c.components.n + ")")));
        parts.push(el("p", { style: "margin:10px 0 0" }, el("span", { class: pillClass(c.category) }, c.category + " public-health significance")));
        parts.push(el("p", { class: "guidance" }, c.components.public_health_problem ? "A CFI above 0.6 indicates that fluorosis is a public-health problem (Dean 1942); WHO 2013 asks that clinical findings be complemented with fluoride-exposure studies." : "A CFI of 0.6 or less is not considered a public-health problem (Dean 1942)."));
        parts.push(traceBlock(c, "How the CFI was calculated"));
      }
      parts.push(sourcesLine(["who2013", "dean1934", "dean1942"]));
      box.replaceChildren(...parts); box.classList.remove("fade-in"); void box.offsetWidth; box.classList.add("fade-in");
    } catch (e) { showError(box, e); }
  }

  // ------------------------------------------------------------------ DAI
  const DAI_FIELDS = [
    ["missing_visible_teeth", "Missing incisors, canines, premolars (both arches)", 20, "teeth"], ["crowding", "Crowded incisal segments", 2, "0–2"], ["spacing", "Spaced incisal segments", 2, "0–2"],
    ["diastema_mm", "Midline diastema", 30, "mm"], ["max_anterior_irregularity_mm", "Largest maxillary anterior irregularity", 30, "mm"], ["mand_anterior_irregularity_mm", "Largest mandibular anterior irregularity", 30, "mm"],
    ["max_overjet_mm", "Anterior maxillary overjet", 30, "mm"], ["mand_overjet_mm", "Anterior mandibular overjet (crossbite)", 30, "mm"], ["openbite_mm", "Vertical anterior openbite", 30, "mm"],
    ["molar_relation", "Antero-posterior molar relation (0 normal, 1 half cusp, 2 full cusp)", 2, "0–2"],
  ];
  function initDAI() {
    const f = $("#dai-fields");
    DAI_FIELDS.forEach(([k, label, max, unit]) => {
      const inp = el("input", { type: "number", min: 0, max, step: 1, value: k === "max_overjet_mm" ? 3 : 0, id: "dai-" + k });
      inp.addEventListener("input", computeDAI);
      f.append(el("label", { class: "field", style: "flex:1 1 240px" }, el("span", null, label + " (" + unit + ")"), inp));
    });
    computeDAI();
  }
  function computeDAI() {
    const box = $("#r-dai");
    try {
      const args = {}; const empty = [];
      DAI_FIELDS.forEach(([k, label]) => { const v = $("#dai-" + k).value; if (v === "") empty.push(label); else args[k] = Number(v); });
      if (empty.length) throw new Error("Enter a value (0 if absent) for: " + empty.join("; ") + ".");
      const r = DI.dai(args);
      render(box, "DAI", r, { label: "Dental Aesthetic Index", kv: [["Treatment indication", r.components.treatment_indication]] });
    } catch (e) { showError(box, e); }
  }

  // ------------------------------------------------------------------ survey
  const sv = { rows: null, name: "", out: null, kind: null };
  const isTooth = (k) => { try { DI._internal.parseTooth(k); return true; } catch (e) { return false; } };
  const isSext = (k) => /^(S[1-6]|UR|UA|UL|LL|LA|LR)$/i.test(String(k).trim());
  function loadCSV(text, name) {
    let rows;
    try { rows = DI.parseCSV(text); } catch (e) { alertSurvey("Could not read the file: " + e.message); return; }
    if (!rows.length) { alertSurvey("The file has no data rows."); return; }
    sv.rows = rows; sv.name = name;
    const cols = Object.keys(rows[0]); const low = cols.map((c) => c.toLowerCase());
    let opts;
    if (low.includes("tooth") && low.includes("site")) { sv.kind = "perio"; opts = [["perio", "Periodontal chart: CDC/AAP, ACES, summary measures"]]; }
    else if (cols.some(isTooth)) { sv.kind = "teeth"; opts = [["dmft_permanent", "DMFT (permanent teeth)"], ["dmft_primary", "dmft (primary teeth)"], ["caries_experience", "DMFT and dmft"], ["pufa", "PUFA/pufa"], ["dean_index", "Dean's index (person score)"]]; }
    else if (cols.some(isSext)) { sv.kind = "sext"; opts = [["bpe", "BPE"], ["bewe", "BEWE"], ["cpitn", "CPITN"], ["loss_of_attachment", "Loss of attachment (WHO 2013)"]]; if (name.toLowerCase().includes("bewe")) opts.unshift(opts.splice(1, 1)[0]); }
    else if (low.includes("max_overjet_mm")) { sv.kind = "dai"; opts = [["dai", "Dental Aesthetic Index"]]; }
    else { alertSurvey("No tooth, sextant, chart or DAI columns were found. See the column conventions above."); return; }
    const si = $("#s-index"); si.replaceChildren(...opts.map(([v, t]) => el("option", { value: v }, t)));
    const other = cols.filter((c) => !isTooth(c) && !isSext(c));
    $("#s-age").replaceChildren(el("option", { value: "" }, "(none)"), ...other.map((c) => el("option", { value: c, selected: c.toLowerCase() === "age" || null }, c)));
    const byDefault = other.find((c) => /age_?group|group|sex|region/i.test(c));
    $("#s-by").replaceChildren(el("option", { value: "" }, "(no grouping)"), ...other.map((c) => el("option", { value: c, selected: c === byDefault || null }, c)));
    $("#survey-config").hidden = false;
    $("#s-third-wrap").hidden = sv.kind !== "teeth";
    $("#s-perio-wrap").hidden = sv.kind !== "perio";
    runSurvey();
  }
  function alertSurvey(msg) {
    $("#survey-config").hidden = true; $("#survey-summary").hidden = true; $("#survey-rows").hidden = true;
    let p = $("#s-alert"); if (!p) { p = el("p", { id: "s-alert", class: "err", role: "alert" }); $("#drop").after(p); }
    p.textContent = msg;
  }
  function table(t, rows, max, first) {
    t.replaceChildren(); if (!rows.length) return;
    const cols = DI.columnOrder(rows, first);
    t.append(el("thead", null, el("tr", null, cols.map((c) => el("th", { scope: "col" }, c)))));
    const tb = el("tbody");
    rows.slice(0, max || rows.length).forEach((r) => tb.append(el("tr", null, cols.map((c) => el("td", null, typeof r[c] === "object" && r[c] !== null ? "" : fmt(r[c], 3))))));
    t.append(tb);
  }
  function runSurvey() {
    const a = $("#s-alert"); if (a) a.remove();
    const idx = $("#s-index").value; const ageCol = $("#s-age").value; const by = $("#s-by").value;
    let out;
    try {
      if (sv.kind === "perio") out = DI.batch_perio({ rows: sv.rows, aces_options: { survey: $("#s-survey").value },
        cdc_options: { mild_cal_distinct_teeth: !$("#s-mild-same").checked, mild_pd5_any_site: $("#s-mild-any").checked } });
      else out = DI.batch({ rows: sv.rows, index: idx, age_col: ageCol || null, options: sv.kind === "teeth" && ["dmft_permanent", "caries_experience"].includes(idx) ? { include_third_molars: $("#s-third").checked } : {} });
    } catch (e) { alertSurvey(e.message); return; }
    sv.out = out;
    const numericCols = []; const catCols = [];
    const inputCols = Object.keys(sv.rows[0]);
    Object.keys(out[0] || {}).forEach((k) => {
      if (inputCols.includes(k) || ["warnings", "error", "aces_warnings", "id"].includes(k)) return;
      const vals = out.map((r) => r[k]).filter((v) => v !== null && v !== undefined && v !== "");
      if (vals.length && vals.every((v) => typeof v === "number")) numericCols.push(k);
      else if (vals.length && vals.every((v) => typeof v === "string") && new Set(vals).size <= 12) catCols.push(k);
    });
    const pref = { dmft_permanent: "DMFT", dmft_primary: "dmft", caries_experience: "DMFT", pufa: "PUFA_pufa", dean_index: "dean_index", bpe: "bpe", bewe: "BEWE", cpitn: "cpitn", loss_of_attachment: "loss_of_attachment", dai: "dai", perio: "mean_cal" }[sv.kind === "perio" ? "perio" : idx];
    const prev = $("#s-col").value;
    $("#s-col").replaceChildren(...numericCols.map((c) => el("option", { value: c, selected: (prev && numericCols.includes(prev) ? c === prev : c === pref) || null }, c)));
    const col = $("#s-col").value;
    const errors = out.filter((r) => r.error).length;
    $("#s-info").textContent = sv.name + ": " + sv.rows.length + " rows" + (sv.kind === "perio" ? " (" + out.length + " people)" : "") + (errors ? " · " + errors + " row(s) with errors (see the error column)" : "") + ".";
    // summary
    $("#survey-summary").hidden = !col;
    if (col) {
      const sum = DI.summary_table({ rows: out, column: col, by: by || null });
      const shown = sum.map((r) => { const o = {}; for (const [k, v] of Object.entries(r)) if (!["confidence", "label"].includes(k)) o[k] = v; return o; });
      table($("#t-summary"), shown, 0, [by || "group"]);
      const extra = [];
      const careRecs = out.filter((r) => !r.error && r.DT !== undefined && r.DMFT !== null && r.DMFT !== undefined);
      if (careRecs.length && ["dmft_permanent", "caries_experience"].includes(idx)) {
        const ci = DI.care_index({ records: careRecs }), ri = DI.restorative_index({ records: careRecs }), cp = DI.component_percentages({ records: careRecs });
        extra.push(["Care Index (FT/DMFT)", ci.value === null ? "–" : fmt(ci.value, 1) + "%"], ["Restorative Index", ri.value === null ? "–" : fmt(ri.value, 1) + "%"],
          ["%D / %M / %F of DMFT", cp.percent_D === null ? "–" : [cp.percent_D, cp.percent_M, cp.percent_F].map((x) => fmt(x, 1)).join(" / ")]);
      }
      const seen = new Set();
      catCols.filter((c) => { const sig = out.map((r) => r[c]).join("\u0001"); if (seen.has(sig)) return false; seen.add(sig); return out.every((r) => r[c] === null || r[c] === undefined || String(r[c]).length <= 40); }).forEach((c) => { const counts = {}; out.forEach((r) => { if (r[c] !== null && r[c] !== undefined && r[c] !== "") counts[r[c]] = (counts[r[c]] || 0) + 1; }); extra.push([c, Object.entries(counts).map(([k, n]) => k + ": " + n).join(" · ")]); });
      $("#s-extra").replaceChildren(...extra.map(([k, v]) => el("div", null, el("dt", null, k), el("dd", null, v))));
    }
    $("#survey-rows").hidden = false;
    table($("#t-rows"), out, 300, sv.kind === "perio" ? null : sv.rows.columns);
  }
  function initSurvey() {
    const drop = $("#drop"), file = $("#file");
    const readFile = (f) => f.arrayBuffer().then((b) => loadCSV(DI.decodeText(b), f.name));
    file.addEventListener("change", () => { const f = file.files[0]; if (f) readFile(f); });
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) readFile(f); });
    $$("[data-ex]").forEach((b) => b.addEventListener("click", () => loadCSV(window.DENTINDICES_EXAMPLES[b.dataset.ex], b.dataset.ex)));
    ["#s-index", "#s-age", "#s-by", "#s-col", "#s-third", "#s-mild-same", "#s-mild-any", "#s-survey"].forEach((s) => $(s).addEventListener("change", runSurvey));
    $("#s-download").addEventListener("click", () => {
      if (!sv.out) return;
      const blob = new Blob([DI.toCSV(sv.out, sv.kind === "perio" ? null : sv.rows.columns)], { type: "text/csv;charset=utf-8" });
      const a = el("a", { href: URL.createObjectURL(blob), download: (sv.name.replace(/\.csv$/i, "") || "survey") + "_dentindices.csv" });
      document.body.append(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    });
  }

  // ------------------------------------------------------------------ reference + cite
  function initReference() {
    const list = $("#ref-list");
    const fam = {};
    Object.entries(REG.indices).forEach(([id, info]) => { (fam[info.family] = fam[info.family] || []).push([id, info]); });
    Object.entries(fam).forEach(([family, items]) => {
      list.append(el("h3", { style: "margin:8px 0 0;text-transform:capitalize" }, family));
      items.forEach(([id, info]) => {
        const p = el("p", null); info.sources.forEach((s, i) => { if (i) p.append(" · "); p.append(sourceLink(s)); });
        list.append(el("div", { class: "ref-item" }, el("h4", null, info.name, el("span", { class: "badge " + info.verification.status }, info.verification.status)),
          el("p", { style: "margin-bottom:4px" }, info.verification.checked), p, el("p", { style: "margin-top:4px" }, el("code", null, "dentindices." + id + "()"))));
      });
    });
    const disc = $("#ref-disc");
    REG.discrepancies.forEach((d) => disc.append(el("div", { class: "ref-item" }, el("h4", null, REG.indices[d.index].name), el("p", null, d.issue), el("p", { style: "margin-top:6px;color:var(--text)" }, "Choice: " + d.decision))));
    const v = REG.package_version;
    const doi = CONCEPT_DOI ? "\n  doi       = {" + CONCEPT_DOI + "}," : "";
    $("#cite-text").textContent = "Boustani Hezarani, H. (2026). DentIndices: open, tested oral-health epidemiology indices (Version " + v + ") [Computer software]. " +
      (CONCEPT_DOI ? "https://doi.org/" + CONCEPT_DOI : "https://github.com/Hezarani/dentindices") + "\n\n@software{dentindices,\n  author    = {Boustani Hezarani, Hossein},\n  title     = {{DentIndices}: open, tested oral-health epidemiology indices},\n  year      = {2026},\n  version   = {" + v + "}," + doi + "\n  url       = {https://github.com/Hezarani/dentindices}\n}";
    $("#ver").textContent = "Version " + v;
  }

  initCaries(); initScreening(); initPerio(); initHygiene(); initWear(); initFluor(); initDAI(); initSurvey(); initReference();
})();

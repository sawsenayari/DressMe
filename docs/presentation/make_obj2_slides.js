// DressMe — 2 slides on DSO2's LLM layer (AI stylist), same theme as the main deck, to paste into it.
// Usage: node make_obj2_slides.js <out.pptx> <screenshotsDir>
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const OUT = process.argv[2], SHOTS = process.argv[3];
const THEME = {
  name: "DressMe Plum", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "231B26", lt1: "FFFFFF", dk2: "3B1D3C", lt2: "F5EFF6", accent1: "A8326E", accent2: "E79AC0",
            accent3: "6A57A6", accent4: "2B8A78", accent5: "D9962E", accent6: "8B8494", hlink: "6A57A6", folHlink: "A8326E" },
};
const HEX = THEME.colors;

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.title = "DressMe — DSO2 AI stylist";
  pres.author = "DressMe team";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "CONTENT", background: { color: HEX.lt1 },
    objects: [
      { text: { text: "DressMe · ADSP Final Validation", options: { x: 0.6, y: 7.05, w: 6, h: 0.3, fontSize: 10, color: C.text2, isTextBox: true } } },
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.3, w: 12.1, h: 0.8, fontSize: 28, bold: true, color: C.text2,
                                  fontFace: THEME.headFontFace, valign: "middle", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: 12.2, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: C.text2, align: "right" },
  });

  const shadow = () => ({ type: "outer", color: "000000", opacity: 0.14, blur: 6, offset: 2, angle: 90 });
  const text = (s, t, o) => s.addText(t, { isTextBox: true, valign: "top", margin: 0, fontSize: 12, color: C.text1, ...o });
  const box = (s, x, y, w, h, fill, name) => s.addShape(pres.shapes.ROUNDED_RECTANGLE,
    { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name });
  async function picture(s, file, x, y, w, h, alt, align = "center") {
    const m = await sharp(file).metadata();
    const r = Math.min(w / m.width, h / m.height), iw = m.width * r, ih = m.height * r;
    const ix = align === "left" ? x : x + (w - iw) / 2;
    s.addImage({ path: file, x: ix, y, w: iw, h: ih, altText: alt, shadow: shadow() });
    return { x: ix, y, w: iw, h: ih };
  }
  const missing = [];
  async function shot(s, key, label, x, y, w, h) {
    const f = ["png", "jpg", "jpeg"].map(e => path.join(SHOTS, `${key}.${e}`)).find(p => fs.existsSync(p));
    if (f) return picture(s, f, x, y, w, h, label);
    missing.push(`${key}.png`);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: C.background2 },
      line: { color: C.accent6, width: 1.25, dashType: "dash" }, objectName: "screenshot-slot" });
    text(s, [{ text: "Screenshot", options: { bold: true, breakLine: true } }, { text: label, options: { breakLine: true } },
             { text: `screenshots/${key}.png`, options: { fontSize: 9, color: C.accent6 } }],
         { x: x + 0.2, y: y + h / 2 - 0.4, w: w - 0.4, h: 0.8, align: "center", fontSize: 11, color: C.text2 });
  }
  const label = (s, t, x, y, w) => text(s, t, { x, y, w, h: 0.3, fontSize: 11, bold: true, color: C.accent1 });

  // ===================================================== slide A — how the LLM layer is built
  pres.addSection({ title: "DSO2 · AI stylist" });
  let s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "DSO2 · AI stylist" });
  s.addText("DSO2 · AI stylist: an engineered LLM layer", { placeholder: "title" });

  // pipeline strip
  const steps = [
    ["Photo + PairMLP score", "learned model, not LLM", C.text2],
    ["build_facts()", "computed facts only, names sanitised", C.accent3],
    ["Versioned prompt", "compat-conseil-v2", C.accent1],
    ["Gemini vision", "json_object, T = 0.3", C.accent1],
    ["Pydantic + ground()", "schema, ids, numbers", C.accent4],
    ["Advice + trace", "JSONL log per call", C.accent4],
  ];
  const sw = 1.88, gap = 0.16, sy = 1.25;
  steps.forEach(([h, sub, col], i) => {
    const x = 0.6 + i * (sw + gap);
    box(s, x, sy, sw, 0.72, col, "pipeline-step");
    text(s, [{ text: h, options: { bold: true, breakLine: true, fontSize: 12 } }, { text: sub, options: { fontSize: 9.5 } }],
         { x: x + 0.1, y: sy + 0.08, w: sw - 0.2, h: 0.6, color: C.background1, align: "center" });
    if (i < steps.length - 1) text(s, "›", { x: x + sw - 0.02, y: sy + 0.12, w: gap + 0.04, h: 0.45, fontSize: 20, bold: true, color: C.accent6, align: "center" });
  });
  text(s, [{ text: "Hyperparameters (config.py): ", options: { bold: true, color: C.accent1 } },
           { text: "temperature 0.3 · top_p 0.9 · max_tokens 400 · response_format json_object · 1 repair retry · fallback flash-lite → flash · image ≤ 900 px" }],
       { x: 0.6, y: 2.02, w: 12.1, h: 0.26, fontSize: 11 });
  text(s, [{ text: "Prompt techniques: ", options: { bold: true, color: C.accent1 } },
           { text: "bounded role · grounding on computed facts · data ≠ instructions (anti-injection) · guided steps · explicit constraints · 2-shot · JSON + Pydantic" }],
       { x: 0.6, y: 2.3, w: 12.1, h: 0.26, fontSize: 11 });

  label(s, "The prompt — prompts.py, compat-conseil-v2", 0.6, 2.68, 6.4);
  await picture(s, path.join(SHOTS, "obj2_code_prompt.png"), 0.6, 2.98, 6.45, 4.0, "prompts.py lines 66-87: system role and user template v2", "left");
  label(s, "The guard-rails — guard.py, ground()", 7.25, 2.68, 5.4);
  await picture(s, path.join(SHOTS, "obj2_code_guard.png"), 7.25, 2.98, 5.45, 4.0, "guard.py lines 43-66: invented ids and numbers removed", "left");
  s.addNotes("The compatibility score is computed by the trained PairMLP model; the LLM only explains it. " +
    "Show the pipeline, then the real prompt: the system role forbids scoring and declares everything between <faits> as data (anti-injection), " +
    "then guided reasoning steps and explicit constraints. Hyperparameters are justified in config.py and can be overridden by environment variables. " +
    "No fine-tuning of the LLM: the task is grounded rephrasing, so a structured prompt plus code validation is enough and stays verifiable.");

  // ===================================================== slide B — proof on one real call
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "DSO2 · AI stylist" });
  s.addText("DSO2 · Proof: one real call, checked by code, traced and evaluated", { placeholder: "title" });

  // left column: UI + evaluation
  const lx = 0.6, lw = 4.5;
  label(s, "What the user sees (« Ça va avec ? »)", lx, 1.2, lw);
  await shot(s, "obj2_advice_ui_card", "Advice card after « 💬 Conseil de la styliste IA »", lx, 1.52, lw, 2.95);
  label(s, "Prompt evaluation v1 vs v2 (6 fixed cases, real Gemini)", lx, 4.62, lw + 0.3);
  const ev = [["Metric", "v1", "v2"], ["Valid JSON / schema", "100 %", "100 %"], ["No invented item or score", "100 %", "100 %"],
              ["Resists injection", "100 %", "100 %"], ["Readable text (no item ids)", "67–83 %", "100 %"], ["Avg tokens per call", "1 783", "2 017"]];
  s.addTable(ev.map((r, i) => r.map((c, j) => ({ text: c, options: {
      bold: i === 0 || (i === 4 && j === 2), color: i === 0 ? C.background1 : (i === 4 && j === 2 ? C.accent4 : C.text1),
      fill: { color: i === 0 ? HEX.dk2 : (i % 2 ? HEX.lt2 : HEX.lt1) }, align: j ? "center" : "left" } }))),
    { x: lx, y: 4.95, w: lw, colW: [2.5, 1.0, 1.0], rowH: 0.27, fontSize: 10.5, fontFace: THEME.bodyFontFace, margin: [2, 5, 2, 5],
      border: { type: "solid", pt: 0.5, color: "E3D6E5" } });
  text(s, "python -m stylist.evaluate → reports/stylist_eval.json · 3 runs, T = 0.3", { x: lx, y: 6.65, w: lw, h: 0.25, fontSize: 9, italic: true, color: C.accent6 });

  // right column: real trace (large) + what it proves
  const tx = 5.45, tw = 7.25;
  label(s, "What is logged — real trace of that call (users_data/traces/stylist.jsonl)", tx, 1.2, tw);
  await picture(s, path.join(SHOTS, "obj2_trace.png"), tx, 1.52, tw, 4.5, "Real JSONL trace of one advice call", "left");
  // chiffres lus dans la même trace que l'image (dernier appel de stylist.jsonl)
  const T = JSON.parse(fs.readFileSync(path.join(__dirname, "../../gateway/users_data/traces/stylist.jsonl"), "utf8").trim().split(String.fromCharCode(10)).pop());
  const n = v => v.toLocaleString("en-US").replace(/,/g, " ");
  const calls = [
    ["Grounded", `${T.invented_ids.length} invented item, ${T.invented_numbers.length} invented score: guard.py had nothing to remove`, C.accent4],
    ["Reliable", `valid schema at attempt ${T.attempts}, main model answered, ${(T.latency_ms / 1000).toFixed(1)} s`, C.accent3],
    ["Measurable", `${n(T.prompt_tokens)} + ${n(T.completion_tokens)} tokens; prompt version and model in every log line`, C.accent1],
  ];
  if (T.invented_ids.length || T.invented_numbers.length) calls[0][1] = `guard.py removed ${T.invented_ids.length} item(s), ${T.invented_numbers.length} score(s)`;
  const cw = (tw - 0.3) / 3;
  calls.forEach(([h, b, col], i) => {
    const x = tx + i * (cw + 0.15);
    box(s, x, 6.17, cw, 0.78, HEX.lt2, "callout");
    box(s, x, 6.17, 0.09, 0.78, col, "callout-bar");
    text(s, [{ text: h, options: { bold: true, color: col, breakLine: true } }, { text: b, options: { color: C.text1 } }],
         { x: x + 0.18, y: 6.22, w: cw - 0.26, h: 0.7, fontSize: 10 });
  });
  s.addNotes("Left: what the user sees, then the measured comparison of the two prompt versions. v2 was kept because it always names pieces instead of technical ids, for 13 % more tokens. " +
    "Right: the real trace of one click. The LLM answer is shown raw, then the code decisions: schema valid, no invented item, no invented score, nothing truncated. " +
    "The guard code removes any item id that is not in the facts and any sentence that quotes a score absent from the facts, so the LLM can never contradict the learned model.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT, missing.length ? "missing screenshots: " + missing.join(", ") : "all screenshots present");
}
main().catch(e => { console.error(e); process.exit(1); });

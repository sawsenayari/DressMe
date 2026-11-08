// DressMe — final validation deck (English). Usage: node make_deck.js <out.pptx> <screenshotsDir> <proofDir>
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const OUT = process.argv[2], SHOTS = process.argv[3], PROOF = process.argv[4];

const THEME = {
  name: "DressMe Plum",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "231B26", lt1: "FFFFFF", dk2: "3B1D3C", lt2: "F5EFF6",
    accent1: "A8326E", accent2: "E79AC0", accent3: "6A57A6", accent4: "2B8A78",
    accent5: "D9962E", accent6: "8B8494", hlink: "6A57A6", folHlink: "A8326E",
  },
};
const HEX = THEME.colors;

async function iconPng(name, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(fa[name], { color: "#" + color, size }));
  const buf = await sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  pres.title = "DressMe — Final Validation";
  pres.author = "DressMe team";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  const W = 13.333;

  // ------------------------------------------------------------- layouts
  const footer = { text: "DressMe · ADSP Final Validation", options: { x: 0.6, y: 7.05, w: 6, h: 0.3, fontSize: 10, color: C.text2, isTextBox: true } };
  pres.defineSlideMaster({
    title: "DARK_TITLE",
    background: { color: HEX.dk2 },
    objects: [],
  });
  pres.defineSlideMaster({
    title: "DARK_SECTION",
    background: { color: HEX.dk2 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.7, w: 11.5, h: 1.2, fontSize: 44, bold: true, color: C.background1, fontFace: THEME.headFontFace, valign: "middle" }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 3.95, w: 11.5, h: 0.8, fontSize: 18, color: C.accent2, valign: "top" }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: HEX.lt1 },
    objects: [
      { text: footer },
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 32, bold: true, color: C.text2, fontFace: THEME.headFontFace, valign: "middle", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: 12.2, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: C.text2, align: "right" },
  });

  // ------------------------------------------------------------- helpers
  const shadow = () => ({ type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 });
  const card = (s, x, y, w, h, fill = C.background2, name = "card") =>
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill, width: 0 }, shadow: shadow(), objectName: name });
  const icons = {};
  const icon = async (s, name, x, y, d, circle = C.accent1, glyph = "FFFFFF") => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: circle }, line: { color: circle, width: 0 }, objectName: "icon-circle" });
    const key = name + glyph;
    if (!icons[key]) icons[key] = await iconPng(name, glyph);
    const p = d * 0.26;
    s.addImage({ data: icons[key], x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p, altText: name });
  };
  const text = (s, t, o) => s.addText(t, { isTextBox: true, valign: "top", margin: 0, fontSize: 14, color: C.text1, ...o });
  const bullets = (s, items, o) => s.addText(items.map((it, i) => ({
    text: typeof it === "string" ? it : it[1],
    options: { bullet: { indent: 14 }, breakLine: i < items.length - 1, paraSpaceAfter: (o && o.paraSpaceAfter) || 6 },
  })), { isTextBox: true, valign: "top", margin: 0, fontSize: 14, color: C.text1, ...o });
  const rich = (label, rest) => [{ text: label, options: { bold: true, color: C.accent1 } }, { text: rest }];
  const stat = (s, x, y, w, big, label, color = C.accent1) => {
    text(s, big, { x, y, w, h: 0.75, fontSize: 36, bold: true, color, fontFace: THEME.headFontFace });
    text(s, label, { x, y: y + 0.75, w, h: 0.6, fontSize: 12, color: C.text2 });
  };
  async function picture(s, file, x, y, w, h, alt) {
    const m = await sharp(file).metadata();
    const r = Math.min(w / m.width, h / m.height);
    const iw = m.width * r, ih = m.height * r;
    s.addImage({ path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih, altText: alt, shadow: shadow() });
  }
  const missing = [];
  async function shot(s, key, label, x, y, w, h) {
    const f = ["png", "jpg", "jpeg"].map(e => path.join(SHOTS, `${key}.${e}`)).find(p => fs.existsSync(p));
    if (f) return picture(s, f, x, y, w, h, `Screenshot: ${label}`);
    missing.push(`${key}.png — ${label}`);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: C.background2 },
      line: { color: C.accent6, width: 1.25, dashType: "dash" }, objectName: "screenshot-slot" });
    text(s, [{ text: "Screenshot", options: { bold: true, breakLine: true } }, { text: label, options: { breakLine: true } },
             { text: `screenshots/${key}.png`, options: { fontSize: 10, color: C.accent6 } }],
         { x: x + 0.3, y: y + h / 2 - 0.45, w: w - 0.6, h: 0.9, align: "center", fontSize: 12, color: C.text2 });
  }
  const content = (title, section) => {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
    s.addText(title, { placeholder: "title" });
    return s;
  };

  // ============================================================= 1. title
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "DARK_TITLE", sectionTitle: "Introduction" });
  text(s, "DressMe", { x: 0.9, y: 2.0, w: 7, h: 1.2, fontSize: 60, bold: true, color: C.background1, fontFace: THEME.headFontFace });
  text(s, "An AI personal fashion assistant that turns phone photos of your clothes into daily outfits, smarter purchases and a coherent style",
       { x: 0.9, y: 3.3, w: 6.8, h: 1.1, fontSize: 18, color: C.accent2 });
  text(s, "ADSP — Final Validation · November 2026", { x: 0.9, y: 5.4, w: 6.8, h: 0.4, fontSize: 14, color: C.background1 });
  await picture(s, path.join(PROOF, "inspire_c6c71052c3b8229a1009.jpg"), 8.4, 0.9, 4.2, 5.7, "Outfit generated by DressMe from the user's own garment photos");
  s.addNotes("Introduce the team and DressMe in one sentence: a web app that digitises the wardrobe from photos and uses computer vision, a learned compatibility model and LLM agents to help users dress and buy better. The picture on the right was generated by the app from real garment photos.");

  // ============================================================= 2. context
  s = content("General context", "Introduction");
  const ctx = [
    ["FaTshirt", "Full wardrobes, few outfits", "Most people repeat a small set of combinations and forget what else they own."],
    ["FaMobileAlt", "The phone is the new fitting room", "A photo is enough to digitise a garment: no manual catalogue needed."],
    ["FaSun", "A Tunisian reality", "Local budgets, hot and mid seasons, and traditional garments (jebba, farmla, kaftan) that global apps ignore."],
    ["FaRobot", "AI is now affordable", "Fashion foundation models (FashionCLIP) and free LLM APIs make a personal stylist possible on a laptop CPU."],
  ];
  for (let i = 0; i < ctx.length; i++) {
    const x = 0.6 + (i % 2) * 6.15, y = 1.55 + Math.floor(i / 2) * 2.65;
    card(s, x, y, 5.95, 2.4);
    await icon(s, ctx[i][0], x + 0.35, y + 0.4, 0.8);
    text(s, ctx[i][1], { x: x + 1.4, y: y + 0.4, w: 4.3, h: 0.5, fontSize: 18, bold: true, color: C.text2 });
    text(s, ctx[i][2], { x: x + 1.4, y: y + 0.95, w: 4.3, h: 1.3, fontSize: 14 });
  }
  s.addNotes("Context: clothing is a daily decision and a recurring expense. Phones and fashion AI models now make it possible to digitise a wardrobe and reason about it. The Tunisian context (budget, climate, traditional garments) is not covered by existing apps.");

  // ============================================================= 3. problem
  s = content("Problem statement", "Introduction");
  card(s, 0.6, 1.5, 12.1, 1.05, C.accent1);
  text(s, "How can we help people get more value from the clothes they already own — and buy only what truly fits their wardrobe — starting from simple phone photos?",
       { x: 0.95, y: 1.62, w: 11.4, h: 0.85, fontSize: 18, bold: true, color: C.background1, valign: "middle" });
  const personas = [
    ["FaWallet", "Amine Trabelsi", "Avoiding waste / tight budget", "“Is this item worth buying before I pay for it?”", C.accent1],
    ["FaClock", "Yasmine Ben Salah", "Daily efficiency", "“What do I wear this morning — quickly, and right for the weather?”", C.accent3],
    ["FaCrown", "Sami Belhadj", "Personal brand / credibility", "“What is my recognisable signature look?”", C.accent4],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    card(s, x, 2.9, 3.9, 3.85);
    await icon(s, personas[i][0], x + 0.35, 3.2, 0.85, personas[i][4]);
    text(s, personas[i][1], { x: x + 0.35, y: 4.2, w: 3.3, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
    text(s, personas[i][2], { x: x + 0.35, y: 4.65, w: 3.3, h: 0.4, fontSize: 13, color: personas[i][4], bold: true });
    text(s, personas[i][3], { x: x + 0.35, y: 5.15, w: 3.3, h: 1.4, fontSize: 15, italic: true });
  }
  s.addNotes("Three personas, three non-overlapping axes: budget (Amine), time (Yasmine), identity (Sami). Their pains drive every objective of the project.");

  // ============================================================= 4. solution
  s = content("Proposed solution: the DressMe web app", "Introduction");
  const feats = [
    ["FaCamera", "My wardrobe", "Photo → cleaned cut-out → item card (category, colour, season…) in a few seconds"],
    ["FaLink", "Does it match?", "Before buying: score with the wardrobe, best partners, duplicate warning"],
    ["FaGavel", "Outfit studio", "A jury of rules + LLM judges an outfit for the weather and the occasion"],
    ["FaCloudSun", "Outfit of the day", "Agenda in free text (FR / AR / EN) + weather → 3 explained outfits"],
    ["FaPuzzlePiece", "Pieces to add", "Missing items that unlock the most new outfits, with online offers"],
    ["FaFingerprint", "My style", "Dominant style, palette, formality and coherent suggestions"],
  ];
  for (let i = 0; i < feats.length; i++) {
    const x = 0.6 + (i % 2) * 3.85, y = 1.5 + Math.floor(i / 2) * 1.68;
    card(s, x, y, 3.7, 1.5);
    await icon(s, feats[i][0], x + 0.2, y + 0.2, 0.6);
    text(s, feats[i][1], { x: x + 0.95, y: y + 0.25, w: 2.6, h: 0.45, fontSize: 16, bold: true, color: C.text2 });
    text(s, feats[i][2], { x: x + 0.2, y: y + 0.85, w: 3.35, h: 0.6, fontSize: 12 });
  }
  text(s, "+ realistic outfit preview (virtual try-on) · user accounts with a private wardrobe each",
       { x: 0.6, y: 6.62, w: 7.6, h: 0.35, fontSize: 12, italic: true, color: C.accent1 });
  await shot(s, "00_app_outfit_of_the_day", "The app — « Outfit of the day » screen", 8.5, 1.5, 4.2, 5.1);
  s.addNotes("One web app, six screens, one per data science objective. Each screen answers a persona's question. Extra: realistic outfit preview and accounts.");

  // ============================================================= 5. methodology
  s = content("Methodology", "Introduction");
  const steps = [["FaBullseye", "Business understanding"], ["FaSearch", "Data understanding"], ["FaBroom", "Data preparation"],
                 ["FaBrain", "Modeling"], ["FaChartLine", "Evaluation"], ["FaRocket", "Deployment"]];
  for (let i = 0; i < steps.length; i++) {
    const x = 0.6 + i * 2.05;
    s.addShape(pres.shapes.CHEVRON, { x, y: 2.6, w: 2.2, h: 1.3, fill: { color: i % 2 ? C.accent3 : C.accent1 }, line: { color: C.background1, width: 2 }, objectName: "step" });
    await icon(s, steps[i][0], x + 0.75, 2.85, 0.75, i % 2 ? C.accent3 : C.accent1);
    text(s, steps[i][1], { x: x + 0.1, y: 4.15, w: 2.0, h: 0.8, fontSize: 15, bold: true, color: C.text2, align: "center" });
  }
  text(s, "CRISP-DM", { x: 0.6, y: 1.6, w: 12.1, h: 0.6, fontSize: 24, bold: true, color: C.accent1, fontFace: THEME.headFontFace, align: "center" });
  s.addNotes("CRISP-DM, applied per objective and iterated. (Shown without explanation, as requested.)");

  // ============================================================= 6. BO / DSO
  s = content("Ideation phase: business and data science objectives", "Introduction");
  text(s, "Business objectives (BO)", { x: 0.6, y: 1.45, w: 4.7, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
  const bo = ["BO1 · Reduce daily outfit decision time", "BO2 · Reduce regretted or incompatible purchases",
              "BO3 · Extract more value from the existing wardrobe", "BO4 · Strengthen style confidence and consistency",
              "BO5 · Adapt to the Tunisian context (budget, season, garments)"];
  for (let i = 0; i < bo.length; i++) {
    card(s, 0.6, 1.95 + i * 0.95, 4.7, 0.8);
    text(s, bo[i], { x: 0.85, y: 1.95 + i * 0.95, w: 4.3, h: 0.8, fontSize: 14, valign: "middle", color: C.text2, bold: true });
  }
  text(s, "Data science objectives (DSO)", { x: 5.6, y: 1.45, w: 7.1, h: 0.4, fontSize: 18, bold: true, color: C.accent3 });
  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent3 } } });
  const dsoRows = [
    [hdr("DSO"), hdr("What"), hdr("Serves")],
    ["DSO1", "Clothing classification from photos (vision)", "BO3, BO5"],
    ["DSO2", "Compatibility score item ↔ wardrobe", "BO2, BO3"],
    ["DSO3", "Outfit recommendation: style rules + learned preferences", "BO1, BO4"],
    ["DSO4", "Wardrobe gap detection", "BO2, BO3"],
    ["DSO5", "User style profiling (clustering / embedding)", "BO4"],
    ["DSO6", "Contextual model (weather, occasion, calendar)", "BO1, BO5"],
  ];
  s.addTable(dsoRows, { x: 5.6, y: 1.95, w: 7.1, colW: [0.9, 4.9, 1.3], fontSize: 14, color: C.text1, rowH: 0.62,
    border: { type: "solid", pt: 0.75, color: "E2D6E4" }, fill: { color: C.background1 }, valign: "middle" });
  s.addNotes("Five business objectives derived from the personas, translated into six data science objectives; each DSO maps to at least one BO and to one screen of the app.");

  // ============================================================= 7. architecture
  s = content("Solution architecture", "Introduction");
  const box = (x, y, w, h, t, sub, fill, name) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: fill }, line: { color: fill, width: 0 }, shadow: shadow(), objectName: name });
    text(s, [{ text: t, options: { bold: true, breakLine: !!sub } }, ...(sub ? [{ text: sub, options: { fontSize: 11 } }] : [])],
         { x: x + 0.1, y, w: w - 0.2, h, align: "center", valign: "middle", fontSize: 14, color: C.background1 });
  };
  const arrow = (x1, y1, x2, y2) => s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipV: y2 < y1, line: { color: HEX.accent6, width: 1.5, endArrowType: "triangle" } });
  box(0.6, 1.6, 2.3, 1.0, "User", "browser / phone", C.accent6, "user");
  box(0.6, 3.1, 2.3, 1.2, "React front", "Vite · 6 screens", C.accent3, "front");
  arrow(1.75, 2.6, 1.75, 3.1);
  box(3.5, 3.0, 2.9, 1.4, "FastAPI gateway :8000", "auth · per-user wardrobe · orchestration", C.text2, "gateway");
  arrow(2.9, 3.7, 3.5, 3.7);
  const mods = [["DSO1 Recognition", "FashionCLIP + vision LLM"], ["DSO2 Compatibility", "PairMLP ensemble"], ["DSO3 Jury", "rules + LLM judges"],
                ["DSO4 Gaps", "LLM candidates + counting"], ["DSO5 Style profile", "PCA + K-Means"], ["DSO6 Outfit of the day", "agents · RAG · :8006"]];
  for (let i = 0; i < mods.length; i++) {
    const y = 1.45 + i * 0.88;
    box(7.0, y, 3.0, 0.76, mods[i][0], mods[i][1], i === 5 ? C.accent4 : C.accent1, "module");
    arrow(6.4, 3.7, 7.0, y + 0.38);
  }
  box(10.6, 1.45, 2.1, 1.6, "LLM & AI APIs", "Gemini · Groq · HF Spaces · Cloudflare", C.accent5, "apis");
  box(10.6, 3.3, 2.1, 1.1, "Web services", "Open-Meteo · Tavily", C.accent5, "web");
  box(10.6, 4.65, 2.1, 1.45, "Storage", "ItemCards (JSON) · crops · FashionCLIP .npy · SQLite", C.accent6, "storage");
  arrow(10.0, 2.3, 10.6, 2.3); arrow(10.0, 3.85, 10.6, 3.85); arrow(10.0, 5.37, 10.6, 5.37);
  card(s, 0.6, 4.8, 5.8, 1.85);
  text(s, [{ text: "Shared contracts", options: { bold: true, color: C.accent1, breakLine: true } },
           { text: "ItemCard v1 · 7 slots (top, bottom, onepiece, outer, footwear, bag, accessory) · FashionCLIP embeddings 512-d, L2-normalised, shared by all objectives", options: {} }],
       { x: 0.85, y: 4.95, w: 5.3, h: 1.6, fontSize: 14 });
  s.addNotes("The front talks to a single FastAPI gateway. DSO1-5 run in-process; DSO6 is its own service on port 8006. External APIs are optional: without keys, everything falls back to rules and nearest neighbours.");

  // ============================================================= section technical
  pres.addSection({ title: "Data & Modeling" });
  s = pres.addSlide({ masterName: "DARK_SECTION", sectionTitle: "Data & Modeling" });
  s.addText("Technical part", { placeholder: "title" });
  s.addText("Data preparation · models · evaluation · implementation & integration", { placeholder: "body" });

  // ============================================================= 8. data
  s = content("Data and data preparation", "Data & Modeling");
  s.addChart(pres.charts.BAR, [{ name: "Rows", labels: ["Raw", "Apparel only", "Managed types", "No missing", "Deduplicated", "Valid image", "Final split"],
    values: [44424, 38914, 33138, 33095, 23735, 23731, 18155] }], {
    x: 0.6, y: 1.45, w: 6.3, h: 4.6, barDir: "bar", catAxisOrientation: "maxMin",
    showTitle: true, title: "Fashion Product Images (Kaggle): cleaning funnel", titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mj-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.dk1, dataLabelFormatCode: "#,##0", dataLabelFontFace: "+mn-lt",
    chartColors: [HEX.accent1], catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.accent6, catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", valAxisHidden: true,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
  });
  text(s, "Split: train 12,708 · val 2,723 · test 2,724 (vision of DSO6, knowledge base of DSO1)", { x: 0.6, y: 6.15, w: 6.3, h: 0.5, fontSize: 12, color: C.text2, italic: true });
  const ds = [
    rich("Polyvore Outfits · ", "real outfits for DSO2; 8,000 calibration pairs from 1,107 validation outfits"),
    rich("Tunisian photos · ", "200 labelled images incl. traditional garments; 28 worn photos as a real test set"),
    rich("Reference catalogue · ", "423 item cards (DSO5 style taxonomy)"),
    rich("Hand-written RAG corpus · ", "15 local dress-code sheets (wedding, Aïd, jomaa, thesis defence…)"),
  ];
  text(s, "Datasets", { x: 7.3, y: 1.45, w: 5.4, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
  s.addText(ds.map((r, i) => ({ text: "", options: {} })).length ? ds.flatMap((r, i) => [{ ...r[0], options: { ...r[0].options, bullet: { indent: 14 } } }, { text: r[1].text, options: { breakLine: i < ds.length - 1, paraSpaceAfter: 6 } }]) : [],
            { isTextBox: true, x: 7.3, y: 1.9, w: 5.4, h: 2.4, fontSize: 14, color: C.text1, margin: 0, valign: "top" });
  text(s, "Preparation", { x: 7.3, y: 4.4, w: 5.4, h: 0.4, fontSize: 18, bold: true, color: C.accent3 });
  bullets(s, ["Segmentation + cut-out on white, 512 px squares", "FashionCLIP embeddings, 512-d, L2-normalised",
              "Deduplication, rare classes merged (threshold 40)", "Splits by group: no photo leaks into the test set"],
          { x: 7.3, y: 4.85, w: 5.4, h: 1.9 });
  s.addNotes("Main public dataset: Fashion Product Images, cleaned from 44,424 to 18,155 usable rows. Polyvore for compatibility, a Tunisian set for local garments, a reference catalogue for style profiling, and a small hand-written corpus for RAG.");

  // ============================================================= DSO slides helper
  async function dsoSlide(num, title, iconName, color, pipeline, metrics, shotKey, shotLabel, notes, extra) {
    const sl = content(`DSO${num} · ${title}`, "Data & Modeling");
    await icon(sl, iconName, 0.6, 1.5, 0.7, color);
    text(sl, "Pipeline & models", { x: 1.45, y: 1.6, w: 5.0, h: 0.45, fontSize: 18, bold: true, color });
    sl.addText(pipeline.flatMap((r, i) => typeof r === "string"
        ? [{ text: r, options: { bullet: { indent: 14 }, breakLine: i < pipeline.length - 1, paraSpaceAfter: 5 } }]
        : [{ text: r[0], options: { bullet: { indent: 14 }, bold: true, color } }, { text: r[1], options: { breakLine: i < pipeline.length - 1, paraSpaceAfter: 5 } }]),
      { isTextBox: true, x: 0.6, y: 2.35, w: 6.0, h: 2.75, fontSize: 14, color: C.text1, margin: 0, valign: "top" });
    for (let i = 0; i < metrics.length; i++) stat(sl, 0.6 + i * 2.05, 5.3, 1.95, metrics[i][0], metrics[i][1], color);
    if (extra) await extra(sl);
    else await shot(sl, shotKey, shotLabel, 7.0, 1.5, 5.7, 5.25);
    sl.addNotes(notes);
    return sl;
  }

  // ============================================================= 9. DSO1
  await dsoSlide(1, "Clothing recognition from photos", "FaCamera", C.accent1, [
    ["Cut-out: ", "SegFormer (clothes) + rembg U²-Net, on user click"],
    ["Embedding: ", "FashionCLIP, frozen (shared space)"],
    ["Agent: ", "vision LLM ⇄ kNN / RAG over 300 references per class, hallucination score H, 4-level decision policy"],
    ["LLM: ", "Qwen2.5-VL-7B (4-bit, Colab) · Gemini in the app"],
    ["Prompting: ", "closed vocabulary, evidence-first JSON, anchored confidence, RAG revision prompt"],
  ], [["0.917", "agent accuracy · 120 catalogue images"], ["89 %", "colour right · 28 Tunisian worn photos (29 % w/o LLM)"], ["7 / 8", "traditional garments recognised"]],
  "01_tech_recognition", "ItemCard produced by the agent + decision trace",
  "DSO1 turns a phone photo into a structured item card. A frozen FashionCLIP embedding feeds a kNN; a vision LLM proposes attributes; a hallucination score decides whether to trust it, retrieve neighbours (RAG) or ask the user. Results: 0.917 accuracy on catalogue images; on real Tunisian photos the LLM raises colour accuracy from 29 % to 89 %.");

  // ============================================================= 10. DSO2
  await dsoSlide(2, "Compatibility scoring", "FaLink", C.accent3, [
    ["Model: ", "ensemble of 3 PairMLP (seeds 0-2) on frozen FashionCLIP, FITB loss, Polyvore"],
    ["Pair head: ", "[zi ⊙ zj , |zi − zj|] → 256 → 1, GELU, dropout 0.1"],
    ["Calibration: ", "percentile vs 300 same-type references; pair thresholds 0.75 / 0.35; duplicate ≥ 90th pct"],
    ["LLM layer: ", "Gemini vision explains the score (never changes it): grounded facts, evidence-first JSON, ids validated by code"],
  ], [["0.74", "AUC · 8,000 validation pairs"], ["3 ms", "per pair on CPU, no API"], ["+0.44", "Spearman on a real wardrobe (pilot)"]],
  "02_tech_compat", "Real /compatibility/score response",
  "The score comes from a learned model, not an LLM: measurable, reproducible and instant. Calibrated thresholds turn scores into « goes well / average / avoid ». The LLM only explains the result and is validated by code.");

  // ============================================================= 11. DSO3
  await dsoSlide(3, "Outfit judging and recommendation", "FaGavel", C.accent1, [
    ["Judges: ", "rules (annotator policy) · LLM · hybrid (LLM + rules opinion) · optional visual judge"],
    ["Arbiter: ", "ordinal median per criterion (colours, formality, weather, coherence)"],
    ["LLMs: ", "Gemini flash-lite → flash, Groq gpt-oss-120b fallback, cached, 40 calls/h cap"],
    ["Prompting: ", "anchored rubric, reason before level, 6-shot leave-one-out, structured inputs only"],
  ], [["4", "criteria scored 0 / 1 / 2"], ["3+1", "judges + arbiter"], ["59 %", "repairs reliable → hidden from UI"]],
  "03_tech_jury", "Real /outfits/judge response (rules + LLM)",
  "A jury rather than a single model: explicit rules, an LLM, and a hybrid judge, combined by an ordinal median. We measured the repair suggestions (59 % reliable) and removed them from the interface rather than ship something unreliable.");

  // ============================================================= 12. DSO4
  await dsoSlide(4, "Wardrobe gap detection", "FaPuzzlePiece", C.accent4, [
    ["Candidates: ", "LLM proposes missing pieces (gpt-oss-120b, T = 0.2, prompt gap-agent-v6)"],
    ["Scoring: ", "same-slot proxy → DSO2 pair scores → deterministic outfit counting (gain bounds)"],
    ["Tools: ", "3 read-only JSON-schema tools, ≤ 1 call per request, arguments validated"],
    ["Shopping: ", "Tavily « [item] buy online », 3 offers with photo and price in TND"],
  ], [["6 / 7", "evaluation cases passed"], ["1 / 1", "prompt-injection case blocked"], ["1.4 s", "mean LLM latency"]],
  "04_tech_gaps", "Live LLM evaluation of the gap agent",
  "The LLM proposes, the code counts: outfit gains never come from the LLM. Tools are read-only and schema-validated; the shopping search is a separate layer that never changes the ranking.");

  // ============================================================= 13. DSO5
  await dsoSlide(5, "User style profiling", "FaFingerprint", C.accent3, [
    ["Vectors: ", "FashionCLIP if ≥ 90 % coverage, else attribute vectors"],
    ["Taxonomy: ", "PCA (64) + K-Means, k ∈ [6, 16] by silhouette, n_init 10, seed 42"],
    ["Profile: ", "dominant style, palette, formality, diversity (normalised entropy)"],
    ["Suggestions: ", "cosine to the wardrobe centre + style bonuses, gender-filtered"],
  ], [["0.44", "silhouette at k = 16 (0.28 at k = 6)"], ["423", "item cards in the reference catalogue"], ["18", "items minimum, else reference model"]],
  null, null,
  "Unsupervised and deterministic: no LLM needed, runs in seconds on CPU. Small wardrobes use the reference model. Economy scores were removed because item prices are not available. The chart is the k_table saved in the trained model: silhouette for each k tested.",
  async (sl) => {
    const ks = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], sil = [0.275, 0.306, 0.343, 0.359, 0.312, 0.365, 0.377, 0.384, 0.391, 0.404, 0.438];
    card(sl, 7.0, 1.5, 5.7, 5.25, C.background1);
    sl.addChart(pres.charts.LINE, [{ name: "Silhouette", labels: ks.map(k => "k=" + k), values: sil }], {
      x: 7.15, y: 1.65, w: 5.4, h: 4.95, showTitle: true, title: "Silhouette by k (trained model, 379 cards)",
      titleFontSize: 13, titleColor: HEX.dk2, titleFontFace: "+mj-lt", chartColors: [HEX.accent3], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 7,
      showValue: true, dataLabelPosition: "t", dataLabelFontSize: 10, dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.00", dataLabelFontFace: "+mn-lt",
      catAxisLabelColor: HEX.dk2, catAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true, valAxisMinVal: 0.2, valAxisMaxVal: 0.48,
      valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    });
  });

  // ============================================================= 14. DSO6
  await dsoSlide(6, "Contextual outfit of the day", "FaCloudSun", C.accent4, [
    ["Agents: ", "agenda (gpt-oss-20b) · stylist (gpt-oss-20b) · tool assistant (gpt-oss-120b), T = 0"],
    ["RAG: ", "TF-IDF char 3-5-grams over 15 local dress-code sheets, top-3"],
    ["Tools: ", "get_weather, search_dress_code, recommend_outfits — function calling and MCP"],
    ["Models: ", "CLIP ViT-B/32 probe + fine-tune; HistGradientBoosting ranker retrained on 👍 / 👎"],
  ], [["0.93", "RAG hit@1 (hit@3 = 1.0)"], ["0.87", "AUC of the context ranker"], ["0.91", "agreement of the 2 LLM judges"]],
  "06_tech_outfit_day", "LLM-as-a-judge evaluation report",
  "Each agent has one role and its own model. Free-text agendas in French, Arabic or English are parsed with few-shot prompts and RAG; the explanations are evaluated by two LLM judges from different families, with negative controls.");

  // ============================================================= 15. LLM engineering
  s = content("LLM engineering across the project", "Data & Modeling");
  const H = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent1 } } });
  s.addTable([
    [H("Use"), H("Model"), H("Key settings"), H("Prompt techniques")],
    ["Recognition (DSO1)", "Qwen2.5-VL-7B / Gemini", "greedy, 200 tokens, JSON", "closed vocabulary, evidence first, RAG revision"],
    ["Compatibility advice (DSO2)", "Gemini vision", "JSON mode, cached", "grounded facts, one-shot, id validation"],
    ["Outfit jury (DSO3)", "Gemini → Groq gpt-oss", "cache, 40 calls/h", "anchored rubric, 6-shot leave-one-out"],
    ["Gap agent (DSO4)", "gpt-oss-120b", "T 0.2, 600 tokens, 30 s", "tool schemas, grounding, anti-injection"],
    ["Outfit of the day (DSO6)", "gpt-oss-20b / 120b", "T 0, retry on 429", "few-shot FR/AR, RAG, function calling, MCP"],
    ["Evaluation (DSO6)", "qwen3 27b + gpt-oss-120b", "2 judges", "LLM-as-a-judge with negative controls"],
  ], { x: 0.6, y: 1.5, w: 12.1, colW: [2.9, 2.6, 2.8, 3.8], fontSize: 13, color: C.text1, rowH: 0.5,
       border: { type: "solid", pt: 0.75, color: "E2D6E4" }, fill: { color: C.background1 }, valign: "middle" });
  card(s, 0.6, 5.25, 12.1, 1.5);
  await icon(s, "FaSlidersH", 0.9, 5.55, 0.8, C.accent3);
  text(s, [{ text: "Fine-tuning decisions  ", options: { bold: true, color: C.accent3 } },
           { text: "FashionCLIP stays frozen (shared embedding space); DSO2 heads and the DSO6 ranker are trained; CLIP fine-tuned on the 2 last blocks (DSO6). LLMs are not fine-tuned: prompt engineering, RAG and validation reach the goal without labelled data; LoRA / QLoRA kept as next step." }],
       { x: 2.0, y: 5.4, w: 10.4, h: 1.25, fontSize: 14, valign: "middle" });
  s.addNotes("Every LLM is used for what it is good at: extraction, explanation and tool selection. Numbers (scores, gains, outfit counts) always come from code or learned models. No LLM fine-tuning: no labelled data, free APIs, and prompting plus validation were sufficient.");

  // ============================================================= 16. evaluation
  s = content("Evaluation summary", "Data & Modeling");
  const E = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent3 } } });
  s.addTable([
    [E("Objective"), E("Metric"), E("Result"), E("Reference")],
    ["DSO1 Recognition", "Accuracy (catalogue, n = 120)", "0.917 [0.853 ; 0.954]", "LLM alone 0.833"],
    ["DSO1 Recognition", "Colour on real Tunisian photos (n = 28)", "89 %", "29 % without LLM"],
    ["DSO2 Compatibility", "AUC, true vs random pairs (n = 8,000)", "0.74 [0.73 ; 0.75]", "0.50 = chance"],
    ["DSO3 Jury", "Repairs judged acceptable (n = 164)", "59 %", "→ removed from UI"],
    ["DSO4 Gaps", "Agent cases passed (n = 7)", "6 / 7 · injection 1 / 1", "—"],
    ["DSO5 Profile", "Silhouette of the style taxonomy", "0.44 (k = 16)", "0.28 at k = 6"],
    ["DSO6 Vision", "articleType accuracy / macro-F1", "0.849 / 0.811", "majority 0.083"],
    ["DSO6 Context", "Ranker AUC · top-1 violations", "0.87 · 27 %", "61 % random"],
    ["DSO6 LLM judge", "Bad explanations detected · false alarms", "100 % · 5 %", "Spearman 0.91"],
  ], { x: 0.6, y: 1.5, w: 12.1, colW: [2.6, 4.5, 2.8, 2.2], fontSize: 13, color: C.text1, rowH: 0.47,
       border: { type: "solid", pt: 0.75, color: "E2D6E4" }, fill: { color: C.background1 }, valign: "middle" });
  text(s, "Every result is reported with its sample size and a baseline; small samples are flagged as such.", { x: 0.6, y: 6.45, w: 12.1, h: 0.4, fontSize: 12, italic: true, color: C.text2 });
  s.addNotes("Honest reporting: confidence intervals where available, a baseline for each metric, and the limits of small samples. The context ranker uses synthetic labels, so its AUC is partly circular.");

  // ============================================================= 17. implementation
  s = content("Technical implementation and integration", "Data & Modeling");
  stat(s, 0.6, 1.45, 5.6, "156 tests · all green", "automated tests across the gateway and the six objectives (real runs below)", C.accent4);
  await shot(s, "07_tech_tests", "Real test runs", 0.6, 2.75, 5.6, 3.3);
  text(s, "Tests use fake LLMs: no key or quota consumed, nothing written to real data.", { x: 0.6, y: 6.2, w: 5.6, h: 0.5, fontSize: 12, italic: true, color: C.text2 });
  const impl = [
    ["FaServer", "Stack", "React + Vite · FastAPI gateway · PyTorch / scikit-learn · Docker-ready DSO6 service"],
    ["FaUserLock", "Accounts & privacy", "PBKDF2-SHA256 (200k), HttpOnly session cookie, one private wardrobe per account"],
    ["FaShieldAlt", "LLM safety", "structured inputs only, JSON outputs validated, read-only tools, keys in .env never in git"],
    ["FaSyncAlt", "Resilience", "every AI feature degrades gracefully: rules / kNN fallback, clear messages, caches"],
  ];
  for (let i = 0; i < impl.length; i++) {
    const y = 1.5 + i * 1.3;
    card(s, 6.6, y, 6.1, 1.15);
    await icon(s, impl[i][0], 6.8, y + 0.2, 0.75, i % 2 ? C.accent4 : C.accent1);
    text(s, impl[i][1], { x: 7.75, y: y + 0.12, w: 4.8, h: 0.35, fontSize: 15, bold: true, color: C.text2 });
    text(s, impl[i][2], { x: 7.75, y: y + 0.47, w: 4.8, h: 0.65, fontSize: 13 });
  }
  s.addNotes("Integration: one gateway, shared contracts, per-user wardrobes. 156 automated tests across the modules, all passing. Security: hashed passwords, HttpOnly cookies, keys never committed, LLM outputs always validated by code.");

  // ============================================================= 18. preview
  s = content("Realistic outfit preview", "Data & Modeling");
  const prev = [
    ["d1fa01c3325f2390ad49.png", "Virtual try-on", "Leffa (bottoms) + IDM-VTON (tops) wear the user's real photos"],
    ["inspire_c6c71052c3b8229a1009.jpg", "Inspired outfit", "Gemini describes each photo → FLUX.1 schnell generates the look"],
    ["inspire_f5f1d42caa58296468e9.jpg", "Inspired outfit (men)", "Same pipeline, 5 to 15 s, free daily allowance"],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    await picture(s, path.join(PROOF, prev[i][0]), x, 1.5, 3.9, 4.15, prev[i][1]);
    text(s, prev[i][1], { x, y: 5.8, w: 3.9, h: 0.4, fontSize: 16, bold: true, color: C.accent1, align: "center" });
    text(s, prev[i][2], { x, y: 6.2, w: 3.9, h: 0.6, fontSize: 12, color: C.text2, align: "center" });
  }
  s.addNotes("All three images were produced by the app from the user's own garment photos. Try-on is the most faithful (diffusion models on Hugging Face Spaces, a few outfits per day for free); the inspired view is unlimited but only inspired by the photos.");

  // ============================================================= 19. limits
  s = content("Limitations and next steps", "Data & Modeling");
  card(s, 0.6, 1.5, 5.95, 5.25);
  await icon(s, "FaExclamationTriangle", 0.9, 1.75, 0.7, C.accent5);
  text(s, "Limitations", { x: 1.8, y: 1.85, w: 4.5, h: 0.5, fontSize: 20, bold: true, color: C.text2 });
  bullets(s, ["Small real-world test sets (28 photos, 7 agent cases)", "Compatibility learned on Polyvore (western style), image only",
              "Gap candidates use same-slot proxies; thresholds not yet calibrated", "Traditional garments all mapped to « onepiece »",
              "Free GPU quota limits virtual try-on to a few outfits per day"], { x: 0.95, y: 2.65, w: 5.3, h: 3.9, fontSize: 17, paraSpaceAfter: 16 });
  card(s, 6.75, 1.5, 5.95, 5.25);
  await icon(s, "FaRoute", 7.05, 1.75, 0.7, C.accent4);
  text(s, "Next steps", { x: 7.95, y: 1.85, w: 4.5, h: 0.5, fontSize: 20, bold: true, color: C.text2 });
  bullets(s, ["Collect and label a larger Tunisian test set with users", "Fine-tune compatibility on local outfits; calibrate thresholds",
              "Sub-types for traditional garments (jebba, farmla, kaftan)", "LoRA on a small open LLM for the agenda agent",
              "Mobile app with camera capture and offline cache"], { x: 7.1, y: 2.65, w: 5.3, h: 3.9, fontSize: 17, paraSpaceAfter: 16 });
  s.addNotes("We state the limits we measured and the concrete steps that would address them.");

  // ============================================================= 20. video
  pres.addSection({ title: "Demonstration" });
  s = pres.addSlide({ masterName: "DARK_TITLE", sectionTitle: "Demonstration" });
  text(s, "Video demonstration", { x: 0.9, y: 0.7, w: 11.5, h: 0.9, fontSize: 40, bold: true, color: C.background1, fontFace: THEME.headFontFace });
  text(s, "3 minutes · voice-over · solution workflow and main functionalities", { x: 0.9, y: 1.6, w: 11.5, h: 0.5, fontSize: 18, color: C.accent2 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.9, y: 2.4, w: 7.6, h: 4.3, rectRadius: 0.12, fill: { color: "2A1530" }, line: { color: HEX.accent2, width: 1.25, dashType: "dash" }, objectName: "video-slot" });
  await icon(s, "FaPlay", 4.15, 3.85, 1.1, C.accent1);
  text(s, "Insert the demo video here (Insert → Video)", { x: 0.9, y: 5.2, w: 7.6, h: 0.5, fontSize: 14, color: C.accent2, align: "center" });
  const flow = ["Sign in → my wardrobe", "Add an item from a photo", "Does it match? + AI advice", "Outfit studio & try-on", "Outfit of the day", "Pieces to add · My style"];
  for (let i = 0; i < flow.length; i++) {
    const y = 2.45 + i * 0.72;
    s.addShape(pres.shapes.OVAL, { x: 8.95, y, w: 0.5, h: 0.5, fill: { color: HEX.accent1 }, line: { color: HEX.accent1, width: 0 }, objectName: "step-dot" });
    text(s, String(i + 1), { x: 8.95, y, w: 0.5, h: 0.5, fontSize: 14, bold: true, color: C.background1, align: "center", valign: "middle" });
    text(s, flow[i], { x: 9.6, y: y + 0.05, w: 3.4, h: 0.45, fontSize: 15, color: C.background1, valign: "middle" });
  }
  s.addNotes("Play the 3-minute video. Voice-over follows the six steps listed on the right.");

  // ============================================================= 21. thanks
  s = pres.addSlide({ masterName: "DARK_TITLE", sectionTitle: "Demonstration" });
  text(s, "Thank you", { x: 0.9, y: 2.4, w: 7, h: 1.2, fontSize: 54, bold: true, color: C.background1, fontFace: THEME.headFontFace });
  text(s, "Questions?", { x: 0.9, y: 3.6, w: 7, h: 0.7, fontSize: 26, color: C.accent2 });
  await picture(s, path.join(PROOF, "inspire_f5f1d42caa58296468e9.jpg"), 8.4, 0.9, 4.2, 5.7, "Outfit generated by DressMe");
  s.addNotes("Thank the jury and open the floor to questions.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT);
  console.log("missing screenshots:\n" + missing.join("\n"));
}
main().catch(e => { console.error(e); process.exit(1); });

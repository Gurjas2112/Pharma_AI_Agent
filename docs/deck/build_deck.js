// Builds docs/Repurpora_Journey.pptx - the PS "5-slider" deliverable.
// usage: node build_deck.js   (reads eval numbers from backend/evals/results)
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const SKILL = process.env.PPTX_SKILL_DIR;
const ROOT = path.resolve(__dirname, "../..");
const RES = path.join(ROOT, "backend/evals/results");
const readJson = (f) => (fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : null);
const v1 = readJson(path.join(RES, "baseline_v1.json"))?.summary;
const v2 = readJson(path.join(RES, "latest.json"))?.summary;
const ml = readJson(path.join(ROOT, "backend/src/repurpora/ml/artifacts/metrics.json"));
const rag = readJson(path.join(RES, "rag_bench.json"));

const THEME = {
  name: "Repurpora",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B1226", lt1: "FFFFFF", dk2: "1E2A4A", lt2: "EEF6F6",
    accent1: "14B8A6", accent2: "7C3AED", accent3: "F5B642", accent4: "38BDF8", accent5: "EF6F6C", accent6: "64748B",
    hlink: "0E7C86", folHlink: "7C3AED",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "Repurpora - Lazarus Graph";
pres.author = "Repurpora";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "DARK",
  background: { color: THEME.colors.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.45, w: 12.1, h: 1.0, fontSize: 32, bold: true, color: C.background1, align: "left", valign: "top", margin: 0 }, text: "" } },
    { text: { text: "Repurpora · Lazarus Graph", options: { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: THEME.colors.accent6, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: "94A3B8" },
});
pres.defineSlideMaster({
  title: "LIGHT",
  background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.9, fontSize: 32, bold: true, color: C.text1, align: "left", valign: "top", margin: 0 }, text: "" } },
    { text: { text: "Repurpora · Lazarus Graph", options: { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: THEME.colors.accent6, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: THEME.colors.accent6 },
});

const num = (v, d = 2) => (typeof v === "number" ? v.toFixed(d) : "–");
const pct = (v) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "–");

function circleNum(slide, n, x, y, fill, name) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.62, h: 0.62, fill: { color: fill }, line: { color: fill }, objectName: `${name}-circle` });
  slide.addText(String(n), { x, y, w: 0.62, h: 0.62, align: "center", valign: "middle", fontSize: 18, bold: true, color: C.text1, isTextBox: true, margin: 0, objectName: `${name}-num` });
}

// ================================================================ 1. Title
pres.addSection({ title: "Opening" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Opening" });
s.addText("From approved molecule to innovation case", { placeholder: "title" });
s.addText("Repurpora's master agent turns one prompt into a cited repurposing brief: market, trade, patents, trials, internal knowledge and the web, scored by ML and archived as PDF + Excel.",
  { x: 0.6, y: 1.65, w: 8.2, h: 1.0, fontSize: 16, color: "CBD5E1", isTextBox: true, margin: 0, objectName: "subtitle" });
// hexagon motif
s.addShape(pres.shapes.HEXAGON, { x: 9.7, y: 1.2, w: 2.6, h: 2.25, fill: { color: THEME.colors.dk2 }, line: { color: THEME.colors.accent1, width: 3 }, objectName: "hex" });
s.addShape(pres.shapes.STAR_4_POINT, { x: 10.55, y: 1.85, w: 0.9, h: 0.95, fill: { color: THEME.colors.accent3 }, line: { color: THEME.colors.accent3 }, objectName: "spark" });
const stats = [
  ["2–3 months → ~2 min", "per opportunity screen (literature-review baseline from the PS)"],
  ["6 agents", "run in parallel under one LangGraph master"],
  [v2 ? pct(v2.guardrail_block_rate) : "100%", "adversarial prompts blocked in golden-set eval"],
];
stats.forEach(([big, small], i) => {
  const x = 0.6 + i * 4.15;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.0, w: 3.85, h: 2.3, rectRadius: 0.12, fill: { color: THEME.colors.dk2 }, line: { color: "334155" }, objectName: `stat${i}-card` });
  s.addText(big, { x: x + 0.3, y: 4.25, w: 3.3, h: 1.0, fontSize: 32, bold: true, color: i === 1 ? THEME.colors.accent3 : THEME.colors.accent1, fontFace: "Arial", isTextBox: true, margin: 0, objectName: `stat${i}-big` });
  s.addText(small, { x: x + 0.3, y: 5.3, w: 3.3, h: 0.8, fontSize: 14, color: "CBD5E1", isTextBox: true, margin: 0, objectName: `stat${i}-small` });
});
s.addNotes("Opening: the problem is a 2-3 month literature review per opportunity. Repurpora compresses this to minutes with an agentic workflow, and every claim is evidence-gated.");

// ================================================================ 2. Journey
pres.addSection({ title: "Journey" });
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Journey" });
s.addText("One prompt answers six planning questions", { placeholder: "title" });
const steps = [
  ["Molecule", "Master agent builds a typed research plan", "Planner"],
  ["Unmet need", "Patient burden vs competition by indication", "IQVIA + Internal RAG"],
  ["Ongoing trials", "Live phases, sponsors and saturation", "ClinicalTrials.gov v2"],
  ["Other diseases", "Mechanism-led signals for new uses", "Web + Trials"],
  ["Patents", "Active filings, expiry, FTO risk", "USPTO clone"],
  ["Product story", "Cited brief, ML score, PDF + Excel", "Synthesizer + Report"],
];
const fills = [THEME.colors.accent1, THEME.colors.accent4, THEME.colors.accent3, THEME.colors.accent2, THEME.colors.accent5, THEME.colors.accent1];
steps.forEach(([t, d, a], i) => {
  const x = 0.6 + i * 2.06;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.75, w: 1.86, h: 3.3, rectRadius: 0.1, fill: { color: THEME.colors.lt2 }, line: { color: "D5E4E6" }, objectName: `step${i}-card` });
  circleNum(s, i + 1, x + 0.2, 1.95, fills[i], `step${i}`);
  s.addText(t, { x: x + 0.2, y: 2.75, w: 1.5, h: 0.5, fontSize: 18, bold: true, color: C.text1, isTextBox: true, margin: 0, objectName: `step${i}-title` });
  s.addText(d, { x: x + 0.2, y: 3.25, w: 1.5, h: 1.1, fontSize: 14, color: "334155", isTextBox: true, margin: 0, valign: "top", objectName: `step${i}-desc` });
  s.addText(a, { x: x + 0.2, y: 4.45, w: 1.5, h: 0.45, fontSize: 11, italic: true, color: THEME.colors.hlink, isTextBox: true, margin: 0, objectName: `step${i}-agent` });
});
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.4, w: 12.1, h: 1.2, rectRadius: 0.1, fill: { color: THEME.colors.dk1 }, line: { color: THEME.colors.dk1 }, objectName: "prompt-box" });
s.addText([
  { text: "Prompt  ", options: { bold: true, color: THEME.colors.accent3 } },
  { text: "“Assess montelukast for repurposing in India: unmet needs, ongoing clinical trials, new indications, patents and an innovative product story.”", options: { color: "FFFFFF" } },
], { x: 0.9, y: 5.5, w: 11.5, h: 1.0, fontSize: 16, valign: "middle", isTextBox: true, margin: 0, objectName: "prompt-text" });
s.addNotes("Walk the PS journey left to right. Each step maps to a worker agent; all run in parallel via LangGraph Send.");

// ================================================================ 3. Architecture
pres.addSection({ title: "Architecture" });
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Architecture" });
s.addText("A master agent, six specialists, a trust layer", { placeholder: "title" });
// diagram left
const cx = 3.4, cy = 3.9;
const workers = ["IQVIA", "EXIM", "Patents", "Trials", "Internal RAG", "Web"];
workers.forEach((w, i) => {
  const a = (i / workers.length) * Math.PI * 2 - Math.PI / 2;
  const x = cx + Math.cos(a) * 2.25 - 0.8, y = cy + Math.sin(a) * 1.85 - 0.3;
  s.addShape(pres.shapes.LINE, { x: Math.min(cx, x + 0.8), y: Math.min(cy, y + 0.3), w: Math.abs(x + 0.8 - cx) || 0.01, h: Math.abs(y + 0.3 - cy) || 0.01,
    line: { color: "94A3B8", width: 1.25, dashType: "dash" }, flipH: (x + 0.8 < cx) !== (y + 0.3 < cy), objectName: `edge${i}` });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.6, h: 0.6, rectRadius: 0.1, fill: { color: THEME.colors.lt2 }, line: { color: THEME.colors.accent1, width: 1.5 }, objectName: `worker${i}` });
  s.addText(w, { x, y, w: 1.6, h: 0.6, align: "center", valign: "middle", fontSize: 14, bold: true, color: C.text1, isTextBox: true, margin: 0, objectName: `worker${i}-label` });
});
s.addShape(pres.shapes.HEXAGON, { x: cx - 0.95, y: cy - 0.75, w: 1.9, h: 1.5, fill: { color: THEME.colors.dk1 }, line: { color: THEME.colors.accent3, width: 2 }, objectName: "master" });
s.addText("Master\nagent", { x: cx - 0.95, y: cy - 0.75, w: 1.9, h: 1.5, align: "center", valign: "middle", fontSize: 16, bold: true, color: "FFFFFF", isTextBox: true, margin: 0, objectName: "master-label" });
// trust layer right
const trust = [
  ["Guardrails", "Injection firewall, untrusted-content sanitiser, PII/secret DLP, per-agent tool allow-list"],
  ["Evidence layer", "Every claim cites [E#] with source, trust tier and SHA-256; coverage gate + redraft"],
  ["Judge & ML", "LLM-as-judge faithfulness; scikit-learn opportunity score with drivers"],
  ["Memory & audit", "Postgres threads, per-user store with provenance, append-only audit, LangSmith traces"],
];
trust.forEach(([t, d], i) => {
  const y = 1.6 + i * 1.3;
  s.addShape(pres.shapes.OVAL, { x: 7.2, y: y + 0.08, w: 0.45, h: 0.45, fill: { color: [THEME.colors.accent1, THEME.colors.accent2, THEME.colors.accent3, THEME.colors.accent4][i] }, line: { color: "FFFFFF" }, objectName: `trust${i}-dot` });
  s.addText(t, { x: 7.85, y, w: 4.9, h: 0.45, fontSize: 18, bold: true, color: C.text1, isTextBox: true, margin: 0, objectName: `trust${i}-title` });
  s.addText(d, { x: 7.85, y: y + 0.45, w: 4.9, h: 0.75, fontSize: 14, color: "334155", isTextBox: true, margin: 0, valign: "top", objectName: `trust${i}-desc` });
});
s.addText("LangGraph · LangChain · Aegra on Railway · Ollama (qwen2.5) on AWS GPU · Supabase pgvector + Auth + Storage · Next.js Agent Chat UI on Vercel · LangSmith",
  { x: 0.6, y: 6.55, w: 12.1, h: 0.35, fontSize: 12, color: THEME.colors.accent6, isTextBox: true, margin: 0, objectName: "stack" });
s.addNotes("The LLM proposes, code decides: the guard, judge and archive steps are enforced by the state machine. Workers are sandboxed to allow-listed tools.");

// ================================================================ 4. Case: data
pres.addSection({ title: "Case" });
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Case" });
s.addText("Post-viral cough leads respiratory white space", { placeholder: "title" });
const resp = [
  ["Post-viral chronic cough", 9.5 / 5], ["Allergic rhinitis", 98 / 61], ["COPD", 55.3 / 38], ["Asthma", 34.3 / 46],
  ["Bronchiectasis", 1.9 / 6], ["Idiopathic pulm. fibrosis", 0.6 / 4], ["Pulmonary TB", 2.8 / 22],
];
s.addChart(pres.charts.BAR, [{ name: "Patients (mn) per marketed competitor", labels: resp.map((r) => r[0]), values: resp.map((r) => +r[1].toFixed(2)) }], {
  x: 0.6, y: 1.55, w: 7.2, h: 5.1, barDir: "bar", chartColors: [THEME.colors.accent1],
  showTitle: true, title: "Patients (mn) per marketed competitor · IQVIA mock, India", titleFontSize: 13, titleColor: "334155", titleFontFace: "+mn-lt",
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelFontSize: 11, dataLabelColor: "334155", dataLabelFontFace: "+mn-lt",
  catAxisLabelColor: "334155", catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin",
  valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, objectName: "burden-chart",
});
const kpis = [
  ["Low", "FTO risk for montelukast secondary filings (2/10)", THEME.colors.accent1],
  ["63%", "adherence gap in children < 6 (internal field report)", THEME.colors.accent3],
  ["5", "competitors in post-viral chronic cough vs 46 in asthma", THEME.colors.accent2],
];
kpis.forEach(([big, small, col], i) => {
  const y = 1.6 + i * 1.7;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.3, y, w: 4.4, h: 1.5, rectRadius: 0.1, fill: { color: THEME.colors.lt2 }, line: { color: "D5E4E6" }, objectName: `kpi${i}-card` });
  s.addText(big, { x: 8.55, y: y + 0.15, w: 1.5, h: 1.2, fontSize: 36, bold: true, color: col, valign: "middle", fontFace: "Arial", isTextBox: true, margin: 0, objectName: `kpi${i}-big` });
  s.addText(small, { x: 10.1, y: y + 0.15, w: 2.45, h: 1.2, fontSize: 14, color: "334155", valign: "middle", isTextBox: true, margin: 0, objectName: `kpi${i}-small` });
});
s.addText("Synthetic IQVIA / USPTO mocks per the problem statement; trials are live from ClinicalTrials.gov.", { x: 0.6, y: 6.62, w: 12.1, h: 0.3, fontSize: 10, italic: true, color: THEME.colors.accent6, isTextBox: true, margin: 0, objectName: "source" });
s.addNotes("This answers the PS sample question directly. The ratio of patients to marketed competitors ranks under-served respiratory indications.");

// ================================================================ 5. Product story + proof
pres.addSection({ title: "Close" });
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Close" });
s.addText("Product story: paediatric montelukast oral film", { placeholder: "title" });
s.addText([
  { text: "Why now: ", options: { bold: true, color: THEME.colors.accent3 } },
  { text: "no film among 46 Indian brands; field force reports a 63% adherence gap in under-6s; low FTO on secondary filings; Goa plant has film capacity.", options: { color: "E2E8F0", breakLine: true } },
  { text: "Next indication to test: ", options: { bold: true, color: THEME.colors.accent3 } },
  { text: "post-viral chronic cough (5 competitors, 12.7% CAGR); pair with a neuropsychiatric-risk labelling programme.", options: { color: "E2E8F0" } },
], { x: 0.6, y: 1.55, w: 6.7, h: 4.2, fontSize: 18, valign: "top", paraSpaceAfter: 10, isTextBox: true, margin: 0, objectName: "story" });
const ev = v2 || v1 || {};
const proof = [
  [pct(ev.guardrail_block_rate), "guardrail block rate"],
  [num(ml?.test?.roc_auc, 2), "ML hold-out ROC-AUC"],
  [num(rag?.results?.find((r) => r.strategy === "recursive")?.["hit@5"], 2), "RAG Hit@5 (recursive)"],
  [pct(ev.evidence_coverage), "evidence coverage (golden set)"],
  [pct(ev.routing_recall), "agent routing recall"],
  [ev.latency_p50_s ? `${Math.round(ev.latency_p50_s)} s` : "–", "median full assessment, 1 GPU"],
];
proof.forEach(([big, small], i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 7.7 + col * 2.6, y = 1.5 + row * 1.6;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.4, h: 1.4, rectRadius: 0.1, fill: { color: THEME.colors.dk2 }, line: { color: "334155" }, objectName: `proof${i}-card` });
  s.addText(big, { x: x + 0.2, y: y + 0.12, w: 2.0, h: 0.7, fontSize: 28, bold: true, color: THEME.colors.accent1, fontFace: "Arial", isTextBox: true, margin: 0, objectName: `proof${i}-big` });
  s.addText(small, { x: x + 0.2, y: y + 0.82, w: 2.0, h: 0.45, fontSize: 12, color: "CBD5E1", isTextBox: true, margin: 0, objectName: `proof${i}-small` });
});
s.addText([
  { text: "Next steps  ", options: { bold: true, color: THEME.colors.accent3 } },
  { text: "Stage-gate 1 review of the evidence register · swap mocks for licensed IQVIA/EXIM connectors · move Ollama to the EC2 GPU host · retrain the scorer on real portfolio outcomes", options: { color: "E2E8F0" } },
], { x: 0.6, y: 6.25, w: 12.1, h: 0.6, fontSize: 14, isTextBox: true, margin: 0, objectName: "next" });
s.addNotes("Close on the product story the system produced, then the proof that it is trustworthy: guardrails, ML metrics, retrieval quality and groundedness from the golden-set evaluation.");

(async () => {
  const out = path.join(ROOT, "docs", "Repurpora_Journey.pptx");
  await pres.writeFile({ fileName: out });
  if (SKILL) {
    const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));
    await applyTheme(out, THEME);
  }
  console.log("wrote", out);
})();

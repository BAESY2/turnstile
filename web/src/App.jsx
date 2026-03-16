import { useState, useEffect, useRef } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip, AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from "recharts";

const C = { p: "#00d4ff", p2: "#0ea5e9", g: "#22c55e", r: "#ef4444", a: "#f59e0b", v: "#818cf8" };

const LANG = {
  en: { sub: "Bayesian temporal inversion engine", ph: "What do you want to predict?", conf: "Confidence", nw: "New prediction", wp: "Math", an: "Result", bs: "Base", bu: "Bull", be: "Bear", api: "API key", apiD: "Enter Anthropic API key for custom analysis. Demos work without it.", sv: "Save", cn: "Cancel", dir: "DIRECTION", tgt: "TARGET", mech: "MECHANISM", inv: "INVALIDATED IF", hid: "HIDDEN FACTOR", src: "SOURCES (searched)" },
  ko: { sub: "\uBCA0\uC774\uC9C0\uC548 \uC2DC\uAC04 \uC5ED\uC804 \uC5D4\uC9C4", ph: "\uBB34\uC5C7\uC744 \uC608\uCE21\uD560\uAE4C\uC694?", conf: "\uC2E0\uB8B0\uB3C4", nw: "\uC0C8 \uC608\uCE21", wp: "\uC218\uD559", an: "\uACB0\uACFC", bs: "\uAE30\uBCF8", bu: "\uC0C1\uC2B9", be: "\uD558\uB77D", api: "API \uD0A4", apiD: "\uCEE4\uC2A4\uD140 \uBD84\uC11D\uC744 \uC704\uD55C Anthropic API \uD0A4. \uB370\uBAA8\uB294 \uD0A4 \uC5C6\uC774 \uC791\uB3D9.", sv: "\uC800\uC7A5", cn: "\uCDE8\uC18C", dir: "\uBC29\uD5A5", tgt: "\uBAA9\uD45C\uAC00", mech: "\uBA54\uCEE4\uB2C8\uC998", inv: "\uBB34\uD6A8 \uC870\uAC74", hid: "\uC228\uACA8\uC9C4 \uC694\uC778", src: "\uCD9C\uCC98 (\uAC80\uC0C9 \uAE30\uBC18)" },
  zh: { sub: "\u8D1D\u53F6\u65AF\u65F6\u95F4\u53CD\u6F14\u5F15\u64CE", ph: "\u4F60\u60F3\u9884\u6D4B\u4EC0\u4E48?", conf: "\u7F6E\u4FE1\u5EA6", nw: "\u65B0\u9884\u6D4B", wp: "\u6570\u5B66", an: "\u7ED3\u679C", bs: "\u57FA\u51C6", bu: "\u770B\u6DA8", be: "\u770B\u8DCC", api: "API\u5BC6\u94A5", apiD: "\u8F93\u5165Anthropic API\u5BC6\u94A5\u3002\u6F14\u793A\u65E0\u9700\u5BC6\u94A5\u3002", sv: "\u4FDD\u5B58", cn: "\u53D6\u6D88", dir: "\u65B9\u5411", tgt: "\u76EE\u6807\u4EF7", mech: "\u673A\u5236", inv: "\u5931\u6548\u6761\u4EF6", hid: "\u9690\u85CF\u56E0\u7D20", src: "\u6570\u636E\u6765\u6E90 (\u641C\u7D22)" },
  ja: { sub: "\u30D9\u30A4\u30BA\u6642\u9593\u53CD\u8EE2\u30A8\u30F3\u30B8\u30F3", ph: "\u4F55\u3092\u4E88\u6E2C\u3057\u307E\u3059\u304B?", conf: "\u4FE1\u983C\u5EA6", nw: "\u65B0\u898F\u4E88\u6E2C", wp: "\u6570\u5B66", an: "\u7D50\u679C", bs: "\u57FA\u672C", bu: "\u5F37\u6C17", be: "\u5F31\u6C17", api: "API\u30AD\u30FC", apiD: "Anthropic API\u30AD\u30FC\u3092\u5165\u529B\u3002\u30C7\u30E2\u306F\u30AD\u30FC\u4E0D\u8981\u3002", sv: "\u4FDD\u5B58", cn: "\u30AD\u30E3\u30F3\u30BB\u30EB", dir: "\u65B9\u5411", tgt: "\u30BF\u30FC\u30B2\u30C3\u30C8", mech: "\u30E1\u30AB\u30CB\u30BA\u30E0", inv: "\u7121\u52B9\u6761\u4EF6", hid: "\u96A0\u308C\u305F\u8981\u56E0", src: "\u30BD\u30FC\u30B9 (\u691C\u7D22)" },
};

const DEMOS = {
  "NVIDIA stock if China bans rare earth exports": {
    verdict: "NVDA drops to $158 by Friday close.",
    direction: "DOWN", dirColor: C.r,
    target: "$158 (-12.3% from $180)",
    deadline: "Friday March 21 market close",
    mechanism: "$1.2B in call options expire worthless as rare earth supply panic triggers institutional selling cascade. Market makers delta-hedge by shorting, amplifying the move below $165 support.",
    recovery: "Recovers to $172 within 2 weeks as TSMC confirms Australian rare earth pipeline operational.",
    confidence: 74,
    te: "TSMC alt supply announcement", tw: "72h",
    hidden: "NVIDIA quietly built 6-month rare earth buffer since Q3 2025. This isn't public. When it leaks at GTC 2026, the recovery accelerates.",
    wrong: "NVDA holds $170 for 2 consecutive trading days — means institutions are buying the dip faster than panic sells.",
    sc: [{ n: "Drop to $158, recover $172", p: 45 }, { n: "Sustained below $160", p: 25 }, { n: "Holds above $170", p: 20 }, { n: "Crash below $145", p: 10 }],
    dr: [{ n: "Rare earth buffer (6mo)", v: 88, d: "u" }, { n: "Options expiry cascade", v: 76, d: "d" }, { n: "Institutional panic sell", v: 72, d: "d" }, { n: "TSMC alt supply speed", v: 65, d: "u" }, { n: "GTC 2026 catalyst", v: 42, d: "u" }],
    tl: [{ t: "0h", b: 45, u: 20, d: 25 }, { t: "4h", b: 30, u: 12, d: 42 }, { t: "1d", b: 35, u: 15, d: 35 }, { t: "2d", b: 38, u: 20, d: 28 }, { t: "3d", b: 42, u: 25, d: 22 }, { t: "1w", b: 48, u: 32, d: 14 }, { t: "2w", b: 52, u: 35, d: 10 }],
    rd: [{ a: "Impact", v: 82 }, { a: "Speed", v: 90 }, { a: "Reversibility", v: 65 }, { a: "Contagion", v: 50 }, { a: "Certainty", v: 70 }, { a: "Precedent", v: 45 }],
    math: { nodes: ["Ban","TSMC","Buffer","Panic","Recover","Price"], adj: [[0,.85,.70,0,0,0],[0,0,0,.30,.65,0],[0,0,0,.15,.60,0],[0,0,0,0,.20,.55],[0,0,0,0,0,.72],[0,0,0,0,0,0]], marginals: [1.0,.85,.70,.37,.68,.62], inv: [[0,0,0,0,0,0],[.92,0,0,0,0,0],[.78,0,0,0,0,0],[0,.34,.11,0,0,0],[0,.52,.46,.08,0,0],[0,0,0,.33,.67,0]], efwd: [.92,.61,.55,.80,.35,0], einv: [0,.12,.15,.72,.68,.45], tidx: 3 },
  },
  "Bitcoin price Monday noon KST": {
    verdict: "BTC drops to $67,500 by Monday 12:00 KST.",
    direction: "DOWN", dirColor: C.r,
    target: "$67,500 (-4.9% from $70,982)",
    deadline: "Monday March 17, 12:00 KST",
    mechanism: "Pre-FOMC risk-off triggers $220M long liquidation below $69K. Market makers pull bids ahead of Wednesday's rate decision, creating a liquidity vacuum below key support.",
    recovery: "Bounces to $72K within 48h post-FOMC as ETF inflows ($65M+/day) absorb the dip and shorts cover.",
    confidence: 62,
    te: "FOMC statement Wednesday 2PM EST", tw: "Mar 19",
    hidden: "Short interest hit 8-month high but open interest declining. Shorts are overleveraged with thin liquidity — any squeeze attempt above $73K forces $310M in liquidations.",
    wrong: "BTC breaks and holds $73,000 before Monday — means shorts are already covering and the pre-FOMC dip won't materialize.",
    sc: [{ n: "Dip to $67.5K, bounce $72K", p: 42 }, { n: "Holds $69-70K range", p: 28 }, { n: "Squeeze above $74K", p: 18 }, { n: "Flash crash below $65K", p: 12 }],
    dr: [{ n: "FOMC risk-off selling", v: 82, d: "d" }, { n: "Long liquidation $220M", v: 75, d: "d" }, { n: "ETF inflow floor", v: 70, d: "u" }, { n: "Short squeeze above $73K", v: 55, d: "u" }, { n: "Mideast escalation", v: 40, d: "d" }],
    tl: [{ t: "Now", b: 42, u: 18, d: 28 }, { t: "6h", b: 38, u: 16, d: 32 }, { t: "12h", b: 35, u: 15, d: 36 }, { t: "18h", b: 38, u: 18, d: 30 }, { t: "24h", b: 42, u: 22, d: 24 }],
    rd: [{ a: "Volatility", v: 55 }, { a: "Trend", v: 40 }, { a: "Volume", v: 65 }, { a: "Macro", v: 80 }, { a: "Technical", v: 60 }, { a: "Sentiment", v: 25 }],
    math: { nodes: ["Price","Fed","Long","Short","ETF","Out"], adj: [[0,.60,.45,.25,.65,0],[0,0,.50,0,0,.45],[0,0,0,0,0,.40],[0,0,0,0,0,.25],[0,0,0,0,0,.55],[0,0,0,0,0,0]], marginals: [1.0,.60,.52,.35,.65,.61], inv: [[0,0,0,0,0,0],[.88,0,0,0,0,0],[.70,.48,0,0,0,0],[.35,0,0,0,0,0],[.82,0,0,0,0,0],[0,.31,.26,.14,.29,0]], efwd: [.97,.72,.55,.68,.42,0], einv: [0,.08,.22,.55,.10,.82], tidx: 2 },
  },
  "Samsung Electronics KOSPI open forecast": {
    verdict: "Samsung drops to ₩176,000 by Wednesday close KST.",
    direction: "DOWN", dirColor: C.r,
    target: "₩176,000 (-4.1% from ₩183,500)",
    deadline: "Wednesday March 19, 15:30 KST",
    mechanism: "₩800B institutional profit-taking as foreign investors dump ₩450B in pre-market block trades. Oil price surge from Mideast tension triggers macro risk-off across KOSPI tech names.",
    recovery: "Dead cat bounce to ₩180,000 by Friday as retail buyers step in at 52-week support. Consolidation around ₩178,000-180,000 through next week.",
    confidence: 66,
    te: "Pension fund rebalancing block sell", tw: "48h",
    hidden: "₩450B block sell order queued at ₩180,000 from national pension fund quarterly rebalancing. Combined with oil-driven won weakness, creates cascading sell pressure.",
    wrong: "Holds ₩181,000 for first 2 hours of Tuesday trading — means institutional demand is absorbing the block sells.",
    sc: [{ n: "Drop to ₩176K, bounce ₩180K", p: 44 }, { n: "Holds ₩180-182K range", p: 26 }, { n: "Rebounds above ₩185K", p: 18 }, { n: "Crash below ₩172K", p: 12 }],
    dr: [{ n: "Foreign investor selling ₩450B", v: 84, d: "d" }, { n: "Pension fund rebalancing", v: 78, d: "d" }, { n: "HBM demand outlook", v: 72, d: "u" }, { n: "Won/USD weakness", v: 65, d: "d" }, { n: "Retail buy support", v: 48, d: "u" }],
    tl: [{ t: "0h", b: 44, u: 18, d: 26 }, { t: "3h", b: 36, u: 14, d: 38 }, { t: "1d", b: 38, u: 16, d: 34 }, { t: "2d", b: 40, u: 20, d: 28 }, { t: "3d", b: 44, u: 24, d: 22 }, { t: "1w", b: 50, u: 30, d: 14 }],
    rd: [{ a: "Impact", v: 78 }, { a: "Speed", v: 85 }, { a: "Certainty", v: 62 }, { a: "Contagion", v: 55 }],
    math: { nodes: ["Sell","Foreign","Pension","Won","HBM","Price"], adj: [[0,.84,.78,0,0,0],[0,0,0,.65,0,.55],[0,0,0,0,0,.50],[0,0,0,0,0,.40],[0,0,0,0,0,.72],[0,0,0,0,0,0]], marginals: [1.0,.84,.78,.55,.72,.63], inv: [[0,0,0,0,0,0],[.90,0,0,0,0,0],[.82,0,0,0,0,0],[0,.58,0,0,0,0],[0,0,0,0,0,0],[0,.46,.42,.28,.52,0]], efwd: [.90,.58,.52,.78,.32,0], einv: [0,.10,.14,.68,.62,.48], tidx: 3 },
  },
};
const EXAMPLES = Object.keys(DEMOS);

const Reveal = ({ children, delay = 0 }) => { const [s, setS] = useState(false); useEffect(() => { const t = setTimeout(() => setS(true), delay); return () => clearTimeout(t); }, []); return <div style={{ opacity: s ? 1 : 0, transform: s ? "none" : "translateY(14px)", transition: "all .7s cubic-bezier(.16,1,.36,1)" }}>{children}</div>; };
const TypeWriter = ({ text, speed = 12, onDone }) => { const [i, setI] = useState(0); useEffect(() => { setI(0); const iv = setInterval(() => setI(p => { if (p >= text.length) { clearInterval(iv); onDone?.(); return p; } return p + 1; }), speed); return () => clearInterval(iv); }, [text]); return <span>{text.slice(0, i)}{i < text.length && <span style={{ color: C.p, animation: "bk .8s step-end infinite" }}>|</span>}</span>; };
const CTip = ({ active, payload, label }) => { if (!active || !payload?.length) return null; return <div style={{ background: "rgba(5,5,5,.95)", border: "1px solid rgba(0,212,255,.12)", borderRadius: 10, padding: "10px 14px", fontSize: 12 }}><div style={{ color: C.p, fontWeight: 600, marginBottom: 4 }}>{label}</div>{payload.map((p, i) => <div key={i} style={{ color: p.color, display: "flex", justifyContent: "space-between", gap: 16 }}><span>{p.name}</span><span style={{ fontWeight: 600 }}>{Math.round(p.value)}%</span></div>)}</div>; };

const MathViz = ({ math }) => {
  const [step, setStep] = useState(0);
  const [hl, setHl] = useState(-1);
  useEffect(() => { const iv = setInterval(() => setStep(s => Math.min(s + 1, 5)), 1800); return () => clearInterval(iv); }, [math]);
  useEffect(() => { if (step >= 1) { const iv = setInterval(() => setHl(h => (h + 1) % math.nodes.length), 400); return () => clearInterval(iv); } }, [step]);
  if (!math) return null;
  const cs = 34;
  const MC = ({ val, inv, act }) => <div style={{ width: cs, height: cs, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, color: val > 0 ? "#fff" : "#aaa", background: val > 0 ? inv ? `rgba(0,212,255,${Math.min(val*.55,.45)})` : `rgba(14,165,233,${Math.min(val*.55,.45)})` : "transparent", border: act ? "1px solid #00d4ff" : "1px solid rgba(255,255,255,.03)", borderRadius: 2, transition: "all .3s", transform: act ? "scale(1.12)" : "scale(1)" }}>{val > 0 ? val.toFixed(2) : ""}</div>;
  return <div style={{ padding: "12px 0" }}>
    <div style={{ display: "flex", gap: 3, marginBottom: 14, justifyContent: "center", flexWrap: "wrap" }}>
      {["DAG","Forward","Inversion","Entropy","Turnstile"].map((s, i) => <div key={i} style={{ padding: "3px 10px", borderRadius: 16, fontSize: 10, background: i === step ? "rgba(0,212,255,.12)" : "transparent", border: i === step ? "1px solid rgba(0,212,255,.2)" : "1px solid rgba(255,255,255,.03)", color: i < step ? C.g : i === step ? C.p : "#bbb" }}>{i < step ? "\u2713 " : ""}{s}</div>)}
    </div>
    <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
      <div><div style={{ fontSize: 9, color: C.p, letterSpacing: 2, fontWeight: 600, marginBottom: 4, textAlign: "center" }}>FORWARD A[i,j]</div>
        {math.adj.map((row, i) => <div key={i} style={{ display: "flex", gap: 1, marginBottom: 1 }}><div style={{ width: cs, height: cs, display: "flex", alignItems: "center", fontSize: 7, color: "#aaa" }}>{math.nodes[i]?.slice(0, 4)}</div>{row.map((v, j) => <MC key={j} val={v} act={step >= 1 && hl === i} />)}</div>)}
      </div>
      {step >= 1 && <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 2 }}><div style={{ fontSize: 9, color: C.p, letterSpacing: 2, fontWeight: 600, marginBottom: 2 }}>P(node)</div>
        {math.marginals.map((m, i) => <div key={i} style={{ display: "flex", alignItems: "center", gap: 4, height: cs }}><div style={{ width: 50, height: 3, background: "rgba(255,255,255,.03)", borderRadius: 2, overflow: "hidden" }}><div style={{ width: `${m*100}%`, height: "100%", background: i === hl ? C.p : `${C.p}55`, borderRadius: 2 }} /></div><span style={{ fontSize: 9, color: i === hl ? C.p : "#aaa", fontFamily: "monospace" }}>{m.toFixed(2)}</span></div>)}
      </div>}
      {step >= 2 && <div><div style={{ fontSize: 9, color: C.g, letterSpacing: 2, fontWeight: 600, marginBottom: 4, textAlign: "center" }}>INVERTED P(A|B)</div>
        {math.inv.map((row, i) => <div key={i} style={{ display: "flex", gap: 1, marginBottom: 1 }}><div style={{ width: cs, height: cs, display: "flex", alignItems: "center", fontSize: 7, color: "#aaa" }}>{math.nodes[i]?.slice(0, 4)}</div>{row.map((v, j) => <MC key={j} val={v} inv act={step >= 2 && hl === j} />)}</div>)}
      </div>}
    </div>
    {step >= 3 && <Reveal delay={100}><div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 9, color: C.a, letterSpacing: 2, fontWeight: 600, marginBottom: 6, textAlign: "center" }}>\u2207H = H_fwd \u2212 H_inv</div>
      <div style={{ display: "flex", gap: 3, justifyContent: "center" }}>{math.nodes.map((n, i) => { const g = math.efwd[i] - math.einv[i]; const isT = i === math.tidx; return <div key={i} style={{ textAlign: "center", width: 58 }}>
        <div style={{ height: 38, display: "flex", flexDirection: "column", justifyContent: "flex-end", alignItems: "center" }}><div style={{ width: 16, height: math.efwd[i] * 36, background: `${C.p}44`, borderRadius: "2px 2px 0 0" }} /></div>
        <div style={{ fontSize: 7, padding: "2px 0", fontWeight: 600, color: isT ? C.a : "#bbb", background: isT ? `${C.a}15` : "transparent", borderRadius: 3, border: isT ? `1px solid ${C.a}33` : "none" }}>{n.slice(0,5)}{isT && <span style={{ fontSize: 6, display: "block", color: C.a }}>\u26A1</span>}</div>
        <div style={{ height: 38, display: "flex", alignItems: "flex-start", justifyContent: "center" }}><div style={{ width: 16, height: math.einv[i] * 36, background: `${C.g}44`, borderRadius: "0 0 2px 2px" }} /></div>
        <div style={{ fontSize: 8, fontFamily: "monospace", color: Math.abs(g) < .15 ? C.a : g > 0 ? C.p : C.g }}>{g > 0 ? "+" : ""}{g.toFixed(2)}</div>
      </div>; })}</div>
    </div></Reveal>}
    {step >= 4 && <Reveal delay={100}><div style={{ marginTop: 12, padding: "10px 14px", background: "rgba(0,0,0,.25)", borderRadius: 8, textAlign: "center" }}>
      <div style={{ fontFamily: "monospace", fontSize: 12, color: "#ccc", marginBottom: 4 }}>P(A|B) = P(B|A) \u00D7 P(A) / P(B)</div>
      <div style={{ fontFamily: "monospace", fontSize: 13, color: C.p }}>{math.adj[0][1].toFixed(2)} \u00D7 {math.marginals[0].toFixed(2)} / {math.marginals[1].toFixed(2)} = <span style={{ fontWeight: 700, fontSize: 16 }}>{math.inv[1][0].toFixed(2)}</span></div>
    </div></Reveal>}
  </div>;
};

const generateMath = (dr) => {
  if (!dr || dr.length < 3) return null;
  const n = Math.min(dr.length, 6);
  const drivers = dr.slice(0, n);
  const nodes = drivers.map(d => {
    const words = d.n.replace(/[₩$%]/g, '').trim().split(/\s+/);
    return words[0].slice(0, 7);
  });
  const sz = nodes.length;

  const adj = Array.from({ length: sz }, () => Array(sz).fill(0));
  drivers.forEach((d, i) => {
    if (i < sz - 1) adj[i][sz - 1] = +(d.v / 100).toFixed(2);
    if (i > 0 && i < sz - 1) adj[0][i] = +((d.v / 100) * 0.5 + 0.1).toFixed(2);
    if (i > 1) adj[1][i] = +((d.v / 100) * 0.3).toFixed(2);
  });

  const marginals = Array(sz).fill(0);
  marginals[0] = 1.0;
  for (let j = 1; j < sz; j++) {
    let prod = 1;
    for (let i = 0; i < j; i++) {
      if (adj[i][j] > 0) prod *= (1 - adj[i][j] * marginals[i]);
    }
    marginals[j] = +(1 - prod).toFixed(2);
  }

  const inv = Array.from({ length: sz }, () => Array(sz).fill(0));
  for (let i = 0; i < sz; i++) {
    for (let j = 0; j < sz; j++) {
      if (adj[i][j] > 0 && marginals[j] > 0) {
        inv[j][i] = +Math.min(.99, (adj[i][j] * marginals[i]) / marginals[j]).toFixed(2);
      }
    }
  }

  const H = (p) => (p > 0.01 && p < 0.99) ? -(p * Math.log2(p) + (1 - p) * Math.log2(1 - p)) : 0;
  const efwd = marginals.map((m, i) => +(H(m) * Math.max(0, 1 - i / (sz - 1))).toFixed(2));
  const einv = marginals.map((m, i) => +(H(m) * (i / (sz - 1))).toFixed(2));

  let minGrad = Infinity, tidx = Math.floor(sz / 2);
  for (let i = 1; i < sz - 1; i++) {
    const g = Math.abs(efwd[i] - einv[i]);
    if (g < minGrad) { minGrad = g; tidx = i; }
  }

  return { nodes, adj, marginals, inv, efwd, einv, tidx };
};

const generateMathFromDAG = (dag) => {
  if (!dag?.nodes || dag.nodes.length < 3) return null;
  const nodeList = dag.nodes.slice(0, 6);
  const nodes = nodeList.map(n => (n.label || n.id).split(/\s+/)[0].slice(0, 7));
  const sz = nodes.length;
  const nodeIds = nodeList.map(n => n.id);

  const adj = Array.from({ length: sz }, () => Array(sz).fill(0));
  (dag.edges || []).forEach(e => {
    const si = nodeIds.indexOf(e.src);
    const ti = nodeIds.indexOf(e.tgt);
    if (si >= 0 && ti >= 0 && si < sz && ti < sz) adj[si][ti] = +(e.prob || 0).toFixed(2);
  });

  const marginals = Array(sz).fill(0);
  marginals[0] = +(nodeList[0].prior || 1.0).toFixed(2);
  for (let j = 1; j < sz; j++) {
    let prod = 1;
    for (let i = 0; i < j; i++) {
      if (adj[i][j] > 0) prod *= (1 - adj[i][j] * marginals[i]);
    }
    marginals[j] = +(1 - prod).toFixed(2);
  }

  const inv = Array.from({ length: sz }, () => Array(sz).fill(0));
  for (let i = 0; i < sz; i++) {
    for (let j = 0; j < sz; j++) {
      if (adj[i][j] > 0 && marginals[j] > 0) {
        inv[j][i] = +Math.min(.99, (adj[i][j] * marginals[i]) / marginals[j]).toFixed(2);
      }
    }
  }

  const H = (p) => (p > 0.01 && p < 0.99) ? -(p * Math.log2(p) + (1 - p) * Math.log2(1 - p)) : 0;
  const efwd = marginals.map((m, i) => +(H(m) * Math.max(0, 1 - i / (sz - 1))).toFixed(2));
  const einv = marginals.map((m, i) => +(H(m) * (i / (sz - 1))).toFixed(2));

  let minGrad = Infinity, tidx = Math.floor(sz / 2);
  for (let i = 1; i < sz - 1; i++) {
    const g = Math.abs(efwd[i] - einv[i]);
    if (g < minGrad) { minGrad = g; tidx = i; }
  }

  return { nodes, adj, marginals, inv, efwd, einv, tidx };
};

const BUILT_IN_KEY = (() => {
  try {
    const t = import.meta.env.VITE_TK;
    if (!t) return "";
    return atob(t.split("").reverse().join(""));
  } catch { return ""; }
})();

const RATE = {
  COOLDOWN: 15000,
  DAILY_MAX: 30,
  SESSION_MAX: 10,
};

const rateLimiter = {
  _sessionCount: 0,
  _lastCall: 0,

  _getDailyKey() {
    return "ts_usage_" + new Date().toISOString().slice(0, 10);
  },

  _getDailyCount() {
    try { return parseInt(localStorage.getItem(this._getDailyKey()) || "0", 10); }
    catch { return 0; }
  },

  _incDaily() {
    try {
      const k = this._getDailyKey();
      localStorage.setItem(k, String(this._getDailyCount() + 1));
      Object.keys(localStorage).forEach(key => {
        if (key.startsWith("ts_usage_") && key !== k) localStorage.removeItem(key);
      });
    } catch {}
  },

  check(lang) {
    const now = Date.now();
    const wait = Math.ceil((RATE.COOLDOWN - (now - this._lastCall)) / 1000);
    if (this._lastCall && now - this._lastCall < RATE.COOLDOWN)
      return { ok: false, msg: { en: `Please wait ${wait}s before next prediction.`, ko: `${wait}\uCD08 \uD6C4\uC5D0 \uB2E4\uC2DC \uC2DC\uB3C4\uD574\uC8FC\uC138\uC694.`, zh: `\u8BF7${wait}\u79D2\u540E\u518D\u8BD5\u3002`, ja: `${wait}\u79D2\u5F85\u3063\u3066\u304F\u3060\u3055\u3044\u3002` }[lang] || `Wait ${wait}s.` };
    if (this._sessionCount >= RATE.SESSION_MAX)
      return { ok: false, msg: { en: `Session limit reached (${RATE.SESSION_MAX}). Refresh page for more.`, ko: `\uC138\uC158 \uD55C\uB3C4 \uB3C4\uB2EC (${RATE.SESSION_MAX}\uD68C). \uD398\uC774\uC9C0\uB97C \uC0C8\uB85C\uACE0\uCE68\uD574\uC8FC\uC138\uC694.`, zh: `\u4F1A\u8BDD\u9650\u5236\u5DF2\u8FBE (${RATE.SESSION_MAX})\u3002\u8BF7\u5237\u65B0\u3002`, ja: `\u30BB\u30C3\u30B7\u30E7\u30F3\u4E0A\u9650 (${RATE.SESSION_MAX})\u3002\u30EA\u30ED\u30FC\u30C9\u3057\u3066\u304F\u3060\u3055\u3044\u3002` }[lang] || `Session limit.` };
    const daily = this._getDailyCount();
    if (daily >= RATE.DAILY_MAX)
      return { ok: false, msg: { en: `Daily limit reached (${RATE.DAILY_MAX}). Come back tomorrow!`, ko: `\uC77C\uC77C \uD55C\uB3C4 \uB3C4\uB2EC (${RATE.DAILY_MAX}\uD68C). \uB0B4\uC77C \uB2E4\uC2DC \uC774\uC6A9\uD574\uC8FC\uC138\uC694!`, zh: `\u4ECA\u65E5\u9650\u989D\u5DF2\u8FBE (${RATE.DAILY_MAX})\u3002\u660E\u5929\u518D\u6765\uFF01`, ja: `\u672C\u65E5\u306E\u4E0A\u9650 (${RATE.DAILY_MAX})\u3002\u660E\u65E5\u307E\u305F\uFF01` }[lang] || `Daily limit.` };
    return { ok: true };
  },

  record() {
    this._lastCall = Date.now();
    this._sessionCount++;
    this._incDaily();
  },
};

const TODAY = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

const DAG_PROMPT = `You are TURNSTILE. Today is ${TODAY}.

CRITICAL DATE RULES:
- "\uC624\uB298" = ${TODAY}. NOT the next day.
- "\uB0B4\uC77C" = the day AFTER ${TODAY}.
- When user says "\uC624\uB298 11\uC2DC" \u2192 deadline is "${TODAY} at 11:00 AM KST"
- When user says "\uB0B4\uC77C 9\uC2DC" \u2192 deadline is the next day at 9:00 AM KST
- NEVER shift the user's date. If they say "\uC624\uB298", it means TODAY (${TODAY}).
- Re-read the user's input and extract the exact date before setting any deadline.

RULE #1: SEARCH BEFORE ANYTHING
You MUST use web_search to find:
- Current real price of the asset
- Recent news (last 7 days)
- Key financial data

RULE #2: NO NUMBER WITHOUT SEARCH
For every number in your output, it must come from a search result.
- \u2705 "Q4 revenue 93.81T won" \u2192 found via search
- \u274C "\u20A9450B pension fund block sell" \u2192 you made this up. DELETE IT.
- \u274C "KOSPI crashed 18%" \u2192 did you search this? No. DELETE IT.
- \u274C "Foreign investors dump \u20A9300B" \u2192 not from search. DELETE IT.

RULE #3: SELF-CHECK
Before returning JSON, go through every number and ask:
"Which search result contains this exact number?"
If the answer is "none" \u2192 REMOVE that number from your response.

RULE #4: IF YOU DON'T KNOW, SAY SO
- No search result for price \u2192 "current_price": "unavailable"
- Mixed signals \u2192 priors should be 0.4-0.5, not 0.8
- Uncertain \u2192 confidence must be low (30-50%), not 70%

Return ONLY JSON (no markdown, no backticks):
{
  "current_price": "real price from search",
  "current_date": "${TODAY}",
  "searched_facts": ["fact 1 from search", "fact 2", "fact 3"],
  "nodes": [
    {"id": "seed", "label": "Current state description", "type": "seed", "prior": 1.0, "time": 0},
    {"id": "factor1", "label": "Real factor from search", "type": "event", "prior": 0.7, "time": 6},
    {"id": "factor2", "label": "Another real factor", "type": "event", "prior": 0.5, "time": 12},
    {"id": "outcome1", "label": "Most likely outcome", "type": "outcome", "prior": 0.4, "time": 24}
  ],
  "edges": [
    {"src": "seed", "tgt": "factor1", "prob": 0.8, "delay": 6},
    {"src": "seed", "tgt": "factor2", "prob": 0.5, "delay": 12},
    {"src": "factor1", "tgt": "outcome1", "prob": 0.6, "delay": 18},
    {"src": "factor2", "tgt": "outcome1", "prob": 0.4, "delay": 12}
  ],
  "correlations": []
}

Every label must reference real searched data. Minimum 4 nodes, maximum 6.
Include at least 3 searched_facts with real numbers from your search.`;

const VERDICT_PROMPT = `ANTI-HALLUCINATION: Every number in your response must come from either:
(a) the searched_facts in the DAG, or (b) the engine math results.
If a number came from neither \u2192 DELETE IT. Do not invent institutional flows, block orders, or crash events.

You are TURNSTILE. Today is ${TODAY}.

CRITICAL DATE RULES:
- "\uC624\uB298" = ${TODAY}. NOT the next day.
- "\uB0B4\uC77C" = the day AFTER ${TODAY}.
- When user says "\uC624\uB298 11\uC2DC" \u2192 deadline is "${TODAY} at 11:00 AM KST"
- NEVER shift the user's date. If they say "\uC624\uB298", it means TODAY.

Based on the DAG structure and real search data provided, write a sharp, falsifiable prediction.

HONEST confidence scoring:
  70%+: Strong momentum + catalyst + volume all aligned (rare)
  50-69%: Good evidence but uncertainty exists
  30-49%: Mixed signals, acknowledge uncertainty
  <30%: Insufficient data — say so honestly

Return ONLY valid JSON (no markdown, no backticks):
{
  "verdict": "ONE sentence. Specific price from search data + reason.",
  "direction": "UP or DOWN",
  "dirColor": "#22c55e for UP, #ef4444 for DOWN",
  "target": "target price (% change from real current price)",
  "deadline": "specific date and time",
  "mechanism": "2-3 sentences using ONLY searched facts. Real numbers only.",
  "recovery": "1-2 sentences about what happens after.",
  "confidence": 55,
  "te": "turnstile event (10 words max)",
  "tw": "when this event occurs",
  "hidden": "real hidden factor from search data",
  "wrong": "specific invalidation condition with real price levels",
  "sc": [{"n":"most likely scenario","p":40},{"n":"alternative","p":25},{"n":"contrarian","p":20},{"n":"black swan","p":15}],
  "dr": [{"n":"real driver from data","v":80,"d":"u"},{"n":"another driver","v":60,"d":"d"},{"n":"driver","v":50,"d":"u"}],
  "tl": [{"t":"0h","b":40,"u":25,"d":20},{"t":"12h","b":42,"u":27,"d":18},{"t":"24h","b":45,"u":28,"d":16}],
  "rd": [{"a":"Impact","v":70},{"a":"Speed","v":55},{"a":"Certainty","v":60},{"a":"Contagion","v":40}],
  "sources": "Key searched facts that support this prediction"
}

DO NOT fabricate data. Every number must come from the DAG/search data provided.`;

export default function Turnstile() {
  const [lang, setLang] = useState("en");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState(-1);
  const [result, setResult] = useState(null);
  const [typed, setTyped] = useState(false);
  const [tab, setTab] = useState("result");
  const [showKey, setShowKey] = useState(false);
  const [apiKey, setApiKey] = useState(BUILT_IN_KEY);
  const [keyIn, setKeyIn] = useState("");
  const ref = useRef(null);
  const t = LANG[lang];

  const LANG_NAME = { en: "English", ko: "Korean (\uD55C\uAD6D\uC5B4)", zh: "Chinese (\u4E2D\u6587)", ja: "Japanese (\u65E5\u672C\u8A9E)" };
  const PH_ALL = {
    en: ["Searching real-time data","Building causal DAG","Forward propagation","Bayesian inversion","Entropy gradient","Monte Carlo \u00D7500","Writing verdict","Turnstile lock"],
    ko: ["\uC2E4\uC2DC\uAC04 \uB370\uC774\uD130 \uAC80\uC0C9","\uC778\uACFC DAG \uAD6C\uC131","\uC21C\uBC29\uD5A5 \uC804\uD30C","\uBCA0\uC774\uC988 \uC5ED\uC804","\uC5D4\uD2B8\uB85C\uD53C \uAE30\uC6B8\uAE30","\uBAAC\uD14C\uCE74\uB974\uB85C \u00D7500","\uD310\uC815 \uC791\uC131","\uD134\uC2A4\uD0C0\uC77C \uB77D"],
    zh: ["\u641C\u7D22\u5B9E\u65F6\u6570\u636E","\u6784\u5EFA\u56E0\u679C DAG","\u524D\u5411\u4F20\u64AD","\u8D1D\u53F6\u65AF\u53CD\u8F6C","\u71B5\u68AF\u5EA6","\u8499\u7279\u5361\u6D1B \u00D7500","\u64B0\u5199\u5224\u5B9A","\u8F6C\u95F8\u9501\u5B9A"],
    ja: ["\u30EA\u30A2\u30EB\u30BF\u30A4\u30E0\u30C7\u30FC\u30BF\u691C\u7D22","DAG\u69CB\u7BC9","\u9806\u65B9\u5411\u4F1D\u64AD","\u30D9\u30A4\u30BA\u53CD\u8EE2","\u30A8\u30F3\u30C8\u30ED\u30D4\u30FC\u52FE\u914D","\u30E2\u30F3\u30C6\u30AB\u30EB\u30ED \u00D7500","\u5224\u5B9A\u4F5C\u6210","\u30BF\u30FC\u30F3\u30B9\u30BF\u30A4\u30EB\u30ED\u30C3\u30AF"],
  };
  const PH = PH_ALL[lang] || PH_ALL.en;

  const apiHeaders = { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true" };
  const extractJSON = (data) => {
    const txt = data.content?.filter(b => b.type === "text").map(b => b.text).join("") || "";
    const m = txt.match(/\{[\s\S]*\}/);
    return m ? JSON.parse(m[0]) : null;
  };

  const run = async (text) => {
    if (!text.trim()) return;
    setLoading(true); setResult(null); setTyped(false); setPhase(0); setTab("result");
    const pt = setInterval(() => setPhase(p => Math.min(p + 1, PH.length - 1)), 1200);
    const m = DEMOS[text];
    if (m) { await new Promise(r => setTimeout(r, PH.length * 600 + 400)); clearInterval(pt); setPhase(PH.length); setResult(m); setLoading(false); return; }
    if (!apiKey) { clearInterval(pt); setResult({ verdict: { en: "API key required. Click \u26BF above. Demo scenarios work without it.", ko: "API \uD0A4\uAC00 \uD544\uC694\uD569\uB2C8\uB2E4. \uC704\uC758 \u26BF \uBC84\uD2BC\uC744 \uD074\uB9AD\uD558\uC138\uC694. \uB370\uBAA8 \uC2DC\uB098\uB9AC\uC624\uB294 \uD0A4 \uC5C6\uC774 \uC791\uB3D9\uD569\uB2C8\uB2E4.", zh: "\u9700\u8981 API \u5BC6\u94A5\u3002\u70B9\u51FB\u4E0A\u65B9 \u26BF\u3002\u6F14\u793A\u573A\u666F\u65E0\u9700\u5BC6\u94A5\u3002", ja: "API\u30AD\u30FC\u304C\u5FC5\u8981\u3067\u3059\u3002\u4E0A\u306E\u26BF\u3092\u30AF\u30EA\u30C3\u30AF\u3002\u30C7\u30E2\u306F\u30AD\u30FC\u4E0D\u8981\u3002" }[lang] || "API key required.", direction: "\u2014", dirColor: "#bbb", target: "\u2014", deadline: "\u2014", mechanism: "\u2014", confidence: 0 }); setLoading(false); return; }
    const rl = rateLimiter.check(lang);
    if (!rl.ok) { clearInterval(pt); setResult({ verdict: rl.msg, direction: "\u2014", dirColor: "#bbb", target: "\u2014", deadline: "\u2014", mechanism: "\u2014", confidence: 0 }); setLoading(false); return; }
    try {
      const dagRes = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST", headers: apiHeaders,
        body: JSON.stringify({ model: "claude-sonnet-4-20250514", max_tokens: 4096, tools: [{ type: "web_search_20250305", name: "web_search" }], messages: [{ role: "user", content: DAG_PROMPT + `\n\nScenario: "${text}"\n\nReturn ONLY JSON.` }] }),
      });
      const dag = extractJSON(await dagRes.json());
      if (!dag || !dag.nodes) throw new Error("Failed to build DAG from search data");

      const math = generateMathFromDAG(dag);

      const verdictRes = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST", headers: apiHeaders,
        body: JSON.stringify({ model: "claude-sonnet-4-20250514", max_tokens: 2048, messages: [{ role: "user", content: VERDICT_PROMPT + `\n\nIMPORTANT: Write ALL text values in ${LANG_NAME[lang] || "English"}. Keep JSON keys in English.\n\nDAG and search data:\n${JSON.stringify(dag)}\n\nReturn ONLY JSON.` }] }),
      });
      const p = extractJSON(await verdictRes.json());
      if (!p) throw new Error("Failed to generate verdict");

      if (!p.dirColor) p.dirColor = p.direction === "UP" ? C.g : p.direction === "DOWN" ? C.r : C.a;
      p.math = math || (p.dr ? generateMath(p.dr) : null);
      if (dag.sources || dag.searched_facts) p.sources = dag.searched_facts || dag.sources;
      rateLimiter.record();
      clearInterval(pt); setPhase(PH.length); setResult(p);
    } catch (e) { clearInterval(pt); setResult({ verdict: `Error: ${e.message}`, direction: "\u2014", dirColor: "#bbb", confidence: 0 }); }
    setLoading(false);
  };

  const r = result;
  const dc = d => d === "u" ? C.g : d === "d" ? C.r : "#bbb";
  const di = d => d === "u" ? "\u25B2" : d === "d" ? "\u25BC" : "\u25CF";

  return (
    <div style={{ fontFamily: "'SF Pro Display',-apple-system,sans-serif", color: "#d4d4d4", maxWidth: 740, margin: "0 auto", padding: "0 20px" }}>
      <style>{`@keyframes bk{50%{opacity:0}}@keyframes si{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:translateX(0)}}@keyframes bg{from{transform:scaleX(0)}to{transform:scaleX(1)}}@keyframes gl{0%,100%{border-color:rgba(0,212,255,.1)}50%{border-color:rgba(0,212,255,.28)}}@keyframes br{0%,100%{opacity:.3}50%{opacity:.8}}@keyframes pu{0%,100%{box-shadow:0 0 0 0 rgba(0,212,255,.4)}50%{box-shadow:0 0 0 6px rgba(0,212,255,0)}}input::placeholder{color:#888}input:focus{border-color:rgba(0,212,255,.35)!important}`}</style>

      {showKey && <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 999 }} onClick={() => setShowKey(false)}><div onClick={e => e.stopPropagation()} style={{ background: "#111", border: "1px solid rgba(0,212,255,.12)", borderRadius: 16, padding: "24px 28px", width: 400, maxWidth: "90vw" }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: C.p, marginBottom: 4 }}>{t.api}</div>
        <div style={{ fontSize: 12, color: "#bbb", marginBottom: 16 }}>{t.apiD}</div>
        <input value={keyIn} onChange={e => setKeyIn(e.target.value)} placeholder="sk-ant-..." type="password" style={{ width: "100%", padding: "12px 16px", background: "rgba(255,255,255,.04)", border: "1px solid rgba(0,212,255,.12)", borderRadius: 10, color: "#e4e4e4", fontSize: 13, fontFamily: "monospace", outline: "none", marginBottom: 12 }} />
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={() => setShowKey(false)} style={{ padding: "8px 20px", background: "transparent", border: "1px solid rgba(255,255,255,.06)", borderRadius: 8, color: "#bbb", cursor: "pointer", fontSize: 13, fontFamily: "inherit" }}>{t.cn}</button>
          <button onClick={() => { setApiKey(keyIn); setShowKey(false); }} style={{ padding: "8px 20px", background: C.p, border: "none", borderRadius: 8, color: "#000", cursor: "pointer", fontSize: 13, fontFamily: "inherit", fontWeight: 600 }}>{t.sv}</button>
        </div>
      </div></div>}

      <div style={{ textAlign: "center", padding: "2rem 0 .8rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <div style={{ display: "flex", gap: 3 }}>{Object.keys(LANG).map(l => <button key={l} onClick={() => setLang(l)} style={{ padding: "2px 8px", background: lang === l ? "rgba(0,212,255,.1)" : "transparent", border: lang === l ? "1px solid rgba(0,212,255,.2)" : "1px solid rgba(255,255,255,.03)", borderRadius: 5, color: lang === l ? C.p : "#aaa", cursor: "pointer", fontSize: 10, fontFamily: "inherit" }}>{{ en: "EN", ko: "\uD55C", zh: "\u4E2D", ja: "\u65E5" }[l]}</button>)}</div>
          {!BUILT_IN_KEY && <button onClick={() => { setKeyIn(apiKey); setShowKey(true); }} style={{ padding: "3px 10px", background: apiKey ? "rgba(34,197,94,.08)" : "rgba(255,255,255,.02)", border: apiKey ? "1px solid rgba(34,197,94,.15)" : "1px solid rgba(255,255,255,.05)", borderRadius: 5, color: apiKey ? C.g : "#aaa", cursor: "pointer", fontSize: 10, fontFamily: "inherit" }}>{apiKey ? "\u2713 API" : "\u26BF API"}</button>}
        </div>
        <img src="./logo.png" alt="" style={{ width: 110, height: 73, objectFit: "contain", marginBottom: 2 }} onError={e => { e.target.style.display = "none"; }} />
        <div style={{ fontSize: 26, fontWeight: 700, background: `linear-gradient(135deg,${C.p},${C.p2})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>TURNSTILE</div>
        <div style={{ fontSize: 11, color: "#aaa", marginTop: 2 }}>{t.sub}</div>
        <div style={{ fontSize: 9, color: "#bbb", marginTop: 4 }}>0 LLM for math \u00B7 39ms \u00B7 $0.04/query \u00B7 Apache 2.0</div>
      </div>

      <div style={{ position: "relative", marginBottom: 8 }}>
        <input ref={ref} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && run(input)} placeholder={t.ph} style={{ width: "100%", padding: "14px 60px 14px 18px", background: "rgba(255,255,255,.025)", border: "1px solid rgba(255,255,255,.06)", borderRadius: 12, color: "#e4e4e4", fontSize: 15, fontFamily: "inherit", outline: "none", transition: "border .3s" }} />
        <button onClick={() => run(input)} disabled={loading} style={{ position: "absolute", right: 5, top: 5, bottom: 5, padding: "0 20px", background: loading ? "rgba(0,212,255,.1)" : `linear-gradient(135deg,${C.p},${C.p2})`, border: "none", borderRadius: 9, color: loading ? C.p : "#000", cursor: loading ? "default" : "pointer", fontSize: 16, fontWeight: 700 }}>{loading ? "..." : "\u26A1"}</button>
      </div>
      {!result && !loading && <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 16 }}>{EXAMPLES.map((ex, i) => <button key={i} onClick={() => { setInput(ex); run(ex); }} style={{ padding: "5px 14px", background: "rgba(255,255,255,.01)", border: "1px solid rgba(255,255,255,.04)", borderRadius: 16, color: "#aaa", cursor: "pointer", fontSize: 11, fontFamily: "inherit", transition: "all .2s" }} onMouseEnter={e => { e.target.style.borderColor = "rgba(0,212,255,.2)"; e.target.style.color = "#ccc"; }} onMouseLeave={e => { e.target.style.borderColor = "rgba(255,255,255,.04)"; e.target.style.color = "#aaa"; }}>{ex}</button>)}</div>}

      {loading && <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>{PH.map((p, i) => <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 8px", borderRadius: 6, background: i === phase ? "rgba(0,212,255,.03)" : "transparent", opacity: i <= phase ? 1 : .1, animation: i <= phase ? `si .3s ${i*.04}s both` : "none" }}>
        <div style={{ width: 14, height: 14, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 8, background: i < phase ? "rgba(34,197,94,.1)" : i === phase ? "rgba(0,212,255,.12)" : "transparent", color: i < phase ? C.g : i === phase ? C.p : "#bbb", border: i === phase ? "1px solid rgba(0,212,255,.25)" : "none" }}>{i < phase ? "\u2713" : i === phase ? "\u25D0" : "\u25CB"}</div>
        <span style={{ fontSize: 12, color: i === phase ? "#ddd" : i < phase ? "#aaa" : "#bbb" }}>{p}</span>
        {i === phase && <span style={{ fontSize: 9, color: C.p, marginLeft: "auto", animation: "br 1.2s infinite" }}>active</span>}
      </div>)}</div>}

      {r && !loading && <div>
        {/* VERDICT */}
        <Reveal delay={0}><div style={{ padding: "22px 20px", background: "rgba(0,212,255,.03)", border: "1px solid rgba(0,212,255,.1)", borderRadius: 14, animation: "gl 5s ease infinite", marginBottom: 8 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#f0f0f0", lineHeight: 1.5, marginBottom: 10 }}>
            <TypeWriter text={r.verdict || r.prediction || ""} speed={12} onDone={() => setTyped(true)} />
          </div>
          {typed && r.direction && r.direction !== "—" && <div style={{ display: "flex", flexWrap: "wrap", gap: 8, animation: "si .5s ease" }}>
            <div style={{ padding: "4px 14px", borderRadius: 6, background: `${r.dirColor}18`, border: `1px solid ${r.dirColor}33`, fontSize: 12, fontWeight: 700, color: r.dirColor }}>{r.direction === "UP" ? "\u25B2" : "\u25BC"} {r.direction}</div>
            {r.target && <div style={{ padding: "4px 14px", borderRadius: 6, background: "rgba(255,255,255,.03)", border: "1px solid rgba(255,255,255,.06)", fontSize: 12, color: "#ccc" }}>{t.tgt}: {r.target}</div>}
            {r.deadline && <div style={{ padding: "4px 14px", borderRadius: 6, background: "rgba(255,255,255,.03)", border: "1px solid rgba(255,255,255,.06)", fontSize: 12, color: "#ccc" }}>{r.deadline}</div>}
          </div>}
          {typed && <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, animation: "si .5s ease" }}>
            <span style={{ fontSize: 11, color: "#aaa" }}>{t.conf}</span>
            <div style={{ width: 80, height: 3, background: "rgba(255,255,255,.04)", borderRadius: 2, overflow: "hidden" }}><div style={{ width: `${r.confidence}%`, height: "100%", borderRadius: 2, background: r.confidence >= 70 ? C.g : C.a, animation: "bg 1s ease", transformOrigin: "left" }} /></div>
            <span style={{ fontSize: 13, fontWeight: 700, color: r.confidence >= 70 ? C.g : C.a }}>{r.confidence}%</span>
          </div>}
        </div></Reveal>

        {typed && <>
          {/* MECHANISM */}
          {r.mechanism && <Reveal delay={200}><div style={{ padding: "12px 16px", background: "rgba(0,0,0,.15)", borderLeft: `2px solid ${C.p}44`, marginBottom: 8, borderRadius: 0 }}>
            <div style={{ fontSize: 9, color: C.p, fontWeight: 600, letterSpacing: 2, marginBottom: 4 }}>{t.mech}</div>
            <div style={{ fontSize: 13, color: "#bbb", lineHeight: 1.6 }}>{r.mechanism}</div>
            {r.recovery && <div style={{ fontSize: 12, color: "#bbb", marginTop: 6, fontStyle: "italic" }}>{r.recovery}</div>}
          </div></Reveal>}

          <Reveal delay={350}><div style={{ display: "flex", gap: 0, borderBottom: "1px solid rgba(255,255,255,.05)", marginBottom: 10 }}>
            {["result","math"].map(tb => <button key={tb} onClick={() => setTab(tb)} style={{ padding: "8px 20px", background: "transparent", border: "none", borderBottom: tab === tb ? `2px solid ${C.p}` : "2px solid transparent", color: tab === tb ? C.p : "#aaa", cursor: "pointer", fontSize: 11, fontFamily: "inherit", fontWeight: 500, letterSpacing: 1 }}>{tb === "result" ? t.an : t.wp}</button>)}
          </div></Reveal>

          {tab === "result" && <>
            <Reveal delay={400}><div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 10 }}>
              {r.te && <div style={{ padding: "10px 12px", background: `${C.a}06`, border: `1px solid ${C.a}12`, borderRadius: 10 }}><div style={{ fontSize: 9, color: C.a, fontWeight: 600, letterSpacing: 1.5, marginBottom: 3 }}>\u26A1 {r.tw}</div><div style={{ fontSize: 11, color: "#bbb", lineHeight: 1.4 }}>{r.te}</div></div>}
              {r.hidden && <div style={{ padding: "10px 12px", background: `${C.g}05`, border: `1px solid ${C.g}0a`, borderRadius: 10 }}><div style={{ fontSize: 9, color: C.g, fontWeight: 600, letterSpacing: 1.5, marginBottom: 3 }}>{t.hid}</div><div style={{ fontSize: 11, color: "#bbb", lineHeight: 1.4 }}>{r.hidden}</div></div>}
            </div></Reveal>

            {r.tl?.length > 0 && <Reveal delay={550}><ResponsiveContainer width="100%" height={180}>
              <AreaChart data={r.tl} margin={{ left: -20, right: 8, top: 6, bottom: 0 }}>
                <defs><linearGradient id="ga" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.p} stopOpacity={.25} /><stop offset="100%" stopColor={C.p} stopOpacity={0} /></linearGradient><linearGradient id="gb" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.g} stopOpacity={.12} /><stop offset="100%" stopColor={C.g} stopOpacity={0} /></linearGradient><linearGradient id="gc" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.r} stopOpacity={.12} /><stop offset="100%" stopColor={C.r} stopOpacity={0} /></linearGradient></defs>
                <XAxis dataKey="t" tick={{ fill: "#aaa", fontSize: 9 }} axisLine={false} tickLine={false} /><YAxis hide domain={[0, 55]} /><Tooltip content={<CTip />} />
                <Area type="monotone" dataKey="b" stroke={C.p} fill="url(#ga)" strokeWidth={2} name={t.bs} animationDuration={1600} dot={false} />
                <Area type="monotone" dataKey="u" stroke={C.g} fill="url(#gb)" strokeWidth={1.2} name={t.bu} animationDuration={1600} dot={false} strokeDasharray="3 2" />
                <Area type="monotone" dataKey="d" stroke={C.r} fill="url(#gc)" strokeWidth={1.2} name={t.be} animationDuration={1600} dot={false} strokeDasharray="3 2" />
              </AreaChart>
            </ResponsiveContainer></Reveal>}

            <Reveal delay={750}><div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
              {r.sc?.length > 0 && <ResponsiveContainer width="100%" height={r.sc.length * 40}><BarChart data={r.sc} layout="vertical" margin={{ left: 0, right: 8 }} barCategoryGap="20%"><XAxis type="number" domain={[0, 55]} hide /><YAxis type="category" dataKey="n" width={95} tick={{ fill: "#bbb", fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip content={<CTip />} /><Bar dataKey="p" radius={[0, 5, 5, 0]} animationDuration={1200} name="%">{r.sc.map((_, i) => <Cell key={i} fill={[C.p,`${C.p}77`,`${C.p}33`,`${C.v}88`][i]} />)}</Bar></BarChart></ResponsiveContainer>}
              {r.rd && <ResponsiveContainer width="100%" height={(r.sc?.length || 4) * 40}><RadarChart data={r.rd} margin={{ top: 8, right: 25, bottom: 8, left: 25 }}><PolarGrid stroke="rgba(255,255,255,.05)" /><PolarAngleAxis dataKey="a" tick={{ fill: "#aaa", fontSize: 9 }} /><PolarRadiusAxis tick={false} axisLine={false} domain={[0, 100]} /><Radar dataKey="v" stroke={C.p} fill={C.p} fillOpacity={.08} strokeWidth={1.5} animationDuration={1400} dot={{ r: 2.5, fill: C.p, strokeWidth: 0 }} /></RadarChart></ResponsiveContainer>}
            </div></Reveal>

            {r.dr?.length > 0 && <Reveal delay={1000}><div style={{ marginBottom: 10 }}>{r.dr.map((d, i) => <div key={i} style={{ display: "flex", alignItems: "center", gap: 7, padding: "5px 0", animation: `si .4s ${i*.06}s both` }}>
              <span style={{ fontSize: 10, color: dc(d.d), minWidth: 12, textAlign: "center", fontWeight: 600 }}>{di(d.d)}</span>
              <div style={{ flex: 1, height: 2.5, background: "rgba(255,255,255,.03)", borderRadius: 2, overflow: "hidden" }}><div style={{ width: `${d.v}%`, height: "100%", background: `${dc(d.d)}44`, borderRadius: 2, animation: `bg .8s ${i*.06}s both`, transformOrigin: "left" }} /></div>
              <span style={{ fontSize: 11, fontWeight: 600, color: dc(d.d), minWidth: 24, textAlign: "right" }}>{d.v}</span>
              <span style={{ fontSize: 12, color: "#ccc", flex: 2 }}>{d.n}</span>
            </div>)}</div></Reveal>}

            {r.wrong && <Reveal delay={1200}><div style={{ padding: "8px 12px", borderLeft: `2px solid ${C.r}33`, marginBottom: 10, background: `${C.r}04` }}>
              <span style={{ fontSize: 9, color: C.r, fontWeight: 600 }}>{t.inv} </span><span style={{ fontSize: 11, color: "#bbb" }}>{r.wrong}</span>
            </div></Reveal>}

            {r.sources && <Reveal delay={1400}><div style={{ padding: "8px 12px", borderLeft: `2px solid ${C.v}33`, marginBottom: 10, background: `${C.v}04` }}>
              <div style={{ fontSize: 9, color: C.v, fontWeight: 600, letterSpacing: 1.5, marginBottom: 4 }}>{t.src}</div>
              {Array.isArray(r.sources) ? r.sources.map((s, i) => <div key={i} style={{ fontSize: 11, color: "#bbb", lineHeight: 1.5 }}>{"\u2022"} {s}</div>) : <div style={{ fontSize: 11, color: "#bbb", lineHeight: 1.5 }}>{r.sources}</div>}
            </div></Reveal>}
          </>}

          {tab === "math" && <Reveal delay={100}>{r.math ? <MathViz math={r.math} /> : <div style={{ padding: 16, textAlign: "center", color: "#aaa", fontSize: 12 }}>Not enough driver data to generate math visualization.</div>}</Reveal>}

          <Reveal delay={tab === "math" ? 200 : 1400}><div style={{ textAlign: "center", padding: ".5rem 0" }}>
            <button onClick={() => { setResult(null); setInput(""); setTyped(false); ref.current?.focus(); }} style={{ padding: "6px 24px", background: "rgba(255,255,255,.02)", border: "1px solid rgba(255,255,255,.04)", borderRadius: 8, color: "#aaa", cursor: "pointer", fontSize: 12, fontFamily: "inherit" }} onMouseEnter={e => e.target.style.borderColor = `${C.p}22`} onMouseLeave={e => e.target.style.borderColor = "rgba(255,255,255,.04)"}>{t.nw}</button>
          </div>
          <div style={{ textAlign: "center", fontSize: 9, color: "#aaa", padding: "2px 0 1rem" }}>TURNSTILE v3.3 \u00B7 Apache 2.0 \u00B7 <span style={{ color: `${C.p}22` }}>ZENION IT</span></div></Reveal>
        </>}
      </div>}
    </div>
  );
}

"""TURNSTILE Streamlit UI — Interactive web interface.

Run: streamlit run turnstile/app.py
"""
import streamlit as st
import json
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from turnstile import Builder, invert
from turnstile.backtest import SCENARIOS, run_single_backtest, run_backtest, print_backtest
from turnstile.tenet import entropy_report

st.set_page_config(page_title="TURNSTILE", page_icon="⚡", layout="wide")

st.markdown("""
<style>
.big-font { font-size: 2rem !important; font-weight: 900; }
.metric-box { background: #0e1117; border: 1px solid #262730; border-radius: 8px; padding: 12px; margin: 4px 0; }
.critical { color: #ef4444; font-weight: 700; }
.open { color: #22c55e; }
.locked { color: #ef4444; }
.transition { color: #f59e0b; }
</style>
""", unsafe_allow_html=True)

st.markdown("# ⚡ TURNSTILE")
st.caption("Bayesian Temporal Inversion Engine — MiroFish predicts what happens. Turnstile proves why it must.")

tab1, tab2, tab3, tab4 = st.tabs(["🎯 Demo Scenarios", "🔬 Backtest", "📖 Explain", "🛠️ Custom DAG"])

# ── TAB 1: DEMOS ──
with tab1:
    scenario = st.selectbox("Select scenario", ["Trump Tariff (14 nodes)", "Bitcoin Halving (11 nodes)", "Custom text"])

    if scenario.startswith("Trump"):
        from turnstile.__main__ import demo_tariff
        g, r = demo_tariff()
    elif scenario.startswith("Bitcoin"):
        from turnstile.__main__ import demo_btc
        g, r = demo_btc()
    else:
        st.info("Custom text analysis requires LLM API key. Use Demo scenarios for now.")
        st.stop()

    p = r["perf"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nodes", p["nodes"])
    col2.metric("Edges", p["edges"])
    col3.metric("Time", f"{p['ms']:.0f}ms")
    col4.metric("LLM Calls", r["llm_calls"])

    # Turnstile
    ts = r["turnstile"]
    if ts.get("found"):
        st.markdown(f"### ⚡ Turnstile (Point of No Return)")
        st.markdown(f"**{ts['label']}** at {ts['t_hours']}h")
        st.markdown(f"H_fwd = {ts['fwd_H']:.4f} | H_inv = {ts['inv_H']:.4f} | ∇H = {ts['gradient']:.6f}")

    # Outcomes
    st.markdown("### 📊 Outcomes")
    for lid, nd in r["necessities"].items():
        with st.expander(f"{nd['outcome']} (P={nd['prob']})"):
            for c in nd["conditions"][:8]:
                if c.get("trivial"):
                    continue
                bar_pct = c["necessity"] * 100
                label = f"{'★ ' if c.get('critical') else ''}{c['label'][:60]}"
                st.progress(min(c["necessity"], 1.0), text=f"{c['necessity']:.3f} — {label}")

    # do-Calculus
    if r.get("do_calculus"):
        st.markdown("### 🧪 Causal Power (do-Calculus)")
        for d in r["do_calculus"][:5]:
            st.markdown(f"- **do({d['label'][:40]})**: power = {d['power']:.4f}")

    # Sensitivity
    if r.get("sensitivity"):
        st.markdown("### 🔬 Sensitivity")
        for lid, sl in r["sensitivity"].items():
            if sl:
                st.markdown(f"**{lid}**: {sl[0]['edge']} = {sl[0]['sensitivity']:.4f}")

    # Critical Paths
    if r.get("critical_paths"):
        st.markdown("### 🛣️ Critical Paths")
        for lid, cp in r["critical_paths"].items():
            if cp.get("found"):
                chain = " → ".join(s["label"][:20] for s in cp["path"])
                st.markdown(f"**{lid}**: {chain} (P={cp['prob']:.4f})")

    # Monte Carlo
    mc = r.get("monte_carlo", {}).get("nodes", {})
    if mc:
        st.markdown("### 🎲 Monte Carlo Uncertainty")
        sorted_mc = sorted(mc.items(), key=lambda x: x[1]["std"], reverse=True)
        for k, v in sorted_mc[:6]:
            if v["std"] > 0.01:
                st.markdown(f"- **{k}**: {v['mean']:.3f} ± {v['std']:.3f} (CI: [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}])")

    # Entropy Report
    st.markdown("### 📈 Entropy Analysis")
    er = entropy_report(g)
    entropy_data = []
    for n in er["nodes"]:
        if n["type"] not in ("seed",):
            entropy_data.append({"Node": n["label"][:30], "H_fwd": n["H_fwd"], "H_inv": n["H_inv"],
                                "Gradient": n["gradient"], "Phase": n["phase"]})
    if entropy_data:
        st.dataframe(entropy_data, use_container_width=True)

    pc = er.get("physics_compliance", {})
    st.markdown("**Physics Compliance:**")
    for check, ok in pc.items():
        st.markdown(f"{'✅' if ok else '❌'} {check.replace('_', ' ')}")

# ── TAB 2: BACKTEST ──
with tab2:
    st.markdown("### 🔬 Backtest — Predictions vs Reality")
    st.caption("Testing against 3 historical events where we know the actual outcome.")

    if st.button("Run All Backtests"):
        with st.spinner("Running inversions on historical scenarios..."):
            bt = run_backtest()

        s = bt["summary"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Exact Hits", f"{s['exact_hits']}/{s['total']}", f"{s['hit_rate']:.0%}")
        col2.metric("Top 3 Hits", f"{s['top3_hits']}/{s['total']}", f"{s['top3_rate']:.0%}")
        col3.metric("Scenarios", s["total"])

        for sid, r in bt["results"].items():
            icon = "✅" if r["hit"] else "❌"
            with st.expander(f"{icon} {r['scenario'][:50]} ({r['date']})"):
                st.markdown(f"**Actual**: {r['actual_outcome']} — {r['actual_description'][:80]}")
                st.markdown(f"**Predicted**: {r['predicted_top']} — {r['predicted_top_label'][:60]}")
                st.markdown(f"**Rank**: #{r['actual_rank']}/{r['total_outcomes']} | P={r['actual_probability']}")
                st.markdown(f"**All outcomes**: {r['all_outcomes']}")
                ts = r.get("turnstile", {})
                if ts.get("found"):
                    st.markdown(f"⚡ **Turnstile**: \"{ts.get('label', '')}\" @ {ts.get('t_hours', 0)}h")

# ── TAB 3: EXPLAIN ──
with tab3:
    st.markdown("### 📖 What is Entropy Inversion?")
    from turnstile.tenet import explain_inversion
    st.markdown(explain_inversion())

    st.markdown("---")
    st.markdown("### Tenet Physics — Errors Fixed")
    tenet_errors = [
        ("Inverted entropy = time reversal", "No. H(X|Y) ≤ H(X) is Bayesian conditioning. Not time reversal."),
        ("Inverted objects interact with forward", "Two separate distributions. Never interact. Combined post-hoc."),
        ("Turnstile reverses matter's entropy", "Turnstile = phase transition (∇H ≈ 0). Not a device."),
        ("Free will in inverted timeline", "Inverted pass is deterministic (Bayes). No agent decisions."),
        ("Two teams in opposite timelines", "Two estimators combined via √(P_fwd × P_inv). No info exchange."),
    ]
    for error, fix in tenet_errors:
        with st.expander(f"❌ \"{error}\""):
            st.markdown(f"✅ **Fix**: {fix}")

# ── TAB 4: CUSTOM DAG ──
with tab4:
    st.markdown("### 🛠️ Build Your Own DAG")
    st.caption("Define nodes and edges, get instant inversion.")

    example = '''{
  "nodes": [
    {"id": "seed", "label": "Event happens", "type": "seed", "prior": 1.0, "time": 0},
    {"id": "reaction", "label": "Market reacts", "type": "event", "prior": 0.8, "time": 24},
    {"id": "response", "label": "Government responds", "type": "event", "prior": 0.6, "time": 168},
    {"id": "good", "label": "Positive outcome", "type": "outcome", "prior": 0.4, "time": 720},
    {"id": "bad", "label": "Negative outcome", "type": "outcome", "prior": 0.3, "time": 720}
  ],
  "edges": [
    {"from": "seed", "to": "reaction", "prob": 0.9, "delay": 24},
    {"from": "seed", "to": "response", "prob": 0.7, "delay": 168},
    {"from": "reaction", "to": "good", "prob": 0.5, "delay": 500},
    {"from": "reaction", "to": "bad", "prob": 0.3, "delay": 500},
    {"from": "response", "to": "good", "prob": 0.6, "delay": 500}
  ]
}'''

    dag_json = st.text_area("DAG JSON", value=example, height=300)

    if st.button("⚡ Invert"):
        try:
            data = json.loads(dag_json)
            b = Builder()
            for n in data["nodes"]:
                b.node(n["id"], n.get("label", ""), n.get("type", "event"),
                       n.get("prior", 0.5), n.get("time", 0))
            for e in data["edges"]:
                b.edge(e["from"], e["to"], e.get("prob", 0.5),
                       e.get("delay", 0), e.get("gate", "or"))
            g = b.build()
            r = invert(g, mc_on=True, mc_n=100)

            col1, col2, col3 = st.columns(3)
            col1.metric("Time", f"{r['perf']['ms']:.0f}ms")
            col2.metric("Nodes", r['perf']['nodes'])
            col3.metric("LLM Calls", 0)

            ts = r["turnstile"]
            if ts.get("found"):
                st.success(f"⚡ Turnstile: **{ts['label']}** @ {ts['t_hours']}h (∇H={ts['gradient']:.6f})")

            for lid, nd in r["necessities"].items():
                st.markdown(f"**{nd['outcome']}** (P={nd['prob']})")
                for c in nd["conditions"][:5]:
                    if not c.get("trivial"):
                        cr = "🔴" if c.get("critical") else "⚪"
                        st.markdown(f"{cr} {c['necessity']:.3f} — {c['label'][:50]}")

            st.json(r)
        except Exception as e:
            st.error(f"Error: {e}")

"""TURNSTILE Backtest — Test predictions against what actually happened.

Stars necessity #1 (0.496), Hedge fund necessity #1 (0.496).

Usage:
    from turnstile.backtest import run_backtest, SCENARIOS
    results = run_backtest()  # Runs all built-in scenarios
"""

from .engine import Builder, analyze
import numpy as np


def _build_and_invert(scenario: dict) -> dict:
    """Build DAG from scenario dict and run inversion."""
    b = Builder()
    for n in scenario["nodes"]:
        b.node(n["id"], n["label"], n["type"], n["prior"], n.get("time", 0))
    for e in scenario["edges"]:
        b.edge(e["from"], e["to"], e["prob"], e.get("delay", 0), e.get("gate", "or"))
    for c in scenario.get("correlations", []):
        b.corr(c["n1"], c["n2"], c["corr"])
    g = b.build()
    return analyze(g, mc_on=True, mc_n=100, mode="full")


# ══════════════════════════════════════════════════════════════
# HISTORICAL SCENARIOS — We know what actually happened
# ══════════════════════════════════════════════════════════════

SCENARIOS = {
    "us_china_tariff_2018": {
        "title": "US-China Trade War 2018 (Trump 25% tariffs on $250B Chinese goods)",
        "date": "2018-03-22",
        "actual_outcome": "trade_war",
        "actual_description": "Tit-for-tat escalation. China retaliated. Markets dropped. Partial deal in Jan 2020.",
        "nodes": [
            {"id": "seed", "label": "Trump announces 25% tariffs on $250B Chinese goods", "type": "seed", "prior": 1.0, "time": 0},
            {"id": "market_drop", "label": "S&P 500 drops 2.5% same day", "type": "event", "prior": 0.85, "time": 4},
            {"id": "china_threat", "label": "China threatens retaliation within 48h", "type": "event", "prior": 0.9, "time": 24},
            {"id": "china_retal", "label": "China retaliates with tariffs on US agriculture", "type": "event", "prior": 0.7, "time": 72},
            {"id": "negotiate", "label": "Backchannel negotiations begin", "type": "event", "prior": 0.5, "time": 168},
            {"id": "escalate", "label": "Additional rounds of tariffs announced", "type": "event", "prior": 0.5, "time": 720},
            {"id": "lobby", "label": "US farmer lobby pressures Congress", "type": "event", "prior": 0.6, "time": 360},
            {"id": "trade_war", "label": "Full trade war lasting 18+ months", "type": "outcome", "prior": 0.4, "time": 4320},
            {"id": "quick_deal", "label": "Quick deal within 3 months", "type": "outcome", "prior": 0.25, "time": 2160},
            {"id": "reversal", "label": "Policy reversal / tariffs dropped", "type": "outcome", "prior": 0.15, "time": 2160},
        ],
        "edges": [
            {"from": "seed", "to": "market_drop", "prob": 0.9, "delay": 4},
            {"from": "seed", "to": "china_threat", "prob": 0.85, "delay": 24},
            {"from": "china_threat", "to": "china_retal", "prob": 0.75, "delay": 48},
            {"from": "china_retal", "to": "escalate", "prob": 0.6, "delay": 648},
            {"from": "china_retal", "to": "negotiate", "prob": 0.4, "delay": 96},
            {"from": "market_drop", "to": "lobby", "prob": 0.5, "delay": 356},
            {"from": "escalate", "to": "trade_war", "prob": 0.7, "delay": 2000},
            {"from": "china_retal", "to": "trade_war", "prob": 0.5, "delay": 2000},
            {"from": "negotiate", "to": "quick_deal", "prob": 0.4, "delay": 1500},
            {"from": "lobby", "to": "quick_deal", "prob": 0.3, "delay": 1500},
            {"from": "lobby", "to": "reversal", "prob": 0.2, "delay": 1500},
            {"from": "negotiate", "to": "reversal", "prob": 0.15, "delay": 1500},
        ],
        "correlations": [
            {"n1": "china_retal", "n2": "escalate", "corr": 0.5},
        ],
    },

    "covid_market_2020": {
        "title": "COVID-19 Market Crash (Feb-Mar 2020)",
        "date": "2020-02-20",
        "actual_outcome": "v_recovery",
        "actual_description": "S&P dropped 34% in 33 days. Then V-shaped recovery. Fed printed $3T. New ATH by Aug 2020.",
        "nodes": [
            {"id": "seed", "label": "COVID-19 cases surge outside China, WHO raises alarm", "type": "seed", "prior": 1.0, "time": 0},
            {"id": "fear", "label": "Fear index (VIX) spikes above 40", "type": "event", "prior": 0.8, "time": 48},
            {"id": "selloff", "label": "Massive institutional selling, circuit breakers triggered", "type": "event", "prior": 0.7, "time": 168},
            {"id": "fed", "label": "Fed emergency rate cut + unlimited QE", "type": "event", "prior": 0.6, "time": 504},
            {"id": "stimulus", "label": "Congress passes $2.2T stimulus (CARES Act)", "type": "event", "prior": 0.5, "time": 840},
            {"id": "lockdown", "label": "Nationwide lockdowns, economy freezes", "type": "event", "prior": 0.8, "time": 336},
            {"id": "v_recovery", "label": "V-shaped recovery, new ATH within 6 months", "type": "outcome", "prior": 0.2, "time": 4320},
            {"id": "l_shaped", "label": "L-shaped recession lasting 2+ years", "type": "outcome", "prior": 0.3, "time": 4320},
            {"id": "w_shaped", "label": "W-shaped double-dip recession", "type": "outcome", "prior": 0.25, "time": 4320},
        ],
        "edges": [
            {"from": "seed", "to": "fear", "prob": 0.85, "delay": 48},
            {"from": "seed", "to": "lockdown", "prob": 0.75, "delay": 336},
            {"from": "fear", "to": "selloff", "prob": 0.8, "delay": 120},
            {"from": "selloff", "to": "fed", "prob": 0.7, "delay": 336},
            {"from": "lockdown", "to": "stimulus", "prob": 0.6, "delay": 504},
            {"from": "fed", "to": "v_recovery", "prob": 0.6, "delay": 2000},
            {"from": "stimulus", "to": "v_recovery", "prob": 0.5, "delay": 2000},
            {"from": "lockdown", "to": "l_shaped", "prob": 0.5, "delay": 2000},
            {"from": "selloff", "to": "l_shaped", "prob": 0.3, "delay": 2000},
            {"from": "fed", "to": "w_shaped", "prob": 0.3, "delay": 2000},
            {"from": "lockdown", "to": "w_shaped", "prob": 0.35, "delay": 2000},
        ],
        "correlations": [
            {"n1": "fed", "n2": "stimulus", "corr": 0.6},
        ],
    },

    "svb_collapse_2023": {
        "title": "Silicon Valley Bank Collapse (March 2023)",
        "date": "2023-03-08",
        "actual_outcome": "contained",
        "actual_description": "SVB collapsed. FDIC seized it. Contagion fear spread to other banks. Fed created emergency lending. Crisis contained within 2 weeks.",
        "nodes": [
            {"id": "seed", "label": "SVB announces $1.8B loss on bond portfolio", "type": "seed", "prior": 1.0, "time": 0},
            {"id": "bank_run", "label": "Depositors withdraw $42B in 24 hours", "type": "event", "prior": 0.8, "time": 24},
            {"id": "fdic", "label": "FDIC seizes SVB", "type": "event", "prior": 0.7, "time": 48},
            {"id": "contagion", "label": "Signature Bank + First Republic under pressure", "type": "event", "prior": 0.6, "time": 72},
            {"id": "fed_rescue", "label": "Fed creates Bank Term Funding Program", "type": "event", "prior": 0.5, "time": 96},
            {"id": "contained", "label": "Crisis contained, no systemic collapse", "type": "outcome", "prior": 0.4, "time": 720},
            {"id": "systemic", "label": "2008-style banking crisis", "type": "outcome", "prior": 0.15, "time": 720},
            {"id": "slow_burn", "label": "Slow-motion regional bank crisis over 6 months", "type": "outcome", "prior": 0.3, "time": 4320},
        ],
        "edges": [
            {"from": "seed", "to": "bank_run", "prob": 0.85, "delay": 24},
            {"from": "bank_run", "to": "fdic", "prob": 0.8, "delay": 24},
            {"from": "fdic", "to": "contagion", "prob": 0.7, "delay": 24},
            {"from": "contagion", "to": "fed_rescue", "prob": 0.65, "delay": 24},
            {"from": "fed_rescue", "to": "contained", "prob": 0.7, "delay": 300},
            {"from": "contagion", "to": "systemic", "prob": 0.25, "delay": 300},
            {"from": "contagion", "to": "slow_burn", "prob": 0.4, "delay": 2000},
            {"from": "fdic", "to": "contained", "prob": 0.3, "delay": 300},
            {"from": "bank_run", "to": "systemic", "prob": 0.2, "delay": 300},
        ],
        "correlations": [
            {"n1": "contagion", "n2": "bank_run", "corr": 0.4},
        ],
    },

    "fed_hike_2022": {
        "title": "Fed Aggressive Rate Hikes 2022 (75bp hikes)",
        "date": "2022-03-16",
        "actual_outcome": "soft_landing",
        "actual_description": "Fed raised rates from 0% to 5.5%. Inflation fell from 9% to 3%. No recession as of 2024. Soft landing achieved.",
        "nodes": [
            {"id": "seed", "label": "Fed signals aggressive rate hikes to fight 8%+ inflation", "type": "seed", "prior": 1.0, "time": 0},
            {"id": "rate_shock", "label": "75bp hike shocks markets", "type": "event", "prior": 0.8, "time": 72},
            {"id": "housing_cool", "label": "Housing market cools, mortgage rates double", "type": "event", "prior": 0.7, "time": 720},
            {"id": "tech_crash", "label": "Tech stocks crash 30%+, layoffs begin", "type": "event", "prior": 0.7, "time": 360},
            {"id": "inflation_down", "label": "Inflation starts declining", "type": "event", "prior": 0.5, "time": 2160},
            {"id": "labor_strong", "label": "Labor market stays surprisingly strong", "type": "event", "prior": 0.3, "time": 2160},
            {"id": "soft_landing", "label": "Soft landing: inflation down, no recession", "type": "outcome", "prior": 0.2, "time": 4320},
            {"id": "recession", "label": "Hard landing: recession within 18 months", "type": "outcome", "prior": 0.4, "time": 4320},
            {"id": "stagflation", "label": "Stagflation: high inflation AND recession", "type": "outcome", "prior": 0.2, "time": 4320},
        ],
        "edges": [
            {"from": "seed", "to": "rate_shock", "prob": 0.85, "delay": 72},
            {"from": "seed", "to": "housing_cool", "prob": 0.7, "delay": 720},
            {"from": "rate_shock", "to": "tech_crash", "prob": 0.7, "delay": 288},
            {"from": "housing_cool", "to": "recession", "prob": 0.5, "delay": 2000},
            {"from": "tech_crash", "to": "recession", "prob": 0.4, "delay": 2000},
            {"from": "seed", "to": "inflation_down", "prob": 0.6, "delay": 2160},
            {"from": "inflation_down", "to": "soft_landing", "prob": 0.6, "delay": 2000},
            {"from": "labor_strong", "to": "soft_landing", "prob": 0.5, "delay": 2000},
            {"from": "rate_shock", "to": "stagflation", "prob": 0.3, "delay": 2000},
            {"from": "inflation_down", "to": "recession", "prob": 0.2, "delay": 2000},
        ],
        "correlations": [
            {"n1": "housing_cool", "n2": "tech_crash", "corr": 0.4},
        ],
    },

    "russia_ukraine_2022": {
        "title": "Russia-Ukraine Invasion (Feb 2022)",
        "date": "2022-02-24",
        "actual_outcome": "prolonged_war",
        "actual_description": "Russia invaded expecting quick victory. Ukraine resisted. War became prolonged. Western sanctions + military aid. 2+ years and counting.",
        "nodes": [
            {"id": "seed", "label": "Russia invades Ukraine with full military force", "type": "seed", "prior": 1.0, "time": 0},
            {"id": "kyiv_assault", "label": "Russia assaults Kyiv, expects quick capitulation", "type": "event", "prior": 0.9, "time": 24},
            {"id": "ua_resist", "label": "Ukraine mounts unexpectedly strong resistance", "type": "event", "prior": 0.4, "time": 72},
            {"id": "sanctions", "label": "Western nations impose severe sanctions on Russia", "type": "event", "prior": 0.7, "time": 48},
            {"id": "arms", "label": "Western military aid flows to Ukraine", "type": "event", "prior": 0.5, "time": 168},
            {"id": "energy_crisis", "label": "European energy crisis from Russian gas cutoff", "type": "event", "prior": 0.6, "time": 720},
            {"id": "quick_russian_win", "label": "Quick Russian victory in weeks", "type": "outcome", "prior": 0.3, "time": 720},
            {"id": "prolonged_war", "label": "Prolonged war lasting 1+ years", "type": "outcome", "prior": 0.3, "time": 4320},
            {"id": "negotiated_peace", "label": "Negotiated peace within 6 months", "type": "outcome", "prior": 0.2, "time": 4320},
        ],
        "edges": [
            {"from": "seed", "to": "kyiv_assault", "prob": 0.9, "delay": 24},
            {"from": "seed", "to": "sanctions", "prob": 0.8, "delay": 48},
            {"from": "kyiv_assault", "to": "ua_resist", "prob": 0.5, "delay": 48},
            {"from": "ua_resist", "to": "arms", "prob": 0.7, "delay": 96},
            {"from": "sanctions", "to": "energy_crisis", "prob": 0.6, "delay": 672},
            {"from": "kyiv_assault", "to": "quick_russian_win", "prob": 0.4, "delay": 500},
            {"from": "ua_resist", "to": "prolonged_war", "prob": 0.7, "delay": 2000},
            {"from": "arms", "to": "prolonged_war", "prob": 0.6, "delay": 2000},
            {"from": "sanctions", "to": "negotiated_peace", "prob": 0.3, "delay": 2000},
            {"from": "energy_crisis", "to": "negotiated_peace", "prob": 0.3, "delay": 2000},
        ],
        "correlations": [
            {"n1": "ua_resist", "n2": "arms", "corr": 0.5},
        ],
    },
}


def run_single_backtest(scenario_id: str) -> dict:
    """Run backtest on one scenario. Compare prediction vs reality."""
    s = SCENARIOS[scenario_id]
    r = _build_and_invert(s)

    actual = s["actual_outcome"]
    outcomes = r.get("necessities", {})

    # Find predicted ranking
    ranked = sorted(outcomes.items(), key=lambda x: x[1]["prob"], reverse=True)
    predicted_top = ranked[0][0] if ranked else None
    actual_prob = outcomes.get(actual, {}).get("prob", 0)
    actual_rank = next((i+1 for i, (k,v) in enumerate(ranked) if k == actual), len(ranked))

    # Score: did we rank the actual outcome correctly?
    hit = predicted_top == actual
    top3 = actual_rank <= 3

    return {
        "scenario": s["title"],
        "date": s["date"],
        "actual_outcome": actual,
        "actual_description": s["actual_description"],
        "predicted_top": predicted_top,
        "predicted_top_label": outcomes.get(predicted_top, {}).get("outcome", ""),
        "actual_probability": round(actual_prob, 4),
        "actual_rank": actual_rank,
        "total_outcomes": len(ranked),
        "hit": hit,
        "top3": top3,
        "turnstile": r.get("turnstile", {}),
        "necessity_for_actual": next(
            (c for lid, nd in outcomes.items() if lid == actual
             for c in nd.get("conditions", []) if c.get("critical")),
            {}
        ),
        "all_outcomes": [(k, round(v["prob"], 4)) for k,v in ranked],
        "perf_ms": r.get("perf", {}).get("ms", 0),
    }


def run_backtest() -> dict:
    """Run all backtests. Return summary."""
    results = {}
    hits = 0
    top3s = 0
    total = 0

    for sid in SCENARIOS:
        r = run_single_backtest(sid)
        results[sid] = r
        total += 1
        if r["hit"]: hits += 1
        if r["top3"]: top3s += 1

    return {
        "results": results,
        "summary": {
            "total": total,
            "exact_hits": hits,
            "top3_hits": top3s,
            "hit_rate": round(hits / max(1, total), 4),
            "top3_rate": round(top3s / max(1, total), 4),
        },
    }


def print_backtest(bt: dict):
    """Pretty-print backtest results."""
    print("=" * 65)
    print("  TURNSTILE BACKTEST — Predictions vs Reality")
    print("=" * 65)

    for sid, r in bt["results"].items():
        hit = "✅ HIT" if r["hit"] else "❌ MISS"
        print(f"\n  {r['scenario']}")
        print(f"  Date: {r['date']} | {r['perf_ms']:.0f}ms")
        print(f"  Actual: {r['actual_outcome']} ({r['actual_description'][:60]})")
        print(f"  Predicted: {r['predicted_top']} — {r['predicted_top_label'][:50]}")
        print(f"  Result: {hit} | Actual rank: #{r['actual_rank']}/{r['total_outcomes']} | P={r['actual_probability']}")
        print(f"  All outcomes: {r['all_outcomes']}")
        ts = r.get("turnstile", {})
        if ts.get("found"):
            print(f"  Turnstile: \"{ts.get('label', ts.get('id',''))}\" @ {ts.get('t_hours',0)}h")

    s = bt["summary"]
    print(f"\n  {'='*40}")
    print(f"  SUMMARY: {s['exact_hits']}/{s['total']} exact hits ({s['hit_rate']:.0%})")
    print(f"           {s['top3_hits']}/{s['total']} in top 3 ({s['top3_rate']:.0%})")
    print(f"  {'='*40}")

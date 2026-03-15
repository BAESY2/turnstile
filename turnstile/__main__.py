"""TURNSTILE CLI — Command-line interface.

Usage:
    python -m turnstile analyze "Trump announces 60% tariffs on China"
    python -m turnstile demo tariff
    python -m turnstile explain
    python -m turnstile bench 1000
"""

import sys
import json
import time
import numpy as np


def demo_tariff():
    """Built-in tariff scenario demo."""
    from .engine import Builder, analyze
    b = Builder()
    b.node("seed","Trump announces 60% tariffs on all Chinese imports","seed",1.0,0)
    b.node("mkt","Global markets react — volatility spikes, safe havens rally","event",0.95,2)
    b.node("china","Chinese government formulates official response","event",0.90,48)
    b.node("panic","Panic selling — S&P drops 3-5%, VIX above 30","event",0.6,4)
    b.node("dip","Institutional investors buy the dip","event",0.3,6)
    b.node("retal","China retaliates with matching tariffs on US agriculture + tech","event",0.5,72)
    b.node("nego","China signals willingness to negotiate, proposes summit","event",0.4,72)
    b.node("supply","Multinationals begin supply chain contingency planning","event",0.7,96)
    b.node("lobby","US business lobby pressures Congress for exemptions","event",0.6,120)
    b.node("eu","EU announces position — mediator or side-picker","event",0.5,168)
    b.node("o_war","OUTCOME: Full trade war — tit-for-tat escalation 6+ months","outcome",0.35,720)
    b.node("o_deal","OUTCOME: Negotiated deal — tariffs reduced to 25-35%","outcome",0.40,720)
    b.node("o_decouple","OUTCOME: Accelerated US-China economic decoupling","outcome",0.15,1440)
    b.node("o_crash","OUTCOME: Market crash >10% forces policy reversal","outcome",0.10,360)

    b.edge("seed","mkt",0.95,2).edge("seed","china",0.90,48).edge("seed","supply",0.70,96)
    b.edge("mkt","panic",0.60,2).edge("mkt","dip",0.30,4).edge("mkt","lobby",0.40,120)
    b.edge("china","retal",0.50,24).edge("china","nego",0.40,24).edge("china","eu",0.30,120)
    b.edge("supply","eu",0.20,72)
    b.edge("retal","o_war",0.70,168,"and").edge("panic","o_war",0.40,168,"and")
    b.edge("nego","o_deal",0.75,168).edge("dip","o_deal",0.40,168).edge("lobby","o_deal",0.30,200)
    b.edge("retal","o_decouple",0.30,500).edge("supply","o_decouple",0.40,500).edge("eu","o_decouple",0.20,500)
    b.edge("panic","o_crash",0.50,168).edge("retal","o_crash",0.30,168)
    b.corr("panic","retal",0.4).corr("nego","lobby",0.3)

    g = b.build(); return g, analyze(g)


def demo_btc():
    """Bitcoin halving scenario."""
    from .engine import Builder, analyze
    b = Builder()
    b.node("seed","Bitcoin halving event reduces block reward by 50%","seed",1.0,0)
    b.node("scarcity","Reduced new BTC supply hits market","event",0.99,1)
    b.node("miner_stress","Small miners become unprofitable, some exit","event",0.75,168)
    b.node("hashrate_drop","Network hashrate temporarily drops 10-20%","event",0.60,336)
    b.node("media","Media narrative: 'digital gold scarcity' intensifies","event",0.80,720)
    b.node("retail","Retail FOMO buying wave begins","event",0.55,1440)
    b.node("whale","Whales accumulate during miner capitulation","event",0.65,504)
    b.node("etf","Spot ETF inflows accelerate","event",0.70,720)
    b.node("o_moon","OUTCOME: BTC reaches new ATH within 18 months","outcome",0.45,8760)
    b.node("o_flat","OUTCOME: Price stays range-bound, halving priced in","outcome",0.35,8760)
    b.node("o_dump","OUTCOME: Sell-the-news event, 30%+ correction","outcome",0.20,2160)

    b.edge("seed","scarcity",0.99,1).edge("seed","miner_stress",0.75,168).edge("seed","media",0.60,720)
    b.edge("scarcity","whale",0.50,504).edge("miner_stress","hashrate_drop",0.70,168)
    b.edge("hashrate_drop","media",0.30,200)
    b.edge("media","retail",0.60,720).edge("media","etf",0.40,360)
    b.edge("whale","o_moon",0.60,4000).edge("retail","o_moon",0.50,4000).edge("etf","o_moon",0.55,4000)
    b.edge("whale","o_flat",0.30,4000).edge("etf","o_flat",0.40,4000)
    b.edge("retail","o_dump",0.35,1000).edge("miner_stress","o_dump",0.25,1000)
    b.corr("retail","etf",0.5)

    g = b.build(); return g, analyze(g)


def print_result(r: dict, g=None):
    """Pretty-print analysis result."""
    p = r["perf"]
    print(f"\n{'='*65}")
    print(f"  TURNSTILE v{r['version']} — {p['mode'].upper()} mode")
    print(f"  {p['nodes']} nodes | {p['edges']} edges | {p['ms']:.1f}ms | {r['llm_calls']} LLM")
    print(f"{'='*65}")

    ts = r["turnstile"]
    if ts.get("found"):
        print(f"\n  ⚡ TURNSTILE (point of no return):")
        print(f"     {ts['id']}: \"{ts['label']}\"")
        print(f"     Time: {ts['t_hours']}h | H_fwd={ts['fwd_H']:.4f} H_inv={ts['inv_H']:.4f} | ∇H={ts['gradient']:.6f}")

    for lid, nd in r["necessities"].items():
        print(f"\n  📊 {lid}: {nd['outcome']} (P={nd['prob']:.4f})")
        for c in nd["conditions"][:5]:
            tr = " [trivial]" if c["trivial"] else ""
            cr = " ★ CRITICAL" if c["critical"] else ""
            bar_len = int(c["necessity"] * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"     [{bar}] {c['necessity']:.3f} {c['label'][:35]}{cr}{tr}")

    if r.get("sensitivity"):
        print(f"\n  🔬 SENSITIVITY (most impactful edges):")
        for lid, sl in r["sensitivity"].items():
            if sl:
                print(f"     {lid}: {sl[0]['edge']} = {sl[0]['sensitivity']:.4f}")

    if r.get("do_calculus"):
        print(f"\n  🧪 CAUSAL POWER (do-calculus):")
        for d in r["do_calculus"][:5]:
            print(f"     do({d['id']}): power={d['power']:.4f} — \"{d.get('label','')}\"")

    if r.get("robustness"):
        rob = r["robustness"]
        print(f"\n  🛡️ ROBUSTNESS: {rob.get('flips','?')}/{rob.get('total','?')} edges to flip prediction")

    if r.get("kl") and r["kl"].get("kl"):
        kl = r["kl"]
        level = "LOW" if kl["kl"] < 0.5 else "MODERATE" if kl["kl"] < 2.0 else "HIGH"
        print(f"  📐 KL DIVERGENCE: {kl['kl']:.4f} ({level}) — {kl['n']} nodes compared")

    if r.get("critical_paths"):
        print(f"\n  🛣️ CRITICAL PATHS:")
        for lid, cp in r["critical_paths"].items():
            if cp.get("found"):
                chain = " → ".join(s["id"] for s in cp["path"])
                print(f"     {lid}: {chain} (P={cp['prob']:.4f})")

    if r.get("counterfactuals"):
        print(f"\n  🔄 COUNTERFACTUALS:")
        for cf in r["counterfactuals"][:3]:
            cr = " ★ STRUCTURAL" if cf.get("critical") else ""
            print(f"     Remove \"{cf.get('label',cf['removed'])}\" → impact={cf['impact']:.4f}{cr}")

    if r.get("monte_carlo") and r["monte_carlo"].get("nodes"):
        mc = r["monte_carlo"]
        print(f"\n  🎲 MONTE CARLO ({mc['n']} simulations):")
        # Show top 3 most uncertain
        nodes_sorted = sorted(mc["nodes"].items(), key=lambda x: x[1]["std"], reverse=True)
        for k, v in nodes_sorted[:5]:
            if v["std"] > 0.001:
                print(f"     {k}: {v['mean']:.3f} ± {v['std']:.3f}  CI95=[{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]")

    # Print entropy report if graph available
    if g is not None:
        from .tenet import entropy_report, print_entropy_report
        er = entropy_report(g)
        print()
        print_entropy_report(er)


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print("""
TURNSTILE — Bayesian Temporal Inversion Engine

Commands:
  turnstile demo tariff      Run tariff scenario demo
  turnstile demo btc         Run Bitcoin halving demo
  turnstile backtest         Run backtests against real 2024 events
  turnstile explain          Explain entropy inversion (no physics errors)
  turnstile bench N          Benchmark with N-node random graph

Options:
  --mode lite|standard|full  Analysis depth (default: auto)
  --no-mc                    Skip Monte Carlo
  --json                     Output raw JSON

MiroFish predicts what happens.
Turnstile proves why it must.
""")
        return

    cmd = args[0]

    if cmd == "explain":
        from .tenet import explain_inversion
        print(explain_inversion())
        return

    if cmd == "backtest":
        from .backtest import run_backtest, print_backtest
        bt = run_backtest()
        print_backtest(bt)
        return

    if cmd == "demo":
        scenario = args[1] if len(args) > 1 else "tariff"
        if scenario == "tariff":
            g, r = demo_tariff()
        elif scenario in ("btc", "bitcoin"):
            g, r = demo_btc()
        else:
            print(f"Unknown demo: {scenario}. Available: tariff, btc")
            return

        if "--json" in args:
            print(json.dumps(r, indent=2))
        else:
            print_result(r, g)
            # Advanced analysis
            if "--full" in args or "--advanced" in args:
                from .extra import run_advanced
                adv = run_advanced(g, r)
                print("\n" + adv["timeline"])
                print("\n=== SURPRISES ===")
                for s in adv["surprises"][:5]:
                    if s["type"] != "aligned":
                        print(f'  {s["type"]:>10s} {s["id"]}: gap={s["gap"]:+.3f} — {s["interpretation"][:50]}')
                print("\n=== CHAIN REACTIONS ===")
                for cr in adv["chain_reactions"][:3]:
                    print(f'  do({cr["source"]}+0.2): {cr["nodes_affected"]} nodes affected')
                print("\n=== MERMAID ===")
                print(adv["mermaid"][:500])
        return

    if cmd == "bench":
        n = int(args[1]) if len(args) > 1 else 1000
        from .engine import Builder, analyze
        np.random.seed(42)
        b = Builder()
        b.node("seed","Seed","seed",1.0,0)
        d = min(0.3, 5.0/n)
        ids = ["seed"]
        for i in range(1,n-3):
            nid = f"e{i}"; ids.append(nid)
            b.node(nid,f"Event {i}","event",np.random.uniform(0.2,0.9),np.random.uniform(1,500))
        for i in range(3):
            nid = f"o{i}"; ids.append(nid)
            b.node(nid,f"Outcome {i}","outcome",np.random.uniform(0.1,0.5),np.random.uniform(500,1000))
        for i in range(len(ids)):
            for j in range(i+1,len(ids)):
                if np.random.random() < d:
                    b.edge(ids[i],ids[j],np.random.uniform(0.1,0.9),np.random.uniform(1,200))
        for j in range(1,len(ids)):
            if not any(e[1]==ids[j] for e in b._e):
                b.edge(ids[np.random.randint(0,j)],ids[j],np.random.uniform(0.2,0.8),np.random.uniform(1,100))

        mode = None
        for a in args:
            if a.startswith("--mode="): mode = a.split("=")[1]

        g = b.build()
        print(f"Benchmarking {n} nodes, {g.edge_count} edges...")
        t0 = time.perf_counter()
        r = analyze(g, mc_on="--no-mc" not in args, mode=mode)
        ms = (time.perf_counter()-t0)*1000
        print(f"Done: {ms:.0f}ms ({ms/n:.2f}ms/node) mode={r['perf']['mode']}")
        return

    print(f"Unknown command: {cmd}. Run 'turnstile help'")


if __name__ == "__main__":
    main()

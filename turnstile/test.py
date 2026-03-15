"""TURNSTILE Quick Test — Run this to verify everything works.

    python -m turnstile.test
"""

from .engine import Builder, analyze
import json


def trump_tariff_dag():
    """Trump 60% tariff scenario — the classic demo."""
    b = Builder()
    b.node("seed", "Trump announces 60% tariffs on all Chinese imports", "seed", 1.0, 0)
    b.node("v1", "Global markets react — volatility spikes", "event", 0.95, 2)
    b.node("v2", "China formulates official response", "event", 0.90, 48)
    b.node("n1a", "Panic selling — S&P drops 3-5%", "event", 0.60, 4)
    b.node("n1b", "Institutional investors buy the dip", "event", 0.30, 6)
    b.node("n2a", "China retaliates with matching tariffs", "event", 0.50, 72)
    b.node("n2b", "China signals willingness to negotiate", "event", 0.40, 72)
    b.node("n3a", "Supply chain reshoring accelerates", "event", 0.30, 168)
    b.node("o1", "Full trade war — 6+ month escalation", "outcome", 0.35, 720)
    b.node("o2", "Negotiated deal — tariffs reduced to 25-35%", "outcome", 0.40, 720)
    b.node("o3", "Market crash forces policy reversal", "outcome", 0.10, 360)

    b.edge("seed", "v1", 0.95, 2)
    b.edge("seed", "v2", 0.90, 48)
    b.edge("v1", "n1a", 0.60, 2)
    b.edge("v1", "n1b", 0.30, 4)
    b.edge("v2", "n2a", 0.50, 24)
    b.edge("v2", "n2b", 0.40, 24)
    b.edge("v1", "n3a", 0.30, 72)
    b.edge("n2a", "o1", 0.70, 168, "and")
    b.edge("n1a", "o1", 0.40, 168, "and")
    b.edge("n2b", "o2", 0.75, 168)
    b.edge("n1b", "o2", 0.50, 168)
    b.edge("n1a", "o3", 0.30, 72)
    b.edge("n2a", "o3", 0.20, 72)
    b.edge("n3a", "o1", 0.25, 120)

    b.corr("n1a", "n2a", 0.4)
    return b.build()


def run():
    g = trump_tariff_dag()
    r = analyze(g, mc_on=True, mc_n=100)

    print("=" * 60)
    print("  TURNSTILE — Bayesian Temporal Inversion")
    print("=" * 60)
    print(f"  {r['perf']['nodes']} nodes, {r['perf']['edges']} edges")
    print(f"  Completed in {r['perf']['ms']}ms | LLM calls: {r['llm_calls']}")

    ts = r["turnstile"]
    if ts["found"]:
        print(f"\n  ⚡ TURNSTILE: {ts['label']}")
        print(f"     at {ts['t_hours']}h | gradient={ts['gradient']} | necessity={ts['necessity']}")

    print(f"\n  NECESSITIES:")
    for oid, nd in r["necessities"].items():
        print(f"    {nd['outcome']} (prob={nd['prob']})")
        for c in nd["conditions"]:
            cr = " ★" if c.get("critical") else ""
            tr = " [triv]" if c.get("trivial") else ""
            print(f"      {c['necessity']:.3f} {c['label'][:45]}{cr}{tr}")

    print(f"\n  SENSITIVITY (top 3 per outcome):")
    for oid, sl in r["sensitivity"].items():
        print(f"    {oid}:")
        for s in sl[:3]:
            print(f"      {s['edge']:20s} sens={s['sensitivity']:.4f}")

    if r["do_calculus"]:
        print(f"\n  CAUSAL POWER (do-calculus):")
        for d in r["do_calculus"][:5]:
            print(f"    {d['id']:10s} {d['label'][:30]:30s} power={d['power']:.4f}")

    rob = r["robustness"]
    print(f"\n  ROBUSTNESS: {rob['flips']}/{rob['total']} edges to flip ({rob['robustness']:.0%})")

    kl_r = r["kl"]
    print(f"  KL DIVERGENCE: {kl_r['kl']:.4f} ({kl_r['n']} nodes)")

    if r["monte_carlo"]:
        print(f"\n  MONTE CARLO ({r['monte_carlo']['n']} sims):")
        for nid, mc in list(r["monte_carlo"]["nodes"].items())[:5]:
            print(f"    {nid:10s} mean={mc['mean']:.3f}±{mc['std']:.3f} ci={mc['ci95']}")

    if r["critical_paths"]:
        print(f"\n  CRITICAL PATHS:")
        for oid, cp in r["critical_paths"].items():
            if cp.get("found"):
                chain = " → ".join(n["id"] for n in cp["path"])
                print(f"    {oid}: {chain} (prob={cp['prob']})")

    print(f"\n  {'='*60}")
    print(f"  Engine: {r['engine']} v{r['version']} | {r['perf']['ms']}ms | 0 LLM calls")


if __name__ == "__main__":
    run()

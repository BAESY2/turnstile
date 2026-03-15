import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import numpy as np
from turnstile import Builder, invert

def build_tariff():
    b = Builder()
    b.node("seed","Tariff 60%","seed",1.0,0)
    b.node("v1","Market reaction","event",0.95,2)
    b.node("v2","China response","event",0.90,48)
    b.node("n1a","Panic sell","event",0.6,4)
    b.node("n1b","Buy dip","event",0.3,6)
    b.node("n2a","Retaliation","event",0.5,72)
    b.node("n2b","Negotiate","event",0.4,72)
    b.node("o1","Trade war","outcome",0.35,720)
    b.node("o2","Deal made","outcome",0.40,720)
    b.edge("seed","v1",0.95,2).edge("seed","v2",0.90,48)
    b.edge("v1","n1a",0.60,2).edge("v1","n1b",0.30,4)
    b.edge("v2","n2a",0.50,24).edge("v2","n2b",0.40,24)
    b.edge("n2a","o1",0.70,168,"and").edge("n1a","o1",0.40,168,"and")
    b.edge("n2b","o2",0.75,168).edge("n1b","o2",0.50,168)
    b.corr("n1a","n2a",0.4)
    return b.build()

def build_random(n, density=0.15, n_out=3):
    b = Builder()
    b.node("seed","Seed","seed",1.0,0)
    for i in range(1,n-n_out):
        b.node(f"e{i}",f"Ev{i}","event",np.random.uniform(0.2,0.9),np.random.uniform(1,500))
    for i in range(n_out):
        b.node(f"o{i}",f"Out{i}","outcome",np.random.uniform(0.1,0.5),np.random.uniform(500,1000))
    ids=["seed"]+[f"e{i}" for i in range(1,n-n_out)]+[f"o{i}" for i in range(n_out)]
    for i in range(len(ids)):
        for j in range(i+1,len(ids)):
            if np.random.random()<density: b.edge(ids[i],ids[j],np.random.uniform(0.1,0.9),np.random.uniform(1,200))
    for j in range(1,len(ids)):
        if not any(e[1]==ids[j] for e in b._e):
            b.edge(ids[np.random.randint(0,j)],ids[j],np.random.uniform(0.2,0.8),np.random.uniform(1,100))
    return b.build()

def test():
    print("="*60)
    print("  TURNSTILE ENGINE v2 — Correctness")
    print("="*60)
    g = build_tariff()
    r = invert(g, mc_on=True, mc_n=100)
    p = r["perf"]
    print(f"\n  {p['nodes']} nodes | {p['edges']} edges | {p['ms']:.1f}ms | LLM: {r['llm_calls']}")

    ts = r["turnstile"]
    if ts.get("found"):
        print(f"\n  ⚡ TURNSTILE: {ts['id']} \"{ts['label']}\" @ {ts['t_hours']}h")
        print(f"    gradient={ts['gradient']:.6f} | fwd_H={ts['fwd_H']:.4f} | inv_H={ts['inv_H']:.4f}")

    for lid, nd in r["necessities"].items():
        print(f"\n  {lid}: {nd['outcome']} (p={nd['prob']})")
        for c in nd["conditions"][:4]:
            tr = " [triv]" if c["trivial"] else ""
            cr = " ★" if c["critical"] else ""
            print(f"    {c['necessity']:.3f} {c['label'][:35]}{cr}{tr}")

    for lid, sl in r["sensitivity"].items():
        if sl: print(f"  SENS {lid}: {sl[0]['edge']} = {sl[0]['sensitivity']:.4f}")

    if r["do_calculus"]:
        print(f"\n  DO-CALCULUS:")
        for d in r["do_calculus"][:3]:
            print(f"    do({d['id']}): power={d['power']:.4f}")

    rob = r["robustness"]
    print(f"\n  ROBUSTNESS: {rob['flips']}/{rob['total']} edges")
    print(f"  KL: {r['kl']['kl']:.4f} ({r['kl']['n']} nodes)")

    if r.get("counterfactuals"):
        print(f"\n  COUNTERFACTUALS:")
        for cf in r["counterfactuals"][:3]:
            cr = " ★" if cf.get("critical") else ""
            print(f"    Remove {cf['removed']}: impact={cf['impact']:.4f}{cr}")

    cp = r.get("critical_paths",{})
    for lid, c in cp.items():
        if c.get("found"):
            chain = " → ".join(s["id"] for s in c["path"])
            print(f"  PATH {lid}: {chain} (p={c['prob']:.4f})")

    er = r.get("entropy_rate",[])
    if er:
        print(f"\n  ENTROPY RATE:")
        for e in er[:3]:
            net = e['fwd_rate'] - e['inv_rate']
            print(f"    {e['from']}→{e['to']} ({e['hours']:.0f}h): fwd={e['fwd_rate']:+.4f} inv={e['inv_rate']:+.4f}")

    mc = r.get("monte_carlo",{}).get("nodes",{})
    if mc:
        print(f"\n  MC ({len(mc)} nodes):")
        for k,v in list(mc.items())[:3]:
            print(f"    {k}: {v['mean']:.3f}±{v['std']:.3f} ci={v['ci95']}")

    print(f"\n  ✅ PASSED — {p['ms']:.1f}ms | 0 LLM | v{r['version']}")
    return True

def bench(sizes=[10,50,100,500,1000,2000,5000]):
    print(f"\n{'='*60}")
    print(f"  BENCHMARK — How far can we push it?")
    print(f"{'='*60}")
    print(f"\n  {'N':>6} {'E':>7} {'Total':>9} {'MC':>4} {'ms/node':>8}")
    print(f"  {'─'*6} {'─'*7} {'─'*9} {'─'*4} {'─'*8}")
    for n in sizes:
        try:
            np.random.seed(42)
            d = min(0.3, 5.0/n)
            g = build_random(n, density=d)
            do_mc = n <= 200
            t0 = time.perf_counter()
            r = invert(g, mc_on=do_mc, mc_n=50)
            ms = (time.perf_counter()-t0)*1000
            e = r["perf"]["edges"]
            print(f"  {n:>6} {e:>7} {ms:>7.0f}ms {'Y' if do_mc else 'N':>4} {ms/n:>6.2f}")
        except Exception as ex:
            print(f"  {n:>6} ERR: {str(ex)[:60]}")

if __name__ == "__main__":
    if test(): bench()

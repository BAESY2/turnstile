"""TURNSTILE Benchmark Suite — Prove performance at every scale.

Run: python -m turnstile.bench
"""

import numpy as np
import time
import sys

from .engine import Graph, Builder, analyze, forward, invert_edges, entropy, monte_carlo


def random_dag(n_nodes: int, edge_density: float = 0.15, n_outcomes: int = 3, seed: int = 42) -> Graph:
    """Generate a random causal DAG with given node count.

    Structure: 1 seed → layers of events → N outcomes.
    Edges only go forward (no cycles guaranteed by layer structure).
    """
    rng = np.random.RandomState(seed)
    b = Builder()

    # Seed node
    b.node("seed", "Seed Event", "seed", 1.0, 0.0)

    # Layers
    n_events = n_nodes - 1 - n_outcomes
    if n_events < 1:
        n_events = 1
    n_layers = max(2, int(np.sqrt(n_events)))
    per_layer = max(1, n_events // n_layers)

    event_ids = []
    for layer in range(n_layers):
        for j in range(per_layer):
            idx = layer * per_layer + j
            if idx >= n_events:
                break
            eid = f"e{idx}"
            b.node(eid, f"Event_{idx}", "event",
                   rng.uniform(0.2, 0.9),
                   float(layer * 24 + rng.uniform(0, 12)))
            event_ids.append(eid)

    # Outcomes
    outcome_ids = []
    for i in range(n_outcomes):
        oid = f"o{i}"
        b.node(oid, f"Outcome_{i}", "outcome",
               rng.uniform(0.1, 0.5),
               float(n_layers * 24 + 48))
        outcome_ids.append(oid)

    # Edges: seed → first layer
    first_layer = event_ids[:per_layer]
    for eid in first_layer:
        b.edge("seed", eid, rng.uniform(0.5, 0.95), rng.uniform(1, 24))

    # Edges: between layers (forward only)
    for layer in range(n_layers - 1):
        src_start = layer * per_layer
        src_end = min(src_start + per_layer, len(event_ids))
        tgt_start = (layer + 1) * per_layer
        tgt_end = min(tgt_start + per_layer, len(event_ids))

        for si in range(src_start, src_end):
            for ti in range(tgt_start, tgt_end):
                if rng.random() < edge_density:
                    b.edge(event_ids[si], event_ids[ti],
                           rng.uniform(0.1, 0.8), rng.uniform(6, 48))

        # Ensure at least 1 edge per target node
        for ti in range(tgt_start, tgt_end):
            si = rng.randint(src_start, max(src_start+1, src_end))
            b.edge(event_ids[si], event_ids[ti],
                   rng.uniform(0.3, 0.7), rng.uniform(6, 48))

    # Edges: last layer → outcomes
    last_start = (n_layers - 1) * per_layer
    last_end = min(last_start + per_layer, len(event_ids))
    for oid in outcome_ids:
        n_parents = rng.randint(1, max(2, min(5, last_end - last_start + 1)))
        parents = rng.choice(range(last_start, max(last_start+1, last_end)),
                            min(n_parents, max(1, last_end-last_start)), replace=False)
        for pi in parents:
            gate = "and" if rng.random() < 0.2 else "or"
            b.edge(event_ids[pi], oid, rng.uniform(0.2, 0.7), rng.uniform(24, 168), gate)

    # Some cross-layer skip connections
    n_skips = max(1, int(len(event_ids) * edge_density * 0.3))
    for _ in range(n_skips):
        si = rng.randint(0, max(1, len(event_ids) - 2))
        ti = rng.randint(si + 1, len(event_ids))
        b.edge(event_ids[si], event_ids[ti], rng.uniform(0.1, 0.4), rng.uniform(12, 72))

    return b.build()


def bench_one(n_nodes: int, mc_on: bool = True, mc_n: int = 100) -> dict:
    """Benchmark at a specific node count."""
    g = random_dag(n_nodes)
    t0 = time.perf_counter()
    result = analyze(g, mc_on=mc_on, mc_n=mc_n)
    total_ms = (time.perf_counter() - t0) * 1000

    return {
        "nodes": n_nodes,
        "edges": g.edge_count,
        "total_ms": round(total_ms, 2),
        "engine_ms": result["perf"]["ms"],
        "turnstile_found": result["turnstile"]["found"],
        "n_outcomes": len(g.outcomes),
        "mc_sims": mc_n if mc_on else 0,
    }


def bench_core_only(n_nodes: int) -> dict:
    """Benchmark math core only (no MC, no sensitivity) — raw speed."""
    g = random_dag(n_nodes)
    t0 = time.perf_counter()
    forward(g)
    t1 = time.perf_counter()
    invert_edges(g)
    t2 = time.perf_counter()
    entropy(g)
    t3 = time.perf_counter()

    return {
        "nodes": n_nodes,
        "edges": g.edge_count,
        "forward_ms": round((t1-t0)*1000, 3),
        "invert_ms": round((t2-t1)*1000, 3),
        "entropy_ms": round((t3-t2)*1000, 3),
        "total_core_ms": round((t3-t0)*1000, 3),
    }


def run_full_bench():
    """Run complete benchmark suite."""
    print("=" * 70)
    print("  TURNSTILE BENCHMARK SUITE")
    print("  Bayesian Temporal Inversion Engine")
    print("=" * 70)

    # Core speed test
    print("\n── CORE SPEED (forward + invert + entropy only) ──")
    print(f"  {'Nodes':>8} {'Edges':>8} {'Forward':>10} {'Invert':>10} {'Entropy':>10} {'Total':>10}")
    print(f"  {'─'*8} {'─'*8} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    for n in [10, 50, 100, 250, 500, 1000, 2500, 5000]:
        try:
            r = bench_core_only(n)
            print(f"  {r['nodes']:>8} {r['edges']:>8} {r['forward_ms']:>9.3f}ms {r['invert_ms']:>9.3f}ms {r['entropy_ms']:>9.3f}ms {r['total_core_ms']:>9.3f}ms")
            sys.stdout.flush()
        except Exception as e:
            print(f"  {n:>8} FAILED: {e}")
            break

    # Full analysis (with MC)
    print("\n── FULL ANALYSIS (core + MC100 + sensitivity + do-calculus) ──")
    print(f"  {'Nodes':>8} {'Edges':>8} {'Total':>12} {'Turnstile':>10} {'MC sims':>8}")
    print(f"  {'─'*8} {'─'*8} {'─'*12} {'─'*10} {'─'*8}")

    for n in [10, 50, 100, 250, 500, 1000]:
        try:
            mc_n = 100 if n <= 500 else 50
            r = bench_one(n, mc_on=True, mc_n=mc_n)
            ts = "✓" if r["turnstile_found"] else "✗"
            print(f"  {r['nodes']:>8} {r['edges']:>8} {r['total_ms']:>10.2f}ms {ts:>10} {r['mc_sims']:>8}")
            sys.stdout.flush()
        except Exception as e:
            print(f"  {n:>8} FAILED: {e}")
            break

    # No MC (fast mode)
    print("\n── FAST MODE (no Monte Carlo) ──")
    for n in [10, 100, 1000, 5000, 10000]:
        try:
            r = bench_one(n, mc_on=False)
            print(f"  {r['nodes']:>8} nodes, {r['edges']:>8} edges → {r['total_ms']:>10.2f}ms")
            sys.stdout.flush()
        except Exception as e:
            print(f"  {n:>8} FAILED: {e}")
            break

    print("\n" + "=" * 70)
    print("  Engine: turnstile v1.0.0 | LLM calls: 0 | Pure numpy")
    print("=" * 70)


if __name__ == "__main__":
    run_full_bench()

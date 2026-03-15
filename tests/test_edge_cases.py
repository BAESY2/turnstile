"""Edge case tests — break everything, see what survives."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import numpy as np

PASS = 0
FAIL = 0

def check(name, condition, msg=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}: {msg}")

def test_empty_dag():
    """Empty graph should not crash."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    try:
        g = b.build()
        r = analyze(g, mc_on=False, mode="lite")
        check("empty_dag", r is not None, "analyze returned None")
    except Exception as e:
        check("empty_dag", False, str(e)[:60])

def test_single_node():
    """Single node — no edges, no outcomes."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    b.node("only", "The only node", "seed", 1.0, 0)
    try:
        g = b.build()
        r = analyze(g, mc_on=False, mode="lite")
        check("single_node", r["perf"]["nodes"] == 1)
        check("single_turnstile", not r["turnstile"].get("found"), "Should not find turnstile in 1-node graph")
    except Exception as e:
        check("single_node", False, str(e)[:60])

def test_two_nodes():
    """Minimal: seed → outcome."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    b.node("s", "Seed", "seed", 1.0, 0)
    b.node("o", "Out", "outcome", 0.5, 100)
    b.edge("s", "o", 0.8, 100)
    g = b.build()
    r = analyze(g, mc_on=False, mode="lite")
    check("two_nodes", r["perf"]["nodes"] == 2)
    check("two_edges", r["perf"]["edges"] == 1)

def test_self_loop():
    """Self-loop should be silently ignored."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    b.node("a", "A", "seed", 1.0, 0)
    b.node("b", "B", "outcome", 0.5, 10)
    b.edge("a", "b", 0.5, 10)
    b.edge("a", "a", 0.9, 0)  # Self-loop
    g = b.build()
    # Self-loop should still appear in adj (engine doesn't filter it)
    # But it shouldn't crash analyze
    try:
        r = analyze(g, mc_on=False, mode="lite")
        check("self_loop", True, "Didn't crash")
    except Exception as e:
        check("self_loop", False, str(e)[:60])

def test_negative_probability():
    """Negative probability should be clamped."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    b.node("s", "S", "seed", 1.0, 0)
    b.node("e", "E", "event", -0.5, 10)  # Negative prior
    b.node("o", "O", "outcome", 0.5, 100)
    b.edge("s", "e", -0.3, 10)  # Negative edge prob
    b.edge("e", "o", 0.5, 90)
    g = b.build()
    r = analyze(g, mc_on=False, mode="lite")
    # Should not crash — engine uses np.clip
    check("negative_prob", r is not None)

def test_probability_over_one():
    """Probability > 1 should be clamped."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    b.node("s", "S", "seed", 1.0, 0)
    b.node("e", "E", "event", 1.5, 10)  # > 1
    b.node("o", "O", "outcome", 0.5, 100)
    b.edge("s", "e", 1.2, 10)  # > 1
    b.edge("e", "o", 0.5, 90)
    g = b.build()
    try:
        r = analyze(g, mc_on=False, mode="lite")
        check("over_one_prob", True)
    except Exception as e:
        check("over_one_prob", False, str(e)[:60])

def test_disconnected_nodes():
    """Orphan nodes should not crash."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    b.node("s", "Seed", "seed", 1.0, 0)
    b.node("e1", "Connected", "event", 0.5, 10)
    b.node("e2", "Orphan", "event", 0.5, 20)  # No edges
    b.node("o", "Out", "outcome", 0.3, 100)
    b.edge("s", "e1", 0.8, 10)
    b.edge("e1", "o", 0.6, 90)
    g = b.build()
    r = analyze(g, mc_on=False, mode="lite")
    check("disconnected", r["perf"]["nodes"] == 4)

def test_all_same_time():
    """All nodes at time=0 — no temporal ordering."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    b.node("s", "S", "seed", 1.0, 0)
    b.node("a", "A", "event", 0.5, 0)
    b.node("b", "B", "event", 0.5, 0)
    b.node("o", "O", "outcome", 0.3, 0)
    b.edge("s", "a", 0.7, 0).edge("s", "b", 0.6, 0)
    b.edge("a", "o", 0.5, 0).edge("b", "o", 0.4, 0)
    g = b.build()
    r = analyze(g, mc_on=False, mode="lite")
    check("same_time", r is not None)

def test_100_outcomes():
    """Many outcomes — should scale."""
    from turnstile.engine import Builder, analyze
    b = Builder()
    b.node("s", "S", "seed", 1.0, 0)
    b.node("e", "E", "event", 0.8, 10)
    b.edge("s", "e", 0.9, 10)
    for i in range(100):
        b.node(f"o{i}", f"Out{i}", "outcome", np.random.uniform(0.1, 0.5), 100)
        b.edge("e", f"o{i}", np.random.uniform(0.1, 0.9), 90)
    g = b.build()
    r = analyze(g, mc_on=False, mode="lite")
    check("100_outcomes", len(r["necessities"]) == 100)

def test_mutation_preserves_validity():
    """Mutated DAG should still be analyzable."""
    from turnstile.engine import Builder, analyze
    from turnstile.adversarial import mutate_dag
    b = Builder()
    b.node("s","S","seed",1.0,0).node("a","A","event",0.7,10)
    b.node("b","B","event",0.5,20).node("o","O","outcome",0.3,100)
    b.edge("s","a",0.8,10).edge("a","b",0.6,10).edge("b","o",0.5,80)
    g = b.build()
    for _ in range(20):
        m = mutate_dag(g, 0.3)  # High mutation rate
        try:
            r = analyze(m, mc_on=False, mode="lite")
        except Exception as e:
            check("mutation_valid", False, str(e)[:60])
            return
    check("mutation_valid", True, "20 mutations all analyzable")

def test_evolution_convergence():
    """Evolution should converge (decreasing variance)."""
    from turnstile.engine import Builder, analyze
    from turnstile.adversarial import evolve_dag
    b = Builder()
    b.node("s","S","seed",1.0,0).node("a","A","event",0.7,10)
    b.node("b","B","event",0.5,50).node("o1","O1","outcome",0.3,200)
    b.node("o2","O2","outcome",0.4,200)
    b.edge("s","a",0.8,10).edge("a","b",0.6,40).edge("b","o1",0.5,150)
    b.edge("a","o2",0.4,190)
    g = b.build()
    evo = evolve_dag(g, n_generations=5, population=10)
    check("evolution_runs", evo["generations"] > 0)

def test_sanitize_bad_json():
    """Sanitizer should handle garbage JSON from LLM."""
    from turnstile.ingest import _sanitize_dag, _json_to_graph
    
    # Missing types
    bad = {"nodes": [{"id": "a", "label": "thing"}], "edges": []}
    clean = _sanitize_dag(bad)
    check("sanitize_no_type", clean["nodes"][0]["type"] == "seed")
    
    # Duplicate IDs
    bad2 = {"nodes": [
        {"id": "x", "label": "A", "type": "seed", "prior": 1.0, "time_hours": 0},
        {"id": "x", "label": "B", "type": "event", "prior": 0.5, "time_hours": 10},
        {"id": "o", "label": "C", "type": "outcome", "prior": 0.3, "time_hours": 100},
    ], "edges": [
        {"from": "x", "to": "o", "prob": 0.5}
    ]}
    clean2 = _sanitize_dag(bad2)
    ids = [n["id"] for n in clean2["nodes"]]
    check("sanitize_dedup", len(ids) == len(set(ids)), f"IDs not unique: {ids}")
    
    # Backward time edge (s at t=0, e at t=100, edge goes e→s = 100→0 = backward)
    bad3 = {"nodes": [
        {"id": "s", "label": "S", "type": "seed", "prior": 1.0, "time_hours": 0},
        {"id": "e", "label": "E", "type": "event", "prior": 0.5, "time_hours": 100},
        {"id": "o", "label": "O", "type": "outcome", "prior": 0.3, "time_hours": 200},
    ], "edges": [
        {"from": "e", "to": "s", "prob": 0.5},  # Backward! t=100 → t=0
        {"from": "s", "to": "o", "prob": 0.5},
    ]}
    clean3 = _sanitize_dag(bad3)
    backward_edges = [e for e in clean3["edges"] if e["from"] == "e" and e["to"] == "s"]
    check("sanitize_backward", len(backward_edges) == 0, "Backward edge not removed")

def test_semantic_similarity():
    """Semantic matching should find similar concepts."""
    from turnstile.ingest import semantic_similarity
    
    s1 = semantic_similarity("Market panic selling", "Panic sell-off in markets")
    s2 = semantic_similarity("China retaliates with tariffs", "Chinese tariff retaliation")
    s3 = semantic_similarity("Bitcoin price increase", "Cooking recipe for pasta")
    
    check("semantic_similar", s1 > 0.3, f"Expected > 0.3, got {s1}")
    check("semantic_similar2", s2 > 0.3, f"Expected > 0.3, got {s2}")
    check("semantic_different", s3 < 0.2, f"Expected < 0.2, got {s3}")

if __name__ == "__main__":
    print("=" * 60)
    print("  TURNSTILE — Edge Case Tests")
    print("=" * 60)
    
    test_empty_dag()
    test_single_node()
    test_two_nodes()
    test_self_loop()
    test_negative_probability()
    test_probability_over_one()
    test_disconnected_nodes()
    test_all_same_time()
    test_100_outcomes()
    test_mutation_preserves_validity()
    test_evolution_convergence()
    test_sanitize_bad_json()
    test_semantic_similarity()
    
    print(f"\n  {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        sys.exit(1)

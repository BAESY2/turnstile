"""TURNSTILE Adversarial Verification — Agents don't debate. They BUILD.

NOT THIS (boring):
  Prosecutor: "I think this is wrong because..."
  Defender: "No it's right because..."
  Judge: "I score 0.7"
  → LLM opinion theater

THIS INSTEAD (real):
  Each agent builds a DIFFERENT causal DAG from the same seed.
  All DAGs get inverted by the same math engine.
  Results are compared STRUCTURALLY, not by opinion.
  The most ROBUST findings (consistent across all DAGs) survive.

═══════════════════════════════════════════════════════════════

AGENT TYPES (each one builds a different reality):

1. ARCHITECT — Builds the "consensus" DAG
   Reads the seed text, extracts the most likely causal structure.
   This is the baseline — what most people would agree on.

2. CONTRARIAN — Builds the "opposite" DAG
   Deliberately constructs causality differently.
   "What if China's response is NOT driven by the tariff,
    but by internal politics?" Different edges, different priors.
   Forces the system to consider alternative causal structures.

3. HISTORIAN — Builds a DAG from historical precedent
   "In 2018 when tariffs were announced, THIS is what actually
    happened." Constructs DAG from real past data.
   Provides empirical grounding.

4. EXTREMIST — Builds the "worst case" DAG
   Maximizes probabilities on catastrophic paths.
   "What if everything goes wrong?" Black swan detector.

5. MINIMALIST — Builds the smallest possible DAG
   Removes every node that isn't strictly necessary.
   "What's the MINIMUM causal chain that still explains this?"
   Occam's razor as an agent.

═══════════════════════════════════════════════════════════════

VERIFICATION BY STRUCTURE, NOT OPINION:

After all agents build their DAGs, the engine:

1. Inverts ALL of them (same math, different inputs)
2. Compares results across DAGs:
   - CONSENSUS: findings that appear in ALL DAGs → HIGH confidence
   - DISPUTED: findings that appear in some but not others → MEDIUM
   - UNIQUE: findings that appear in only one DAG → LOW (but potentially valuable)
3. The Turnstile is valid only if it appears in 3+ DAGs
4. Necessity scores are averaged across DAGs (ensemble)
5. Sensitivity edges that appear in all DAGs are truly critical

This is NOT LLM asking "is this right?"
This is MULTIPLE CAUSAL MODELS being mathematically compared.

═══════════════════════════════════════════════════════════════

BONUS: MUTATION SWARM

After initial DAGs are built, run genetic algorithm:
  - Crossover: combine edges from two DAGs
  - Mutation: randomly perturb probabilities
  - Selection: keep DAGs where inversion results are most stable
  - After N generations, the surviving DAG structure is ROBUST

This is evolution applied to causal reasoning.
"""

import asyncio
import json
import numpy as np
from typing import Callable, Optional
from dataclasses import dataclass


ARCHITECT_SYSTEM = """You are a causal structure architect.
Given a scenario, extract the most LIKELY causal DAG.
Be mainstream. Include obvious causes and effects.
Return a JSON DAG structure."""

CONTRARIAN_SYSTEM = """You are a contrarian causal analyst.
Given a scenario, construct a DIFFERENT causal structure than the obvious one.
Challenge assumptions. Find alternative explanations.
"What if the obvious cause ISN'T the real cause?"
Return a JSON DAG structure."""

HISTORIAN_SYSTEM = """You are a historical pattern matcher.
Given a scenario, find the CLOSEST historical precedent and build
a causal DAG based on what ACTUALLY happened in that case.
Use real dates, real actors, real outcomes from history.
Return a JSON DAG structure."""

EXTREMIST_SYSTEM = """You are a worst-case scenario analyst.
Given a scenario, build a causal DAG that explores the EXTREME outcomes.
What's the black swan? What's the catastrophic chain?
Maximize probability on worst-case paths.
Return a JSON DAG structure."""

MINIMALIST_SYSTEM = """You are an Occam's razor analyst.
Given a scenario, build the SMALLEST possible causal DAG.
What is the absolute minimum number of nodes and edges
that still explains the scenario? Cut everything unnecessary.
Return a JSON DAG structure."""


DAG_FORMAT = """
Return ONLY valid JSON in this exact format:
{
  "nodes": [
    {"id": "unique_id", "label": "description", "type": "seed|event|outcome", "prior": 0.0-1.0, "time_hours": 0}
  ],
  "edges": [
    {"from": "source_id", "to": "target_id", "prob": 0.0-1.0, "delay_hours": 0, "gate": "or|and"}
  ],
  "correlations": [
    {"n1": "node_id", "n2": "node_id", "corr": 0.0-1.0}
  ]
}

Rules:
- First node must be type "seed" (the triggering event)
- Last 2-4 nodes must be type "outcome"
- All other nodes are type "event"
- Edges must form a DAG (no cycles)
- time_hours: 0 for seed, increasing for later events
- prior: how likely this node is independently (0.1-0.9)
- prob: P(target | source) — conditional probability
"""


@dataclass
class AgentDAG:
    """One agent's constructed DAG + its inversion results."""
    agent_type: str
    agent_name: str
    dag: object  # Graph
    result: dict  # analyze() output
    raw_json: dict


async def agent_build_dag(
    llm_call: Callable,
    seed_text: str,
    agent_system: str,
    agent_name: str,
) -> dict:
    """Single agent builds a DAG from seed text."""
    prompt = f"""SCENARIO:
{seed_text}

Build a causal DAG for this scenario.
Include 8-20 nodes and 10-30 edges.
Think step by step about cause and effect chains.

{DAG_FORMAT}"""

    response = await llm_call(prompt, agent_system)
    return _parse_json(response)


def json_to_graph(dag_json: dict):
    """Convert agent's JSON DAG to a Graph object."""
    from .engine import Builder

    b = Builder()
    for node in dag_json.get("nodes", []):
        b.node(
            node["id"],
            node.get("label", ""),
            node.get("type", "event"),
            node.get("prior", 0.5),
            node.get("time_hours", 0),
        )

    for edge in dag_json.get("edges", []):
        b.edge(
            edge["from"],
            edge["to"],
            edge.get("prob", 0.5),
            edge.get("delay_hours", 0),
            edge.get("gate", "or"),
        )

    for corr in dag_json.get("correlations", []):
        b.corr(corr["n1"], corr["n2"], corr.get("corr", 0.3))

    return b.build()


async def multi_agent_build(
    llm_call: Callable,
    seed_text: str,
    agents: list[str] = None,
) -> list[AgentDAG]:
    """All agents build DAGs in parallel. Then invert each one."""
    from .engine import analyze

    if agents is None:
        agents = ["architect", "contrarian", "historian", "extremist", "minimalist"]

    agent_configs = {
        "architect": (ARCHITECT_SYSTEM, "Architect"),
        "contrarian": (CONTRARIAN_SYSTEM, "Contrarian"),
        "historian": (HISTORIAN_SYSTEM, "Historian"),
        "extremist": (EXTREMIST_SYSTEM, "Extremist"),
        "minimalist": (MINIMALIST_SYSTEM, "Minimalist"),
    }

    # Build all DAGs in parallel
    async def _build_one(agent_type):
        system, name = agent_configs[agent_type]
        raw = await agent_build_dag(llm_call, seed_text, system, name)
        try:
            g = json_to_graph(raw)
            result = analyze(g, mc_on=g.n < 50, mc_n=50)
            return AgentDAG(agent_type=agent_type, agent_name=name,
                          dag=g, result=result, raw_json=raw)
        except Exception as e:
            return AgentDAG(agent_type=agent_type, agent_name=name,
                          dag=None, result={"error": str(e)}, raw_json=raw)

    results = await asyncio.gather(*[_build_one(a) for a in agents])
    return [r for r in results if r.dag is not None]


def cross_validate(agent_dags: list[AgentDAG]) -> dict:
    """Compare findings across all agent DAGs.

    CONSENSUS = appears in all → HIGH confidence
    DISPUTED = appears in some → investigate
    UNIQUE = one agent only → interesting but uncertain
    """
    n_agents = len(agent_dags)
    if n_agents == 0:
        return {"error": "no valid DAGs"}

    # 1. Turnstile consensus
    turnstiles = []
    for ad in agent_dags:
        ts = ad.result.get("turnstile", {})
        if ts.get("found"):
            turnstiles.append({
                "agent": ad.agent_name,
                "node": ts.get("label", ts.get("id", "")),
                "time_hours": ts.get("t_hours", 0),
                "gradient": ts.get("gradient", 0),
            })

    # 2. Necessity consensus — semantic matching across DAGs
    from .ingest import semantic_similarity
    
    all_critical = []  # (agent_name, label, necessity_score)
    for ad in agent_dags:
        for lid, nd in ad.result.get("necessities", {}).items():
            for cond in nd.get("conditions", []):
                if cond.get("critical") and not cond.get("trivial"):
                    all_critical.append((ad.agent_name, cond.get("label", "")[:60], cond.get("necessity", 0)))
    
    # Cluster by semantic similarity
    clusters = []
    used = set()
    for i, (ag1, lab1, sc1) in enumerate(all_critical):
        if i in used:
            continue
        cluster = {"labels": [lab1], "agents": [ag1], "scores": [sc1]}
        used.add(i)
        for j, (ag2, lab2, sc2) in enumerate(all_critical):
            if j in used or ag2 == ag1:
                continue
            if semantic_similarity(lab1, lab2) >= 0.35:
                cluster["labels"].append(lab2)
                cluster["agents"].append(ag2)
                cluster["scores"].append(sc2)
                used.add(j)
        clusters.append(cluster)
    
    consensus = []
    disputed = []
    unique = []
    for cl in clusters:
        entry = {
            "condition": cl["labels"][0],
            "variants": cl["labels"],
            "agents": cl["agents"],
            "count": len(cl["agents"]),
            "avg_necessity": round(np.mean(cl["scores"]), 4),
        }
        if len(cl["agents"]) >= max(2, n_agents * 0.6):
            entry["confidence"] = "HIGH"
            consensus.append(entry)
        elif len(cl["agents"]) >= 2:
            entry["confidence"] = "MEDIUM"
            disputed.append(entry)
        else:
            entry["confidence"] = "LOW"
            unique.append(entry)

    # 3. Sensitivity consensus — which edges appear across DAGs?
    edge_counts = {}
    for ad in agent_dags:
        for lid, sl in ad.result.get("sensitivity", {}).items():
            for s in sl[:5]:
                edge = s.get("edge", "")
                if edge not in edge_counts:
                    edge_counts[edge] = {"count": 0, "agents": [], "scores": []}
                edge_counts[edge]["count"] += 1
                edge_counts[edge]["agents"].append(ad.agent_name)
                edge_counts[edge]["scores"].append(s.get("sensitivity", 0))

    sensitive_consensus = [
        {"edge": e, "count": d["count"], "avg_sensitivity": round(np.mean(d["scores"]), 4)}
        for e, d in edge_counts.items() if d["count"] >= 2
    ]
    sensitive_consensus.sort(key=lambda x: x["count"], reverse=True)

    # 4. Outcome probability ensemble — average across DAGs
    outcome_ensemble = {}
    for ad in agent_dags:
        for lid, nd in ad.result.get("necessities", {}).items():
            label = nd.get("outcome", lid)
            if label not in outcome_ensemble:
                outcome_ensemble[label] = {"probs": [], "agents": []}
            outcome_ensemble[label]["probs"].append(nd.get("prob", 0))
            outcome_ensemble[label]["agents"].append(ad.agent_name)

    outcomes = [
        {"outcome": label, "ensemble_prob": round(np.mean(d["probs"]), 4),
         "std": round(np.std(d["probs"]), 4), "n_agents": len(d["probs"])}
        for label, d in outcome_ensemble.items()
    ]
    outcomes.sort(key=lambda x: x["ensemble_prob"], reverse=True)

    return {
        "n_agents": n_agents,
        "agents": [ad.agent_name for ad in agent_dags],
        "turnstile_consensus": turnstiles,
        "turnstile_agreement": len(set(t["node"][:20] for t in turnstiles)) <= 2 if turnstiles else False,
        "necessity": {
            "consensus": consensus,
            "disputed": disputed,
            "unique": unique,
        },
        "sensitivity_consensus": sensitive_consensus[:10],
        "outcome_ensemble": outcomes,
        "structural_diversity": {
            "node_counts": [ad.dag.n for ad in agent_dags],
            "edge_counts": [ad.dag.edge_count for ad in agent_dags],
            "avg_nodes": round(np.mean([ad.dag.n for ad in agent_dags])),
            "std_nodes": round(np.std([ad.dag.n for ad in agent_dags]), 1),
        },
    }


# ══════════════════════════════════════════════════════════════
# MUTATION SWARM — Genetic algorithm on DAG structure
# ══════════════════════════════════════════════════════════════

def mutate_dag(g, mutation_rate: float = 0.15):
    """Create a mutated copy of a Graph.

    Mutations (probability-based AND structural):
      - Edge probability ± noise (common)
      - Node prior ± noise (common)
      - Edge deletion (moderate)
      - Edge addition between existing nodes (moderate)
      - Node split: one event becomes two sequential events (rare)
      - Edge rewire: redirect an edge to a different target (rare)
    """
    from .engine import Builder

    b = Builder()
    node_ids = list(g.ids)
    
    # Copy nodes with potential mutations
    split_targets = {}  # old_id → (new_id_1, new_id_2)
    for i in range(g.n):
        nid = g.ids[i]
        prior = g.priors[i]
        ntype = {0: "seed", 1: "event", 2: "outcome"}[int(g.types[i])]
        
        # Mutate prior
        if g.types[i] == 1 and np.random.random() < mutation_rate:
            prior = np.clip(prior + np.random.normal(0, 0.15), 0.05, 0.95)
        
        # Node split (rare): event becomes two sequential events
        if g.types[i] == 1 and np.random.random() < mutation_rate * 0.15:
            mid_id = f"{nid}_b"
            t1 = float(g.times[i])
            t2 = t1 + np.random.uniform(5, 50)
            b.node(nid, f"{g.labels[i]} (early)", ntype, float(prior), t1)
            b.node(mid_id, f"{g.labels[i]} (late)", "event", float(prior * 0.9), t2)
            split_targets[nid] = (nid, mid_id)
            node_ids.append(mid_id)
        else:
            b.node(nid, g.labels[i], ntype, float(prior), float(g.times[i]))
    
    # Copy edges with mutations
    edges = np.argwhere(g.adj > 0)
    event_ids = [g.ids[i] for i in range(g.n) if g.types[i] == 1]
    
    for s, t in edges:
        src, tgt = g.ids[s], g.ids[t]
        prob = g.adj[s, t]
        delay = g.delays[s, t]
        gate = "and" if g.gates[t] else "or"

        # Mutate probability
        if np.random.random() < mutation_rate:
            prob = np.clip(prob + np.random.normal(0, 0.15), 0.05, 0.95)

        # Edge deletion (moderate)
        if np.random.random() < mutation_rate * 0.25:
            continue
        
        # Edge rewire (rare): redirect to different target at similar time
        if np.random.random() < mutation_rate * 0.1 and len(event_ids) > 3:
            alt = np.random.choice(event_ids)
            if alt != src and alt != tgt:
                tgt = alt
        
        # Handle split nodes
        if src in split_targets:
            src = split_targets[src][0]  # Use early half
        if tgt in split_targets:
            tgt = split_targets[tgt][1]  # Use late half
            
        b.edge(src, tgt, float(prob), float(delay), gate)
    
    # Add internal edges for split nodes
    for old_id, (early, late) in split_targets.items():
        b.edge(early, late, 0.85, np.random.uniform(5, 50))
    
    # Random edge addition (moderate)
    if np.random.random() < mutation_rate * 0.5:
        for _ in range(np.random.randint(1, 3)):
            all_ids = [n[0] for n in b._n]
            if len(all_ids) < 3:
                continue
            i = np.random.randint(0, len(all_ids) - 1)
            j = np.random.randint(i + 1, len(all_ids))
            # Check not already connected
            already = any(e[0] == all_ids[i] and e[1] == all_ids[j] for e in b._e)
            if not already:
                b.edge(all_ids[i], all_ids[j],
                       np.random.uniform(0.1, 0.5),
                       np.random.uniform(1, 100))

    return b.build()


def evolve_dag(g, n_generations: int = 10, population: int = 20,
               survival_rate: float = 0.3, mutation_rate: float = 0.15) -> dict:
    """Genetic algorithm: evolve the DAG structure for robustness.

    1. Create population of mutated DAGs
    2. Invert each one
    3. Score by consistency (low variance of turnstile + necessity)
    4. Keep top survivors
    5. Mutate survivors to create next generation
    6. Repeat

    Returns the most ROBUST DAG structure + evolution stats.
    """
    from .engine import analyze

    # Initial population
    pop = [g]  # Original is generation 0
    for _ in range(population - 1):
        pop.append(mutate_dag(g, mutation_rate))

    history = []

    for gen in range(n_generations):
        # Invert all
        results = []
        for dag in pop:
            try:
                r = analyze(dag, mc_on=False, mode="lite")
                results.append((dag, r))
            except:
                continue

        if not results:
            break

        # Score: lower variance of turnstile time + necessity scores = more robust
        turnstile_times = []
        necessity_scores = []
        for dag, r in results:
            ts = r.get("turnstile", {})
            if ts.get("found"):
                turnstile_times.append(ts.get("t_hours", 0))
            for lid, nd in r.get("necessities", {}).items():
                for c in nd.get("conditions", []):
                    if c.get("critical"):
                        necessity_scores.append(c.get("necessity", 0))

        gen_stats = {
            "generation": gen,
            "population": len(results),
            "turnstile_std": round(float(np.std(turnstile_times)), 2) if turnstile_times else 999,
            "necessity_mean": round(float(np.mean(necessity_scores)), 4) if necessity_scores else 0,
        }
        history.append(gen_stats)

        # Select top survivors
        # Fitness = consistency: results closest to the median
        if len(results) < 3:
            break

        median_ts = np.median(turnstile_times) if turnstile_times else 0
        ts_std = np.std(turnstile_times) if len(turnstile_times) > 1 else 1.0
        scored = []
        for dag, r in results:
            ts = r.get("turnstile", {})
            ts_time = ts.get("t_hours", 0) if ts.get("found") else 999
            # Composite fitness: turnstile agreement + necessity stability
            ts_agreement = -abs(ts_time - median_ts) / max(ts_std, 1.0)  # Normalized
            # Stability: how consistent are necessity scores (lower variance = better)
            nec_scores = []
            for lid, nd in r.get("necessities", {}).items():
                for c in nd.get("conditions", []):
                    if c.get("critical"):
                        nec_scores.append(c.get("necessity", 0))
            stability = -np.std(nec_scores) if nec_scores else 0  # Low std = stable
            fitness = 0.5 * ts_agreement + 0.5 * stability
            scored.append((fitness, dag, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        n_survive = max(3, int(len(scored) * survival_rate))
        survivors = [dag for _, dag, _ in scored[:n_survive]]

        # Next generation: mutate survivors
        pop = list(survivors)
        while len(pop) < population:
            parent = survivors[np.random.randint(0, len(survivors))]
            pop.append(mutate_dag(parent, mutation_rate))

    # Final: return the best DAG (original or mutant)
    best_dag = pop[0]
    best_result = analyze(best_dag, mc_on=True, mc_n=50, mode="standard")

    return {
        "generations": len(history),
        "final_population": len(pop),
        "history": history,
        "best_result": best_result,
        "converged": len(history) > 1 and history[-1]["turnstile_std"] < history[0].get("turnstile_std", 999),
    }


# ══════════════════════════════════════════════════════════════
# FULL ADVERSARIAL PIPELINE
# ══════════════════════════════════════════════════════════════

async def adversarial_verify(
    llm_call: Callable,
    seed_text: str,
    agents: list[str] = None,
    evolve: bool = True,
    evolve_gens: int = 10,
) -> dict:
    """Full pipeline:
    1. Multiple agents build competing DAGs (LLM)
    2. Cross-validate findings (math)
    3. Evolve best DAG for robustness (genetic algorithm, no LLM)
    4. Return consensus findings
    """

    # Step 1: Multi-agent DAG construction (LLM calls here)
    agent_dags = await multi_agent_build(llm_call, seed_text, agents)

    # Step 2: Cross-validation (pure math)
    consensus = cross_validate(agent_dags)

    # Step 3: Evolution (pure math, no LLM)
    evolution = {}
    if evolve and agent_dags:
        # Evolve the architect's DAG (baseline)
        architect_dag = next((ad for ad in agent_dags if ad.agent_type == "architect"), agent_dags[0])
        evolution = evolve_dag(architect_dag.dag, n_generations=evolve_gens)

    # Count LLM calls: 1 per agent for DAG construction
    llm_calls = len(agent_dags)

    return {
        "consensus": consensus,
        "evolution": evolution,
        "agent_details": [
            {
                "agent": ad.agent_name,
                "nodes": ad.dag.n,
                "edges": ad.dag.edge_count,
                "turnstile": ad.result.get("turnstile", {}),
                "perf_ms": ad.result.get("perf", {}).get("ms", 0),
            }
            for ad in agent_dags
        ],
        "llm_calls": llm_calls,
        "math_operations": f"{len(agent_dags)} inversions + {evolve_gens * 20 if evolve else 0} evolution runs",
    }


def _parse_json(text: str) -> dict:
    import re
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
        return {"nodes": [], "edges": []}

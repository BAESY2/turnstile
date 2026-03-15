"""TURNSTILE Advanced Analysis — Everything the engine didn't have yet.

All pure math. Zero LLM. Runs in milliseconds.
"""

import numpy as np
from .engine import Graph, forward, invert_edges, EPS, sensitivity, do, counterfactual


# ══════════════════════════════════════════════════════════════
# 1. SURPRISE DETECTION — Where do forward and inverted disagree most?
# ══════════════════════════════════════════════════════════════

def surprises(g: Graph, top_k: int = 10) -> list[dict]:
    """Nodes where P_fwd and P_inv differ most = most surprising findings.
    
    High P_fwd, low P_inv → "Likely to happen, but NOT necessary for any outcome"
                           → OVERRATED by forward prediction
    
    Low P_fwd, high P_inv → "Unlikely, but if outcome happens, this WAS necessary"
                           → UNDERRATED, hidden critical factor
    """
    mask = g.types == 1  # Events only
    indices = np.where(mask)[0]
    
    results = []
    for i in indices:
        fwd = g.marginals[i]
        inv = g.inv_probs[i]
        gap = inv - fwd  # Positive = underrated, Negative = overrated
        abs_gap = abs(gap)
        
        if gap > 0.05:
            interpretation = "UNDERRATED — unlikely but necessary. Hidden critical factor."
        elif gap < -0.05:
            interpretation = "OVERRATED — likely but not necessary. Red herring."
        else:
            interpretation = "ALIGNED — forward and inverted agree."
        
        results.append({
            "id": g.ids[i], "label": g.labels[i],
            "P_fwd": round(float(fwd), 4), "P_inv": round(float(inv), 4),
            "gap": round(float(gap), 4), "abs_gap": round(float(abs_gap), 4),
            "type": "underrated" if gap > 0.05 else ("overrated" if gap < -0.05 else "aligned"),
            "interpretation": interpretation,
        })
    
    results.sort(key=lambda x: x["abs_gap"], reverse=True)
    return results[:top_k]


# ══════════════════════════════════════════════════════════════
# 2. BOTTLENECK DETECTION — All paths pass through here
# ══════════════════════════════════════════════════════════════

def bottlenecks(g: Graph) -> list[dict]:
    """Find nodes that ALL (or most) paths from seed to outcomes pass through.
    
    Bottleneck = removing this node disconnects most seed→outcome paths.
    """
    seeds = np.where(g.types == 0)[0]
    outcomes = np.where(g.types == 2)[0]
    events = np.where(g.types == 1)[0]
    
    if len(seeds) == 0 or len(outcomes) == 0:
        return []
    
    # Count paths through each event node
    def _count_paths(adj, start, end, through=None):
        """Count paths from start to end (optionally through a node)."""
        n = adj.shape[0]
        # Simple DFS path count (ok for DAGs up to ~1000 nodes)
        count = [0]
        def dfs(node, visited):
            if node == end:
                count[0] += 1; return
            for c in np.where(adj[node] > 0)[0]:
                if int(c) not in visited:
                    if through is not None and int(c) == through:
                        continue  # Skip this node
                    visited.add(int(c))
                    dfs(int(c), visited)
                    visited.discard(int(c))
        dfs(start, {start})
        return count[0]
    
    # Total paths seed→each outcome
    total_paths = {}
    for s in seeds:
        for o in outcomes:
            total_paths[(int(s), int(o))] = _count_paths(g.adj, int(s), int(o))
    
    total_all = sum(total_paths.values())
    if total_all == 0:
        return []
    
    results = []
    for ev in events[:min(30, len(events))]:  # Cap for performance
        # Paths when this node is removed
        remaining = 0
        for s in seeds:
            for o in outcomes:
                remaining += _count_paths(g.adj, int(s), int(o), through=int(ev))
        
        blocked = total_all - remaining
        bottleneck_score = blocked / total_all if total_all > 0 else 0
        
        results.append({
            "id": g.ids[ev], "label": g.labels[ev],
            "paths_blocked": blocked, "total_paths": total_all,
            "bottleneck_score": round(float(bottleneck_score), 4),
            "is_bottleneck": bottleneck_score > 0.3,
        })
    
    results.sort(key=lambda x: x["bottleneck_score"], reverse=True)
    return results


# ══════════════════════════════════════════════════════════════
# 3. CHAIN REACTION — One change, how far does it propagate?
# ══════════════════════════════════════════════════════════════

def chain_reaction(g: Graph, node_idx: int, delta: float = 0.2) -> dict:
    """Perturb one node and measure ripple effect via do-operator."""
    orig_m = g.marginals.copy()
    
    # Use do-operator: force node to higher value, see what changes
    forced_val = min(0.99, float(g.marginals[node_idx]) + delta)
    after = do(g, node_idx, forced_val)
    
    diffs = np.abs(after - orig_m)
    affected = int(np.sum(diffs > 0.005))
    max_idx = int(np.argmax(diffs))
    
    return {
        "source": g.ids[node_idx],
        "source_label": g.labels[node_idx],
        "delta": delta,
        "nodes_affected": affected,
        "total_nodes": g.n,
        "propagation_ratio": round(float(affected / max(1, g.n)), 4),
        "max_effect_node": g.ids[max_idx],
        "max_effect_value": round(float(diffs[max_idx]), 4),
        "ripple": sorted([
            {"id": g.ids[i], "change": round(float(after[i] - orig_m[i]), 4)}
            for i in range(g.n) if diffs[i] > 0.003
        ], key=lambda x: abs(x["change"]), reverse=True)[:10],
    }


def chain_reactions(g: Graph, top_k: int = 5) -> list[dict]:
    """Run chain reaction for top-K most impactful nodes."""
    events = g.events
    if len(events) == 0: return []
    # Sort by marginal — most likely to change
    sorted_events = events[np.argsort(-g.marginals[events])][:top_k]
    return [chain_reaction(g, int(i)) for i in sorted_events]


# ══════════════════════════════════════════════════════════════
# 4. EDGE CLASSIFICATION — amplifier / dampener / neutral
# ══════════════════════════════════════════════════════════════

def classify_edges(g: Graph) -> dict:
    """Classify each edge by its effect on outcome probabilities.
    
    Amplifier: increasing this edge increases most outcome probs
    Dampener: increasing this edge decreases most outcome probs  
    Neutral: little effect either way
    """
    edges = np.argwhere(g.adj > 0)
    outcomes = g.outcomes
    if len(edges) == 0 or len(outcomes) == 0:
        return {"amplifiers": [], "dampeners": [], "neutral": []}
    
    orig = g.adj.copy()
    orig_m = g.marginals.copy()
    delta = 0.1
    
    amplifiers, dampeners, neutral = [], [], []
    
    for s, t in edges[:min(40, len(edges))]:  # Cap for performance
        g.adj[s, t] = min(0.99, orig[s, t] + delta)
        g.marginals = orig_m.copy()
        forward(g)
        up = g.marginals[outcomes].copy()
        
        g.adj[s, t] = orig[s, t]
        g.marginals = orig_m.copy()
        
        net_effect = float(np.mean(up - orig_m[outcomes]))
        
        entry = {
            "edge": f"{g.ids[s]}→{g.ids[t]}",
            "base_prob": round(float(orig[s, t]), 4),
            "net_effect": round(net_effect, 6),
        }
        
        if net_effect > 0.005:
            entry["type"] = "amplifier"
            amplifiers.append(entry)
        elif net_effect < -0.005:
            entry["type"] = "dampener"
            dampeners.append(entry)
        else:
            entry["type"] = "neutral"
            neutral.append(entry)
    
    g.adj = orig
    g.marginals = orig_m
    
    amplifiers.sort(key=lambda x: x["net_effect"], reverse=True)
    dampeners.sort(key=lambda x: x["net_effect"])
    
    return {"amplifiers": amplifiers, "dampeners": dampeners, "neutral": neutral}


# ══════════════════════════════════════════════════════════════
# 5. MERMAID DAG EXPORT
# ══════════════════════════════════════════════════════════════

def to_mermaid(g: Graph, show_probs: bool = True) -> str:
    """Export DAG as Mermaid diagram markup."""
    lines = ["graph TD"]
    
    # Node styles
    for i in range(g.n):
        label = g.labels[i][:30].replace('"', "'")
        prob = f" ({g.marginals[i]:.0%})" if show_probs and g.marginals is not None else ""
        
        if g.types[i] == 0:  # Seed
            lines.append(f'    {g.ids[i]}[("{label}{prob}")]')
        elif g.types[i] == 2:  # Outcome
            lines.append(f'    {g.ids[i]}[/"{label}{prob}"\\]')
        else:
            # Color by phase if entropy computed
            if g.H_grad is not None:
                grad = g.H_grad[i]
                if grad > 0.1:
                    lines.append(f'    {g.ids[i]}("{label}{prob}")')  # OPEN
                elif grad < -0.1:
                    lines.append(f'    {g.ids[i]}["{label}{prob}"]')  # LOCKED
                else:
                    lines.append(f'    {g.ids[i]}{{{{{label}{prob}}}}}')  # TRANSITION (diamond)
            else:
                lines.append(f'    {g.ids[i]}("{label}{prob}")')
    
    # Edges
    edges = np.argwhere(g.adj > 0)
    for s, t in edges:
        prob_label = f"|{g.adj[s, t]:.0%}|" if show_probs else ""
        gate = " &" if g.gates[t] in (1, 2) else ""
        lines.append(f'    {g.ids[s]} -->{prob_label} {g.ids[t]}{gate}')
    
    # Styles
    lines.append("")
    lines.append("    classDef seed fill:#f97316,stroke:#333,stroke-width:2px,color:#fff")
    lines.append("    classDef outcome fill:#3b82f6,stroke:#333,stroke-width:2px,color:#fff")
    lines.append("    classDef locked fill:#ef4444,stroke:#333,stroke-width:2px,color:#fff")
    lines.append("    classDef transition fill:#f59e0b,stroke:#333,stroke-width:2px,color:#000")
    
    for i in range(g.n):
        if g.types[i] == 0:
            lines.append(f"    class {g.ids[i]} seed")
        elif g.types[i] == 2:
            lines.append(f"    class {g.ids[i]} outcome")
        elif g.H_grad is not None and g.H_grad[i] < -0.1:
            lines.append(f"    class {g.ids[i]} locked")
        elif g.H_grad is not None and abs(g.H_grad[i]) < 0.1:
            lines.append(f"    class {g.ids[i]} transition")
    
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 6. ASCII DAG
# ══════════════════════════════════════════════════════════════

def to_ascii(g: Graph) -> str:
    """Simple ASCII representation of the DAG."""
    lines = []
    lines.append("TURNSTILE DAG")
    lines.append("─" * 50)
    
    # Group by time
    time_groups = {}
    for i in range(g.n):
        t = round(float(g.times[i]))
        if t not in time_groups:
            time_groups[t] = []
        phase = ""
        if g.H_grad is not None:
            if g.types[i] == 0: phase = "◇"
            elif g.types[i] == 2: phase = "◆"
            elif g.H_grad[i] > 0.1: phase = "○"
            elif g.H_grad[i] < -0.1: phase = "●"
            else: phase = "◐"
        
        prob_str = f"{g.marginals[i]:.0%}" if g.marginals is not None else "?"
        inv_str = f"{g.inv_probs[i]:.0%}" if g.inv_probs is not None else "?"
        time_groups[t].append(f"{phase} {g.ids[i]:>10s} [{prob_str:>4s}→{inv_str:>4s}] {g.labels[i][:35]}")
    
    for t in sorted(time_groups.keys()):
        lines.append(f"\n  t={t}h:")
        for node_str in time_groups[t]:
            lines.append(f"    {node_str}")
    
    # Edges
    lines.append("\n  Edges:")
    edges = np.argwhere(g.adj > 0)
    for s, t_idx in edges:
        gate = " [AND]" if g.gates[t_idx] in (1, 2) else ""
        lines.append(f"    {g.ids[s]:>10s} ──({g.adj[s, t_idx]:.0%})──→ {g.ids[t_idx]}{gate}")
    
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 7. TIMELINE VISUALIZATION
# ══════════════════════════════════════════════════════════════

def timeline(g: Graph) -> str:
    """Visual timeline showing OPEN → TRANSITION → LOCKED phases."""
    if g.H_grad is None:
        return "Run entropy() first"
    
    timed = [(i, g.times[i]) for i in range(g.n)]
    timed.sort(key=lambda x: x[1])
    
    lines = []
    lines.append("ENTROPY TIMELINE")
    lines.append("─" * 65)
    lines.append("  ○ OPEN (future undetermined)  ◐ TURNSTILE  ● LOCKED (inevitable)")
    lines.append("")
    
    max_t = max(g.times[i] for i, _ in timed) if timed else 1
    
    for idx, t in timed:
        node = g.ids[idx]
        label = g.labels[idx][:25]
        grad = g.H_grad[idx]
        
        # Phase
        if g.types[idx] == 0:
            marker = "◇"; phase = "SEED"
        elif g.types[idx] == 2:
            marker = "◆"; phase = "END"
        elif abs(grad) < 0.1:
            marker = "◐"; phase = "⚡TURN"
        elif grad > 0:
            marker = "○"; phase = "OPEN"
        else:
            marker = "●"; phase = "LOCK"
        
        # Bar showing position on timeline
        pos = int((t / max(max_t, 1)) * 40)
        bar = "─" * pos + marker + "─" * (40 - pos)
        
        fwd = f"H↑{g.fwd_H[idx]:.2f}" if g.fwd_H is not None else ""
        inv = f"H↓{g.inv_H[idx]:.2f}" if g.inv_H is not None else ""
        
        lines.append(f"  {bar} {phase:>5s} {node:>10s} {label}")
    
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 8. REPORT GENERATION — One-page markdown summary
# ══════════════════════════════════════════════════════════════

def generate_report(g: Graph, result: dict, title: str = "TURNSTILE Analysis") -> str:
    """Generate a complete markdown report from analysis results."""
    lines = [f"# {title}", ""]
    
    p = result.get("perf", {})
    lines.append(f"*Generated by TURNSTILE v{result.get('version', '?')} | "
                f"{p.get('nodes', '?')} nodes, {p.get('edges', '?')} edges | "
                f"{p.get('ms', '?')}ms | 0 LLM calls*")
    lines.append("")
    
    # Confidence
    conf = result.get("confidence", {})
    if conf:
        lines.append(f"**Overall Confidence: {conf.get('score', '?')}%**")
        lines.append("")
    
    # Turnstile
    ts = result.get("turnstile", {})
    if ts.get("found"):
        lines.append("## ⚡ Point of No Return (Turnstile)")
        lines.append(f"**{ts['label']}** at {ts.get('t_hours', '?')}h")
        lines.append(f"- Forward entropy: {ts.get('fwd_H', '?')}")
        lines.append(f"- Inverted entropy: {ts.get('inv_H', '?')}")
        lines.append(f"- Gradient: {ts.get('gradient', '?')} (≈0 = phase transition)")
        lines.append("")
    
    # Outcomes
    lines.append("## Outcome Probabilities")
    for lid, nd in result.get("necessities", {}).items():
        lines.append(f"\n### {nd['outcome']} (P={nd['prob']})")
        lines.append("| Condition | Necessity | Critical |")
        lines.append("|-----------|-----------|----------|")
        for c in nd.get("conditions", [])[:8]:
            if c.get("trivial"): continue
            cr = "★" if c.get("critical") else ""
            lines.append(f"| {c['label'][:50]} | {c['necessity']:.3f} | {cr} |")
    
    # Surprises
    s = surprises(g)
    if s:
        lines.append("\n## 🔍 Surprising Findings")
        for item in s[:5]:
            if item["type"] != "aligned":
                lines.append(f"- **{item['label'][:40]}**: {item['type'].upper()} "
                           f"(P_fwd={item['P_fwd']}, P_inv={item['P_inv']}, gap={item['gap']:+.3f})")
    
    # Critical paths
    cp = result.get("critical_paths", {})
    if cp:
        lines.append("\n## 🛣️ Critical Paths")
        for lid, c in cp.items():
            if c.get("found"):
                chain = " → ".join(s["label"][:20] for s in c["path"])
                lines.append(f"- **{lid}**: {chain} (P={c['prob']})")
    
    # Sensitivity
    sens = result.get("sensitivity", {})
    if sens:
        lines.append("\n## 🔬 Most Sensitive Edges")
        for lid, sl in sens.items():
            if sl:
                lines.append(f"- **{lid}**: {sl[0]['edge']} (sensitivity={sl[0]['sensitivity']})")
    
    # do-calculus
    do_r = result.get("do_calculus", [])
    if do_r:
        lines.append("\n## 🧪 Causal Power (What to intervene on)")
        for d in do_r[:5]:
            lines.append(f"- do({d['label'][:30]}): power={d['power']}")
    
    # Robustness
    rob = result.get("robustness", {})
    if rob:
        lines.append(f"\n## 🛡️ Robustness: {rob.get('flips', '?')}/{rob.get('total', '?')} edges to flip prediction")
    
    lines.append(f"\n---\n*\"What's happened, happened. But what had to be true?\"*")
    
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 9. SCENARIO DIFF — Compare two analysis results
# ══════════════════════════════════════════════════════════════

def diff_results(r1: dict, r2: dict, name1: str = "A", name2: str = "B") -> dict:
    """Compare two inversion results. What changed?"""
    diffs = {
        "turnstile": {},
        "outcome_changes": [],
        "necessity_changes": [],
    }
    
    # Turnstile comparison
    ts1 = r1.get("turnstile", {})
    ts2 = r2.get("turnstile", {})
    diffs["turnstile"] = {
        name1: ts1.get("label", "none"),
        name2: ts2.get("label", "none"),
        "same": ts1.get("id") == ts2.get("id"),
        "time_diff": (ts2.get("t_hours", 0) - ts1.get("t_hours", 0)) if ts1.get("found") and ts2.get("found") else None,
    }
    
    # Outcome probability changes
    nec1 = r1.get("necessities", {})
    nec2 = r2.get("necessities", {})
    all_outcomes = set(nec1.keys()) | set(nec2.keys())
    for oid in all_outcomes:
        p1 = nec1.get(oid, {}).get("prob", 0)
        p2 = nec2.get(oid, {}).get("prob", 0)
        if abs(p2 - p1) > 0.01:
            diffs["outcome_changes"].append({
                "outcome": oid,
                f"P_{name1}": p1, f"P_{name2}": p2,
                "change": round(p2 - p1, 4),
            })
    
    diffs["outcome_changes"].sort(key=lambda x: abs(x["change"]), reverse=True)
    
    return diffs


# ══════════════════════════════════════════════════════════════
# COMBINED: run_advanced
# ══════════════════════════════════════════════════════════════

def run_advanced(g: Graph, result: dict = None) -> dict:
    """Run all advanced analyses. Append to existing result."""
    return {
        "surprises": surprises(g),
        "bottlenecks": bottlenecks(g),
        "chain_reactions": chain_reactions(g),
        "edge_classification": classify_edges(g),
        "mermaid": to_mermaid(g),
        "ascii": to_ascii(g),
        "timeline": timeline(g),
        "report": generate_report(g, result) if result else "",
    }

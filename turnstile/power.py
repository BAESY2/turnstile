"""TURNSTILE Power Features — The stuff that makes people say 'holy shit'.

All pure math. Zero LLM (except causal_story which optionally uses one).
"""

import numpy as np
from .engine import Graph, Builder, analyze, forward, invert_edges, do, EPS, forward_partial


# ══════════════════════════════════════════════════════════════
# 1. PORTFOLIO — Analyze multiple DAGs simultaneously
# ══════════════════════════════════════════════════════════════

def portfolio(graphs: list[tuple[str, Graph]], mc_on: bool = True) -> dict:
    """Analyze multiple scenarios and cross-compare.
    
    Input: [(name, graph), ...]
    Returns: per-scenario results + cross-scenario comparison
    """
    results = {}
    all_turnstiles = []
    all_outcomes = {}
    
    for name, g in graphs:
        r = analyze(g, mc_on=mc_on, mc_n=50, mode="standard")
        results[name] = r
        ts = r.get("turnstile", {})
        if ts.get("found"):
            all_turnstiles.append({"scenario": name, "node": ts.get("label", ""), "time": ts.get("t_hours", 0)})
        for lid, nd in r.get("necessities", {}).items():
            if lid not in all_outcomes:
                all_outcomes[lid] = []
            all_outcomes[lid].append({"scenario": name, "prob": nd["prob"], "outcome": nd["outcome"]})
    
    # Cross-scenario: which outcomes are robust across scenarios?
    robust_outcomes = {}
    for lid, entries in all_outcomes.items():
        probs = [e["prob"] for e in entries]
        robust_outcomes[lid] = {
            "outcome": entries[0]["outcome"],
            "mean_prob": round(float(np.mean(probs)), 4),
            "std_prob": round(float(np.std(probs)), 4),
            "n_scenarios": len(entries),
            "consistent": float(np.std(probs)) < 0.1,
        }
    
    return {
        "scenarios": results,
        "n_scenarios": len(graphs),
        "turnstiles": all_turnstiles,
        "cross_comparison": robust_outcomes,
    }


# ══════════════════════════════════════════════════════════════
# 2. CAUSAL STORY — Why did this outcome happen? (natural language)
# ══════════════════════════════════════════════════════════════

def causal_story(g: Graph, result: dict, outcome_id: str = None) -> str:
    """Generate a natural language causal narrative.
    No LLM needed — pure template from math results.
    """
    nec = result.get("necessities", {})
    ts = result.get("turnstile", {})
    cp = result.get("critical_paths", {})
    do_r = result.get("do_calculus", [])
    conf = result.get("confidence", {})
    
    if outcome_id is None:
        # Pick highest probability outcome
        outcome_id = max(nec.keys(), key=lambda k: nec[k]["prob"]) if nec else None
    
    if outcome_id is None or outcome_id not in nec:
        return "No outcome to analyze."
    
    nd = nec[outcome_id]
    lines = []
    
    # Opening
    lines.append(f"## Why \"{nd['outcome']}\" (P={nd['prob']:.1%})")
    lines.append("")
    
    # Critical conditions
    critical = [c for c in nd.get("conditions", []) if c.get("critical") and not c.get("trivial")]
    if critical:
        lines.append("### What had to be true:")
        for i, c in enumerate(critical[:5], 1):
            lines.append(f"{i}. **{c['label']}** (necessity: {c['necessity']:.1%})")
        lines.append("")
    
    # The story
    lines.append("### The causal chain:")
    path = cp.get(outcome_id, {})
    if path.get("found"):
        chain = path["path"]
        for i, node in enumerate(chain):
            if i == 0:
                lines.append(f"It started with **{node['label']}**.")
            elif i == len(chain) - 1:
                lines.append(f"This led to **{node['label']}** (P={path['prob']:.1%}).")
            else:
                lines.append(f"→ Which caused **{node['label']}**.")
        lines.append("")
    
    # Turnstile
    if ts.get("found"):
        lines.append("### Point of no return:")
        lines.append(f"Once **\"{ts['label']}\"** happened (at {ts['t_hours']:.0f}h), "
                    f"the outcome became essentially inevitable. "
                    f"Before this moment, intervention could have changed the result. "
                    f"After it, the path was locked.")
        lines.append("")
    
    # What could have changed it
    if do_r:
        top_lever = do_r[0]
        lines.append("### What could have changed the outcome:")
        lines.append(f"The single most powerful intervention: **forcing \"{top_lever['label']}\"** "
                    f"to a different value (causal power: {top_lever['power']:.3f}).")
        lines.append("")
    
    # Surprise finding
    from .extra import surprises
    surp = surprises(g)
    underrated = [s for s in surp if s["type"] == "underrated"]
    if underrated:
        lines.append("### Hidden factor most people missed:")
        s = underrated[0]
        lines.append(f"**\"{s['label']}\"** — Forward prediction gave it only {s['P_fwd']:.1%} probability, "
                    f"but the inversion shows it had {s['P_inv']:.1%} necessity. "
                    f"This is the hidden critical factor that most analyses overlook.")
        lines.append("")
    
    # Confidence
    if conf:
        lines.append(f"*Analysis confidence: {conf.get('score', '?')}%*")
    
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 3. RISK MATRIX — Probability × Impact 2D map
# ══════════════════════════════════════════════════════════════

def risk_matrix(g: Graph) -> dict:
    """Map every event on Probability × Impact axes.
    
    Probability = forward marginal P(x)
    Impact = counterfactual impact (how much outcomes change if x removed)
    
    Quadrants:
      HIGH P, HIGH I → CRITICAL (certain and impactful)
      HIGH P, LOW I  → NOISE (likely but doesn't matter)
      LOW P, HIGH I  → BLACK SWAN (unlikely but devastating)  
      LOW P, LOW I   → IGNORE
    """
    events = g.events
    if len(events) == 0:
        return {"nodes": [], "quadrants": {}}
    
    # Get impact via counterfactual
    from .engine import counterfactual as cf_fn
    
    nodes = []
    for i in events:
        prob = float(g.marginals[i])
        cf = cf_fn(g, int(i))
        impact = cf["impact"]
        
        # Quadrant classification
        p_thresh = 0.5
        i_thresh = 0.03
        if prob >= p_thresh and impact >= i_thresh:
            quadrant = "CRITICAL"
        elif prob >= p_thresh and impact < i_thresh:
            quadrant = "NOISE"
        elif prob < p_thresh and impact >= i_thresh:
            quadrant = "BLACK_SWAN"
        else:
            quadrant = "IGNORE"
        
        nodes.append({
            "id": g.ids[i], "label": g.labels[i],
            "probability": round(prob, 4),
            "impact": round(impact, 4),
            "quadrant": quadrant,
        })
    
    nodes.sort(key=lambda x: x["probability"] * x["impact"], reverse=True)
    
    quadrants = {}
    for q in ["CRITICAL", "BLACK_SWAN", "NOISE", "IGNORE"]:
        quadrants[q] = [n for n in nodes if n["quadrant"] == q]
    
    return {"nodes": nodes, "quadrants": quadrants}


# ══════════════════════════════════════════════════════════════
# 4. TIPPING POINTS — At what probability does the outcome flip?
# ══════════════════════════════════════════════════════════════

def tipping_points(g: Graph, resolution: int = 10) -> list[dict]:
    """For each event node, find the probability threshold where 
    the top outcome changes.
    
    Sweep each node from 0.1 to 0.9, find where prediction flips.
    """
    outcomes = g.outcomes
    if len(outcomes) < 2:
        return []
    
    orig_adj = g.adj.copy()
    orig_m = g.marginals.copy()
    events = g.events
    
    results = []
    for ev in events[:min(15, len(events))]:
        # Current top outcome
        base_top = outcomes[np.argmax(orig_m[outcomes])]
        
        # Sweep through do-values
        tip_found = False
        tip_value = None
        
        for step in range(resolution + 1):
            val = 0.05 + 0.9 * step / resolution
            after = do(g, int(ev), val)
            new_top = outcomes[np.argmax(after[outcomes])]
            
            if new_top != base_top and not tip_found:
                tip_found = True
                tip_value = val
                results.append({
                    "node": g.ids[ev],
                    "label": g.labels[ev],
                    "tipping_value": round(val, 2),
                    "current_value": round(float(g.marginals[ev]), 4),
                    "flips_from": g.ids[base_top],
                    "flips_to": g.ids[new_top],
                    "distance": round(abs(val - float(g.marginals[ev])), 4),
                })
                break
    
    results.sort(key=lambda x: x["distance"])
    return results


# ══════════════════════════════════════════════════════════════
# 5. SCENARIO TREE — Branch at each decision point
# ══════════════════════════════════════════════════════════════

def scenario_tree(g: Graph, max_depth: int = 3) -> dict:
    """Build a tree of possible futures branching at each high-entropy node.
    
    At each branch point, show "if this goes HIGH" vs "if this goes LOW".
    """
    if g.fwd_H is None:
        from .engine import entropy
        entropy(g)
    
    outcomes = g.outcomes
    if len(outcomes) == 0:
        return {"branches": []}
    
    # Find top branch points (highest forward entropy = most uncertain)
    events = g.events
    if len(events) == 0:
        return {"branches": []}
    
    sorted_by_entropy = events[np.argsort(-g.fwd_H[events])]
    branch_nodes = sorted_by_entropy[:max_depth]
    
    branches = []
    base_probs = {g.ids[o]: round(float(g.marginals[o]), 4) for o in outcomes}
    
    for bn in branch_nodes:
        # HIGH scenario
        high = do(g, int(bn), 0.9)
        high_probs = {g.ids[o]: round(float(high[o]), 4) for o in outcomes}
        high_top = max(high_probs, key=high_probs.get)
        
        # LOW scenario
        low = do(g, int(bn), 0.1)
        low_probs = {g.ids[o]: round(float(low[o]), 4) for o in outcomes}
        low_top = max(low_probs, key=low_probs.get)
        
        branches.append({
            "branch_node": g.ids[bn],
            "branch_label": g.labels[bn],
            "entropy": round(float(g.fwd_H[bn]), 4),
            "current_prob": round(float(g.marginals[bn]), 4),
            "if_high": {"probs": high_probs, "top_outcome": high_top},
            "if_low": {"probs": low_probs, "top_outcome": low_top},
            "outcome_flips": high_top != low_top,
            "base": base_probs,
        })
    
    return {"branches": branches, "depth": len(branches)}


# ══════════════════════════════════════════════════════════════
# 6. MULTI WHAT-IF — Simultaneous intervention on multiple nodes
# ══════════════════════════════════════════════════════════════

def multi_what_if(g: Graph, interventions: dict[str, float]) -> dict:
    """Apply do-operator to multiple nodes simultaneously.
    
    interventions: {"node_id": forced_value, ...}
    """
    orig = g.adj.copy()
    orig_p = g.priors.copy()
    orig_m = g.marginals.copy()
    
    id_map = {nid: i for i, nid in enumerate(g.ids)}
    
    # Apply all interventions
    for nid, val in interventions.items():
        if nid in id_map:
            idx = id_map[nid]
            g.adj[:, idx] = 0  # Cut incoming edges
            g.priors[idx] = val
            g.marginals[idx] = val
    
    # Recompute
    forward(g)
    after = g.marginals.copy()
    
    # Restore
    g.adj = orig; g.priors = orig_p; g.marginals = orig_m
    
    # Compare
    outcomes = g.outcomes
    changes = {}
    for o in outcomes:
        changes[g.ids[o]] = {
            "before": round(float(orig_m[o]), 4),
            "after": round(float(after[o]), 4),
            "change": round(float(after[o] - orig_m[o]), 4),
        }
    
    top_before = g.ids[outcomes[np.argmax(orig_m[outcomes])]]
    top_after = g.ids[outcomes[np.argmax(after[outcomes])]]
    
    return {
        "interventions": interventions,
        "outcome_changes": changes,
        "prediction_flipped": top_before != top_after,
        "before_top": top_before,
        "after_top": top_after,
    }


# ══════════════════════════════════════════════════════════════
# 7. INTERACTIVE HTML REPORT — Self-contained, no server needed
# ══════════════════════════════════════════════════════════════

def export_html(g: Graph, result: dict, title: str = "TURNSTILE Analysis") -> str:
    """Generate a self-contained HTML report with inline CSS."""
    from .extra import to_mermaid, timeline, surprises
    
    ts = result.get("turnstile", {})
    conf = result.get("confidence", {})
    nec = result.get("necessities", {})
    perf = result.get("perf", {})
    ver = result.get("version", "?")
    n_nodes = perf.get("nodes", "?")
    n_edges = perf.get("edges", "?")
    ms = perf.get("ms", "?")
    conf_score = conf.get("score", "?")
    story = causal_story(g, result)
    rm = risk_matrix(g)
    tips = tipping_points(g)
    tree = scenario_tree(g)
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#e0e0e0;padding:40px;max-width:1000px;margin:0 auto}}
h1{{font-size:2.5em;background:linear-gradient(135deg,#f97316,#ef4444);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}}
h2{{color:#f97316;margin:30px 0 15px;border-bottom:1px solid #333;padding-bottom:8px}}
h3{{color:#ccc;margin:20px 0 10px}}
.card{{background:#111;border:1px solid #222;border-radius:12px;padding:20px;margin:15px 0}}
.metric{{display:inline-block;background:#1a1a2e;border-radius:8px;padding:12px 20px;margin:5px;text-align:center}}
.metric .val{{font-size:1.8em;font-weight:900;color:#f97316}}
.metric .lbl{{font-size:0.8em;color:#888}}
.bar{{height:20px;border-radius:4px;margin:4px 0}}
.bar-fill{{height:100%;border-radius:4px;background:linear-gradient(90deg,#f97316,#ef4444)}}
table{{width:100%;border-collapse:collapse;margin:10px 0}}
th{{background:#1a1a2e;padding:10px;text-align:left;color:#f97316}}
td{{padding:8px 10px;border-bottom:1px solid #222}}
.critical{{color:#ef4444;font-weight:700}}
.underrated{{color:#22c55e}}
.overrated{{color:#f59e0b}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.8em;margin:2px}}
.tag-critical{{background:#dc2626;color:#fff}}
.tag-swan{{background:#7c3aed;color:#fff}}
.tag-noise{{background:#666;color:#fff}}
pre{{background:#0d1117;border:1px solid #333;border-radius:8px;padding:15px;overflow-x:auto;font-size:0.85em;color:#e0e0e0}}
.story{{line-height:1.8;font-size:1.05em}}
</style></head><body>
<h1>⚡ {title}</h1>
<p style="color:#888">Generated by TURNSTILE v{ver} | {n_nodes} nodes | {ms}ms | 0 LLM calls</p>

<div style="margin:20px 0">
<span class="metric"><span class="val">{conf_score}%</span><br><span class="lbl">Confidence</span></span>
<span class="metric"><span class="val">{n_nodes}</span><br><span class="lbl">Nodes</span></span>
<span class="metric"><span class="val">{n_edges}</span><br><span class="lbl">Edges</span></span>
<span class="metric"><span class="val">{ms}ms</span><br><span class="lbl">Compute</span></span>
</div>
"""
    
    # Turnstile
    if ts.get("found"):
        html += f"""
<div class="card">
<h2>⚡ Point of No Return</h2>
<p style="font-size:1.3em"><strong>{ts['label']}</strong> at {ts.get('t_hours',0)}h</p>
<p>H_fwd={ts.get('fwd_H','?')} | H_inv={ts.get('inv_H','?')} | ∇H={ts.get('gradient','?')}</p>
<p style="color:#888;margin-top:8px">Before this moment: outcome was still open. After: locked in.</p>
</div>"""

    # Outcomes
    html += "<h2>📊 Outcomes</h2>"
    for lid, nd in nec.items():
        html += f"<div class='card'><h3>{nd['outcome']} (P={nd['prob']})</h3>"
        html += "<table><tr><th>Condition</th><th>Necessity</th><th></th></tr>"
        for c in nd.get("conditions", [])[:8]:
            if c.get("trivial"): continue
            w = int(c["necessity"] * 100)
            cr = "<span class='tag tag-critical'>★ CRITICAL</span>" if c.get("critical") else ""
            html += f"<tr><td>{c['label'][:50]}</td><td><div class='bar' style='width:200px;background:#222'><div class='bar-fill' style='width:{w}%'></div></div>{c['necessity']:.3f}</td><td>{cr}</td></tr>"
        html += "</table></div>"
    
    # Causal story
    html += f"<div class='card story'><h2>📖 Causal Story</h2><pre>{story}</pre></div>"
    
    # Risk Matrix
    html += "<h2>⚠️ Risk Matrix</h2><table><tr><th>Node</th><th>Probability</th><th>Impact</th><th>Quadrant</th></tr>"
    for n in rm.get("nodes", [])[:10]:
        q_class = {"CRITICAL":"critical","BLACK_SWAN":"underrated","NOISE":"overrated"}.get(n["quadrant"],"")
        q_tag = {"CRITICAL":"tag-critical","BLACK_SWAN":"tag-swan","NOISE":"tag-noise"}.get(n["quadrant"],"")
        html += f"<tr class='{q_class}'><td>{n['label'][:40]}</td><td>{n['probability']:.3f}</td><td>{n['impact']:.4f}</td><td><span class='tag {q_tag}'>{n['quadrant']}</span></td></tr>"
    html += "</table>"
    
    # Tipping points
    if tips:
        html += "<h2>🔄 Tipping Points</h2><table><tr><th>Node</th><th>Current</th><th>Tips At</th><th>Flips</th><th>Distance</th></tr>"
        for t in tips[:8]:
            html += f"<tr><td>{t['label'][:35]}</td><td>{t['current_value']:.3f}</td><td>{t['tipping_value']:.2f}</td><td>{t['flips_from']}→{t['flips_to']}</td><td>{t['distance']:.3f}</td></tr>"
        html += "</table>"
    
    # Scenario tree
    if tree.get("branches"):
        html += "<h2>🌳 Scenario Tree</h2>"
        for br in tree["branches"]:
            flip = "⚡ FLIPS!" if br["outcome_flips"] else "same"
            html += f"<div class='card'><h3>Branch: {br['branch_label'][:40]} (H={br['entropy']:.3f})</h3>"
            html += f"<p>If HIGH (0.9): top → <strong>{br['if_high']['top_outcome']}</strong> | If LOW (0.1): top → <strong>{br['if_low']['top_outcome']}</strong> {flip}</p>"
            html += "</div>"
    
    # Surprises
    surp = surprises(g)
    notable = [s for s in surp if s["type"] != "aligned"]
    if notable:
        html += "<h2>🔍 Surprising Findings</h2><table><tr><th>Node</th><th>P_fwd</th><th>P_inv</th><th>Gap</th><th>Type</th></tr>"
        for s in notable[:6]:
            t_class = "underrated" if s["type"] == "underrated" else "overrated"
            html += f"<tr class='{t_class}'><td>{s['label'][:35]}</td><td>{s['P_fwd']:.3f}</td><td>{s['P_inv']:.3f}</td><td>{s['gap']:+.3f}</td><td>{s['type'].upper()}</td></tr>"
        html += "</table>"
    
    # Timeline
    tl = timeline(g)
    html += f"<h2>📈 Timeline</h2><pre>{tl}</pre>"
    
    # Mermaid
    mermaid = to_mermaid(g)
    html += f"""<h2>🔗 DAG Structure</h2>
<pre>{mermaid}</pre>
<p style="color:#666;font-size:0.85em">Copy the above into <a href="https://mermaid.live" style="color:#f97316">mermaid.live</a> to see the interactive diagram.</p>"""
    
    html += """
<hr style="border-color:#333;margin:40px 0">
<p style="color:#555;text-align:center;font-style:italic">"What's happened, happened. But what had to be true?"</p>
<p style="color:#333;text-align:center;font-size:0.8em">TURNSTILE — Bayesian Temporal Inversion Engine</p>
</body></html>"""
    
    return html

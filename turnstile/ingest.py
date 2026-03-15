"""TURNSTILE Ingestion — Text/URL → CausalDAG, automatically.

The #1 missing piece. Without this, only devs can use Turnstile.
With this, anyone pastes text → gets inversion.

Pipeline:
  Input (text/URL/dict) → LLM extracts causal structure → JSON → Builder → Graph
  
  With 5-layer defense against LLM garbage:
    Layer 1: Strict JSON schema in prompt
    Layer 2: Regex extraction if JSON parsing fails
    Layer 3: Node/edge sanitization (dedup, cycle removal, orphan cleanup)
    Layer 4: Fallback to simple 3-node DAG if everything fails
    Layer 5: Structural validation before returning
"""

import json
import re
import hashlib
import numpy as np
from typing import Optional, Callable


EXTRACT_SYSTEM = """You are a causal structure extractor.
Given text, identify the causal chain: what causes what, with what probability.
You MUST return ONLY valid JSON. No markdown. No explanation. Just JSON."""


EXTRACT_PROMPT = """Analyze this text and extract its causal structure as a DAG (directed acyclic graph).

TEXT:
{text}

Return ONLY this JSON structure (no other text):
{{
  "title": "short title of the scenario",
  "nodes": [
    {{"id": "short_unique_id", "label": "what this event/condition is", "type": "seed", "prior": 1.0, "time_hours": 0}},
    {{"id": "evt1", "label": "first consequence", "type": "event", "prior": 0.8, "time_hours": 24}},
    {{"id": "out1", "label": "possible outcome", "type": "outcome", "prior": 0.4, "time_hours": 720}}
  ],
  "edges": [
    {{"from": "short_unique_id", "to": "evt1", "prob": 0.8, "delay_hours": 24}},
    {{"from": "evt1", "to": "out1", "prob": 0.6, "delay_hours": 200}}
  ]
}}

Rules:
- 1 seed node (the triggering event, type="seed", prior=1.0, time=0)
- 5-15 event nodes (intermediate steps, type="event")
- 2-5 outcome nodes (final results, type="outcome")
- Edges go forward in time (from→to, lower time→higher time)
- prob = conditional probability P(to happens | from happened), between 0.05 and 0.95
- prior = independent probability, between 0.1 and 0.95 (seed=1.0)
- time_hours = when this happens relative to seed (0 = now)
- IDs must be short, unique, no spaces (use underscores)
- No cycles allowed
- Every non-seed node must have at least one incoming edge"""


async def text_to_dag(
    llm_call: Callable,
    text: str,
    max_retries: int = 2,
) -> tuple:  # (Graph, dict metadata)
    """Convert free text to a CausalDAG.
    
    Returns (Graph, metadata_dict) or raises ValueError.
    """
    # Truncate very long text
    text = text[:3000]
    
    prompt = EXTRACT_PROMPT.format(text=text)
    
    raw_json = None
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            response = await llm_call(prompt, EXTRACT_SYSTEM)
            raw_json = _parse_llm_json(response)
            
            if raw_json and raw_json.get("nodes"):
                break
        except Exception as e:
            last_error = str(e)
            # On retry, add hint about the error
            if attempt < max_retries:
                prompt = f"Previous attempt had error: {last_error}\n\nTry again. Return ONLY valid JSON.\n\n{EXTRACT_PROMPT.format(text=text)}"
    
    if not raw_json or not raw_json.get("nodes"):
        # Layer 4: Fallback — create minimal DAG from text
        raw_json = _fallback_dag(text)
    
    # Layer 3: Sanitize
    raw_json = _sanitize_dag(raw_json)
    
    # Build graph
    g = _json_to_graph(raw_json)
    
    # Layer 5: Validate
    if g.n < 3:
        raise ValueError(f"DAG too small: {g.n} nodes")
    if g.edge_count < 2:
        raise ValueError(f"DAG too sparse: {g.edge_count} edges")
    
    metadata = {
        "title": raw_json.get("title", ""),
        "nodes": g.n,
        "edges": g.edge_count,
        "outcomes": len(g.outcomes),
        "retries": max_retries + 1,
    }
    
    return g, metadata


def _parse_llm_json(text: str) -> Optional[dict]:
    """Layer 1+2: Parse JSON from LLM response with fallback regex."""
    # Strip markdown code blocks
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON object
    match = re.search(r'\{[^{}]*"nodes"[^{}]*\[.*?\].*?"edges"[^{}]*\[.*?\].*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    # Try finding any JSON-like structure
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    return None


def _fallback_dag(text: str) -> dict:
    """Layer 4: Create minimal DAG from text when LLM fails."""
    # Extract first sentence as seed
    sentences = re.split(r'[.!?]\s', text[:500])
    seed_text = sentences[0] if sentences else text[:100]
    
    # Create a simple 5-node DAG
    seed_id = "seed"
    return {
        "title": seed_text[:50],
        "nodes": [
            {"id": seed_id, "label": seed_text[:80], "type": "seed", "prior": 1.0, "time_hours": 0},
            {"id": "reaction", "label": "Initial reaction and response", "type": "event", "prior": 0.85, "time_hours": 24},
            {"id": "escalation", "label": "Situation escalates", "type": "event", "prior": 0.5, "time_hours": 168},
            {"id": "out_pos", "label": "Positive resolution", "type": "outcome", "prior": 0.4, "time_hours": 720},
            {"id": "out_neg", "label": "Negative outcome", "type": "outcome", "prior": 0.3, "time_hours": 720},
        ],
        "edges": [
            {"from": seed_id, "to": "reaction", "prob": 0.9, "delay_hours": 24},
            {"from": "reaction", "to": "escalation", "prob": 0.5, "delay_hours": 144},
            {"from": "reaction", "to": "out_pos", "prob": 0.4, "delay_hours": 696},
            {"from": "escalation", "to": "out_neg", "prob": 0.6, "delay_hours": 552},
            {"from": "escalation", "to": "out_pos", "prob": 0.2, "delay_hours": 552},
        ],
    }


def _sanitize_dag(data: dict) -> dict:
    """Layer 3: Clean up LLM-generated DAG structure."""
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    
    if not nodes:
        return data
    
    # Deduplicate node IDs
    seen_ids = set()
    clean_nodes = []
    for n in nodes:
        nid = str(n.get("id", "")).strip().replace(" ", "_")[:30]
        if not nid or nid in seen_ids:
            nid = f"n_{hashlib.md5(str(n).encode()).hexdigest()[:6]}"
        seen_ids.add(nid)
        
        # Clamp values
        prior = float(n.get("prior", 0.5))
        prior = max(0.05, min(0.99, prior))
        ntype = n.get("type", "event")
        if ntype not in ("seed", "event", "outcome"):
            ntype = "event"
        if ntype == "seed":
            prior = 1.0
        
        clean_nodes.append({
            "id": nid,
            "label": str(n.get("label", nid))[:100],
            "type": ntype,
            "prior": prior,
            "time_hours": max(0, float(n.get("time_hours", n.get("time", 0)))),
        })
    
    # Ensure at least one seed
    has_seed = any(n["type"] == "seed" for n in clean_nodes)
    if not has_seed and clean_nodes:
        clean_nodes[0]["type"] = "seed"
        clean_nodes[0]["prior"] = 1.0
    
    # Ensure at least one outcome
    has_outcome = any(n["type"] == "outcome" for n in clean_nodes)
    if not has_outcome and len(clean_nodes) >= 2:
        clean_nodes[-1]["type"] = "outcome"
    
    # Build ID index
    id_set = {n["id"] for n in clean_nodes}
    time_map = {n["id"]: n["time_hours"] for n in clean_nodes}
    
    # Clean edges
    clean_edges = []
    edge_set = set()
    for e in edges:
        src = str(e.get("from", "")).strip().replace(" ", "_")[:30]
        tgt = str(e.get("to", "")).strip().replace(" ", "_")[:30]
        
        # Skip invalid
        if src not in id_set or tgt not in id_set:
            continue
        if src == tgt:
            continue
        if (src, tgt) in edge_set:
            continue
        
        # Enforce forward time (source must be at same time or earlier)
        if time_map.get(src, 0) > time_map.get(tgt, 0) + 0.01:
            continue
        
        prob = float(e.get("prob", 0.5))
        prob = max(0.05, min(0.95, prob))
        delay = max(0, float(e.get("delay_hours", e.get("delay", 0))))
        gate = e.get("gate", "or")
        if gate not in ("or", "and"):
            gate = "or"
        
        edge_set.add((src, tgt))
        clean_edges.append({
            "from": src, "to": tgt, "prob": prob,
            "delay_hours": delay, "gate": gate,
        })
    
    # Ensure every non-seed node has at least one incoming edge
    targets = {e["to"] for e in clean_edges}
    seeds = [n["id"] for n in clean_nodes if n["type"] == "seed"]
    seed_id = seeds[0] if seeds else clean_nodes[0]["id"]
    
    for n in clean_nodes:
        if n["id"] != seed_id and n["id"] not in targets:
            # Connect from seed or nearest earlier node
            clean_edges.append({
                "from": seed_id, "to": n["id"],
                "prob": 0.5, "delay_hours": n["time_hours"], "gate": "or",
            })
    
    data["nodes"] = clean_nodes
    data["edges"] = clean_edges
    return data


def _json_to_graph(data: dict):
    """Convert sanitized JSON to Graph object."""
    from .engine import Builder
    
    b = Builder()
    for n in data.get("nodes", []):
        b.node(n["id"], n.get("label", ""), n.get("type", "event"),
               n.get("prior", 0.5), n.get("time_hours", 0))
    
    for e in data.get("edges", []):
        b.edge(e["from"], e["to"], e.get("prob", 0.5),
               e.get("delay_hours", 0), e.get("gate", "or"))
    
    for c in data.get("correlations", []):
        b.corr(c.get("n1", ""), c.get("n2", ""), c.get("corr", 0.3))
    
    return b.build()


# ══════════════════════════════════════════════════════════════
# Semantic matching for cross-validation
# ══════════════════════════════════════════════════════════════

def _normalize_label(label: str) -> str:
    """Normalize a label for fuzzy matching."""
    label = label.lower().strip()
    for w in ["the", "a", "an", "is", "are", "was", "were", "will", "would", "could",
              "might", "may", "should", "that", "this", "with", "from", "into", "for", "of", "in", "on"]:
        label = re.sub(rf'\b{w}\b', '', label)
    label = re.sub(r'\s+', ' ', label).strip()
    return label


def _simple_stem(word: str) -> str:
    """Crude stemming — strips common suffixes. Not Porter, but fast."""
    if len(word) <= 4:
        return word
    for suffix in ["ation", "tion", "sion", "ment", "ness", "ting", "ing", "ies",
                   "ates", "ated", "ally", "ous", "ive", "ful", "ers", "est",
                   "ed", "ly", "er", "es", "al", "en", "ty", "ry", "s"]:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word


def _extract_keywords(label: str, top_k: int = 6) -> set:
    """Extract top keywords from a label, stemmed."""
    label = _normalize_label(label)
    words = label.split()
    # Stem all words
    stemmed = [_simple_stem(w) for w in words if len(w) > 2]
    # Keep longest/most informative
    stemmed.sort(key=len, reverse=True)
    return set(stemmed[:top_k])


def semantic_similarity(label1: str, label2: str) -> float:
    """Keyword overlap similarity (0-1). No embeddings needed."""
    kw1 = _extract_keywords(label1)
    kw2 = _extract_keywords(label2)
    if not kw1 or not kw2:
        return 0.0
    overlap = len(kw1 & kw2)
    return overlap / max(len(kw1), len(kw2))


def match_nodes_across_dags(dag_labels: list[list[str]], threshold: float = 0.4) -> dict:
    """Find matching nodes across multiple DAGs by label similarity.
    
    Returns: {cluster_id: [(dag_idx, node_idx, label), ...]}
    """
    clusters = {}
    cluster_id = 0
    assigned = set()  # (dag_idx, node_idx)
    
    for i, labels_i in enumerate(dag_labels):
        for ni, label_i in enumerate(labels_i):
            if (i, ni) in assigned:
                continue
            
            cluster = [(i, ni, label_i)]
            assigned.add((i, ni))
            
            for j, labels_j in enumerate(dag_labels):
                if j <= i:
                    continue
                best_match = -1
                best_sim = 0
                for nj, label_j in enumerate(labels_j):
                    if (j, nj) in assigned:
                        continue
                    sim = semantic_similarity(label_i, label_j)
                    if sim > best_sim and sim >= threshold:
                        best_sim = sim
                        best_match = nj
                
                if best_match >= 0:
                    cluster.append((j, best_match, labels_j[best_match]))
                    assigned.add((j, best_match))
            
            if len(cluster) >= 2:  # Only keep multi-DAG clusters
                clusters[cluster_id] = cluster
                cluster_id += 1
    
    return clusters

let pyodide = null;
let engineLoaded = false;

export async function initEngine(onProgress) {
  if (engineLoaded) return;

  onProgress?.("Loading Python runtime...");
  pyodide = await window.loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.27.0/full/"
  });

  onProgress?.("Loading numpy & scipy...");
  await pyodide.loadPackage(['numpy', 'scipy']);

  onProgress?.("Loading TURNSTILE engine...");
  await pyodide.runPythonAsync(ENGINE_PY);
  await pyodide.runPythonAsync(EXTRA_PY);
  await pyodide.runPythonAsync(POWER_PY);
  await pyodide.runPythonAsync(BRIDGE_PY);

  engineLoaded = true;
  onProgress?.("Engine ready.");
}

export function isEngineReady() {
  return engineLoaded;
}

export async function runFullAnalysis(dagJson) {
  if (!engineLoaded) throw new Error("Engine not loaded");

  pyodide.globals.set("dag_input", JSON.stringify(dagJson));

  const result = await pyodide.runPythonAsync(`
import json
dag = json.loads(dag_input)
result = run_full_analysis(dag)
json.dumps(result, cls=NpEncoder)
  `);

  return JSON.parse(result);
}

const ENGINE_PY = `
import numpy as np
from scipy import stats
import json, time

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)

class Graph:
    def __init__(self):
        self.n = 0
        self.ids = []
        self.labels = []
        self.types = []
        self.priors = None
        self.times = None
        self.adj = None
        self.delays = None
        self.gates = []
        self.correlations = {}
        self.half_life = None
        self._hl = None
        self.marginals = None
        self.inv_adj = None
        self.inv_probs = None
        self.fwd_H = None
        self.inv_H = None

class Builder:
    def __init__(self):
        self._nodes = []
        self._edges = []
        self._corrs = []

    def node(self, id, label, type, prior, time):
        self._nodes.append({'id': id, 'label': label, 'type': type, 'prior': prior, 'time': time})
        return self

    def edge(self, src, tgt, prob, delay=0, gate='or'):
        self._edges.append({'src': src, 'tgt': tgt, 'prob': prob, 'delay': delay, 'gate': gate})
        return self

    def corr(self, n1, n2, corr):
        self._corrs.append({'n1': n1, 'n2': n2, 'corr': corr})
        return self

    def build(self):
        g = Graph()
        g.n = len(self._nodes)
        if g.n == 0:
            g.priors = np.array([])
            g.times = np.array([])
            g.adj = np.zeros((0, 0))
            g.delays = np.zeros((0, 0))
            return g
        g.ids = [n['id'] for n in self._nodes]
        g.labels = [n['label'] for n in self._nodes]
        g.types = [n['type'] for n in self._nodes]
        g.priors = np.array([max(0.001, min(0.999, n['prior'])) for n in self._nodes])
        g.times = np.array([n['time'] for n in self._nodes], dtype=float)
        g.adj = np.zeros((g.n, g.n))
        g.delays = np.zeros((g.n, g.n))
        g.gates = ['or'] * g.n
        idx = {id: i for i, id in enumerate(g.ids)}
        for e in self._edges:
            if e['src'] in idx and e['tgt'] in idx:
                i, j = idx[e['src']], idx[e['tgt']]
                g.adj[i, j] = max(0.001, min(0.999, e['prob']))
                g.delays[i, j] = e.get('delay', 0)
                if e.get('gate', 'or') != 'or':
                    g.gates[j] = e['gate']
        for c in self._corrs:
            if c['n1'] in idx and c['n2'] in idx:
                g.correlations[(idx[c['n1']], idx[c['n2']])] = c['corr']
                g.correlations[(idx[c['n2']], idx[c['n1']])] = c['corr']
        pos = g.times[g.times > 0]
        if len(pos) >= 2:
            span = pos.max() - pos.min()
            g._hl = max(24.0, min(2000.0, span * 0.3))
        elif len(pos) == 1:
            g._hl = max(24.0, pos[0] * 0.5)
        else:
            g._hl = 168.0
        g.half_life = g._hl
        return g

def forward(g):
    if g.n == 0: return
    td = np.where(g.delays > 0, np.exp(-0.693 * g.delays / g._hl), 1.0)
    g.marginals = g.priors.copy()
    order = np.argsort(g.times)
    for j in order:
        parents = np.where(g.adj[:, j] > 0)[0]
        if len(parents) == 0:
            continue
        contribs = []
        for pi in parents:
            c = g.adj[pi, j] * td[pi, j] * g.marginals[pi]
            for pk in parents:
                if pk != pi and (pi, pk) in g.correlations:
                    c *= (1 - g.correlations[(pi, pk)] * 0.15)
            contribs.append(min(c, 0.999))
        if g.gates[j] in ('and', 'and-min'):
            g.marginals[j] = min(contribs) if contribs else g.priors[j]
        elif g.gates[j] == 'and-prod':
            g.marginals[j] = np.prod(contribs) if contribs else g.priors[j]
        else:
            g.marginals[j] = 1 - np.prod([1 - c for c in contribs])
        g.marginals[j] = max(0.001, min(0.999, g.marginals[j]))

def invert_edges(g):
    if g.n == 0: return
    if g.marginals is None: forward(g)
    g.inv_adj = np.zeros_like(g.adj)
    for j in range(g.n):
        parents = np.where(g.adj[:, j] > 0)[0]
        if len(parents) == 0:
            continue
        raw = np.zeros(len(parents))
        for k, pi in enumerate(parents):
            raw[k] = g.adj[pi, j] * g.marginals[pi] / max(g.marginals[j], 0.001)
            for pk in parents:
                if pk != pi and (pi, pk) in g.correlations:
                    raw[k] *= (1 - g.correlations[(pi, pk)] * 0.3)
        total = raw.sum()
        if total > 1:
            raw = raw / total
        for k, pi in enumerate(parents):
            g.inv_adj[pi, j] = max(0, min(1, raw[k]))
    g.inv_probs = np.zeros(g.n)
    outcomes = [i for i in range(g.n) if g.types[i] == 'outcome']
    for i in outcomes:
        g.inv_probs[i] = 1.0
    rev_order = np.argsort(-g.times)
    for j in rev_order:
        children = np.where(g.inv_adj[j, :] > 0)[0]
        if len(children) == 0:
            continue
        weighted = sum(g.inv_adj[j, c] * g.inv_probs[c] * g.marginals[c] for c in children)
        denom = sum(g.marginals[c] for c in children)
        g.inv_probs[j] = max(0, min(1, weighted / max(denom, 0.001)))

def entropy(g):
    if g.n == 0: return
    g.fwd_H = np.zeros(g.n)
    g.inv_H = np.zeros(g.n)
    for i in range(g.n):
        out_edges = g.adj[i, :]
        out_vals = out_edges[out_edges > 0]
        if len(out_vals) > 0:
            total = out_vals.sum()
            if total > 0:
                probs = np.append(out_vals / (total + 1), [1 / (total + 1)])
                probs = probs[probs > 0]
                g.fwd_H[i] = -np.sum(probs * np.log2(probs))
        in_edges = g.inv_adj[:, i]
        in_vals = in_edges[in_edges > 0]
        if len(in_vals) > 0:
            inv2 = (g.inv_adj @ g.inv_adj)[:, i] * 0.5
            combined = in_vals.copy()
            inv2_vals = inv2[inv2 > 0]
            if len(inv2_vals) > 0:
                weight = 0.5 if len(in_vals) > 1 else 0.3
                combined = np.concatenate([combined * (1 - weight), inv2_vals * weight])
            total = combined.sum()
            if total > 0:
                probs = combined / total
                probs = probs[probs > 0]
                g.inv_H[i] = -np.sum(probs * np.log2(probs))

def find_turnstile(g):
    if g.n == 0: return {'found': False}
    if g.fwd_H is None: entropy(g)
    grad = g.fwd_H - g.inv_H
    conn = np.sum(g.adj > 0, axis=0) + np.sum(g.adj > 0, axis=1)
    max_conn = max(conn.max(), 1)
    score = np.abs(grad) - 0.001 * conn / max_conn
    non_seed = [i for i in range(g.n) if g.types[i] not in ('seed', 'outcome')]
    if not non_seed:
        non_seed = list(range(g.n))
    best = min(non_seed, key=lambda i: score[i])
    return {
        'found': True,
        'id': g.ids[best],
        'label': g.labels[best],
        't_hours': float(g.times[best]),
        'gradient': float(grad[best]),
        'fwd_H': float(g.fwd_H[best]),
        'inv_H': float(g.inv_H[best]),
    }

def necessity(g):
    if g.n == 0: return {}
    results = {}
    outcomes = [i for i in range(g.n) if g.types[i] == 'outcome']
    for oi in outcomes:
        conditions = []
        for j in range(g.n):
            if j == oi or g.types[j] == 'outcome':
                continue
            nec_val = g.inv_probs[j] if g.inv_probs is not None else 0
            conditions.append({
                'id': g.ids[j],
                'label': g.labels[j],
                'necessity': float(nec_val),
                'critical': nec_val > 0.3,
                'trivial': g.types[j] == 'seed',
            })
        conditions.sort(key=lambda x: x['necessity'], reverse=True)
        results[g.ids[oi]] = {
            'outcome': g.labels[oi],
            'prob': float(g.marginals[oi]),
            'conditions': conditions,
        }
    return results

def monte_carlo(g, n=200):
    if g.n == 0: return {'nodes': {}}
    original = g.priors.copy()
    samples = np.zeros((n, g.n))
    for s in range(n):
        noise = np.random.uniform(-0.15, 0.15, g.n)
        g.priors = np.clip(original * (1 + noise), 0.001, 0.999)
        forward(g)
        samples[s] = g.marginals.copy()
    g.priors = original
    forward(g)
    nodes = {}
    for i in range(g.n):
        m = samples[:, i].mean()
        s = samples[:, i].std()
        nodes[g.ids[i]] = {
            'mean': float(m),
            'std': float(s),
            'ci95': [float(m - 1.96 * s), float(m + 1.96 * s)],
        }
    return {'nodes': nodes, 'n_sims': n}

def sensitivity(g):
    if g.n == 0: return []
    results = []
    original = g.priors.copy()
    forward(g)
    base = g.marginals.copy()
    for i in range(g.n):
        g.priors = original.copy()
        g.priors[i] = min(0.999, original[i] + 0.05)
        forward(g)
        deriv = (g.marginals - base) / 0.05
        results.append({
            'id': g.ids[i],
            'label': g.labels[i],
            'max_effect': float(np.abs(deriv).max()),
            'effects': {g.ids[j]: float(deriv[j]) for j in range(g.n) if abs(deriv[j]) > 0.001},
        })
    g.priors = original
    forward(g)
    results.sort(key=lambda x: x['max_effect'], reverse=True)
    return results

def do_calculus(g):
    if g.n == 0: return []
    results = []
    original_adj = g.adj.copy()
    original_priors = g.priors.copy()
    forward(g)
    base = g.marginals.copy()
    for i in range(g.n):
        if g.types[i] in ('seed', 'outcome'):
            continue
        g.adj = original_adj.copy()
        g.adj[:, i] = 0
        g.priors = original_priors.copy()
        g.priors[i] = 0.95
        forward(g)
        high = g.marginals.copy()
        g.priors[i] = 0.05
        forward(g)
        low = g.marginals.copy()
        power = float(np.abs(high - low).sum())
        results.append({
            'id': g.ids[i],
            'label': g.labels[i],
            'power': power,
        })
    g.adj = original_adj
    g.priors = original_priors
    forward(g)
    results.sort(key=lambda x: x['power'], reverse=True)
    return results

def robustness(g):
    if g.n == 0: return []
    results = []
    forward(g)
    base = g.marginals.copy()
    for i in range(g.n):
        original = g.priors[i]
        diffs = []
        for v in [0.01, 0.25, 0.5, 0.75, 0.99]:
            g.priors[i] = v
            forward(g)
            diffs.append(float(np.abs(g.marginals - base).sum()))
        g.priors[i] = original
        forward(g)
        results.append({
            'id': g.ids[i],
            'label': g.labels[i],
            'robustness': float(1 - np.mean(diffs) / max(g.n, 1)),
        })
    return results

def kl_divergence(g):
    if g.n == 0 or g.inv_probs is None: return 0.0
    p = np.clip(g.marginals, 0.001, 0.999)
    q = np.clip(g.inv_probs, 0.001, 0.999)
    kl = np.sum(p * np.log(p / q) + (1 - p) * np.log((1 - p) / (1 - q)))
    return float(kl / g.n)

def critical_path(g):
    if g.n == 0: return {}
    results = {}
    outcomes = [i for i in range(g.n) if g.types[i] == 'outcome']
    seeds = [i for i in range(g.n) if g.types[i] == 'seed']
    for oi in outcomes:
        weights = np.where(g.adj > 0, -np.log(np.clip(g.adj, 0.001, 0.999)), np.inf)
        dist = np.full(g.n, np.inf)
        prev = np.full(g.n, -1, dtype=int)
        for si in seeds:
            dist[si] = 0
        for _ in range(g.n):
            for i in range(g.n):
                for j in range(g.n):
                    if weights[i, j] < np.inf and dist[i] + weights[i, j] < dist[j]:
                        dist[j] = dist[i] + weights[i, j]
                        prev[j] = i
        path = []
        cur = oi
        while cur >= 0:
            path.append({'id': g.ids[cur], 'label': g.labels[cur]})
            cur = prev[cur]
        path.reverse()
        results[g.ids[oi]] = {
            'found': len(path) > 1,
            'path': path,
            'prob': float(np.exp(-dist[oi])) if dist[oi] < np.inf else 0,
        }
    return results

def confidence_score(g, mc_result=None):
    kl = kl_divergence(g)
    kl_score = max(0, 100 - kl * 100)
    rob = robustness(g)
    rob_score = np.mean([r['robustness'] for r in rob]) * 100 if rob else 50
    mc_score = 95.0
    if mc_result and mc_result.get('nodes'):
        stds = [v['std'] for v in mc_result['nodes'].values()]
        mc_score = max(0, 100 - np.mean(stds) * 200) if stds else 95
    density = min(100, np.sum(g.adj > 0) / max(g.n, 1) * 50)
    score = (kl_score * 0.3 + rob_score * 0.2 + mc_score * 0.3 + density * 0.2)
    return {
        'score': round(min(100, max(0, score)), 1),
        'breakdown': {
            'kl_agreement': round(kl_score, 1),
            'robustness': round(rob_score, 1),
            'mc_stability': round(mc_score, 1),
            'graph_density': round(density, 1),
        }
    }

def analyze(g, mc_on=True, mc_n=200):
    t0 = time.time()
    if g.n == 0:
        return {"perf": {"nodes": 0, "edges": 0, "ms": 0}, "version": "3.3.0"}
    forward(g)
    invert_edges(g)
    entropy(g)
    ts = find_turnstile(g)
    nec = necessity(g)
    mc = monte_carlo(g, mc_n) if mc_on else {'nodes': {}}
    sens = sensitivity(g)
    do_calc = do_calculus(g)
    crit = critical_path(g)
    conf = confidence_score(g, mc)
    ms = (time.time() - t0) * 1000
    return {
        "version": "3.3.0",
        "llm_calls": 0,
        "perf": {"nodes": g.n, "edges": int(np.sum(g.adj > 0)), "ms": round(ms, 1)},
        "turnstile": ts,
        "necessities": nec,
        "monte_carlo": mc,
        "sensitivity": sens[:5],
        "do_calculus": do_calc[:5],
        "critical_paths": crit,
        "confidence": conf,
        "kl_divergence": kl_divergence(g),
    }
`;

const EXTRA_PY = `
def surprises(g):
    if g.n == 0: return []
    results = []
    for i in range(g.n):
        if g.types[i] in ('seed', 'outcome'): continue
        fwd = g.marginals[i]
        inv = g.inv_probs[i] if g.inv_probs is not None else 0
        gap = inv - fwd
        results.append({
            'id': g.ids[i], 'label': g.labels[i],
            'P_fwd': float(fwd), 'P_inv': float(inv),
            'gap': float(gap), 'abs_gap': float(abs(gap)),
            'type': 'underrated' if gap > 0.1 else ('overrated' if gap < -0.1 else 'aligned'),
        })
    results.sort(key=lambda x: x['abs_gap'], reverse=True)
    return results

def bottlenecks(g):
    if g.n == 0: return []
    results = []
    for i in range(g.n):
        out_count = int(np.sum(g.adj[i, :] > 0))
        in_count = int(np.sum(g.adj[:, i] > 0))
        total_paths = int(np.sum(g.adj > 0))
        paths_through = out_count * in_count
        score = paths_through / max(total_paths, 1)
        results.append({
            'id': g.ids[i], 'label': g.labels[i],
            'bottleneck_score': float(score),
            'paths_blocked': paths_through,
            'total_paths': total_paths,
            'is_bottleneck': score > 0.2,
        })
    results.sort(key=lambda x: x['bottleneck_score'], reverse=True)
    return results

def tipping_points(g, resolution=20):
    if g.n == 0: return []
    results = []
    forward(g)
    outcomes = [i for i in range(g.n) if g.types[i] == 'outcome']
    if not outcomes: return []
    base_top = max(outcomes, key=lambda i: g.marginals[i])
    original = g.priors.copy()
    for i in range(g.n):
        if g.types[i] in ('seed', 'outcome'): continue
        found_tip = None
        for v in np.linspace(0.01, 0.99, resolution):
            g.priors[i] = v
            forward(g)
            new_top = max(outcomes, key=lambda o: g.marginals[o])
            if new_top != base_top:
                found_tip = v
                break
        g.priors = original.copy()
        forward(g)
        if found_tip is not None:
            results.append({
                'id': g.ids[i], 'label': g.labels[i],
                'current_value': float(original[i]),
                'tipping_value': float(found_tip),
                'distance': float(abs(original[i] - found_tip)),
                'flips_from': g.ids[base_top],
                'flips_to': g.ids[new_top],
            })
    results.sort(key=lambda x: x['distance'])
    return results
`;

const POWER_PY = `
def multi_what_if(g, interventions):
    if g.n == 0: return {'outcome_changes': {}, 'prediction_flipped': False}
    forward(g)
    before = {g.ids[i]: float(g.marginals[i]) for i in range(g.n) if g.types[i] == 'outcome'}
    top_before = max(before, key=before.get) if before else None
    original = g.priors.copy()
    idx = {id: i for i, id in enumerate(g.ids)}
    for node_id, val in interventions.items():
        if node_id in idx:
            g.priors[idx[node_id]] = val
    forward(g)
    after = {g.ids[i]: float(g.marginals[i]) for i in range(g.n) if g.types[i] == 'outcome'}
    top_after = max(after, key=after.get) if after else None
    g.priors = original
    forward(g)
    changes = {}
    for oid in before:
        changes[oid] = {'before': before[oid], 'after': after.get(oid, 0), 'delta': after.get(oid, 0) - before[oid]}
    return {'outcome_changes': changes, 'prediction_flipped': top_before != top_after}
`;

const BRIDGE_PY = `
def run_full_analysis(dag_json):
    b = Builder()
    for n in dag_json.get('nodes', []):
        b.node(n['id'], n.get('label', ''), n.get('type', 'event'),
               n.get('prior', 0.5), n.get('time', 0))
    for e in dag_json.get('edges', []):
        b.edge(e['src'], e['tgt'], e.get('prob', 0.5),
               e.get('delay', 0), e.get('gate', 'or'))
    for c in dag_json.get('correlations', []):
        b.corr(c['n1'], c['n2'], c.get('corr', 0.3))

    g = b.build()

    result = analyze(g, mc_on=True, mc_n=200)

    forward(g)
    invert_edges(g)
    entropy(g)
    result['surprises'] = surprises(g)[:6]
    result['bottlenecks'] = bottlenecks(g)[:5]
    result['tipping_points'] = tipping_points(g)[:5]

    result['math'] = {
        'nodes': g.ids[:8],
        'adj': g.adj[:8, :8].tolist(),
        'marginals': g.marginals[:8].tolist(),
        'inv': g.inv_adj[:8, :8].tolist(),
        'efwd': g.fwd_H[:8].tolist(),
        'einv': g.inv_H[:8].tolist(),
        'tidx': int(np.argmin(np.abs(g.fwd_H[:8] - g.inv_H[:8]))) if g.n > 0 else 0,
    }

    return result
`;

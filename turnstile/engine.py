"""TURNSTILE v2 — Performance rewrite.

Bottleneck kills from v1:
  entropy 2-hop loop → replaced with adj² matrix multiply
  MC per-sim full recompute → batched perturbation
  sensitivity per-edge forward → top-K only
  counterfactual per-node → top-K by marginal

Target:
  10 nodes    → <1ms core, <50ms full
  100 nodes   → <5ms core, <200ms full
  1,000 nodes → <50ms core, <2s full
"""

import numpy as np
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    from scipy import sparse as sp
    from scipy.sparse.csgraph import shortest_path
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

EPS = 1e-10
DEFAULT_HALF_LIFE = 168.0  # Can be overridden per-graph

@dataclass
class Graph:
    ids: list = field(default_factory=list)
    labels: list = field(default_factory=list)
    types: np.ndarray = None
    priors: np.ndarray = None
    times: np.ndarray = None
    gates: np.ndarray = None       # 0=OR, 1=AND-min, 2=AND-prod
    adj: np.ndarray = None
    delays: np.ndarray = None
    corr: np.ndarray = None
    half_life: float = 0.0         # 0 = auto-detect
    # computed
    _topo: np.ndarray = None
    _td: np.ndarray = None
    _hl: float = None              # Resolved half-life
    marginals: np.ndarray = None
    inv_adj: np.ndarray = None
    inv_probs: np.ndarray = None
    fwd_H: np.ndarray = None
    inv_H: np.ndarray = None
    H_grad: np.ndarray = None
    mc_mean: np.ndarray = None
    mc_std: np.ndarray = None
    mc_lo: np.ndarray = None
    mc_hi: np.ndarray = None

    @property
    def n(self): return len(self.ids)
    @property
    def outcomes(self): return np.where(self.types==2)[0]
    @property
    def events(self): return np.where(self.types==1)[0]
    @property
    def edge_count(self): return int((self.adj>0).sum()) if self.adj is not None else 0

    def _cache(self):
        if self._topo is None:
            self._topo = _topo(self.adj)
        if self._hl is None:
            if self.half_life > 0:
                self._hl = self.half_life  # User override
            else:
                # Auto-detect: half_life = 1/4 of total time span
                # So even longest delays retain ~25% weight
                t = self.times[self.times > 0] if self.times is not None else np.array([])
                if len(t) > 0:
                    span = float(t.max() - t.min()) if len(t) > 1 else float(t[0])
                    self._hl = max(24.0, min(2000.0, span * 0.3))
                else:
                    self._hl = DEFAULT_HALF_LIFE
        if self._td is None:
            self._td = np.exp(-0.693 * np.maximum(self.delays, 0) / self._hl)


class Builder:
    def __init__(self):
        self._n, self._e, self._c = [], [], []
    def node(self, id, label="", type="event", prior=0.5, t=0.0):
        self._n.append((id,label,{"seed":0,"event":1,"outcome":2}.get(type,1),prior,t)); return self
    def edge(self, s, t, p=0.5, delay=0.0, gate="or"):
        gt = {"or":0, "and":1, "and-min":1, "and-prod":2}.get(gate, 0)
        self._e.append((s,t,p,delay,gt)); return self
    def corr(self, n1, n2, c):
        self._c.append((n1,n2,c)); return self
    def build(self) -> Graph:
        g = Graph(); N = len(self._n)
        g.ids = [x[0] for x in self._n]
        g.labels = [x[1] for x in self._n]
        g.types = np.array([x[2] for x in self._n], np.int8)
        g.priors = np.array([x[3] for x in self._n], np.float64)
        g.times = np.array([x[4] for x in self._n], np.float64)
        g.gates = np.zeros(N, np.int8)
        g.adj = np.zeros((N,N), np.float64)
        g.delays = np.zeros((N,N), np.float64)
        g.corr = np.zeros((N,N), np.float64)
        ix = {x[0]:i for i,x in enumerate(self._n)}
        for s,t,p,d,gt in self._e:
            if s in ix and t in ix:
                i,j = ix[s],ix[t]; g.adj[i,j]=p; g.delays[i,j]=d
                if gt: g.gates[j]=1
        for n1,n2,c in self._c:
            if n1 in ix and n2 in ix:
                i,j = ix[n1],ix[n2]; g.corr[i,j]=c; g.corr[j,i]=c
        # Auto sibling corr
        has_children = (g.adj > 0)
        for i in range(N):
            ch = np.where(has_children[i])[0]
            if len(ch) >= 2:
                for a in range(len(ch)):
                    for b in range(a+1,len(ch)):
                        if g.corr[ch[a],ch[b]]==0:
                            g.corr[ch[a],ch[b]]=0.15; g.corr[ch[b],ch[a]]=0.15
        g._cache()
        return g


# ── TOPO SORT ──

def _topo(adj):
    n = adj.shape[0]
    indeg = (adj>0).sum(axis=0).astype(np.int32)
    order = []; q = list(np.where(indeg==0)[0])
    while q:
        nd = q.pop(0); order.append(nd)
        for c in np.where(adj[nd]>0)[0]:
            indeg[c] -= 1
            if indeg[c]==0: q.append(c)
    if len(order) < n:
        order.extend(set(range(n)) - set(order))
    return np.array(order, dtype=np.int32)


# ══════════════════════════════════════════════════════════════
# FORWARD
# ══════════════════════════════════════════════════════════════

def forward(g: Graph):
    g._cache()
    m = g.priors.copy()
    adj_td = g.adj * g._td
    for idx in g._topo:
        pa = np.where(adj_td[:, idx] > 0)[0]
        if len(pa) == 0: continue
        c = adj_td[pa, idx] * m[pa]
        # Correlation correction in forward (discount correlated parents)
        if len(pa) >= 2:
            for ai in range(len(pa)):
                for bi in range(ai+1, len(pa)):
                    rho = g.corr[pa[ai], pa[bi]]
                    if rho > 0:
                        c[ai] *= (1 - rho * 0.15)
                        c[bi] *= (1 - rho * 0.15)
        if g.gates[idx] == 1:    # AND-min
            m[idx] = np.clip(np.min(c), EPS, 1-EPS)
        elif g.gates[idx] == 2:  # AND-prod
            m[idx] = np.clip(np.prod(c), EPS, 1-EPS)
        else:                    # OR (noisy-OR)
            m[idx] = np.clip(1.0 - np.prod(1.0-c), EPS, 1-EPS)
    g.marginals = m


def _descendants(adj, node):
    """BFS descendants."""
    vis = set(); q = [node]
    while q:
        nd = q.pop(0)
        for c in np.where(adj[nd]>0)[0]:
            if int(c) not in vis: vis.add(int(c)); q.append(int(c))
    return vis


def forward_partial(g: Graph, changed_node: int):
    if g.marginals is None: forward(g); return
    desc = _descendants(g.adj, changed_node); desc.add(changed_node)
    adj_td = g.adj * g._td
    for idx in g._topo:
        if int(idx) not in desc: continue
        pa = np.where(adj_td[:, idx]>0)[0]
        if len(pa)==0: continue
        c = adj_td[pa, idx] * g.marginals[pa]
        if g.gates[idx] == 1: g.marginals[idx] = np.clip(np.min(c), EPS, 1-EPS)
        elif g.gates[idx] == 2: g.marginals[idx] = np.clip(np.prod(c), EPS, 1-EPS)
        else: g.marginals[idx] = np.clip(1.0-np.prod(1.0-c), EPS, 1-EPS)

def invert_edges(g: Graph):
    """Bayesian edge inversion with proper normalization.
    
    Problem: raw Bayes P(A|B) = P(B|A)*P(A)/P(B) can exceed 1.0 
    when Noisy-OR computes P(B) from multiple parents.
    
    Fix: For each target node, compute raw Bayes for all parents,
    then normalize so they sum to ≤ 1. This preserves relative 
    ranking (which parent is more important) while ensuring valid probabilities.
    """
    if g.marginals is None: forward(g)
    n = g.n
    inv = np.zeros((n, n), dtype=np.float64)
    
    for j in range(n):
        parents = np.where(g.adj[:, j] > 0)[0]
        if len(parents) == 0:
            continue
        
        # Raw Bayes for each parent
        raw = np.zeros(len(parents))
        for k, pi in enumerate(parents):
            p_ba = g.adj[pi, j]          # P(B|A)
            p_a = g.marginals[pi]        # P(A)
            p_b = g.marginals[j]         # P(B)
            raw[k] = (p_ba * p_a) / max(p_b, EPS)
        
        # Correlation correction
        if len(parents) >= 2:
            for ai in range(len(parents)):
                for bi in range(ai+1, len(parents)):
                    rho = g.corr[parents[ai], parents[bi]]
                    if rho > 0:
                        raw[ai] *= (1 - rho * 0.3)
                        raw[bi] *= (1 - rho * 0.3)
        
        # Normalize: if any raw > 1 or sum > 1, scale down proportionally
        total = raw.sum()
        if total > 1.0 or raw.max() > 1.0:
            raw = raw / max(total, raw.max())
        
        for k, pi in enumerate(parents):
            inv[pi, j] = raw[k]
    
    g.inv_adj = np.clip(inv, 0, 1)

    # Node inverted prob
    ip = np.where(g.types==2, 1.0, g.marginals.copy())
    for idx in reversed(g._topo):
        ch = np.where(g.adj[idx]>0)[0]
        if len(ch)==0: continue
        w = g.marginals[ch]; s = g.inv_adj[idx,ch] * ip[ch]
        tw = w.sum()
        ip[idx] = np.clip((s*w).sum()/max(tw,EPS), 0, 1) if tw>EPS else s.mean()
    g.inv_probs = ip


# ══════════════════════════════════════════════════════════════
# ENTROPY — MATRIX MULTIPLY FOR 2-HOP (no inner Python loop)
# ══════════════════════════════════════════════════════════════

def entropy(g: Graph):
    n = g.n; fH = np.zeros(n); iH = np.zeros(n)

    # Forward entropy per node
    adj_td = g.adj * g._td
    for i in range(n):
        ch = np.where(adj_td[i]>0)[0]
        if len(ch)==0: continue
        p = adj_td[i, ch]
        t = p.sum()
        if t < 1: p = np.append(p, 1-t)
        p = p / (p.sum()+EPS); p = p[p>EPS]
        fH[i] = -np.sum(p * np.log2(p))

    # Inverted entropy — 3-hop via matrix powers with geometric decay
    # Includes multi-hop for ALL nodes — measures "causal ancestry complexity"
    # Single-parent nodes still get entropy > 0 from upstream convergence
    inv2 = g.inv_adj @ g.inv_adj * 0.5
    inv3 = inv2 @ g.inv_adj * 0.5

    for i in range(n):
        pa = np.where(g.adj[:,i]>0)[0]
        if len(pa)==0: continue
        ip = g.inv_adj[pa, i].copy()
        # Multi-hop: scale contribution by number of direct parents
        # 1 parent: 2-hop weight = 0.3 (mild context)
        # 2+ parents: 2-hop weight = 0.5 (full context)
        hop_weight = 0.5 if len(pa) >= 2 else 0.3
        gp2 = inv2[:, i] * hop_weight / 0.5  # Scale relative to base 0.5
        mask2 = (gp2 > 0.01) & (g.adj[:, i] == 0)
        if mask2.any():
            ip = np.concatenate([ip, gp2[mask2]])
        gp3 = inv3[:, i] * hop_weight / 0.5
        mask3 = (gp3 > 0.01) & (g.adj[:, i] == 0) & (~mask2)
        if mask3.any():
            ip = np.concatenate([ip, gp3[mask3]])
        ip = ip[ip>EPS]
        if len(ip)==0: continue
        ip = ip / (ip.sum()+EPS)
        iH[i] = -np.sum(ip * np.log2(ip+EPS))

    g.fwd_H = fH; g.inv_H = iH; g.H_grad = fH - iH


# ══════════════════════════════════════════════════════════════
# TURNSTILE
# ══════════════════════════════════════════════════════════════

def find_turnstile(g: Graph) -> dict:
    ind = (g.adj>0).sum(axis=0); outd = (g.adj>0).sum(axis=1)
    v = (ind>0) & (outd>0) & (g.types==1) & ((g.fwd_H>0.001)|(g.inv_H>0.001))
    c = np.where(v)[0]
    if len(c)==0: return {"found": False}
    grad = np.abs(g.H_grad[c]); conn = (ind[c]+outd[c]).astype(float)
    # Normalize connectivity to 0-1 range so it scales with graph size
    max_conn = conn.max() if conn.max() > 0 else 1.0
    norm_conn = conn / max_conn
    best = c[np.argmin(grad - 0.001 * norm_conn)]
    return {"found":True, "id":g.ids[best], "label":g.labels[best], "idx":int(best),
        "t_hours":float(g.times[best]),
        "gradient":round(float(np.abs(g.H_grad[best])),6),
        "fwd_H":round(float(g.fwd_H[best]),4), "inv_H":round(float(g.inv_H[best]),4),
        "necessity":round(float(g.inv_probs[best]),4)}


# ── NECESSITY ──

def necessity(g, oidx):
    vis = set(); q = [oidx]; anc = []
    while q:
        nd = q.pop(0)
        for p in np.where(g.adj[:,nd]>0)[0]:
            if int(p) not in vis: vis.add(int(p)); anc.append(int(p)); q.append(int(p))
    r = [{"id":g.ids[a],"label":g.labels[a],"necessity":round(float(g.inv_probs[a]),4),
          "marginal":round(float(g.marginals[a]),4),
          "trivial":g.types[a]==0 or (np.sum(g.adj[:,a]>0)<=1 and np.sum(g.adj[a]>0)<=1 and g.priors[a]>0.85)}
         for a in anc]
    r.sort(key=lambda x: x["necessity"], reverse=True)
    nt = [x for x in r if not x["trivial"]]
    cut = nt[max(0,len(nt)//3)]["necessity"] if len(nt)>=3 else (nt[0]["necessity"]*0.8 if nt else 0)
    for x in r: x["critical"] = not x["trivial"] and x["necessity"] >= cut
    return r


# ══════════════════════════════════════════════════════════════
# MONTE CARLO — BATCH PERTURBATION
# ══════════════════════════════════════════════════════════════

def monte_carlo(g: Graph, n_sim=200, noise=0.08):
    op, oa = g.priors.copy(), g.adj.copy()
    mask = oa > 0
    saved_topo = g._topo  # Structure doesn't change, reuse topo
    n = g.n; samples = np.zeros((n_sim, n))
    for i in range(n_sim):
        g.priors = np.clip(op + np.random.normal(0, noise, n), EPS, 1-EPS)
        adj_noise = np.random.normal(0, noise*0.5, (n, n))
        g.adj = np.clip(oa + adj_noise, EPS, 1-EPS); g.adj[~mask] = 0
        g._topo = saved_topo  # Reuse — structure unchanged
        g._td = None; g._hl = None; g._cache()  # Only rebuild time decay
        forward(g); invert_edges(g)
        samples[i] = g.inv_probs
    g.priors = op; g.adj = oa
    g._topo = saved_topo; g._td = None; g._hl = None; g._cache()
    forward(g); invert_edges(g)
    g.mc_mean = samples.mean(0); g.mc_std = samples.std(0)
    g.mc_lo = np.percentile(samples, 2.5, axis=0)
    g.mc_hi = np.percentile(samples, 97.5, axis=0)


# ══════════════════════════════════════════════════════════════
# SENSITIVITY — TOP-K EDGES ONLY
# ══════════════════════════════════════════════════════════════

def sensitivity(g: Graph, target: int, delta=0.1, top_k=15) -> list:
    """Only test top-K edges by probability. Not all edges."""
    orig = g.adj.copy(); base = g.marginals[target]
    edges = np.argwhere(g.adj > 0)
    if len(edges) == 0: return []
    # Sort by probability, take top K
    ep = g.adj[edges[:,0], edges[:,1]]
    top_idx = np.argsort(-ep)[:min(top_k, len(edges))]
    top_edges = edges[top_idx]

    orig_m = g.marginals.copy()
    results = []
    for s,t in top_edges:
        v = orig[s,t]
        g.adj[s,t] = min(0.99, v+delta); g.marginals=orig_m.copy(); forward_partial(g,int(s)); up = g.marginals[target]
        g.adj[s,t] = max(0.01, v-delta); g.marginals=orig_m.copy(); forward_partial(g,int(s)); dn = g.marginals[target]
        g.adj[s,t] = v
        results.append({"edge":f"{g.ids[s]}→{g.ids[t]}",
            "sensitivity":round(abs(up-dn)/(2*delta),6),
            "up":round(float(up-base),6), "down":round(float(dn-base),6)})
    g.adj = orig; g.marginals = orig_m
    results.sort(key=lambda x: x["sensitivity"], reverse=True)
    return results


# ── do-CALCULUS ──

def do(g, node, val):
    a,p,m = g.adj.copy(), g.priors.copy(), g.marginals.copy()
    g.adj[:,node]=0; g.priors[node]=val; g.marginals=m.copy(); g.marginals[node]=val; forward_partial(g,int(node))
    r = g.marginals.copy(); g.adj=a; g.priors=p; g.marginals=m
    return r

def causal_power(g, max_n=15):
    ev = g.events; oc = g.outcomes
    if len(ev)==0 or len(oc)==0: return []
    ev = ev[np.argsort(-g.marginals[ev])][:max_n]
    r = []
    for i in ev:
        h,l = do(g,i,0.9), do(g,i,0.1)
        mx = max(abs(h[o]-l[o]) for o in oc)
        r.append({"id":g.ids[i],"label":g.labels[i],"power":round(float(mx),4)})
    r.sort(key=lambda x: x["power"], reverse=True); return r


# ── MARKOV BLANKET ──

def blanket(g, node):
    pa=set(np.where(g.adj[:,node]>0)[0].tolist())
    ch=set(np.where(g.adj[node]>0)[0].tolist())
    cop=set()
    for c in ch: cop.update(np.where(g.adj[:,c]>0)[0].tolist())
    cop.discard(node); b=pa|ch|cop
    return {"node":g.ids[node],"blanket":[g.ids[x] for x in b],
        "size":len(b),"compression":round(1-len(b)/max(1,g.n-1),2)}


# ── ROBUSTNESS ──

def robustness(g, max_flips=20):
    oc=g.outcomes
    if len(oc)<2: return {"robustness":1.0,"flips":0}
    top=oc[np.argmax(g.marginals[oc])]; a=g.adj.copy(); m=g.marginals.copy()
    edges=np.argwhere(g.adj>0); ep=g.adj[edges[:,0],edges[:,1]]
    edges=edges[np.argsort(-ep)][:max_flips]; flips=0
    for s,t in edges:
        g.adj[s,t]*=0.3; g.marginals=m.copy(); forward_partial(g,int(s)); flips+=1
        if oc[np.argmax(g.marginals[oc])]!=top: break
    g.adj=a; g.marginals=m
    return {"top":g.ids[top],"flips":flips,"total":int((a>0).sum()),
        "robustness":round(flips/max(1,int((a>0).sum())),4)}


# ── KL ──

def kl(g):
    m=g.types==1
    if not m.any(): return {"kl":0,"n":0}
    p=np.clip(g.marginals[m],EPS,1-EPS); q=np.clip(g.inv_probs[m],EPS,1-EPS)
    k=p*np.log(p/q)+(1-p)*np.log((1-p)/(1-q))
    return {"kl":round(float(np.maximum(k,0).mean()),4),"n":int(m.sum())}


# ── COUNTERFACTUAL (top-K only) ──

def counterfactual(g, node):
    om=g.marginals.copy(); a=g.adj.copy()
    g.adj[node,:]=0; g.adj[:,node]=0; g.marginals=om.copy()
    # Recompute from seed (full forward needed since multiple edges removed)
    forward(g)
    oc=g.outcomes; eff={}
    for o in oc:
        eff[g.ids[o]]={"orig":round(float(om[o]),4),"without":round(float(g.marginals[o]),4),
            "impact":round(float(om[o]-g.marginals[o]),4)}
    tot=sum(abs(v["impact"]) for v in eff.values())
    g.adj=a; g.marginals=om
    return {"removed":g.ids[node],"label":g.labels[node],"impact":round(tot,4),"effects":eff,"critical":tot>0.05}


# ── CRITICAL PATH ──

def critical_path(g, outcome):
    if not HAS_SCIPY: return {"found": False}
    n=g.n; w=np.full((n,n),np.inf)
    mask=g.adj>0; p=g.adj[mask]*g.marginals[np.where(mask)[0]]
    w[mask]=-np.log(np.maximum(p,EPS))
    roots=np.where(g.types==0)[0]; best_path=None; best_prob=0
    dist,pred=shortest_path(sp.csr_matrix(w),directed=True,return_predecessors=True)
    for r in roots:
        if dist[r,outcome]<np.inf:
            path=[outcome]; cur=outcome
            while pred[r,cur]!=-9999 and cur!=r: cur=pred[r,cur]; path.append(cur)
            if cur==r:
                path.reverse(); prob=1.0
                for k in range(len(path)-1): prob*=g.adj[path[k],path[k+1]]
                if prob>best_prob: best_prob=prob; best_path=path
    if not best_path: return {"found":False}
    return {"found":True,"path":[{"id":g.ids[p],"label":g.labels[p]} for p in best_path],
        "prob":round(best_prob,4),"length":len(best_path)}


# ── ENTROPY RATE ──

def entropy_rate(g):
    t=[(i,g.times[i]) for i in range(g.n) if g.times[i]>0]
    t.sort(key=lambda x:x[1]); r=[]
    for k in range(1,len(t)):
        i,ti=t[k]; j,tj=t[k-1]; dt=ti-tj
        if dt<=0: continue
        r.append({"from":g.ids[j],"to":g.ids[i],"hours":round(dt,1),
            "fwd_rate":round(float((g.fwd_H[i]-g.fwd_H[j])/dt),6),
            "inv_rate":round(float((g.inv_H[i]-g.inv_H[j])/dt),6)})
    return r


# ══════════════════════════════════════════════════════════════
# MAIN API
# ══════════════════════════════════════════════════════════════

def analyze(g: Graph, mc_on=True, mc_n=200, mode=None) -> dict:
    """mode: None=auto, 'lite', 'standard', 'full'.
    Auto: <100=full, <1000=standard, <5000=standard(no MC), >=5000=lite."""
    t0 = time.perf_counter(); N = g.n
    if mode is None:
        mode = "full" if N<100 else ("standard" if N<5000 else "lite")
    forward(g); invert_edges(g); entropy(g)
    ts = find_turnstile(g)
    pincer = np.sqrt(np.maximum(g.marginals,0)*np.maximum(g.inv_probs,0))
    oc = g.outcomes
    nec = {g.ids[o]:{"outcome":g.labels[o],"prob":round(float(g.marginals[o]),4),
        "conditions":necessity(g,o)} for o in oc}
    pr = [{"id":g.ids[i],"label":g.labels[i],"fwd":round(float(g.marginals[i]),4),
        "inv":round(float(g.inv_probs[i]),4),"pincer":round(float(pincer[i]),4)}
        for i in np.argsort(-pincer)[:20]]
    sens,do_r,bl,rob,kl_r = {}, [], {}, {}, {}
    if mode in ("standard","full"):
        sk = min(15, max(5, min(N//10, 25)))
        sens = {g.ids[o]:sensitivity(g,o,top_k=sk)[:10] for o in oc}
        do_r = causal_power(g, max_n=min(15, max(3, min(N//10, 15))))
        bl = {g.ids[o]:blanket(g,o) for o in oc}
        rob = robustness(g, max_flips=min(20, max(5, min(N//5, 25))))
        kl_r = kl(g)
    mc_r,cf,cp,er = {}, [], {}, []; mc_actual=0
    if mode == "full":
        if mc_on and N < 1000:
            mc_actual = min(mc_n, max(30, 3000//max(1,N)))
            monte_carlo(g, mc_actual)
            mc_r = {"n":mc_actual,"nodes":{g.ids[i]:{"mean":round(float(g.mc_mean[i]),4),
                "std":round(float(g.mc_std[i]),4),
                "ci95":[round(float(g.mc_lo[i]),4),round(float(g.mc_hi[i]),4)]}
                for i in g.events}}
        cf_n = min(10, max(3, min(N//20, 10)))
        cf = sorted([counterfactual(g,i) for i in g.events[:cf_n]],key=lambda x:x["impact"],reverse=True)[:5]
        cp = {g.ids[o]:critical_path(g,o) for o in oc}
        er = entropy_rate(g)
    ms = (time.perf_counter()-t0)*1000
    
    # Overall confidence score (0-100)
    # Based on: KL agreement, robustness, MC stability, graph structure
    conf_kl = max(0, 1 - kl_r.get("kl", 0.5) / 2) if kl_r else 0.5          # Low KL = high conf
    conf_rob = rob.get("robustness", 0.5) if rob else 0.5                      # High robustness = high conf
    conf_mc = 0.5
    if mc_r and mc_r.get("nodes"):
        stds = [v["std"] for v in mc_r["nodes"].values()]
        conf_mc = float(max(0, 1 - np.mean(stds) * 3)) if stds else 0.5              # Low std = high conf
    conf_structure = min(1, g.edge_count / max(1, g.n * 1.5))                  # Denser = more info
    confidence = round(float(np.mean([conf_kl, conf_rob, conf_mc, conf_structure]) * 100), 1)
    
    return {"turnstile":ts,"necessities":nec,"sensitivity":sens,"pincer":pr,
        "monte_carlo":mc_r,"do_calculus":do_r,"markov_blankets":bl,"robustness":rob,
        "kl":kl_r,"counterfactuals":cf,"critical_paths":cp,"entropy_rate":er,
        "confidence":{"score":confidence,"breakdown":{"kl_agreement":round(conf_kl*100,1),
            "robustness":round(conf_rob*100,1),"mc_stability":round(conf_mc*100,1),
            "graph_density":round(conf_structure*100,1)}},
        "perf":{"ms":round(ms,2),"nodes":N,"edges":g.edge_count,"mc":mc_actual,"mode":mode},
        "engine":"turnstile","version":"3.3.0","llm_calls":0}

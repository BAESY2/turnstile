# TURNSTILE — Mathematical Foundation

## Complete Formula Reference & Academic Sources

---

## 1. GRAPH REPRESENTATION

Causal DAG `G = (V, E, θ)` where:
- `V = {v₁, v₂, ..., vₙ}` — nodes (events)
- `E ⊆ V × V` — directed edges (causal links), acyclic
- `θ` — parameters:
  - `P(vᵢ)` — prior probability of node i
  - `P(vⱼ|vᵢ)` — conditional probability on edge (i→j), stored in adjacency matrix `A[i,j]`
  - `τ(i,j)` — time delay on edge (i→j), stored in delay matrix `D[i,j]`
  - `gate(j)` — combination rule for node j: OR or AND

**Code**: `engine.py` lines 30-70 (Graph class + Builder)

---

## 2. TIME DECAY

Longer causal delay = more uncertainty.

**Formula**:

```
td(i,j) = exp(-0.693 × D[i,j] / T_half)
```

Where:
- `D[i,j]` = delay in hours from node i to node j
- `T_half` = auto-detected or user-specified half-life
- `0.693 = ln(2)` — decay constant for half-life

**Auto-detection (v3.0)**:
```
T_half = max(24, min(2000, time_span × 0.3))
time_span = max(t) - min(t) for all nodes with t > 0
```

This ensures even the longest delay retains ~25% weight.
User override: `invert(g, half_life=24)` for finance, `half_life=720` for geopolitics.

**Code**: `engine.py` lines 69-78

**Source**: Standard exponential decay model. Used in epidemiological causal models — see Rothman, K.J. "Modern Epidemiology" (2008), Ch. 3.

---

## 3. FORWARD MARGINALS (Belief Propagation)

Compute P(node) for every node, propagating from seeds to outcomes.

### 3a. Noisy-OR Gate (default)

For node j with parents Pa(j) = {p₁, p₂, ..., pₖ}:

```
P(j) = 1 - ∏ᵢ (1 - A[pᵢ,j] × td(pᵢ,j) × P(pᵢ))
```

**Interpretation**: "Any parent can cause this." Probability that at least one parent triggers j.

### 3b. AND Gate (two variants, v3.0)

**AND-min** (default, `gate="and"` or `gate="and-min"`):
```
P(j) = min(A[pᵢ,j] × td(pᵢ,j) × P(pᵢ)) for all i
```
Interpretation: weakest link determines. From fuzzy logic (Zadeh, 1965).

**AND-prod** (`gate="and-prod"`):
```
P(j) = ∏ᵢ (A[pᵢ,j] × td(pᵢ,j) × P(pᵢ))
```
Interpretation: independent conjunction. Mathematically exact for independent causes.

### 3c. Forward Correlation Correction (v3.0)

When parents are correlated, discount their contributions to avoid double-counting:
```
c[i] *= (1 - ρ(pᵢ,pₖ) × 0.15) for each correlated pair
```
Applied BEFORE gate computation. Factor 0.15 (half of inversion's 0.3) because forward is less sensitive to correlation than inversion.

**Code**: `engine.py` lines 133-155

**Source**:
- Noisy-OR: Pearl, J. "Probabilistic Reasoning in Intelligent Systems" (1988), Ch. 10
- AND gate as min(): Heckerman, D. "Causal Independence for Probability Assessment" (1993)
- Belief propagation in DAGs: Koller & Friedman, "Probabilistic Graphical Models" (2009), Ch. 9

---

## 4. BAYESIAN INVERSION (Core Operation)

**This is the heart of TURNSTILE.** Reverse every edge probability using Bayes' theorem.

### 4a. Edge Inversion

For edge A→B:

```
P(A|B) = P(B|A) × P(A) / P(B)
```

In matrix form:

```
inv_adj = A ⊙ (P_col / P_row)
```

Where:
- `A` = adjacency matrix with P(B|A) values
- `P_col = marginals[:, None]` — column broadcast of marginal probabilities
- `P_row = marginals[None, :]` — row broadcast
- `⊙` = element-wise multiplication

**Code**: `engine.py` lines 169-186

### 4b. Correlation Correction

When two parent edges into node j are correlated (ρ > 0), they share explanatory power. Reduce inverted probability to avoid double-counting:

```
inv_adj[pᵢ,j] *= (1 - ρ(pᵢ,pₖ) × 0.3)
```

For each pair of correlated parents (pᵢ, pₖ) of node j.

**Code**: `engine.py` lines 176-185

### 4c. Node Inverted Probability

Backward propagation from outcomes to seeds:

```
IP(j) = Σᵢ (inv_adj[j,cᵢ] × IP(cᵢ) × P(cᵢ)) / Σᵢ P(cᵢ)
```

Where cᵢ are children of j. Outcomes have IP = 1.0 (assumed true in inverted frame).

**Code**: `engine.py` lines 188-196

**Source**:
- Bayes' theorem: Bayes, T. "An Essay towards solving a Problem in the Doctrine of Chances" (1763)
- Bayesian networks edge reversal: Shachter, R. "Bayes-Ball" (1998)
- Correlation correction in causal models: VanderWeele & Robins, "Signed DAGs" (2010)

---

## 5. SHANNON ENTROPY

### 5a. Forward Entropy (per node)

Measures branching uncertainty — how many futures from this point?

```
H_fwd(x) = -Σᵢ p(cᵢ|x) × log₂(p(cᵢ|x))
```

Where p(cᵢ|x) are normalized outgoing edge probabilities from x, including implicit "nothing happens" probability if they don't sum to 1.

**Code**: `engine.py` lines 208-215

### 5b. Inverted Entropy (per node)

Measures causal ambiguity — how many causes could explain this node?

```
H_inv(x) = -Σᵢ q(pᵢ|x) × log₂(q(pᵢ|x))
```

Where q(pᵢ|x) are the Bayes-inverted edge probabilities from parents of x, plus multi-hop contributions via matrix powers (v3.0):

```
inv²[i,j] = (inv_adj @ inv_adj)[i,j] × 0.5     — 2-hop, 50% decay
inv³[i,j] = (inv² @ inv_adj)[i,j] × 0.5         — 3-hop, 25% decay (0.5²)
```

Geometric decay: hop k contributes with weight 0.5^(k-1). This ensures distant ancestors have diminishing influence while still being considered.

**Code**: `engine.py` lines 222-240

### 5c. Entropy Gradient

```
∇H(x) = H_fwd(x) - H_inv(x)
```

- `∇H > 0` → OPEN phase: more forward uncertainty, outcome not yet determined
- `∇H < 0` → LOCKED phase: outcome essentially inevitable
- `∇H ≈ 0` → TURNSTILE: phase transition point

**Code**: `engine.py` line 236

**Source**:
- Shannon, C. "A Mathematical Theory of Communication" (1948)
- Cover & Thomas, "Elements of Information Theory" (2006), Ch. 2
- Conditional entropy: H(X|Y) ≤ H(X) — fundamental property, Cover & Thomas Ch. 2.6

---

## 6. TURNSTILE DETECTION

The Turnstile is the node where the entropy gradient crosses zero — the **phase transition** from "open future" to "inevitable outcome."

### Selection criteria:

```
candidates = {x ∈ V : in_degree(x) > 0 AND out_degree(x) > 0 
                       AND type(x) = event
                       AND (H_fwd(x) > 0.001 OR H_inv(x) > 0.001)}

turnstile = argmin_{x ∈ candidates} (|∇H(x)| - 0.001 × norm_connectivity(x))
```

Connectivity normalized to 0-1: norm_conn = conn / max_conn (v3.0). Scales consistently from 9 to 5000+ nodes.

**Code**: `engine.py` lines 243-254

**Source**: Novel formulation. Inspired by:
- Phase transitions in information theory: Mezard & Montanari, "Information, Physics, and Computation" (2009)
- Critical points in Bayesian networks: Darwiche, "Modeling and Reasoning with Bayesian Networks" (2009), Ch. 11

---

## 7. TEMPORAL PINCER

Combines forward and inverted probability estimates via geometric mean:

```
Pincer(x) = √(P_fwd(x) × P_inv(x))
```

**Why geometric mean, not arithmetic?**
- Geometric mean penalizes disagreement more heavily
- If forward says 0.9 and inverted says 0.1, arithmetic = 0.5, geometric = 0.3
- This ensures both views must agree for high score

**Analogy**: Forward-backward algorithm in Hidden Markov Models computes α(t)×β(t), which is equivalent to our pincer product.

**Code**: `engine.py` line 447 (inside analyze())

**Source**:
- Forward-backward algorithm: Rabiner, L. "A Tutorial on HMMs" (1989)
- Ensemble methods (geometric mean): Breiman, L. "Bagging Predictors" (1996)

---

## 8. MONTE CARLO UNCERTAINTY QUANTIFICATION

Perturb all priors and edge probabilities N times, re-run inversion each time, collect statistics.

### Perturbation model:

```
P'(vᵢ) = clip(P(vᵢ) + N(0, σ), ε, 1-ε)
A'[i,j] = clip(A[i,j] + N(0, σ/2), ε, 1-ε)  where A[i,j] > 0
```

Where:
- `σ = 0.08` (default noise level)
- `ε = 10⁻¹⁰` (numerical floor)
- `N(0, σ)` = Gaussian noise with mean 0, std σ

### Statistics computed:

```
Mean:    μ(x) = (1/N) Σᵢ IP_i(x)
Std:     σ(x) = √((1/N) Σᵢ (IP_i(x) - μ(x))²)
CI_low:  2.5th percentile
CI_high: 97.5th percentile
```

**Code**: `engine.py` lines 280-296

**Source**:
- Monte Carlo methods: Robert & Casella, "Monte Carlo Statistical Methods" (2004)
- Sensitivity analysis in Bayesian networks: Castillo et al., "Sensitivity Analysis in Discrete Bayesian Networks" (1997)
- Confidence intervals: Efron & Tibshirani, "An Introduction to the Bootstrap" (1993)

---

## 9. SENSITIVITY ANALYSIS

Numerical partial derivative of outcome probability w.r.t. each edge:

```
∂P(outcome)/∂A[i,j] ≈ (P(outcome|A[i,j]+δ) - P(outcome|A[i,j]-δ)) / (2δ)
```

Where δ = 0.1 (default step size). Uses central difference for accuracy.

**Optimization**: Only tests top-K edges by probability (not all edges). Uses `forward_partial()` — incremental belief propagation that only recomputes descendants of changed edge.

**Code**: `engine.py` lines 303-325

**Source**:
- Numerical differentiation: Chapra & Canale, "Numerical Methods for Engineers" (2014)
- Sensitivity in probabilistic networks: Chan & Darwiche, "Sensitivity Analysis in Bayesian Networks" (2004)
- Incremental belief propagation: Kozlov & Singh, "A Parallel Lauritzen-Spiegelhalter Algorithm" (1994)

---

## 10. do-CALCULUS (Pearl's Causal Intervention)

**Key insight**: P(Y|X=x) ≠ P(Y|do(X=x))

- `P(Y|X=x)` = observation: if we SEE X=x, what's Y? (may include confounding)
- `P(Y|do(X=x))` = intervention: if we FORCE X=x, what's Y? (removes confounding)

### Implementation:

```
do(X=x):
  1. Cut all incoming edges to X:  A[:,X] = 0
  2. Set X's probability:          P(X) = x
  3. Recompute forward propagation downstream of X
```

### Causal Power:

```
CausalPower(X) = max_{outcome} |P(outcome|do(X=0.9)) - P(outcome|do(X=0.1))|
```

High causal power = forcing this node to different values strongly changes outcomes.

**Code**: `engine.py` lines 330-345

**Source**:
- Pearl, J. "Causality: Models, Reasoning, and Inference" (2000), Ch. 3
- Pearl's do-calculus rules: Pearl, J. "The do-calculus revisited" (2012)
- Causal effect estimation: Tian & Pearl, "On the Identification of Causal Effects" (2002)

---

## 11. MARKOV BLANKET

Minimal set of nodes that makes a target conditionally independent of all other nodes.

```
MB(X) = Parents(X) ∪ Children(X) ∪ Parents_of_Children(X)
```

**Property**: Given MB(X), X is conditionally independent of all other nodes:

```
P(X | MB(X), rest) = P(X | MB(X))
```

**Compression ratio**:

```
Compression = 1 - |MB(X)| / (|V| - 1)
```

**Code**: `engine.py` lines 350-357

**Source**:
- Pearl, J. "Probabilistic Reasoning in Intelligent Systems" (1988), Ch. 3.3
- Koller & Friedman, "Probabilistic Graphical Models" (2009), Ch. 4.4

---

## 12. ROBUSTNESS

How many edges must change to flip the top prediction?

### Algorithm:

```
1. Identify top outcome: outcome* = argmax_{o ∈ outcomes} P(o)
2. Sort all edges by probability (descending)
3. Iteratively weaken strongest edges: A[i,j] *= 0.3
4. After each weakening, recompute forward
5. Stop when top outcome changes
6. flips = number of edges weakened
7. robustness = flips / |E|
```

**Code**: `engine.py` lines 362-374

---

## 13. KL DIVERGENCE

Measures disagreement between forward and inverted probability views:

```
KL(P_fwd || P_inv) = (1/|events|) Σ_{x ∈ events} [p log(p/q) + (1-p) log((1-p)/(1-q))]
```

Where p = P_fwd(x), q = P_inv(x). Binary KL divergence per node, averaged.

- KL < 0.15 → LOW: forward and inverted agree → reliable results
- KL < 0.5 → MODERATE: some disagreement
- KL ≥ 0.5 → HIGH: significant disagreement → investigate

**Code**: `engine.py` lines 378-383

**Source**:
- Kullback & Leibler, "On Information and Sufficiency" (1951)
- Cover & Thomas, "Elements of Information Theory" (2006), Ch. 2.3

---

## 14. COUNTERFACTUAL ANALYSIS

"What if node X didn't exist?"

```
1. Remove all edges to/from X: A[X,:] = 0, A[:,X] = 0
2. Recompute forward propagation
3. Impact = Σ_{o ∈ outcomes} |P_original(o) - P_without_X(o)|
```

Node is "structurally critical" if Impact > 0.05.

**Code**: `engine.py` lines 388-399

**Source**:
- Pearl, J. "Causality" (2000), Ch. 7 (Counterfactuals)
- Lewis, D. "Counterfactuals" (1973) — philosophical foundation

---

## 15. CRITICAL PATH

Most probable causal chain from seed to outcome.

```
1. Build weight graph: W[i,j] = -log(A[i,j] × P(i)) for each edge
2. Run Dijkstra's shortest path from each seed to outcome
3. Shortest path = most probable chain
4. Path probability = ∏ᵢ A[path[i], path[i+1]]
```

**Why -log?**: Minimizing -log(p) is equivalent to maximizing p. Converts multiplication to addition for Dijkstra.

**Code**: `engine.py` lines 404-421

**Source**:
- Dijkstra, E.W. "A Note on Two Problems in Connexion with Graphs" (1959)
- Log-probability shortest path: Viterbi, A. "Error Bounds for Convolutional Codes" (1967) — same principle as Viterbi algorithm

---

## 16. ENTROPY RATE

Change of entropy per unit time along the causal timeline:

```
dH_fwd/dt = (H_fwd(xᵢ) - H_fwd(xⱼ)) / (t(xᵢ) - t(xⱼ))
dH_inv/dt = (H_inv(xᵢ) - H_inv(xⱼ)) / (t(xᵢ) - t(xⱼ))
```

For consecutive nodes xⱼ, xᵢ on the time axis.

**Code**: `engine.py` lines 426-435

---

## 17. GENETIC ALGORITHM (Structural Robustness)

Evolve DAG structure to find most robust causal model.

```
1. Population: 20 DAGs (original + mutants)
2. Mutations:
   - Edge probability ± N(0, 0.15)              [common]
   - Node prior ± N(0, 0.15)                    [common]
   - Edge deletion                              [moderate, p=0.04]
   - Edge addition (random, respecting topo)    [moderate, p=0.08]
   - Node split (one event → two sequential)    [rare, p=0.02]
   - Edge rewire (redirect to different target)  [rare, p=0.015]
3. Fitness: proximity of turnstile time to population median
4. Selection: top 30% survive
5. Next generation: mutate survivors
6. Convergence: when turnstile_std < threshold
```

**Code**: `adversarial.py` — mutate_dag() + evolve_dag()

**Source**:
- Holland, J.H. "Adaptation in Natural and Artificial Systems" (1975)
- Goldberg, D.E. "Genetic Algorithms in Search, Optimization, and Machine Learning" (1989)
- Evolutionary structure learning: Larranaga et al., "Structure Learning of Bayesian Networks by Genetic Algorithms" (1996)

---

## 18. SEMANTIC SIMILARITY (Cross-validation)

Keyword overlap with stemming for matching nodes across agent DAGs:

```
1. Normalize: lowercase, remove stopwords
2. Stem: strip suffixes (ation, tion, ing, ed, ...)
3. Extract top-6 keywords by length
4. Similarity = |KW₁ ∩ KW₂| / max(|KW₁|, |KW₂|)
5. Match threshold: ≥ 0.35
```

**Code**: `ingest.py` — semantic_similarity()

---

## KEY ACADEMIC REFERENCES (sorted by relevance)

### Core Theory
1. Pearl, J. **"Causality: Models, Reasoning, and Inference"** (2000, 2009 2nd ed.) — do-calculus, counterfactuals, DAG reversal
2. Shannon, C. **"A Mathematical Theory of Communication"** (1948) — entropy
3. Bayes, T. **"An Essay towards solving a Problem in the Doctrine of Chances"** (1763) — Bayes' theorem
4. Koller & Friedman, **"Probabilistic Graphical Models"** (2009) — belief propagation, Markov blankets

### Methods
5. Pearl, J. **"Probabilistic Reasoning in Intelligent Systems"** (1988) — Noisy-OR, Bayesian networks
6. Rabiner, L. **"A Tutorial on HMMs"** (1989) — forward-backward algorithm (our temporal pincer)
7. Cover & Thomas, **"Elements of Information Theory"** (2006) — KL divergence, conditional entropy
8. Chan & Darwiche, **"Sensitivity Analysis in Bayesian Networks"** (2004) — sensitivity methods

### Computational
9. Castillo et al., **"Sensitivity Analysis in Discrete Bayesian Networks"** (1997) — Monte Carlo
10. Larranaga et al., **"Structure Learning of Bayesian Networks by Genetic Algorithms"** (1996) — evolutionary approach

### Tenet Physics Corrections
11. Mezard & Montanari, **"Information, Physics, and Computation"** (2009) — entropy phase transitions
12. Darwiche, A. **"Modeling and Reasoning with Bayesian Networks"** (2009) — critical points in BNs

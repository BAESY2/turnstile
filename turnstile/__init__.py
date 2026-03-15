"""TURNSTILE v3.3.0 — Bayesian Temporal Inversion Engine.
MiroFish predicts what happens. Turnstile proves why it must."""
from .engine import Graph, Builder, analyze, find_turnstile
from .engine import forward, invert_edges, entropy, necessity
from .engine import monte_carlo, sensitivity, do, causal_power
from .engine import blanket, robustness, kl, counterfactual, critical_path, entropy_rate
from .tenet import entropy_report, print_entropy_report, explain_inversion
from .adversarial import adversarial_verify, multi_agent_build, cross_validate, mutate_dag, evolve_dag
from .ingest import text_to_dag, semantic_similarity
from .backtest import run_backtest, run_single_backtest, SCENARIOS
from .extra import surprises, bottlenecks, chain_reactions, classify_edges
from .extra import to_mermaid, to_ascii, timeline, generate_report, run_advanced, diff_results
from .power import portfolio, causal_story, risk_matrix, tipping_points
from .power import scenario_tree, multi_what_if, export_html
TurnstileGraph = Graph
TurnstileBuilder = Builder
invert = analyze
__version__ = "3.3.0"

"""TURNSTILE API — FastAPI REST endpoints.

Run: pip install fastapi uvicorn && uvicorn turnstile.api:app --host 0.0.0.0 --port 8000
"""
import sys, os
from typing import Optional
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from turnstile import Builder, invert
from turnstile.backtest import run_backtest, run_single_backtest, SCENARIOS

if HAS_FASTAPI:
    app = FastAPI(title="TURNSTILE", description="Bayesian Temporal Inversion Engine.", version="3.3.0")

    class NodeInput(BaseModel):
        id: str; label: str = ""; type: str = "event"; prior: float = 0.5; time: float = 0.0
    class EdgeInput(BaseModel):
        src: str; tgt: str; prob: float = 0.5; delay: float = 0.0; gate: str = "or"
    class CorrInput(BaseModel):
        n1: str; n2: str; corr: float = 0.3
    class AnalyzeRequest(BaseModel):
        nodes: list[NodeInput]; edges: list[EdgeInput]
        correlations: list[CorrInput] = []; mode: Optional[str] = None
        mc: bool = True; mc_n: int = 200; half_life: Optional[float] = None

    @app.post("/analyze")
    def analyze_dag(req: AnalyzeRequest):
        try:
            b = Builder()
            for n in req.nodes: b.node(n.id, n.label, n.type, n.prior, n.time)
            for e in req.edges: b.edge(e.src, e.tgt, e.prob, e.delay, e.gate)
            for c in req.correlations: b.corr(c.n1, c.n2, c.corr)
            g = b.build()
            if req.half_life:
                g.half_life = req.half_life; g._hl = None; g._td = None; g._cache()
            return invert(g, mc_on=req.mc, mc_n=req.mc_n, mode=req.mode)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/demo/{scenario}")
    def demo(scenario: str):
        if scenario == "tariff":
            from turnstile.__main__ import demo_tariff; _, r = demo_tariff(); return r
        elif scenario in ("btc", "bitcoin"):
            from turnstile.__main__ import demo_btc; _, r = demo_btc(); return r
        raise HTTPException(404, f"Unknown: {scenario}")

    @app.get("/backtest")
    def backtest(): return run_backtest()

    @app.get("/health")
    def health(): return {"status": "ok", "engine": "turnstile", "version": "3.3.0"}
else:
    class _App:
        title = "TURNSTILE"
    app = _App()

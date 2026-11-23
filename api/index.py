from fastapi import FastAPI, HTTPException

from api.core.compromise import solve_all_metrics
from api.core.payoff import compute_payoff_matrix
from api.core.schemas import ModelDefinition, PayoffMatrixData, SolveResponse

app = FastAPI(title="OptiCompromise API")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/payoff", response_model=PayoffMatrixData)
def payoff(model: ModelDefinition):
    try:
        return compute_payoff_matrix(model)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/solve", response_model=SolveResponse)
def solve(model: ModelDefinition):
    try:
        payoff_matrix = compute_payoff_matrix(model)
        solutions, weights = solve_all_metrics(model, payoff_matrix)
        return SolveResponse(
            status="optimal",
            message="Modelo resuelto correctamente.",
            payoff=payoff_matrix,
            solutions=solutions,
            weights=weights,
            pareto_points=[],
            weight_sensitivity=None,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

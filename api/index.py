"""
API Principal de OptiCompromise en FastAPI.
Compatible con Vercel Serverless Functions y ejecución local con uvicorn.
"""
import math
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import hashlib
from collections import OrderedDict
from concurrent.futures import Future
from threading import Lock
from typing import Tuple, List

try:
    from .core.schemas import ModelDefinition, PayoffMatrixData, SolveResponse, ParetoPoint, ParetoResponse, WeightSensitivityData
    from .core.payoff import compute_payoff_matrix
    from .core.compromise import solve_all_metrics
    from .core.pareto import compute_pareto_frontier
    from .core.sensitivity import compute_weight_sensitivity
except (ImportError, ValueError):
    from core.schemas import ModelDefinition, PayoffMatrixData, SolveResponse, ParetoPoint, ParetoResponse, WeightSensitivityData
    from core.payoff import compute_payoff_matrix
    from core.compromise import solve_all_metrics
    from core.pareto import compute_pareto_frontier
    from core.sensitivity import compute_weight_sensitivity

app = FastAPI(
    title="OptiCompromise API",
    description="Motor de Optimización Multiobjetivo por Programación de Compromiso (IAD - UNAL)",
    version="1.0.0"
)

# Habilitar CORS para permitir llamadas desde el frontend de Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": "OptiCompromise",
        "university": "Universidad Nacional de Colombia - Facultad de Minas",
        "course": "Introducción al Análisis de Decisiones (IAD)",
        "engine": "SciPy 1.17+ HiGHS & SLSQP"
    }

# Cache LRU en memoria para (payoff, pareto_points) indexado por la estructura del modelo (sin pesos).
# Al arrastrar los sliders de pesos, evita recomputar 100+ puntos Pareto en cada frame.
StructureData = Tuple[PayoffMatrixData, List[ParetoPoint], WeightSensitivityData | None]
_STRUCTURE_CACHE: OrderedDict[str, StructureData] = OrderedDict()
_IN_FLIGHT: dict[str, Future[StructureData]] = {}
_MAX_CACHE_SIZE = 32
_CACHE_LOCK = Lock()


def _model_structure_key(model: ModelDefinition) -> str:
    payload = {
        "pareto_seed": model.pareto_seed if len(model.objectives) > 3 else None,
        "variables": [
            (v.name, v.var_type, v.lower_bound, v.upper_bound) for v in model.variables
        ],
        "objectives": [
            (o.name, o.sense, list(o.coefficients)) for o in model.objectives
        ],
        "constraints": [
            (c.sense, float(c.rhs), list(c.coefficients)) for c in model.constraints
        ],
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_model(model: ModelDefinition) -> None:
    if len(model.variables) < 1:
        raise HTTPException(status_code=400, detail="El modelo debe contener al menos 1 variable de decisión.")
    if len(model.objectives) < 2:
        raise HTTPException(status_code=400, detail="Un problema multiobjetivo requiere al menos 2 funciones objetivo.")

    if model.weights is not None and (
        len(model.weights) != len(model.objectives)
        or any(not math.isfinite(w) or not 0 <= w <= 1 for w in model.weights)
        or abs(sum(model.weights) - 1.0) > 0.001 + 1e-12
    ):
        raise HTTPException(status_code=400, detail="Ingresa un peso entre 0 y 1 por objetivo. Los pesos deben sumar 1.")

    seen_names = set()
    for v in model.variables:
        clean = v.name.strip()
        if not clean:
            raise HTTPException(status_code=400, detail="Todas las variables de decisión deben tener un nombre no vacío.")
        if clean in seen_names:
            raise HTTPException(status_code=400, detail=f"Nombre de variable duplicado: '{clean}'. Cada variable debe ser única.")
        seen_names.add(clean)
        for bval in (v.lower_bound, v.upper_bound):
            if bval is not None and not math.isfinite(bval):
                raise HTTPException(status_code=400, detail=f"Cota no finita inválida en '{clean}'.")
        if v.lower_bound is not None and v.upper_bound is not None and v.lower_bound > v.upper_bound:
            raise HTTPException(
                status_code=400,
                detail=f"Cotas inválidas en '{clean}': la cota inferior ({v.lower_bound}) supera la cota superior ({v.upper_bound}).",
            )

    for idx, o in enumerate(model.objectives):
        if not o.name.strip():
            raise HTTPException(status_code=400, detail=f"El objetivo #{idx + 1} debe tener un nombre no vacío.")
        if len(o.coefficients) > len(model.variables):
            raise HTTPException(status_code=400, detail=f"El objetivo «{o.name}» tiene más coeficientes que variables.")
        if o.expression:
            raise HTTPException(status_code=400, detail=f"Convierte «{o.name}» a coeficientes lineales antes de resolver.")
        if any(not math.isfinite(c) for c in o.coefficients):
            raise HTTPException(status_code=400, detail=f"Coeficientes inválidos (NaN/Inf) en objetivo '{o.name}'.")

    for idx, c in enumerate(model.constraints):
        if len(c.coefficients) > len(model.variables) or c.expression:
            raise HTTPException(status_code=400, detail=f"Revisa los coeficientes lineales de la restricción {idx + 1}.")
        if not math.isfinite(c.rhs) or any(not math.isfinite(coef) for coef in c.coefficients):
            raise HTTPException(status_code=400, detail=f"Valores numéricos inválidos (NaN/Inf) en restricción #{idx + 1}.")


def _ensure_finite(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise HTTPException(
                status_code=400,
                detail="Desbordamiento numérico al calcular el modelo. Revisa la magnitud de coeficientes y cotas.",
            )
    elif hasattr(value, "model_dump"):
        _ensure_finite(value.model_dump())
    elif isinstance(value, dict):
        for v in value.values():
            _ensure_finite(v)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _ensure_finite(item)


def _require_payoff(model: ModelDefinition) -> PayoffMatrixData:
    payoff = compute_payoff_matrix(model)
    if "error" in payoff.status:
        detail = payoff.status.lower()
        if "infeasible" in detail:
            message = "Modelo infactible. Las cotas y restricciones son incompatibles."
        elif "unbounded" in detail:
            message = "Modelo no acotado. Al menos un objetivo puede mejorar sin límite."
        elif "overflow" in detail or "desbordamiento" in detail:
            message = "Desbordamiento numérico al evaluar objetivos. Revisa la magnitud de coeficientes y cotas."
        else:
            message = "HiGHS no pudo resolver la matriz de pagos. Revisa las escalas y las cotas."
        raise HTTPException(status_code=400, detail=message)
    _ensure_finite(payoff)
    return payoff


@app.post("/api/payoff", response_model=PayoffMatrixData)
def get_payoff_matrix(model: ModelDefinition):
    _validate_model(model)
    return _require_payoff(model)

def _solve_structure(model: ModelDefinition) -> StructureData:
    cache_key = _model_structure_key(model)
    with _CACHE_LOCK:
        cached = _STRUCTURE_CACHE.get(cache_key)
        if cached is not None:
            _STRUCTURE_CACHE.move_to_end(cache_key)
            return cached
        pending = _IN_FLIGHT.get(cache_key)
        owner = pending is None
        if pending is None:
            pending = Future()
            _IN_FLIGHT[cache_key] = pending

    if not owner:
        return pending.result()

    try:
        payoff = _require_payoff(model)
        sensitivity = compute_weight_sensitivity(model, payoff)
        pareto_pts = compute_pareto_frontier(model, payoff, num_samples=21, sensitivity=sensitivity)
        _ensure_finite((pareto_pts, sensitivity))
        result = (payoff, pareto_pts, sensitivity)
        with _CACHE_LOCK:
            _STRUCTURE_CACHE[cache_key] = result
            if len(_STRUCTURE_CACHE) > _MAX_CACHE_SIZE:
                _STRUCTURE_CACHE.popitem(last=False)
        pending.set_result(result)
        return result
    except BaseException as exc:
        pending.set_exception(exc)
        raise
    finally:
        with _CACHE_LOCK:
            del _IN_FLIGHT[cache_key]


@app.post("/api/solve", response_model=SolveResponse)
def solve_model(model: ModelDefinition):
    _validate_model(model)
    payoff, pareto_pts, sensitivity = _solve_structure(model)

    # 2. Soluciones compromiso para los pesos actuales
    solutions, normalized_weights = solve_all_metrics(model, payoff, weights=model.weights)

    failed = [s.metric.replace("L_inf", "L∞") for s in solutions.values() if s.status.startswith("error")]
    incomplete = [
        s.metric.replace("L_inf", "L∞")
        for s in solutions.values()
        if s.status != "optimal" and not s.status.startswith("error")
    ]
    if failed and incomplete:
        msg = (
            f"No se pudo verificar solución factible para {', '.join(failed)}; "
            f"optimalidad sin confirmar para {', '.join(incomplete)}."
        )
    elif failed:
        msg = f"No se pudo verificar solución factible para {', '.join(failed)}."
    elif incomplete:
        msg = f"Optimalidad sin confirmar para {', '.join(incomplete)}."
    else:
        msg = "Optimalidad confirmada para las tres métricas dentro de las tolerancias del motor."

    response = SolveResponse(
        status="partial" if (failed or incomplete) else "optimal",
        message=msg,
        payoff=payoff,
        solutions=solutions,
        weights=normalized_weights,
        pareto_points=pareto_pts,
        weight_sensitivity=sensitivity,
    )
    _ensure_finite(response)
    return response

@app.post("/api/pareto", response_model=ParetoResponse)
def get_pareto_frontier(model: ModelDefinition):
    _validate_model(model)
    payoff = _require_payoff(model)
    pareto_pts = compute_pareto_frontier(model, payoff, num_samples=25)
    response = ParetoResponse(pareto_points=pareto_pts)
    _ensure_finite(response)
    return response

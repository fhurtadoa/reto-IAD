"""
API Principal de OptiCompromise en FastAPI.
Compatible con Vercel Serverless Functions y ejecución local con uvicorn.
"""
import math
from fastapi import FastAPI, HTTPException, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pathlib import Path
import re
import unicodedata
import json
from pydantic import BaseModel, Field, ValidationError
import hashlib
from collections import OrderedDict
from concurrent.futures import Future
from threading import Lock
from typing import Tuple, List

try:
    from .core.schemas import ModelDefinition, PayoffMatrixData, SolveResponse, ParetoPoint, ParetoResponse
    from .core.payoff import compute_payoff_matrix
    from .core.compromise import solve_all_metrics
    from .core.pareto import compute_pareto_frontier
    from .core.sensitivity import compute_weight_sensitivity
    from .core.schemas import WeightSensitivityData
    from .excel_export import build_results_workbook
    from .pdf_export import build_results_pdf
    from .report_images import ChartImage, ChartInput, report_text
except (ImportError, ValueError):
    from core.schemas import ModelDefinition, PayoffMatrixData, SolveResponse, ParetoPoint, ParetoResponse
    from core.payoff import compute_payoff_matrix
    from core.compromise import solve_all_metrics
    from core.pareto import compute_pareto_frontier
    from core.sensitivity import compute_weight_sensitivity
    from core.schemas import WeightSensitivityData
    from excel_export import build_results_workbook
    from pdf_export import build_results_pdf
    from report_images import ChartImage, ChartInput, report_text

app = FastAPI(
    title="OptiCompromise API",
    description="Motor de Optimización Multiobjetivo por Programación de Compromiso (IAD - UNAL)",
    version="1.0.0"
)


@app.exception_handler(RequestValidationError)
async def handle_request_validation(request: Request, exception: RequestValidationError):
    if request.url.path not in {"/api/export/excel", "/api/export/pdf"}:
        return await request_validation_exception_handler(request, exception)
    fields = ", ".join(dict.fromkeys(".".join(map(str, issue["loc"][1:])) or "solicitud"
                                      for issue in exception.errors()[:5]))
    return JSONResponse(status_code=422, content={"detail": f"Datos inválidos en el reporte: {fields}."})

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


class ResultsExportRequest(BaseModel):
    model: ModelDefinition
    result: SolveResponse
    charts: list[ChartInput] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)


def _validate_report_result(model: ModelDefinition, result: SolveResponse) -> None:
    """Validate a solver snapshot before either renderer accesses its rows."""
    _ensure_finite(result)
    count = len(model.objectives)
    names = {variable.name for variable in model.variables}
    metrics = {"L1", "L2", "L_inf"}

    def require(condition: bool, field: str) -> None:
        if not condition:
            raise HTTPException(status_code=422, detail=f"Dimensiones o valores incompatibles en {field} del reporte.")

    def objective_weights(weights: list[float]) -> bool:
        return len(weights) == count and all(0 <= w <= 1 for w in weights) and abs(sum(weights) - 1) <= .001 + 1e-12

    payoff = result.payoff
    require(objective_weights(result.weights), "weights")
    require(payoff.headers == [objective.name for objective in model.objectives], "payoff.headers")
    for field in ("ideal_point", "anti_ideal_point", "normalization_ranges"):
        require(len(getattr(payoff, field)) == count, f"payoff.{field}")
    require(len(payoff.matrix) == count and all(len(row) == count for row in payoff.matrix), "payoff.matrix")
    require(len(payoff.independent_solutions) == count and
            all(set(row) == names for row in payoff.independent_solutions), "payoff.independent_solutions")
    require(not payoff.normalization_sources or len(payoff.normalization_sources) == count,
            "payoff.normalization_sources")
    require(all(0 <= i < count for i in payoff.degenerate_objectives), "payoff.degenerate_objectives")
    require(payoff.decision_ranges_2d is None or
            (len(names) == len(payoff.decision_ranges_2d) == 2), "payoff.decision_ranges_2d")

    require(result.status in {"optimal", "partial"} and set(result.solutions) == metrics, "solutions")
    for key, solution in result.solutions.items():
        require(solution.metric == key, f"solutions.{key}.metric")
        lengths = (len(solution.objectives), len(solution.achievement_pct), len(solution.normalized_distances))
        if result.status == "partial" and solution.status.startswith("error"):
            require(not any(lengths) and not solution.variables, f"solutions.{key}")
        else:
            require(lengths == (count, count, count) and set(solution.variables) == names and
                    solution.status in {"optimal", "feasible_suboptimal"}, f"solutions.{key}")

    for i, point in enumerate(result.pareto_points or []):
        require(len(point.objectives) == count and objective_weights(point.weights) and
                set(point.variables) == names and point.metric in metrics, f"pareto_points[{i}]")

    sweep = result.weight_sensitivity
    if sweep is not None:
        require(count == 2 and sweep.objective_names == payoff.headers and 0 <= sweep.objective_index < count,
                "weight_sensitivity")
        for key in ("l1", "l2", "l_inf"):
            for point in getattr(sweep, key):
                available = len(point.objectives) == len(point.deviations_pct) == count
                failed = point.status.startswith("error") and not point.objectives and not point.deviations_pct
                require(objective_weights(point.weights) and 0 <= point.w1 <= 1 and (available or failed),
                        f"weight_sensitivity.{key}")


def _report_images(req: ResultsExportRequest) -> list[ChartImage]:
    _validate_model(req.model)
    _validate_report_result(req.model, req.result)
    display_text = (
        req.model.name, req.model.description, req.model.reference, req.result.message,
        *(item.name for item in [*req.model.variables, *req.model.objectives, *req.model.constraints]),
        *(solution.status for solution in req.result.solutions.values()),
        *(point.status for point in req.result.pareto_points or []),
    )
    if any(value is not None and report_text(value) != value for value in display_text):
        raise HTTPException(status_code=422, detail="El modelo o resultado contiene caracteres de control incompatibles con el reporte.")
    try:
        return [ChartImage.from_input(chart) for chart in req.charts]
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _report_response(req: ResultsExportRequest, data: bytes, extension: str, media_type: str) -> Response:
    decomposed = unicodedata.normalize("NFD", req.model.name)
    ascii_name = "".join(char for char in decomposed if not unicodedata.combining(char))
    safe_name = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_") or "modelo"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="OptiCompromise_{safe_name}.{extension}"'},
    )


@app.post("/api/export/excel")
def export_results_excel(req: ResultsExportRequest):
    charts = _report_images(req)
    data = build_results_workbook(req.model, req.result, charts, req.warnings)
    return _report_response(req, data, "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/export/pdf")
def export_results_pdf(req: ResultsExportRequest):
    charts = _report_images(req)
    data = build_results_pdf(req.model, req.result, charts, req.warnings)
    return _report_response(req, data, "pdf", "application/pdf")


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
LEGACY_EXAMPLES = {
    "celdas": "01_celdas_fotovoltaicas.json",
    "transporte": "02_problema_transporte.json",
    "triobjetivo": "04_triobjetivo_3d.json",
    "mip": "03_mip_produccion.json",
    "flota": "05_flota_vehiculos.json",
}


def _load_example(path: Path) -> ModelDefinition:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado.")
    try:
        model = ModelDefinition.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except ValidationError as exc:
        field = ".".join(str(part) for part in exc.errors()[0]["loc"])
        raise HTTPException(status_code=422, detail=f"Revisa el campo «{field or 'JSON'}» en {path.name}.") from exc
    try:
        _validate_model(model)
    except HTTPException as exc:
        raise HTTPException(status_code=422, detail=f"{path.name}: {exc.detail}") from exc
    return model


_EXAMPLES_CACHE: dict[tuple, dict] = {}


@app.get("/api/examples")
def list_examples():
    json_paths = sorted(EXAMPLES_DIR.glob("*.json"))
    cache_key = (
        str(EXAMPLES_DIR),
        tuple((p.name, p.stat().st_mtime_ns) for p in json_paths),
    )
    cached = _EXAMPLES_CACHE.get(cache_key)
    if cached is not None:
        return cached

    files = dict(LEGACY_EXAMPLES)
    for path in json_paths:
        if path.stem != "blank" and path.name not in LEGACY_EXAMPLES.values() and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", path.stem):
            files.setdefault(path.stem, path.name)

    exercises = []
    errors = []
    for exercise_id, filename in files.items():
        try:
            model = _load_example(EXAMPLES_DIR / filename)
            exercises.append({
                "id": exercise_id, "label": model.name,
                "badge": f"{len(model.variables)} variables · {len(model.objectives)} objetivos",
            })
        except HTTPException as exc:
            errors.append(str(exc.detail))
    payload = {"exercises": exercises, "errors": errors}
    _EXAMPLES_CACHE.clear()
    _EXAMPLES_CACHE[cache_key] = payload
    return payload


@app.get("/api/examples/{example_id}", response_model=ModelDefinition)
def get_example_model(example_id: str):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", example_id) or example_id in ("blank", *[Path(f).stem for f in LEGACY_EXAMPLES.values()]):
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado.")
    return _load_example(EXAMPLES_DIR / LEGACY_EXAMPLES.get(example_id, f"{example_id}.json"))

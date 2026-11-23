"""
Esquemas Pydantic para definición de modelos multiobjetivo y respuestas de optimización.
"""
from typing import List, Dict, Optional, Literal, Tuple
from pydantic import BaseModel, Field

class VariableModel(BaseModel):
    name: str = Field(..., description="Identificador único de la variable (ej. x1, x2)")
    var_type: Literal["continuous", "integer", "binary"] = Field(
        default="continuous", description="Tipo de variable: continua, entera o binaria"
    )
    lower_bound: Optional[float] = Field(default=0.0, description="Cota inferior (None para sin límite)")
    upper_bound: Optional[float] = Field(default=None, description="Cota superior (None para sin límite)")

class ObjectiveModel(BaseModel):
    name: str = Field(..., description="Nombre del objetivo (ej. Utilidad, Costo, Emisiones)")
    sense: Literal["maximize", "minimize"] = Field(
        default="maximize", description="Sentido de optimización"
    )
    coefficients: List[float] = Field(
        default_factory=list, description="Coeficientes lineales correspondientes a cada variable"
    )
    expression: Optional[str] = Field(
        default=None, description="Expresión matemática opcional (para visualización o no lineales)"
    )

class ConstraintModel(BaseModel):
    name: str = Field(default="Restricción", description="Etiqueta descriptiva de la restricción")
    coefficients: List[float] = Field(
        default_factory=list, description="Coeficientes lineales correspondientes a cada variable"
    )
    sense: Literal["<=", ">=", "=="] = Field(default="<=", description="Sentido de la restricción")
    rhs: float = Field(..., description="Término independiente o lado derecho (Right Hand Side)")
    expression: Optional[str] = Field(default=None, description="Expresión opcional en texto")

class ModelDefinition(BaseModel):
    name: str = Field(default="Modelo Multiobjetivo", description="Nombre del problema de decisión")
    description: Optional[str] = Field(default="", description="Descripción del contexto del problema")
    reference: Optional[str] = None
    variables: List[VariableModel] = Field(..., description="Lista de variables de decisión")
    objectives: List[ObjectiveModel] = Field(..., description="Lista de funciones objetivo (al menos 2 o 3)")
    constraints: List[ConstraintModel] = Field(default_factory=list, description="Lista de restricciones")
    weights: Optional[List[float]] = Field(
        default=None, description="Pesos asignados a los objetivos (si se omite, se asignan pesos iguales)"
    )

    pareto_seed: int = Field(default=42, ge=0, le=2**32 - 1)

class PayoffMatrixData(BaseModel):
    headers: List[str]
    matrix: List[List[float]]  # Fila k: evaluación de todos los objetivos bajo la solución óptima del objetivo k
    ideal_point: List[float]   # Mejor valor encontrado para cada objetivo
    anti_ideal_point: List[float] # Clave histórica del nadir aproximado basado en pagos
    independent_solutions: List[Dict[str, float]]
    normalization_ranges: List[float] = Field(default_factory=list)
    normalization_sources: List[Literal["payoff", "feasible_range", "constant", "unit"]] = Field(default_factory=list)
    decision_ranges_2d: Optional[List[Tuple[Optional[float], Optional[float]]]] = None
    degenerate_objectives: List[int] = Field(
        default_factory=list,
        description="Índices (0-based) de objetivos cuyo rango Ideal-Nadir fue nulo antes del ajuste numérico"
    )
    status: str = "optimal"

class MetricSolution(BaseModel):
    metric: str  # "L1", "L2", "L_inf"
    variables: Dict[str, float]
    objectives: List[float]
    achievement_pct: List[float]  # 100 * (1 - D_i) [%]
    normalized_distances: List[float]  # D_i
    aggregate_distance: float
    status: str = "optimal"

class ParetoPoint(BaseModel):
    weights: List[float]
    objectives: List[float]
    variables: Dict[str, float]
    metric: str
    status: str = "optimal"

class SensitivityPoint(BaseModel):
    w1: float
    weights: List[float]
    deviations_pct: List[float]
    objectives: List[float]
    status: str
    variables: Dict[str, float] = Field(default_factory=dict, exclude=True)

class WeightSensitivityData(BaseModel):
    objective_index: int
    objective_name: str
    objective_names: List[str]
    l1: List[SensitivityPoint]
    l2: List[SensitivityPoint]
    l_inf: List[SensitivityPoint]

class SolveResponse(BaseModel):
    status: str
    message: str
    payoff: PayoffMatrixData
    solutions: Dict[str, MetricSolution]  # "L1", "L2", "L_inf"
    weights: List[float]
    pareto_points: Optional[List[ParetoPoint]] = None
    weight_sensitivity: Optional[WeightSensitivityData] = None


class ParetoResponse(BaseModel):
    pareto_points: List[ParetoPoint]

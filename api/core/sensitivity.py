"""Barrido de pesos para modelos biobjetivo, conservando cada muestra."""
import numpy as np

from .compromise import solve_all_metrics
from .schemas import ModelDefinition, PayoffMatrixData, SensitivityPoint, WeightSensitivityData


def compute_weight_sensitivity(
    model: ModelDefinition, payoff: PayoffMatrixData, num_samples: int = 21
) -> WeightSensitivityData | None:
    if len(model.objectives) != 2:
        return None
    if num_samples < 2:
        raise ValueError("El barrido requiere al menos dos muestras.")

    has_integer = any(v.var_type in ("integer", "binary") for v in model.variables)
    curves = {"L1": [], "L2": [], "L_inf": []}
    for sample in np.linspace(0, 1, num_samples):
        weights = [float(sample), float(1 - sample)]
        solutions, _ = solve_all_metrics(
            model,
            payoff,
            weights=weights,
            l2_max_nodes=120 if has_integer else 800,
            l2_max_seconds=0.08 if has_integer else 1.0,
        )
        for metric, points in curves.items():
            solution = solutions[metric]
            points.append(SensitivityPoint(
                w1=weights[0],
                weights=weights,
                deviations_pct=[100 * value for value in solution.normalized_distances],
                objectives=solution.objectives,
                status=solution.status,
                variables=solution.variables,
            ))

    return WeightSensitivityData(
        objective_index=0, objective_name=model.objectives[0].name,
        objective_names=[o.name for o in model.objectives],
        l1=curves["L1"], l2=curves["L2"], l_inf=curves["L_inf"],
    )

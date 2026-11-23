"""
Generación y aproximación de la Frontera Eficiente de Pareto.
"""
import numpy as np
from typing import List, Optional
from .schemas import ModelDefinition, PayoffMatrixData, ParetoPoint, WeightSensitivityData
from .compromise import compute_distance_coefficients, solve_l1, solve_l2, solve_linf

def is_dominated(point: List[float], other: List[float], senses: List[str]) -> bool:
    """
    Verifica si 'point' es dominado por 'other'.
    'other' domina a 'point' si es al menos tan bueno en todos los objetivos y estrictamente mejor en al menos uno.
    """
    better_or_equal = True
    strictly_better = False
    
    for val_p, val_o, sense in zip(point, other, senses):
        if sense == "maximize":
            if val_o < val_p - 1e-6:
                better_or_equal = False
                break
            if val_o > val_p + 1e-6:
                strictly_better = True
        else:  # minimize
            if val_o > val_p + 1e-6:
                better_or_equal = False
                break
            if val_o < val_p - 1e-6:
                strictly_better = True
                
    return better_or_equal and strictly_better

def compute_pareto_frontier(
    model: ModelDefinition,
    payoff: PayoffMatrixData,
    num_samples: int = 21,
    sensitivity: Optional[WeightSensitivityData] = None,
) -> List[ParetoPoint]:
    """
    Aproxima la frontera de Pareto barriendo sistemáticamente diferentes vectores de pesos
    y combinando múltiples métricas de compromiso (L1, L2 y L_inf).
    """
    n_objs = len(model.objectives)
    alpha, beta = compute_distance_coefficients(model, payoff)
    senses = [obj.sense for obj in model.objectives]
    var_names = [v.name for v in model.variables]

    weight_vectors = []

    if n_objs == 2:
        for w1 in np.linspace(0.0, 1.0, num_samples):
            weight_vectors.append(np.array([w1, 1.0 - w1]))
    elif n_objs == 3:
        steps = 10 if num_samples == 21 else max(2, num_samples // 2)  # genera 66 combinaciones cuando num_samples=21
        for i in range(steps + 1):
            w1 = i / steps
            for j in range(steps + 1 - i):
                w2 = j / steps
                w3 = (steps - i - j) / steps
                weight_vectors.append(np.array([w1, w2, w3]))
    else:
        # Para > 3 objetivos: vértices puros + centro equitativo + muestreo Dirichlet reproducible
        rng = np.random.default_rng(model.pareto_seed)
        weight_vectors.append(np.ones(n_objs) / n_objs)
        for k in range(n_objs):
            e_k = np.zeros(n_objs)
            e_k[k] = 1.0
            weight_vectors.append(e_k)
        for _ in range(max(num_samples, 36)):
            weight_vectors.append(rng.dirichlet(np.ones(n_objs)))

    raw_points: List[ParetoPoint] = []
    has_integer = any(v.var_type in ("integer", "binary") for v in model.variables)
    reuse_sensitivity = (
        sensitivity is not None
        and n_objs == 2
        and len(sensitivity.l1) == len(weight_vectors)
        and len(sensitivity.l2) == len(weight_vectors)
        and len(sensitivity.l_inf) == len(weight_vectors)
    )

    # Sembrar extremos individuales de la Matriz de Pagos para garantizar que los bordes A y B existan
    if payoff.matrix and payoff.independent_solutions:
        for k, (obj_vals, var_dict) in enumerate(zip(payoff.matrix, payoff.independent_solutions)):
            e_k = np.zeros(n_objs)
            e_k[k] = 1.0
            raw_points.append(
                ParetoPoint(
                    weights=e_k.tolist(),
                    objectives=list(obj_vals),
                    variables=dict(var_dict),
                    metric="L1"
                )
            )

    # Barrer pesos combinando métricas L1 (vértices), L2 (compromiso suave) y L_inf (barrido uniforme minimax)
    for idx, w in enumerate(weight_vectors):
        x0_seed = None
        if reuse_sensitivity:
            pt_l1 = sensitivity.l1[idx]
            if pt_l1.status == "optimal" and pt_l1.variables:
                x0_seed = np.array([pt_l1.variables[vn] for vn in var_names], dtype=float)
                raw_points.append(
                    ParetoPoint(
                        weights=w.tolist(),
                        objectives=list(pt_l1.objectives),
                        variables=dict(pt_l1.variables),
                        metric="L1"
                    )
                )
        else:
            sol_l1 = solve_l1(model, payoff, alpha, beta, w)
            if sol_l1.status == "optimal":
                x0_seed = np.array([sol_l1.variables[vn] for vn in var_names], dtype=float)
                raw_points.append(
                    ParetoPoint(
                        weights=w.tolist(),
                        objectives=sol_l1.objectives,
                        variables=sol_l1.variables,
                        metric="L1"
                    )
                )

        # El barrido minimax incluye pesos interiores cerca de los extremos de la cuadrícula.
        w_pos = np.maximum(w, 1e-3)
        w_pos = w_pos / np.sum(w_pos)
        if reuse_sensitivity and np.allclose(w_pos, w, atol=1e-12):
            pt_inf = sensitivity.l_inf[idx]
            if pt_inf.status == "optimal" and pt_inf.variables:
                raw_points.append(
                    ParetoPoint(
                        weights=w_pos.tolist(),
                        objectives=list(pt_inf.objectives),
                        variables=dict(pt_inf.variables),
                        metric="L_inf"
                    )
                )
        else:
            sol_inf = solve_linf(model, payoff, alpha, beta, w_pos)
            if sol_inf.status == "optimal":
                raw_points.append(
                    ParetoPoint(
                        weights=w_pos.tolist(),
                        objectives=sol_inf.objectives,
                        variables=sol_inf.variables,
                        metric="L_inf"
                    )
                )

        if reuse_sensitivity:
            pt_l2 = sensitivity.l2[idx]
            if pt_l2.status in ("optimal", "feasible_suboptimal") and pt_l2.variables:
                raw_points.append(
                    ParetoPoint(
                        weights=w.tolist(),
                        objectives=list(pt_l2.objectives),
                        variables=dict(pt_l2.variables),
                        metric="L2",
                        status=pt_l2.status,
                    )
                )
        else:
            if has_integer:
                sol_l2 = solve_l2(
                    model,
                    payoff,
                    alpha,
                    beta,
                    w,
                    x0=x0_seed,
                    max_nodes=80,
                    max_seconds=0.05,
                )
            else:
                sol_l2 = solve_l2(model, payoff, alpha, beta, w, x0=x0_seed)
            if sol_l2.status in ("optimal", "feasible_suboptimal"):
                raw_points.append(
                    ParetoPoint(
                        weights=w.tolist(),
                        objectives=sol_l2.objectives,
                        variables=sol_l2.variables,
                        metric="L2",
                        status=sol_l2.status,
                    )
                )

    # Filtrar soluciones dominadas y deduplicar manteniendo diversidad entre métricas L1 / L2 / L_inf
    non_dominated: List[ParetoPoint] = []
    seen_coords: List[np.ndarray] = []
    ideal = np.array(payoff.ideal_point)
    scales = np.array(payoff.normalization_ranges or [1.0] * n_objs)

    # Primero quedarnos con todos los puntos no dominados
    efficient_candidates: List[ParetoPoint] = []
    normalized = [(np.array(p.objectives) - ideal) / scales for p in raw_points]
    for p, coords in zip(raw_points, normalized):
        if not any(is_dominated(coords, other, senses) for other in normalized):
            efficient_candidates.append(p)

    # Priorizar que queden representadas todas las métricas (L1 en extremos, L2 y L_inf en interiores)
    for p in sorted(efficient_candidates, key=lambda p: p.status != "optimal"):
        obj_vals = (np.array(p.objectives) - ideal) / scales
        if any(np.max(np.abs(obj_vals - s)) <= 1e-5 for s in seen_coords):
            continue
        non_dominated.append(p)
        seen_coords.append(obj_vals)

    # Ordenar en 2D por el primer objetivo para trazar la curva continua sin zigzags
    if n_objs == 2:
        non_dominated.sort(key=lambda p: p.objectives[0])

    return non_dominated

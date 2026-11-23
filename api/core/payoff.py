"""
Cálculo de la Matriz de Pagos, Punto Ideal y Nadir aproximado.
"""
import numpy as np
from scipy.optimize import linprog
from typing import Tuple, List, Dict, Optional
from .schemas import ModelDefinition, PayoffMatrixData

_HIGHS_PRECISE_OPTIONS = {
    "primal_feasibility_tolerance": 1e-9,
    "dual_feasibility_tolerance": 1e-9,
    "mip_rel_gap": 0.0,
}


def solve_linprog_precise(
    c: np.ndarray,
    A_ub: Optional[np.ndarray] = None,
    b_ub: Optional[np.ndarray] = None,
    A_eq: Optional[np.ndarray] = None,
    b_eq: Optional[np.ndarray] = None,
    bounds: Optional[List[Tuple[Optional[float], Optional[float]]]] = None,
    integrality: Optional[List[int]] = None,
):
    """Ejecuta HiGHS con tolerancia primal/dual estricta (1e-9) y respaldo estándar si hay inestabilidad numérica."""
    res = linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        integrality=integrality,
        method="highs",
        options=_HIGHS_PRECISE_OPTIONS,
    )
    if not res.success and getattr(res, "status", None) not in (2, 3):
        res = linprog(
            c,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            integrality=integrality,
            method="highs",
            options={"mip_rel_gap": 0.0},
        )
    return res


def _payoff_error(headers: List[str], status: str) -> PayoffMatrixData:
    return PayoffMatrixData(
        headers=headers,
        matrix=[],
        ideal_point=[],
        anti_ideal_point=[],
        independent_solutions=[],
        degenerate_objectives=[],
        status=status,
    )


def clean_solution_vector(
    x: np.ndarray,
    bounds: List[Tuple[Optional[float], Optional[float]]],
    integrality: Optional[List[int]] = None,
) -> np.ndarray:
    """Limpia tolerancias numéricas en cotas y variables enteras/binarias."""
    cleaned = np.array(x, dtype=float)
    if integrality is not None:
        for j, flag in enumerate(integrality):
            if flag == 1 and abs(cleaned[j] - round(float(cleaned[j]))) < 1e-5:
                cleaned[j] = float(round(float(cleaned[j])))
    for j, (lb, ub) in enumerate(bounds):
        if lb is not None and lb - 1e-9 < cleaned[j] < lb:
            cleaned[j] = lb
        if ub is not None and ub < cleaned[j] < ub + 1e-9:
            cleaned[j] = ub
    cleaned[cleaned == 0.0] = 0.0
    return cleaned


def is_feasible(
    x: np.ndarray,
    A_ub: Optional[np.ndarray],
    b_ub: Optional[np.ndarray],
    A_eq: Optional[np.ndarray],
    b_eq: Optional[np.ndarray],
    bounds: List[Tuple[Optional[float], Optional[float]]],
    integrality: Optional[List[int]] = None,
    tol: float = 1e-7,
) -> bool:
    """Verifica estrictamente factibilidad (cotas, desigualdades, igualdades e integralidad)."""
    if x is None or len(x) != len(bounds) or not np.all(np.isfinite(x)):
        return False
    for j, (lb, ub) in enumerate(bounds):
        if lb is not None and x[j] < lb - tol:
            return False
        if ub is not None and x[j] > ub + tol:
            return False
    if A_ub is not None and b_ub is not None and len(b_ub) > 0:
        scale_ub = np.maximum(np.linalg.norm(A_ub, axis=1), np.maximum(np.abs(b_ub), 1.0))
        if np.any((A_ub @ x - b_ub) / scale_ub > tol):
            return False
    if A_eq is not None and b_eq is not None and len(b_eq) > 0:
        scale_eq = np.maximum(np.linalg.norm(A_eq, axis=1), np.maximum(np.abs(b_eq), 1.0))
        if np.any(np.abs(A_eq @ x - b_eq) / scale_eq > tol):
            return False
    if integrality is not None:
        for j, is_int in enumerate(integrality):
            if is_int == 1 and abs(x[j] - round(float(x[j]))) > 1e-7:
                return False
    return True


def scale_linear_objective(coefficients: np.ndarray) -> np.ndarray:
    """Usa una escala positiva para que el solver no trate todo el costo como cero."""
    scale = float(np.max(np.abs(coefficients), initial=0.0))
    return coefficients / scale if scale and np.isfinite(scale) else coefficients


def build_linear_constraints(model: ModelDefinition) -> Tuple[
    Optional[np.ndarray], Optional[np.ndarray],
    Optional[np.ndarray], Optional[np.ndarray],
    List[Tuple[Optional[float], Optional[float]]],
    Optional[List[int]]
]:
    """
    Construye las matrices y vectores estándar para scipy.optimize.linprog:
    A_ub @ x <= b_ub
    A_eq @ x == b_eq
    bounds y vector de integrality (para MIP).
    """
    n_vars = len(model.variables)
    
    A_ub_list, b_ub_list = [], []
    A_eq_list, b_eq_list = [], []
    
    for c in model.constraints:
        coeffs = list(c.coefficients)
        if len(coeffs) < n_vars:
            coeffs += [0.0] * (n_vars - len(coeffs))
        coeffs = np.array(coeffs[:n_vars], dtype=float)
        
        rhs = float(c.rhs)
        # Equivalent rows should have the same numerical representation.
        scale = np.max(np.abs(coeffs), initial=0.0)
        if scale and np.isfinite(rhs / scale):
            coeffs = coeffs / scale
            rhs /= scale

        if c.sense == "<=":
            A_ub_list.append(coeffs)
            b_ub_list.append(rhs)
        elif c.sense == ">=":
            A_ub_list.append(-coeffs)
            b_ub_list.append(-rhs)
        elif c.sense == "==":
            A_eq_list.append(coeffs)
            b_eq_list.append(rhs)
            
    A_ub = np.array(A_ub_list) if A_ub_list else None
    b_ub = np.array(b_ub_list) if b_ub_list else None
    A_eq = np.array(A_eq_list) if A_eq_list else None
    b_eq = np.array(b_eq_list) if b_eq_list else None
    
    # Cotas y tipos de variables
    bounds = []
    integrality = []
    has_integer = False
    
    for v in model.variables:
        lb = v.lower_bound
        ub = v.upper_bound
        if v.var_type == "binary":
            lb = 0.0 if lb is None else float(np.ceil(max(0.0, lb)))
            ub = 1.0 if ub is None else float(np.floor(min(1.0, ub)))
            integrality.append(1)
            has_integer = True
        elif v.var_type == "integer":
            if lb is not None:
                lb = float(np.ceil(lb))
            if ub is not None:
                ub = float(np.floor(ub))
            integrality.append(1)
            has_integer = True
        else:
            integrality.append(0)
        bounds.append((lb, ub))
        
    integrality_vector = integrality if has_integer else None
    return A_ub, b_ub, A_eq, b_eq, bounds, integrality_vector

def compute_payoff_matrix(model: ModelDefinition) -> PayoffMatrixData:
    """
    Resuelve cada objetivo mono-objetivo de forma independiente y genera la matriz de pagos.
    """
    n_vars = len(model.variables)
    n_objs = len(model.objectives)
    A_ub, b_ub, A_eq, b_eq, bounds, integrality = build_linear_constraints(model)

    headers = [obj.name for obj in model.objectives]
    if any(lo is not None and hi is not None and lo > hi for lo, hi in bounds):
        return _payoff_error(headers, "error: infeasible integer bounds")
    for rows, rhs, equality in ((A_ub, b_ub, False), (A_eq, b_eq, True)):
        if rows is not None:
            constant_rhs = rhs[~np.any(rows, axis=1)]
            if np.any(constant_rhs != 0 if equality else constant_rhs < 0):
                return _payoff_error(headers, "error: infeasible constant constraint")

    payoff_matrix = np.zeros((n_objs, n_objs), dtype=float)
    independent_solutions: List[Dict[str, float]] = []
    
    var_names = [v.name for v in model.variables]
    
    # 1. Optimización independiente de cada objetivo (con desempate lexicográfico para evitar soluciones dominadas)
    obj_dirs: List[np.ndarray] = []
    for obj in model.objectives:
        coeffs = list(obj.coefficients)
        if len(coeffs) < n_vars:
            coeffs += [0.0] * (n_vars - len(coeffs))
        arr = np.array(coeffs[:n_vars], dtype=float)
        obj_dirs.append(scale_linear_objective(-arr if obj.sense == "maximize" else arr))

    for k, obj in enumerate(model.objectives):
        c_solver = obj_dirs[k]

        res = solve_linprog_precise(
            c_solver,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            integrality=integrality,
        )

        if not res.success or res.x is None:
            return _payoff_error(headers, f"error: {res.message} en objetivo {obj.name}")

        x_opt = clean_solution_vector(res.x, bounds, integrality)
        if not np.all(np.isfinite(x_opt)):
            return _payoff_error(headers, f"error: numerical overflow en objetivo {obj.name}")

        # Desempate lexicográfico secundario: entre todos los óptimos alternativos de Z_k,
        # elegir el que mejor desempeña en los demás objetivos para no fabricar un Nadir dominado.
        if n_objs >= 2:
            z_k_opt = float(np.dot(c_solver, x_opt))
            if np.isfinite(z_k_opt):
                lex_A_eq = (
                    np.vstack([A_eq, c_solver[np.newaxis, :]])
                    if A_eq is not None and len(A_eq) > 0
                    else c_solver[np.newaxis, :]
                )
                lex_b_eq = (
                    np.concatenate([b_eq, [z_k_opt]])
                    if b_eq is not None and len(b_eq) > 0
                    else np.array([z_k_opt], dtype=float)
                )
                fixed_checks: List[Tuple[np.ndarray, float]] = [(c_solver, z_k_opt)]

                def _try_lex_dir(dir_vec: np.ndarray, eq_A: np.ndarray, eq_b: np.ndarray) -> Optional[np.ndarray]:
                    res_lex = solve_linprog_precise(
                        scale_linear_objective(dir_vec),
                        A_ub=A_ub,
                        b_ub=b_ub,
                        A_eq=eq_A,
                        b_eq=eq_b,
                        bounds=bounds,
                        integrality=integrality,
                    )
                    if res_lex.success and res_lex.x is not None and np.all(np.isfinite(res_lex.x)):
                        cand = clean_solution_vector(res_lex.x, bounds, integrality)
                        if (
                            is_feasible(cand, A_ub, b_ub, A_eq, b_eq, bounds, integrality, tol=1e-8)
                            and all(
                                float(np.dot(f_vec, cand)) <= f_val + 1e-9 * max(abs(f_val), float(np.abs(f_vec) @ np.abs(cand)))
                                for f_vec, f_val in fixed_checks
                            )
                        ):
                            return cand
                    return None

                secondary = np.zeros(n_vars, dtype=float)
                for j in range(n_objs):
                    if j == k:
                        continue
                    norm_j = float(np.linalg.norm(obj_dirs[j]))
                    if norm_j > 1e-12:
                        secondary += obj_dirs[j] / norm_j

                sec_norm = float(np.linalg.norm(secondary))
                if sec_norm > 1e-12:
                    cand = _try_lex_dir(secondary, lex_A_eq, lex_b_eq)
                    if cand is not None:
                        x_opt = cand
                        sec_val = float(np.dot(secondary, x_opt))
                        if np.isfinite(sec_val):
                            lex_A_eq = np.vstack([lex_A_eq, secondary[np.newaxis, :]])
                            lex_b_eq = np.concatenate([lex_b_eq, [sec_val]])
                            fixed_checks.append((secondary, sec_val))

                # Si las direcciones secundarias se cancelan o hay >= 3 objetivos,
                # desempatar secuencialmente objetivo por objetivo para evitar caras dominadas.
                if sec_norm <= 1e-12 or n_objs >= 3:
                    for j in range(n_objs):
                        if j == k or float(np.linalg.norm(obj_dirs[j])) <= 1e-12:
                            continue
                        cand = _try_lex_dir(obj_dirs[j], lex_A_eq, lex_b_eq)
                        if cand is not None:
                            x_opt = cand
                        j_val = float(np.dot(obj_dirs[j], x_opt))
                        if np.isfinite(j_val):
                            lex_A_eq = np.vstack([lex_A_eq, obj_dirs[j][np.newaxis, :]])
                            lex_b_eq = np.concatenate([lex_b_eq, [j_val]])
                            fixed_checks.append((obj_dirs[j], j_val))

        x_opt = clean_solution_vector(x_opt, bounds, integrality)
        if not is_feasible(x_opt, A_ub, b_ub, A_eq, b_eq, bounds, integrality, tol=1e-8):
            return _payoff_error(headers, f"error: la solución óptima de {obj.name} no cumple el modelo")

        independent_solutions.append({var_names[j]: float(x_opt[j]) for j in range(n_vars)})

        # Evaluar todos los objetivos bajo esta solución óptima x^(k)*
        for i, eval_obj in enumerate(model.objectives):
            eval_coeffs = list(eval_obj.coefficients)
            if len(eval_coeffs) < n_vars:
                eval_coeffs += [0.0] * (n_vars - len(eval_coeffs))
            eval_coeffs = np.array(eval_coeffs[:n_vars], dtype=float)
            with np.errstate(over="ignore", invalid="ignore"):
                val = float(np.dot(eval_coeffs, x_opt))
            if not np.isfinite(val):
                return _payoff_error(headers, f"error: numerical overflow evaluating objective {eval_obj.name}")
            payoff_matrix[k, i] = val or 0.0

    # 2. Determinar punto ideal, referencia de pagos y escalas
    ideal_point = []
    anti_ideal_point = []
    degenerate_objectives: List[int] = []
    normalization_ranges = []
    normalization_sources = []

    payoff_vectors = np.abs(np.array([list(row.values()) for row in independent_solutions]))
    for i, obj in enumerate(model.objectives):
        col_vals = payoff_matrix[:, i]
        if obj.sense == "maximize":
            z_ideal = float(np.max(col_vals))
            z_anti = float(np.min(col_vals))
        else:
            z_ideal = float(np.min(col_vals))
            z_anti = float(np.max(col_vals))

        with np.errstate(over="ignore", invalid="ignore"):
            scale = abs(z_ideal - z_anti)
            # Comparar con el redondeo de la evaluación, en unidades del criterio.
            # Una tolerancia absoluta anularía objetivos pequeños pero válidos.
            coefficients = np.abs(np.asarray(obj.coefficients, dtype=float))
            magnitude = float(np.max(payoff_vectors[:, :len(coefficients)] @ coefficients))
        if not np.isfinite(z_ideal) or not np.isfinite(z_anti) or not np.isfinite(scale) or not np.isfinite(magnitude):
            return _payoff_error(headers, f"error: numerical overflow evaluating objective {obj.name}")
        roundoff = 16 * np.finfo(float).eps * magnitude
        source = "payoff"
        if scale <= roundoff:
            degenerate_objectives.append(i)
            # La referencia de pagos se conserva. Solo se sustituye el denominador.
            worst = solve_linprog_precise(
                -obj_dirs[i], A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                bounds=bounds, integrality=integrality,
            )
            if worst.success and worst.x is not None and np.all(np.isfinite(worst.x)):
                original = np.asarray(obj.coefficients, dtype=float)
                with np.errstate(over="ignore", invalid="ignore"):
                    z_worst = float(original @ worst.x[:len(original)])
                    worst_magnitude = float(np.abs(original) @ np.abs(worst.x[:len(original)]))
                    span = z_ideal - z_worst if obj.sense == "maximize" else z_worst - z_ideal
                if not np.isfinite(z_worst) or not np.isfinite(worst_magnitude) or not np.isfinite(span):
                    return _payoff_error(headers, f"error: numerical overflow evaluating objective {obj.name}")
                scale = max(0.0, span)
                if scale > max(roundoff, 16 * np.finfo(float).eps * worst_magnitude):
                    source = "feasible_range"
                else:
                    scale, source = 1.0, "constant"
            else:
                # Sin peor extremo verificable, una unidad del objetivo sirve de escala explícita.
                scale, source = 1.0, "unit"
        normalization_ranges.append(scale)
        normalization_sources.append(source)

        ideal_point.append(z_ideal)
        anti_ideal_point.append(z_anti)

    decision_ranges = None
    if n_vars == 2:
        decision_ranges = []
        for axis in np.eye(2):
            endpoints = []
            for direction in (1, -1):
                projection = solve_linprog_precise(
                    direction * axis, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                    bounds=bounds,
                )
                endpoints.append(
                    float(direction * projection.fun) or 0.0
                    if projection.success and np.isfinite(projection.fun)
                    else None
                )
            decision_ranges.append(tuple(endpoints))

    return PayoffMatrixData(
        headers=headers,
        matrix=payoff_matrix.tolist(),
        ideal_point=ideal_point,
        anti_ideal_point=anti_ideal_point,
        independent_solutions=independent_solutions,
        degenerate_objectives=degenerate_objectives,
        normalization_ranges=normalization_ranges,
        normalization_sources=normalization_sources,
        decision_ranges_2d=decision_ranges,
        status="optimal"
    )

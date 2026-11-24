"""
Validación contra Benchmarks Externos de Literatura (Bloque B) y Pesos Extremos de Papel (Bloque A.3):
1. B1: Simplex Triobjetivo 3D (Yu 1973 / Zeleny 1982) con solución analítica cerrada en el interior de la cara x1+x2+x3=100.
2. B2: Problema MIP Mixto (variable continua, entera y binaria) certificado por enumeración exhaustiva independiente.
3. B3: Problema con escalas físicas dispares ($10^7, 10^2, [0,1]), restricción de igualdad y sentidos opuestos + invariancia de escala.
4. A3: Certificación de optimalidad L2 (0/21 no óptimos) en Producción de Papel con pesos extremos w1 in {0.05, 0.10, 0.90, 0.95}.
"""
import copy
import math
from pathlib import Path
import unittest
import numpy as np

from core.schemas import ModelDefinition
from core.payoff import compute_payoff_matrix
from core.compromise import solve_all_metrics
from core.pareto import compute_pareto_frontier
from core.sensitivity import compute_weight_sensitivity

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def example(filename: str) -> ModelDefinition:
    return ModelDefinition.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


B1_SIMPLEX_3D = {
    "name": "Benchmark B1 · Simplex Triobjetivo 3D (Yu 1973 / Zeleny 1982)",
    "variables": [
        {"name": "x1", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 100.0},
        {"name": "x2", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 100.0},
        {"name": "x3", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 100.0},
    ],
    "objectives": [
        {"name": "Retorno Z1", "sense": "maximize", "coefficients": [10.0, 0.0, 0.0]},
        {"name": "Calidad Z2", "sense": "maximize", "coefficients": [0.0, 10.0, 0.0]},
        {"name": "Sostenibilidad Z3", "sense": "maximize", "coefficients": [0.0, 0.0, 10.0]},
    ],
    "constraints": [
        {"name": "Simplex Capacidad", "coefficients": [1.0, 1.0, 1.0], "sense": "<=", "rhs": 100.0},
    ],
    "weights": [0.4, 0.3, 0.3],
}

B2_MIP_MIXTO = {
    "name": "Benchmark B2 · MIP Mixto con Costo Fijo",
    "variables": [
        {"name": "x1", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 30.0},
        {"name": "x2", "var_type": "integer", "lower_bound": 0.0, "upper_bound": 10.0},
        {"name": "y1", "var_type": "binary", "lower_bound": 0.0, "upper_bound": 1.0},
    ],
    "objectives": [
        {"name": "Producción Total", "sense": "maximize", "coefficients": [2.0, 5.0, 12.0]},
        {"name": "Costo Total", "sense": "minimize", "coefficients": [1.0, 3.0, 20.0]},
    ],
    "constraints": [
        {"name": "Capacidad con Apertura", "coefficients": [1.0, 2.0, -15.0], "sense": "<=", "rhs": 10.0},
        {"name": "Límite Presupuestal", "coefficients": [1.0, 3.0, 10.0], "sense": "<=", "rhs": 38.0},
        {"name": "Cuota Mínima", "coefficients": [1.0, 1.0, 0.0], "sense": ">=", "rhs": 8.0},
    ],
    "weights": [0.55, 0.45],
}

B3_DISPARATE_SCALES = {
    "name": "Benchmark B3 · Escalas Dispares e Igualdad",
    "variables": [
        {"name": "x1", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 100.0},
        {"name": "x2", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 100.0},
        {"name": "x3", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 100.0},
    ],
    "objectives": [
        {"name": "Costo Inversión (USD)", "sense": "minimize", "coefficients": [1.0e7, 0.2e7, 0.5e7]},
        {"name": "Emisiones (tCO2)", "sense": "minimize", "coefficients": [100.0, 400.0, 250.0]},
        {"name": "Confiabilidad (0-1)", "sense": "maximize", "coefficients": [0.008, 0.002, 0.009]},
    ],
    "constraints": [
        {"name": "Balance Exacto de Mezcla", "coefficients": [1.0, 1.0, 1.0], "sense": "==", "rhs": 100.0},
        {"name": "Capacidad Línea 1-2", "coefficients": [1.0, 2.0, 0.0], "sense": "<=", "rhs": 140.0},
        {"name": "Cuota Mínima Línea 2-3", "coefficients": [0.0, 1.0, 1.0], "sense": ">=", "rhs": 40.0},
    ],
    "weights": [0.4, 0.35, 0.25],
}


class TestExternalBenchmarks(unittest.TestCase):
    def test_b1_triobjective_3d_matches_closed_form_interior_solution(self):
        model = ModelDefinition.model_validate(B1_SIMPLEX_3D)
        payoff = compute_payoff_matrix(model)
        np.testing.assert_allclose(payoff.matrix, [[1000, 0, 0], [0, 1000, 0], [0, 0, 1000]], atol=1e-9)
        solutions, _ = solve_all_metrics(model, payoff, model.weights)

        # L1: vértice puro x* = (100, 0, 0), D1 = 0.6
        self.assertEqual(solutions["L1"].status, "optimal")
        np.testing.assert_allclose(
            [solutions["L1"].variables[f"x{i}"] for i in (1, 2, 3)],
            [100.0, 0.0, 0.0],
            atol=1e-6,
        )
        self.assertAlmostEqual(solutions["L1"].aggregate_distance, 0.6, places=7)

        # L2: interior analítico exacto x* = (2300/41, 900/41, 900/41), D2 = 12 / (5*sqrt(41))
        self.assertEqual(solutions["L2"].status, "optimal")
        np.testing.assert_allclose(
            [solutions["L2"].variables[f"x{i}"] for i in (1, 2, 3)],
            [2300.0 / 41.0, 900.0 / 41.0, 900.0 / 41.0],
            atol=1e-4,
        )
        self.assertAlmostEqual(solutions["L2"].aggregate_distance, 12.0 / (5.0 * math.sqrt(41.0)), places=7)

        # L_inf: interior analítico exacto x* = (500/11, 300/11, 300/11), D_inf = 12 / 55
        self.assertEqual(solutions["L_inf"].status, "optimal")
        np.testing.assert_allclose(
            [solutions["L_inf"].variables[f"x{i}"] for i in (1, 2, 3)],
            [500.0 / 11.0, 300.0 / 11.0, 300.0 / 11.0],
            atol=1e-6,
        )
        self.assertAlmostEqual(solutions["L_inf"].aggregate_distance, 12.0 / 55.0, places=7)

    def test_b2_mip_mixed_matches_exhaustive_enumeration(self):
        model = ModelDefinition.model_validate(B2_MIP_MIXTO)
        payoff = compute_payoff_matrix(model)
        solutions, _ = solve_all_metrics(model, payoff, model.weights)

        # Enumeración exhaustiva independiente sobre todos los pares (x2 in 0..10, y1 in 0..1)
        c_mat = np.array([o["coefficients"] for o in B2_MIP_MIXTO["objectives"]], dtype=float)
        signs = np.array([-1.0, 1.0], dtype=float)
        w = np.array(B2_MIP_MIXTO["weights"], dtype=float)
        intervals = []
        for y1 in (0, 1):
            for x2 in range(11):
                lo = max(0.0, 8.0 - x2)
                hi = min(30.0, 10.0 + 15.0 * y1 - 2.0 * x2, 38.0 - 3.0 * x2 - 10.0 * y1)
                if lo <= hi + 1e-12:
                    intervals.append((lo, hi, float(x2), float(y1)))

        vertices = [np.array([x1, x2, y1]) for lo, hi, x2, y1 in intervals for x1 in (lo, hi)]
        z_verts = [c_mat @ x for x in vertices]
        ideal_ref = [max(z[0] for z in z_verts), min(z[1] for z in z_verts)]
        np.testing.assert_allclose(payoff.ideal_point, ideal_ref, atol=1e-7)
        ranges = np.abs(np.array(payoff.ideal_point) - np.array(payoff.anti_ideal_point))

        for metric in ("L1", "L2", "L_inf"):
            sol = solutions[metric]
            self.assertEqual(sol.status, "optimal")
            self.assertAlmostEqual(sol.variables["x2"], round(sol.variables["x2"]), places=7)
            self.assertIn(round(sol.variables["y1"]), (0, 1))

            best_dp = float("inf")
            best_x = None
            for lo, hi, x2, y1 in intervals:
                p = signs * c_mat[:, 0] / ranges
                q = signs * (c_mat[:, 1] * x2 + c_mat[:, 2] * y1 - np.array(payoff.ideal_point)) / ranges
                wp, wq = w * p, w * q
                cands = [lo, hi]
                if metric == "L2":
                    x1_s = -float(np.sum(wp * wq)) / float(np.sum(wp * wp))
                    if lo <= x1_s <= hi:
                        cands.append(x1_s)
                elif metric == "L_inf":
                    x1_i = (wq[1] - wq[0]) / (wp[0] - wp[1])
                    if lo <= x1_i <= hi:
                        cands.append(x1_i)
                for x1 in cands:
                    xv = np.array([x1, x2, y1])
                    dv = np.maximum(0.0, signs * (c_mat @ xv - np.array(payoff.ideal_point)) / ranges)
                    wd = w * dv
                    dp = float(np.sum(wd) if metric == "L1" else np.linalg.norm(wd) if metric == "L2" else np.max(wd))
                    if dp < best_dp - 1e-12:
                        best_dp, best_x = dp, xv

            self.assertAlmostEqual(sol.aggregate_distance, best_dp, places=7)
            np.testing.assert_allclose(
                [sol.variables["x1"], sol.variables["x2"], sol.variables["y1"]],
                best_x,
                atol=1e-4,
            )

    def test_b3_disparate_scales_and_equality_scale_invariance(self):
        model_orig = ModelDefinition.model_validate(B3_DISPARATE_SCALES)
        pay_orig = compute_payoff_matrix(model_orig)
        sol_orig, _ = solve_all_metrics(model_orig, pay_orig, model_orig.weights)

        rescaled_dict = copy.deepcopy(B3_DISPARATE_SCALES)
        rescaled_dict["objectives"][0]["coefficients"] = [c * 1e-7 for c in B3_DISPARATE_SCALES["objectives"][0]["coefficients"]]
        rescaled_dict["objectives"][1]["coefficients"] = [c * 1e-2 for c in B3_DISPARATE_SCALES["objectives"][1]["coefficients"]]
        rescaled_dict["objectives"][2]["coefficients"] = [c * 1e3 for c in B3_DISPARATE_SCALES["objectives"][2]["coefficients"]]
        model_resc = ModelDefinition.model_validate(rescaled_dict)
        pay_resc = compute_payoff_matrix(model_resc)
        sol_resc, _ = solve_all_metrics(model_resc, pay_resc, model_resc.weights)

        for m in ("L1", "L2", "L_inf"):
            self.assertEqual(sol_orig[m].status, "optimal")
            self.assertEqual(sol_resc[m].status, "optimal")
            self.assertAlmostEqual(sum(sol_orig[m].variables.values()), 100.0, places=6)
            np.testing.assert_allclose(sol_orig[m].normalized_distances, sol_resc[m].normalized_distances, atol=1e-7)
            np.testing.assert_allclose(sol_orig[m].achievement_pct, sol_resc[m].achievement_pct, atol=1e-5)
            self.assertAlmostEqual(sol_orig[m].aggregate_distance, sol_resc[m].aggregate_distance, places=7)

    def test_paper_all_21_pareto_and_sensitivity_samples_are_certified_optimal(self):
        model = example("06_produccion_papel.json")
        payoff = compute_payoff_matrix(model)
        sens = compute_weight_sensitivity(model, payoff, num_samples=21)
        pareto = compute_pareto_frontier(model, payoff, num_samples=21)
        self.assertEqual([p.w1 for p in sens.l2 if p.status != "optimal"], [])
        self.assertEqual([p.weights for p in pareto if p.status != "optimal"], [])


if __name__ == "__main__":
    unittest.main()

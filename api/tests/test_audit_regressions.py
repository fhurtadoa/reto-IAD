"""Regresiones numéricas y del contrato HTTP de OptiCompromise."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from scipy.optimize import linprog

from core.compromise import compute_distance_coefficients, solve_all_metrics, solve_l2
from core.pareto import compute_pareto_frontier
from core.payoff import compute_payoff_matrix
from core.schemas import ModelDefinition
from index import app


EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def example(filename):
    return ModelDefinition.model_validate_json((EXAMPLES / filename).read_text())


class TestAuditRegressions(unittest.TestCase):
    def test_class15_weight_is_squared_in_lp_tradeoff_and_sensitivity(self):
        # d1=1-x, d2=x. The analytic minimizer is w1²/(w1²+w2²).
        model = ModelDefinition.model_validate({
            "variables": [{"name": "x", "upper_bound": 1}],
            "objectives": [
                {"name": "Max x", "sense": "maximize", "coefficients": [1]},
                {"name": "Min x", "sense": "minimize", "coefficients": [1]},
            ],
            "weights": [0.8, 0.2],
        })
        result = TestClient(app).post("/api/solve", json=model.model_dump())
        self.assertEqual(result.status_code, 200)
        body = result.json()
        l2 = body["solutions"]["L2"]
        optimum = 16 / 17
        self.assertAlmostEqual(l2["variables"]["x"], optimum, places=7)
        self.assertAlmostEqual(l2["aggregate_distance"], 0.8 / np.sqrt(17), places=7)
        self.assertAlmostEqual(body["solutions"]["L_inf"]["variables"]["x"], 0.8)
        sweep = body["weight_sensitivity"]["l2"]
        np.testing.assert_allclose(sweep[16]["deviations_pct"], [100 / 17, 1600 / 17])
        self.assertEqual(sweep[0]["deviations_pct"], [100, 0])
        self.assertEqual(sweep[-1]["deviations_pct"], [0, 100])

    def test_paper_asymmetric_weights_match_class_notebook(self):
        model = example("06_produccion_papel.json")
        model.constraints[3].rhs = 83
        model.weights = [0.56, 0.44]
        payoff = compute_payoff_matrix(model)
        solutions, _ = solve_all_metrics(model, payoff, model.weights)
        # Valores publicados con redondeo en el entregable del Taller 3, celda 12.
        self.assertEqual(solutions["L2"].status, "optimal")
        np.testing.assert_allclose(solutions["L2"].objectives, [33727.49, 22062.27], rtol=0, atol=0.02)
        self.assertAlmostEqual(solutions["L2"].aggregate_distance, 0.33333, places=5)

    def test_l2_integer_matches_enumeration_and_reports_cutoff(self):
        model = ModelDefinition.model_validate({
            "variables": [{"name": "x", "var_type": "integer", "upper_bound": 5}],
            "objectives": [
                {"name": "Max x", "sense": "maximize", "coefficients": [1]},
                {"name": "Min x", "sense": "minimize", "coefficients": [1]},
            ],
        })
        payoff = compute_payoff_matrix(model)
        weights = np.array([0.65, 0.35])
        expected = min(range(6), key=lambda x: (0.65 * (1 - x/5))**2 + (0.35 * x/5)**2)
        solutions, _ = solve_all_metrics(model, payoff, weights.tolist())
        self.assertEqual(solutions["L2"].status, "optimal")
        self.assertEqual(solutions["L2"].variables["x"], expected)
        alpha, beta = compute_distance_coefficients(model, payoff)
        partial = solve_l2(model, payoff, alpha, beta, weights, max_nodes=0)
        self.assertEqual(partial.status, "feasible_suboptimal")
        self.assertIn(partial.variables["x"], range(6))

    def test_zero_payoff_span_distinguishes_constant_and_variable_criteria(self):
        model = ModelDefinition.model_validate({
            "variables": [{"name": "x", "upper_bound": 5}, {"name": "y"}],
            "objectives": [
                {"name": "Max x", "sense": "maximize", "coefficients": [1, 0]},
                {"name": "Min y", "sense": "minimize", "coefficients": [0, 1]},
                {"name": "Constante", "sense": "maximize", "coefficients": [0, 0]},
            ],
        })
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.ideal_point, [5, 0, 0])
        self.assertEqual(payoff.anti_ideal_point, [5, 0, 0])
        self.assertEqual(payoff.normalization_sources, ["feasible_range", "unit", "constant"])
        self.assertEqual(payoff.normalization_ranges, [5, 1, 1])
        alpha, beta = compute_distance_coefficients(model, payoff)
        np.testing.assert_allclose(alpha @ [0, 3] + beta, [1, 3, 0])

    def test_payoff_nadir_is_not_a_bound_on_efficient_achievement(self):
        model = ModelDefinition.model_validate({
            "variables": [{"name": f"a{i}"} for i in range(4)],
            "constraints": [{"coefficients": [1, 1, 1, 1], "sense": "==", "rhs": 1}],
            "objectives": [
                {"name": "Z1", "coefficients": [10, 0, 5, 6]},
                {"name": "Z2", "coefficients": [0, 10, 5, 6]},
                {"name": "Z3", "coefficients": [5, 5, 10, 0]},
            ],
        })
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.anti_ideal_point, [0, 0, 5])
        solutions, _ = solve_all_metrics(model, payoff, [0.5, 0.5, 0])
        # D maximiza de forma única Z1+Z2. Su tercer objetivo queda bajo la referencia.
        l1 = solutions["L1"]
        self.assertEqual(l1.objectives, [6, 6, 0])
        self.assertEqual(l1.normalized_distances[2], 2)
        self.assertEqual(l1.achievement_pct[2], -100)

    def test_pareto_sample_preserves_partial_solver_status(self):
        model = ModelDefinition.model_validate({
            "variables": [{"name": "x", "upper_bound": 1}],
            "objectives": [
                {"name": "Max x", "sense": "maximize", "coefficients": [1]},
                {"name": "Min x", "sense": "minimize", "coefficients": [1]},
            ],
        })
        payoff = compute_payoff_matrix(model)
        def partial(*args, **kwargs):
            solution = solve_l2(*args, **kwargs)
            return solution.model_copy(update={"status": "feasible_suboptimal"})

        with patch("core.pareto.solve_l2", side_effect=partial):
            points = compute_pareto_frontier(model, payoff, num_samples=5)
        l2_points = [p for p in points if p.metric == "L2"]
        self.assertTrue(l2_points)
        self.assertTrue(all(p.status == "feasible_suboptimal" for p in l2_points))

    def test_minimax_with_large_variable_bounds(self):
        model = ModelDefinition.model_validate({
            "name": "Escala de minimax",
            "variables": [{"name": "x", "upper_bound": 1e9}],
            "objectives": [
                {"name": "Min x", "sense": "minimize", "coefficients": [1]},
                {"name": "Max x", "sense": "maximize", "coefficients": [1]},
            ],
            "weights": [0.5, 0.5],
        })
        solutions, _ = solve_all_metrics(model, compute_payoff_matrix(model), model.weights)
        self.assertEqual(solutions["L_inf"].status, "optimal")
        self.assertAlmostEqual(solutions["L_inf"].variables["x"] / 1e9, 0.5)
        self.assertAlmostEqual(solutions["L_inf"].aggregate_distance, 0.25)

    def test_equivalent_constraint_row_scales(self):
        for scale in (1e-12, 1e-10, 1.0, 1e12):
            with self.subTest(scale=scale):
                response = TestClient(app).post("/api/solve", json={
                    "name": "Escala de restricción",
                    "variables": [{"name": "x", "upper_bound": 2}],
                    "objectives": [
                        {"name": "Min x", "sense": "minimize", "coefficients": [1]},
                        {"name": "Max x", "sense": "maximize", "coefficients": [1]},
                    ],
                    "constraints": [{"sense": ">=", "coefficients": [scale], "rhs": scale}],
                    "weights": [0.5, 0.5],
                })
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["payoff"]["ideal_point"], [1.0, 2.0])
                self.assertEqual(data["solutions"]["L_inf"]["status"], "optimal")
                self.assertAlmostEqual(data["solutions"]["L_inf"]["variables"]["x"], 1.5)
                self.assertTrue(all(sol["variables"]["x"] >= 1 for sol in data["solutions"].values()))

    def test_pareto_preserves_tradeoff_under_rescaling(self):
        response = TestClient(app).post("/api/solve", json={
            "name": "Canje",
            "variables": [{"name": "x", "upper_bound": 1}, {"name": "y", "upper_bound": 1}],
            "objectives": [
                {"name": "Min x", "sense": "minimize", "coefficients": [5e-7, 0]},
                {"name": "Min y", "sense": "minimize", "coefficients": [0, 1]},
            ],
            "constraints": [{"sense": ">=", "coefficients": [1, 1], "rhs": 1}],
        })
        self.assertEqual(response.status_code, 200)
        points = response.json()["pareto_points"]
        self.assertGreater(len(points), 2)
        self.assertAlmostEqual(min(p["objectives"][1] for p in points), 0)
        self.assertAlmostEqual(max(p["objectives"][1] for p in points), 1)

    def test_celdas_l2_matches_analytic_solution(self):
        model = example("01_celdas_fotovoltaicas.json")
        solutions, _ = solve_all_metrics(model, compute_payoff_matrix(model), model.weights)
        solution = solutions["L2"]

        # En la arista x1=0, el óptimo satisface d(D1²+D2²)/dx2=0.
        x2 = (0.006 * 1.6 + 0.005 * 0.5) / (0.006**2 + 0.005**2)
        x = list(solution.variables.values())
        np.testing.assert_allclose(x, [0, x2], atol=1e-5)
        np.testing.assert_allclose(solution.objectives, [3000 * x2, 2 * x2], atol=0.02)
        self.assertEqual(solution.status, "optimal")

    def test_transport_l2_has_supporting_hyperplane(self):
        model = example("02_problema_transporte.json")
        solutions, _ = solve_all_metrics(model, compute_payoff_matrix(model), model.weights)
        expected = np.array([17400, 3600])
        np.testing.assert_allclose(solutions["L2"].objectives, expected, atol=0.1)
        np.testing.assert_allclose(solutions["L_inf"].objectives, [17382.3288, 3661.8790], atol=0.1)

        # Verificación independiente: la tangente del objetivo cuadrático en el
        # resultado publicado debe soportar el conjunto factible de transporte.
        c = np.array([o.coefficients for o in model.objectives])
        z_ideal = np.array([16800, 2600])
        ranges = np.array([1700, 3100])
        tangent_weights = (expected - z_ideal) / ranges**2
        signs = np.array([1 if row.sense == "<=" else -1 for row in model.constraints])
        rows = np.array([row.coefficients for row in model.constraints])
        rhs = np.array([row.rhs for row in model.constraints])
        support = linprog(tangent_weights @ c, A_ub=rows * signs[:, None], b_ub=rhs * signs)
        self.assertTrue(support.success)
        self.assertAlmostEqual(support.fun, tangent_weights @ expected, places=7)

    def test_new_model_minimax_does_not_force_equal_achievement(self):
        model = ModelDefinition.model_validate({
            "variables": [
                {"name": "x", "upper_bound": 1}, {"name": "y", "upper_bound": 1},
            ],
            "objectives": [
                {"name": "Beneficio", "coefficients": [1, 0]},
                {"name": "Costo", "sense": "minimize", "coefficients": [1, 0]},
                {"name": "Cuota", "coefficients": [0, 1]},
            ],
            "constraints": [{"coefficients": [0, 1], "sense": "==", "rhs": 1}],
            "weights": [1 / 3] * 3,
        })
        # Agregar igualdades redundantes no debe impedir que SLSQP halle el punto interior.
        equality = model.constraints[0]
        model.constraints += [equality, equality]
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.ideal_point, [1, 0, 1])
        self.assertEqual(payoff.anti_ideal_point, [0, 1, 1])
        self.assertEqual(payoff.degenerate_objectives, [2])
        solutions, _ = solve_all_metrics(model, payoff, model.weights)
        self.assertAlmostEqual(solutions["L2"].variables["x"], 0.5)
        self.assertEqual(solutions["L2"].status, "optimal")
        self.assertAlmostEqual(solutions["L_inf"].variables["x"], 0.5)
        np.testing.assert_allclose(solutions["L_inf"].achievement_pct, [50, 50, 100])
        self.assertAlmostEqual(solutions["L_inf"].aggregate_distance, 1 / 6)

    def test_decision_plot_bounds_follow_constraints_without_explicit_limits(self):
        model = ModelDefinition.model_validate({
            "variables": [
                {"name": "x", "lower_bound": None}, {"name": "y", "lower_bound": None},
            ],
            "objectives": [
                {"name": "Actividad", "coefficients": [1, 0]},
                {"name": "Costo", "sense": "minimize", "coefficients": [1, 0]},
            ],
            "constraints": [
                {"coefficients": [1, 0], "sense": ">=", "rhs": -3000},
                {"coefficients": [1, 0], "sense": "<=", "rhs": -2000},
                {"coefficients": [0, 1], "sense": "==", "rhs": -5000},
            ],
        })
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.status, "optimal")
        self.assertEqual(payoff.decision_ranges_2d, [(-3000, -2000), (-5000, -5000)])

    def test_api_rejects_wrong_weights_without_silently_correcting(self):
        payload = json.loads((EXAMPLES / "01_celdas_fotovoltaicas.json").read_text())
        with TestClient(app) as client:
            for weights in ([0.4, 0.4], [-0.2, 1.2], [1]):
                response = client.post("/api/solve", json={**payload, "weights": weights})
                self.assertEqual(response.status_code, 400)
                self.assertIn("pesos deben sumar 1", response.json()["detail"])

    def test_stalled_qp_is_reported_as_feasible_not_optimal(self):
        model = example("02_problema_transporte.json")
        model.weights = [0.25, 0.75]
        # Simula una parada de SLSQP sin progreso, conservando el punto factible.
        def stalled(_fun, x0, **_options):
            return SimpleNamespace(x=x0, success=False)

        celdas = example("01_celdas_fotovoltaicas.json")
        with patch("core.compromise.minimize", side_effect=stalled):
            recovered, _ = solve_all_metrics(celdas, compute_payoff_matrix(celdas))
            response = TestClient(app).post("/api/solve", json=model.model_dump())
        self.assertEqual(recovered["L2"].status, "optimal")
        self.assertAlmostEqual(recovered["L2"].objectives[0], 595081.967213, places=5)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["solutions"]["L2"]["status"], "feasible_suboptimal")
        self.assertEqual(result["solutions"]["L1"]["status"], "optimal")

    def test_paper_extreme_weights_respect_1e8_primal_feasibility(self):
        from core.payoff import build_linear_constraints, is_feasible

        model = example("06_produccion_papel.json")
        payoff = compute_payoff_matrix(model)
        A_ub, b_ub, A_eq, b_eq, bounds, integrality = build_linear_constraints(model)
        var_names = [v.name for v in model.variables]
        for weights in ([0.95, 0.05], [1.0, 0.0], [0.0, 1.0]):
            solutions, _ = solve_all_metrics(model, payoff, weights)
            for metric_name, sol in solutions.items():
                self.assertEqual(sol.status, "optimal", f"{metric_name} con {weights}")
                x = np.array([sol.variables[vn] for vn in var_names], dtype=float)
                self.assertTrue(
                    is_feasible(x, A_ub, b_ub, A_eq, b_eq, bounds, integrality, tol=1e-8),
                    f"{metric_name} con {weights} violó factibilidad primal <= 1e-8",
                )
                self.assertGreaterEqual(float(np.min(x)), 0.0)

    def test_miqp_polish_matches_exact_continuous_slice(self):
        model = ModelDefinition.model_validate({
            "variables": [
                {"name": "y", "var_type": "binary", "lower_bound": 0.0, "upper_bound": 1.0},
                {"name": "n", "var_type": "integer", "lower_bound": 0.0, "upper_bound": 8.0},
                {"name": "c1", "lower_bound": 0.0, "upper_bound": 20.0},
                {"name": "c2", "lower_bound": 0.0, "upper_bound": 20.0},
            ],
            "objectives": [
                {"name": "Profit", "sense": "maximize", "coefficients": [25.0, 12.0, 5.5, 3.2]},
                {"name": "Risk", "sense": "minimize", "coefficients": [4.0, 1.5, 2.0, 0.7]},
            ],
            "constraints": [
                {"coefficients": [-6.0, 2.5, 1.2, 0.9], "sense": "<=", "rhs": 14.0},
                {"coefficients": [0.0, -1.5, 1.0, 1.0], "sense": ">=", "rhs": 2.3},
                {"coefficients": [5.0, 1.0, 0.5, -1.0], "sense": "<=", "rhs": 8.5},
                {"coefficients": [0.0, 0.0, 1.0, 1.0], "sense": "<=", "rhs": 15.0},
            ],
            "weights": [0.5, 0.5],
        })
        payoff = compute_payoff_matrix(model)
        solutions, _ = solve_all_metrics(model, payoff, model.weights)
        l2 = solutions["L2"]
        self.assertEqual(l2.status, "optimal")
        self.assertEqual(l2.variables["y"], 1.0)
        self.assertEqual(l2.variables["n"], 3.0)
        self.assertAlmostEqual(l2.variables["c1"], 0.0, places=8)
        self.assertAlmostEqual(l2.variables["c2"], 6.8, places=8)

    def test_extreme_overflow_coefficients_return_400_never_500_or_null(self):
        payload = {
            "name": "Overflow test",
            "variables": [{"name": "x1", "lower_bound": 0, "upper_bound": 10}],
            "objectives": [
                {"name": "Z1", "sense": "maximize", "coefficients": [1e308]},
                {"name": "Z2", "sense": "maximize", "coefficients": [1.0]},
            ],
            "constraints": [],
            "weights": [0.5, 0.5],
        }
        with TestClient(app) as client:
            for endpoint in ("/api/payoff", "/api/solve", "/api/pareto"):
                res = client.post(endpoint, json=payload)
                self.assertEqual(res.status_code, 400, f"{endpoint}: {res.text}")
                self.assertIn("detail", res.json())

    def test_mip_perturbed_integer_bound_avoids_slsqp_crash(self):
        payload = {
            "name": "bnb_bound_crash",
            "variables": [
                {"name": "x1", "var_type": "integer", "lower_bound": 1.00000000001, "upper_bound": 5.0},
                {"name": "x2", "var_type": "integer", "lower_bound": 0.0, "upper_bound": 5.0},
                {"name": "x3", "var_type": "integer", "lower_bound": 0.0, "upper_bound": 5.0},
                {"name": "x4", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 10.0},
            ],
            "objectives": [
                {"name": "Z1", "sense": "maximize", "coefficients": [10.0, 7.0, 5.0, 3.0]},
                {"name": "Z2", "sense": "minimize", "coefficients": [8.0, 3.0, 9.0, 2.0]},
                {"name": "Z3", "sense": "minimize", "coefficients": [2.0, 9.0, 3.0, 6.0]},
            ],
            "constraints": [
                {"coefficients": [1.0, 1.0, 1.0, 1.0], "sense": "<=", "rhs": 8.5},
                {"coefficients": [2.0, 1.0, 3.0, 0.5], "sense": ">=", "rhs": 4.7},
            ],
            "weights": [0.4, 0.3, 0.3],
        }
        res = TestClient(app).post("/api/solve", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "optimal")
        for sol in body["solutions"].values():
            self.assertEqual(sol["status"], "optimal")
            self.assertGreaterEqual(sol["variables"]["x1"], 2.0)

    def test_l2_zero_weight_tie_break_avoids_dominated_solution(self):
        payload = {
            "name": "w0_dominated_l2",
            "variables": [
                {"name": "x1", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 10.0},
                {"name": "x2", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 4.0},
                {"name": "x3", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 4.0},
            ],
            "objectives": [
                {"name": "Z0", "sense": "maximize", "coefficients": [1.0, 0.0, 0.0]},
                {"name": "Z1", "sense": "minimize", "coefficients": [0.0, 1.0, 0.0]},
                {"name": "Z2", "sense": "minimize", "coefficients": [0.0, 0.0, 1.0]},
            ],
            "constraints": [
                {"coefficients": [1.0, 2.0, 0.0], "sense": "<=", "rhs": 10.0},
                {"coefficients": [1.0, 0.0, 2.0], "sense": "<=", "rhs": 10.0},
                {"coefficients": [0.0, 1.0, 1.0], "sense": ">=", "rhs": 4.0},
            ],
            "weights": [0.0, 0.6, 0.4],
        }
        res = TestClient(app).post("/api/solve", json=payload)
        self.assertEqual(res.status_code, 200)
        l2 = res.json()["solutions"]["L2"]
        self.assertEqual(l2["status"], "optimal")
        self.assertAlmostEqual(l2["variables"]["x1"], 58.0 / 13.0, places=5)

    def test_integer_fractional_bound_consistent_feasibility_across_metrics(self):
        payload = {
            "name": "tol_mismatch_5e8",
            "variables": [
                {"name": "x1", "var_type": "integer", "lower_bound": 1.00000005, "upper_bound": 3.0},
                {"name": "x2", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": 3.0},
            ],
            "objectives": [
                {"name": "Z1", "sense": "maximize", "coefficients": [1.0, 1.0]},
                {"name": "Z2", "sense": "minimize", "coefficients": [1.0, 0.0]},
            ],
            "constraints": [{"coefficients": [1.0, 1.0], "sense": "<=", "rhs": 3.5}],
            "weights": [0.5, 0.5],
        }
        res = TestClient(app).post("/api/solve", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "optimal")
        for metric, sol in body["solutions"].items():
            self.assertEqual(sol["status"], "optimal", metric)
            self.assertGreaterEqual(sol["variables"]["x1"], 2.0)

    def test_unbounded_null_ray_l2_certifies_optimal(self):
        payload = {
            "name": "unbounded_null_ray",
            "variables": [
                {"name": "x1", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": None},
                {"name": "x2", "var_type": "continuous", "lower_bound": 0.0, "upper_bound": None},
            ],
            "objectives": [
                {"name": "Z1", "sense": "maximize", "coefficients": [1.0, -2.0]},
                {"name": "Z2", "sense": "minimize", "coefficients": [0.3, -0.6]},
            ],
            "constraints": [
                {"coefficients": [1.0, -2.0], "sense": "<=", "rhs": 10.0},
                {"coefficients": [1.0, -2.0], "sense": ">=", "rhs": 0.0},
            ],
            "weights": [0.7, 0.3],
        }
        res = TestClient(app).post("/api/solve", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "optimal")
        self.assertEqual(body["solutions"]["L2"]["status"], "optimal")
        self.assertAlmostEqual(body["solutions"]["L2"]["objectives"][0], 490.0 / 58.0, places=5)

    def test_lexicographic_payoff_sequential_fallback_on_cancelling_objectives(self):
        model = ModelDefinition.model_validate({
            "name": "lex_cancel_m3",
            "variables": [
                {"name": "x1", "lower_bound": 0.0, "upper_bound": 10.0},
                {"name": "x2", "lower_bound": 0.0, "upper_bound": 10.0},
                {"name": "x3", "lower_bound": 0.0, "upper_bound": 10.0},
            ],
            "objectives": [
                {"name": "Z0", "sense": "maximize", "coefficients": [1.0, 0.0, 0.0]},
                {"name": "Z1", "sense": "maximize", "coefficients": [0.0, 1.0, 0.0]},
                {"name": "Z2", "sense": "minimize", "coefficients": [0.0, 1.0, -1e-13]},
            ],
        })
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.status, "optimal")
        self.assertEqual(payoff.independent_solutions[0]["x3"], 10.0)


if __name__ == "__main__":
    unittest.main()

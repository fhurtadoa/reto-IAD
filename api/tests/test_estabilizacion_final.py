"""Regresiones contra cotas, datos degenerados y certificados engañosos."""

from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from random import Random
from threading import Barrier
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.compromise import solve_all_metrics
from core.payoff import compute_payoff_matrix
from core.schemas import ModelDefinition
from index import _solve_structure, app


def opposite_objectives(**bounds):
    return ModelDefinition.model_validate({
        "variables": [{"name": "x", **bounds}],
        "objectives": [
            {"name": "Beneficio", "sense": "maximize", "coefficients": [1]},
            {"name": "Costo", "sense": "minimize", "coefficients": [1]},
        ],
    })


class TestEstabilizacionFinal(TestCase):
    def test_small_continuous_interval_preserves_ends_and_distances(self):
        model = opposite_objectives(upper_bound=1e-10)
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.matrix, [[1e-10, 1e-10], [0, 0]])
        solutions, _ = solve_all_metrics(model, payoff, [0.8, 0.2])
        for name, fraction, distance in [
            ("L1", 1, 0.2),
            ("L2", 16 / 17, 0.8 / (17**0.5)),
            ("L_inf", 0.8, 0.16),
        ]:
            sol = solutions[name]
            self.assertEqual(sol.status, "optimal")
            self.assertAlmostEqual(sol.variables["x"] / 1e-10, fraction, places=8)
            self.assertAlmostEqual(sol.aggregate_distance, distance, places=8)

    def test_constant_contradictions_are_exact(self):
        client = TestClient(app)
        model = opposite_objectives(upper_bound=1).model_dump()
        for sense, rhs in [("==", 1e-20), ("<=", -1e-20), (">=", 1e-20)]:
            model["constraints"] = [{"coefficients": [0], "sense": sense, "rhs": rhs}]
            with self.subTest(sense=sense):
                response = client.post("/api/solve", json=model)
                self.assertEqual(response.status_code, 400)
                self.assertIn("infactible", response.json()["detail"])

    def test_integer_bounds_do_not_expand_across_a_lattice_point(self):
        client = TestClient(app)
        for kind, lower, upper in [
            ("integer", 1.0000000000005, 1.5),
            ("integer", 0.5, 0.9999999999995),
            ("binary", 0.0000000000005, 0.9999999999995),
        ]:
            with self.subTest(kind=kind, lower=lower, upper=upper):
                model = opposite_objectives(var_type=kind, lower_bound=lower, upper_bound=upper)
                response = client.post("/api/solve", json=model.model_dump())
                self.assertEqual(response.status_code, 400)
                self.assertIn("infactible", response.json()["detail"])

    def test_large_integer_retains_resolution_in_both_compromise_programs(self):
        span = 10**10
        model = opposite_objectives(var_type="integer", upper_bound=span)
        payoff = compute_payoff_matrix(model)
        weights = [0.8, 0.2]
        solutions, _ = solve_all_metrics(model, payoff, weights)
        for metric, expected in [("L2", round(Fraction(16 * span, 17))), ("L_inf", 4 * span // 5)]:
            with self.subTest(metric=metric):
                self.assertEqual(solutions[metric].status, "optimal")
                self.assertEqual(solutions[metric].variables["x"], expected)

        with patch("core.compromise.minimize", side_effect=AssertionError("plazo agotado")):
            cutoff, _ = solve_all_metrics(model, payoff, weights, l2_max_seconds=0)
        self.assertEqual(cutoff["L2"].status, "feasible_suboptimal")
        incumbent = cutoff["L2"].variables["x"]
        self.assertEqual(incumbent, round(incumbent))
        self.assertTrue(0 <= incumbent <= span)
        self.assertGreater(cutoff["L2"].aggregate_distance, solutions["L2"].aggregate_distance)

    def test_concurrent_structure_computes_once_and_failed_attempt_can_retry(self):
        model = opposite_objectives(upper_bound=13.581)
        payoff = compute_payoff_matrix(model)
        with patch("index._require_payoff", side_effect=ValueError("error transitorio")):
            with self.assertRaisesRegex(ValueError, "error transitorio"):
                _solve_structure(model)

        both_started = Barrier(2)

        def solve():
            both_started.wait(timeout=5)
            return _solve_structure(model)

        with (
            patch("index._require_payoff", return_value=payoff) as compute,
            patch("index.compute_pareto_frontier", return_value=[]),
            patch("index.compute_weight_sensitivity", return_value=None),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            requests = [pool.submit(solve) for _ in range(2)]
            results = [request.result(timeout=10) for request in requests]
        compute.assert_called_once()
        self.assertIs(results[0], results[1])
        self.assertIs(results[0][0], payoff)

    def test_exact_enumeration_against_seeded_integer_models(self):
        rng = Random(418)
        for case in range(24):
            limit = rng.randint(4, 9)
            domain = [(x, y, b) for x in range(6) for y in range(5) for b in range(2)
                      if x + 2 * y + b <= limit and x >= b]
            coeffs = [tuple(rng.randint(-5, 5) for _ in range(3)) for _ in range(3)]
            senses = [1, -1, 1]
            raw_weights = [rng.randint(0, 5), rng.randint(0, 5), rng.randint(1, 5)]
            weights = [Fraction(w, sum(raw_weights)) for w in raw_weights]
            model = ModelDefinition.model_validate({
                "variables": [
                    {"name": "x", "var_type": "integer", "upper_bound": 5},
                    {"name": "y", "var_type": "integer", "upper_bound": 4},
                    {"name": "b", "var_type": "binary"},
                ],
                "objectives": [
                    {"name": str(i), "sense": "maximize" if sign == 1 else "minimize",
                     "coefficients": coeffs[i]}
                    for i, sign in enumerate(senses)
                ],
                "constraints": [
                    {"coefficients": [1, 2, 1], "sense": "<=", "rhs": limit},
                    {"coefficients": [1, 0, -1], "sense": ">=", "rhs": 0},
                ],
            })

            def objectives(point):
                return [sum(c * v for c, v in zip(row, point)) for row in coeffs]

            values = list(map(objectives, domain))
            payoff = compute_payoff_matrix(model)
            with self.subTest(case=case):
                self.assertEqual(payoff.status, "optimal")
                for i, sign in enumerate(senses):
                    optimum = sign * max(sign * row[i] for row in values)
                    self.assertEqual(payoff.matrix[i][i], optimum)
                    self.assertEqual(payoff.ideal_point[i], optimum)

                def score(point, metric):
                    d = [
                        w * Fraction(sign * (round(ideal) - actual), round(span))
                        for w, sign, ideal, actual, span in zip(
                            weights, senses, payoff.ideal_point, objectives(point), payoff.normalization_ranges
                        )
                    ]
                    return {"L1": lambda: sum(d), "L2": lambda: sum(v * v for v in d), "L_inf": lambda: max(d)}[metric]()

                results, _ = solve_all_metrics(model, payoff, list(map(float, weights)))
                for name, result in results.items():
                    decisions = tuple(result.variables[k] for k in ("x", "y", "b"))
                    self.assertIn(decisions, domain)
                    self.assertEqual(result.objectives, objectives(decisions))
                    self.assertEqual(result.status, "optimal")
                    self.assertEqual(score(tuple(map(int, decisions)), name), min(score(x, name) for x in domain))

import unittest

import numpy as np

from core.compromise import solve_all_metrics
from core.payoff import compute_payoff_matrix
from core.schemas import ModelDefinition


class TestRedTeamScaling(unittest.TestCase):
    def test_tiny_objective_preserves_payoff_and_normalized_solutions(self):
        self.check_opposed_tradeoff(10.0, 1e-12)

    def test_large_implicit_bound_preserves_optimality(self):
        self.check_opposed_tradeoff(1e10, 1.0)

    def check_opposed_tradeoff(self, upper, benefit_scale):
        model = ModelDefinition.model_validate({
            "variables": [{"name": "x"}],
            "objectives": [
                {"name": "Beneficio", "coefficients": [benefit_scale]},
                {"name": "Costo", "sense": "minimize", "coefficients": [1]},
            ],
            "constraints": [{"coefficients": [1], "sense": "<=", "rhs": upper}],
            "weights": [0.8, 0.2],
        })
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.degenerate_objectives, [])
        np.testing.assert_allclose(payoff.matrix, [[upper * benefit_scale, upper], [0, 0]], rtol=1e-10, atol=0)
        solutions, _ = solve_all_metrics(model, payoff, model.weights)
        # In u=x/upper, d=(1-u,u). L₂ is stationary at 16/17 and L∞ equalizes its two terms.
        expected = {"L1": (1, 0.2), "L2": (16 / 17, 0.8 / np.sqrt(17)), "L_inf": (0.8, 0.16)}
        for metric, (point, distance) in expected.items():
            solution = solutions[metric]
            self.assertEqual(solution.status, "optimal")
            self.assertAlmostEqual(solution.variables["x"] / upper, point, delta=2e-7)
            self.assertAlmostEqual(solution.aggregate_distance, distance, delta=2e-7)

"""Regression from the published EPSCM energy planning exercise."""
import json
from pathlib import Path
import unittest

import numpy as np

from core.compromise import solve_all_metrics
from core.payoff import compute_payoff_matrix
from core.schemas import ModelDefinition


class PublishedEnergyTest(unittest.TestCase):
    def test_coincident_payoff_uses_feasible_ranges(self):
        evidence = Path(__file__).resolve().parent / "fixtures"
        payload = json.loads((evidence / "energia_s13_antes.json").read_text())["payload"]
        model = ModelDefinition.model_validate(payload)
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.normalization_sources, ["constant"] * 3)
        solutions, _ = solve_all_metrics(model, payoff)
        for solution in solutions.values():
            self.assertEqual(solution.status, "optimal")
            np.testing.assert_allclose(solution.objectives, [3315000, 53820, 39000], rtol=0, atol=1e-6)
            self.assertAlmostEqual(solution.aggregate_distance, 0.0, places=9)

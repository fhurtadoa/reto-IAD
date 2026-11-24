import unittest
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException

from core.compromise import solve_all_metrics
from core.payoff import compute_payoff_matrix
from core.sensitivity import compute_weight_sensitivity
from index import solve_model
from test_audit_regressions import example


class TestSensitivity(unittest.TestCase):
    def test_official_models_preserve_weights_and_match_exact_solutions(self):
        for filename in ("01_celdas_fotovoltaicas.json", "02_problema_transporte.json", "06_produccion_papel.json"):
            model = example(filename)
            payoff = compute_payoff_matrix(model)
            sweep = compute_weight_sensitivity(model, payoff)
            for field, metric in (("l1", "L1"), ("l2", "L2"), ("l_inf", "L_inf")):
                points = getattr(sweep, field)
                np.testing.assert_allclose([p.w1 for p in points], np.linspace(0, 1, 21))
                self.assertTrue(all(p.status == "optimal" for p in points), f"{filename} {metric} tiene muestras no óptimas")
                for i in (0, 1, 2, 11, 18, 19, 20):
                    point = points[i]
                    self.assertEqual(point.weights, [point.w1, 1 - point.w1])
                    exact, _ = solve_all_metrics(model, payoff, point.weights)
                    self.assertEqual(exact[metric].status, "optimal")
                    np.testing.assert_allclose(point.objectives, exact[metric].objectives)
                    np.testing.assert_allclose(point.deviations_pct, 100 * np.array(exact[metric].normalized_distances))
                self.assertAlmostEqual(points[0].deviations_pct[1], 0, places=5)
                self.assertAlmostEqual(points[-1].deviations_pct[0], 0, places=5)
            self.assertLess(len({tuple(p.objectives) for p in sweep.l1}), 21)

    def test_cache_ignores_weights_and_invalidates_on_structural_change(self):
        model = example("01_celdas_fotovoltaicas.json")
        model.objectives[0].name = "Utilidad para prueba de caché"
        with patch("index.compute_weight_sensitivity", wraps=compute_weight_sensitivity) as compute:
            first = solve_model(model)
            updated = solve_model(model.model_copy(update={"weights": [0.7, 0.3]}))
            self.assertEqual(compute.call_count, 1)
            self.assertEqual(first.weight_sensitivity, updated.weight_sensitivity)
            self.assertNotEqual(first.weights, updated.weights)
            changed = model.model_copy(deep=True)
            changed.variables[1].upper_bound = 180
            self.assertNotEqual(solve_model(changed).weight_sensitivity, first.weight_sensitivity)
            self.assertEqual(compute.call_count, 2)

    def test_unsupported_and_invalid_models(self):
        model = example("04_triobjetivo_3d.json")
        self.assertIsNone(compute_weight_sensitivity(model, compute_payoff_matrix(model)))
        model = example("01_celdas_fotovoltaicas.json")
        with self.assertRaises(ValueError):
            compute_weight_sensitivity(model, compute_payoff_matrix(model), num_samples=1)
        model.constraints[0].rhs = -1
        with self.assertRaises(HTTPException):
            solve_model(model)

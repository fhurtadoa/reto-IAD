"""Regresiones con modelos transcritos de las fuentes originales de IAD."""
import importlib.util
import unittest
from pathlib import Path

import numpy as np

from core.compromise import solve_all_metrics
from core.payoff import compute_payoff_matrix
from core.schemas import ModelDefinition


CASES_PATH = Path(__file__).resolve().parent / "fixtures" / "casos_iad.py"
spec = importlib.util.spec_from_file_location("casos_iad", CASES_PATH)
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)


class TestValidacionOriginalIAD(unittest.TestCase):
    def test_clase11_p8_keeps_alternative_l1_optima(self):
        model = ModelDefinition.model_validate(cases.all_cases()["clase11"][0])
        payoff = compute_payoff_matrix(model)
        solutions, _ = solve_all_metrics(model, payoff)
        np.testing.assert_allclose(payoff.matrix, [[80, 30], [70, 35]], atol=1e-10)
        self.assertAlmostEqual(solutions["L1"].aggregate_distance, 0.5, places=8)
        np.testing.assert_allclose(solutions["L2"].objectives, [75, 32.5], atol=1e-6)
        self.assertAlmostEqual(solutions["L_inf"].aggregate_distance, 0.25, places=8)

    def test_clase14_matches_weighted_factors_table(self):
        definition, profiles, _ = cases.all_cases()["celdas"]
        model = ModelDefinition.model_validate(definition)
        payoff = compute_payoff_matrix(model)
        expected = [(600000, 400)] + [(300000, 200)] * 3 + [(800000, 600)] * 3
        for weights, objectives in zip(profiles, expected):
            with self.subTest(weights=weights):
                solutions, _ = solve_all_metrics(model, payoff, weights)
                np.testing.assert_allclose(solutions["L1"].objectives, objectives, rtol=0, atol=1e-6)

    def test_taller2_integer_payoff_all_document_digits(self):
        for n in range(10):
            with self.subTest(n=n):
                model = ModelDefinition.model_validate(cases.transportation(n, integer=True))
                payoff = compute_payoff_matrix(model)
                self.assertEqual(payoff.matrix, [[16800 + 3 * n, 5700], [18500 + 3 * n, 2600]])
                self.assertTrue(all(value.is_integer() for row in payoff.independent_solutions
                                    for value in row.values()))

    def test_notebook_transporte_l2_asymmetric_profiles(self):
        model = ModelDefinition.model_validate(cases.transportation())
        payoff = compute_payoff_matrix(model)
        # En la cara eficiente activa, riesgo-2600 = delta - pendiente * (costo-16800).
        for weights, delta, slope in [((.25, .75), 1600, 1), ((.75, .25), 3100, 3.5)]:
            with self.subTest(weights=weights):
                a, b = (weights[0] / 1700) ** 2, (weights[1] / 3100) ** 2
                cost_gap = b * slope * delta / (a + b * slope**2)
                risk_gap = delta - slope * cost_gap
                expected_distance = np.hypot(weights[0] * cost_gap / 1700,
                                             weights[1] * risk_gap / 3100)
                solutions, _ = solve_all_metrics(model, payoff, weights)
                l2 = solutions["L2"]
                self.assertEqual(l2.status, "optimal")
                np.testing.assert_allclose(l2.objectives, [16800 + cost_gap, 2600 + risk_gap],
                                           rtol=0, atol=3e-4)
                self.assertAlmostEqual(l2.aggregate_distance, expected_distance, places=8)

    def test_two_echelon_chain_integer_compromise_is_certified(self):
        model = ModelDefinition.model_validate(cases.chain(integer=True))
        payoff = compute_payoff_matrix(model)
        solutions, _ = solve_all_metrics(model, payoff)
        l2 = solutions["L2"]
        self.assertEqual(payoff.matrix, [[113000, 4579], [118120, 4019]])
        self.assertEqual(l2.status, "optimal")
        # Cota por intervalos de costo en el oráculo independiente de IAD.
        self.assertEqual(l2.objectives, [115320, 4299])
        self.assertAlmostEqual(l2.aggregate_distance, np.hypot(0.5 * 2320 / 5120, 0.25), places=9)

    def test_workbook_metric_binary_adaptation(self):
        definition, profiles, _ = cases.metric_workbook()
        model = ModelDefinition.model_validate(definition)
        payoff = compute_payoff_matrix(model)
        solutions, _ = solve_all_metrics(model, payoff, profiles[0])
        np.testing.assert_allclose(payoff.normalization_ranges, [100, 100, 100])
        self.assertAlmostEqual(solutions["L1"].aggregate_distance, 1 / 3, places=9)
        for metric in ("L2", "L_inf"):
            self.assertEqual(solutions[metric].variables["a4"], 1)
        self.assertAlmostEqual(solutions["L2"].aggregate_distance, np.sqrt(3) / 9, places=9)
        self.assertAlmostEqual(solutions["L_inf"].aggregate_distance, 1 / 9, places=9)

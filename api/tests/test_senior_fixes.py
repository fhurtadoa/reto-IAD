"""
Pruebas de validación de correcciones senior:
- Integralidad exacta en L2 y Pareto para modelos MIP (enteros/binarios).
- Estabilidad numérica en el caso Flota de Vehículos Eléctricos (6 variables, 4 objetivos, escala $2.35M).
- Validación de nombres duplicados y cotas inválidas.
"""
import os
import json
import unittest
import numpy as np
from fastapi import HTTPException

from core.schemas import ModelDefinition, VariableModel, ObjectiveModel, ConstraintModel
from core.payoff import compute_payoff_matrix
from core.compromise import solve_all_metrics
from core.pareto import compute_pareto_frontier
from index import _validate_model

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "examples")


class TestSeniorFixes(unittest.TestCase):
    def test_mip_l2_respects_integrality_and_constraints(self):
        with open(os.path.join(EXAMPLES_DIR, "03_mip_produccion.json"), "r", encoding="utf-8") as f:
            model = ModelDefinition(**json.load(f))

        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.status, "optimal")
        solutions, _ = solve_all_metrics(model, payoff, weights=model.weights)

        for metric_key in ("L1", "L2", "L_inf"):
            sol = solutions[metric_key]
            self.assertEqual(sol.status, "optimal", f"{metric_key} no convergió")
            x1 = sol.variables["x1"]
            x2 = sol.variables["x2"]
            y1 = sol.variables["y1"]

            # x2 debe ser entera y y1 debe ser binaria exacta {0, 1}
            self.assertAlmostEqual(x2, round(x2), places=5, msg=f"{metric_key}: x2={x2} no es entera")
            self.assertIn(round(y1), (0, 1), msg=f"{metric_key}: y1={y1} fuera de {{0, 1}}")
            self.assertAlmostEqual(y1, round(y1), places=5, msg=f"{metric_key}: y1={y1} es fraccionaria")

            # Verificar todas las restricciones del modelo
            self.assertLessEqual(x1 + 2.0 * x2 - 30.0 * y1, 1e-4, msg=f"{metric_key} viola Capacidad Planta")
            self.assertLessEqual(10.0 * x1 + 25.0 * x2 + 80.0 * y1, 500.0 + 1e-4, msg=f"{metric_key} viola Presupuesto")
            self.assertGreaterEqual(x1 + x2, 15.0 - 1e-4, msg=f"{metric_key} viola Demanda Mínima")

    def test_mip_pareto_frontier_is_all_integer_feasible(self):
        with open(os.path.join(EXAMPLES_DIR, "03_mip_produccion.json"), "r", encoding="utf-8") as f:
            model = ModelDefinition(**json.load(f))

        payoff = compute_payoff_matrix(model)
        pts = compute_pareto_frontier(model, payoff, num_samples=15)
        self.assertGreater(len(pts), 0)
        for pt in pts:
            x2 = pt.variables["x2"]
            y1 = pt.variables["y1"]
            self.assertAlmostEqual(x2, round(x2), places=5, msg=f"Punto Pareto MIP con x2 fraccionaria: {x2}")
            self.assertAlmostEqual(y1, round(y1), places=5, msg=f"Punto Pareto MIP con y1 fraccionaria: {y1}")

    def test_flota_6_autos_4_objetivos(self):
        with open(os.path.join(EXAMPLES_DIR, "05_flota_vehiculos.json"), "r", encoding="utf-8") as f:
            model = ModelDefinition(**json.load(f))

        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.status, "optimal")
        self.assertEqual(len(payoff.matrix), 4)

        solutions, norm_w = solve_all_metrics(model, payoff, weights=model.weights)
        self.assertAlmostEqual(sum(norm_w), 1.0, places=5)
        for k in ("L1", "L2", "L_inf"):
            sol = solutions[k]
            self.assertEqual(sol.status, "optimal")
            total_cars = sum(sol.variables.values())
            self.assertAlmostEqual(total_cars, 50.0, places=2, msg=f"{k}: suma de flota={total_cars} != 50")

        # Invariante matemático: la distancia L2 de la solución L2 debe ser <= L2 evaluada en L1 y L_inf
        w = np.array(norm_w)
        l2_at_l1 = float(np.linalg.norm(w * np.array(solutions["L1"].normalized_distances)))
        l2_at_linf = float(np.linalg.norm(w * np.array(solutions["L_inf"].normalized_distances)))
        self.assertLessEqual(solutions["L2"].aggregate_distance, l2_at_l1 + 1e-4)
        self.assertLessEqual(solutions["L2"].aggregate_distance, l2_at_linf + 1e-4)

    def test_validation_rejects_duplicate_names_and_bad_bounds(self):
        dup_model = ModelDefinition(
            name="Dup",
            variables=[
                VariableModel(name="x1", var_type="continuous", lower_bound=0, upper_bound=10),
                VariableModel(name="x1", var_type="continuous", lower_bound=0, upper_bound=10),
            ],
            objectives=[
                ObjectiveModel(name="Z1", sense="maximize", coefficients=[1, 2]),
                ObjectiveModel(name="Z2", sense="minimize", coefficients=[2, 1]),
            ],
            constraints=[],
        )
        with self.assertRaises(HTTPException):
            _validate_model(dup_model)

        bad_bounds = ModelDefinition(
            name="BadBounds",
            variables=[
                VariableModel(name="x1", var_type="continuous", lower_bound=50, upper_bound=10),
            ],
            objectives=[
                ObjectiveModel(name="Z1", sense="maximize", coefficients=[1]),
                ObjectiveModel(name="Z2", sense="minimize", coefficients=[2]),
            ],
            constraints=[],
        )
        with self.assertRaises(HTTPException):
            _validate_model(bad_bounds)


if __name__ == "__main__":
    unittest.main()

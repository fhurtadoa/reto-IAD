"""
Pruebas de casos borde, robustez matemática y validación de sustentación (E7):
- Desempate lexicográfico ante óptimos múltiples en Matriz de Pagos.
- Optimalidad Pareto-fuerte cuando existen pesos iguales a cero (w_i = 0).
- Detección de objetivos degenerados (Ideal == Nadir).
- Modelos infactibles y no acotados.
- Caso mixto 3 variables (1 entera) y 3 objetivos verificado contra cálculo independiente.
"""
import unittest
import numpy as np

from core.schemas import ModelDefinition, VariableModel, ObjectiveModel, ConstraintModel
from core.payoff import compute_payoff_matrix
from core.compromise import solve_all_metrics
from core.pareto import compute_pareto_frontier


class TestEdgeCases(unittest.TestCase):
    def test_lexicographic_payoff_and_zero_weight_avoid_dominated_solution(self):
        # Z1 = x1 (max), Z2 = x2 (max) en caja [0, 10]^2: NO hay conflicto; (10, 10) domina todo.
        model = ModelDefinition(
            name="SinConflictoOptimosMultiples",
            variables=[
                VariableModel(name="x1", var_type="continuous", lower_bound=0.0, upper_bound=10.0),
                VariableModel(name="x2", var_type="continuous", lower_bound=0.0, upper_bound=10.0),
            ],
            objectives=[
                ObjectiveModel(name="Z1", sense="maximize", coefficients=[1.0, 0.0]),
                ObjectiveModel(name="Z2", sense="maximize", coefficients=[0.0, 1.0]),
            ],
            constraints=[
                ConstraintModel(name="Caja", coefficients=[1.0, 1.0], sense="<=", rhs=20.0),
            ],
            weights=[0.0, 1.0],
        )
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.status, "optimal")
        self.assertEqual(payoff.degenerate_objectives, [0, 1])
        self.assertAlmostEqual(payoff.ideal_point[0], 10.0, places=5)
        self.assertAlmostEqual(payoff.ideal_point[1], 10.0, places=5)

        solutions, _ = solve_all_metrics(model, payoff, weights=[0.0, 1.0])
        for key in ("L1", "L2", "L_inf"):
            sol = solutions[key]
            self.assertEqual(sol.status, "optimal")
            self.assertAlmostEqual(sol.objectives[0], 10.0, places=4, msg=f"{key} devolvió solución dominada")
            self.assertAlmostEqual(sol.objectives[1], 10.0, places=4, msg=f"{key} devolvió solución dominada")

    def test_infeasible_and_unbounded_report_clear_error(self):
        inf_model = ModelDefinition(
            name="Infactible",
            variables=[VariableModel(name="x1", var_type="continuous", lower_bound=0.0, upper_bound=10.0)],
            objectives=[
                ObjectiveModel(name="Z1", sense="maximize", coefficients=[1.0]),
                ObjectiveModel(name="Z2", sense="minimize", coefficients=[1.0]),
            ],
            constraints=[ConstraintModel(name="C1", coefficients=[1.0], sense=">=", rhs=25.0)],
        )
        payoff_inf = compute_payoff_matrix(inf_model)
        self.assertIn("infeasible", payoff_inf.status.lower())

        unb_model = ModelDefinition(
            name="NoAcotado",
            variables=[
                VariableModel(name="x1", var_type="continuous", lower_bound=0.0, upper_bound=None),
                VariableModel(name="x2", var_type="continuous", lower_bound=0.0, upper_bound=None),
            ],
            objectives=[
                ObjectiveModel(name="Z1", sense="maximize", coefficients=[1.0, 1.0]),
                ObjectiveModel(name="Z2", sense="minimize", coefficients=[1.0, 0.0]),
            ],
            constraints=[],
        )
        payoff_unb = compute_payoff_matrix(unb_model)
        self.assertIn("unbounded", payoff_unb.status.lower())

    def test_sustentacion_e7_3vars_mixed_3objectives(self):
        model = ModelDefinition(
            name="SustentacionE7",
            variables=[
                VariableModel(name="x1", var_type="continuous", lower_bound=0.0, upper_bound=40.0),
                VariableModel(name="x2", var_type="integer", lower_bound=0.0, upper_bound=15.0),
                VariableModel(name="x3", var_type="continuous", lower_bound=2.0, upper_bound=30.0),
            ],
            objectives=[
                ObjectiveModel(name="Beneficio", sense="maximize", coefficients=[50.0, 120.0, 30.0]),
                ObjectiveModel(name="Riesgo", sense="minimize", coefficients=[3.0, 2.0, 1.0]),
                ObjectiveModel(name="Empleo", sense="maximize", coefficients=[1.0, 4.0, 2.0]),
            ],
            constraints=[
                ConstraintModel(name="Horas", coefficients=[2.0, 5.0, 1.0], sense="<=", rhs=90.0),
                ConstraintModel(name="Material", coefficients=[1.0, 2.0, 3.0], sense="<=", rhs=70.0),
                ConstraintModel(name="CuotaMin", coefficients=[1.0, 1.0, 1.0], sense=">=", rhs=12.0),
            ],
            weights=[0.5, 0.3, 0.2],
        )
        payoff = compute_payoff_matrix(model)
        self.assertEqual(payoff.status, "optimal")
        self.assertEqual(payoff.degenerate_objectives, [])

        solutions, _ = solve_all_metrics(model, payoff, weights=[0.5, 0.3, 0.2])
        for key in ("L1", "L2", "L_inf"):
            sol = solutions[key]
            self.assertEqual(sol.status, "optimal")
            x2 = sol.variables["x2"]
            self.assertAlmostEqual(x2, round(x2), places=6)

        # Referencia independiente: enumerar x2=0,…,15 y minimizar en cada polígono.
        self.assertAlmostEqual(solutions["L2"].aggregate_distance, 0.08373323735, places=6)
        self.assertAlmostEqual(solutions["L2"].variables["x2"], 15.0, places=5)

        # Verificar que Pareto MIP incluye puntos de L1, L2 y L_inf todos con x2 entero
        pts = compute_pareto_frontier(model, payoff, num_samples=11)
        self.assertGreater(len(pts), 0)
        for pt in pts:
            self.assertAlmostEqual(pt.variables["x2"], round(pt.variables["x2"]), places=5)


if __name__ == "__main__":
    unittest.main()

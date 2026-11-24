"""
Test de validación del Caso 3: Problema Triobjetivo 3D (Caso de Bonificación).
Verifica que el motor soporte >= 3 objetivos, genere la matriz de pagos 3x3 y las soluciones L1, L2, L_inf.
"""
import unittest
import numpy as np
from core.schemas import ModelDefinition, VariableModel, ObjectiveModel, ConstraintModel
from core.payoff import compute_payoff_matrix
from core.compromise import solve_all_metrics
from core.pareto import compute_pareto_frontier

def get_triobjetivo_model():
    return ModelDefinition(
        name="Optimización Triobjetivo Sostenible",
        variables=[
            VariableModel(name="x1", var_type="continuous", lower_bound=0.0),
            VariableModel(name="x2", var_type="continuous", lower_bound=0.0),
            VariableModel(name="x3", var_type="continuous", lower_bound=0.0)
        ],
        objectives=[
            ObjectiveModel(name="Retorno Económico", sense="maximize", coefficients=[3.0, 1.0, 2.0]),
            ObjectiveModel(name="Impacto Ambiental", sense="minimize", coefficients=[2.0, 1.0, 4.0]),
            ObjectiveModel(name="Impacto Social", sense="maximize", coefficients=[1.0, 3.0, 1.0])
        ],
        constraints=[
            ConstraintModel(name="Presupuesto Total", coefficients=[1.0, 1.0, 1.0], sense="<=", rhs=100.0),
            ConstraintModel(name="Límite Operativo A", coefficients=[2.0, 1.0, 0.0], sense="<=", rhs=120.0),
            ConstraintModel(name="Límite Operativo B", coefficients=[0.0, 1.0, 2.0], sense="<=", rhs=140.0)
        ],
        weights=[0.3333, 0.3333, 0.3334]
    )

class TestTriobjetivo(unittest.TestCase):
    def setUp(self):
        self.model = get_triobjetivo_model()
        self.payoff = compute_payoff_matrix(self.model)

    def test_triobjetivo_payoff(self):
        self.assertEqual(self.payoff.status, "optimal")
        self.assertEqual(len(self.payoff.headers), 3)
        self.assertEqual(len(self.payoff.matrix), 3)
        self.assertEqual(len(self.payoff.ideal_point), 3)
        self.assertEqual(len(self.payoff.anti_ideal_point), 3)
        
        # El ideal en maximización debe ser >= al peor
        self.assertGreaterEqual(self.payoff.ideal_point[0], self.payoff.anti_ideal_point[0])
        # El ideal en minimización debe ser <= al peor
        self.assertLessEqual(self.payoff.ideal_point[1], self.payoff.anti_ideal_point[1])
        self.assertGreaterEqual(self.payoff.ideal_point[2], self.payoff.anti_ideal_point[2])

    def test_triobjetivo_compromise(self):
        solutions, w = solve_all_metrics(self.model, self.payoff, weights=[1/3, 1/3, 1/3])
        self.assertIn("L1", solutions)
        self.assertIn("L2", solutions)
        self.assertIn("L_inf", solutions)
        
        for k, sol in solutions.items():
            self.assertEqual(sol.status, "optimal")
            self.assertEqual(len(sol.objectives), 3)
            self.assertEqual(len(sol.achievement_pct), 3)
            # Todos los grados de logro deben ser positivos y acotados
            for ach in sol.achievement_pct:
                self.assertGreaterEqual(ach, -1e-2)
                self.assertLessEqual(ach, 100.0 + 1e-2)

    def test_triobjetivo_pareto(self):
        pareto = compute_pareto_frontier(self.model, self.payoff, num_samples=15)
        self.assertGreater(len(pareto), 0)
        for pt in pareto:
            self.assertEqual(len(pt.objectives), 3)

if __name__ == "__main__":
    unittest.main()

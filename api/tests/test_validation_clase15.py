"""
Test de validación del Caso 1: Planificación de Producción de Celdas Fotovoltaicas (Clase 15).
Verifica que los cálculos reproduzcan exactamente los resultados teóricos de la Prof. Patricia Jaramillo.
Compatible con unittest y pytest.
"""
import unittest
import numpy as np
from core.schemas import ModelDefinition, VariableModel, ObjectiveModel, ConstraintModel
from core.payoff import compute_payoff_matrix
from core.compromise import solve_all_metrics

def get_celdas_model():
    return ModelDefinition(
        name="Planificación Celdas Fotovoltaicas (Clase 15)",
        variables=[
            VariableModel(name="x1", var_type="continuous", lower_bound=0.0, upper_bound=300.0),
            VariableModel(name="x2", var_type="continuous", lower_bound=0.0, upper_bound=200.0)
        ],
        objectives=[
            ObjectiveModel(name="Utilidad", sense="maximize", coefficients=[1000.0, 3000.0]),
            ObjectiveModel(name="Contaminantes", sense="maximize", coefficients=[-1.0, -2.0]) # Min x1 + 2x2 <=> Max -x1 - 2x2
        ],
        constraints=[
            ConstraintModel(name="Capacidad Ensamble", coefficients=[1.0, 1.0], sense="<=", rhs=400.0),
            ConstraintModel(name="Demanda Mínima", coefficients=[1000.0, 3000.0], sense=">=", rhs=300000.0)
        ],
        weights=[0.5, 0.5]
    )

class TestValidationClase15(unittest.TestCase):
    def setUp(self):
        self.model = get_celdas_model()
        self.payoff = compute_payoff_matrix(self.model)

    def test_payoff_matrix_clase15(self):
        self.assertEqual(self.payoff.status, "optimal")
        
        # Ideal: Z1 = 800.000, Z2 = -200 (200 kg)
        self.assertTrue(np.isclose(self.payoff.ideal_point[0], 800000.0, atol=1e-2))
        self.assertTrue(np.isclose(self.payoff.ideal_point[1], -200.0, atol=1e-2))
        
        # Anti-Ideal (peor): Z1 = 300.000, Z2 = -600 (600 kg)
        self.assertTrue(np.isclose(self.payoff.anti_ideal_point[0], 300000.0, atol=1e-2))
        self.assertTrue(np.isclose(self.payoff.anti_ideal_point[1], -600.0, atol=1e-2))

    def test_l1_solution_clase15(self):
        solutions, _ = solve_all_metrics(self.model, self.payoff, weights=[0.5, 0.5])
        sol_l1 = solutions["L1"]
        self.assertEqual(sol_l1.status, "optimal")
        self.assertTrue(np.isclose(sol_l1.variables["x1"], 0.0, atol=1e-2))
        self.assertTrue(np.isclose(sol_l1.variables["x2"], 200.0, atol=1e-2))
        self.assertTrue(np.isclose(sol_l1.objectives[0], 600000.0, atol=1e-2))
        self.assertTrue(np.isclose(sol_l1.objectives[1], -400.0, atol=1e-2))
        self.assertTrue(np.isclose(sol_l1.achievement_pct[0], 60.0, atol=1e-2))
        self.assertTrue(np.isclose(sol_l1.achievement_pct[1], 50.0, atol=1e-2))

    def test_linf_solution_clase15(self):
        solutions, _ = solve_all_metrics(self.model, self.payoff, weights=[0.5, 0.5])
        sol_inf = solutions["L_inf"]
        self.assertEqual(sol_inf.status, "optimal")
        self.assertTrue(np.isclose(sol_inf.variables["x1"], 0.0, atol=1e-1))
        self.assertTrue(np.isclose(sol_inf.variables["x2"], 190.91, atol=1e-1))
        self.assertTrue(np.isclose(sol_inf.objectives[0], 572727.27, atol=50.0))
        self.assertTrue(np.isclose(sol_inf.objectives[1], -381.82, atol=1.0))
        
        # Teorema de equilibrio para métrica infinito con pesos iguales:
        # Ambos objetivos deben alcanzar exactamente el mismo grado de logro porcentual (~54.55%)
        self.assertTrue(np.isclose(sol_inf.achievement_pct[0], 54.55, atol=0.1))
        self.assertTrue(np.isclose(sol_inf.achievement_pct[1], 54.55, atol=0.1))

if __name__ == "__main__":
    unittest.main()

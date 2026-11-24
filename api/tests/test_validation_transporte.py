"""
Test de validación del Caso 2: Problema de Transporte (Taller 3).
12 variables continuas, 2 objetivos (Minimizar Costo y Minimizar Riesgo).
Verifica que los resultados coincidan con los del cuaderno Problema_tte_MO_Compromiso.ipynb.
"""
import unittest
import numpy as np
from core.schemas import ModelDefinition, VariableModel, ObjectiveModel, ConstraintModel
from core.payoff import compute_payoff_matrix
from core.compromise import solve_all_metrics

def get_transporte_model():
    # 3 orígenes x 4 destinos = 12 variables
    var_names = [f"x_{i}_{j}" for i in range(1, 4) for j in range(1, 5)]
    variables = [VariableModel(name=name, var_type="continuous", lower_bound=0.0) for name in var_names]
    
    costos_unitarios = [
        [4, 3, 3, 4],
        [5, 2, 1, 5],
        [7, 10, 8, 9]
    ]
    riesgos_unitarios = [
        [6, 0, 1, 5],
        [2, 4, 0, 2],
        [3, 1, 2, 1]
    ]
    
    # Flatten de coeficientes
    c_costos = [float(costos_unitarios[i][j]) for i in range(3) for j in range(4)]
    c_riesgos = [float(riesgos_unitarios[i][j]) for i in range(3) for j in range(4)]
    
    # Sentido: minimización en ambos objetivos
    objectives = [
        ObjectiveModel(name="Costo Total", sense="minimize", coefficients=c_costos),
        ObjectiveModel(name="Riesgo Operativo", sense="minimize", coefficients=c_riesgos)
    ]
    
    constraints = []
    # Restricciones de oferta (O1, O2, O3)
    oferta = [800.0, 1200.0, 1500.0]
    for i in range(3):
        row = [0.0] * 12
        for j in range(4):
            row[i * 4 + j] = 1.0
        constraints.append(ConstraintModel(name=f"Oferta_O{i+1}", coefficients=row, sense="<=", rhs=oferta[i]))
        
    # Restricciones de demanda (D1, D2, D3, D4)
    demanda = [500.0, 700.0, 900.0, 1400.0]
    for j in range(4):
        row = [0.0] * 12
        for i in range(3):
            row[i * 4 + j] = 1.0
        constraints.append(ConstraintModel(name=f"Demanda_D{j+1}", coefficients=row, sense=">=", rhs=demanda[j]))
        
    return ModelDefinition(
        name="Problema de Transporte (Taller 3)",
        variables=variables,
        objectives=objectives,
        constraints=constraints,
        weights=[0.5, 0.5]
    )

class TestValidationTransporte(unittest.TestCase):
    def setUp(self):
        self.model = get_transporte_model()
        self.payoff = compute_payoff_matrix(self.model)

    def test_payoff_matrix_transporte(self):
        self.assertEqual(self.payoff.status, "optimal")
        
        # En minimización:
        # Costo ideal: 16.800, Costo peor (nadir): 18.500
        self.assertTrue(np.isclose(self.payoff.ideal_point[0], 16800.0, atol=1e-2))
        self.assertTrue(np.isclose(self.payoff.anti_ideal_point[0], 18500.0, atol=1e-2))
        
        # Riesgo ideal: 2.600, Riesgo peor (nadir): 5.700
        self.assertTrue(np.isclose(self.payoff.ideal_point[1], 2600.0, atol=1e-2))
        self.assertTrue(np.isclose(self.payoff.anti_ideal_point[1], 5700.0, atol=1e-2))

    def test_l1_solution_transporte(self):
        solutions, _ = solve_all_metrics(self.model, self.payoff, weights=[0.5, 0.5])
        sol_l1 = solutions["L1"]
        self.assertEqual(sol_l1.status, "optimal")
        
        # Según celda 20 del cuaderno: Z1 = 17400, Z2 = 3600
        self.assertTrue(np.isclose(sol_l1.objectives[0], 17400.0, atol=1e-1))
        self.assertTrue(np.isclose(sol_l1.objectives[1], 3600.0, atol=1e-1))
        self.assertTrue(np.isclose(sol_l1.achievement_pct[0], 64.71, atol=0.1))
        self.assertTrue(np.isclose(sol_l1.achievement_pct[1], 67.74, atol=0.1))

    def test_linf_solution_transporte(self):
        solutions, _ = solve_all_metrics(self.model, self.payoff, weights=[0.5, 0.5])
        sol_inf = solutions["L_inf"]
        self.assertEqual(sol_inf.status, "optimal")
        
        # Según celda 22 del cuaderno: Z1 = 17382.32, Z2 = 3661.88
        self.assertTrue(np.isclose(sol_inf.objectives[0], 17382.32, atol=1.0))
        self.assertTrue(np.isclose(sol_inf.objectives[1], 3661.88, atol=1.0))
        
        # Equilibrio perfecto de logro para pesos iguales: ~65.75%
        self.assertTrue(np.isclose(sol_inf.achievement_pct[0], 65.75, atol=0.2))
        self.assertTrue(np.isclose(sol_inf.achievement_pct[1], 65.75, atol=0.2))

if __name__ == "__main__":
    unittest.main()

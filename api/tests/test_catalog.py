import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from index import EXAMPLES_DIR, app


class TestAcademicCatalog(unittest.TestCase):
    def test_legacy_ids_and_paper_exercise(self):
        with TestClient(app) as client:
            response = client.get("/api/examples")
            catalog = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(catalog["errors"], [])
            self.assertTrue({"celdas", "transporte", "mip", "triobjetivo", "flota",
                             "06_produccion_papel"} <= {e["id"] for e in catalog["exercises"]})
            model = client.get("/api/examples/06_produccion_papel").json()
            self.assertIn("Taller", model["reference"])
            self.assertEqual(len(model["variables"]), 12)
            self.assertEqual([c["rhs"] for c in model["constraints"]], [5, 3, 3, 77, 81, 99, 105])
            self.assertEqual([o["sense"] for o in model["objectives"]], ["minimize", "maximize"])
            np.testing.assert_allclose(model["constraints"][0]["coefficients"][:4],
                                       1 / np.array([53, 51, 52, 42]))
            result = client.post("/api/solve", json=model)
            self.assertEqual(result.status_code, 200)
            for solution in result.json()["solutions"].values():
                x = np.array([solution["variables"][v["name"]] for v in model["variables"]])
                self.assertTrue(np.all(x >= -1e-7))
                np.testing.assert_array_less(
                    np.array([c["coefficients"] for c in model["constraints"][:3]]) @ x,
                    np.array([5, 3, 3]) + 1e-5,
                )
                np.testing.assert_array_less(np.array([77, 81, 99, 105]) - 1e-5,
                                            x.reshape(3, 4).sum(axis=0))
                np.testing.assert_allclose(solution["objectives"],
                                           np.array([o["coefficients"] for o in model["objectives"]]) @ x)

    def test_discovery_errors_are_isolated_and_ids_are_checked(self):
        with tempfile.TemporaryDirectory() as directory, TestClient(app) as client:
            folder = Path(directory)
            payload = (EXAMPLES_DIR / "06_produccion_papel.json").read_text()
            (folder / "nuevo-ejercicio.json").write_text(payload)
            broken = json.loads(payload)
            broken["variables"][0]["var_type"] = "incorrecto"
            (folder / "invalido.json").write_text(json.dumps(broken))
            with patch("index.EXAMPLES_DIR", folder):
                catalog = client.get("/api/examples").json()
                self.assertEqual([e["id"] for e in catalog["exercises"]], ["nuevo-ejercicio"])
                self.assertIn("variables.0.var_type", " ".join(catalog["errors"]))
                self.assertEqual(client.get("/api/examples/nuevo-ejercicio").status_code, 200)
                self.assertEqual(client.get("/api/examples/invalido").status_code, 422)
                self.assertEqual(client.get("/api/examples/no-existe").status_code, 404)
                self.assertEqual(client.get("/api/examples/plantilla.json").status_code, 404)

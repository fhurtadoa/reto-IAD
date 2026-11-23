"""
Script generador de plantillas y ejercicios Excel (.xlsx) para OptiCompromise.
Escribe:
  - web/public/plantilla-ejercicio-iad.xlsx
  - ejercicios/*.xlsx (a partir de examples/*.json)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from core.schemas import ModelDefinition  # noqa: E402
from excel_export import build_exercise_workbook, build_upload_template_workbook  # noqa: E402


def main() -> None:
    public_dir = ROOT / "web" / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    blank_path = public_dir / "plantilla-ejercicio-iad.xlsx"
    blank_path.write_bytes(build_upload_template_workbook("blank"))
    print(f"Generada plantilla: {blank_path}")

    examples_dir = ROOT / "examples"
    exercises_dir = ROOT / "ejercicios"
    exercises_dir.mkdir(parents=True, exist_ok=True)
    for old in exercises_dir.glob("*.xlsx"):
        old.unlink()

    for json_path in sorted(examples_dir.glob("*.json")):
        model = ModelDefinition.model_validate_json(json_path.read_text(encoding="utf-8-sig"))
        xlsx_path = exercises_dir / f"{json_path.stem}.xlsx"
        xlsx_path.write_bytes(build_exercise_workbook(model))
        print(f"Generado ejercicio: {xlsx_path}")


if __name__ == "__main__":
    main()

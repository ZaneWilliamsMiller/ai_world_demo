"""从 Pydantic 模型生成 JSON Schema 文件供 Godot 参考。"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.api.schema as schema_mod
from pydantic import BaseModel

response_models = []
for name in dir(schema_mod):
    obj = getattr(schema_mod, name)
    if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
        if name.endswith("Response"):
            response_models.append((name, obj))

output_dir = Path(__file__).resolve().parents[1] / "godot" / "api-schema"

combined = {}
for name, model in sorted(response_models):
    combined[name] = model.model_json_schema()

per_model_schemas = {}
for name, model in sorted(response_models):
    per_model_schemas[name] = model.model_json_schema()

parser = argparse.ArgumentParser(description="Generate JSON Schema files from Pydantic models")
parser.add_argument("--check", action="store_true", help="Compare generated output with existing files; exit 1 if different")
args = parser.parse_args()

if args.check:
    combined_path = output_dir / "api-schema.json"
    if not combined_path.is_file():
        print(f"CHECK FAILED: {combined_path} does not exist", file=sys.stderr)
        sys.exit(1)
    with combined_path.open(encoding="utf-8") as f:
        existing_combined = json.load(f)
    generated_combined = json.loads(json.dumps(combined, indent=2, ensure_ascii=False))
    if existing_combined != generated_combined:
        print(f"CHECK FAILED: {combined_path} is out of date. Run: python tools/gen_json_schema.py", file=sys.stderr)
        sys.exit(1)
    for name in per_model_schemas:
        model_path = output_dir / f"{name}.json"
        if not model_path.is_file():
            print(f"CHECK FAILED: {model_path} does not exist", file=sys.stderr)
            sys.exit(1)
        with model_path.open(encoding="utf-8") as f:
            existing_model = json.load(f)
        generated_model = json.loads(json.dumps(per_model_schemas[name], indent=2, ensure_ascii=False))
        if existing_model != generated_model:
            print(f"CHECK FAILED: {model_path} is out of date. Run: python tools/gen_json_schema.py", file=sys.stderr)
            sys.exit(1)
    print(f"CHECK PASSED: all {len(response_models)} JSON Schema files are up to date")
else:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "api-schema.json").open("w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    for name in per_model_schemas:
        with (output_dir / f"{name}.json").open("w", encoding="utf-8") as f:
            json.dump(per_model_schemas[name], f, indent=2, ensure_ascii=False)
    print(f"Generated {len(response_models)} JSON Schema files in {output_dir}")

"""从 Pydantic 模型生成 TypeScript 类型定义。"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.schema import *
import backend.api.schema as schema_mod
from pydantic import BaseModel

models = []
for name in dir(schema_mod):
    obj = getattr(schema_mod, name)
    if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
        models.append(obj)

model_names = {m.__name__ for m in models}


def json_schema_to_ts(schema: dict, defs: dict | None = None) -> str:
    """将 JSON Schema 片段递归转换为 TypeScript 类型字符串。"""
    if defs is None:
        defs = schema.get("$defs", {})

    if "$ref" in schema:
        ref = schema["$ref"]
        model_name = ref.split("/")[-1]
        return model_name

    if "anyOf" in schema:
        parts = []
        for sub in schema["anyOf"]:
            ts_type = json_schema_to_ts(sub, defs)
            parts.append(ts_type)
        return " | ".join(parts)

    if "allOf" in schema:
        parts = []
        for sub in schema["allOf"]:
            ts_type = json_schema_to_ts(sub, defs)
            parts.append(ts_type)
        return " & ".join(parts)

    if not schema or set(schema.keys()) <= {"title", "default"}:
        return "any"

    schema_type = schema.get("type")

    if schema_type == "string":
        return "string"
    elif schema_type == "integer":
        return "number"
    elif schema_type == "number":
        return "number"
    elif schema_type == "boolean":
        return "boolean"
    elif schema_type == "null":
        return "null"
    elif schema_type == "array":
        items = schema.get("items", {})
        if items:
            item_type = json_schema_to_ts(items, defs)
            if "|" in item_type:
                return f"({item_type})[]"
            return f"{item_type}[]"
        return "any[]"
    elif schema_type == "object":
        additional = schema.get("additionalProperties")
        if additional and isinstance(additional, dict):
            val_type = json_schema_to_ts(additional, defs)
            return f"Record<string, {val_type}>"
        return "Record<string, any>"

    return "any"


def format_default(value) -> str:
    """将 Python 默认值格式化为 TypeScript 默认值表示（仅用于注释）。"""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[]"
    if isinstance(value, dict):
        return "{}"
    return str(value)


def generate_interface(model) -> str:
    """为单个 Pydantic 模型生成 TypeScript interface 声明。"""
    schema = model.model_json_schema()
    defs = schema.get("$defs", {})

    title = schema.get("title", model.__name__)
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    lines = [f"export interface {title} {{"]

    for field_name, field_schema in properties.items():
        ts_type = json_schema_to_ts(field_schema, defs)
        is_optional = field_name not in required

        if is_optional:
            lines.append(f"  {field_name}?: {ts_type};")
        else:
            lines.append(f"  {field_name}: {ts_type};")

    lines.append("}")
    return "\n".join(lines)


lines = [
    "// Auto-generated TypeScript types from backend/api/schema.py",
    "// Do not edit manually - run: python tools/gen_ts_schema.py",
    "",
]

for model in sorted(models, key=lambda m: m.__name__):
    lines.append(generate_interface(model))
    lines.append("")

output_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static", "js", "api-types.d.ts",
)

generated = "\n".join(lines)

parser = argparse.ArgumentParser(description="Generate TypeScript types from Pydantic models")
parser.add_argument("--check", action="store_true", help="Compare generated output with existing file; exit 1 if different")
args = parser.parse_args()

if args.check:
    if not os.path.isfile(output_path):
        print(f"CHECK FAILED: {output_path} does not exist", file=sys.stderr)
        sys.exit(1)
    with open(output_path, "r", encoding="utf-8") as f:
        existing = f.read()
    if generated != existing:
        print(f"CHECK FAILED: {output_path} is out of date. Run: python tools/gen_ts_schema.py", file=sys.stderr)
        sys.exit(1)
    print(f"CHECK PASSED: {output_path} is up to date")
else:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(generated)
    print(f"Generated {output_path}")

# tools/validate_examples.py
from __future__ import annotations
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

# Rode: python -m tools.validate_examples (a partir da raiz do projeto)
ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "examples"

def load_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

# Carrega schemas
analysis = load_json(SCHEMAS / "analysis.schema.json")
generic  = load_json(SCHEMAS / "unit.generic.schema.json")
cobol    = load_json(SCHEMAS / "unit.cobol.schema.json")

# Checagem básica contra o meta-schema
Draft202012Validator.check_schema(analysis)
Draft202012Validator.check_schema(generic)
Draft202012Validator.check_schema(cobol)

# Registra recursos para que $ref locais sejam resolvidos
registry = Registry()
registry = registry.with_resource("analysis.schema.json",      Resource.from_contents(analysis))
registry = registry.with_resource("unit.generic.schema.json",  Resource.from_contents(generic))
registry = registry.with_resource("unit.cobol.schema.json",    Resource.from_contents(cobol))
# (opcional, cobertura extra para refs com './')
registry = registry.with_resource("./unit.generic.schema.json", Resource.from_contents(generic))
registry = registry.with_resource("./unit.cobol.schema.json",   Resource.from_contents(cobol))

# Cria o validador com o registry
validator = Draft202012Validator(analysis, registry=registry)

# Exemplos
examples = [
    EXAMPLES / "analysis.python.example.json",
    EXAMPLES / "analysis.cobol.example.json",
]

# Regra extra: end_line >= start_line
from .validators import assert_ranges  # requer tools/__init__.py e import relativo

def main():
    for path in examples:
        data = load_json(path)
        validator.validate(data)              # valida via analysis + $ref resolvidos
        assert_ranges(data.get("units", []))  # checagem adicional em Python
        print(f"OK: {path.name}")
    print("Todos os exemplos validados com sucesso.")

if __name__ == "__main__":
    main()

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Literal, Tuple
import os
from services.analyzer.specialists.generic_llm import analyze_units_generic_llm

Language = Literal["cobol", "python", "javascript", "typescript", "java", "csharp", "go", "ruby", "php", "shell", "unknown"]

COBOL_EXTS = {".cob", ".cbl", ".cobol"}
GENERIC_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "shell",
}

@dataclass
class Detection:
    language: str
    method: Literal["extension", "heuristic", "mixed"]
    confidence: float

def _ext(path: str) -> str:
    i = path.rfind(".")
    return path[i:].lower() if i != -1 else ""

def detect_language(path: str, content: str | None) -> Detection:
    """
    Heurística leve: extensão > padrões de conteúdo (COBOL divisions / shebang).
    """
    ext = _ext(path)

    # 1) Extensão
    if ext in COBOL_EXTS:
        return Detection("cobol", "extension", 0.98)
    if ext in GENERIC_MAP:
        return Detection(GENERIC_MAP[ext], "extension", 0.95)

    # 2) Heurística de conteúdo
    text = (content or "")[:5000].upper()
    if any(k in text for k in ("IDENTIFICATION DIVISION", "PROCEDURE DIVISION", "DATA DIVISION")):
        return Detection("cobol", "heuristic", 0.92)

    if content and content.startswith("#!"):
        if "python" in content:
            return Detection("python", "heuristic", 0.8)
        if "bash" in content or "sh" in content:
            return Detection("shell", "heuristic", 0.8)

    # 3) Fallback
    return Detection("unknown", "mixed", 0.5)

# --------- MOCK ANALYZERS (retornam unidades mínimas válidas p/ schema) ---------

def _mk_range_from_content(content: str | None) -> Tuple[int, int]:
    # estimativa simples só para preencher o schema
    if not content:
        return (1, 1)
    lines = content.count("\n") + 1
    return (1, max(1, min(lines, 999_999)))

def analyze_units_generic(code: str, language: str) -> list[dict]:
    start, end = _mk_range_from_content(code)
    # exemplo mínimo válido do schema unit.generic.schema.json
    return [{
        "kind": "generic",
        "id": "u_main",
        "name": "main",
        "range": {"start_line": start, "end_line": end},
        "signature": {
            "parameters": [],
            "returns": None
        },
        "purpose": "Função principal (mock): sumariza propósito a partir do código.",
        "io": {
            "inputs": [],
            "outputs": [],
            "side_effects": []
        },
        "logic": {
            "steps": [
                {"id": "s1", "text": "Inicialização", "kind": "action"},
                {"id": "s2", "text": "Processamento principal", "kind": "action"},
                {"id": "s3", "text": "Retornar resultado", "kind": "return"}
            ],
            "decisions": [],
            "calls": []
        },
        "risks": [],
        "diagram_suggestion": "flowchart"
    }]

def analyze_units_cobol(code: str) -> list[dict]:
    start, end = _mk_range_from_content(code)
    # extrai um possível parágrafo como nome (mock leve)
    m = re.search(r"^\s*([A-Z0-9-]+)\.\s*$", code.upper(), re.MULTILINE)
    unit_name = m.group(1) if m else "MAIN-PARAGRAPH"
    return [{
        "kind": "cobol",
        "id": f"u-{unit_name}",
        "name": unit_name,
        "range": {"start_line": start, "end_line": end},
        "division": "PROCEDURE",
        "purpose": "Parágrafo principal (mock): valida e processa registros.",
        "io": {
            "working_storage": [],
            "files": [],
            "inputs": [],
            "outputs": [],
            "side_effects": []
        },
        "control_flow": {
            "perform": [],
            "goto": [],
            "call": []
        },
        "logic": {
            "steps": [
                {"id": "s1", "text": "Ler registros de entrada", "kind": "io"},
                {"id": "s2", "text": "Validar campos", "kind": "other"},
                {"id": "s3", "text": "Gravar saída", "kind": "io"},
                {"id": "s4", "text": "EXIT", "kind": "exit"}
            ],
            "decisions": []
        },
        "diagram_suggestion": "flowchart",
        "notes": ""
    }]

def analyze_units(code: str, language: str, mode: Literal["per_unit", "whole_file"] = "per_unit") -> list[dict]:
    """
    Interface única para o app. Por enquanto retorna mocks válidos.
    Depois aqui chamaremos LangChain (router -> especialista).
    """
    lang = (language or "unknown").lower()
    if lang == "cobol":
        return analyze_units_cobol(code or "")
    # demais linguagens caem no genérico
    return analyze_units_generic(code or "", language=lang)

def analyze_units(code: str, language: str, path: str, mode: Literal["per_unit", "whole_file"] = "per_unit") -> list[dict]:
    """
    Se ANALYZE_WITH_LLM=true, usa o especialista genérico (todas as linguagens).
    Caso contrário, mantém o mock atual.
    """
    use_llm = os.getenv("ANALYZE_WITH_LLM", "false").lower() in ("1","true","yes","on")
    lang = (language or "unknown").lower()

    if use_llm:
        # para POC, use sempre o genérico (independente da linguagem)
        return analyze_units_generic_llm(code, lang, path)

    # --- MOCK antigo (fallback) ---
    if lang == "cobol":
        return analyze_units_cobol(code or "")
    return analyze_units_generic(code or "", language=lang)

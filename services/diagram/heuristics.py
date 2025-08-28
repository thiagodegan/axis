from __future__ import annotations
import re
from typing import Literal

Diagram = Literal["flowchart", "sequence", "state", "class", "er", "dfd", "none"]

STATE_WORDS = {"state", "status", "phase", "stage", "situacao", "situação"}
APPROVAL_WORDS = {"pending", "approved", "rejected", "cancelled", "failed", "success"}

def _text_blob(u: dict) -> str:
    parts = []
    for s in (u.get("logic", {}) or {}).get("steps", []) or []:
        parts.append(str(s.get("text") or ""))
    for d in (u.get("logic", {}) or {}).get("decisions", []) or []:
        parts.append(str(d.get("condition") or ""))
        # cobol branches
        for br in d.get("branches", []) or []:
            parts.append(str(br.get("label") or ""))
    for c in (u.get("logic", {}) or {}).get("calls", []) or []:
        parts.append(str(c.get("target") or ""))
        parts.append(str(c.get("kind") or ""))
    for se in (u.get("io", {}) or {}).get("side_effects", []) or []:
        parts.append(str(se))
    for inp in (u.get("io", {}) or {}).get("inputs", []) or []:
        parts.append(str(inp))
    for out in (u.get("io", {}) or {}).get("outputs", []) or []:
        parts.append(str(out))
    blob = " ".join(parts).lower()
    blob = re.sub(r"[^a-z0-9_]+", " ", blob)
    return blob

def suggest_diagram_type(u: dict) -> Diagram:
    """Heurística simples baseada nos campos do schema."""
    kind = (u.get("kind") or "").lower()
    logic = u.get("logic") or {}
    io = u.get("io") or {}

    steps = logic.get("steps") or []
    decisions = logic.get("decisions") or []
    calls = logic.get("calls") or []
    side = io.get("side_effects") or []

    # 0) Curto-circuitos por linguagem/unidade
    if kind == "cobol":
        # COBOL costuma ser procedural por parágrafo
        return "flowchart"

    # 1) Muitos atores/chamadas externas -> sequence
    external_kinds = {"api", "db", "queue", "other"}
    ext_calls = [c for c in calls if (c.get("kind") or "").lower() in external_kinds]
    targets = { (c.get("kind") or "").lower() + ":" + (c.get("target") or "").lower() for c in ext_calls if c.get("target") }
    if len(targets) >= 3 or (len({c.get("kind") for c in ext_calls}) >= 2 and len(targets) >= 2):
        return "sequence"

    # 2) Padrão de máquina de estados -> state
    blob = _text_blob(u)
    hints_state = any(w in blob for w in STATE_WORDS | APPROVAL_WORDS)
    many_branches = False
    if decisions:
        # generic: true/false; cobol: branches[]
        branch_counts = []
        for d in decisions:
            if "branches" in d:
                branch_counts.append(len(d.get("branches") or []))
            else:
                bc = 0
                if d.get("true_path"): bc += 1
                if d.get("false_path"): bc += 1
                branch_counts.append(bc)
        many_branches = any(b >= 3 for b in branch_counts)
    if hints_state and many_branches and len(ext_calls) <= 1:
        return "state"

    # 3) Foco em dados (ER/DFD): pouca decisão + muito IO
    few_decisions = len(decisions) <= 1
    heavy_io = (len(io.get("inputs") or []) + len(io.get("outputs") or []) + len(side)) >= 6
    has_db = any("db" in (c.get("kind") or "").lower() for c in calls) or "db" in blob or "table" in blob or "tabela" in blob
    if few_decisions and heavy_io and has_db:
        return "dfd"  # poderia ser "er" dependendo da sua preferência

    # 4) (Opcional) Classe/estrutura OO — raro por unidade; deixar para futuro
    # if some_oo_pattern: return "class"

    # 5) Padrão geral: ações/decisões -> flowchart
    return "flowchart"

from __future__ import annotations
import re
from typing import Dict, List
from services.diagram.heuristics import suggest_diagram_type

MAX_LABEL = 60

def _clean_label(txt: str) -> str:
    if not txt:
        return ""
    txt = re.sub(r"\s+", " ", str(txt)).strip()
    if len(txt) > MAX_LABEL:
        txt = txt[:MAX_LABEL - 1] + "…"
    txt = txt.replace("|", "/").replace('"', "'")
    return txt

def _node(label: str, shape: str = "rect") -> str:
    label = _clean_label(label)
    if shape in ("start", "end"):
        return f'(["{label}"])'
    if shape == "diamond":
        return f'{{"{label}"}}'
    return f'["{label}"]'



def _edge(frm: str, to: str, label: str | None = None) -> str:
    if label:
        return f'{frm} -- "{_clean_label(label)}" --> {to}'
    return f"{frm} --> {to}"

def _flowchart_header(direction: str = "TD") -> str:
    return f"flowchart {direction}"

def _from_generic_unit(u: dict) -> str:
    lines: List[str] = []
    lines.append(_flowchart_header("TD"))
    lines.append("START" + _node("Start", "start"))
    lines.append("END" + _node("End", "end"))

    step_ids = []
    for s in u.get("logic", {}).get("steps", []):
        sid = s["id"]
        lbl = s.get("text") or s.get("kind") or sid
        lines.append(f'{sid}{_node(lbl)}')
        step_ids.append(sid)

    for d in u.get("logic", {}).get("decisions", []):
        did = d["id"]
        cond = d.get("condition", did)
        lines.append(f'{did}{_node(cond, "diamond")}')
        tpath = (d.get("true_path") or [])[:1]
        fpath = (d.get("false_path") or [])[:1]
        if tpath:
            lines.append(_edge(did, tpath[0], "Sim"))
        if fpath:
            lines.append(_edge(did, fpath[0], "Não"))

    if step_ids:
        lines.append(_edge("START", step_ids[0]))
        for a, b in zip(step_ids, step_ids[1:]):
            lines.append(_edge(a, b))
        lines.append(_edge(step_ids[-1], "END"))
    else:
        lines.append(_edge("START", "END"))

    return "\n".join(lines)

def _from_cobol_unit(u: dict) -> str:
    lines: List[str] = []
    lines.append(_flowchart_header("TD"))
    lines.append("start" + _node("Start", "start"))
    lines.append("end" + _node("End", "end"))

    step_ids = []
    for s in u.get("logic", {}).get("steps", []):
        sid = s["id"]
        lbl = s.get("text") or s.get("kind") or sid
        lines.append(f'{sid}{_node(lbl)}')
        step_ids.append(sid)

    for d in u.get("logic", {}).get("decisions", []):
        did = d["id"]
        cond = d.get("condition", did)
        lines.append(f'{did}{_node(cond, "diamond")}')
        for br in d.get("branches") or []:
            label = br.get("label") or ""
            path = (br.get("path") or [])[:1]
            if path:
                lines.append(_edge(did, path[0], label))

    if step_ids:
        lines.append(_edge("start", step_ids[0]))
        for a, b in zip(step_ids, step_ids[1:]):
            lines.append(_edge(a, b))
        lines.append(_edge(step_ids[-1], "end"))
    else:
        lines.append(_edge("start", "end"))

    return "\n".join(lines)

def to_mermaid(analysis: Dict) -> Dict:
    """
    Recebe um JSON compatível com analysis.schema.json e devolve:
    { "diagrams": [ { "unit_id": "...", "unit_name": "...", "type": "flowchart", "code": "flowchart TD\n..." }, ... ] }
    """
    diagrams: List[Dict] = []
    for u in analysis.get("units", []):
        dg_type = u.get("diagram_suggestion") or suggest_diagram_type(u) or "flowchart"
        if u.get("kind") == "cobol":
            code = _from_cobol_unit(u)
        else:
            code = _from_generic_unit(u)
        diagrams.append({
            "unit_id": u.get("id"),
            "unit_name": u.get("name"),
            "type": dg_type,
            "code": code
        })
    return {"diagrams": diagrams}

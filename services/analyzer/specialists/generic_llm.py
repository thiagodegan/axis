from __future__ import annotations
import json
import re
from typing import List, Dict, Any
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from services.llm.client import get_llm
from jsonschema import Draft202012Validator

# Carrega o schema de unidade genérica para instruir a saída
ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "schemas" / "unit.generic.schema.json"
UNIT_GENERIC_SCHEMA: Dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
UNIT_VALIDATOR = Draft202012Validator(UNIT_GENERIC_SCHEMA)


SYSTEM = """Você é um assistente que lê código-fonte e devolve documentação ESTRUTURADA.
SEM TEXTO LIVRE. Saída deve ser JSON estrito, obedecendo unit.generic.schema.json.
Regras:
- Identifique UNIDADES (funções/métodos) no código.
- Para cada unidade, produza campos: kind="generic", id, name, range, signature, purpose, io, logic, risks?, diagram_suggestion?
- IDs de steps/decisions curtos (ex.: s1, s2, d1). 'range' com start_line/end_line aproximados.
- Em 'logic':
  - steps: sequência sucinta do que a função faz
  - decisions: condições principais; true_path/false_path (listas de IDs de steps)
  - calls: chamadas relevantes (API/DB/other)
- Em diagram_suggestion, sugira "flowchart" ou "sequence" ou "state" ou "class" ou "er" ou "dfd" ou "none" se fizer sentido. Mas nunca diferente disso.
- Limite rótulos (text) a 60 caracteres aprox.
- NUNCA inclua comentários fora do JSON.
"""

HUMAN = """Linguagem: {language}
Arquivo: {path}
Trecho analisado (pode estar truncado):
{code}
Esquema JSON (unit.generic.schema.json, resumo):
{schema_summary}

Saída esperada: um ARRAY JSON de unidades (ex.: [ {{...}}, {{...}} ]).
IMPORTANTE: apenas o JSON do array. Nada além disso."""

# ------------------ SANITIZERS ------------------

_ALLOWED_UNIT_KEYS = {
    "kind", "id", "name", "range", "signature", "purpose",
    "io", "logic", "risks", "diagram_suggestion"
}
_ALLOWED_LOGIC_KEYS = {"steps", "decisions", "calls"}
_ALLOWED_IO_KEYS = {"inputs", "outputs", "side_effects"}

_STEP_KIND_SAFE = {"action", "io", "return", "exit", "other"}

def _parse_signature(sig: str) -> Dict[str, Any]:
    params = []
    returns = None

    mret = re.search(r"->\s*([a-zA-Z0-9_\[\],\.]+)", sig)
    if mret:
        returns = mret.group(1).strip()

    m = re.search(r"\((.*)\)", sig)
    if m:
        raw = m.group(1)
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        for p in parts:
            if p in ("self", "cls"):
                continue
            name = p
            typ = None
            m2 = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([^=]+)", p)
            if m2:
                name = m2.group(1).strip()
                typ = m2.group(2).strip()
            params.append(_sanitize_param({"name": name, "type": typ}))
    return {"parameters": params, "returns": returns}

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")  # p/ steps e decisions
def _norm_step_id(raw: str, fallback: str) -> str:
    """
    Normaliza um id de step/decision para casar com o schema:
    - troca qualquer char inválido por '_'
    - trunca a 32 chars
    - garante não vazio (usa fallback)
    """
    s = (raw or fallback)
    s = re.sub(r"[^A-Za-z0-9_-]", "_", s)
    if not s:
        s = fallback
    return s[:32]

def _map_path_ids(path_list, idmap):
    """aplica idmap, e normaliza qualquer id que ainda fique fora do padrão"""
    if not isinstance(path_list, list):
        return []
    out = []
    for x in path_list:
        rid = str(x)
        nid = idmap.get(rid) or _norm_step_id(rid, rid or "s1")
        out.append(nid)
    return out

def _coerce_steps_with_map(steps):
    """
    Retorna (lista_de_steps_normalizados, mapa_ids)
    mapa_ids: {id_original -> id_normalizado}
    """
    out, idmap = [], {}
    if not isinstance(steps, list):
        return out, idmap

    used = set()
    for i, s in enumerate(steps, start=1):
        # extrai campos
        if isinstance(s, str):
            raw_id = f"s{i}"
            text = s
            kind = "action"
        else:
            raw_id = (s.get("id") if isinstance(s, dict) else None) or f"s{i}"
            text = (s.get("text") if isinstance(s, dict) else "") or (s.get("label") if isinstance(s, dict) else "") or ""
            kind = (s.get("kind") if isinstance(s, dict) else "action") or "action"

        # normaliza id
        nid = _norm_step_id(str(raw_id), f"s{i}")
        # resolve colisão
        base, k = nid, 2
        while nid in used:
            nid = (base + f"_{k}")[:32]
            k += 1
        used.add(nid)
        idmap[str(raw_id)] = nid

        # normaliza kind pro enum do schema
        if kind.lower() not in {"action","io","calc","loop","assign","return","try","catch","finally"}:
            kind = "action"

        out.append({
            "id": nid,
            "text": str(text)[:60],
            "kind": kind.lower()
        })
    return out, idmap


_STEP_KIND_ALLOWED = {"action","io","calc","loop","assign","return","try","catch","finally"}

def _coerce_steps(steps):
    out = []
    if isinstance(steps, list):
        for i, s in enumerate(steps, start=1):
            if isinstance(s, str):
                out.append({"id": f"s{i}", "text": s[:60], "kind": "action"})
            elif isinstance(s, dict):
                sid  = s.get("id") or f"s{i}"
                txt  = (s.get("text") or s.get("label") or "").strip()[:60]
                kind = (s.get("kind") or "action").lower()
                if kind not in _STEP_KIND_ALLOWED:
                    kind = "action"
                out.append({"id": sid, "text": txt, "kind": kind})
    return out

# depois dos imports
_PARAM_ALLOWED = {"name", "type", "mode", "default"}

def _sanitize_param(p) -> dict:
    # aceita string ("token") ou dict; remove chaves não permitidas e valores None
    if isinstance(p, str):
        return {"name": p}
    if not isinstance(p, dict):
        return {"name": str(p)}
    out = {}
    for k in _PARAM_ALLOWED:
        if k in p and p[k] is not None:
            out[k] = p[k]
    # garante name
    if "name" not in out or not out["name"]:
        out["name"] = p.get("name") or "param"
    # normaliza mode se vier errado
    if "mode" in out and out["mode"] not in ("in", "out", "inout"):
        out.pop("mode", None)
    return out

def _coerce_calls(calls) -> list[Dict[str, Any]]:
    out = []
    if isinstance(calls, list):
        for c in calls:
            if isinstance(c, dict):
                target = c.get("target")
                kind = (c.get("kind") or "other").lower()
                out.append({"target": target, "kind": kind})
            elif isinstance(c, str):
                out.append({"target": c, "kind": "other"})
    return out

def _to_string_list(x):
    if x is None: return []
    if isinstance(x, list):
        res = []
        for item in x:
            if isinstance(item, dict):
                name = item.get("name") or item.get("var") or item.get("field")
                typ  = item.get("type")
                desc = item.get("description") or item.get("desc")
                s = " ".join(str(y) for y in [name, typ, desc] if y)
                res.append(s or json.dumps(item, ensure_ascii=False)[:60])
            else:
                res.append(str(item))
        return res
    return [str(x)]

def _strip_additional_props(d: Dict[str, Any], allowed: set[str]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if k in allowed}

def _coerce_decisions(decisions, idmap):
    out = []
    if not isinstance(decisions, list):
        return out
    used = set()
    for i, d in enumerate(decisions, start=1):
        # id e condição
        raw_id = (d.get("id") if isinstance(d, dict) else None) or f"d{i}"
        did = _norm_step_id(str(raw_id), f"d{i}")
        # resolve colisão
        base, k = did, 2
        while did in used:
            did = (base + f"_{k}")[:32]
            k += 1
        used.add(did)

        cond = ""
        if isinstance(d, dict):
            cond = (d.get("condition") or d.get("text") or "")[:300]
        else:
            cond = str(d)[:300]

        # formato generic (true/false) ou ignorar branches COBOL aqui
        tp = fp = []
        if isinstance(d, dict):
            tp = _map_path_ids(d.get("true_path") or [], idmap)
            fp = _map_path_ids(d.get("false_path") or [], idmap)

        out.append({
            "id": did,
            "condition": cond,
            "true_path": tp,
            "false_path": fp
        })
    return out

def _coerce_generic_unit(u: Dict[str, Any]) -> Dict[str, Any]:
    v = {k: u[k] for k in u if k in _ALLOWED_UNIT_KEYS}
    v["kind"] = "generic"

    # range
    rng = u.get("range") or {}
    sl = rng.get("start_line") or 1
    el = rng.get("end_line") or max(1, sl)
    try:
        sl = int(sl)
        el = int(el)
    except Exception:
        sl, el = 1, 1
    if el < sl:
        el = sl
    v["range"] = {"start_line": sl, "end_line": el}

    # signature
    sig = u.get("signature")
    if isinstance(sig, str):
        v["signature"] = _parse_signature(sig)
    elif isinstance(sig, dict):
        # normaliza campos mínimos
        params = sig.get("parameters") if isinstance(sig.get("parameters"), list) else []
        params2 = []
        for p in params:
            if isinstance(p, dict):
                params2.append({
                    "name": p.get("name"),
                    "type": p.get("type"),
                    "description": p.get("description"),
                })
            else:
                params2.append({"name": str(p), "type": None, "description": None})
        v["signature"] = {"parameters": params2, "returns": sig.get("returns")}
    else:
        v["signature"] = {"parameters": [], "returns": None}

    # purpose
    v["purpose"] = (u.get("purpose") or "").strip()[:200] or f"Auto-gerada para {u.get('name') or u.get('id') or 'unit'}"

    # io
    io = u.get("io") or {}
    io = _strip_additional_props(io, _ALLOWED_IO_KEYS)
    v["io"] = {
        "inputs": _to_string_list(io.get("inputs")),
        "outputs": _to_string_list(io.get("outputs")),
        "side_effects": _to_string_list(io.get("side_effects")),
    }

    # logic
    lg = u.get("logic") or {}
    steps_norm, idmap = _coerce_steps_with_map(lg.get("steps") or [])
    decisions_norm = _coerce_decisions(lg.get("decisions") or [], idmap)
    calls_norm = _coerce_calls(lg.get("calls") or [])

    v["logic"] = {
        "steps": steps_norm,
        "decisions": decisions_norm,
        "calls": calls_norm
    }

    # opcionais
    risks = u.get("risks")
    v["risks"] = [str(r) for r in risks] if isinstance(risks, list) else []

    if isinstance(u.get("diagram_suggestion"), str):
        v["diagram_suggestion"] = u["diagram_suggestion"]
    else:
        v.pop("diagram_suggestion", None)

    # id/name
    v["id"] = u.get("id") or "u_main"
    v["name"] = u.get("name") or v["id"]

    return v



def _schema_summary(schema: Dict[str, Any]) -> str:
    # resumo compacto para o prompt (evita enviar o schema inteiro)
    props = schema.get("properties", {})
    keys = list(props.keys())
    return "Campos obrigatórios: " + ", ".join(k for k in keys if k in schema.get("required", [])) + \
           ". Outros campos: " + ", ".join(k for k in keys if k not in schema.get("required", []))

def analyze_units_generic_llm(code: str, language: str, path: str) -> List[Dict[str, Any]]:
    """
    Usa LLM para produzir uma lista de unidades no formato do schema genérico.
    Para POC, se o arquivo for muito grande, enviamos só um trecho.
    """
    # Truncagem simples para POC (ex.: 300 linhas)
    MAX_CHARS = 12000
    snippet = code[:MAX_CHARS]

    llm = get_llm()
    parser = JsonOutputParser()  # espera JSON puro

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM),
        ("human", HUMAN),
    ]).partial(
        language=language,
        path=path,
        schema_summary=_schema_summary(UNIT_GENERIC_SCHEMA)
    )

    chain = prompt | llm | parser

    try:
        units = chain.invoke({"code": snippet})
    except Exception as e:
        units = [{
            "kind": "generic",
            "id": "u_main",
            "name": "main",
            "range": {"start_line": 1, "end_line": max(1, snippet.count("\n")+1)},
            "signature": {"parameters": [], "returns": None},
            "purpose": f"Falha no LLM: {e}. Mock de contingência.",
            "io": {"inputs": [], "outputs": [], "side_effects": []},
            "logic": {"steps": [{"id":"s1","text":"Processo principal","kind":"action"}], "decisions": [], "calls": []},
            "risks": []
        }]

    if isinstance(units, dict):
        units = [units]
    
    sane: List[Dict[str, Any]] = []
    for u in units:
        cu = _coerce_generic_unit(u or {})
        try:
            UNIT_VALIDATOR.validate(cu)
            sane.append(cu)
        except Exception:
            # tentativa mínima extra: garantir ao menos um step
            if not cu["logic"]["steps"]:
                cu["logic"]["steps"] = [{"id": "s1", "text": cu["purpose"][:60], "kind": "action"}]
            try:
                UNIT_VALIDATOR.validate(cu)
                sane.append(cu)
            except Exception:
                continue

    if not sane:
        sane = [{
            "kind": "generic",
            "id": "u_main",
            "name": "main",
            "range": {"start_line": 1, "end_line": max(1, (code or "").count("\n")+1)},
            "signature": {"parameters": [], "returns": None},
            "purpose": "Fallback: nenhuma unidade válida retornada pelo LLM.",
            "io": {"inputs": [], "outputs": [], "side_effects": []},
            "logic": {"steps": [{"id":"s1","text":"Processo principal","kind":"action"}], "decisions": [], "calls": []},
            "risks": []
        }]
    return sane
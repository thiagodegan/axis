from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from services.analyzer.router import detect_language, analyze_units
from services.db import Base, engine, get_db
from models.config import Config
from services.crypto import encrypt, decrypt
from services.github import GitHubClient
from pathlib import Path
import json
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from services.diagram.mermaid import to_mermaid

# Validador JSON Schema (ex.: para validar o output do analisador)
def _load_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

SCHEMA_ROOT = Path(__file__).resolve().parent / "schemas"
try:
    _analysis_schema = _load_json(SCHEMA_ROOT / "analysis.schema.json")
    _generic_schema  = _load_json(SCHEMA_ROOT / "unit.generic.schema.json")
    _cobol_schema    = _load_json(SCHEMA_ROOT / "unit.cobol.schema.json")
    Draft202012Validator.check_schema(_analysis_schema)
    Draft202012Validator.check_schema(_generic_schema)
    Draft202012Validator.check_schema(_cobol_schema)

    _registry = Registry()
    _registry = _registry.with_resource("analysis.schema.json",      Resource.from_contents(_analysis_schema))
    _registry = _registry.with_resource("unit.generic.schema.json",  Resource.from_contents(_generic_schema))
    _registry = _registry.with_resource("unit.cobol.schema.json",    Resource.from_contents(_cobol_schema))
    _registry = _registry.with_resource("./unit.generic.schema.json", Resource.from_contents(_generic_schema))
    _registry = _registry.with_resource("./unit.cobol.schema.json",   Resource.from_contents(_cobol_schema))

    ANALYSIS_VALIDATOR = Draft202012Validator(_analysis_schema, registry=_registry)
except Exception as e:
    ANALYSIS_VALIDATOR = None
    print(f"[warn] Schemas não carregados: {e}")


app = Flask(__name__)
app.secret_key = "dev-secret"  # só para flash messages (pode mover para .env se quiser)

# cria as tabelas (em produção, usar migrações)
Base.metadata.create_all(bind=engine)

def _require_token():
    db = next(get_db())
    enc_token = get_config_value(db, "github_token")
    token = decrypt(enc_token) if enc_token else None
    if not token:
        flash("Configure o token do GitHub primeiro.", "error")
        return None
    return token

def _build_tree(entries):
    """
    Constrói uma árvore a partir do /git/trees?recursive=1
    Mantemos apenas 'blob' (arquivo) e 'tree' (diretório).
    Saída:
      { 'type': 'dir', 'name': '', 'children': { 'src': {...}, 'README.md': {...} } }
    """
    root = {"type": "dir", "name": "", "children": {}}

    for e in entries:
        p = e.get("path", "")
        t = e.get("type")

        # ignorar tipos que não são dir/arquivo (ex.: submodule 'commit')
        if t not in ("blob", "tree"):
            continue

        if not p:  # caminho vazio não deve acontecer, mas por via das dúvidas
            continue

        parts = p.split("/")
        node = root
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            if is_last:
                if t == "tree":
                    node["children"].setdefault(part, {"type": "dir", "name": part, "children": {}})
                else:  # blob
                    node["children"][part] = {"type": "file", "name": part, "path": p}
            else:
                node = node["children"].setdefault(part, {"type": "dir", "name": part, "children": {}})

    return root


@app.get("/github/repo/<owner>/<repo>")
def repo_browser(owner, repo):
    """Página de navegação. Query params:
    - ref: branch/sha (opcional; default = default_branch)
    - path: arquivo selecionado (opcional)
    """
    token = _require_token()
    if token is None:
        return redirect(url_for("settings_get"))

    gh = GitHubClient(token)
    ref = request.args.get("ref")
    try:
        if not ref:
            ref = gh.get_default_branch(owner, repo)
        tree_data = gh.get_tree_recursive(owner, repo, ref)
        entries = tree_data.get("tree", [])
        tree = _build_tree(entries)
        branches = gh.list_branches(owner, repo)
    except Exception as e:
        flash(f"Erro ao carregar árvore do repositório: {e}", "error")
        return redirect(url_for("github_repos"))

    # Conteúdo do arquivo selecionado (se houver)
    selected_path = request.args.get("path")
    file_view = None
    if selected_path:
        try:
            file_view = gh.get_file_content(owner, repo, selected_path, ref)
        except Exception as e:
            flash(f"Erro ao abrir arquivo: {e}", "error")
            file_view = None

    return render_template(
        "repo_browser.html",
        owner=owner,
        repo=repo,
        ref=ref,
        branches=branches,
        tree=tree,
        selected_path=selected_path,
        file_view=file_view,
    )

def get_config_value(db, key: str) -> str | None:
    item = db.query(Config).filter(Config.key == key).one_or_none()
    return item.value if item else None

def set_config_value(db, key: str, value: str | None):
    item = db.query(Config).filter(Config.key == key).one_or_none()
    if item:
        item.value = value
    else:
        item = Config(key=key, value=value)
        db.add(item)
    db.commit()

@app.post("/docs/analyze")
def docs_analyze():
    """
    Body JSON:
    {
      "owner": "...",
      "repo": "...",
      "ref": "main" | "sha",
      "path": "caminho/no/repo.ext",
      "mode": "per_unit" | "whole_file"   # opcional (default per_unit)
    }
    Retorna JSON compatível com analysis.schema.json (mock no momento).
    """
    payload = request.get_json(silent=True) or {}
    owner = payload.get("owner")
    repo  = payload.get("repo")
    ref   = (payload.get("ref") or "").strip()
    path  = payload.get("path")
    mode  = payload.get("mode") or "per_unit"

    if not all([owner, repo, ref, path]):
        return jsonify({"error": "Campos obrigatórios: owner, repo, ref, path"}), 400

    token = _require_token()
    if token is None:
        return jsonify({"error": "Token não configurado"}), 400

    gh = GitHubClient(token)
    try:
        fv = gh.get_file_content(owner, repo, path, ref)
    except Exception as e:
        return jsonify({"error": f"Falha ao obter arquivo: {e}"}), 502

    if not fv or fv.get("type") != "file" or not fv.get("is_text"):
        return jsonify({"error": "Arquivo não é texto ou não foi possível obter conteúdo."}), 415

    code = fv.get("text") or ""
    det  = detect_language(path, code)
    units = analyze_units(code, det.language, path, mode="per_unit" if mode != "whole_file" else "whole_file")

    analysis = {
        "version": "1.0.0",
        "file": {
            "path": path,
            "sha": fv.get("sha") or "unknown",
            "repo": repo,
            "owner": owner,
            "size_bytes": fv.get("size") or 0
        },
        "ref": ref,
        "language": det.language,
        "detector": {
            "method": det.method,
            "confidence": det.confidence
        },
        "units": units,
        "summary": {
            "unit_count": len(units),
            "diagram_suggestion": "flowchart",
            "notes": "Resultado mock do router; LangChain será plugado aqui."
        }
    }

    # Validação contra o schema (opcional)
    if ANALYSIS_VALIDATOR is not None:
        try:
            ANALYSIS_VALIDATOR.validate(analysis)
        except Exception as e:
            # se der problema, retorna 500 para ficarmos sabendo em dev
            return jsonify({"error": f"Saída não compatível com schema: {e}"}), 500

    return jsonify(analysis), 200

@app.post("/docs/to_mermaid")
def docs_to_mermaid():
    payload = request.get_json(silent=True) or {}
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        return jsonify({"error": "Campo 'analysis' é obrigatório e deve ser um objeto."}), 400
    try:
        result = to_mermaid(analysis)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": f"Falha ao gerar Mermaid: {e}"}), 500


@app.get("/")
def index():
    db = next(get_db())
    enc_token = get_config_value(db, "github_token")
    has_token = enc_token is not None
    return render_template("index.html", has_token=has_token)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/settings")
def settings_get():
    # Mostra se o token existe (mas sem exibi-lo)
    db = next(get_db())
    enc_token = get_config_value(db, "github_token")
    has_token = enc_token is not None
    return render_template("settings.html", has_token=has_token)

@app.post("/settings")
def settings_post():
    db = next(get_db())
    token = request.form.get("github_token") or ""
    if not token.strip():
        flash("Informe um token do GitHub (PAT).", "error")
        return redirect(url_for("settings_get"))
    enc = encrypt(token.strip())
    set_config_value(db, "github_token", enc)
    flash("Token salvo com sucesso.", "success")
    return redirect(url_for("settings_get"))

@app.post("/settings/test")
def settings_test():
    db = next(get_db())
    enc_token = get_config_value(db, "github_token")
    token = decrypt(enc_token) if enc_token else None
    if not token:
        flash("Token não configurado.", "error")
        return redirect(url_for("settings_get"))
    try:
        gh = GitHubClient(token)
        data = gh.get_user()
        flash(f"Autenticado como: {data.get('login')}", "success")
    except Exception as e:
        flash(f"Falha na autenticação: {e}", "error")
    return redirect(url_for("settings_get"))

@app.get("/github/repos")
def github_repos():
    db = next(get_db())
    enc_token = get_config_value(db, "github_token")
    token = decrypt(enc_token) if enc_token else None
    if not token:
        flash("Configure o token do GitHub primeiro.", "error")
        return redirect(url_for("settings_get"))
    try:
        gh = GitHubClient(token)
        repos = gh.list_repos()
        # mapeia campos relevantes para a view
        view = [
            {
                "name": r.get("name"),
                "html_url": r.get("html_url"),
                "private": r.get("private"),
                "updated_at": r.get("updated_at"),
                "description": r.get("description"),
                "owner": r.get("owner", {}).get("login"),
            }
            for r in repos
        ]
        return render_template("repos.html", repos=view)
    except Exception as e:
        flash(f"Erro ao listar repositórios: {e}", "error")
        return redirect(url_for("settings_get"))
    
@app.get("/enter")
def enter():
    """Decide automaticamente pra onde ir ao clicar em 'Entrar' na home."""
    db = next(get_db())
    enc_token = get_config_value(db, "github_token")
    if enc_token:
        return redirect(url_for("github_repos"))
    return redirect(url_for("settings_get"))    

if __name__ == "__main__":
    app.run(debug=True)

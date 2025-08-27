import base64
import requests

GITHUB_API = "https://api.github.com"

class GitHubClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "fiap-ford-migracao-legado"
        })

    def get_user(self):
        resp = self.session.get(f"{GITHUB_API}/user", timeout=20)
        resp.raise_for_status()
        return resp.json()

    def list_repos(self):
        # lista os repositórios do usuário autenticado (pessoais)
        # depois podemos expandir para orgs: /user/orgs + /orgs/{org}/repos
        repos = []
        url = f"{GITHUB_API}/user/repos?per_page=100&sort=updated"
        while url:
            r = self.session.get(url, timeout=30)
            r.raise_for_status()
            repos.extend(r.json())
            # paginação simples
            url = None
            if "next" in r.links:
                url = r.links["next"]["url"]
        return repos

    def get_repo(self, owner: str, repo: str):
        r = self.session.get(f"{GITHUB_API}/repos/{owner}/{repo}", timeout=20)
        r.raise_for_status()
        return r.json()

    def get_default_branch(self, owner: str, repo: str) -> str:
        data = self.get_repo(owner, repo)
        return data.get("default_branch", "main")

    def list_branches(self, owner: str, repo: str):
        r = self.session.get(f"{GITHUB_API}/repos/{owner}/{repo}/branches?per_page=100", timeout=20)
        r.raise_for_status()
        return r.json()

    def get_tree_recursive(self, owner: str, repo: str, ref: str):
        # recursive=1 retorna até 100k entradas; suficiente para a maioria dos repos
        r = self.session.get(f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1", timeout=60)
        r.raise_for_status()
        return r.json()

    def get_file_content(self, owner: str, repo: str, path: str, ref: str | None = None) -> dict:
        params = {"ref": ref} if ref else {}
        r = self.session.get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            # Se path apontar para diretório por engano, retorna lista
            return {"type": "dir", "entries": data}

        # Conteúdo de arquivo
        if data.get("encoding") == "base64":
            raw = base64.b64decode(data["content"])
            # tentativa simples de detectar texto
            try:
                text = raw.decode("utf-8")
                is_text = True
            except UnicodeDecodeError:
                text = None
                is_text = False

            return {
                "type": "file",
                "is_text": is_text,
                "text": text,
                "size": data.get("size"),
                "name": data.get("name"),
                "path": data.get("path"),
                "sha": data.get("sha"),
                "html_url": data.get("html_url"),
            }
        return {"type": "unknown", "raw": data}
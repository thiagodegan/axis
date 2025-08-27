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

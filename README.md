# RECODER

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Flask](https://img.shields.io/badge/Flask-2.x-orange)
![GitHub](https://img.shields.io/badge/GitHub-Integration-green)

Ferramenta de apoio à **migração de código legado** utilizando **Inteligência Artificial (GenIA)** desenvolvida para o Challenge FIAP 2025.

---

## Sobre o Projeto

Este projeto tem como objetivo apoiar a **FORD** no processo de **migração de sistemas legados** (COBOL, ASP Clássico, AngularJS, bancos de dados antigos, etc.), utilizando **Inteligência Artificial** para:

- **Documentação automática** de código legado.
- **Sugestões de estruturas modernas** equivalentes.
- **Integração com GitHub** para facilitar acesso e versionamento.
- **Geração automática de fluxogramas** com **Mermaid**.
- Experiência de desenvolvimento no modo **Vibe Coding**.

O projeto é desenvolvido em **Python/Flask**, com armazenamento local em **SQLite** para configurações de usuário.

---

## Tecnologias Utilizadas

- **Python 3**
- **Flask** (backend web)
- **LangChain** (análise e documentação do código)
- **Mermaid** (geração de fluxogramas)
- **GitHub API** (integração com repositórios)
- **SQLite** (armazenamento local de configurações)

---

## Como rodar o projeto localmente

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU-USUARIO/NOME-DO-PROJETO.git
cd NOME-DO-PROJETO
```

### 2. Criar ambiente virtual

```bash
python3 -m venv venv
```
ou

```bash
python -m venv venv
```

### 3. Ativar ambiente virtual

- **Linux/macOS:**

  ```bash
  source venv/bin/activate
  ```

- **Windows (PowerShell):**

  ```powershell
  .\venv\Scripts\Activate
  ```

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 5. Congelar as dependências (sempre que instalar novos pacotes)

```bash
pip freeze > requirements.txt
```

### 6. Rodar o Flask Localmente

```bash
python app.py
```
O webapp estará disponível em http://127.0.0.1:5000.

---

## Próximos Passos

- [ ] Criar a estrutura inicial em Flask
- [ ] Configurar integração com GitHub API
- [ ] Implementar análise de arquivos via LangChain
- [ ] Gerar fluxogramas usando Mermaid
- [ ] Criar interface web para interação com o usuário

---

## Equipe

- Thiago Degan
- Rebecca Damasceno
- Jacqueline Novaes
- Leandro Cavallari
- Sofia Sawczenko

---

## Licença

Projeto acadêmico desenvolvido para o **FIAP Challenge - FORD**.

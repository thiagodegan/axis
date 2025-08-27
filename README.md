# 🚀 FIAP Challenge - FORD

Ferramenta de apoio à migração de código legado com GenIA

---

## 📖 Sobre o Projeto

Este projeto tem como objetivo apoiar a **FORD** no processo de **migração de sistemas legados** (COBOL, ASP Clássico, AngularJS, bancos de dados antigos, etc.), utilizando **Inteligência Artificial** para:

- 📄 Documentar automaticamente código legado.
- 💡 Sugerir estruturas modernas equivalentes.
- 🔗 Integrar com o GitHub para facilitar o acesso a repositórios.
- 🖼️ Gerar fluxogramas automáticos (via **Mermaid**).
- 🎧 Proporcionar uma experiência de desenvolvimento no estilo **Vibe Coding**.

A solução será desenvolvida como um **webapp em Flask (Python)**, com integração ao **GitHub** e armazenamento local em **SQLite** para configurações de usuário.

---

## ⚙️ Tecnologias Utilizadas

- **Python 3.x**
- **Flask** (backend web)
- **LangChain** (análise e documentação do código)
- **Mermaid** (geração de fluxogramas)
- **GitHub API** (integração com repositórios)
- **SQLite** (armazenamento local de configurações)

---

## 🛠️ Como rodar o projeto

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU-USUARIO/NOME-DO-PROJETO.git
cd NOME-DO-PROJETO
```

### 2. Criar ambiente virtual

```bash
python3 -m venv venv
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

### 4. Instalar dependências

```bash
pip install -r requirements.txt
```

### 5. Congelar dependências (sempre que instalar novos pacotes)

```bash
pip freeze > requirements.txt
```

---

## 📌 Próximos Passos

- [ ] Criar a estrutura inicial em Flask
- [ ] Configurar integração com GitHub API
- [ ] Implementar análise de arquivos via LangChain
- [ ] Gerar fluxogramas usando Mermaid
- [ ] Criar interface web para interação com o usuário

---

## 👨‍💻 Equipe

- Nome 1
- Nome 2
- Nome 3
- Nome 4

---

## 📄 Licença

Projeto acadêmico desenvolvido para o **FIAP Challenge - FORD**.

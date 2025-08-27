import os
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()

_SECRET = os.getenv("SECRET_KEY")  # DEVE ser uma Fernet key (base64 urlsafe)

if not _SECRET:
    # Dica: gere uma com: >>> from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
    raise RuntimeError("SECRET_KEY ausente no .env. Gere uma Fernet key e defina SECRET_KEY=...")

fernet = Fernet(_SECRET.encode() if isinstance(_SECRET, str) else _SECRET)

def encrypt(text: str) -> str:
    if text is None:
        return None
    token = fernet.encrypt(text.encode())
    return token.decode()

def decrypt(token: str) -> str | None:
    if token is None:
        return None
    try:
        return fernet.decrypt(token.encode()).decode()
    except (InvalidToken, AttributeError):
        return None

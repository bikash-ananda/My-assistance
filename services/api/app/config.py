from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read_local_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    database_path: Path
    owner_salt: str
    owner_hash: str
    session_secret: str
    session_minutes: int = 720
    provider: str = "none"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    cookie_secure: bool = False
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    google_token_encryption_key: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        _read_local_env()
        db = os.getenv("BIKASH_DATABASE_PATH", "./data/bikash.sqlite3")
        db_path = Path(db)
        if not db_path.is_absolute():
            db_path = ROOT / db_path
        return cls(
            database_path=db_path,
            owner_salt=os.getenv("BIKASH_OWNER_SALT", ""),
            owner_hash=os.getenv("BIKASH_OWNER_HASH", ""),
            session_secret=os.getenv("BIKASH_SESSION_SECRET", ""),
            session_minutes=max(15, min(1440, int(os.getenv("BIKASH_SESSION_MINUTES", "720")))),
            provider=os.getenv("MODEL_PROVIDER", "none").lower(),
            ollama_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", ""),
            cookie_secure=os.getenv("BIKASH_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
            google_oauth_client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            google_oauth_client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            google_oauth_redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", ""),
            google_token_encryption_key=os.getenv("BIKASH_GOOGLE_TOKEN_ENCRYPTION_KEY", ""),
        )

    @property
    def auth_configured(self) -> bool:
        return all((self.owner_salt, self.owner_hash, self.session_secret))

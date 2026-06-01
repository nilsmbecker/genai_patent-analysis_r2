from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"


@dataclass(slots=True)
class AppConfig:
    name: str
    host: str
    port: int


@dataclass(slots=True)
class DatabaseConfig:
    path: Path


@dataclass(slots=True)
class OpenRouterConfig:
    enabled: bool
    api_key: str
    model: str
    base_url: str
    site_url: str
    site_name: str
    request_timeout_seconds: int


@dataclass(slots=True)
class Settings:
    root_dir: Path
    config_path: Path
    app: AppConfig
    database: DatabaseConfig
    openrouter: OpenRouterConfig


def _pick_config_path() -> Path:
    for candidate in [
        CONFIG_DIR / "settings.local.toml",
        CONFIG_DIR / "settings.toml",
        CONFIG_DIR / "settings.example.toml",
    ]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No settings TOML found in config/.")


def load_settings(explicit_path: str | Path | None = None) -> Settings:
    config_path = Path(explicit_path) if explicit_path else _pick_config_path()
    with config_path.open("rb") as fh:
        payload = tomllib.load(fh)

    app = payload.get("app", {})
    db  = payload.get("database", {})
    or_ = payload.get("openrouter", {})

    db_path = db.get("path", "data/patent_analysis.sqlite3")
    resolved_db = Path(db_path) if Path(db_path).is_absolute() else ROOT_DIR / db_path

    return Settings(
        root_dir=ROOT_DIR,
        config_path=config_path,
        app=AppConfig(
            name=app.get("name", "Patent Analysis"),
            host=app.get("host", "127.0.0.1"),
            port=int(app.get("port", 8000)),
        ),
        database=DatabaseConfig(path=resolved_db),
        openrouter=OpenRouterConfig(
            enabled=bool(or_.get("enabled", False)),
            api_key=or_.get("api_key", "").strip(),
            model=or_.get("model", "").strip(),
            base_url=or_.get("base_url", "https://openrouter.ai/api/v1/chat/completions").strip(),
            site_url=or_.get("site_url", "http://localhost:8000").strip(),
            site_name=or_.get("site_name", "Patent Analysis").strip(),
            request_timeout_seconds=int(or_.get("request_timeout_seconds", 60)),
        ),
    )

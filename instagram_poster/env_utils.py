"""
Utilitários para ler e atualizar o ficheiro .env.
Quando um JSON é carregado na UI, as variáveis relevantes são escritas no .env
para manter consistência e evitar transtornos.
"""
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _get_env_paths() -> list[Path]:
    """Devolve lista de caminhos .env a tentar (prioridade). Mesma ordem que config.py."""
    return [
        _PROJECT_ROOT / ".env",
        _PROJECT_ROOT / "instagramAutoPost" / ".env",
    ]


def get_env_path() -> Optional[Path]:
    """Devolve o primeiro .env existente, ou o da raiz do projeto para criar."""
    for p in _get_env_paths():
        if p.exists():
            return p
    return _PROJECT_ROOT / ".env"


def update_env_vars(updates: dict[str, str]) -> bool:
    """
    Atualiza ou adiciona variáveis no .env.
    Preserva comentários e variáveis existentes.
    updates: {"VAR_NAME": "valor", ...}
    """
    env_path = get_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)

    # Ler conteúdo atual
    lines: list[str] = []
    existing_keys: set[str] = set()
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                existing_keys.add(key)
            lines.append(line)

    # Atualizar valores
    keys_to_add = set(updates.keys()) - existing_keys
    keys_to_update = set(updates.keys()) & existing_keys

    new_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in keys_to_update:
                # Escapar valor se necessário (evitar quebras de linha no valor)
                val = str(updates[key]).replace("\n", " ").strip()
                new_lines.append(f"{key}={val}\n")
                keys_to_update.discard(key)
                i += 1
                continue
        new_lines.append(line + ("\n" if not line.endswith("\n") else ""))
        i += 1

    # Adicionar novas variáveis no final (antes de linhas em branco finais)
    if keys_to_add:
        # Inserir antes das últimas linhas em branco
        while new_lines and new_lines[-1].strip() == "":
            new_lines.pop()
        if new_lines and not new_lines[-1].endswith("\n\n"):
            new_lines.append("\n")
        for key in sorted(keys_to_add):
            val = str(updates[key]).replace("\n", " ").strip()
            new_lines.append(f"{key}={val}\n")
        new_lines.append("\n")

    env_path.write_text("".join(new_lines), encoding="utf-8")

    # Recarregar variáveis de ambiente para a sessão atual
    from dotenv import load_dotenv
    load_dotenv(env_path, override=True)
    return True


def update_env_from_oauth_client_json(data: dict) -> bool:
    """Extrai client_id e client_secret do JSON OAuth e atualiza o .env."""
    updates = {}
    for key in ("web", "installed"):
        if key in data:
            c = data[key]
            cid = (c.get("client_id") or "").strip()
            csec = (c.get("client_secret") or "").strip()
            if cid and csec:
                updates["GOOGLE_OAUTH_CLIENT_ID"] = cid
                updates["GOOGLE_OAUTH_CLIENT_SECRET"] = csec
                return update_env_vars(updates)
    return False


def update_env_from_service_account_json(saved_path: str) -> bool:
    """Atualiza GOOGLE_SERVICE_ACCOUNT_JSON no .env com o caminho do ficheiro guardado."""
    return update_env_vars({"GOOGLE_SERVICE_ACCOUNT_JSON": saved_path})


def update_env_from_sheet_id(sheet_id: str) -> bool:
    """Atualiza IG_SHEET_ID no .env."""
    return update_env_vars({"IG_SHEET_ID": sheet_id})


def update_env_from_gemini_key(api_key: str) -> bool:
    """Atualiza GEMINI_API_KEY no .env."""
    return update_env_vars({"GEMINI_API_KEY": api_key})

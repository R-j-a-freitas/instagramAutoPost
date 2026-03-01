"""
Autenticação da aplicação — login com email e password.
Utilizador padrão: clubtwocomma@gmail.com
Password definida na primeira utilização.
"""
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Optional

import streamlit as st

# Raiz do projeto
_AUTH_ROOT = Path(__file__).resolve().parent.parent
_AUTH_FILE = _AUTH_ROOT / ".auth.json"

# Utilizador padrão (se AUTH_ALLOWED_USERS não estiver definido)
DEFAULT_USER = "clubtwocomma@gmail.com"


def _get_allowed_emails() -> set[str]:
    """
    Lista de emails autorizados a fazer login.
    Define no .env: AUTH_ALLOWED_USERS=email1@x.com,email2@y.com
    Se vazio, usa apenas clubtwocomma@gmail.com.
    """
    raw = os.getenv("AUTH_ALLOWED_USERS", "").strip()
    if not raw:
        return {DEFAULT_USER}
    emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return emails if emails else {DEFAULT_USER}


def _is_auth_enabled() -> bool:
    """Auth pode ser desativada via AUTH_ENABLED=false (desenvolvimento)."""
    return os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")


def _load_auth_data() -> dict:
    """Carrega o ficheiro de credenciais."""
    if not _AUTH_FILE.exists():
        return {"users": {}}
    try:
        with open(_AUTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"users": {}}


def _save_auth_data(data: dict) -> None:
    """Guarda o ficheiro de credenciais."""
    with open(_AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _hash_password(password: str, salt: str) -> str:
    """Hash da password com salt."""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _user_exists(email: str) -> bool:
    """Verifica se o utilizador já tem password definida."""
    data = _load_auth_data()
    return email.lower().strip() in data.get("users", {})


def _set_password(email: str, password: str) -> None:
    """Define a password para o utilizador (primeira utilização)."""
    email = email.lower().strip()
    if not email or not password:
        raise ValueError("Email e password são obrigatórios.")
    if len(password) < 6:
        raise ValueError("A password deve ter pelo menos 6 caracteres.")
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    data = _load_auth_data()
    data.setdefault("users", {})[email] = {"salt": salt, "hash": pw_hash}
    _save_auth_data(data)


def _verify_password(email: str, password: str) -> bool:
    """Verifica se a password está correta."""
    email = email.lower().strip()
    data = _load_auth_data()
    user = data.get("users", {}).get(email)
    if not user:
        return False
    salt = user.get("salt", "")
    pw_hash = user.get("hash", "")
    return _hash_password(password, salt) == pw_hash


def _is_logged_in() -> bool:
    """Verifica se o utilizador está autenticado na sessão."""
    return st.session_state.get("auth_logged_in", False)


def _set_logged_in(email: str) -> None:
    """Marca o utilizador como autenticado."""
    st.session_state.auth_logged_in = True
    st.session_state.auth_email = email


def _logout() -> None:
    """Termina a sessão."""
    if "auth_logged_in" in st.session_state:
        del st.session_state.auth_logged_in
    if "auth_email" in st.session_state:
        del st.session_state.auth_email


def _render_login_form() -> None:
    """Renderiza o formulário de login ou definição de password."""
    st.markdown("## 🔐 Acesso à aplicação")
    allowed = _get_allowed_emails()
    default = DEFAULT_USER if DEFAULT_USER in allowed else next(iter(allowed), "")
    email = st.text_input("Email", value=default, key="auth_email_input")
    if not email:
        st.warning("Introduz o email.")
        st.stop()

    email = email.lower().strip()
    if email not in allowed:
        st.error("Este email não está autorizado a aceder à aplicação.")
        st.stop()

    user_exists = _user_exists(email)

    if user_exists:
        # Login
        st.caption("Introduz a password para entrar.")
        password = st.text_input("Password", type="password", key="auth_password_input")
        if st.button("Entrar", type="primary", key="auth_login_btn"):
            if password and _verify_password(email, password):
                _set_logged_in(email)
                st.rerun()
            else:
                st.error("Password incorreta.")
    else:
        # Primeira utilização — definir password
        st.info(f"Primeira utilização para **{email}**. Define a password de acesso.")
        password = st.text_input("Nova password", type="password", key="auth_new_password")
        password2 = st.text_input("Confirmar password", type="password", key="auth_new_password2")
        if st.button("Definir password e entrar", type="primary", key="auth_set_btn"):
            if not password:
                st.error("Introduz a password.")
            elif len(password) < 6:
                st.error("A password deve ter pelo menos 6 caracteres.")
            elif password != password2:
                st.error("As passwords não coincidem.")
            else:
                try:
                    _set_password(email, password)
                    _set_logged_in(email)
                    st.success("Password definida. A entrar...")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    st.stop()


def render_auth_sidebar() -> None:
    """Mostra o utilizador e botão Terminar sessão na sidebar (quando autenticado)."""
    if not _is_auth_enabled() or not _is_logged_in():
        return
    email = st.session_state.get("auth_email", "")
    st.caption(f"👤 {email}")
    if st.button("Terminar sessão", key="auth_logout_btn"):
        _logout()
        st.rerun()


def require_auth() -> None:
    """
    Exige autenticação. Se o utilizador não estiver autenticado,
    mostra o formulário de login e interrompe a execução (st.stop()).
    Chama no início de app.py e de cada página.
    """
    if not _is_auth_enabled():
        return
    if _is_logged_in():
        return
    _render_login_form()

"""Comptes DressMe : inscription, connexion, sessions et dossier de garde-robe propre à chaque utilisateur.

Stockage (dossier DRESSME_USERS_DIR, jamais dans git) :
  users.json      comptes : identifiant, nom, e-mail, sel + empreinte PBKDF2-SHA256 du mot de passe
  sessions.json   sessions : empreinte SHA-256 du jeton de session -> utilisateur, date d'expiration
  stores/<id>/    garde-robe de l'utilisateur (wardrobe.json, items/, emb/), même format que DRESSME_STORE
Le jeton de session n'est jamais enregistré en clair : seule son empreinte est gardée.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

PBKDF2_ROUNDS = 200_000
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(ValueError):
    """Erreur présentable à l'utilisateur (message en français)."""


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS).hex()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Users:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.users_file = self.root / "users.json"
        self.sessions_file = self.root / "sessions.json"
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- fichiers
    def _read(self, path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _write(self, path: Path, data) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def public(user: dict) -> dict:
        return {"id": user["id"], "name": user["name"], "email": user["email"]}

    # ---------------------------------------------------------------- comptes
    def register(self, name: str, email: str, password: str, import_from: Path | None = None) -> dict:
        name, email = (name or "").strip(), (email or "").strip().lower()
        if not name or len(name) > 60:
            raise AuthError("Indiquez votre nom (60 caractères au plus).")
        if not EMAIL_RE.match(email) or len(email) > 120:
            raise AuthError("Adresse e-mail invalide.")
        if len(password or "") < 8:
            raise AuthError("Le mot de passe doit contenir au moins 8 caractères.")
        with self._lock:
            users = self._read(self.users_file, [])
            if any(u["email"] == email for u in users):
                raise AuthError("Un compte existe déjà avec cette adresse e-mail.")
            salt = secrets.token_bytes(16)
            user = {"id": "u_" + secrets.token_hex(6), "name": name, "email": email, "salt": salt.hex(),
                    "hash": _hash_password(password, salt), "created": int(time.time())}
            first = not users
            users.append(user)
            self._write(self.users_file, users)
        self.store_of(user, import_from=import_from if first else None)
        return user

    def authenticate(self, email: str, password: str) -> dict:
        email = (email or "").strip().lower()
        user = next((u for u in self._read(self.users_file, []) if u["email"] == email), None)
        # même temps de calcul que l'adresse existe ou non (pas d'indice sur les comptes existants)
        salt = bytes.fromhex(user["salt"]) if user else b"0" * 16
        ok = hmac.compare_digest(_hash_password(password or "", salt), user["hash"] if user else "")
        if not user or not ok:
            raise AuthError("Adresse e-mail ou mot de passe incorrect.")
        return user

    def get(self, user_id: str) -> dict | None:
        return next((u for u in self._read(self.users_file, []) if u["id"] == user_id), None)

    # ---------------------------------------------------------------- sessions
    def new_session(self, user: dict) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            sessions = {k: v for k, v in self._read(self.sessions_file, {}).items() if v["exp"] > now}   # purge
            sessions[_token_digest(token)] = {"user": user["id"], "exp": now + SESSION_DAYS * 86400}
            self._write(self.sessions_file, sessions)
        return token

    def user_for_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        s = self._read(self.sessions_file, {}).get(_token_digest(token))
        if not s or s["exp"] < time.time():
            return None
        return self.get(s["user"])

    def drop_session(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            sessions = self._read(self.sessions_file, {})
            if sessions.pop(_token_digest(token), None) is not None:
                self._write(self.sessions_file, sessions)

    # ---------------------------------------------------------------- garde-robe
    def store_of(self, user: dict, import_from: Path | None = None) -> Path:
        """Dossier de garde-robe de l'utilisateur, créé au besoin. import_from : garde-robe existante recopiée
        (premier compte créé uniquement, pour ne pas perdre la garde-robe d'avant les comptes)."""
        d = self.root / "stores" / user["id"]
        if not (d / "wardrobe.json").exists():
            if import_from and (Path(import_from) / "wardrobe.json").exists():
                shutil.copytree(import_from, d, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("*.joblib", "llm_cache", "__pycache__"))
            else:
                (d / "items").mkdir(parents=True, exist_ok=True)
                (d / "emb").mkdir(parents=True, exist_ok=True)
                (d / "wardrobe.json").write_text("[]", encoding="utf-8")
        return d

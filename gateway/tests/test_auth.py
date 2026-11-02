"""Comptes : inscription, connexion, déconnexion et garde-robes séparées (chaque compte ne voit que ses pièces)."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_accounts_and_separate_wardrobes(tmp_path, monkeypatch):
    legacy = tmp_path / "ancienne"
    (legacy / "items").mkdir(parents=True)
    (legacy / "items" / "it_0001_raw.jpg").write_bytes(b"jpg")
    (legacy / "wardrobe.json").write_text(json.dumps([{"id": "it_0001", "name": "Blue shirt", "slot": "top", "type": "Shirts",
                                                       "colour": ["blue"], "image": "items/it_0001_raw.jpg"}]), encoding="utf-8")
    monkeypatch.setenv("DRESSME_AUTH", "1")
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from auth import Users
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "LEGACY_STORE", legacy)
    monkeypatch.setattr(g, "USERS", Users(tmp_path / "comptes"))
    monkeypatch.setattr(g, "_cache", {})
    a, b, anon = TestClient(g.app), TestClient(g.app), TestClient(g.app)

    assert anon.get("/wardrobe/items").status_code == 401 and anon.get("/files/items/it_0001_raw.jpg").status_code == 401
    assert anon.get("/auth/me").status_code == 401 and anon.get("/health").status_code == 200   # route publique

    r = a.post("/auth/register", json={"name": "Sawsen", "email": "Sawsen@Exemple.tn", "password": "motdepasse1"})
    assert r.status_code == 200 and r.json()["email"] == "sawsen@exemple.tn" and "dressme_session" in r.cookies
    assert [x["id"] for x in a.get("/wardrobe/items").json()] == ["it_0001"]          # 1er compte : reprend l'ancienne garde-robe
    assert a.get("/files/items/it_0001_raw.jpg").status_code == 200

    assert b.post("/auth/register", json={"name": "Amir", "email": "amir@exemple.tn", "password": "autremotdepasse"}).status_code == 200
    assert b.get("/wardrobe/items").json() == []                                       # 2e compte : garde-robe vide, à lui
    assert b.get("/files/items/it_0001_raw.jpg").status_code == 404                    # pas d'accès aux photos des autres
    assert a.get("/auth/me").json()["name"] == "Sawsen" and b.get("/auth/me").json()["name"] == "Amir"

    # validations et erreurs
    assert anon.post("/auth/register", json={"name": "X", "email": "amir@exemple.tn", "password": "12345678"}).status_code == 409
    assert anon.post("/auth/register", json={"name": "X", "email": "pas-un-email", "password": "12345678"}).status_code == 422
    assert anon.post("/auth/register", json={"name": "X", "email": "x@exemple.tn", "password": "court"}).status_code == 422
    assert anon.post("/auth/login", json={"email": "amir@exemple.tn", "password": "faux"}).status_code == 401
    assert anon.post("/auth/login", json={"email": "AMIR@exemple.tn", "password": "autremotdepasse"}).status_code == 200
    assert anon.get("/wardrobe/items").json() == []                                    # connecté sur le compte d'Amir
    assert anon.post("/auth/logout").status_code == 200 and anon.get("/wardrobe/items").status_code == 401

    stored = (tmp_path / "comptes" / "users.json").read_text(encoding="utf-8") + (tmp_path / "comptes" / "sessions.json").read_text(encoding="utf-8")
    assert "motdepasse1" not in stored and "autremotdepasse" not in stored            # ni mot de passe ni jeton en clair
    assert a.cookies.get("dressme_session") not in stored

import os, tempfile
import pytest

TEST_DB = os.path.join(tempfile.mkdtemp(), "fb.db")
os.environ.setdefault("DRESSME_DB", TEST_DB)


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    """app/agent.py charge .env avec override=True à l'import : le DRESSME_DB et les modèles par agent du .env local
    écraseraient ceux des tests (retours écrits dans la vraie base, modèles inattendus). On les refixe à chaque test."""
    monkeypatch.setenv("DRESSME_DB", TEST_DB)
    for agent in ("AGENDA", "EXPLAIN", "ASSISTANT", "JUDGE", "JUDGE2"):
        monkeypatch.delenv(f"LLM_MODEL_{agent}", raising=False)

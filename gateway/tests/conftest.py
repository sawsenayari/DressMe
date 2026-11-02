"""Les tests des objectifs tournent sans comptes (DRESSME_AUTH=0) ; test_auth.py active l'authentification."""
import pytest


@pytest.fixture(autouse=True)
def _sans_comptes(monkeypatch, request):
    if request.module.__name__.split(".")[-1] != "test_auth":
        monkeypatch.setenv("DRESSME_AUTH", "0")

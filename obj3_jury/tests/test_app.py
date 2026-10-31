import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.pop("APP_DATA", None)

import gradio as gr  # noqa: E402
import pytest  # noqa: E402

import app  # noqa: E402
from dressme.llm import MockLLM  # noqa: E402

RULES_ONLY = "Règles seules (gratuit, instantané)"
FULL = "Jury complet (règles + LLM + hybride)"
GOOD = ["d_shirt_white.jpg", "d_trouser_navy.jpg", "d_oxford_black.jpg"]
BAD = ["d_tee_white.jpg", "d_jeans_blue.jpg", "d_sandal_tan.jpg"]


def sd(i):
    return gr.SelectData(target=None, data={"index": i, "value": None, "selected": True})


def fake_llm(level):
    crit = {c: {"niveau": level, "raison": "x"} for c in ("couleurs", "formalite", "meteo", "coherence")}
    verdict = ["déconseillé", "à améliorer", "convient"][level]
    return MockLLM(lambda prompt: {"criteres": crit, "verdict": verdict, "raisons": ["r"], "_modele": "mock"})


@pytest.fixture(autouse=True)
def reset():
    app.LLM = None
    app._calls.clear()
    yield


def test_ui_builds_and_data_loaded():
    assert app.build_ui() is not None
    assert len(app.DESC) >= 30 and app.groups_available()


def test_catalogue_filters_by_category():
    items, ids = app.catalogue("Ladieswear", "chaussures")
    assert ids and all(app.DESC[i]["categorie"] == "chaussures" for i in ids) and len(items) == len(ids)


def test_add_remove_and_limits():
    _, ids = app.catalogue("Ladieswear", "*")
    sel = []
    for k in range(app.MAX_PIECES + 2):
        sel, items = app.on_add(sel, ids, sd(k))
    assert len(sel) == app.MAX_PIECES and len(items) == app.MAX_PIECES
    sel, _ = app.on_add(sel, ids, sd(0))                 # doublon ignoré
    assert len(sel) == app.MAX_PIECES
    sel, items = app.on_remove(sel, sd(0))
    assert len(sel) == app.MAX_PIECES - 1
    assert app.on_clear() == ([], [])


def test_rules_only_good_outfit():
    html, rows, det, rep, repg = app.evaluate(GOOD, 18, False, "travail", RULES_ONLY)
    assert "Convient" in html and len(rows) == 4 and rep == "" and repg == []


def test_bad_outfit_gets_repair():
    html, rows, det, rep, repg = app.evaluate(BAD, 20, True, "décontracté", RULES_ONLY)
    assert "Déconseillé" in html or "À améliorer" in html or "à améliorer" in html
    assert "Correction minimale" in rep and 1 <= len(repg) <= 2


def test_empty_selection_is_safe():
    assert app.evaluate([], 18, False, "travail", RULES_ONLY) == ("", [], "", "", [])


def test_full_jury_with_llm():
    app.LLM = fake_llm(1)
    html, rows, det, rep, repg = app.evaluate(GOOD, 18, False, "travail", FULL)
    assert rows[0][2] != "—" and rows[0][3] != "—"      # colonnes LLM et hybride remplies
    assert "Trois juges" not in det and "LLM" in html


def test_llm_failure_falls_back_to_rules():
    class Broken:
        def json_call(self, *a, **k):
            raise RuntimeError("quota")
    app.LLM = Broken()
    html, rows, det, rep, repg = app.evaluate(GOOD, 18, False, "travail", FULL)
    assert "indisponible" in det and rows[0][2] == "—"


def test_no_key_message_and_budget():
    _, _, det, _, _ = app.evaluate(GOOD, 18, False, "travail", FULL)
    assert "Aucune clé LLM" in det
    app.LLM = fake_llm(2)
    old = app.MAX_LLM_PER_HOUR
    app.MAX_LLM_PER_HOUR = 2
    try:
        app.evaluate(GOOD, 18, False, "travail", FULL)                 # consomme 2 appels
        _, _, det, _, _ = app.evaluate(GOOD, 18, False, "travail", FULL)
        assert "Plafond" in det
    finally:
        app.MAX_LLM_PER_HOUR = old

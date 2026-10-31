@echo off
REM Lance la passerelle (port 8000) pour le front. Depuis la racine du depot, venv active.
REM Variables facultatives : DRESSME_STORE (catalogue + images + emb), MAX_WARDROBE (defaut 40)
python -m uvicorn app:app --app-dir gateway --port 8000

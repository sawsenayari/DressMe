@echo off
REM Lance la passerelle (port 8000) pour le front. Depuis la racine du depot, venv active.
REM Variables facultatives : DRESSME_STORE (catalogue + images + emb), MAX_WARDROBE (defaut 40)
REM UTF-8 : les messages de l'Obj1 contiennent des emojis (sinon UnicodeEncodeError sur la console Windows)
set PYTHONIOENCODING=utf-8
python -m uvicorn app:app --app-dir gateway --port 8000

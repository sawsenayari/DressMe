@echo off
REM Lance la passerelle (port 8000) pour le front. Depuis la racine du depot, venv active.
REM Variables facultatives : DRESSME_STORE (catalogue + images + emb), MAX_WARDROBE (defaut 40)
REM UTF-8 : les messages de l'Obj1 contiennent des emojis (sinon UnicodeEncodeError sur la console Windows)
set PYTHONIOENCODING=utf-8
REM Objectif 6 (tenue du jour) sur le port 8006, dans sa propre fenetre et son venv (obj6_app\.venv, requirements.txt)
if exist obj6_app\.venv\Scripts\python.exe start "DressMe Obj6 (8006)" /D obj6_app .venv\Scripts\python.exe -m uvicorn app.main:app --port 8006
python -m uvicorn app:app --app-dir gateway --port 8000

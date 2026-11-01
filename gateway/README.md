# Passerelle DressMe (provisoire, avant l'objectif 6)
Un seul backend (port 8000) pour le front. Lancement depuis la racine du dépôt : `run_all.bat`
(ou `python -m uvicorn app:app --app-dir gateway --port 8000`), puis http://127.0.0.1:8000/docs.

| Route du front | Source | État |
|---|---|---|
| GET /wardrobe/items | catalogue de fiches (Obj5 `data/wardrobe.json`) | lecture seule |
| POST /wardrobe/items | Obj1 (photo -> ItemCard + emb) | OK si l'Obj1 se charge, sinon 501 |
| POST /compatibility/score | photo -> FashionCLIP -> Obj2 | OK si catalogue avec embeddings + modèle téléchargé |
| GET /gaps | Obj4 `gap_report.json` (liste ou contrat v1 `{gaps: [...]}`) | rapport statique (repli) ; slots Polyvore ramenés aux slots du front |
| GET/PUT /profile | Obj5 | OK (espace « attributs » tant que les embeddings manquent) |
| GET /outfits/today | Obj6 (HTTP, port 8006 : candidats + météo) -> jury Obj3 (règles) + Obj2 `/pairs` | OK si obj6_app est lancé, sinon 501 ; `compat01` null sans embeddings |
| POST /outfits/judge | Obj3 (règles + réparations) + Obj2 `/pairs` -> `OutfitJuryResult` | OK ; score = niveau x 50, juges visuel et LLM marqués « non disponible », `score01` absent sans embeddings |

Limites : `newOutfits` vaut 0 (à fournir par l'Obj4) ; la garde-robe est plafonnée à 40 articles (MAX_WARDROBE) car le
temps de calcul croît avec son carré (~3 s à 40 articles sur CPU) ; le premier appel de /compatibility/score télécharge FashionCLIP (~600 Mo).
Test : `python -m pytest -q gateway/tests` (catalogue synthétique, FashionCLIP remplacé ; le modèle Obj5 est réentraîné dans un dossier temporaire, pas dans `obj5_profil/models`). Lancer chaque dossier de tests séparément (ils s'appellent tous `tests`).

Obj6 : service séparé (ses chemins sont relatifs à `obj6_app` et son `.env` est chargé en mode override), lancé par `run_all.bat` ; la passerelle reste le seul backend du front (port 8000). Variable `OBJ6_URL` (défaut http://127.0.0.1:8006).

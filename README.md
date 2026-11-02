# DressMe — monorepo (projet ESPRIT, 6 objectifs)

Application de garde-robe intelligente : un front React parle à **une seule passerelle** (port 8000), qui appelle les six objectifs.

```
frontend (React + Vite, 5173) ──► gateway (FastAPI, 8000) ──┬─► obj1_reconnaissance  photo -> fiche ItemCard v1 + embedding   (en interne)
                                                            ├─► obj2_compat          compatibilité /compat et /pairs        (en interne)
                                                            ├─► obj3_jury            jury de tenues (règles)                (en interne)
                                                            ├─► obj4_manques         rapport de manques (gap_report.json)   (fichier)
                                                            ├─► obj5_profil          profil de style                        (en interne)
                                                            └─► obj6_app             tenue du jour (météo, agenda)          (HTTP, port 8006)
```

| Écran du front | Route de la passerelle | Objectifs |
|---|---|---|
| Today | `GET /outfits/today` | Obj6 → jury Obj3 + Obj2 |
| Wardrobe | `GET /wardrobe/items`, `POST /wardrobe/items` | catalogue, Obj1 |
| Outfit Studio | `POST /outfits/judge` | jury Obj3 + Obj2 |
| Does it match? | `POST /compatibility/score` | Obj2 |
| Gaps | `GET /gaps` | Obj4 |
| Style Profile | `GET/PUT /profile` | Obj5 |

Contrats communs : 7 slots (`top, bottom, onepiece, outer, footwear, bag, accessory`), fiche **ItemCard v1**, embeddings
**FashionCLIP** `patrickjohncyh/fashion-clip` (512, norme 1). Ports de référence : 8000 passerelle, 8002 Obj2, 8003 Obj3, 8005 Obj5, 8006 Obj6.

## 1. Installation (Windows, une seule fois)

Prérequis : Python 3.12, Node.js 18+, Git. Toutes les commandes se lancent dans `cmd`, depuis la racine du dépôt.

```bat
git clone https://github.com/sawsenayari/DressMe.git
cd DressMe
```

**Passerelle + objectifs 1 à 5** (un venv à la racine, ignoré par git) :

```bat
python -m venv venv
venv\Scripts\activate
pip install -r gateway\requirements.txt
```

**Objectif 6** (son propre venv : ses chemins sont relatifs à `obj6_app`) :

```bat
python -m venv obj6_app\.venv
obj6_app\.venv\Scripts\pip install -r obj6_app\requirements.txt
copy obj6_app\.env.example obj6_app\.env
```

Mettre sa propre clé Groq dans `obj6_app\.env` (facultatif : sans clé, l'agenda est lu par mots-clés). **Ne jamais commiter de `.env`.**

**Front** :

```bat
cd frontend
npm install
copy .env.example .env
cd ..
```

Derrière un proxy qui intercepte le HTTPS (erreur `CERTIFICATE_VERIFY_FAILED`) : `pip install truststore` puis ajouter
`--use-feature=truststore` aux commandes `pip install`.

## 2. Lancement

Fenêtre 1 (backend) :

```bat
venv\Scripts\activate
run_all.bat
```

`run_all.bat` ouvre l'Obj6 dans une seconde fenêtre (8006) et lance la passerelle (8000). Vérifier : http://127.0.0.1:8000/health

Fenêtre 2 (front) :

```bat
cd frontend
npm run dev
```

Ouvrir http://localhost:5173, puis **créer un compte** (ou se connecter) : chaque compte a sa propre garde-robe.
**Comptes** : à l'ouverture, l'écran de connexion s'affiche ; « Créer un compte » (nom, e-mail, mot de passe de
8 caractères au moins). Chaque compte a sa propre garde-robe, rangée dans `gateway\users_data\stores\<id>\` (hors git) ;
mots de passe hachés (PBKDF2-SHA256 salé), session dans un cookie HttpOnly de 30 jours. **Le tout premier compte créé
reprend la garde-robe existante** (dossier `DRESSME_STORE`) ; les suivants démarrent vides. Variables : `DRESSME_USERS_DIR`
(dossier des comptes), `DRESSME_AUTH=0` (désactive les comptes : garde-robe unique `DRESSME_STORE`, utilisé par les tests).

Au premier appel, FashionCLIP (~600 Mo) et SegFormer (~110 Mo) sont téléchargés depuis Hugging Face. Ensuite, `set HF_HUB_OFFLINE=1` évite tout accès réseau.

## 3. Garde-robe de départ avec de vraies photos

Le catalogue par défaut (`obj5_profil/data/wardrobe.json`, 423 fiches) n'a ni photos ni embeddings : compatibilité et images y sont indisponibles.
Pour partir de vraies pièces, utiliser le store de l'Obj1 (photos et embeddings) **sur une copie**, avant de créer le
premier compte (il reprend ce dossier) :

```bat
xcopy /E /I /Y obj1_reconnaissance\data\store %TEMP%\dressme_store
set DRESSME_STORE=%TEMP%\dressme_store
set DRESSME_PROFILE_MODEL=%TEMP%\style_model_demo.joblib
run_all.bat
```

À tester : Today (changer d'occasion), Wardrobe (« Ajouter une pièce » avec une photo), Outfit Studio (composer une tenue),
Does it match? (`frontend\public\images\cream-trousers.jpg`, puis `obj1_reconnaissance\data\store\items\it_0001_raw.jpg` pour un doublon), Gaps.
Style Profile : sous 18 pièces, l'Obj5 ne peut pas s'entraîner sur la garde-robe ; le profil est alors calculé avec son modèle
de référence (`obj5_profil/models/style_model.joblib`, lecture seule) et la page l'indique.

## 4. Tests

Lancer chaque dossier séparément (ils s'appellent tous `tests`), venv activé :

```bat
cd gateway && python -m pytest -q tests && cd ..
cd obj1_reconnaissance && python -m pytest -q && cd ..
cd obj2_compat && python -m pytest -q tests && python recette.py && cd ..
cd obj3_jury && python -m pytest -q && cd ..
cd obj4_manques && python -m pytest -q && cd ..
cd obj5_profil && python -m pytest -q tests && cd ..
cd obj6_app && .venv\Scripts\python -m pytest -q && cd ..
cd frontend && npx tsc --noEmit && npm run build && cd ..
```

## 5. Ce qui n'est pas dans git (trop lourd, régénérable ou personnel)

| Fichier / dossier | Rôle | Comment l'obtenir |
|---|---|---|
| `obj1_reconnaissance/data/inbox`, `tunisian*`, `database`, `general_training_items` | photos et jeux d'entraînement de l'Obj1 | demander à l'équipe Obj1 |
| `obj6_app/models/clip_visual_ft.pt` (336 Mo) | vision de l'Obj6 (`/api/analyze-photo` seulement) | demander à l'équipe Obj6 |
| `obj6_app/data/images`, `emb_clip*`, `feedback.db` | images et embeddings de l'Obj6, retours utilisateurs | régénérer (`obj6_app/README.md`) |
| photos + `emb/` du catalogue de 423 fiches | compatibilité sur le vrai catalogue | `store/` du passage Colab de l'Obj1 |
| `.env`, `venv`, `node_modules`, `dist` | secrets et environnements locaux | créés à l'installation |

## 6. Limites connues

- Ajout de photo (Obj1) sans Kaggle ni GPU : avec `GEMINI_API_KEY` dans `gateway/.env`, l'agent de l'Obj1 tourne en mode complet avec Gemini à la place de Qwen (photo analysée, contrôle par les voisins, RAG) ; sans clé, vote des voisins seul. Mesure sur 28 photos portées tunisiennes : couleur juste 89 % avec Gemini contre 29 % sans, pièces traditionnelles 7/8 contre 0/8 ; photos produit ≈ 90 % dans les deux cas. Limites de l'Obj1 : une pièce traditionnelle est toujours rangée en « robe / pièce unique », chaleur et formalité sont des valeurs par défaut (dictionnaire officiel absent).
- Jury (Obj3) : règles seules par défaut. Juge LLM dans Outfit Studio : `copy gateway\.env.example gateway\.env`,
  y mettre `LLM_API_KEY` (Groq) ou `GEMINI_API_KEY`, puis relancer `run_all.bat` (≈ 10 s par évaluation, 40 appels LLM / heure).
  Avec `GEMINI_API_KEY`, le juge visuel (Gemini) juge aussi la photo de la tenue (avis informatif, hors vote). Today reste en règles seules.
- L'Obj6 n'a que 6 slots (pas de `bag`, converti en `accessory`) et sa vision utilise open_clip, pas FashionCLIP.
- Le store de démo de l'Obj1 contient une erreur de reconnaissance signalée par l'Obj1 lui-même (`it_0010`, basket classée « onepiece »).
- Réparateur de tenues (Obj3) retiré de l'interface : sur 164 réparations testées, 59 % seulement donnaient une tenue jugée « convient » et sensée (corrections partielles, bottes ou manteau proposés par forte chaleur : les règles ignorent la chaleur des chaussures). Il reste dans la réponse de `POST /outfits/judge` (`repairs`).

## 7. Contribuer

1. Créer une branche : `git checkout -b prenom/sujet`.
2. Modifier, puis lancer les tests du dossier touché (section 4) et ceux de `gateway`.
3. Vérifier `git status` : aucun `.env`, aucun fichier de plus de 20 Mo.
4. Pousser la branche et ouvrir une Pull Request vers `main` ; un autre membre relit avant la fusion.

Détails par objectif : le `README.md` de chaque dossier ; passerelle : `gateway/README.md`.

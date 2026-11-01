# HANDOFF — DressMe (état au 1er novembre 2026)

Document de passation : où en est le projet, comment il fonctionne, comment le lancer et le tester, ce qui reste à faire.
Installation détaillée : `README.md` (racine). Détails de la passerelle : `gateway/README.md`.

## 1. En une phrase

Le front React parle à **une seule passerelle** (`gateway/app.py`, port 8000) qui appelle les six objectifs ; tout est
branché, testé et poussé sur `main` (GitHub `sawsenayari/DressMe`, dépôt **public**).

## 2. Qui fait quoi

| Écran du front | Route de la passerelle | Objectifs appelés |
|---|---|---|
| **Today** (tenue du jour) | `GET /outfits/today`, `POST /outfits/feedback` | Obj6 (tenue, météo) → jury Obj3 (règles) → compatibilité Obj2 |
| **Wardrobe** | `GET/POST /wardrobe/items`, `PUT/DELETE /wardrobe/items/{id}` | Obj1 (reconnaissance de la photo) |
| **Composer une tenue** (Outfit Studio) | `POST /outfits/judge` | jury Obj3 (règles + IA + photos en option) + Obj2 |
| **Does it match ?** | `POST /compatibility/score` | Obj2 (FashionCLIP + PairMLP) |
| **Pièces à ajouter** (Gaps) | `GET /gaps` | Obj4 (rapport statique `gap_report.json`) |
| **Mon profil de style** | `GET/PUT /profile` | Obj5 |

Ports : 8000 passerelle (seul backend du front), 8006 Obj6 (service HTTP lancé par `run_all.bat`), 5173 front (Vite).
Les autres objectifs sont appelés **en interne** par la passerelle (pas de serveur à lancer).
Contrats communs : 7 slots (`top, bottom, onepiece, outer, footwear, bag, accessory`), fiche **ItemCard v1**,
embeddings **FashionCLIP** `patrickjohncyh/fashion-clip` (512, norme 1).

## 3. Lancer (Windows, `cmd`, depuis la racine)

Fenêtre 1 (backend : passerelle 8000 + fenêtre Obj6 8006) :

```bat
venv\Scripts\activate
run_all.bat
```

(Sans `venv` à la racine : `set PATH=%CD%\obj3_jury\venv\Scripts;%PATH%` avant `run_all.bat`.)

Fenêtre 2 (front), puis ouvrir http://localhost:5173 :

```bat
cd frontend
npm run dev
```

Dans le front, le badge en haut à droite doit afficher **« 👗 Ma garde-robe »** (sinon : données de démonstration).

**Démo avec de vraies photos** (store de l'Obj1, 11 pièces), sur une copie pour ne pas toucher aux fichiers suivis par git :

```bat
xcopy /E /I /Y obj1_reconnaissance\data\store %TEMP%\dressme_store
set DRESSME_STORE=%TEMP%\dressme_store
set DRESSME_PROFILE_MODEL=%TEMP%\style_model_demo.joblib
set HF_HUB_OFFLINE=1
run_all.bat
```

### Clés (facultatives, jamais dans git)

`copy gateway\.env.example gateway\.env`, puis renseigner :

| Variable | Effet |
|---|---|
| `DRESSME_JURY_LLM=1` | active l'avis de l'IA et l'analyse des photos dans « Composer une tenue » |
| `LLM_API_KEY` (Groq) | juges texte de l'Obj3 |
| `GEMINI_API_KEY` | juges texte (prioritaire), **analyse des photos** (jury), **reconnaissance des photos ajoutées** (Obj1 en mode complet) |

Sans clé : tout fonctionne en règles seules et l'Obj1 reconnaît par « voisins » (moins précis). `obj6_app\.env` (clé Groq de
l'Obj6, facultative) est séparé. Vérifier avant chaque commit : aucun `.env`, aucune clé dans `git diff --cached`.

## 4. Tester

Automatique (chaque dossier séparément, venv activé) :

| Dossier | Commande (depuis ce dossier) | Attendu |
|---|---|---|
| `gateway` | `python -m pytest -q tests` | 11 réussis (≈ 6 min) |
| `obj1_reconnaissance` | `python -m pytest -q` | 30 |
| `obj2_compat` | `python -m pytest -q tests` puis `python recette.py` | 13 + recette PASS |
| `obj3_jury` | `python -m pytest -q` | 11 |
| `obj4_manques` | `python -m pytest -q` | 53 (+ 2 ignorés) |
| `obj5_profil` | `python -m pytest -q tests` | 11 |
| `obj6_app` | `.venv\Scripts\python -m pytest -q` | 17 |
| `frontend` | `npx tsc --noEmit` puis `npm run build` | sans erreur |

Les tests n'appellent jamais les vraies clés (Gemini / Groq remplacés par des faux) et n'écrivent ni dans le catalogue,
ni dans le modèle Obj5, ni dans le cache Obj1.

À la main (front) : **Today** → changer de contexte (la tenue change), « Autre proposition » (tenues différentes),
« Valider & Porter » ; **Wardrobe** → « Ajouter une pièce » (formulaire pré-rempli puis modifiable), recherche, filtres,
✏️ Modifier, 🗑️ Supprimer ; **Composer une tenue** → choisir haut / bas / chaussures, changer contexte et température ;
**Does it match ?** → `frontend\public\images\cream-trousers.jpg`, puis une photo déjà dans la garde-robe (doublon) ;
**Pièces à ajouter** ; **Mon profil de style**. Aucune erreur 500 ne doit apparaître (F12 → Console / Réseau).

## 5. Ce qui a été fait (principaux commits, du plus récent au plus ancien)

| Commit | Contenu |
|---|---|
| `362092a` | Today : tenue adaptée au contexte (la compatibilité ne fait plus gagner la même tenue partout), filtre unique « Contexte du jour » (5 choix dont sport et cérémonie), doublons écartés |
| `3201fe1` | Obj1 avec Gemini à la place de Qwen (sans GPU) ; ajout de photo en 3 temps (analyse → formulaire pré-rempli → enregistrer / annuler) |
| `b3907cc` | Textes en langage simple partout ; réparateur de tenues retiré de l'interface (59 % de réparations fiables) |
| `b424ac1`, `9f06d10` | Jury Obj3 : avis de l'IA et analyse des photos (Gemini) en option ; note nuancée |
| `dfe95d1`, `5667d54` | Wardrobe : mêmes champs à l'ajout et à la modification ; recherche, filtres, modifier, supprimer |
| `4c994ef` | Today : « Autre proposition », « Valider & Porter » reliés à l'Obj6 |
| `2818c68`, `b37d4be` | Profil Obj5 sous 18 pièces (modèle de référence) ; ajout de photo sans Kaggle ; guide d'installation |
| `19948b9`, `c89db3a` | Vrai jury dans Outfit Studio ; correctif FashionCLIP (transformers 5) ; vrais partenaires dans Does it match ? |
| `072e760`, `b7b04e6`, `a93794f` | Audit (tous les tests verts), intégration Obj6 et Obj1 |

## 6. Limites connues (à connaître avant de démontrer)

- **Catalogue par défaut sans photos** : `obj5_profil/data/wardrobe.json` (423 fiches) n'a ni images ni embeddings ;
  utiliser le store de démo de l'Obj1 (section 3) ou récupérer le `store/` du passage Colab de l'Obj1.
- **Obj1** : une pièce traditionnelle est toujours rangée en « robe / pièce unique » ; chaleur et formalité sont des
  valeurs par défaut (dictionnaire officiel jamais fourni). Mesure sur 28 photos portées : couleur juste 89 % avec Gemini
  (29 % sans). Le store de démo contient `it_0010`, une photo de baskets reconnue comme vêtement traditionnel (à corriger).
- **Obj3** : les règles ignorent la chaleur des chaussures (bottes acceptées à 35 °C en règles seules) ; le réparateur reste
  dans la réponse de `/outfits/judge` mais n'est pas affiché.
- **Obj6** : pas de mode budget ; 6 slots (le sac devient « accessoire ») ; sa vision utilise open_clip, pas FashionCLIP.
- **Obj4** : rapport statique (pas recalculé à chaque ajout de pièce).
- **Obj5** : moins de 18 pièces → profil calculé avec le modèle de référence (indiqué à l'écran).
- **Réseau** : derrière un proxy qui intercepte le HTTPS, `pip` et les API (Gemini, Groq, météo) échouent en
  `CERTIFICATE_VERIFY_FAILED` ; `pip install truststore` puis `--use-feature=truststore` pour pip.
- **Python global cassé** sur le poste d'origine (torch compilé pour NumPy 1.x) : toujours utiliser un venv.
- **npm audit** : 2 failles modérées dans `react-router` (correctif = passage en v7, non fait).

## 7. Prochaines étapes suggérées

1. Récupérer le `store/` complet de l'Obj1 (photos + `emb/` + `recognition_report.json`) pour le catalogue de 423 fiches.
2. Obj1 (avec Amir) : dictionnaire chaleur / formalité, rangement des pièces traditionnelles par sous-type (jebba = robe,
   chemise brodée = haut…).
3. Obj3 : prendre en compte la chaleur des chaussures dans les règles, puis réévaluer le réparateur avant de le réafficher.
4. Obj4 : recalculer le rapport de manques depuis la garde-robe réelle.
5. Obj6 : mode budget, sac en slot à part entière.
6. Mettre à jour `react-router` (v7) et vérifier l'application.

## 8. Règles d'équipe

Une branche par sujet (`prenom/sujet`), tests du dossier touché + `gateway`, `git status` sans `.env` ni fichier de plus de
20 Mo, Pull Request relue par un autre membre avant fusion dans `main`.

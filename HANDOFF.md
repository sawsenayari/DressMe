# HANDOFF — DressMe (état au 1er novembre 2026)

Document de passation : où en est le projet, comment il fonctionne, comment le lancer et le tester, ce qui reste à faire.
Installation détaillée : `README.md` (racine). Détails de la passerelle : `gateway/README.md`.

## 1. En une phrase

Le front React parle à **une seule passerelle** (`gateway/app.py`, port 8000) qui appelle les six objectifs ; tout est
branché, testé et poussé sur `main` (GitHub `sawsenayari/DressMe`, dépôt **public**).

## 2. Qui fait quoi

| Écran du front | Route de la passerelle | Objectifs appelés |
|---|---|---|
| **Tenue du jour** (`/`) | `GET /outfits/options`, `POST /outfits/recommend`, `POST /outfits/feedback` | Obj6 (agent de l'agenda, météo, 3 tenues) → jury Obj3 (règles) → compatibilité Obj2 |
| **Ma garde-robe** (`/wardrobe`) | `POST /wardrobe/crop`, `GET/POST /wardrobe/items`, `PUT/DELETE /wardrobe/items/{id}` | découpage de l'Obj6 (amélioration de la photo) puis Obj1 (reconnaissance) |
| **Composer une tenue** (`/studio`) | `POST /outfits/judge` | jury Obj3 (règles + IA en option) + Obj2 |
| **Ça va avec ?** (`/match`) | `POST /compatibility/score` | Obj2 (FashionCLIP + PairMLP) |
| **Pièces à ajouter** (`/gaps`) | `GET /gaps`, `GET /gaps/shopping` | Obj4 (candidats IA, proxies, comptage des tenues) + Obj2 (scores) |
| **Mon style** (`/profile`) | `GET /profile`, `GET /profile/recommendations` | Obj5 (profil, pièces suggérées) |

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

**Comptes** : à l'ouverture, l'écran de connexion s'affiche ; « Créer un compte » (nom, e-mail, mot de passe de
8 caractères au moins). Chaque compte a sa propre garde-robe, rangée dans `gateway\users_data\stores\<id>\` (hors git) ;
mots de passe hachés (PBKDF2-SHA256 salé), session dans un cookie HttpOnly de 30 jours. **Le tout premier compte créé
reprend la garde-robe existante** (dossier `DRESSME_STORE`) ; les suivants démarrent vides. Variables : `DRESSME_USERS_DIR`
(dossier des comptes), `DRESSME_AUTH=0` (désactive les comptes : garde-robe unique `DRESSME_STORE`, utilisé par les tests).

**Garde-robe de départ avec de vraies photos** (store de l'Obj1), à fixer **avant** de créer le premier compte, sur une
copie pour ne pas toucher aux fichiers suivis par git :

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
| `DRESSME_JURY_LLM=1` | active l'avis de l'IA dans « Composer une tenue » (`DRESSME_JURY_VISUAL=1` : juge visuel Gemini, hors interface) |
| `LLM_API_KEY` (Groq) | juges texte de l'Obj3 |
| `GEMINI_API_KEY` | juges texte (prioritaire), **reconnaissance des photos ajoutées** (Obj1 en mode complet) |
| `HF_TOKEN` | jeton gratuit Hugging Face (lecture) pour l'**essayage réaliste** ; sans jeton, quota anonyme très court |

Sans clé : tout fonctionne en règles seules et l'Obj1 reconnaît par « voisins » (moins précis). `obj6_app\.env` (clé Groq de
l'Obj6, facultative) est séparé. Vérifier avant chaque commit : aucun `.env`, aucune clé dans `git diff --cached`.

## 4. Tester

Automatique (chaque dossier séparément, venv activé) :

| Dossier | Commande (depuis ce dossier) | Attendu |
|---|---|---|
| `gateway` | `python -m pytest -q tests` | 17 réussis (≈ 9 min) |
| `obj1_reconnaissance` | `python -m pytest -q` | 30 |
| `obj2_compat` | `python -m pytest -q tests` puis `python recette.py` | 13 + recette PASS |
| `obj3_jury` | `python -m pytest -q` | 11 |
| `obj4_manques` | `python -m pytest -q` | 53 (+ 2 ignorés) |
| `obj5_profil` | `python -m pytest -q tests` | 11 |
| `obj6_app` | `.venv\Scripts\python -m pytest -q` | 17 |
| `frontend` | `npx tsc --noEmit` puis `npm run build` | sans erreur |

Les tests n'appellent jamais les vraies clés (Gemini / Groq remplacés par des faux) et n'écrivent ni dans le catalogue,
ni dans le modèle Obj5, ni dans le cache Obj1.

À la main (front) : **Today** → Femme / Homme, ville, agenda en français, arabe ou anglais (exemples cliquables), envies,
« Explications de la styliste IA », « Proposer des tenues » ; vérifier la ligne de contexte, les avertissements,
« Orchestration » (durée des étapes), puis 👍 / 🔀 / 👎 sur une tenue ; **Wardrobe** → « Ajouter une pièce » (photo portée : choix du vêtement ; fond chargé : photo détourée ; puis formulaire pré-rempli et modifiable), recherche, filtres,
✏️ Modifier, 🗑️ Supprimer ; **Composer une tenue** → choisir haut / bas / chaussures, changer contexte et température ;
**Does it match ?** → `frontend\public\images\cream-trousers.jpg`, puis une photo déjà dans la garde-robe (doublon) ;
**Pièces à ajouter** ; **Mon profil de style** → filtrer les pièces suggérées par catégorie et Femme / Homme,
« Recalculer ». Aucune erreur 500 ne doit apparaître (F12 → Console / Réseau).

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
- **Découpage (module de l'Obj6, dans la passerelle)** : SegFormer `mattmdjaga/segformer_b2_clothes` + rembg `u2netp`
  (téléchargés au premier usage, 4,6 Mo pour u2netp), seulement sur clic « Améliorer la photo » : « Analyser la photo »
  envoie la photo entière à l'Obj1 (découpeur de l'Obj1 en mode « none », sans détourage). Bon sur les photos
  portées occidentales et les photos à plat ; approximatif sur les tenues traditionnelles portées (l'utilisateur peut
  garder la photo d'origine). Photo produit sur fond clair : pas d'étape.
- **Obj1** : une pièce traditionnelle est toujours rangée en « robe / pièce unique » ; chaleur et formalité sont des
  valeurs par défaut (dictionnaire officiel jamais fourni). Mesure sur 28 photos portées : couleur juste 89 % avec Gemini
  (29 % sans). Le store de démo contient `it_0010`, une photo de baskets reconnue comme vêtement traditionnel (à corriger).
- **Obj3** : les règles ignorent la chaleur des chaussures (bottes acceptées à 35 °C en règles seules) ; le réparateur reste
  dans la réponse de `/outfits/judge` mais n'est pas affiché.
- **Obj6** : pas de mode budget ; 6 slots (le sac devient « accessoire ») ; sa vision utilise open_clip, pas FashionCLIP.
- **Obj4** : analyse calculée sur la garde-robe (candidats de l'IA Gemini/Groq, sinon liste de pièces de base). Chaque
  candidat est simulé par une pièce de même catégorie (proxy de l'Obj4) ; seuils 0,70 / 0,40 non calibrés. Chiffre
  affiché et classement : comptage de l'Obj4 avec chaque association tranchée au score 0,5 de l'Obj2 (ajout de la
  passerelle) ; les bornes prudente / optimiste suivent la formule de l'Obj4. Comptage corrigé dans la passerelle :
  chaque veste ou sac compatible donne une tenue différente (l'Obj4 plafonnait à « avec ou sans », si bien qu'une veste
  ou un sac de plus ne pouvait jamais rien ajouter). « 🔎 Recherche en ligne » (requête Tavily « [pièce] buy online »)
  demande `DRESSME_TAVILY_API_KEY` dans `gateway/.env`.
  `gap_report.json` ne sert plus que d'exemple quand la garde-robe n'a pas de photos.
- **Essayage réaliste** (« Aperçu de la tenue » de Composer une tenue et Tenue du jour, bouton « 📸 Essayage réaliste »,
  `POST /outfits/tryon`) : essayage virtuel par diffusion sur des Spaces Hugging Face gratuits (`gradio_client`). Les
  photos des pièces sont « portées » par un mannequin photo (`gateway/assets/tryon/`, femme ou homme selon les pièces) :
  bas (« Lower-body ») ou robe (« Dress ») d'abord avec OOTDiffusion, puis haut ou veste avec IDM-VTON (OOTDiffusion
  donne des taches sur une image déjà retouchée). Photos posées sur fond blanc au format 3:4 avant l'envoi. Chaussures et
  accessoires sont montrés à côté. ≈ 20-30 s par pièce ; résultat en cache dans `tryon/` de la garde-robe ; si le quota
  GPU gratuit coupe au milieu, la pièce déjà portée est montrée (résultat partiel, non mis en cache). Les Spaces sont
  appelés par leur adresse directe (`*.hf.space`), ce qui marche aussi avec `HF_HUB_OFFLINE=1`. Limites : une jupe ou un
  short prend la longueur du pantalon du mannequin ; le quota gratuit d'un compte Hugging Face ne permet que quelques
  essayages par jour. Les photos partent chez Hugging Face.
- **Obj5** : profil et suggestions utilisent la taxonomie de référence (16 styles appris sur 423 fiches, espace
  d'attributs, pas FashionCLIP faute d'embeddings du catalogue) ; palette = part des pièces par couleur ; suggestions
  sans photos (catalogue de référence sans images) ; orientation Économie non évaluable sans prix.
- **Réseau** : derrière un proxy qui intercepte le HTTPS, `pip` et les API (Gemini, Groq, météo) échouent en
  `CERTIFICATE_VERIFY_FAILED` ; `pip install truststore` puis `--use-feature=truststore` pour pip.
- **Python global cassé** sur le poste d'origine (torch compilé pour NumPy 1.x) : toujours utiliser un venv.
- **npm audit** : 2 failles modérées dans `react-router` (correctif = passage en v7, non fait).

## 7. Prochaines étapes suggérées

1. Récupérer le `store/` complet de l'Obj1 (photos + `emb/` + `recognition_report.json`) pour le catalogue de 423 fiches.
2. Obj1 (avec Amir) : dictionnaire chaleur / formalité, rangement des pièces traditionnelles par sous-type (jebba = robe,
   chemise brodée = haut…).
3. Obj3 : prendre en compte la chaleur des chaussures dans les règles, puis réévaluer le réparateur avant de le réafficher.
4. Obj4 : calibrer les seuils de compatibilité et remplacer les proxies par une vraie représentation des pièces proposées.
5. Obj6 : mode budget, sac en slot à part entière.
6. Mettre à jour `react-router` (v7) et vérifier l'application.

## 8. Règles d'équipe

Une branche par sujet (`prenom/sujet`), tests du dossier touché + `gateway`, `git status` sans `.env` ni fichier de plus de
20 Mo, Pull Request relue par un autre membre avant fusion dans `main`.

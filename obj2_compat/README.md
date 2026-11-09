# DressMe - service de compatibilité (objectif 2)

Lancer (CPU suffit) :
    pip install -r requirements.txt
    uvicorn app:app --port 8002
    python -m pytest -q tests          # 10 tests

## POST /compat
Entrée : {"candidate": Item, "wardrobe": [Item, ...]}  (garde-robe >= 2 articles)
Item   : {"id": "...", "embedding": [512 floats FashionCLIP sur image_crop], "category": "tops" | "slot": "top"}
Sortie : {"rank100", "score01", "verdict", "partners": [2 meilleurs], "duplicate": {id, similarity, pct, is_duplicate}, "model"}
- rank100 = % de 300 articles Polyvore aléatoires de même catégorie que le candidat qui scorent MOINS bien
  que lui avec la même garde-robe (50 = hasard). Verdict : >=70 compatible, 40-69 moyenne, <40 peu compatible.
- doublon : article le plus semblable ; is_duplicate si >= 90e centile des paires aléatoires de même catégorie.

## POST /pairs
Entrée : {"a": [Item...], "b": [Item...]}   Sortie : {"scores01": [[...]], "verdicts": [[...]], "thresholds": {...}} (len(a) x len(b))
- score01 d'une paire = centile du score de la paire parmi les scores (a, 300 références de la catégorie de b), moyenné dans les deux sens.
- Verdict d'une paire : >= 0,75 « va bien » ; 0,35 à 0,75 « moyen » ; < 0,35 « peu probable ».
  Calibrage (31/10/2026) sur 8 000 paires de validation Polyvore propres (1 107 tenues ; 4 000 vraies paires d'une même tenue contre 4 000 paires où b est remplacé par un article de même catégorie d'une autre tenue) :
  AUC 0,74 [0,73 ; 0,75] ; part de vraies paires = 21 % sous 0,35, 42 % entre les deux seuils, 70 % au-dessus de 0,75.
  Attention : une paire « aléatoire » n'est pas forcément incompatible ; ces pourcentages mesurent la ressemblance avec de vraies paires de tenues, pas une vérité de goût.
  Seuils à reconfirmer sur le jeu réel commun avec l'équipe.

## Catégories : accessories, all-body, bags, bottoms, hats, jewellery, outerwear, scarves, shoes, sunglasses, tops
"slot" -> catégorie par défaut : top=tops, bottom=bottoms, onepiece=all-body, outer=outerwear, footwear=shoes, bag=bags, accessory=accessories
(utiliser "category" pour jewellery, hats, scarves, sunglasses).

## Limites connues
- Le service reçoit des embeddings : le calcul FashionCLIP (patrickjohncyh/fashion-clip) se fait en amont, sur image_crop.
- Modèle image seule (3 graines), entraîné sur Polyvore ; test réel pilote : 1 garde-robe, Spearman +0,44 [+0,05 ; +0,75].
- Latence CPU : ~0,3 s par /compat ; ~3 ms par paire de /pairs.

## v1.3 – intégration avec les fiches ItemCard (objectifs 1, 3, 5, 6)
- Lancer avec le dossier des fiches : `DRESSME_STORE=/chemin/fiches uvicorn app:app --port 8002`
  (le dossier contient les `*.json` des fiches et `emb/<id>.npy`).
- `/compat` et `/pairs` acceptent, pour chaque article : un **identifiant** (la fiche est cherchée dans DRESSME_STORE),
  ou une **fiche complète**, dont `embedding` est soit un vecteur de 512 nombres, soit un **chemin .npy** (relatif à DRESSME_STORE).
- `partners` renvoie `{id, category, pair_score01}` (contrat ItemCard / compat v1).
- Fiche sans embedding -> erreur 422 explicite. Calculer les embeddings avec `python embed_cards.py DOSSIER_DES_FICHES`
  (FashionCLIP, image_crop sinon image ; NON testé avec le vrai modèle dans mon environnement).
- Recette : 11 PASS, 0 FAIL, 1 SKIP (le rejeu du test réel demande real_embeddings.npz et resultat_5B.csv) ; 13 tests automatiques.

## Styliste IA (couche LLM)
Conseil sur photo qui explique le score sans le modifier : voir `stylist/README.md`
(prompts versionnés, garde-fous, évaluation v1 / v2). 7 tests de plus (`tests/test_stylist.py`).

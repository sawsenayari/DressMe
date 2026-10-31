---
title: DressMe
emoji: 👗
colorFrom: indigo
colorTo: pink
sdk: gradio
sdk_version: 6.31.0
app_file: app.py
pinned: false
---

# DressMe — interface web du jury de tenues

Compose une tenue avec de vraies photos, choisis la météo et l'occasion : trois juges (règles, LLM, hybride) et un arbitre donnent un verdict par critère (couleurs, formalité, météo, cohérence), puis un réparateur propose de changer **une** pièce.

Interface : **Gradio** (événements par composant, pas de rechargement du script à chaque clic ; galerie d'images cliquable ; API générée automatiquement).

## 1. Essayer tout de suite (données fictives, sans clé)
```bash
pip install -r requirements.txt
python app.py            # http://127.0.0.1:7860  (mode démo : tuiles de couleur)
python -m pytest -q      # 9 tests
```

## 2. Avec tes vraies photos (Colab)
Ouvre `Deploy_DressMe.ipynb` dans Colab et lance les cellules dans l'ordre :
1. configuration (Drive, dézip, clés facultatives) ;
2. installation ;
3. contrôle des données ;
4. `prepare_app_data.py` : copie les photos décrites, les descriptions CLIP et les tenues annotées dans `app_data/` ;
5. lancement : un lien public **temporaire** apparaît.

Prérequis côté Drive : `dressme_data/` avec `wardrobe/`, `truth.json`, `perception_clip.json` (toutes les pièces décrites), et si possible `survey2/`, `survey3/` annotés (exemples du prompt LLM).

## 3. Déploiement durable (Hugging Face Spaces)
La dernière cellule du notebook crée un Space Gradio **privé**, envoie les fichiers et enregistre les clés comme secrets du Space. Ensuite : Space > Settings pour contrôler les secrets, puis attendre la fin du build.

## Variables d'environnement
| Variable | Rôle |
|---|---|
| `APP_DATA` | dossier de données (défaut `./app_data`, sinon mode démo) |
| `GEMINI_API_KEY` | active le jury complet (Gemini, gratuit) |
| `LLM_API_KEY` | clé Groq, repli si Gemini est indisponible |
| `GEMINI_MODELS` | modèles Gemini séparés par des virgules |
| `MAX_LLM_PER_HOUR` | plafond d'appels LLM par heure (défaut 40) |

Sans clé, l'application marche avec les règles seules.

## Sécurité
- Clés uniquement dans les variables d'environnement ou les Secrets (jamais dans le code ni le dépôt).
- Aucun texte libre n'est envoyé au LLM : seulement des descriptions structurées et des valeurs choisies dans des listes.
- Réponses du LLM validées par le code (niveaux 0 à 2, critères obligatoires) ; en cas d'échec, repli sur les règles.
- Plafond d'appels par heure pour protéger le quota gratuit ; aucune donnée utilisateur n'est enregistrée.
- Palier gratuit Gemini : le contenu envoyé peut être réutilisé par Google. Ne mets pas de photos personnelles.
- **Licence des photos** : les images viennent du dataset H&M. Je n'ai pas vérifié si leur redistribution publique est permise. Garde le Space **privé** tant que ce n'est pas clarifié.

## Limites connues
- Prototype validé sur 40 à 60 tenues et un seul évaluateur : aucun juge n'est significativement meilleur qu'un autre.
- Environ 23 % des pièces sont mal décrites par la perception.
- Règle non couverte : « chaussures de sport » ne sont pas pénalisées au travail (seulement « baskets »), donc le réparateur peut en proposer.
- L'interface ne permet pas encore d'ajouter ses propres photos (il faudrait CLIP à l'exécution).

## Arborescence
```
app.py                  interface Gradio
prepare_app_data.py     prépare app_data/ depuis dressme_data/
dressme/                jury : règles (politique), LLM v3, hybride, arbitre, réparateur
data/demo_wardrobe.json données fictives du mode démo
tests/test_app.py       9 tests (sans réseau ni clé)
Deploy_DressMe.ipynb    notebook de lancement et de déploiement
```

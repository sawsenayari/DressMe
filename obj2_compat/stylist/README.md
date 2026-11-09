# Styliste IA — couche LLM de l'Obj2

Le score de compatibilité vient du modèle PairMLP (mesuré, reproductible). Le LLM **explique** ce score à partir de la
photo ; il n'a jamais le droit de noter. Appelé par `POST /compatibility/advice` (gateway), uniquement sur clic.

```
photo + score PairMLP ──► build_facts ──► prompt versionné ──► Gemini vision (JSON) ──► schéma Pydantic ──► garde-fous ──► conseil
                          (noms nettoyés)   (prompts.py)          (llm.py)              (schema.py)          (guard.py)
                                                                       └── JSON invalide : 1 relance avec l'erreur ──┘
                                                         trace JSONL : version, modèle, latence, jetons, corrections
```

| Fichier | Rôle |
|---|---|
| `config.py` | hyperparamètres justifiés (température 0,3, top_p 0,9, max_tokens 400, timeout 20 s, 1 relance), surchargeables par variables d'environnement |
| `prompts.py` | registre des prompts versionnés (`compat-conseil-v1` gelée, `compat-conseil-v2` par défaut) et journal des changements |
| `schema.py` | contrat de sortie : `RawAdvice` (attendu du LLM) et `Advice` (renvoyé au front) |
| `guard.py` | entrée : noms de pièces suspects neutralisés ; sortie : ids et chiffres absents des faits retirés, longueur bornée |
| `llm.py` | client Gemini (API compatible OpenAI), mode `json_object`, repli flash-lite → flash, mesure latence et jetons |
| `advisor.py` | orchestration + réparation du JSON + trace |
| `evaluate.py` | banc d'évaluation des versions de prompt sur `eval_cases.json` |

## Choix du LLM
Gemini 3.5 flash-lite (repli : flash) : multimodal (il faut **voir** la photo), mode JSON natif, quota gratuit, ~1 à 1,5 s.
Pas de fine-tuning : la tâche est une reformulation ancrée sur des faits ; un prompt structuré + validation par le code
suffit et reste vérifiable. La seule partie entraînée de l'Obj2 est la tête PairMLP du score.

## Techniques de prompt engineering (v2)
rôle borné dans le message système · ancrage sur des faits JSON entre balises `<faits>` · séparation données / consignes
(anti-injection) · étapes de raisonnement guidées sans les écrire · contraintes numérotées · 2 exemples few-shot
(cas favorable, cas défavorable + doublon) · sortie JSON imposée et validée.

## Sécurité
- Noms de pièces = données utilisateur : nettoyés, et remplacés par le type s'ils contiennent des formulations de consigne.
- Sortie jamais crue sur parole : schéma Pydantic, ids hors listes retirés, phrase supprimée si elle cite une note absente des faits.
- Clé `GEMINI_API_KEY` côté serveur seulement (`.env`, hors git) ; photo envoyée seulement sur clic ; la trace ne contient ni photo ni clé.
- Panne ou quota : pas de conseil, le score reste affiché.

## Évaluation
```
python -m stylist.evaluate                 # vrai Gemini (clé de l'environnement, sinon gateway/.env) -> reports/stylist_eval.json
python -m stylist.evaluate --fake          # hors ligne, vérifie le banc
```
6 cas figés (`stylist-eval-v1`) : compatible, moyen, peu compatible, doublon, injection dans un nom, sans partenaire.
Métriques mesurées sur la sortie **brute** du LLM (qualité du prompt) et **finale** (après garde-fous).

Résultat réel (09/11/2026, température 0,3) :

| Métrique | v1 | v2 |
|---|---|---|
| JSON valide / schéma valide | 100 % | 100 % |
| Aucune pièce ni note inventée (brut) | 100 % | 100 % |
| ≤ 45 mots | 100 % | 100 % |
| Texte lisible, sans id technique | 67 % (67 à 83 % sur 3 runs) | **100 %** (3 runs sur 3) |
| Doublon annoncé en premier | 100 % | 100 % |
| Honnête si peu compatible | 100 % | 100 % |
| Résiste à l'injection | 100 % | 100 % |
| Latence médiane | 1,0 s | 1,2 s |
| Jetons moyens | 1 783 | 2 017 (+13 %) |

Limites : 6 cas seulement (à agrandir), métriques par règles (pas de juge humain sur la qualité du conseil), une seule
exécution par version (température 0,3 : la v1 a donné 67 %, 83 % puis 67 % de textes lisibles sur trois runs).
Si aucun appel n'aboutit (clé invalide, quota), le banc s'arrête avec l'erreur et n'écrase pas le dernier rapport.

Tests : `python -m pytest -q tests/test_stylist.py` (7 tests, client simulé).

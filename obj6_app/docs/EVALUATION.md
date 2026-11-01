# Évaluation des composants LLM — protocole

Commande unique : `python -m training.eval_all` (ou chaque évaluation séparément). Les rapports sont écrits dans `reports/` (JSON + `evaluation_summary.md`).
Le quota gratuit de Groq limite le débit : l'agent attend automatiquement (erreur 429) ; compte quelques minutes par évaluation.

| # | Évaluation | Question posée | Méthode | Commande |
|---|---|---|---|---|
| 1 | Agent agenda | Comprend-il l'occasion et la formalité d'un texte libre ? | Jeu étiqueté (38 phrases FR / AR / EN / mixte, hors exemples du prompt), ablation règles / LLM / LLM+RAG | `python -m training.eval_agent` |
| 2 | LLM-as-a-judge | Les explications de la styliste sont-elles pertinentes, fidèles, honnêtes, claires ? | Un LLM juge note 4 critères (1-5) avec un barème ; **contrôle** : une explication d'un autre contexte doit être moins bien notée | `python -m training.eval_judge` |
| 3 | Assistant à outils | Appelle-t-il les bons outils, dans le bon ordre, avec de bons arguments, et sa réponse reste-t-elle fidèle ? | Vérifications programmatiques + juge de fidélité (groundedness) ; mode local ou `--mcp` | `python -m training.eval_tools` |

## 1. Agent agenda
- Métriques : exactitude de l'occasion avec **intervalle de confiance de Wilson à 95 %** (n est petit), erreur moyenne sur la formalité, part de réponses réellement produites par le LLM, exactitude par langue, liste des erreurs.
- Plusieurs occasions sont acceptées quand la situation est ambiguë (ex. visite chez les parents).
- Garde-fou : le script retire toute phrase présente dans le prompt (fuite de test). Dans l'ancienne version, 2 phrases sur 18 étaient dans ce cas : les anciens chiffres étaient légèrement optimistes.
- Lecture : si « Traité par le LLM » est inférieur à n, les repli par mots-clés faussent la comparaison ; regarder `accuracy_on_llm_answered`.

## 2. LLM-as-a-judge
| Critère | Ce qu'il mesure |
|---|---|
| pertinence | S'appuie sur la vraie météo et la vraie occasion |
| fidélité | N'invente aucun vêtement hors liste |
| honnêteté | Signale les alertes, n'en invente pas |
| clarté | Une phrase courte, français correct |

Un **panel de deux juges** (`LLM_MODEL_JUDGE`, `LLM_MODEL_JUDGE2`) note chaque explication ; le rapport donne les notes de chaque juge et leur **accord** (Spearman). Procédure complète : `python -m training.check_llm`, `python -m training.eval_judge`, `python -m training.label_cases` (tu notes 15 cas sans voir les notes des juges), puis `python -m training.eval_judge --compare reports/judge_cases.csv`.

Biais connus du juge et parades :
| Biais | Parade utilisée |
|---|---|
| Auto-préférence (un modèle note mieux son propre style) | Juge principal d'une **autre famille** (Qwen) que le générateur (gpt-oss) ; le juge 2 (même famille) sert seulement à mesurer l'accord |
| Préférence pour les textes longs | Barème explicite, critère de brièveté séparé, vérification programmatique des 25 mots |
| Indulgence générale | **Contrôle négatif** : explications d'un autre contexte ; mesure de la discrimination du juge (part des cas où la bonne explication gagne) |
| Fiabilité inconnue | Notes humaines (`label_cases`) puis corrélation de Spearman juge / humain ; plus l'accord entre les deux juges |

## 3. Assistant à outils
Métriques (chacune avec intervalle de confiance) : tous les outils appelés, `get_weather` avant `recommend_outfits`, arguments valides (occasion dans la liste, température numérique, genre), occasion attendue, **température passée = température reçue de l'outil** (détecte les chiffres inventés), réponse fidèle aux résultats de l'outil (juge). Durée moyenne par scénario.

## Limites à citer
8 scénarios et 38 phrases : les intervalles de confiance sont larges. Étiquettes écrites par l'auteur. Le juge est un LLM : la corrélation avec des notes humaines doit être mesurée avant de lui faire confiance.

## Choix du modèle par agent
`python -m training.eval_models` compare les modèles disponibles (gpt-oss-20b, gpt-oss-120b, qwen3.8-27b, allam-2-7b) sur le jeu de l'agent agenda : exactitude avec intervalle de confiance, erreur de formalité, part de réponses sans repli, secondes par phrase. Le modèle recommandé est celui qui répond dans au moins 90 % des cas avec la meilleure exactitude. `allam-2-7b` (spécialisé arabe, contexte de 4096 jetons) est le candidat à tester pour l'arabe et le dialecte.

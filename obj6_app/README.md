# DressMe v2 — objectif 6 + vision + RAG + feedback
1. Données  : `python -m training.prepare_data` (nettoyage → data/clean.csv, data/data_report.json)
2. Vision   : `pip install -r requirements-ml.txt` puis `python -m training.vision` (+ `--finetune --epochs 3 --unfreeze 2`) → models/vision_metrics.json
3. Contexte : `python -m training.train --styles data/styles.csv` (+ `--feedback data/feedback.db` pour intégrer les 👍/👎)
4. Agent    : `python -m training.eval_agent` (règles vs LLM vs LLM+RAG) ; debug : /api/parse?text=… /api/rag?q=…
5. Serveur  : `uvicorn app.main:app --reload` (dans le monorepo DressMe : `--port 8006`, lancé par `run_all.bat` ; le port 8000 est celui de la passerelle) ; Docker : `docker build --build-arg ML=1 -t dressme .` ; tests : `pytest`
6. Découpe   : `python -m training.crop_dataset --limit 1500` (catalogue) ; les photos envoyées dans l'interface sont découpées à la volée
7. Évaluation: `python -m training.eval_agent` · `python -m training.eval_rag` · `pytest`
8. MCP       : `python -m app.mcp_server` (serveur) ; l'assistant peut l'utiliser via la case « Passer par MCP » — voir docs/ARCHITECTURE.md
ATTENTION : après mise à jour, relance `python -m training.train --styles data/styles.csv` (les variables du modèle ont changé).
9. Évaluations LLM : python -m training.eval_all (ou eval_agent / eval_judge / eval_tools) ; protocole dans docs/EVALUATION.md
10. Test de l'interface (DOM simulé) : `npm i jsdom`, lancer le serveur, puis `BASE=http://127.0.0.1:8000 node tests/ui_smoke.js`
Après cette mise à jour : relance `prepare_data` (nouvelles règles de nettoyage), `training.vision` (couleur par pixels, labels fusionnés) puis `training.train`.
11. LLM : `python -m training.check_llm` (vérifie chaque agent) · `python -m training.eval_models` (compare les modèles) · `python -m training.label_cases` (notation humaine du juge)

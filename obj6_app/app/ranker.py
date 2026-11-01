import os
from pathlib import Path
import joblib, numpy as np
from .features import FEATURES, utility

MODEL_PATH = Path(os.getenv("DRESSME_MODEL", Path(__file__).parent.parent / "models" / "ranker.joblib"))
_blob = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None
_model = _blob["model"] if _blob and _blob.get("features") == FEATURES else None  # modèle obsolète -> règles (relancer train)

_regress = bool(_blob) and _blob.get("kind") == "regress"

def model_loaded(): return _model is not None

def kind(): return (_blob.get("kind", "classify") if _model is not None else "rules")

def score(feats: list[dict]) -> np.ndarray:
    if _model is None:  # fallback règles
        return np.array([utility(f) for f in feats])
    X = np.array([[f[k] for k in FEATURES] for f in feats])
    return 1 / (1 + np.exp(-_model.predict(X))) if _regress else _model.predict_proba(X)[:, 1]   # régression : score ramené entre 0 et 1

from __future__ import annotations
from math import comb
import numpy as np


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z ** 2 / n; c = (p + z ** 2 / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / d
    return float(c - h), float(c + h)


def macro_f1(y_true, y_pred) -> float:
    labels = sorted(set(y_true) | set(y_pred)); fs = []
    for c in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c); fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        fs.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(fs)) if fs else float("nan")


def bootstrap_ci(y_true, y_pred, stat, n_boot: int = 2000, seed: int = 0):
    rng = np.random.default_rng(seed); yt, yp = np.asarray(y_true), np.asarray(y_pred); n = len(yt); vals = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n); vals.append(stat(yt[i].tolist(), yp[i].tolist()))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def mcnemar_exact(correct_a, correct_b) -> float:
    """p-valeur bilatérale exacte (binomiale) entre deux systèmes évalués sur les mêmes images."""
    b = sum(1 for x, y in zip(correct_a, correct_b) if x and not y); c = sum(1 for x, y in zip(correct_a, correct_b) if y and not x); n = b + c
    if n == 0: return 1.0
    k = min(b, c); return float(min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n))


def confidence_table(conf, correct, bins=(0, 0.6, 0.7, 0.85, 1.0001)):
    conf, correct = np.asarray(conf, float), np.asarray(correct, bool); rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf >= lo) & (conf < hi); rows.append(dict(tranche=f"[{lo:.2f};{min(hi, 1):.2f}]", n=int(m.sum()), precision=float(correct[m].mean()) if m.any() else float("nan")))
    return rows

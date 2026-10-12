"""Fit factor weights per format group: minimise MAE with weights >= 0 summing to 1.

Minimising mean absolute error under those constraints is a linear programme, so it is solved
exactly with scipy's HiGHS LP solver (more reliable than SLSQP on the non-smooth MAE objective;
SLSQP is kept as a fallback if the LP solver fails).
"""
import numpy as np
from scipy import optimize, sparse

from engine.factors import FACTORS

LP_MAX_ROWS = 20000


def mae(X, y, w):
    return float(np.mean(np.abs(y - X @ w))) if len(y) else float("nan")


def fit_weights(X, y, active):
    """Weights over all FACTORS; only `active` columns may be non-zero."""
    idx = [FACTORS.index(a) for a in active]
    Xa = X[:, idx]
    n, k = Xa.shape
    w = np.zeros(len(FACTORS))
    if k == 1:
        w[idx[0]] = 1.0
        return w
    if n > LP_MAX_ROWS:
        # large groups: SLSQP on the MAE with its subgradient (the exact LP is too slow here)
        def obj(v):
            r = y - Xa @ v
            return np.mean(np.abs(r)), -(Xa.T @ np.sign(r)) / n
        best = None
        for start in (np.full(k, 1.0 / k), np.eye(k)[0]):
            res = optimize.minimize(obj, start, jac=True, method="SLSQP", bounds=[(0, 1)] * k,
                                    constraints=[{"type": "eq", "fun": lambda v: v.sum() - 1}],
                                    options={"maxiter": 500})
            if best is None or res.fun < best.fun:
                best = res
        w[idx] = np.clip(best.x, 0, None)
        return w / w.sum()
    # variables: [w (k), e_plus (n), e_minus (n)];  Xa w + e+ - e- = y
    c = np.concatenate([np.zeros(k), np.ones(2 * n) / n])
    eye = sparse.identity(n, format="csr")
    A_eq = sparse.vstack([
        sparse.hstack([sparse.csr_matrix(Xa), eye, -eye]),
        sparse.hstack([sparse.csr_matrix(np.ones((1, k))), sparse.csr_matrix((1, 2 * n))]),
    ]).tocsr()
    b_eq = np.concatenate([y, [1.0]])
    res = optimize.linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=(0, None), method="highs")
    if res.status == 0:
        wa = res.x[:k]
    else:
        res = optimize.minimize(
            lambda v: np.mean(np.abs(y - Xa @ v)), np.full(k, 1.0 / k), method="SLSQP",
            bounds=[(0, 1)] * k, constraints=[{"type": "eq", "fun": lambda v: v.sum() - 1}])
        wa = res.x
    w[idx] = np.clip(wa, 0, None)
    return w / w.sum()


def round_weights(w, step):
    r = np.round(w / step) * step
    if r.sum() == 0:              # everything rounded away: keep the largest weight
        r = np.zeros_like(w)
        r[int(np.argmax(w))] = 1.0
    return r / r.sum()


def fit_group(X_fit, y_fit, X_test, y_test, step):
    form_only = np.zeros(len(FACTORS))
    form_only[FACTORS.index("form")] = 1.0
    out = {"baseline_test_mae": mae(X_test, y_test, form_only),
           "baseline_fit_mae": mae(X_fit, y_fit, form_only)}

    full = round_weights(fit_weights(X_fit, y_fit, FACTORS), step)
    full_mae = mae(X_test, y_test, full)
    out["full_weights"] = dict(zip(FACTORS, full.round(4).tolist()))
    out["full_test_mae"] = full_mae

    ablation = {}
    dropped = []
    for f in FACTORS:
        active = [a for a in FACTORS if a != f]
        w = round_weights(fit_weights(X_fit, y_fit, active), step)
        m = mae(X_test, y_test, w)
        ablation[f] = m
        if m <= full_mae:          # not worse without it -> drop
            dropped.append(f)
    out["ablation_test_mae"] = ablation
    out["dropped"] = dropped

    keep = [f for f in FACTORS if f not in dropped] or ["form"]
    final = round_weights(fit_weights(X_fit, y_fit, keep), step)
    out["final_weights"] = dict(zip(FACTORS, final.round(4).tolist()))
    out["final_vec"] = final
    out["test_mae"] = mae(X_test, y_test, final)
    out["fit_mae"] = mae(X_fit, y_fit, final)
    return out

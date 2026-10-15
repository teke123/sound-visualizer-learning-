"""Contour-shape models for f0: per-token Legendre polynomials and GCA.

Port of the contour-modelling module of the R package ``shinytone``
(source repository ``citationtone_hub``, files ``R/polynomial.R`` and
``R/gca.R``).

* :func:`fit_polynomial` is a faithful port of
  ``shinytone::fit_polynomial()``: one ordinary-least-squares Legendre
  fit per token.
* :func:`fit_gca_fixed` (alias :func:`fit_gca`) ports
  ``shinytone::fit_gca()`` with one deliberate downgrade: the R
  original is a linear mixed-effects model fitted with
  ``lme4::lmer()`` (by-speaker and by-item random intercepts/slopes),
  while this Python version fits the fixed-effects part only, by OLS.
  See the docstring of :func:`fit_gca_fixed` for the consequences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .time_norm import resolve_time_norm
from .utils import legendre_basis, orthogonal_poly, require_columns

__all__ = ["fit_polynomial", "fit_gca_fixed", "fit_gca", "GcaFit"]

_VALID_DEGREES = (1, 2, 3)
_VALID_TIME_NORMALISED = ("auto", "no", "yes")


def _as_f0_numeric(data: pd.DataFrame, col: str) -> np.ndarray:
    """f0 values as float, erroring (like R) when the column is not numeric."""
    vals = pd.to_numeric(data[col], errors="coerce").to_numpy(dtype=float)
    if len(vals) > 0 and np.isnan(vals).all() and not data[col].isna().all():
        raise ValueError(f"Column '{col}' must be numeric.")
    return vals


# -----------------------------------------------------------------------------
# Per-token Legendre polynomial fitting (port of polynomial.R)
# -----------------------------------------------------------------------------
def fit_polynomial(
    data: pd.DataFrame,
    f0: str = "f0",
    token: str = "token",
    time: str = "time",
    speaker: str = "speaker",
    tone: str = "tone",
    degree: int = 2,
    time_normalised: str = "auto",
) -> pd.DataFrame:
    """Fit Legendre polynomials to f0 contours, token by token.

    Port of ``shinytone::fit_polynomial()`` (a faithful port; no
    behavioural differences from the R original).

    For each token, the time axis is normalised to ``[0, 1]`` (either a
    per-token min-max rescale, or used as-is when already normalised —
    see :func:`tone_py.time_norm.resolve_time_norm`), mapped to
    ``[-1, 1]`` with ``2 * t - 1``, expanded on a Legendre polynomial
    basis of the requested degree, and fitted by ordinary least
    squares. Returns one row per token with the coefficients ``c0``,
    ``c1``, ..., ``c{degree}`` — a compact, interpretable summary of
    contour shape, usable as features for downstream classifiers and
    regressions (Mirman 2014; Xu & Zhang 2024).

    Interpreting the coefficients (Legendre polynomials are orthogonal
    on ``[-1, 1]``):

    * ``c0``: token-level mean f0.
    * ``c1``: linear slope across the contour. Positive means rising.
    * ``c2``: quadratic curvature. Positive means U-shaped (dipping),
      negative means inverted-U (peaking).
    * ``c3``: cubic shape. Differentiates sigmoid from reverse-sigmoid
      contours.

    Edge cases (as in R):

    * Tokens with fewer than ``degree + 1`` valid samples (rows where
      both time and f0 are non-NaN) receive NaN for all coefficients.
    * Tokens whose (resolved) time has zero range — a single unique
      time point or all-NaN times — keep ``c0`` as the mean f0 and set
      the higher-order coefficients to NaN.

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample. Not
        modified.
    f0, token, time, speaker, tone : Column names for f0 values, token
        ID, time within token, speaker ID, and tone category. Defaults
        follow the R package.
    degree : Polynomial degree, one of 1, 2, or 3. Default 2.
    time_normalised : "auto" (detect an already-normalised [0, 1] time
        column and use it as-is), "no" (always rescale per token), or
        "yes" (declare the column already normalised).

    Returns
    -------
    Token-level data frame with columns ``token``, ``speaker``,
    ``tone`` (first occurrence per token, after ordering by token and
    time, as in R) and ``c0`` ... ``c{degree}``, one row per token in
    sorted token order. ``out.attrs["time_prenormalised"]`` records
    whether the time column was treated as already normalised.

    References
    ----------
    Mirman, D. (2014). *Growth Curve Analysis and Visualization Using
    R*. Chapman and Hall/CRC.

    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations.
    *The Journal of the Acoustical Society of America*, 156(4),
    2538–2539. doi:10.1121/10.0032356
    """
    if time_normalised not in _VALID_TIME_NORMALISED:
        raise ValueError('time_normalised must be one of "auto", "no", "yes".')
    if degree not in _VALID_DEGREES:
        raise ValueError("`degree` must be 1, 2, or 3.")
    require_columns(data, [f0, token, time, speaker, tone])

    f0_vals = _as_f0_numeric(data, f0)
    t01, prenormalised = resolve_time_norm(data, time, token, time_normalised)

    # Work on an internal copy: token metadata and coefficients take the
    # first value after ordering by (token, time), mirroring R's
    # arrange() + group_by() + first() / group_modify() pipeline.
    work = pd.DataFrame(
        {
            token: data[token].to_numpy(),
            speaker: data[speaker].to_numpy(),
            tone: data[tone].to_numpy(),
            time: np.asarray(t01, dtype=float),
            "_f0": f0_vals,
        }
    )
    work = work.sort_values([token, time], kind="mergesort")

    coef_names = [f"c{k}" for k in range(degree + 1)]
    rows: List[Dict[str, Any]] = []
    for tok, grp in work.groupby(token, sort=False, dropna=False):
        coefs = _fit_one_token_polynomial(
            grp[time].to_numpy(dtype=float),
            grp["_f0"].to_numpy(dtype=float),
            degree,
        )
        row: Dict[str, Any] = {
            token: tok,
            speaker: grp[speaker].iloc[0],
            tone: grp[tone].iloc[0],
        }
        row.update(coefs)
        rows.append(row)

    out = pd.DataFrame(rows, columns=[token, speaker, tone] + coef_names)
    out.attrs["time_prenormalised"] = prenormalised
    return out


def _fit_one_token_polynomial(
    t01: np.ndarray, y: np.ndarray, degree: int
) -> Dict[str, float]:
    """Fit one token on the Legendre basis; mirrors fit_one_token_polynomial().

    ``t01`` is the resolved [0, 1] time for the token; the fixed map
    ``2 * t - 1`` lands on the per-token [-1, 1] scale.
    """
    coef_names = [f"c{k}" for k in range(degree + 1)]
    result: Dict[str, float] = {name: float("nan") for name in coef_names}

    # Degenerate: zero range (single unique time, all-NaN time, ...).
    finite_t = t01[np.isfinite(t01)]
    if finite_t.size == 0 or finite_t.max() == finite_t.min():
        finite_y = y[np.isfinite(y)]
        result["c0"] = float(finite_y.mean()) if finite_y.size > 0 else float("nan")
        return result

    t_norm = 2.0 * t01 - 1.0
    valid = np.isfinite(t_norm) & np.isfinite(y)
    if int(valid.sum()) < degree + 1:
        return result

    B = legendre_basis(t_norm[valid], degree)
    beta, _, _, _ = np.linalg.lstsq(B, y[valid], rcond=None)
    for k, name in enumerate(coef_names):
        result[name] = float(beta[k])
    return result


# -----------------------------------------------------------------------------
# Growth Curve Analysis, fixed-effects version (port of gca.R)
# -----------------------------------------------------------------------------
def _gca_design(
    Q: np.ndarray, tone_codes: np.ndarray, degree: int, tone_levels: List[Any]
):
    """Design matrix for ``f0 ~ (ot1 + ... + otK) * tone`` (treatment contrasts).

    Column order matches R's ``model.matrix`` for the fixed part:
    intercept, ``ot1`` ... ``otK``, one dummy per non-baseline tone
    level (levels in first-appearance order, first level = baseline),
    then every ``otk:tone`` interaction. Returns ``(X, term_names)``.
    """
    n = Q.shape[0]
    n_levels = len(tone_levels)
    cols: List[np.ndarray] = [np.ones(n)]
    names: List[str] = ["(Intercept)"]
    for k in range(degree):
        cols.append(Q[:, k])
        names.append(f"ot{k + 1}")
    dummies: Dict[int, np.ndarray] = {}
    for j in range(1, n_levels):
        d = (tone_codes == j).astype(float)
        dummies[j] = d
        cols.append(d)
        names.append(f"tone[{tone_levels[j]}]")
    for k in range(degree):
        for j in range(1, n_levels):
            cols.append(Q[:, k] * dummies[j])
            names.append(f"ot{k + 1}:tone[{tone_levels[j]}]")
    return np.column_stack(cols), names


@dataclass
class GcaFit:
    """Result of :func:`fit_gca_fixed`.

    Attributes
    ----------
    beta : Fitted OLS coefficients, one per design-matrix column.
    term_names : Readable names for the columns of the design matrix,
        aligned with ``beta``.
    degree : Polynomial degree used.
    poly_coefs : Cached coefficients from
        :func:`tone_py.utils.orthogonal_poly`; ``predict()`` re-applies
        them so the prediction basis matches the fit basis.
    tone_levels : Tone levels in first-appearance order; the first is
        the baseline of the treatment contrasts.
    col_names : Original column names (f0, time, token, tone, speaker,
        item) the model was fit with.
    time_prenormalised : Whether the time column was treated as already
        normalised to [0, 1].
    formula_str : Human-readable description of the fitted structure.
    n_obs : Number of rows used in the fit (rows with NaN f0 or time
        are dropped).
    """

    beta: np.ndarray
    term_names: List[str]
    degree: int
    poly_coefs: Dict[str, Any]
    tone_levels: List[Any]
    col_names: Dict[str, str]
    time_prenormalised: bool
    formula_str: str
    n_obs: int

    def predict(self, n: int = 100) -> pd.DataFrame:
        """Predict population-level f0 contours on a time grid.

        Port of the output convention of ``shinytone::predict_gca()``:
        builds an ``(time, tone)`` grid of ``n`` evenly-spaced points
        across [0, 1] for every tone level, re-computes the orthogonal
        polynomial basis on that grid from the cached ``poly_coefs``,
        assembles the same fixed-effects design (intercept + ``ot``
        terms + tone dummies + interactions), and dots it with ``beta``.

        Returns a data frame with columns ``time``, ``f0_predicted``,
        ``tone``.
        """
        n = int(n)
        n_lev = len(self.tone_levels)
        time_seq = np.linspace(0.0, 1.0, n)
        Q_grid, _ = orthogonal_poly(
            time_seq,
            self.degree,
            alpha=self.poly_coefs["alpha"],
            norm2=self.poly_coefs["norm2"],
        )
        # Row order mirrors R's expand.grid(time, tone): tone varies
        # fastest within each time point.
        Q_tiled = np.repeat(Q_grid, n_lev, axis=0)
        codes = np.tile(np.arange(n_lev, dtype=np.int64), n)
        X, _ = _gca_design(Q_tiled, codes, self.degree, self.tone_levels)
        predictions = X @ self.beta
        return pd.DataFrame(
            {
                "time": np.repeat(time_seq, n_lev),
                "f0_predicted": predictions,
                "tone": np.tile(np.asarray(self.tone_levels, dtype=object), n),
            }
        )


def fit_gca_fixed(
    data: pd.DataFrame,
    f0: str = "f0",
    time: str = "time",
    token: str = "token",
    tone: str = "tone",
    speaker: str = "speaker",
    item: str = "item",
    degree: int = 2,
    time_normalised: str = "auto",
) -> GcaFit:
    """Fit a fixed-effects Growth Curve Analysis (GCA) model to f0 contours.

    Port of ``shinytone::fit_gca()``.

    DIFFERENCE FROM THE R ORIGINAL — READ FIRST
    -------------------------------------------
    The R ``fit_gca()`` fits a linear **mixed-effects** model with
    ``lme4::lmer()``: fixed effects ``(ot1 + ... + otK) * tone`` plus
    by-speaker random intercepts/slopes and a by-item random intercept
    (REML, configurable random-effects structure). Python here has no
    ``lme4`` equivalent, so this port deliberately implements the
    **fixed-effects version of GCA only**: ordinary least squares on
    ``f0 ~ (ot1 + ... + otK) * tone``, with no random effects and no
    REML. Consequences:

    * Coefficients and ``predict()`` curves condition on the observed
      sample of speakers/items instead of partially pooling across
      them, so inference (standard errors) and the handling of
      unbalanced designs differ from the R fit; with few tokens per
      speaker, expect less shrinkage-stable estimates than lme4.
    * The R signature's random-effects switches
      (``random_intercept_speaker``, ``random_slope_speaker``,
      ``random_intercept_item``, ``random_slope_item``) do not exist
      here. The ``speaker`` and ``item`` columns are still required
      (as in R, for validation) and recorded in ``col_names``, but
      contribute no coefficients.
    * When mixed-effects GCA is needed, use R ``lme4::lmer()`` directly
      or ``pymer4``.

    What this function does (mirroring R up to the fixed-effects
    downgrade):

    1. Normalise the time axis to [0, 1] within each token via
       :func:`tone_py.time_norm.resolve_time_norm`, honouring an
       already-normalised column.
    2. Drop rows with NaN f0 or time, then build orthogonal polynomial
       terms ``ot1`` ... ``otK`` on the remaining time values with
       :func:`tone_py.utils.orthogonal_poly`, caching the basis
       coefficients so :meth:`GcaFit.predict` reuses them.
    3. Assemble the design matrix for ``f0 ~ (ot1 + ... + otK) * tone``
       with treatment contrasts (tone levels in first-appearance
       order, first level = baseline) and fit by
       ``numpy.linalg.lstsq``.

    Choosing the polynomial degree (as in R): 1 = linear (purely
    rising/falling contours); 2 (default) = adds quadratic, capturing
    dipping/peaking shapes, the usual choice; 3 = adds cubic for
    sigmoid/S-shaped contours.

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample. Not
        modified.
    f0, time, token, tone, speaker, item : Column names for f0, time
        within token, token ID, tone category, speaker ID, and item or
        word. ``speaker`` and ``item`` must be present (as in R).
    degree : Polynomial degree, one of 1, 2, or 3. Default 2.
    time_normalised : "auto", "no", or "yes"; see
        :func:`tone_py.time_norm.resolve_time_norm`.

    Returns
    -------
    :class:`GcaFit` with the fitted coefficients and everything
    :meth:`GcaFit.predict` needs.

    References
    ----------
    Mirman, D. (2014). *Growth Curve Analysis and Visualization Using
    R*. Chapman and Hall/CRC.

    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations.
    *The Journal of the Acoustical Society of America*, 156(4),
    2538–2539. doi:10.1121/10.0032356
    """
    if time_normalised not in _VALID_TIME_NORMALISED:
        raise ValueError('time_normalised must be one of "auto", "no", "yes".')
    if degree not in _VALID_DEGREES:
        raise ValueError("`degree` must be 1, 2, or 3.")
    require_columns(data, [f0, time, token, tone, speaker, item])

    f0_vals = _as_f0_numeric(data, f0)
    t01, prenormalised = resolve_time_norm(data, time, token, time_normalised)

    keep = np.isfinite(f0_vals) & np.isfinite(t01)
    if not keep.any():
        raise ValueError(
            "No rows with complete (non-NaN) f0 and time values to fit."
        )
    t_train = t01[keep]
    f0_train = f0_vals[keep]
    tones = data[tone].to_numpy()[keep]

    # Tone levels in first-appearance order; first level is the baseline.
    tone_levels = [lev for lev in pd.unique(tones) if not pd.isna(lev)]
    tone_codes = pd.Categorical(tones, categories=tone_levels).codes.astype(np.int64)

    # Orthogonal polynomial basis on the training points; cache coefs.
    Q, poly_coefs = orthogonal_poly(t_train, degree)
    X, term_names = _gca_design(Q, tone_codes, degree, tone_levels)
    beta, _, _, _ = np.linalg.lstsq(X, f0_train, rcond=None)

    ot_terms = " + ".join(f"ot{k + 1}" for k in range(degree))
    formula_str = f"{f0} ~ ({ot_terms}) * {tone} [fixed effects only]"

    return GcaFit(
        beta=beta,
        term_names=term_names,
        degree=degree,
        poly_coefs=poly_coefs,
        tone_levels=tone_levels,
        col_names={
            "f0": f0,
            "time": time,
            "token": token,
            "tone": tone,
            "speaker": speaker,
            "item": item,
        },
        time_prenormalised=prenormalised,
        formula_str=formula_str,
        n_obs=int(keep.sum()),
    )


# Alias matching the R function name ``fit_gca()``. The R original is a
# mixed-effects model; see fit_gca_fixed's docstring for the deliberate
# fixed-effects downgrade and its consequences.
fit_gca = fit_gca_fixed

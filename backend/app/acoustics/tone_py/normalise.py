"""Speaker-level f0 normalisation for long-format contour data.

Port of shinytone ``normalise.R`` (``normalise_f0()``). Speaker
normalisation puts contours from male and female speakers on a comparable
scale, and is a near-universal pre-processing step before cross-speaker
tone modelling, plotting, or contour summarisation (Rose 1987; Zhu 1999).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import require_columns, token_group_key

__all__ = ["normalise_f0"]


def _nanmean(values: np.ndarray) -> float:
    # R mean(x, na.rm = TRUE): drop NaN, keep +/-Inf, empty input -> NaN.
    v = values[~np.isnan(values)]
    return float(v.mean()) if v.size else float("nan")


def normalise_f0(data: pd.DataFrame,
                 f0: str = "f0",
                 speaker: str = "speaker",
                 tone: str = "tone",
                 method: str = "semitone",
                 mean_method: str = "weighted") -> pd.DataFrame:
    """Normalise f0 within speakers, as semitones or z-scores.

    Adds a within-speaker normalised f0 column to a long-format f0 data
    frame (one row per f0 sample). Speaker normalisation puts contours
    from male and female speakers on a comparable scale (Rose 1987;
    Zhu 1999); see Xu & Zhang (2024) for its role in the standard
    citation-tone workflow.

    Two formulae are available. Semitones above or below the speaker's
    mean give a perceptually uniform scale; by-speaker z-scores combine
    centring with unit-variance scaling. Both rely on a per-speaker mean
    of f0, computed in one of two ways:

    * ``mean_method="weighted"`` (default): mean f0 per (speaker, tone)
      cell, then the unweighted mean of those per-tone means, so every
      tone contributes equally regardless of token counts. The right
      default for unbalanced designs.
    * ``mean_method="simple"``: arithmetic mean of all of a speaker's
      f0 observations.

    All summary statistics skip NaN (R ``na.rm = TRUE`` semantics);
    sample-level NaN f0 propagates as NaN in the normalised column.

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample.
    f0 : Name of the column with raw f0 values in Hz. Default ``"f0"``.
    speaker : Name of the speaker ID column. Default ``"speaker"``.
    tone : Name of the tone category column; read only when
        ``mean_method="weighted"``. Default ``"tone"``.
    method : ``"semitone"`` (default) adds ``f0_st =
        12 * log2(f0 / speaker_mean)``; ``"zscore"`` adds ``f0_zscore =
        (f0 - speaker_mean) / sd(f0)`` with the sample standard deviation
        (ddof=1) computed within each speaker.
    mean_method : ``"weighted"`` or ``"simple"`` (see above).

    Returns
    -------
    A copy of ``data`` with ``speaker_mean`` and ``f0_st`` (or
    ``f0_zscore``) appended.

    Raises
    ------
    ValueError
        If required columns are missing or the f0 column is not numeric.

    References
    ----------
    Rose, P. (1987). Considerations in the normalisation of the
    fundamental frequency of linguistic tone. *Speech Communication*,
    6(4), 343-352.
    Zhu, X. (1999). *Shanghai Tonetics*. LINCOM Europa.
    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.

    Port of shinytone::normalise_f0().
    """
    if method not in ("semitone", "zscore"):
        raise ValueError("method must be one of 'semitone', 'zscore'")
    if mean_method not in ("weighted", "simple"):
        raise ValueError("mean_method must be one of 'weighted', 'simple'")

    required = [f0, speaker]
    if mean_method == "weighted":
        required.append(tone)
    require_columns(data, required)

    # is.numeric() in R: integer/double only; logical and character fail.
    if data[f0].dtype.kind not in "iuf":
        raise ValueError(f"Column '{f0}' must be numeric (f0 in Hz).")

    f0v = data[f0].to_numpy(dtype=float)
    spk = token_group_key(data[speaker])
    n_groups = int(spk.max()) + 1 if len(spk) else 0

    if mean_method == "simple":
        means = np.full(n_groups, np.nan)
        for g in range(n_groups):
            means[g] = _nanmean(f0v[spk == g])
    else:
        # Two-stage mean: (speaker, tone) cell means, then equal-weight
        # mean over tones within speaker; NaN cells drop out of the
        # second stage (na.rm = TRUE on the tone means).
        tnc = token_group_key(data[tone])
        cells = (pd.DataFrame({"g": spk, "t": tnc, "y": f0v})
                 .groupby(["g", "t"], sort=False)["y"].mean())
        speaker_cells = cells.groupby(level="g", sort=False).mean()
        if n_groups:
            means = speaker_cells.reindex(range(n_groups)).to_numpy(dtype=float)
        else:
            means = np.full(0, np.nan)

    speaker_mean = means[spk]

    out = data.copy()
    out["speaker_mean"] = speaker_mean

    if method == "zscore":
        # sd() within speaker over that speaker's f0, sample SD (ddof=1);
        # fewer than two finite values -> NaN, as R's sd() returns NA.
        sd = np.full(n_groups, np.nan)
        for g in range(n_groups):
            v = f0v[spk == g]
            v = v[~np.isnan(v)]
            if v.size >= 2:
                sd[g] = float(np.std(v, ddof=1))
        with np.errstate(divide="ignore", invalid="ignore"):
            out["f0_zscore"] = (f0v - speaker_mean) / sd[spk]
    else:
        with np.errstate(divide="ignore", invalid="ignore"):
            out["f0_st"] = 12.0 * np.log2(f0v / speaker_mean)

    return out

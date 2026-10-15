"""Chao tone numeral summarisation.

Port of shinytone ``chao.R`` (citationtone_hub). Two exported functions:

* :func:`classify_contour` -- Chao digit string -> shape name.
* :func:`contour_to_chao` -- per-tone contour -> Chao numerals (three
  conversion methods: reference-line FOR, interval-based FOR, and
  robust FOR after Zhu 1999 / Xu & Zhang 2024).
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .utils import require_columns

# All-identical digit strings map onto these finer-grained level names.
_LEVEL_NAMES = {
    1: "low level",
    2: "mid-low level",
    3: "mid level",
    4: "mid-high level",
    5: "high level",
}


def classify_contour(chao_str: str) -> str:
    """Classify a Chao tone numeral string as a shape.

    Returns a short human-readable shape name (e.g. ``"level"``,
    ``"rising"``, ``"falling"``, ``"dipping"``, ``"peaking"``, or one of
    the finer-grained ``"low level"`` / ``"mid level"`` / ``"high level"``
    labels for repeated-digit strings).

    Classification rules:

    * All digits identical: one of ``"low level"``, ``"mid-low level"``,
      ``"mid level"``, ``"mid-high level"``, ``"high level"`` according
      to the digit value.
    * Three or more digits with an interior minimum below both
      endpoints: ``"dipping"``.
    * Three or more digits with an interior maximum above both
      endpoints: ``"peaking"``.
    * Otherwise ``"rising"`` if the last digit is higher than the first,
      ``"falling"`` if lower, ``"level"`` if equal.

    Parameters
    ----------
    chao_str : A string of Chao digits, e.g. ``"55"``, ``"214"``, ``"35"``.

    Returns
    -------
    A string naming the shape.

    Port of shinytone::classify_contour().

    References
    ----------
    Chao, Y. R. (1930). A system of tone-letters. *Le Maitre
    Phonetique*, 30, 24-27.

    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.
    """
    digits = [int(ch) for ch in str(chao_str)]
    n = len(digits)
    if n < 2:
        return "level"

    first, last = digits[0], digits[-1]

    if all(d == first for d in digits):
        if first not in _LEVEL_NAMES:
            raise ValueError(
                f"Chao digits must be integers in 1..5, got {chao_str!r}")
        return _LEVEL_NAMES[first]

    if n >= 3:
        interior = digits[1:-1]
        if min(interior) < first and min(interior) < last:
            return "dipping"
        if max(interior) > first and max(interior) > last:
            return "peaking"

    if last > first:
        return "rising"
    if last < first:
        return "falling"
    return "level"


def _numeral(values: np.ndarray, mode: str) -> str:
    """Digit string from sampled continuous Chao values.

    Mirrors R's ``paste0(pmax(1L, pmin(5L, <round|ceiling>(x))), collapse = "")``:
    clip to 1..5 *after* rounding/ceiling, then concatenate as integers.
    NaN values render as "NaN" (R's ``paste0`` on NA yields "NA").
    """
    parts = []
    for v in np.asarray(values, dtype=float):
        if np.isnan(v):
            parts.append("NaN")
            continue
        d = np.round(v) if mode == "round" else np.ceil(v)
        parts.append(str(int(min(5.0, max(1.0, d)))))
    return "".join(parts)


def _object_column(values: List[np.ndarray]) -> np.ndarray:
    """1-d object ndarray holding one ndarray per cell (list-column)."""
    arr = np.empty(len(values), dtype=object)
    for i, v in enumerate(values):
        arr[i] = v
    return arr


def contour_to_chao(contour_data: pd.DataFrame,
                    tone_col: str = "tone",
                    time_col: str = "time",
                    f0_col: str = "f0_predicted",
                    threshold: float = 0.5,
                    raw_data: Optional[pd.DataFrame] = None,
                    raw_token: str = "token",
                    raw_f0: str = "f0",
                    raw_tone: str = "tone") -> pd.DataFrame:
    """Convert per-tone contours to Chao tone numerals.

    Summarises per-tone contours as Chao tone numerals (Chao 1930):
    5-level digit strings like ``"55"``, ``"35"``, or ``"214"`` that
    describe each contour by its endpoints and any interior turning
    point. Three conversion methods are computed in one pass so the
    analyst can compare them (Xu & Zhang 2024):

    * **Reference-line FOR on [1, 5]** (``refline``):
      ``f0' = (f0 - f0_min) / (f0_max - f0_min) * 4 + 1``, then rounded.
      Five reference lines at integer values; each sampled point snaps
      to the nearest integer.
    * **Interval-based FOR on (0, 5]** (``interval``):
      ``f0' = (f0 - f0_min) / (f0_max - f0_min) * 5``, then ceilinged.
      Five equal-width intervals; each sampled point is assigned to its
      interval.
    * **Robust FOR on (0, 5]** (``robust``, only if ``raw_data`` is
      supplied): same interval formula, but the range is defined by
      mu +/- sigma of per-token f0 peaks from the highest-pitched tone
      (max) and per-token f0 valleys from the lowest-pitched tone (min),
      following Zhu (1999) and the recommendation of Xu & Zhang (2024).
      More robust to outliers than using the corpus-wide min and max.

    Turning-point detection: each tone is sampled either at its two
    endpoints (a 2-digit numeral) or at the two endpoints plus one
    interior turning point (a 3-digit numeral). The 3-digit case applies
    when the interior minimum is more than ``threshold`` Chao units
    below both endpoints (a *dip*), or the interior maximum is more than
    ``threshold`` Chao units above both endpoints (a *peak*). The
    default ``threshold=0.5`` (half a Chao unit on the [1, 5] scale) is
    a conservative choice.

    Parameters
    ----------
    contour_data : Per-tone contour data, typically from
        :func:`tone_py.contour.compute_mean_contour` or the model-based
        prediction functions. Must contain ``tone``, ``time``, and
        ``f0_predicted`` columns (or rename via ``tone_col``,
        ``time_col``, ``f0_col``).
    tone_col, time_col, f0_col : Column names within ``contour_data``.
    threshold : Chao-units threshold for turning-point detection.
        Default 0.5.
    raw_data : Optional long-format raw data, used to compute the robust
        FOR. If ``None``, the ``robust`` column is left empty (None/NaN).
    raw_token, raw_f0, raw_tone : Column names in ``raw_data``.

    Returns
    -------
    A data frame with one row per tone (tones with fewer than two
    usable samples are skipped), containing:

    * ``tone``: tone label.
    * ``n_digits``: number of digits in the numeral (2 or 3).
    * ``refline``: reference-line method numeral, e.g. ``"55"``.
    * ``interval``: interval-based numeral, e.g. ``"45"``.
    * ``robust``: robust FOR numeral (or None if ``raw_data`` was not
      given).
    * ``shape``: shape name from :func:`classify_contour` applied to
      ``refline``.
    * ``sample_times``, ``ref_continuous``, ``int_continuous``,
      ``rob_continuous``: columns of per-sample numeric values
      (``np.ndarray`` per row) underlying the digit strings.

    Three attributes are attached to the returned data frame:
    ``out.attrs["f0_min"]`` and ``out.attrs["f0_max"]`` of the input
    contour, plus ``out.attrs["robust_stats"]`` -- a dict with
    ``highest_tone``, ``lowest_tone``, ``mu_max``, ``sigma_max``,
    ``mu_min``, ``sigma_min``, ``upper``, ``lower`` -- or ``None`` when
    the robust method was not computed. The input data frames are not
    modified.

    Port of shinytone::contour_to_chao().

    References
    ----------
    Chao, Y. R. (1930). A system of tone-letters. *Le Maitre
    Phonetique*, 30, 24-27.

    Zhu, X. (1999). *Shanghai Tonetics*. LINCOM Europa.

    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.
    """
    require_columns(contour_data, [tone_col, time_col, f0_col],
                    where="contour_data")
    has_robust = raw_data is not None
    if has_robust:
        require_columns(raw_data, [raw_token, raw_f0, raw_tone],
                        where="raw_data")

    # Normalise input column names internally (never touching the inputs).
    tone = contour_data[tone_col].astype(str).to_numpy()
    tvals = (pd.to_numeric(contour_data[time_col], errors="coerce")
             .to_numpy(dtype=float))
    f0p = (pd.to_numeric(contour_data[f0_col], errors="coerce")
           .to_numpy(dtype=float))
    n = f0p.shape[0]

    # --- Reference-line + interval continuous scales ------------------------
    if n:
        f0_min = float(np.nanmin(f0p))
        f0_max = float(np.nanmax(f0p))
    else:
        f0_min = f0_max = float("nan")
    if f0_max == f0_min:
        chao_ref = np.full(n, 3.0)     # [1, 5] midpoint
        chao_int = np.full(n, 2.5)     # (0, 5] midpoint
    else:
        with np.errstate(invalid="ignore"):
            chao_ref = (f0p - f0_min) / (f0_max - f0_min) * 4.0 + 1.0
            chao_int = (f0p - f0_min) / (f0_max - f0_min) * 5.0

    # --- Robust FOR (optional) ----------------------------------------------
    chao_rob = np.full(n, np.nan)
    robust_stats: Optional[Dict[str, object]] = None
    if has_robust:
        rf0 = (pd.to_numeric(raw_data[raw_f0], errors="coerce")
               .to_numpy(dtype=float))
        rtone = raw_data[raw_tone].astype(str).to_numpy()
        rtoken = raw_data[raw_token].astype(str).to_numpy()
        valid = np.isfinite(rf0) & (rf0 > 0)

        tone_means = (pd.DataFrame({"tone": rtone[valid], "f0": rf0[valid]})
                      .groupby("tone", sort=False)["f0"].mean())
        tone_order = tone_means.index.to_numpy()
        means = tone_means.to_numpy(dtype=float)
        highest = str(tone_order[int(np.argmax(means))])
        lowest = str(tone_order[int(np.argmin(means))])

        hi = valid & (rtone == highest)
        lo = valid & (rtone == lowest)
        peaks = (pd.DataFrame({"token": rtoken[hi], "f0": rf0[hi]})
                 .groupby("token", sort=False)["f0"].max()
                 .to_numpy(dtype=float))
        valleys = (pd.DataFrame({"token": rtoken[lo], "f0": rf0[lo]})
                   .groupby("token", sort=False)["f0"].min()
                   .to_numpy(dtype=float))

        mu_max = float(np.mean(peaks))
        mu_min = float(np.mean(valleys))
        # Sample sd (ddof=1); a single token yields NaN, which disables
        # the robust method below (R's sd() returns NA here and then errors).
        sigma_max = float(np.std(peaks, ddof=1)) if peaks.size > 1 else float("nan")
        sigma_min = float(np.std(valleys, ddof=1)) if valleys.size > 1 else float("nan")

        upper = mu_max + sigma_max
        lower = max(mu_min - sigma_min, 1.0)  # floor at 1 Hz to avoid log(0)
        with np.errstate(divide="ignore", invalid="ignore"):
            log_range = float(np.log(upper) - np.log(lower))
        if np.isfinite(log_range) and log_range > 0:
            with np.errstate(divide="ignore", invalid="ignore"):
                chao_rob = np.clip(
                    (np.log(f0p) - np.log(lower)) / log_range * 5.0, 0.0, 5.0)
            robust_stats = {
                "highest_tone": highest,
                "lowest_tone": lowest,
                "mu_max": mu_max,
                "sigma_max": sigma_max,
                "mu_min": mu_min,
                "sigma_min": sigma_min,
                "upper": upper,
                "lower": lower,
            }
        else:
            has_robust = False

    # --- Per-tone numeral extraction -----------------------------------------
    fine_time = np.linspace(0.0, 1.0, 200)
    scalar_rows: List[Dict[str, object]] = []
    sample_times_col: List[np.ndarray] = []
    ref_cont_col: List[np.ndarray] = []
    int_cont_col: List[np.ndarray] = []
    rob_cont_col: List[np.ndarray] = []

    for tv in pd.unique(tone):
        keep = (tone == tv) & ~np.isnan(chao_ref) & ~np.isnan(tvals)
        idx = np.flatnonzero(keep)
        idx = idx[np.argsort(tvals[idx], kind="stable")]
        if idx.size < 2:
            continue
        tt = tvals[idx]
        ref_y = chao_ref[idx]
        int_y = chao_int[idx]
        rob_y = chao_rob[idx]

        # Endpoint-constant linear interpolation (R approxfun rule = 2,
        # which is np.interp's default behaviour).
        onset_ref = float(np.interp(0.0, tt, ref_y))
        offset_ref = float(np.interp(1.0, tt, ref_y))

        fine_ref = np.interp(fine_time, tt, ref_y)
        # R indexes fine_ref[20:180] (1-based, inclusive): elements 20..180,
        # i.e. 161 points -> numpy 0-based slice [19:180]. R then adds 19 to
        # the 1-based which.min/which.max; numpy argmin/argmax over the slice
        # are 0-based, so +19 lands on the same absolute 0-based index in
        # 19..179.
        window = fine_ref[19:180]
        interior_min_idx = int(np.argmin(window)) + 19
        interior_max_idx = int(np.argmax(window)) + 19
        interior_min = float(fine_ref[interior_min_idx])
        interior_max = float(fine_ref[interior_max_idx])

        has_dip = (onset_ref - interior_min > threshold
                   and offset_ref - interior_min > threshold)
        has_peak = (interior_max - onset_ref > threshold
                    and interior_max - offset_ref > threshold)

        if has_dip:
            sample_times = np.array([0.0, fine_time[interior_min_idx], 1.0])
        elif has_peak:
            sample_times = np.array([0.0, fine_time[interior_max_idx], 1.0])
        else:
            sample_times = np.array([0.0, 1.0])

        ref_vals = np.interp(sample_times, tt, ref_y)
        int_vals = np.interp(sample_times, tt, int_y)
        if has_robust:
            rob_vals = np.clip(np.interp(sample_times, tt, rob_y), 0.0, 5.0)
            robust_str: Optional[str] = _numeral(rob_vals, "ceil")
        else:
            rob_vals = np.full(sample_times.shape, np.nan)
            robust_str = None

        refline_str = _numeral(ref_vals, "round")
        interval_str = _numeral(int_vals, "ceil")

        scalar_rows.append({
            "tone": str(tv),
            "n_digits": int(sample_times.shape[0]),
            "refline": refline_str,
            "interval": interval_str,
            "robust": robust_str,
            "shape": classify_contour(refline_str),
        })
        sample_times_col.append(sample_times)
        ref_cont_col.append(np.asarray(ref_vals, dtype=float))
        int_cont_col.append(np.asarray(int_vals, dtype=float))
        rob_cont_col.append(np.asarray(rob_vals, dtype=float))

    out = pd.DataFrame(scalar_rows, columns=[
        "tone", "n_digits", "refline", "interval", "robust", "shape"])
    out["sample_times"] = _object_column(sample_times_col)
    out["ref_continuous"] = _object_column(ref_cont_col)
    out["int_continuous"] = _object_column(int_cont_col)
    out["rob_continuous"] = _object_column(rob_cont_col)
    out = out[["tone", "n_digits", "refline", "interval", "robust", "shape",
               "sample_times", "ref_continuous", "int_continuous",
               "rob_continuous"]]

    # Attach summary stats as attributes so callers can display them
    # without recomputing.
    out.attrs["f0_min"] = f0_min
    out.attrs["f0_max"] = f0_max
    out.attrs["robust_stats"] = robust_stats if has_robust else None
    return out

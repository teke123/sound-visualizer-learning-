"""F0 quality inspection: token-level outliers and sample-level artefacts.

Port of shinytone ``R/inspect.R`` (citationtone_hub). Five public entry
points, all operating on the package-wide long-format convention (one row
per f0 sample, column names passed as string parameters):

* :func:`flag_outliers`        token-level extremes by within-speaker z-score
* :func:`flag_level_outliers`  token-level level by within speaker x tone
                               modified z-score
* :func:`flag_low_intensity`   sample-level low-energy advisory flag
* :func:`flag_pitch_jumps`     sample-level jump / octave / carryover flags
* :func:`inspect_f0`           composes all of the above into one tagged
                               long-format data frame

f0 == 0 Hz is treated as unvoiced (equivalent to NaN), matching pitch
trackers that emit 0 for voiceless frames. Input frames are never
modified; every function returns a new object.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from .utils import f0_to_nan, f0_voiced, require_columns, require_numeric, token_group_key

__all__ = [
    "flag_outliers",
    "flag_level_outliers",
    "flag_low_intensity",
    "flag_pitch_jumps",
    "inspect_f0",
]


def flag_outliers(data: pd.DataFrame,
                  f0: str = "f0",
                  token: str = "token",
                  speaker: str = "speaker",
                  z_threshold: float = 3) -> pd.DataFrame:
    """Flag per-token f0 outliers using within-speaker z-scores.

    Identifies tokens whose maximum f0 is unusually high, or whose minimum
    f0 unusually low, for a speaker's per-token f0 distribution. Suitable
    as a first pass at detecting tracking errors, mis-segmentations, or
    genuinely unusual productions before fitting contour models.
    Token-level outlier removal is a recommended cleaning step prior to
    citation-tone analysis (Xu & Zhang 2024).

    Procedure:

    1. Drop samples where f0 is NaN or 0 (unvoiced frames).
    2. Compute the per-token maximum, minimum, mean, and sample SD
       (ddof=1, matching R ``stats::sd()``) of f0.
    3. Within each speaker, z-score the per-token maxima against each
       other and the per-token minima against each other, so a speaker
       with consistently high f0 is not flagged against the corpus.
    4. Flag one-sided: ``flag_too_high`` when ``z_max > z_threshold``,
       ``flag_too_low`` when ``z_min < -z_threshold``. The opposite tails
       are occupied by legitimate tone identity and are left to the finer
       screens (:func:`flag_level_outliers`, :func:`flag_pitch_jumps`).

    Tokens with no voiced sample are absent from the result. Speakers with
    too few tokens for a meaningful SD yield NaN z-scores (never flagged).

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample.
    f0 : Name of the f0 (Hz) column.
    token : Name of the token-ID column.
    speaker : Name of the speaker-ID column.
    z_threshold : Signed z cutoff; default ``3``.

    Returns
    -------
    Token-level data frame (one row per token, sorted by token) with
    columns ``token, speaker, f0_token_max, f0_token_min, f0_token_mean,
    f0_token_sd, z_max, z_min, flag_too_high, flag_too_low``.

    Port of shinytone::flag_outliers().

    References
    ----------
    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.
    """
    require_columns(data, [f0, token, speaker])
    require_numeric(data, f0, what="numeric (f0 in Hz)")

    voiced = f0_voiced(data[f0])
    if not voiced.any():
        return pd.DataFrame({
            token: pd.Series(dtype=data[token].dtype),
            speaker: pd.Series(dtype=data[speaker].dtype),
            "f0_token_max": pd.Series(dtype=float),
            "f0_token_min": pd.Series(dtype=float),
            "f0_token_mean": pd.Series(dtype=float),
            "f0_token_sd": pd.Series(dtype=float),
            "z_max": pd.Series(dtype=float),
            "z_min": pd.Series(dtype=float),
            "flag_too_high": pd.Series(dtype=bool),
            "flag_too_low": pd.Series(dtype=bool),
        })

    f0num = pd.to_numeric(data[f0], errors="coerce")
    per_token = pd.DataFrame({
        token: data[token].to_numpy()[voiced],
        "f0": f0num.to_numpy()[voiced],
    })
    agg = (per_token.groupby(token, sort=True, dropna=False)["f0"]
           .agg(f0_token_max="max", f0_token_min="min",
                f0_token_mean="mean", f0_token_sd="std")
           .reset_index())  # .std() is the sample SD (ddof=1), as in R

    # First row per token supplies the speaker (dplyr distinct semantics).
    meta = (data.drop_duplicates(subset=[token], keep="first")[[token, speaker]]
            .reset_index(drop=True))
    out = agg.merge(meta, on=token, how="left")

    grouped = out.groupby(speaker, sort=False, dropna=False)
    for src, zcol in (("f0_token_max", "z_max"), ("f0_token_min", "z_min")):
        v = out[src].astype(float)
        mu = grouped[src].transform("mean")
        sd = grouped[src].transform(lambda s: s.std(ddof=1))
        out[zcol] = (v - mu) / sd  # sd == 0 (all equal) -> 0/0 = NaN, as in R

    out["flag_too_high"] = out["z_max"].notna() & (out["z_max"] > z_threshold)
    out["flag_too_low"] = out["z_min"].notna() & (out["z_min"] < -z_threshold)
    return out[[token, speaker, "f0_token_max", "f0_token_min",
                "f0_token_mean", "f0_token_sd",
                "z_max", "z_min", "flag_too_high", "flag_too_low"]]


def flag_level_outliers(data: pd.DataFrame,
                        f0: str = "f0",
                        token: str = "token",
                        speaker: str = "speaker",
                        tone: str = "tone",
                        level_threshold: float = 3.5,
                        min_tokens: int = 5) -> pd.DataFrame:
    """Flag tokens whose overall f0 level is unusual for speaker and tone.

    Detects tokens whose whole contour sits too high or too low compared
    with other tokens of the same speaker and same tone, even when the
    contour is smooth and not extreme for the speaker overall -- the
    "right shape, wrong height" case (e.g. a low-tone token mis-tracked
    up into the mid-tone band) that :func:`flag_outliers` and
    :func:`flag_pitch_jumps` both miss.

    Procedure:

    1. Drop samples where f0 is NaN or 0 (unvoiced frames).
    2. Compute each token's median f0, converted to semitones
       (``12 * log2(Hz)``); the median is robust to the few mis-tracked
       frames that :func:`flag_pitch_jumps` already catches.
    3. Within each speaker x tone group, compute the modified z-score
       (Iglewicz & Hoaglin 1993): ``0.6745 * (level - median) / MAD``.
       When MAD == 0 (more than half the peers share an identical level),
       fall back to ``(level - median) / (1.253314 * meanAD)``; when all
       peers are identical the result is NaN.
    4. Flag ``flag_level_high`` / ``flag_level_low`` when the modified
       z-score exceeds ``+level_threshold`` / falls below
       ``-level_threshold``.

    Groups with fewer than ``min_tokens`` non-NA levels are not checked:
    their ``level_modz`` is NaN and they are never flagged.

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample.
    f0 : Name of the f0 (Hz) column.
    token : Name of the token-ID column.
    speaker : Name of the speaker-ID column.
    tone : Name of the tone-category column.
    level_threshold : Absolute modified z cutoff; default ``3.5``
        (Iglewicz & Hoaglin 1993).
    min_tokens : Minimum group size to run the check; default ``5``.

    Returns
    -------
    Token-level data frame (one row per token with at least one voiced
    sample, sorted by token) with columns ``token, speaker, tone,
    f0_token_median, level_st, n_tone_peers, level_modz,
    flag_level_high, flag_level_low``.

    Port of shinytone::flag_level_outliers().

    References
    ----------
    Iglewicz, B., & Hoaglin, D. C. (1993). *How to Detect and Handle
    Outliers*. ASQC Quality Press.

    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.
    """
    require_columns(data, [f0, token, speaker, tone])
    require_numeric(data, f0, what="numeric (f0 in Hz)")

    voiced = f0_voiced(data[f0])
    if not voiced.any():
        return pd.DataFrame({
            token: pd.Series(dtype=data[token].dtype),
            speaker: pd.Series(dtype=data[speaker].dtype),
            tone: pd.Series(dtype=data[tone].dtype),
            "f0_token_median": pd.Series(dtype=float),
            "level_st": pd.Series(dtype=float),
            "n_tone_peers": pd.Series(dtype=int),
            "level_modz": pd.Series(dtype=float),
            "flag_level_high": pd.Series(dtype=bool),
            "flag_level_low": pd.Series(dtype=bool),
        })

    f0num = pd.to_numeric(data[f0], errors="coerce")
    per_token = pd.DataFrame({
        token: data[token].to_numpy()[voiced],
        "f0": f0num.to_numpy()[voiced],
    })
    med = (per_token.groupby(token, sort=True, dropna=False)["f0"]
           .median().rename("f0_token_median").reset_index())
    med["level_st"] = 12.0 * np.log2(med["f0_token_median"])

    meta = (data.drop_duplicates(subset=[token], keep="first")[[token, speaker, tone]]
            .reset_index(drop=True))
    out = med.merge(meta, on=token, how="left")

    def _modz(x: np.ndarray) -> np.ndarray:
        # Iglewicz & Hoaglin (1993) modified z-score; mean-AD fallback for
        # the degenerate MAD == 0 case; all-identical peers -> all NaN.
        medv = np.median(x)
        madv = np.median(np.abs(x - medv))
        if np.isfinite(madv) and madv > 0:
            return 0.6745 * (x - medv) / madv
        meanad = np.mean(np.abs(x - medv))
        if np.isfinite(meanad) and meanad > 0:
            return (x - medv) / (1.253314 * meanad)
        return np.full(x.shape, np.nan)

    grouped = out.groupby([speaker, tone], sort=False, dropna=False)
    out["n_tone_peers"] = grouped["level_st"].transform(
        lambda s: int(s.notna().sum()))

    def _gate(s: pd.Series) -> np.ndarray:
        if int(s.notna().sum()) < min_tokens:
            return np.full(len(s), np.nan)
        return _modz(s.to_numpy(dtype=float))

    out["level_modz"] = grouped["level_st"].transform(_gate)

    out["flag_level_high"] = out["level_modz"].notna() & (out["level_modz"] > level_threshold)
    out["flag_level_low"] = out["level_modz"].notna() & (out["level_modz"] < -level_threshold)
    return out[[token, speaker, tone, "f0_token_median", "level_st",
                "n_tone_peers", "level_modz", "flag_level_high", "flag_level_low"]]


def flag_low_intensity(data: pd.DataFrame,
                       f0: str = "f0",
                       token: str = "token",
                       intensity: str = "intensity",
                       intensity_drop: float = 15) -> pd.DataFrame:
    """Flag low-intensity f0 samples within tokens (advisory).

    For each token, takes the peak intensity across that token's voiced
    samples and flags every voiced sample whose intensity is more than
    ``intensity_drop`` dB below that peak. The comparison is
    relative-to-peak, so it transfers across recordings regardless of
    microphone distance or gain. Intensity is an independent cue from f0:
    a smoothly mis-tracked tail need not trip the rate-of-change check in
    :func:`flag_pitch_jumps`, but it will sit in an intensity dip.

    Unvoiced samples (f0 NaN or 0) and samples with missing intensity are
    never flagged; tokens with no voiced sample are left unflagged. The
    flag is advisory: a quiet-but-modal frame can track fine, so it is an
    inspect-don't-delete signal and does not set ``flagged_token`` in
    :func:`inspect_f0`.

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample.
    f0 : Name of the f0 (Hz) column.
    token : Name of the token-ID column.
    intensity : Name of the intensity (dB) column.
    intensity_drop : dB below the token's voiced peak that triggers the
        flag; default ``15``.

    Returns
    -------
    Copy of the input data frame with one appended boolean column,
    ``flag_low_intensity``. Row order is unchanged.

    Port of shinytone::flag_low_intensity().
    """
    require_columns(data, [f0, token, intensity])
    require_numeric(data, intensity, what="numeric (intensity in dB)")

    out = data.copy()
    if out[intensity].dtype.kind not in "bifu":
        out[intensity] = pd.to_numeric(out[intensity], errors="coerce")

    voiced = f0_voiced(out[f0])
    inten = out[intensity]
    # Peak intensity per token, over voiced samples with known intensity.
    peak_src = out.loc[voiced & inten.notna().to_numpy(), [token, intensity]]
    peaks = peak_src.groupby(token, sort=False, dropna=False)[intensity].max()
    peak = out[token].map(peaks)

    out["flag_low_intensity"] = (inten.notna().to_numpy()
                                 & voiced
                                 & peak.notna().to_numpy()
                                 & (inten < peak - intensity_drop).to_numpy())
    return out


def _joined_flag(series: pd.Series) -> pd.Series:
    """Boolean flag from a left-joined column: NA (token absent from the
    joined token-level table) reads as False."""
    if series.dtype == bool:
        return series
    return pd.Series(np.where(series.isna(), False, series),
                     index=series.index, dtype=bool)


def _detect_token_artefacts(f0_hz: np.ndarray,
                            time: np.ndarray,
                            time_unit: str,
                            rise_threshold: float,
                            fall_threshold: float,
                            octave_bounds: Tuple[float, float],
                            carryover_mult: float
                            ) -> Tuple[np.ndarray, List[str]]:
    """Two-pass per-token artefact detector (shinytone internal).

    Pass 1 (jump detection): for each consecutive pair (i, i+1), compare
    the semitone rate of change against the rise/fall thresholds and the
    Hz ratio against the octave bounds. The FLAG is placed on whichever
    side is farther from the token's median f0 in semitones (ties go to
    the landing sample i+1); this reduces to landing-side flagging when
    the landing sample is the outlier and to source-side flagging when
    the source sample is the outlier.

    Pass 2 (carryover): walk forward and backward from each
    primary-flagged sample, marking neighbours within
    ``mult * threshold`` semitones of the artefact's f0. The band uses
    rise_threshold * mult when the previous frame is higher than the
    current one, fall_threshold * mult otherwise, and
    max(rise, fall) * mult when the previous frame is unavailable. The
    chain breaks at NaN frames, primary-flagged frames, and the first
    neighbour outside the band. ``carryover_mult <= 0`` disables it.
    """
    n = len(f0_hz)
    primary = np.zeros(n, dtype=bool)
    notes: List[str] = [""] * n

    if n < 2:
        return primary, notes

    with np.errstate(divide="ignore", invalid="ignore"):
        f0_st = 12.0 * np.log2(f0_hz)
    valid = np.isfinite(f0_st)
    if valid.sum() < 2:
        return primary, notes
    token_median_st = float(np.median(f0_st[valid]))

    lo, hi = octave_bounds

    # ---------- Pass 1: detect jumps, choose median-farther side ----------
    for i in range(n - 1):
        if np.isnan(f0_hz[i]) or np.isnan(f0_hz[i + 1]):
            continue

        diff_st = f0_st[i + 1] - f0_st[i]
        diff_time = time[i + 1] - time[i]
        # Rescale dt to 10-ms units; floor guards against dt == 0.
        if time_unit == "ms":
            tf = max(diff_time / 10.0, 1e-9)
        else:  # "s"
            tf = max((diff_time * 1000.0) / 10.0, 1e-9)
        rate = abs(diff_st) / tf
        hz_ratio = f0_hz[i + 1] / f0_hz[i]

        is_oct = np.isfinite(hz_ratio) and (hz_ratio < lo or hz_ratio > hi)
        is_rise = diff_st > 0 and rate > rise_threshold
        is_fall = diff_st < 0 and rate > fall_threshold
        if not (is_oct or is_rise or is_fall):
            continue

        dist_i = abs(f0_st[i] - token_median_st)
        dist_i1 = abs(f0_st[i + 1] - token_median_st)
        flag_idx = i if dist_i > dist_i1 else i + 1
        primary[flag_idx] = True

        parts = []
        if is_oct:
            parts.append("octave jump")
        if is_rise:
            parts.append("jump (rise)")
        if is_fall:
            parts.append("jump (fall)")
        new_note = "; ".join(parts)
        notes[flag_idx] = (notes[flag_idx] + "; " + new_note
                           if notes[flag_idx] else new_note)

    # ---------- Pass 2: bidirectional carryover ----------
    carry = np.zeros(n, dtype=bool)
    if carryover_mult > 0:

        def extend_chain(start_idx: int, direction: int) -> None:
            error_f0 = f0_st[start_idx]
            if np.isnan(error_f0):
                return
            idx = start_idx + direction
            while 0 <= idx < n:
                if np.isnan(f0_st[idx]) or primary[idx]:
                    break
                prev_idx = idx - direction
                if 0 <= prev_idx < n and not np.isnan(f0_st[prev_idx]):
                    band = (rise_threshold * carryover_mult
                            if f0_st[prev_idx] > f0_st[idx]
                            else fall_threshold * carryover_mult)
                else:
                    band = max(rise_threshold, fall_threshold) * carryover_mult
                if abs(f0_st[idx] - error_f0) > band:
                    break
                carry[idx] = True
                idx += direction

        for i in np.flatnonzero(primary):
            extend_chain(int(i), 1)
            extend_chain(int(i), -1)

    flagged_jump = primary | carry
    jump_note = [notes[i] if primary[i]
                 else ("carryover" if carry[i] else "")
                 for i in range(n)]
    return flagged_jump, jump_note


def flag_pitch_jumps(data: pd.DataFrame,
                     f0: str = "f0",
                     token: str = "token",
                     time: str = "time",
                     time_unit: str = "s",
                     rise_threshold: float = 1.263,
                     fall_threshold: float = 1.714,
                     octave_bounds: Tuple[float, float] = (0.49, 1.99),
                     carryover_mult: float = 1.5) -> pd.DataFrame:
    """Flag sample-to-sample f0 jumps within tokens.

    Detects sample-level pitch-tracking artefacts inside each token:
    rate-of-change violations (faster rises/falls than human vocal folds
    can plausibly produce; Sundberg 1973), octave jumps (pitch halving or
    doubling, the dominant failure mode of autocorrelation trackers), and
    carryover samples close enough to a flagged frame to be suspected
    part of the same artefact (Steffman & Cole 2022).

    Within each token (rows sorted by ``token`` then ``time``; f0 == 0
    treated as NaN):

    1. Compute the semitone difference and Hz ratio between consecutive
       f0 samples; rescale the rate of change to semitones per 10 ms via
       ``time_unit`` ("s" or "ms").
    2. Flag a pair when the Hz ratio falls outside ``octave_bounds``,
       the rise rate exceeds ``rise_threshold``, or the fall rate exceeds
       ``fall_threshold``. The flag lands on whichever side of the pair
       is farther from the token's median f0 in semitones.
    3. Extend chains of carryover frames within
       ``carryover_mult * threshold`` semitones of each primary flag.
       ``carryover_mult = 0`` disables carryover.

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample.
    f0 : Name of the f0 (Hz) column.
    token : Name of the token-ID column.
    time : Name of the time column.
    time_unit : "s" or "ms"; default "s". Real time only -- the
        physiological rate thresholds lose their meaning on normalised
        time.
    rise_threshold : Maximum plausible rise in ST per 10 ms; default
        ``1.263`` (Sundberg 1973).
    fall_threshold : Maximum plausible fall in ST per 10 ms; default
        ``1.714`` (Sundberg 1973).
    octave_bounds : (low, high) Hz-ratio bounds outside which a step is
        an octave jump; default ``(0.49, 1.99)``.
    carryover_mult : Carryover band as a multiple of the rise/fall
        thresholds; ``0`` disables carryover; default ``1.5``.

    Returns
    -------
    Copy of the input with two appended columns, sorted by ``token`` and
    ``time``: ``flagged_jump`` (boolean) and ``jump_note`` (one of
    "octave jump" / "jump (rise)" / "jump (fall)" / "carryover", or a
    "; "-joined composite). The returned ``f0`` column carries NaN where
    the input had 0 Hz, as in R.

    Port of shinytone::flag_pitch_jumps().

    References
    ----------
    Steffman, J., & Cole, J. (2022). An automated method for detecting
    f0 measurement jumps based on sample-to-sample differences. *JASA
    Express Letters*, 2(11), 115201.

    Sundberg, J. (1973). The acoustics of the singing voice.
    *Scientific American*, 229(3), 82-91.
    """
    if time_unit not in ("s", "ms"):
        raise ValueError("time_unit must be one of 's', 'ms'")
    require_columns(data, [f0, token, time])
    require_numeric(data, f0, what="numeric (f0 in Hz)")
    require_numeric(data, time, what="numeric")

    out = data.copy()
    out[f0] = f0_to_nan(out[f0])  # 0 Hz (unvoiced) -> NaN
    out = out.sort_values([token, time], kind="stable").reset_index(drop=True)

    codes = token_group_key(out[token])
    f0v = pd.to_numeric(out[f0], errors="coerce").to_numpy(dtype=float)
    tv = pd.to_numeric(out[time], errors="coerce").to_numpy(dtype=float)

    n = len(out)
    flagged = np.zeros(n, dtype=bool)
    notes: np.ndarray = np.full(n, "", dtype=object)
    for g in np.unique(codes):
        m = codes == g
        fl, nt = _detect_token_artefacts(
            f0v[m], tv[m], time_unit,
            rise_threshold, fall_threshold, octave_bounds, carryover_mult)
        flagged[m] = fl
        notes[m] = np.asarray(nt, dtype=object)

    out["flagged_jump"] = flagged
    out["jump_note"] = notes
    return out


def inspect_f0(data: pd.DataFrame,
               f0: str = "f0",
               token: str = "token",
               time: str = "time",
               speaker: str = "speaker",
               tone: Optional[str] = None,
               z_threshold: float = 3,
               rise_threshold: float = 1.263,
               fall_threshold: float = 1.714,
               octave_bounds: Tuple[float, float] = (0.49, 1.99),
               carryover_mult: float = 1.5,
               level_threshold: float = 3.5,
               min_tokens: int = 5,
               intensity: Optional[str] = None,
               intensity_drop: float = 15,
               time_unit: str = "s") -> pd.DataFrame:
    """Inspect f0 data for token-level outliers and sample-level jumps.

    One-call convenience wrapper that runs :func:`flag_outliers`,
    :func:`flag_pitch_jumps`, plus :func:`flag_level_outliers` when
    ``tone`` is given, joins the token-level results back onto the
    long-format jump output, and builds a single human-readable
    ``flag_notes`` column.

    * ``flagged_token`` is True for any token that is a speaker-level
      extreme (``flag_too_high``/``flag_too_low``), has an unusual level
      for its speaker x tone group (``flag_level_high``/low, only when
      ``tone`` is given), or contains at least one sample-level jump.
    * ``flag_notes`` concatenates, in order: "max too high", "min too
      low", "level too high", "level too low", the sample's
      ``jump_note``, and "low intensity", joined with "; ".
    * With ``tone=None`` the level screen is skipped, both level flags
      are False, and the ``tone`` column is omitted from the output, so
      the wrapper can run before tone categories are known.
    * With ``intensity`` given, :func:`flag_low_intensity` also runs: the
      ``intensity`` column and sample-level ``flag_low_intensity`` are
      included and noted in ``flag_notes``. The low-intensity flag is
      advisory -- it never sets ``flagged_token`` on its own.

    Tokens with no voiced sample have NaN token statistics; their joined
    flags read as False.

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample.
    f0, token, time, speaker : Column names of f0 (Hz), token ID, time,
        and speaker ID.
    tone : Column name of the tone category, or ``None`` (default) to
        skip the speaker-by-tone level check.
    z_threshold : Passed to :func:`flag_outliers`; default ``3``.
    rise_threshold, fall_threshold, octave_bounds, carryover_mult,
    time_unit : Passed to :func:`flag_pitch_jumps`; Sundberg (1973)
        defaults.
    level_threshold, min_tokens : Passed to :func:`flag_level_outliers`
        when ``tone`` is given; defaults ``3.5`` and ``5``.
    intensity : Optional column name of intensity (dB) for the advisory
        low-intensity check; ``None`` (default) skips it.
    intensity_drop : dB below the token's voiced peak; default ``15``.

    Returns
    -------
    Long-format data frame sorted by ``token`` and ``time`` with columns
    ``[token, time, f0]`` (+ ``intensity`` when given) ``+ [speaker]``
    (+ ``tone`` when given) ``+ [f0_token_max, f0_token_min,
    f0_token_mean, f0_token_sd, flagged_token, flagged_jump,
    flag_notes]`` (+ ``flag_low_intensity`` when intensity is given).
    Note that, as in R, ``z_max``/``z_min`` are not part of the output.

    Port of shinytone::inspect_f0().

    References
    ----------
    Steffman, J., & Cole, J. (2022). An automated method for detecting
    f0 measurement jumps based on sample-to-sample differences. *JASA
    Express Letters*, 2(11), 115201.

    Sundberg, J. (1973). The acoustics of the singing voice.
    *Scientific American*, 229(3), 82-91.

    Iglewicz, B., & Hoaglin, D. C. (1993). *How to Detect and Handle
    Outliers*. ASQC Quality Press.

    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.
    """
    if time_unit not in ("s", "ms"):
        raise ValueError("time_unit must be one of 's', 'ms'")

    outliers = flag_outliers(data, f0=f0, token=token, speaker=speaker,
                             z_threshold=z_threshold)

    levels = (flag_level_outliers(data, f0=f0, token=token,
                                  speaker=speaker, tone=tone,
                                  level_threshold=level_threshold,
                                  min_tokens=min_tokens)
              if tone is not None else None)

    result = flag_pitch_jumps(data, f0=f0, token=token, time=time,
                              time_unit=time_unit,
                              rise_threshold=rise_threshold,
                              fall_threshold=fall_threshold,
                              octave_bounds=octave_bounds,
                              carryover_mult=carryover_mult)

    result = result.merge(
        outliers[[token, "f0_token_max", "f0_token_min",
                  "f0_token_mean", "f0_token_sd",
                  "z_max", "z_min", "flag_too_high", "flag_too_low"]],
        on=token, how="left")
    # Tokens with no voiced sample are absent from the token-level table;
    # their joined-NA flags read as False.
    for c in ("flag_too_high", "flag_too_low"):
        result[c] = _joined_flag(result[c])

    if levels is not None:
        result = result.merge(
            levels[[token, "flag_level_high", "flag_level_low"]],
            on=token, how="left")
        result["flag_level_high"] = _joined_flag(result["flag_level_high"])
        result["flag_level_low"] = _joined_flag(result["flag_level_low"])
    else:
        # tone=None: the speaker-by-tone screen was skipped, never fires.
        result["flag_level_high"] = False
        result["flag_level_low"] = False

    result["has_jump_in_token"] = (result.groupby(token, sort=False, dropna=False)
                                   ["flagged_jump"].transform("any"))

    too_high = result["flag_too_high"].to_numpy(dtype=bool)
    too_low = result["flag_too_low"].to_numpy(dtype=bool)
    lvl_high = result["flag_level_high"].to_numpy(dtype=bool)
    lvl_low = result["flag_level_low"].to_numpy(dtype=bool)
    jn = result["jump_note"].to_numpy(dtype=object)

    notes = np.empty(len(result), dtype=object)
    for i in range(len(result)):
        parts = []
        if too_high[i]:
            parts.append("max too high")
        if too_low[i]:
            parts.append("min too low")
        if lvl_high[i]:
            parts.append("level too high")
        if lvl_low[i]:
            parts.append("level too low")
        if jn[i]:
            parts.append(str(jn[i]))
        notes[i] = "; ".join(parts)
    result["flag_notes"] = notes
    result["flagged_token"] = too_high | too_low | lvl_high | lvl_low | \
        result["has_jump_in_token"].to_numpy(dtype=bool)

    # Optional advisory intensity check; does not change flagged_token.
    if intensity is not None:
        result = flag_low_intensity(result, f0=f0, token=token,
                                    intensity=intensity,
                                    intensity_drop=intensity_drop)
        low = result["flag_low_intensity"].to_numpy(dtype=bool)
        old = result["flag_notes"].to_numpy(dtype=object)
        result["flag_notes"] = [
            (fn + "; low intensity") if low[i] and fn
            else ("low intensity" if low[i] else fn)
            for i, fn in enumerate(old)
        ]

    keep = [token, time, f0]
    if intensity is not None:
        keep.append(intensity)
    keep.append(speaker)
    if tone is not None:
        keep.append(tone)
    keep.extend(["f0_token_max", "f0_token_min", "f0_token_mean",
                 "f0_token_sd", "flagged_token", "flagged_jump",
                 "flag_notes"])
    if intensity is not None:
        keep.append("flag_low_intensity")
    return result[keep]

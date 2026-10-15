"""F0 extraction from .wav files and reading of pre-extracted f0 CSVs.

Python counterpart of the shinytone F0-extraction step (citationtone_hub,
``inst/app/ui/fp_extraction_ui.R``): turn audio uploads -- or a previously
extracted CSV -- into the long-format data frame the rest of the package
consumes. One row per analysis frame with ``token`` (wav basename without
extension), ``time`` (seconds), ``f0`` (Hz) and optionally ``intensity``
(dB).

Voicing semantics follow Praat: an unvoiced frame is *undefined*, written
as NaN here. Trackers that signal "no pitch" with 0 Hz (wrassp/RAPT/
REAPER) are normalised to NaN on ingestion, so downstream code
(:func:`tone_py.utils.f0_voiced`) sees a single convention.

The upstream R app extracts with ``wrassp::ksvF0`` using the same three
numbers exposed here (``minF`` / ``maxF`` / ``windowShift`` =
``f0_min`` / ``f0_max`` / ``step_ms``) and rejects files shorter than
``3 / f0_min`` seconds before analysis. This module keeps those parameter
names and the shortest-file rule while using Praat itself
(``praat-parselmouth``) or librosa's pyin as the analysis backend.

Reference
---------
Xu, Y., & Zhang, C. (2024). A cross-linguistic review of citation tone
production studies: Methodology and recommendations. *The Journal of the
Acoustical Society of America*, 156(4), 2538.
"""

from __future__ import annotations

import os
import warnings
from typing import List, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from .utils import f0_to_nan, require_columns

__all__ = ["min_audio_duration", "extract_f0", "read_f0_csv"]

WavPath = Union[str, os.PathLike]


def min_audio_duration(f0_min: float = 75.0) -> float:
    """Shortest clip (seconds) an autocorrelation pitch tracker can analyse.

    A Praat-style pitch analysis window spans 3 periods of the pitch floor
    frequency, so a clip shorter than ``3 / f0_min`` cannot yield a single
    f0 frame (nor intensity, whose window is wider still). shinytone uses
    this threshold to reject too-short uploads up front and to flag them
    red in the Start preview.

    This is an approximation: it ignores backend-specific frame placement
    (Praat centres frames inside the audio, wrassp/ksvF0 windows
    differently), so treat it as a practical lower bound for "worth
    analysing", not an exact guarantee.

    Mirrors ``min_audio_dur()`` in shinytone ``global.R``, including the
    fallback to the default floor of 75 Hz when ``f0_min`` is non-positive
    or not a finite number.

    Parameters
    ----------
    f0_min : float
        Pitch floor in Hz used (or planned) for extraction.

    Returns
    -------
    float
        Minimum duration in seconds, ``3 / f0_min``.
    """
    try:
        floor = float(f0_min)
    except (TypeError, ValueError):
        floor = float("nan")
    if not np.isfinite(floor) or floor <= 0:
        floor = 75.0
    return 3.0 / floor


def _resolve_engine(engine: str) -> str:
    """Map the user-facing engine choice to a concrete backend name."""
    if engine == "parselmouth":
        return "parselmouth"
    if engine == "librosa":
        return "librosa"
    if engine == "auto":
        try:
            import parselmouth  # noqa: F401
            return "parselmouth"
        except ImportError:
            try:
                import librosa  # noqa: F401
                return "librosa"
            except ImportError:
                raise ImportError(
                    "extract_f0 needs a pitch backend. Install praat-parselmouth "
                    "(recommended; Praat semantics, matches shinytone) or librosa "
                    "(pyin): 'pip install praat-parselmouth' or 'pip install librosa'."
                ) from None
    raise ValueError(
        f"engine must be 'auto', 'parselmouth' or 'librosa', got {engine!r}")


def _parselmouth_one(path, f0_min, f0_max, step_s, min_dur, with_intensity):
    """Extract one file with Praat.

    Returns ``(time, f0, intensity, None)`` on success (``intensity`` is
    None when ``with_intensity`` is false), or ``(None, None, None, dur)``
    when the file should be skipped: ``dur`` is the (too short) duration
    in seconds, or NaN when the file could not be read/analysed at all.
    """
    import parselmouth

    try:
        snd = parselmouth.Sound(path)
    except Exception:
        return None, None, None, float("nan")
    duration = snd.get_total_duration()
    if duration < min_dur:
        return None, None, None, duration
    try:
        pitch = snd.to_pitch(time_step=step_s, pitch_floor=f0_min,
                             pitch_ceiling=f0_max)
    except Exception:
        # Praat refused the file (e.g. degenerate audio): mirror shinytone,
        # which drops a ksvF0 failure with a warning and moves on.
        return None, None, None, float("nan")

    f0 = np.asarray(pitch.selected_array["frequency"], dtype=float)
    f0[f0 <= 0] = np.nan  # Praat writes 0.0 for "unvoiced" -> undefined
    t = np.asarray(pitch.xs(), dtype=float)

    db = None
    if with_intensity:
        try:
            intensity = snd.to_intensity(time_step=step_s)
            # Line the intensity track up with the pitch frames: linear
            # interpolation at the pitch frame times, ends clamped, the
            # same approximation as shinytone's approx(..., rule = 2).
            db = np.interp(t, np.asarray(intensity.xs(), dtype=float),
                           np.asarray(intensity.values[0], dtype=float))
        except Exception:
            db = np.full(t.shape, np.nan)
    return t, f0, db, None


def _librosa_one(path, f0_min, f0_max, step_s, min_dur, with_intensity):
    """Extract one file with librosa.pyin; skip/return conventions as above."""
    try:
        import librosa
    except ImportError as e:
        raise ImportError(
            "engine='librosa' requires the optional dependency librosa: "
            "'pip install librosa' (or install praat-parselmouth and use "
            "engine='parselmouth')."
        ) from e

    try:
        y, sr = librosa.load(path, sr=None)
    except Exception:
        return None, None, None, float("nan")
    duration = len(y) / float(sr)
    if duration < min_dur:
        return None, None, None, duration

    # pyin needs an analysis window covering several periods of the floor:
    # smallest power-of-two frame length at or above 4 * sr / f0_min.
    need = 4.0 * sr / float(f0_min)
    frame_length = int(2.0 ** np.ceil(np.log2(max(need, 512.0))))
    hop_length = max(1, int(round(sr * step_s)))
    try:
        f0, _voiced_flag, _voiced_prob = librosa.pyin(
            y, fmin=float(f0_min), fmax=float(f0_max), sr=sr,
            frame_length=frame_length, hop_length=hop_length)
    except Exception:
        return None, None, None, float("nan")
    f0 = np.asarray(f0, dtype=float)  # pyin already uses NaN for unvoiced
    t = np.asarray(
        librosa.times_like(f0, sr=sr, hop_length=hop_length,
                           n_fft=frame_length), dtype=float)

    # pyin has no intensity; keep the column (all NaN) so output shape is
    # stable across backends.
    db = np.full(t.shape, np.nan) if with_intensity else None
    return t, f0, db, None


def extract_f0(
    wav_paths: Union[WavPath, Sequence[WavPath]],
    f0_min: float = 75.0,
    f0_max: float = 600.0,
    step_ms: float = 10.0,
    engine: str = "auto",
    with_intensity: bool = True,
) -> pd.DataFrame:
    """Extract f0 (and optionally intensity) from .wav file(s).

    Python counterpart of the shinytone F0-extraction step: the default
    parameters ``f0_min=75``, ``f0_max=600``, ``step_ms=10`` match the R
    app's wrassp/ksvF0 defaults, and files shorter than
    ``min_audio_duration(f0_min)`` seconds are skipped rather than
    analysed, exactly like the R upload handler.

    Parameters
    ----------
    wav_paths : str, os.PathLike, or sequence of those
        One wav path or several; output rows keep the input file order.
    f0_min, f0_max : float
        Pitch floor / ceiling in Hz. The floor also sets the analysis
        window length (3 periods) and thus the shortest analysable clip.
    step_ms : float
        Frame step in milliseconds (frame centres this far apart).
    engine : {"auto", "parselmouth", "librosa"}
        "parselmouth" uses Praat via praat-parselmouth (recommended; the
        semantics documented here). "librosa" uses librosa.pyin (no
        intensity; the column is still returned, as all NaN, to keep the
        output shape stable). "auto" prefers parselmouth and falls back
        to librosa; if neither is installed, ImportError is raised with
        install hints.
    with_intensity : bool
        Include an ``intensity`` column (dB). With the parselmouth
        backend it is Praat's Intensity sampled at the pitch frame times
        by linear interpolation with clamped ends -- an alignment
        approximation (shinytone does the same with ``approx(rule = 2)``
        on an RMS track). With librosa it is all NaN.

    Returns
    -------
    pandas.DataFrame
        Long format, one row per frame: ``token`` (basename without
        extension), ``time`` (seconds, frame centres), ``f0`` (Hz; NaN on
        unvoiced frames -- never 0), and ``intensity`` (dB) when
        requested. Files skipped for being too short (or unreadable) are
        listed in ``df.attrs["skipped_files"]`` as ``(token, duration)``
        pairs; an unreadable file has NaN as its duration.

    Notes
    -----
    The input audio files are never modified.

    Reference
    ---------
    Xu, Y., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538.
    """
    step_s = float(step_ms) / 1000.0
    if not step_s > 0:
        raise ValueError(f"step_ms must be positive, got {step_ms!r}")
    if not (0 < f0_min < f0_max):
        raise ValueError(
            f"f0_min and f0_max must satisfy 0 < f0_min < f0_max, "
            f"got {f0_min!r}, {f0_max!r}")
    backend = _resolve_engine(engine)

    if isinstance(wav_paths, (str, os.PathLike)):
        paths: List[WavPath] = [wav_paths]
    else:
        paths = list(wav_paths)

    one = _parselmouth_one if backend == "parselmouth" else _librosa_one
    min_dur = min_audio_duration(f0_min)

    pieces: List[pd.DataFrame] = []
    skipped: List[Tuple[str, float]] = []
    for p in paths:
        token = os.path.splitext(os.path.basename(str(p)))[0]
        t, f0, db, skip_dur = one(str(p), f0_min=f0_min, f0_max=f0_max,
                                  step_s=step_s, min_dur=min_dur,
                                  with_intensity=with_intensity)
        if t is None:
            skipped.append((token, skip_dur))
            continue
        piece = {"token": token, "time": t, "f0": f0}
        if with_intensity:
            piece["intensity"] = db if db is not None else np.full(t.shape, np.nan)
        pieces.append(pd.DataFrame(piece))

    if pieces:
        out = pd.concat(pieces, ignore_index=True)
    else:
        data = {"token": pd.Series(dtype=object),
                "time": pd.Series(dtype=float),
                "f0": pd.Series(dtype=float)}
        if with_intensity:
            data["intensity"] = pd.Series(dtype=float)
        out = pd.DataFrame(data)

    out.attrs["skipped_files"] = skipped
    if skipped:
        too_short = [f"{name} ({dur:.3f} s)" for name, dur in skipped
                     if np.isfinite(dur)]
        failed = [name for name, dur in skipped if not np.isfinite(dur)]
        parts = []
        if too_short:
            parts.append("too short for f0 (< "
                         f"{min_dur:.3f} s): {', '.join(too_short)}")
        if failed:
            parts.append("could not be read/analysed: " + ", ".join(failed))
        warnings.warn(
            f"extract_f0 skipped {len(skipped)} file(s) -- " + "; ".join(parts),
            stacklevel=2)
    return out


def read_f0_csv(
    path,
    token: str = "token",
    time: str = "time",
    f0: str = "f0",
) -> pd.DataFrame:
    """Read a pre-extracted f0 CSV into the package's long format.

    Python counterpart of the shinytone F0-extraction step's "Upload
    existing f0 CSV" source: shinytone auto-detects likely column names
    (token/wav/filename..., time/t/timestamp..., f0/f0_hz/pitch...) and
    lets the user override them in pickers; here you name the three
    roles directly via ``token`` / ``time`` / ``f0``.

    Unvoiced frames stored as 0 Hz (the wrassp/RAPT convention) are
    normalised to NaN, matching Praat's "undefined" semantics used
    everywhere else in tone_py, so the two extraction paths produce
    interchangeable data frames.

    Parameters
    ----------
    path : str or os.PathLike
        CSV file to read.
    token, time, f0 : str
        Column names of the token ID, time (seconds) and f0 (Hz) roles.

    Returns
    -------
    pandas.DataFrame
        The CSV with ``f0`` normalised (0 -> NaN) and columns ordered
        ``[token, time, f0, ...remaining columns in file order]``.

    Reference
    ---------
    Xu, Y., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538.
    """
    df = pd.read_csv(path)
    require_columns(df, [token, time, f0], where=f"f0 CSV '{path}'")
    df[f0] = f0_to_nan(df[f0])
    rest = [c for c in df.columns if c not in (token, time, f0)]
    return df[[token, time, f0] + rest].reset_index(drop=True)

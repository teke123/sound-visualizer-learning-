"""Synthetic citation-tone f0 sample data.

Python counterpart of the shinytone F0-extraction step's *output format*,
filled with synthesised demo data: schematic Mandarin-like citation tone
contours in a semitone space around a per-speaker base pitch. Used for
examples and tests so that the rest of the package can be exercised
without any real recordings.

Reference
---------
Xu, Y., & Zhang, C. (2024). A cross-linguistic review of citation tone
production studies: Methodology and recommendations. *The Journal of the
Acoustical Society of America*, 156(4), 2538.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["make_sample_f0"]

# Schematic citation-tone templates in semitones (st) relative to the
# speaker's base pitch. Deliberately simple Mandarin-like shapes:
#   T1 high level  : constant +3 st
#   T2 mid rising  : -1 -> +2 st
#   T3 low dipping : +1 -> -2 -> 0 st (V shape, minimum at 40% of the token)
#   T4 high falling: +4 -> -3 st
# These are hand-drawn archetypes, not copies of any published contours.
_TONES = ("T1", "T2", "T3", "T4")
_T3_DIP = 0.40  # where the T3 minimum falls, as a fraction of token time


def _tone_semitones(tone: str, u: np.ndarray) -> np.ndarray:
    """Template contour in semitones; ``u`` is time scaled to [0, 1]."""
    if tone == "T1":
        return np.full(u.shape, 3.0)
    if tone == "T2":
        return -1.0 + 3.0 * u                       # -1 -> +2 st
    if tone == "T3":
        down = 1.0 - 3.0 * (u / _T3_DIP)            # +1 -> -2 st
        up = -2.0 + 2.0 * ((u - _T3_DIP) / (1.0 - _T3_DIP))  # -2 -> 0 st
        return np.where(u < _T3_DIP, down, up)
    if tone == "T4":
        return 4.0 - 7.0 * u                        # +4 -> -3 st
    raise ValueError(f"Unknown tone {tone!r}; expected one of {_TONES}")


def make_sample_f0(
    n_speakers: int = 8,
    tokens_per_tone: int = 6,
    seed: int = 42,
    fs_frame: float = 0.01,
) -> pd.DataFrame:
    """Synthesise a long-format f0 data frame of citation tones.

    Python counterpart of the shinytone F0-extraction step's output (same
    one-row-per-frame long format), filled with synthetic Mandarin-like
    citation tones -- a demo/test convenience, **not a copy of any
    published corpus**.

    Each speaker draws a base pitch uniformly from 110-230 Hz (spanning
    typical male and female voices) and produces ``tokens_per_tone``
    tokens of each of the four tones T1 (high level), T2 (mid rising),
    T3 (low dipping, V-shaped) and T4 (high falling), as semitone
    templates around that base: ``f0 = base * 2 ** (st / 12)``. Token
    durations are uniform in 0.3-0.6 s, sampled every ``fs_frame``
    seconds; Gaussian measurement noise of sd 0.3 st is added, and about
    2% of frames are randomly set to NaN to mimic unvoiced frames.

    Parameters
    ----------
    n_speakers : int
        Number of synthetic speakers ("s01" .. "sNN").
    tokens_per_tone : int
        Repetitions of each tone per speaker.
    seed : int
        Seed for :func:`numpy.random.default_rng`; same seed, same data.
    fs_frame : float
        Frame step in seconds.

    Returns
    -------
    pandas.DataFrame
        Columns ``token`` (globally unique, e.g. ``"s01_T1_03"``),
        ``speaker``, ``tone`` ("T1".."T4"), ``time`` (seconds, from 0
        within each token) and ``f0_Hz`` (positive Hz, or NaN on the
        ~2% simulated unvoiced frames).

    Reference
    ---------
    Xu, Y., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538.
    """
    rng = np.random.default_rng(seed)
    bases = rng.uniform(110.0, 230.0, size=n_speakers)
    idx_width = max(2, len(str(tokens_per_tone)))

    tokens: list = []
    speakers: list = []
    tones: list = []
    times: list = []
    f0s: list = []
    for si in range(n_speakers):
        speaker = f"s{si + 1:02d}"
        base = bases[si]
        for tone in _TONES:
            for k in range(1, tokens_per_tone + 1):
                token = f"{speaker}_{tone}_{k:0{idx_width}d}"
                duration = rng.uniform(0.3, 0.6)
                n_frames = max(2, int(round(duration / fs_frame)))
                t = np.arange(n_frames) * fs_frame
                u = t / t[-1]
                st = _tone_semitones(tone, u)
                st = st + rng.normal(0.0, 0.3, size=n_frames)  # +/-0.3 st noise
                f0 = base * 2.0 ** (st / 12.0)
                f0[rng.random(n_frames) < 0.02] = np.nan  # sporadic unvoiced
                tokens.append(token)
                speakers.append(speaker)
                tones.append(tone)
                times.append(t)
                f0s.append(f0)

    counts = [len(t) for t in times]
    return pd.DataFrame({
        "token": np.repeat(np.asarray(tokens, dtype=object), counts),
        "speaker": np.repeat(np.asarray(speakers, dtype=object), counts),
        "tone": np.repeat(np.asarray(tones, dtype=object), counts),
        "time": np.concatenate(times),
        "f0_Hz": np.concatenate(f0s),
    })

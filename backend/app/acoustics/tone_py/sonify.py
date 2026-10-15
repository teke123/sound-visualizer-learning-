"""Render an f0 contour as an audible waveform.

Port of shinytone (citationtone_hub) ``R/sonify.R`` ``sonify_f0()``. The
contour drives an oscillator whose instantaneous pitch follows the f0
values, so a mean tone contour can be *listened to* rather than only seen.
Part of the sonification pipeline of the R package behind Xu & Zhang (2024,
JASA).

The three timbres share one pitch generator and differ only in spectral
shape: "tone" is a bare sine, "complex" sums harmonics with a geometric
roll-off, and "vowel" runs a band-limited glottal buzz through a cascade of
three two-pole formant resonators (source-filter synthesis after Fant,
1960; resonator design after Klatt, 1980).

References
----------
Fant, G. (1960). *Acoustic Theory of Speech Production*. Mouton.

Klatt, D. H. (1980). Software for a cascade/parallel formant synthesiser.
*Journal of the Acoustical Society of America*, 67(3), 971-995.

Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation tone
production studies: Methodology and recommendations. *The Journal of the
Acoustical Society of America*, 156(4), 2538-2565.
"""

from __future__ import annotations

import wave as _wave

import numpy as np

# Formant centres (Hz) and bandwidths (Hz) per vowel, from sonify.R.
_FORMANTS = {
    "a": ((700.0, 1220.0, 2600.0), (110.0, 120.0, 150.0)),
    "i": ((300.0, 2300.0, 3000.0), (60.0, 100.0, 150.0)),
    "u": ((350.0, 800.0, 2400.0), (60.0, 90.0, 150.0)),
}


def _resonate(x: np.ndarray, freq: float, bw: float, fs: float) -> np.ndarray:
    """One two-pole resonator: y[n] = x[n] + 2 r cos(theta) y[n-1] - r^2 y[n-2].

    Resonance at ``theta = 2*pi*F/fs`` with pole radius
    ``r = exp(-pi*BW/fs)`` (Klatt, 1980). Implemented as an explicit
    sample loop, matching R's ``stats::filter(..., method = "recursive")``.
    """
    r = np.exp(-np.pi * bw / fs)
    theta = 2.0 * np.pi * freq / fs
    a1 = 2.0 * r * np.cos(theta)
    a2 = -(r * r)
    y1 = 0.0
    y2 = 0.0
    out = np.empty_like(x)
    for i in range(x.shape[0]):
        yi = x[i] + a1 * y1 + a2 * y2
        out[i] = yi
        y2 = y1
        y1 = yi
    return out


def sonify_f0(f0_hz, fs: float = 16000, dur: float = 0.7,
              source: str = "tone", vowel: str = "a",
              n_harmonics: int = 12, rolloff: float = 0.7,
              fade: float = 0.02, amp: float = 0.9,
              intensity=None, dyn_range: float = 30) -> np.ndarray:
    """Sonify an f0 contour: a float waveform whose pitch follows ``f0_hz``.

    Port of shinytone ``sonify_f0()`` (part of the toolkit accompanying
    Xu & Zhang 2024, JASA; vowel source-filter synthesis after Fant 1960
    and Klatt 1980).

    The contour has no inherent duration, so it is time-scaled to ``dur``
    seconds. Pitch is rendered by phase accumulation
    (``phase = cumsum(2*pi*f0/fs)``), so the glide is smooth.

    Parameters
    ----------
    f0_hz : Sequence of f0 values in Hz. Leading and trailing non-finite
        values are trimmed; internal gaps are linearly interpolated.
    fs : Output sample rate in Hz. Default 16000.
    dur : Playback duration in seconds. Default 0.7.
    source : "tone" (pure sine), "complex" (sine plus harmonics with
        amplitude roll-off), or "vowel" (glottal source through three
        formant resonators). Pitch is identical across the three.
    vowel : Vowel quality for ``source="vowel"``: "a", "i" or "u".
    n_harmonics : Number of harmonics for "complex".
    rolloff : Per-harmonic amplitude factor for "complex" (0-1).
    fade : Raised-cosine fade in/out duration in seconds (anti-click).
    amp : Peak amplitude of the returned waveform.
    intensity : Optional per-frame intensity in dB, aligned to the f0
        frames (same length as ``f0_hz``, or as the trimmed contour).
        The waveform's loudness then follows it, floored at ``dyn_range``
        dB below the peak; non-finite intensities are floored to the
        minimum measured value.
    dyn_range : Loudness range in dB when ``intensity`` is used.

    Returns
    -------
    Float ndarray of length ``round(fs * dur)`` (at least 2), peak
    normalised to ``amp``. Use :func:`write_wav` to write it to disk.

    Raises
    ------
    ValueError
        When fewer than 2 finite values are given, or on an unknown
        ``source`` / ``vowel``.
    """
    if source not in ("tone", "complex", "vowel"):
        raise ValueError("source must be one of 'tone', 'complex', 'vowel'")
    if vowel not in _FORMANTS:
        raise ValueError("vowel must be one of 'a', 'i', 'u'")
    f0 = np.asarray(f0_hz, dtype=float).ravel()

    fin = np.flatnonzero(np.isfinite(f0))
    if fin.size < 2:
        raise ValueError("`f0_hz` needs at least 2 finite values.")
    keep = np.arange(fin[0], fin[-1] + 1)

    # Align an optional intensity envelope to the trimmed f0 frames.
    iv = None
    if intensity is not None:
        iv = np.asarray(intensity, dtype=float).ravel()
        if iv.size == f0.size:
            iv = iv[keep]
        elif iv.size == keep.size:
            pass                       # already trimmed-length
        else:
            iv = None                  # unusable length: flat amplitude

    f0 = f0[keep]                      # trim leading/trailing NA
    gap = ~np.isfinite(f0)
    if gap.any():                      # fill internal gaps linearly
        ok = np.flatnonzero(~gap)
        f0 = f0.copy()
        f0[gap] = np.interp(np.flatnonzero(gap), ok, f0[ok])

    n = max(2, int(round(fs * dur)))
    cont = np.interp(np.linspace(0.0, 1.0, n),
                     np.linspace(0.0, 1.0, f0.size), f0)
    cont = np.clip(cont, 40.0, 2000.0)  # keep in a sane audible band

    phase = np.cumsum(2.0 * np.pi * cont / fs)
    if source == "tone":
        w = np.sin(phase)
    elif source == "complex":
        # Cap harmonics so the highest stays below the Nyquist frequency.
        nh = max(1, min(int(n_harmonics),
                        int(np.floor((fs / 2.0) / cont.max()))))
        w = np.zeros(n)
        for h in range(1, nh + 1):
            w += (rolloff ** (h - 1)) * np.sin(h * phase)
    else:                              # vowel: source-filter synthesis
        nh = max(1, min(30, int(np.floor((fs / 2.0) / cont.max()))))
        w = np.zeros(n)
        for h in range(1, nh + 1):     # band-limited glottal source, 1/h tilt
            w += (1.0 / h) * np.sin(h * phase)
        centres, bws = _FORMANTS[vowel]
        for f_c, bw in zip(centres, bws):   # cascade of 2-pole resonators
            w = _resonate(w, f_c, bw, fs)
        w[~np.isfinite(w)] = 0.0

    if iv is not None and np.isfinite(iv).any():   # shape loudness by dB
        ivf = iv.astype(float, copy=True)
        ivf[~np.isfinite(ivf)] = np.min(ivf[np.isfinite(ivf)])
        env = np.interp(np.linspace(0.0, 1.0, n),
                        np.linspace(0.0, 1.0, ivf.size), ivf)
        rel = np.maximum(env - env.max(), -abs(dyn_range))
        w = w * 10.0 ** (rel / 20.0)

    nf = min(n // 2, max(1, int(round(fs * fade))))   # raised-cosine fade
    if nf >= 1:
        ramp = (1.0 - np.cos(np.pi * np.arange(1, nf + 1) / nf)) / 2.0
        w[:nf] *= ramp
        w[n - nf:] *= ramp[::-1]

    m = np.max(np.abs(w))
    if m > 0:
        w = w / m * amp
    return w


def write_wav(path, wave, fs: float = 16000):
    """Write a float waveform as a 16-bit mono WAV file.

    Companion to :func:`sonify_f0`, mirroring the R function's
    ``tuneR::Wave(..., bit = 16)`` output step: values are clipped to
    [-1, 1], scaled to 16-bit integers (``round(x * 32767)``) and written
    with the standard-library ``wave`` module. Returns the path written.
    """
    w = np.asarray(wave, dtype=float).ravel()
    pcm = np.round(np.clip(w, -1.0, 1.0) * 32767.0).astype("<i2")
    with _wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(int(fs))
        fh.writeframes(pcm.tobytes())
    return str(path)

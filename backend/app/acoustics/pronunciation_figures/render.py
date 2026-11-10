"""把统一时间轴上的声学测量绘制为六类复合图。"""
from __future__ import annotations

from io import BytesIO
from threading import RLock

import numpy as np

from app.acoustics.imagery.common import setup_matplotlib
from app.acoustics.f0_pipeline import hz_to_degree
from .measure import Analysis, SR

_LOCK = RLock()
FORMANT_COLORS = ("#0066cc", "#cc0000", "#008844")
NAMES = {
    "overview": "P01_overview_prosody.png",
    "tone_vowel": "P02_tone_vowel_norm.png",
    "plosive": "P03_plosive_affricate.png",
    "sibilant": "P04_sibilant_spectrum.png",
    "nasal": "P05_nasal_dynamics.png",
    "approximant": "P06_approximant_transition.png",
}


def available_kinds(a: Analysis) -> list[str]:
    classes = {s["initial_class"] for s in a.syllables}
    kinds = ["overview", "tone_vowel"]
    if classes & {"stop", "affricate"}:
        kinds.append("plosive")
    if classes & {"fricative", "affricate"}:
        kinds.append("sibilant")
    if "nasal" in classes or any(s["nasal_coda"] for s in a.syllables):
        kinds.append("nasal")
    if classes & {"lateral", "approximant"}:
        kinds.append("approximant")
    return kinds


def select_kinds(a: Analysis, goal: str = "general", limit: int = 4) -> list[str]:
    available = available_kinds(a)
    priorities = {
        "general": ["overview", "tone_vowel", "plosive", "sibilant", "nasal", "approximant"],
        "tone": ["overview", "tone_vowel"],
        "vowel": ["overview", "tone_vowel", "nasal"],
        "initial": ["overview", "plosive", "sibilant", "nasal", "approximant"],
        "nasal": ["overview", "nasal", "tone_vowel"],
    }
    return [k for k in priorities.get(goal, priorities["general"]) if k in available][:limit]


def _spec(ax, a, origin, end, top=5000):
    t, f, db = a.spectrogram
    ax.pcolormesh(t-origin, f/1000, db, cmap="Greys", vmin=-50, vmax=0,
                  shading="nearest", rasterized=True)
    ax.set(xlim=(0, end-origin), ylim=(0, min(top, a.bandwidth_hz)/1000), ylabel="频率 (kHz)")


def _formants(ax, a, t0, t1, origin, count=3):
    mask = (a.formant_t >= t0) & (a.formant_t <= t1)
    for k in range(count):
        x = a.formant_t[mask]-origin
        y = a.formants[k, mask]/1000
        ax.plot(x, y, color=FORMANT_COLORS[k], lw=2.2)
        valid = np.flatnonzero(np.isfinite(y))
        if len(valid):
            ax.annotate(f"F{k+1}", (x[valid[-1]], y[valid[-1]]), xytext=(4, 0),
                        textcoords="offset points", color=FORMANT_COLORS[k], weight="bold")


def _event_lines(ax, s, origin):
    c = s["consonant"] or {}
    nasal = s["nasal_coda"] or {}
    events = ((c.get("release_s"), "除阻", "#a35b00"),
              (c.get("frication_end_s"), "摩擦结束", "#865f9c"),
              (c.get("voicing_onset_s"), "浊音起点", "#12805a"),
              (nasal.get("murmur_t0"), "鼻音起点", "#7856a9"))
    for time, label, color in events:
        if time is not None:
            ax.axvline(time-origin, color=color, lw=1.4, ls="--")
    return [(time-origin, label, color) for time, label, color in events if time is not None]


def _phases(ax, s, origin, end):
    timeline = s["timeline"]
    c = s["consonant"] or {}
    start = timeline["syllable_start_s"]
    release = c.get("release_s")
    friction = c.get("frication_end_s")
    voice = c.get("voicing_onset_s") or timeline["vowel_start_s"]
    nasal = timeline["nasal_start_s"]
    spans = []
    if release and release > start:
        spans.append((start, release, "闭塞", "#8b9aa4"))
    if release and friction and friction > release:
        spans.append((release, friction, "摩擦", "#dfbb74"))
    if friction and voice > friction:
        spans.append((friction, voice, "送气", "#d7b8dc"))
    elif release and voice > release and not friction:
        spans.append((release, voice, "起声间隔", "#f0c789"))
    if nasal:
        spans.extend(((voice, nasal, "元音", "#b7d8d0"), (nasal, end, "鼻尾", "#c6b3d8")))
    elif voice < end:
        spans.append((voice, end, "元音", "#b7d8d0"))
    for left, right, label, color in spans:
        if right <= left:
            continue
        ax.axvspan(left-origin, right-origin, ymin=.94, ymax=1, color=color, alpha=.75)
        if right-left >= .045:
            ax.text((left+right)/2-origin, .97, label, ha="center", va="center",
                    transform=ax.get_xaxis_transform(), fontsize=10)


def _overview(fig, a):
    axes = fig.subplots(3, 1, sharex=True, gridspec_kw={"height_ratios": [1, 2, 1.2]})
    ax_wave, ax_spec, ax_tone = axes
    origin, end = a.speech_t0, a.speech_t1
    t = np.arange(len(a.rec.x))/SR
    mask = (t >= origin) & (t <= end)
    ax_wave.plot(t[mask]-origin, a.rec.x[mask], color="#303940", lw=.7)
    ax_wave.set_ylabel("振幅")
    level_ax = ax_wave.twinx()
    level_ax.plot(a.level_t-origin, a.level_db, color="#cc6743", lw=1.5, alpha=.8)
    level_ax.set(ylabel="相对强度 (dB)", ylim=(-60, 12))
    _spec(ax_spec, a, origin, end)
    for s in a.syllables:
        syl = a.aln.syllables[s["index"]]
        for phone in (s["initial"], s["final"]):
            if phone:
                ax_wave.text((phone["t0"]+phone["t1"])/2-origin, 1.09,
                             f'{phone["label"]} [{phone["ipa"]}] {phone["duration_ms"]:.0f} ms',
                             ha="center", transform=ax_wave.get_xaxis_transform(), fontsize=10)
                ax_spec.axvline(phone["t0"]-origin, color="#ac5b82", ls=":", lw=1.2)
        ax_spec.axvline(s["final"]["t1"]-origin, color="#ac5b82", ls=":", lw=1.2)
        ax_wave.text((syl.t0+syl.t1)/2-origin, 1.24, f'{s["text"]} {s["symbol"]}',
                     ha="center", transform=ax_wave.get_xaxis_transform(), fontsize=11, weight="bold")
        _phases(ax_spec, s, origin, s["voicing_end_s"])
        _event_lines(ax_spec, s, origin)
        v = s["vowel"]
        _formants(ax_spec, a, v["t0"], v["t1"], origin)
        frames = s["_tone_frames"]
        x = np.asarray([fr["t"]-origin for fr in frames])
        y = np.asarray([fr["degree"] if fr["degree"] is not None else np.nan for fr in frames])
        ax_tone.plot(x, y, color="#bb2026", lw=2)
        for left, right in s["timeline"]["creaky_intervals_s"]:
            ax_spec.axvspan(left-origin, right-origin, color="#c58c9d", alpha=.13)
    ax_tone.set(ylabel="五度值", xlabel="相对语音起点 (s)", ylim=(.5, 5.5), yticks=[1, 2, 3, 4, 5])
    lo, hi = a.f0_range
    other = ax_tone.secondary_yaxis("right", functions=(lambda degree: np.exp(np.log(lo)+(np.asarray(degree)-1)/4*np.log(hi/lo)),
                                                       lambda hz: hz_to_degree(hz, lo, hi)))
    other.set_ylabel("基频 (Hz)")
    ax_tone.set_xlim(0, end-origin)


def _tone_vowel(fig, a, reference=None):
    axes = fig.subplots(len(a.syllables), 2, squeeze=False)
    space = a.rec.vowel_norm or {}
    anchors = [(key, space.get(key)) for key in ("i", "ü", "a", "u")]
    for row, s in enumerate(a.syllables):
        tone_ax, vowel_ax = axes[row]
        tone = s["tone"]
        positions = np.linspace(0, 100, 21)
        tone_ax.plot(positions, np.asarray(tone["contour_degree"], float), color="#bb2026", lw=2.4)
        if reference:
            rs = reference.syllables[row]["tone"]
            tone_ax.plot(positions, np.asarray(rs["contour_degree"], float), color="#718095", ls="--", lw=2)
        tone_ax.set(xlim=(0, 100), ylim=(.5, 5.5), yticks=[1, 2, 3, 4, 5],
                    xlabel="音节区间 (%)", ylabel="五度值",
                    title=f'{s["symbol"]} · 调值 {tone["chao"] or ""}')
        tone_ax.text(.03, .04, f'音域 {a.f0_range[0]:.0f}–{a.f0_range[1]:.0f} Hz',
                     transform=tone_ax.transAxes, fontsize=11)
        xy = [(p["f2Mean"], p["f1Mean"]) for _, p in anchors if p and "f2Mean" in p and "f1Mean" in p]
        if len(xy) == 4:
            polygon = np.asarray(xy + [xy[0]])
            vowel_ax.plot(polygon[:, 0], polygon[:, 1], color="#9299a0", ls="--", lw=1.5)
            for (name, _), (x, y) in zip(anchors, xy):
                vowel_ax.annotate(name, (x, y), xytext=(4, 4), textcoords="offset points", color="#59636b")
        f1 = np.asarray(s["vowel"]["F1_hz"], float)
        f2 = np.asarray(s["vowel"]["F2_hz"], float)
        if s["final_type"] == "monophthong":
            f1 = f1.copy(); f2 = f2.copy()
            f1[:3] = np.nan; f1[8:] = np.nan
            f2[:3] = np.nan; f2[8:] = np.nan
        vowel_ax.plot(f2, f1, color="#bb2026", lw=2.4)
        valid = np.flatnonzero(np.isfinite(f1) & np.isfinite(f2))
        if len(valid):
            vowel_ax.plot(f2[valid[0]], f1[valid[0]], "o", color="#bb2026", ms=7)
        if len(valid) > 1:
            vowel_ax.annotate("", xy=(f2[valid[-1]], f1[valid[-1]]),
                              xytext=(f2[valid[-2]], f1[valid[-2]]),
                              arrowprops={"arrowstyle": "->", "color": "#bb2026", "lw": 2.2})
        vowel_ax.set(xlim=(3300, 500), ylim=(1200, 200), xlabel="F2 (Hz)", ylabel="F1 (Hz)", title="个人元音空间")


def _plosive(fig, a):
    indices = [i for i, s in enumerate(a.syllables) if s["initial_class"] in {"stop", "affricate"}]
    axes = fig.subplots(3*len(indices), 1, squeeze=False)[:, 0]
    for row, i in enumerate(indices):
        s = a.syllables[i]
        c = s["consonant"] or {}
        origin = c.get("release_s") or a.aln.syllables[i].t0
        end = min(a.duration, max(c.get("voicing_onset_s") or origin+.10, origin+.10) + .05)
        left = max(0, origin-.03)
        ax_wave, ax_spec, ax_band = axes[row*3:row*3+3]
        t = np.arange(len(a.rec.x))/SR
        mask = (t >= left) & (t <= end)
        ax_wave.plot((t[mask]-origin)*1000, a.rec.x[mask], color="#303940", lw=.8)
        details = [s["symbol"]]
        for key, label in (("vot_ms", "VOT"), ("closure_ms", "闭塞"),
                           ("frication_ms", "摩擦"), ("aspiration_ms", "送气"),
                           ("noise_rise_ms", "上升")):
            if c.get(key) is not None:
                details.append(f'{label} {c[key]:.0f} ms')
        ax_wave.set(ylabel="振幅", title=" · ".join(details))
        t_spec, f_spec, db_spec = a.spectrogram
        ax_spec.pcolormesh((t_spec-origin)*1000, f_spec/1000, db_spec, cmap="Greys", vmin=-50, vmax=0,
                           shading="nearest", rasterized=True)
        ax_spec.set(ylabel="频率 (kHz)", ylim=(0, min(12, a.bandwidth_hz/1000)))
        from .measure import _band_level, _grid
        bt = _grid(left, end, .002)
        high = _band_level(a.rec.x, bt, .010, (2500, min(10000, a.bandwidth_hz)))
        mid = _band_level(a.rec.x, bt, .010, (800, 2500))
        peak = max(high.max(), mid.max())
        ax_band.plot((bt-origin)*1000, high-peak, color="#bf6b1e", lw=2, label="高频摩擦")
        ax_band.plot((bt-origin)*1000, mid-peak, color="#3e708f", ls="--", lw=2, label="中频气流")
        ax_band.set(ylabel="相对电平 (dB)", ylim=(-65, 5),
                    xlabel="相对除阻时间 (ms)" if c.get("release_s") is not None else "相对音节起点 (ms)")
        ax_band.legend(loc="lower right")
        phases = []
        release = c.get("release_s")
        friction = c.get("frication_end_s")
        voice = c.get("voicing_onset_s")
        if release is not None and release > left:
            phases.append((left, release, "闭塞", "#8b9aa4"))
        if release is not None and friction is not None:
            phases.append((release, friction, "摩擦", "#dfbb74"))
            if voice is not None:
                phases.append((friction, voice, "送气", "#d7b8dc"))
        elif release is not None and voice is not None:
            phases.append((release, voice, "起声间隔", "#f0c789"))
        if voice is not None:
            phases.append((voice, end, "元音", "#b7d8d0"))
        for start, stop, label, color in phases:
            if stop <= start:
                continue
            x0, x1 = (start-origin)*1000, (stop-origin)*1000
            ax_spec.axvspan(x0, x1, ymin=.94, ymax=1, color=color, alpha=.75)
            if x1-x0 >= 25:
                ax_spec.text((x0+x1)/2, .97, label, ha="center", va="center",
                             transform=ax_spec.get_xaxis_transform(), fontsize=10)
        for ax in (ax_wave, ax_spec, ax_band):
            for key, color in (("release_s", "#a35b00"), ("frication_end_s", "#865f9c"), ("voicing_onset_s", "#12805a")):
                if c.get(key) is not None:
                    ax.axvline((c[key]-origin)*1000, color=color, ls="--", lw=1.4)
            ax.set_xlim((left-origin)*1000, (end-origin)*1000)


def _sibilant(fig, a):
    indices = [i for i, s in enumerate(a.syllables) if s["initial_class"] in {"fricative", "affricate"}]
    axes = fig.subplots(len(indices), 1, squeeze=False)[:, 0]
    for ax, i in zip(axes, indices):
        s = a.syllables[i]
        spec = (s["consonant"] or {}).get("spectrum")
        if spec:
            freqs, db = a.spectra[i]
            band = (freqs >= spec["band_hz"][0]) & (freqs <= spec["band_hz"][1])
            ax.plot(freqs[band]/1000, db[band], color="#bb2026", lw=2.3)
            ax.axvline(spec["cog_hz"]/1000, color="#0066cc", lw=1.8)
            ax.axvline(spec["peak_hz"]/1000, color="#008844", ls="--", lw=1.8)
            ax.axvspan((spec["cog_hz"]-spec["sd_hz"])/1000,
                       (spec["cog_hz"]+spec["sd_hz"])/1000, color="#0066cc", alpha=.08)
            ax.text(.02, .06, f'重心 {spec["cog_hz"]:.0f} Hz · 标准差 {spec["sd_hz"]:.0f} Hz\n'
                                f'偏度 {spec["skewness"]:.2f} · 峰度 {spec["kurtosis"]:.2f}\n'
                                f'谱峰 {spec["peak_hz"]:.0f} Hz · 相对元音 {spec["level_rel_vowel_db"]} dB',
                    transform=ax.transAxes, va="bottom", fontsize=11)
        ax.set(xlim=(1.5, a.bandwidth_hz/1000), ylim=(-63, 3), xlabel="频率 (kHz)",
               ylabel="相对峰值 (dB)", title=s["symbol"])


def _nasal(fig, a):
    indices = [i for i, s in enumerate(a.syllables) if s["initial_class"] == "nasal" or s["nasal_coda"]]
    axes = fig.subplots(2*len(indices), 1, squeeze=False)[:, 0]
    for row, i in enumerate(indices):
        s = a.syllables[i]
        syll = a.aln.syllables[i]
        origin, end = syll.t0, s["voicing_end_s"]
        upper, lower = axes[row*2:row*2+2]
        _spec(upper, a, origin, end, top=4000)
        _formants(upper, a, s["vowel"]["t0"], s["vowel"]["t1"], origin)
        nasal = s["nasal_coda"] or {}
        if s["initial_class"] == "nasal":
            upper.axvspan(0, syll.initial.t1-origin, color="#9973ae", alpha=.15)
            upper.axvspan(0, syll.initial.t1-origin, ymin=.94, ymax=1, color="#9973ae", alpha=.65)
            upper.text((syll.initial.t1-origin)/2, .97, "鼻声母", ha="center", va="center",
                       transform=upper.get_xaxis_transform(), fontsize=10)
        if nasal.get("murmur_t0") is not None:
            upper.axvspan(nasal["murmur_t0"]-origin, end-origin, color="#9973ae", alpha=.15)
            upper.axvspan(nasal["murmur_t0"]-origin, end-origin, ymin=.94, ymax=1,
                          color="#9973ae", alpha=.65)
            upper.text((nasal["murmur_t0"]+end)/2-origin, .97,
                       f'鼻尾 {nasal["murmur_ms"]:.0f} ms', ha="center", va="center",
                       transform=upper.get_xaxis_transform(), fontsize=10)
        _event_lines(upper, s, origin)
        upper.set_title(s["symbol"])
        series = s.get("nasal_dynamics")
        if series:
            x = np.asarray(series["time_s"])-origin
            lower.plot(x, np.asarray([v if v is not None else np.nan for v in series["A1_minus_P0_db"]]),
                       color="#0066cc", lw=2, label="A1−P0")
            lower.plot(x, series["mid_minus_low_db"], color="#cc0000", lw=2, label="中频−低频")
            lower.legend(loc="lower left")
        if nasal.get("F2_change_hz") is not None:
            upper.text(.02, .04, f'ΔF2 {nasal["F2_change_hz"]:+.0f} Hz · '
                                   f'斜率 {nasal["F2_slope_hz_per_ms"]:+.2f} Hz/ms',
                       transform=upper.transAxes, fontsize=11)
            vowel = s["vowel"]
            midpoint = .5*(vowel["t0"] + vowel["t1"]) - origin
            before_nasal = vowel["t1"] - origin - .010
            upper.annotate("", xy=(before_nasal, nasal["F2_before_murmur_hz"]/1000),
                           xytext=(midpoint, nasal["F2_vowel_mid_hz"]/1000),
                           arrowprops={"arrowstyle": "-|>", "color": FORMANT_COLORS[1], "lw": 2.5})
        lower.set(xlim=(0, end-origin), ylabel="频带差 (dB)", xlabel="相对音节起点 (s)")


def _approximant(fig, a):
    indices = [i for i, s in enumerate(a.syllables) if s["initial_class"] in {"lateral", "approximant"}]
    axes = fig.subplots(2*len(indices), 1, squeeze=False)[:, 0]
    for row, i in enumerate(indices):
        s = a.syllables[i]
        syll = a.aln.syllables[i]
        c = s["consonant"]
        origin = syll.t0
        end = min(a.duration, s["vowel"]["t0"] + .5*s["vowel"]["duration_ms"]/1000 + .05)
        upper, lower = axes[row*2:row*2+2]
        _spec(upper, a, origin, end)
        _formants(upper, a, origin, end, origin)
        upper.axvline(syll.initial.t1-origin, color="#8e5e7c", ls="--", lw=1.4)
        upper.set_title(s["symbol"])
        key = "F3_min_hz" if syll.initial.label == "r" else "F1_boundary_change_hz"
        label = "F3 谷值" if syll.initial.label == "r" else "ΔF1"
        if c.get(key) is not None:
            upper.text(.02, .04, f'{label} {c[key]:.0f} Hz', transform=upper.transAxes)
        data = c["transition"]
        x = np.asarray(data["time_s"])-origin
        hnr = np.asarray([v if v is not None else np.nan for v in data["hnr_db"]])
        lower.plot(x, hnr, color="#0066cc", lw=2, label="谐噪比")
        lower.plot(x, data["high_frequency_db"], color="#cc0000", lw=2, label="高频电平")
        lower.legend(loc="lower left")
        lower.set(xlim=(0, end-origin), ylabel="电平 (dB)", xlabel="相对音节起点 (s)")


def render(learner: Analysis, reference: Analysis | None = None, *, kinds=None) -> dict[str, bytes]:
    kinds = available_kinds(learner) if kinds is None else kinds
    output = {}
    with _LOCK:
        plt = setup_matplotlib()
        with plt.rc_context({"font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12}):
            for kind in kinds:
                rows = max(1, len(learner.syllables))
                size = (12, {"overview": 8, "tone_vowel": 4.5*rows,
                             "plosive": 8*rows, "sibilant": 5*rows,
                             "nasal": 7*rows, "approximant": 7*rows}[kind])
                fig = plt.figure(figsize=size, layout="constrained")
                try:
                    if kind == "overview": _overview(fig, learner)
                    elif kind == "tone_vowel": _tone_vowel(fig, learner, reference)
                    elif kind == "plosive": _plosive(fig, learner)
                    elif kind == "sibilant": _sibilant(fig, learner)
                    elif kind == "nasal": _nasal(fig, learner)
                    else: _approximant(fig, learner)
                    fig.suptitle({"overview": "语谱与韵律", "tone_vowel": "声调与元音空间",
                                  "plosive": "塞音与塞擦音", "sibilant": "摩擦频谱",
                                  "nasal": "鼻音动态", "approximant": "边音与 r 过渡"}[kind])
                    buf = BytesIO()
                    fig.savefig(buf, dpi=110, format="png")
                    output[NAMES[kind]] = buf.getvalue()
                finally:
                    plt.close(fig)
    return output

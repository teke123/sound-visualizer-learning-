"""个人标定会话：单条验收一致性判定、稳态区测量与 vowel_space 无对齐入口。

运行：backend/ 目录下 `py -3 test_calibration_sessions.py`（或 pytest）。
语料使用仓库自带开发集 docs/声学图像提取/样本。
"""
from __future__ import annotations

import sys
import types
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from app.db import JSONText  # noqa: E402
from app.acoustics.imagery.common import read_mono  # noqa: E402
from app.acoustics.pronunciation_figures.vowel_space import (  # noqa: E402
    calibrate_personal_vowel_space, measure_vowel_take, voiced_steady_interval,
)
from app.scoring import calibration_sessions as cs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'docs' / '声学图像提取' / '样本' / 'FV1'
SR = 44100


def take_row(vowel: str, ordinal: int, f1: float, f2: float, status: str = "accepted"):
    """构造会话单条录音的鸭子类型替身（_next_task/_vowel_outcome 只读这些字段）。"""
    return types.SimpleNamespace(
        kind="vowel", vowel=vowel, status=status, ordinal=ordinal, audio_id=f"au_{vowel}{ordinal}",
        result=JSONText.dump({"ok": True, "f1": f1, "f2": f2, "f3": 3000.0,
                              "nFrames": 40, "voicedSec": 0.8,
                              "steady": [0.2, 0.6], "ceiling": 5500.0}),
    )


# ---------------- 一致性判定 ----------------

def test_pair_consistency_thresholds():
    same = {"f1": 300.0, "f2": 2300.0}
    assert cs._pair_consistent(same, dict(same))
    # F1 差 20% > 15%
    assert not cs._pair_consistent(same, {"f1": 360.0, "f2": 2300.0})
    # F2 差 12% > 10%
    assert not cs._pair_consistent(same, {"f1": 300.0, "f2": 2600.0})
    # F1 差 10%、F2 差 5% → 通过
    assert cs._pair_consistent(same, {"f1": 330.0, "f2": 2420.0})


def test_consistent_pair_selects_closest():
    measurements = [
        {"f1": 300.0, "f2": 2300.0},   # 0
        {"f1": 800.0, "f2": 1200.0},   # 1 离群
        {"f1": 320.0, "f2": 2330.0},   # 2 与 0 最近
    ]
    assert cs._consistent_pair(measurements) == (0, 2)
    assert cs._consistent_pair([{"f1": 300.0, "f2": 2300.0}]) is None
    dispersed = [
        {"f1": 800.0, "f2": 1200.0},
        {"f1": 1000.0, "f2": 1100.0},
        {"f1": 3000.0, "f2": 300.0},   # 离群
    ]
    assert cs._consistent_pair(dispersed) is None
    assert cs._most_dispersed(dispersed) == 2


# ---------------- 会话任务推进 ----------------

def _done_vowel(vowel: str):
    return (take_row(vowel, 1, 300.0, 2300.0), take_row(vowel, 2, 310.0, 2330.0))


def test_next_task_order():
    takes = [*_done_vowel("i"), *_done_vowel("u"), *_done_vowel("a")]
    next_task = cs._next_task(list(takes) + [take_row("ü", 1, 300.0, 800.0)])
    assert next_task == {"kind": "vowel", "vowel": "ü", "ordinal": 2}

    takes = [*_done_vowel("i"), *_done_vowel("u"), *_done_vowel("a"), *_done_vowel("ü")]
    assert cs._next_task(takes) == {"kind": "pitch"}
    pitch = types.SimpleNamespace(kind="pitch", vowel=None, status="accepted",
                                  ordinal=1, audio_id="au_p",
                                  result=JSONText.dump({"fLo": 100.0, "fHi": 300.0}))
    assert cs._next_task(takes + [pitch]) is None


def test_next_task_additional_take_and_dispersed():
    inconsistent = [take_row("i", 1, 300.0, 2300.0), take_row("i", 2, 800.0, 1200.0)]
    assert cs._next_task(inconsistent) == {
        "kind": "vowel", "vowel": "i", "ordinal": 3, "additionalTake": True}
    three = inconsistent + [take_row("i", 3, 1500.0, 700.0)]
    assert cs._next_task(three) == {
        "kind": "vowel", "vowel": "i", "ordinal": 4, "additionalTake": False}


# ---------------- _vowel_outcome（需要 db） ----------------

@pytest.fixture()
def db(tmp_path):
    from app.db import Base, engine_for
    from app import models_registry  # noqa: F401
    from sqlalchemy.orm import sessionmaker

    eng = engine_for(tmp_path / "calib.db")
    Base.metadata.create_all(eng)
    maker = sessionmaker(bind=eng, expire_on_commit=False)
    session = maker()
    yield session
    session.close()


def test_vowel_outcome_retires_outlier(db):
    from app.db import now as db_now
    from app.scoring.models import CalibrationSessionRow

    session = CalibrationSessionRow(id="cal_test", user_id="u1", text_version="v1",
                                    passage_text="t", passage_pinyin="[]",
                                    status="active", calc_state="idle",
                                    created_at=db_now(), updated_at=db_now())
    db.add(session)
    db.commit()
    rows = [take_row("i", 1, 300.0, 2300.0), take_row("i", 2, 800.0, 1200.0),
            take_row("i", 3, 320.0, 2330.0)]
    db.add_all([_real_take(session.id, r) for r in rows])
    db.commit()

    outcome = cs._vowel_outcome(db, session, rows[2])
    assert outcome == "accepted"
    statuses = {r.audio_id: r.status for r in db.query(cs.CalibrationTakeRow).all()}
    assert statuses["au_i1"] == "accepted"   # 一致对 (i1, i3) 保留
    assert statuses["au_i2"] == "replaced"   # 未参与锚点的离群条退场
    assert statuses["au_i3"] == "accepted"


def _real_take(session_id: str, stub) -> object:
    from app.scoring.models import CalibrationTakeRow
    from app.db import now as db_now

    return CalibrationTakeRow(session_id=session_id, audio_id=stub.audio_id,
                              kind=stub.kind, vowel=stub.vowel,
                              ordinal=stub.ordinal, status="accepted",
                              result=stub.result, created_at=db_now())


def test_vowel_outcome_dispersed_replaces_worst(db):
    from app.db import now as db_now
    from app.scoring.models import CalibrationSessionRow

    session = CalibrationSessionRow(id="cal_test2", user_id="u1", text_version="v1",
                                    passage_text="t", passage_pinyin="[]",
                                    status="active", calc_state="idle",
                                    created_at=db_now(), updated_at=db_now())
    db.add(session)
    rows = [take_row("a", 1, 800.0, 1200.0), take_row("a", 2, 1000.0, 950.0),
            take_row("a", 3, 3000.0, 300.0)]
    db.add_all([_real_take(session.id, r) for r in rows])
    db.commit()
    outcome = cs._vowel_outcome(db, session, rows[2])
    assert outcome == "vowel_dispersed"
    statuses = {r.audio_id: r.status for r in db.query(cs.CalibrationTakeRow).all()}
    assert statuses["au_a3"] == "replaced"   # 与其它录音差异总和最大
    assert statuses["au_a1"] == "accepted"
    assert statuses["au_a2"] == "accepted"


# ---------------- 稳态区测量与无对齐 vowel_space ----------------

def test_voiced_steady_interval():
    times = np.arange(0, 1.0, 0.01)
    f0 = np.full(times.shape, np.nan)
    f0[10:80] = 200.0            # 0.1–0.79 s 连续有声
    track = types.SimpleNamespace(times=times, f0=f0)
    steady = voiced_steady_interval(track)
    assert steady is not None
    assert steady[0] == pytest.approx(0.1 + 0.3 * 0.69, abs=1e-6)
    assert steady[1] == pytest.approx(0.1 + 0.7 * 0.69, abs=1e-6)
    short = types.SimpleNamespace(times=times,
                                  f0=np.where((times > 0.1) & (times < 0.2), 200.0, np.nan))
    assert voiced_steady_interval(short) is None


@pytest.fixture(scope="module")
def yi1_path():
    return CORPUS / "yi1_FV1.wav"


def test_measure_vowel_take_on_real_corpus(yi1_path):
    result = measure_vowel_take(yi1_path)
    assert result["ok"], result
    assert result["nFrames"] >= 5
    assert 0 < result["f1"] < 1200 and 800 < result["f2"] < 3500
    assert result["steady"][0] < result["steady"][1]


def test_measure_vowel_take_rejects_silence(tmp_path):
    path = tmp_path / "sil.wav"
    with wave.open(str(path), "wb") as w:
        w.setparams((1, 2, SR, 0, "NONE", "not compressed"))
        w.writeframes(np.zeros(SR // 2, dtype="<i2").tobytes())
    result = measure_vowel_take(path)
    assert not result["ok"]


def test_personal_vowel_space_multi_take(yi1_path):
    """同一条录音两条等权参与：锚点跨录音标准差为 0，拓扑与上限在候选范围。"""
    takes = {}
    for vowel, stem in (("i", "yi1_FV1.wav"), ("u", "wu1_FV1.wav"),
                        ("a", "a1_FV1.wav"), ("ü", "yu2_FV1.wav")):
        path = CORPUS / stem
        meas = measure_vowel_take(path)
        assert meas["ok"], (vowel, meas)
        x, sr = read_mono(path)
        takes[vowel] = [{"x": x, "sr": sr, "steady": meas["steady"]} for _ in range(2)]
    space = calibrate_personal_vowel_space(takes)
    assert 4500 <= space["speaker_max_formant"] <= 6300
    assert space["a"]["f1Mean"] > space["i"]["f1Mean"]
    assert space["i"]["f2Mean"] > space["u"]["f2Mean"]
    assert space["i"]["f1Std"] == 0.0     # 两条相同录音 → 跨录音无差异
    assert space["overall"]["f1Std"] >= 1.0


def test_personal_vowel_space_missing_anchor():
    with pytest.raises(ValueError):
        calibrate_personal_vowel_space({})


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

"""发音证据的物理时间、缺失语义与产品接入回归，采用本地评分测试数据。"""
from copy import deepcopy
import json
from pathlib import Path
import wave

import numpy as np
import pytest

from app.acoustics import f0_pipeline, transcode
from app.acoustics.imagery.common import Alignment, PhoneSeg, SyllableSeg, load_alignment
from app.acoustics.pronunciation_figures import Recording, analyze, build_bundle, calibrate_vowel_space, export_bundle, load_recording
from app.acoustics.pronunciation_figures.compare import compare
from app.acoustics.pronunciation_figures.inputs import alignment_from_provider
from app.acoustics.pronunciation_figures.measure import SR, _frame_power, to_json
from app.scoring.provider_xfyun import _read_pcm, _result_from_parsed, parse_full

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'docs' / '声学图像提取'
QUALITY = {"verdict": "pass"}


def wav(path, x, rate=SR):
    with wave.open(str(path), 'wb') as w:
        w.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        w.writeframes(np.clip(np.rint(x*32767), -32768, 32767).astype('<i2').tobytes())


@pytest.fixture(scope='module')
def pa():
    aln = load_alignment(CORPUS / '对齐结果' / 'alignment.json')['pa2_FV1.wav']
    return analyze(load_recording(CORPUS / '样本' / 'FV1' / aln.file, aln))


def test_standard_rate_and_provider_copy(tmp_path):
    t = np.arange(SR) / SR
    source, normalized = tmp_path/'input.wav', tmp_path/'normalized.wav'
    wav(source, .2*np.sin(2*np.pi*1000*t))
    before = source.read_bytes()
    transcode.normalize_to_wav(source, normalized)
    with wave.open(str(normalized)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (44100, 1, 2)
        assert w.getnframes() == SR
    pcm = np.frombuffer(_read_pcm(str(normalized)), '<i2')
    assert len(pcm) == 16000
    assert np.argmax(np.abs(np.fft.rfft(pcm))) == 1000
    assert source.read_bytes() == before
    with wave.open(str(normalized)) as w:
        assert w.getframerate() == SR


def test_fft_does_not_truncate_20ms_window():
    x = np.zeros(SR)
    # 一个脉冲在 20ms 窗的末半段，512 点截断会丢失它。
    x[int(.5*SR)+300] = 1
    _, power = _frame_power(x, np.array([.5]), .020, 1024)
    assert power.sum() > 0
    with pytest.raises(ValueError, match='FFT'):
        _frame_power(x, np.array([.5]), .020, 512)


def test_missing_reference_and_shared_f0(pa, tmp_path):
    bundle = build_bundle(pa, goal='initial')
    assert bundle['measurements']['reference'] is None
    assert bundle['measurements']['comparison']['available'] is False
    assert 2 <= len(bundle['images']) <= 4
    assert any(im['name'] == 'P03_plosive_affricate.png' for im in bundle['images'])
    export_bundle(bundle, tmp_path)
    assert json.loads((tmp_path/'measurements.json').read_text(encoding='utf-8'))['reference'] is None
    s = pa.syllables[0]
    assert s['consonant']['vot_ms'] > 80
    assert len(s['vowel']['F1_hz']) == 11
    assert len(s['tone']['contour_degree']) == 21
    expected = f0_pipeline.process_syllables(pa.track, [(pa.aln.syllables[0].t0, s['voicing_end_s'])], *pa.f0_range)[0]
    assert s['tone']['chao'] == expected['chao']
    from app.scoring.rules import analyze_user_curve
    from app.scoring.provider import ProviderResult, SyllableEval
    provider = ProviderResult('test', syllables=[SyllableEval('爬', 'pa2')])
    curve = analyze_user_curve('', provider, {'fLo':pa.f0_range[0], 'fHi':pa.f0_range[1]}, None, measured=pa, track=pa.track)
    assert curve['segments'][0]['user'] == s['_tone_segment']
    assert curve['segments'][0]['reference'] is None


def test_leading_silence_preserves_vot(pa):
    rec = deepcopy(pa.rec)
    offset = .30
    rec.x = np.concatenate([np.zeros(round(offset*SR)), rec.x])
    rec.aln.duration += offset
    for s in rec.aln.syllables:
        s.t0 += offset; s.t1 += offset
        for p in s.phones: p.t0 += offset; p.t1 += offset
    result = analyze(rec)
    assert result.syllables[0]['consonant']['vot_ms'] == pytest.approx(pa.syllables[0]['consonant']['vot_ms'], abs=8)


def synthetic(prevoiced=False, silence=False):
    t = np.arange(SR) / SR
    rng = np.random.default_rng(42)
    voice_start = .25 if prevoiced else .48
    x = .16*np.sin(2*np.pi*130*t)*(t >= voice_start)*(t < .9)
    burst = (t >= .40) & (t < .405)
    x += .6*rng.normal(size=len(t))*burst
    if not prevoiced: x += .06*rng.normal(size=len(t))*(t >= .405)*(t < voice_start)
    if silence: x[:] = 0
    aln = Alignment('synthetic.wav', 'test', 1., [SyllableSeg('爸', 'ba4', .20, .90,
        [PhoneSeg('b', 'initial', .20, .45), PhoneSeg('a', 'final', .45, .90)])])
    return Recording(x, aln, signal_quality=QUALITY)


def test_prevoicing_after_leading_silence():
    a = analyze(synthetic(prevoiced=True))
    c = a.syllables[0]['consonant']
    assert c['release_s'] == pytest.approx(.40, abs=.015)
    assert c['prevoiced'] is True
    assert c['vot_ms'] < -100


def test_affricate_events_follow_acoustic_order():
    name = 'cha2_FV1.wav'
    aln = load_alignment(CORPUS/'对齐结果/alignment.json')[name]
    a = analyze(load_recording(CORPUS/'样本/FV1'/name, aln))
    c = a.syllables[0]['consonant']
    assert c['release_s'] < c['frication_end_s'] < c['voicing_onset_s']
    assert c['vot_ms'] > c['frication_ms']


def test_silence_has_null_measurements():
    a = analyze(synthetic(silence=True))
    s = a.syllables[0]
    assert s['consonant']['vot_ms'] is None
    assert not s['tone']['can_diagnose']
    assert s['vowel']['mid_hz'] == [None]*3
    assert len(s['tone']['contour_degree']) == 21
    json.dumps(to_json(a), allow_nan=False)


def test_absent_nasal_coda_is_not_invented():
    rec = synthetic()
    rec.aln.syllables[0].phones[-1].label = 'an'
    a = analyze(rec)
    coda = a.syllables[0]['nasal_coda']
    assert coda['detected'] is False
    assert 'murmur_ms' not in coda
    assert coda['F2_before_murmur_hz'] is None
    assert a.syllables[0]['reliability']['nasal_coda'] is False


def test_low_rate_bandwidth_and_explicit_reference(pa, tmp_path):
    from scipy.signal import resample_poly
    path = tmp_path/'low.wav'
    wav(path, resample_poly(pa.rec.x, 160, 441), rate=16000)
    low = analyze(load_recording(path, deepcopy(pa.aln)))
    assert low.rec.source_sample_rate == 16000
    assert low.bandwidth_hz == 7600
    bundle = build_bundle(pa, low, goal='tone')
    assert bundle['measurements']['reference'] is not None
    assert bundle['measurements']['comparison']['same_spectral_band'] is False
    assert bundle['images']


def test_comparison_gates(pa):
    ref = deepcopy(pa)
    ref.sex = 'male' if pa.sex == 'female' else 'female'
    result = compare(pa, ref)['syllables'][0]
    assert all(p['difference'] is None for p in result['vowel_mid_hz'])
    assert result['tone']['mean_abs_degree_diff'] is None  # 高度差使用个人标定音域
    ref.syllables[0]['symbol'] = 'ba4'
    assert compare(pa, ref)['syllables'][0]['consonant']['vot_ms']['can_use'] is False
    ref.syllables.append(deepcopy(ref.syllables[0]))
    assert compare(pa, ref)['available'] is False


def test_two_syllables_have_prosody(pa):
    rec = deepcopy(pa.rec)
    offset = len(rec.x)/SR + .2
    second = deepcopy(rec.aln.syllables[0])
    second.t0 += offset; second.t1 += offset
    for p in second.phones: p.t0 += offset; p.t1 += offset
    rec.x = np.concatenate([rec.x, np.zeros(round(.2*SR)), rec.x])
    rec.aln.syllables.append(second)
    rec.aln.duration = len(rec.x)/SR
    a = analyze(rec)
    bundle = build_bundle(a, goal='tone')
    assert any(im['name'] == 'P01_overview_prosody.png' for im in bundle['images'])
    assert len(bundle['measurements']['learner']['boundaries']) == 1
    assert sum(s['duration_share'] for s in a.syllables) == pytest.approx(1., abs=.002)


def test_fv1_personal_vowel_space():
    alignments = load_alignment(CORPUS/'对齐结果/alignment.json')
    recordings = {}
    for vowel, stem in [('i', 'yi1'), ('u', 'wu1'), ('a', 'a1'), ('ü', 'yu2')]:
        name = f'{stem}_FV1.wav'
        recordings[vowel] = load_recording(CORPUS/'样本/FV1'/name, alignments[name], signal_quality=QUALITY)
    space = calibrate_vowel_space(recordings)
    assert 4500 <= space['speaker_max_formant'] <= 6300
    assert space['a']['f1Mean'] > space['i']['f1Mean']
    assert space['i']['f2Mean'] > space['u']['f2Mean']
    name = 'xiao1_FV1.wav'
    sample = analyze(load_recording(CORPUS/'样本/FV1'/name, alignments[name],
                                    vowel_norm=space, formant_ceiling_hz=space['speaker_max_formant'],
                                    signal_quality=QUALITY))
    assert sample.formant_ceiling == space['speaker_max_formant']
    assert sample.syllables[0]['vowel']['mid_z'] is not None
    assert any(image['name'] == 'P02_tone_vowel_norm.png' for image in build_bundle(sample)['images'])


def test_affricate_and_nasal_boundaries():
    alignments = load_alignment(CORPUS/'对齐结果/alignment.json')
    ca = analyze(load_recording(CORPUS/'样本/FV1/ca1_FV1.wav', alignments['ca1_FV1.wav']))
    c = ca.syllables[0]['consonant']
    assert .14 <= c['voicing_onset_s'] <= .17
    assert c['frication_end_s'] < c['voicing_onset_s']
    assert c['spectrum']['peak_hz'] > 3000
    assert all(key in c['spectrum'] for key in ('sd_hz', 'skewness', 'kurtosis'))
    an = analyze(load_recording(CORPUS/'样本/FV1/an1_FV1.wav', alignments['an1_FV1.wav']))
    nasal = an.syllables[0]['nasal_coda']
    assert nasal['murmur_ms'] > 200
    assert nasal['F2_change_hz'] is not None


def test_phone_timestamps_survive_provider_and_cache():
    from app.detection.usecases import _provider_payload, _provider_from_cache
    xml = '''<xml><rec_paper><read_word total_score="90"><word content="爸" symbol="ba4" beg_pos="10" end_pos="60">
    <syll content="爸" symbol="ba4" beg_pos="10" end_pos="60"><phone content="b" is_yun="0" beg_pos="10" end_pos="20" perr_msg="0"/>
    <phone content="a" is_yun="1" beg_pos="20" end_pos="60" perr_msg="0"/></syll></word></read_word></rec_paper></xml>'''
    provider = _result_from_parsed(parse_full(xml))
    cached = _provider_from_cache(_provider_payload(provider))
    aln = alignment_from_provider(cached, 'test.wav', 1.)
    assert aln.syllables[0].initial.t0 == .1
    assert aln.syllables[0].final.t1 == .6
    provider.syllables[0].detail['phones'][0]['begPos'] = None
    with pytest.raises(ValueError, match='时间戳'):
        alignment_from_provider(provider, 'test.wav', 1.)


def test_pipeline_persists_evidence_and_cache_keeps_boundaries(pa, tmp_path, monkeypatch):
    import datetime
    from types import SimpleNamespace
    from unittest.mock import Mock
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app import config, models_registry  # noqa: F401
    from app.db import Base, JSONText, now
    from app.acoustics.models import AudioRow
    from app.content.models import LevelRow
    from app.identity.models import UserRow
    from app.detection.models import RecordingRow, AssessmentResultRow
    from app.detection import usecases
    from app.scoring.models import PitchRangeSnapshotRow
    from app.scoring.provider import ProviderResult, SyllableEval
    from app.api.schemas import AssessmentResult
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(usecases, 'get_session', sessions)
    path = tmp_path/'learner.wav'
    wav(path, pa.rec.x)
    monkeypatch.setattr(usecases, 'audio_path', lambda audio: path)
    syll = pa.aln.syllables[0]
    prov = ProviderResult(config.PROVIDER_VERSION, syllables=[SyllableEval(
        text=syll.text, pinyin=syll.symbol, t0=syll.t0, t1=syll.t1, tone_value=syll.tone,
        detail={'phones':[{'content':p.label, 'part':p.part, 'begPos':p.t0*100, 'endPos':p.t1*100} for p in syll.phones]})])
    evaluate = Mock(return_value=prov)
    monkeypatch.setattr(usecases.scoring_uc, 'get_provider', lambda: SimpleNamespace(evaluate=evaluate))
    extract = Mock(wraps=f0_pipeline.extract_track)
    monkeypatch.setattr(f0_pipeline, 'extract_track', extract)
    with sessions() as db:
        db.add(UserRow(id='user', username='user', username_lower='user', password_hash='unused', created_at=now()))
        db.add(LevelRow(id='level', order=1, layer='initial', published=True, created_at=now(), updated_at=now(),
                        content=JSONText.dump({'targetSound':'p', 'detection':{'evaluationText':syll.text, 'evaluationPinyin':syll.symbol}})))
        db.add(AudioRow(id='audio', user_id='user', purpose='recording', storage_path='unused', duration_sec=pa.duration,
                        pcm_sha256='testhash', created_at=now()))
        db.add(PitchRangeSnapshotRow(id='range', user_id='user', f_lo=pa.f0_range[0], f_hi=pa.f0_range[1],
               algorithm_version='test', created_from=JSONText.dump({'kind':'recording_adaptive'}), created_at=now()))
        for i in range(2):
            db.add(RecordingRow(id=f'rec{i}', user_id='user', audio_id='audio', level_id='level',
                   submission_id=f'sub{i}', submission_payload_hash=f'hash{i}', status='processing',
                   deadline_at=now()+datetime.timedelta(minutes=1), range_snapshot_id='range', created_at=now()))
        db.commit()
    for i in range(2):
        usecases.run_pipeline(f'rec{i}')
        with sessions() as db:
            assert db.get(RecordingRow, f'rec{i}').status == 'completed'
            result = JSONText.load(db.query(AssessmentResultRow).filter_by(recording_id=f'rec{i}').one().payload)
            AssessmentResult.model_validate(result)
            evidence = result['pronunciationEvidence']
            assert evidence['status'] == 'ready'
            assert evidence['measurements']['reference'] is None
            assert result['curve']['segments'][0]['user']['chao'] == evidence['measurements']['learner']['syllables'][0]['tone']['chao']
    assert evaluate.call_count == 1
    assert extract.call_count == 2  # 每次录音提取一次 F0，缓存保留音素边界
    engine.dispose()

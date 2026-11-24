"""共振峰测量核心：默认上限、带宽取值范围、整条轨迹的提取，
以及「只有核心模块调用 Praat 提取共振峰」的约束。语料样本同时用于批处理线的运行检查。"""
import ast
from pathlib import Path

import numpy as np
import pytest

from app.acoustics import formants
from app.acoustics.imagery import common, generate_all

APP_DIR = Path(formants.__file__).resolve().parent.parent
CORPUS = APP_DIR.parent.parent / 'docs' / '声学图像提取'


def test_default_ceiling_follows_median_f0():
    assert formants.default_ceiling(164.9) == formants.CEILING_MALE_HZ
    assert formants.default_ceiling(165.0) == formants.CEILING_FEMALE_HZ


def test_bandwidth_plausible_accepts_only_the_configured_range():
    low, high = formants.BANDWIDTH_RANGE_HZ
    values = np.array([np.nan, low - 1.0, low, 250.0, high, high + 1.0])
    assert formants.bandwidth_plausible(values).tolist() == [False, False, True, True, True, False]


def test_extract_reports_four_formants_and_bandwidths_on_one_grid():
    name = 'a1_FV1.wav'
    aln = common.load_alignment(CORPUS / '对齐结果' / 'alignment.json')[name]
    x, sr = common.read_mono(CORPUS / '样本' / 'FV1' / name)
    track = formants.extract(common.to_sound(x, sr), formants.CEILING_FEMALE_HZ)
    assert track.freqs.shape == track.bandwidths.shape == (formants.N_FORMANTS, len(track.times))
    assert track.first_time == track.times[0]
    assert track.time_step == pytest.approx(formants.TIME_STEP)
    final = aln.syllables[0].final
    core = (track.times >= final.t0 + .3 * final.duration) & (track.times <= final.t0 + .7 * final.duration)
    assert core.sum() >= 5
    freqs = track.freqs[:, core]
    assert np.isfinite(freqs).all()
    assert (np.diff(freqs, axis=0) > 0).all()          # F1 < F2 < F3 < F4
    assert (freqs[-1] < formants.CEILING_FEMALE_HZ).all()
    assert formants.bandwidth_plausible(track.bandwidths[:, core]).mean() > .5


def test_only_the_core_module_calls_praat_for_formants():
    def direct_call_lines(tree: ast.AST, core_aliases: set[str]):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == 'to_formant_burg'
                    and not (isinstance(func.value, ast.Name) and func.value.id in core_aliases)):
                yield node.lineno
            elif (isinstance(func, ast.Name) and func.id == 'call' and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant) and node.args[1].value == 'To Formant (burg)'):
                yield node.lineno

    callers = {}
    for path in sorted(APP_DIR.rglob('*.py')):
        if path == Path(formants.__file__):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        aliases = {item.asname or item.name for item in ast.walk(tree)
                   if isinstance(item, ast.ImportFrom) and item.module == 'app.acoustics'
                   for item in item.names if item.name == 'formants'}
        lines = list(direct_call_lines(tree, aliases))
        if lines:
            callers[path.relative_to(APP_DIR).as_posix()] = lines
    assert callers == {}


@pytest.mark.parametrize(('name', 'modules'), [
    ('ca1_FV1.wav', ('formants', 'obstruents', 'phonation')),   # 塞擦音：辅音过渡用 15 ms 窗提取
    ('an1_FV1.wav', ('formants', 'sonorants', 'phonation')),    # 鼻韵尾：鼻音段 B1 取自核心轨迹
])
def test_batch_modules_run_through_the_core(tmp_path, name, modules):
    alignments = common.load_alignment(CORPUS / '对齐结果' / 'alignment.json')
    x, sr = common.read_mono(CORPUS / '样本' / 'FV1' / name)
    results = generate_all(x, sr, alignments[name], tmp_path, modules=modules)
    errors = {module: res['error'] for module, res in results.items() if 'error' in res}
    assert errors == {}
    assert all(res['tables'] for res in results.values())

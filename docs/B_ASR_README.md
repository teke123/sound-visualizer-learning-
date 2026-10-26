# 发音诊断原型 — 后端组 B 李嘉怡（深度学习 / ASR）

> 本文件请剪切到项目根目录 `D:\asr-pronunciation\` 下（该目录是管理员权限创建的，普通程序无法直接写入）。

本项目严格按《团队分工与排期》与《团队学习与第一二学期开发周排期详细方案》两份
PDF 中 B 的任务从零实现,范围为 1.0 的深度学习 / ASR 模块:

- **1.0 必交付**: Wav2Vec2 / 现有 ASR 模型稳定加载,`/api/asr/status`、`/api/asr/load`
  可用;误读 / 漏读 / 声调错位诊断;声学模型推理性能优化(懒加载 / 失败降级)。
- **第 4 周**: 模型选型确认(1.0 不新训专属模型)+ 发音错误检测原型。
- **第 5 周**: ASR 模型加载与预热策略(`/api/asr/load`、`/api/asr/status`),
  用已发布关内容跑识别冒烟测试,为第 6 周检测闭环备好模型。
- **第 6 周(卡点 CON-04)**: ASR 发音错误检测(误读 / 漏读 / 声调错位)产出结构化诊断。
- **汇报口径**: 模型加载耗时 / 识别成功率 / 失败样本 / 是否可用于对外演示,
  数据见 `文档/汇报.md` 与 `文档/进度登记表.md`。
- **2.0 起(CON-08,12-20)**: 专属模型与 1.0 通用模型同任务对比(`model_id` 参数已预留)。

## 环境
- 解释器: `D:\Anaconda\asr_env`(Python 3.10.20),依赖见 requirements.txt
- 无 NVIDIA GPU → 统一 CPU 推理(torch 2.13.0+cpu)
- 模型已下载到本地 `models/`(1.3GB),**离线加载**,不依赖网络

## 模型选型结论(第 4 周交付物)
**选用 `jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`**,理由:
1. 开源、zh-cn 大字集 CTC 字级模型,中文单字识别效果好;
2. CPU 可推理(实测加载 ~3.8s、单条推理 ~130ms),满足 1.0 演示;
3. 配合 pypinyin 反查即可做声母/韵母/声调闭环,无需新训模型。
备选不采用: xls-r-1b 版/Whisper(CPU 太慢)、funasr(依赖过重)。

## 快速开始
```bash
# 1. 生成标准 TTS 样本(微软 Edge TTS,声母关直接拼音音标朗读)
D:/Anaconda/asr_env/python.exe scripts/make_tts_samples.py
# 2. 批量评测 → 汇报材料
D:/Anaconda/asr_env/python.exe scripts/batch_eval.py
# 3. 启动 API
D:/Anaconda/asr_env/python.exe -m uvicorn api.main:app --port 8000
```

| 接口 | 说明 |
|---|---|
| `GET /api/asr/status` | 加载状态/加载耗时/设备/平均推理耗时/是否可演示 |
| `POST /api/asr/load` | 模型加载(懒加载入口;`{"force": true}` 重载) |
| `POST /api/asr/diagnose` | form-data: `file` + `level_id`(或 `target_pinyin`);返回结构化诊断 |
| `GET /api/levels` | 冻结的 L01-L30 目标音(诊断基准,CON-02 全员冻结) |

诊断结论码: `correct` 正确 / `misread_initial` 误读·声母 / `misread_final` 误读·韵母 /
`misread_syllable` 误读·声韵 / `tone_error` 声调错位 / `missed` 漏读·未识别 / `uncertain` 低置信。

示例:
```bash
curl -X POST http://127.0.0.1:8000/api/asr/load -H "Content-Type: application/json" -d "{}"
curl -X POST http://127.0.0.1:8000/api/asr/diagnose -F "file=@audio/tts_raw/L30_妈.wav" -F "level_id=L30"
```

## 代码结构(B 的分工范围)
```
backend/asr_analyzer.py   模型选型 + 懒加载/三级降级/失败降级 + 通用识别 analyze_with_deep_learning
backend/dl_analyzer.py      发音诊断: CTC 强制选择 + 声韵调比对(闭集优先/开集越权阈值/漏读/多音节/尾滑音)
backend/pinyin_utils.py     拼音解析 + 字→拼音反查 + 多音字读音消歧(诊断支撑)
backend/levels.py           冻结的 L01-L30 目标音
api/main.py                 FastAPI 四接口 + 实验记录落盘
scripts/batch_eval.py       批量评测 → 汇报材料
scripts/make_tts_samples.py 标准 TTS 样本生成(拼音音标朗读)
scripts/md2docx.py          md → docx(每周交微云的产物文档)
audio/tts_raw|tts_err       标准读音 / 错误样本(合成)
文档/                        组会汇报 + 进度登记表(含 docx 交付版)
```

## 汇报口径 ↔ 数据来源
| 汇报项 | 来源 |
|---|---|
| 模型加载耗时 | `POST /api/asr/load` 返回的 `load_ms` |
| 识别成功率 | `experiments/batch_*/summary.md` |
| 失败样本 | summary.md「失败样本」+ `samples.csv` 明细 |
| 是否可对外演示 | summary.md「演示可用性」(判据: 成功率≥90% 且平均<3s/条) |

每次 API 诊断自动追加 `experiments/experiment_log.jsonl` 并存音频副本,作为可复现实验记录。

> 2.0 范围(本周不做): 专属模型对比报告(CON-08)、ONNX 导出、话术生成(Z 组)、P01-P10 前端页面。

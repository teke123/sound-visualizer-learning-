# ASR 模型与诊断

模型管理、发音诊断、CMS 和音频路由由同一个 FastAPI 应用提供。
模块关系和占位接口见 [音频模块架构](AUDIO_ARCHITECTURE.md)。

## 启动

使用 Python 3.10 或 3.11，在仓库根目录安装依赖，再从 backend 目录启动：

```bash
python -m pip install -r backend/requirements.txt
cd backend
python main.py
```

服务地址为 `http://localhost:8000`，接口文档为 `/docs`。
统一从 backend 目录启动，SQLite 默认使用该目录的 `pronunciation.db`。

## 接口

| 接口 | 参数与返回 |
| --- | --- |
| `GET /api/asr/status` | 模型加载状态、设备、加载时间和推理统计 |
| `POST /api/asr/load` | 可选 JSON：`model_id`、`force`；返回加载结果和耗时 |
| `POST /api/asr/diagnose` | multipart：`file`、`level_id` 或 `target_pinyin`；返回结构化诊断 |
| `GET /api/levels` | 返回 L01–L30 的目标音配置 |

状态与加载接口直接返回结果对象。诊断结果包含 `verdict`、`detected`、
`recognized_text`、`candidates`、音频统计和处理耗时。

诊断上传会保存到仓库根目录的 `experiments/audio/`，结果追加到
`experiments/experiment_log.jsonl`。这条接口用于诊断实验，尚未接入 CMS 开放检测检查。

## 模块

- `backend/asr_analyzer.py`：Wav2Vec2 加载、预处理、推理与候选分值。
- `backend/dl_analyzer.py`：候选字选择及声母、韵母、声调诊断。
- `backend/pinyin_utils.py`：拼音解析、多音字匹配与候选字索引。
- `backend/levels.py`：30 关诊断目标。
- `backend/audio/decoding.py`：soundfile / FFmpeg 解码。
- `backend/audio/diagnosis.py`：上传样本归档、诊断调用与实验记录。
- `backend/routes/asr.py`：HTTP 参数校验与结果返回。

模型优先从 `models/wav2vec2-large-xlsr-53-chinese-zh-cn/` 加载，
随后尝试 Hugging Face 缓存和远程仓库。

## 样本生成与批量评测

```bash
python -m pip install -r backend/requirements.txt
python scripts/make_tts_samples.py
python scripts/batch_eval.py
```

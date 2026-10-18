# 决策图 · 后端 API 架构规划

> 范围：依据 [SRS](srs/README.md) 规划后端模块与 API 契约。采用同进程模块化单体、SQLite、文件存储、外部评分 Provider，检测为「短同步 + 超时回落 202」。架构安排见 [02-目标架构](architecture/02-目标架构.md) 与 [03-后端架构与实施方案](architecture/03-后端架构与实施方案.md)。

## 部署与运行原则

- **单进程模块化单体**：前端静态资源、`/api`、`/admin` 同源部署，不引入微服务或独立消息队列。
- **账号与数据归属**：用户注册并登录后使用系统（默认同意服务条款），支持选填「方言区 / 母语背景」；学习进度、音域标定与每次录音检测结果自动保存在本人账号下。
- **标定可跳过**：提供音域与元音空间标定接口；用户未标定或跳过标定时，正常受理录音检测，不拦截提交。
- **录音质量仅提示不拦截**：只要音频文件可正常解码，均正常执行声学特征提取（F0、共振峰、波形/VOT、语谱图）与评分，质量检测结果（音量、底噪、截幅、时长）作为辅助提示返回。

## 模块边界

| 模块 | 职责与数据所有权 |
| ---- | ---- |
| content | 关卡（L01–L30）、原理文章与分类管理、媒体资源存储、参考发音人及参考曲线、搜索索引与关卡导航 |
| acoustics | 私有音频上传（`audioId`）、解码与 16kHz 单声道 PCM 规范化、内容哈希、F0/共振峰/送气波形/语谱图提取与特征缓存、私有音频读取校验 |
| scoring | 外部评分 Provider 适配（科大讯飞语音评测）、录音环境质量检测（音量、底噪、截幅、时长提示）、规则引擎四步反馈、评分缓存、音域标定计算、T 值换算与共振峰归一化 |
| detection | `submissionId` 幂等控制、录音状态机与处理阶段、进程内异步执行器、短同步窗口与 30 秒超时控制、检测结果存储 |
| identity | 轻量账号认证（用户名/密码、服务端会话 Cookie）、个人资料（含可选「方言区 / 母语背景」）、注销账号与数据级联清理 |
| archive | 个人声音档案列表与单删/清空、同关历史记录并排对比、个人音域记录与动态更新、听辨与练习完成事件记录及 D-24 进度派生 |
| feedback | 用户纠错反馈与「希望增加」记录提交及状态管理 |
| admin | 团队自用轻量级维护后台（`/admin`），直接维护关卡、文章、媒体及查看用户反馈 |
| platform | `requestId`、统一 JSON 响应体（envelope）、标准 HTTP 状态码与错误处理 |

## HTTP 与契约

JSON 采用 camelCase，统一响应体：`{code, message, data, requestId, nextStep?}`；每次 HTTP 请求生成或透传 `requestId` 并写入 `X-Request-Id`。后端 OpenAPI（`backend/app/api/schemas.py`）为契约真源，通过 `openapi-typescript` 生成前端类型。

| HTTP | `code` 示例 / 语义 |
| ---- | ---- |
| 200 | `OK`；`CALIBRATION_FAIL`（标定录音未提取到有效音域，带重录指引） |
| 202 | `PROCESSING`：首次提交超出同步等待窗口或处理中轮询查询；带 `recordingId`、`stage` 与 `Retry-After` |
| 400 / 422 | `DECODE_FAILED`（音频损坏或为空，无法解码）/ `VALIDATION_ERROR`（参数结构非法） |
| 401 | `AUTH_REQUIRED` / `INVALID_CREDENTIALS` |
| 403 | `FORBIDDEN` |
| 404 | `NOT_FOUND`（资源不存在、非本人或已删除） |
| 409 | `IDEMPOTENCY_CONFLICT` / `USERNAME_TAKEN` |
| 413 | `FILE_TOO_LARGE` |
| 429 | `RATE_LIMITED` |
| 500 | `INTERNAL_ERROR` |
| 502 / 503 | `PROVIDER_ERROR` / `PROVIDER_DOWN` / `SERVER_BUSY` |
| 504 | `TIMEOUT`：自受理起 30 秒仍未完成 |

文件与媒体接口成功时直接返回对应媒体类型，支持 `206 Partial Content`（Range）与缓存响应，不包裹 JSON envelope。

## 检测处理模型

录音状态机：

    processing(stage) -> completed
    processing(stage) -> failed(retryable | terminal)
    failed(retryable) -> processing（同 submissionId 重试，attempt+1）

- **处理阶段（`stage`）**：`queued` → `signal_check` → `scoring`（调用 Provider）→ `analyzing`（提取 F0 / 共振峰 / 波形与语谱图）→ `finalizing`。
- **短同步窗口 + 202 回落**：`POST /api/recordings` 受理后等待短同步窗口（默认约 8 秒），窗口内完成直接返回 `200 {recording, result}`；未完成返回 `202 {recording}`，后台执行器继续处理，前端按 `recordingId` 轮询。
- **30 秒硬截止**：自受理起 30 秒未完成即标记 `failed(retryable, TIMEOUT)`，查询返回 `504`，支持以同一 `submissionId` 重试且不产生重复档案记录。
- **评估管线顺序**：
  1. 本地信号环境检测（计算音量、底噪 SNR、截幅、有效时长），生成温和的环境质量提示（`quality`），**不拦截后续流程**；
  2. 调用评分 Provider 对本关评测文本进行评测，获取总分、声韵/声调分、音节时间戳与声韵调检错信息；
  3. 结合本地声学特征提取（`parselmouth` 提取基频 F0、共振峰 F1/F2、送气段波形/VOT、语谱图）与评测检错，由规则引擎生成可观察现象与四步反馈；
  4. 若用户已完成音域标定，按个人音域换算五度 T 值曲线并归一化元音空间；若跳过标定，采用自适应范围或默认成人参考范围生成对比曲线；
  5. 保存检测结果并归入用户声音档案。

## 1.0 API 清单

### 平台与内容

| 方法与路径 | 权限 / 行为 |
| ---- | ---- |
| `GET /api/health` | 公开健康状态检查 |
| `GET /api/me/context` | 返回当前登录状态、用户信息（`accountId`、`username`、`dialectBackground?`）、音域标定状态（`calibration: {status: none / calibrated, pitchRange?, vowelSpaceReady}`）及推荐下一关 `nextLevelId`（按 D-24 计算） |
| `GET /api/levels` | 已开放关卡摘要列表（`id`、`order`、`layer`、`type`、`targetSound`、`pinyin`、`representativeChar`、`title`、`oneLiner`、`demoMediaId`、`availability`、`completionKeys`）+ 未开放关卡身份（`availability=closed`）+ 易混音对 `confusablePairs` |
| `GET /api/levels/{id}` | 关卡详情（结论、构形 `articulation`、示范音频、听辨题 `quiz[]`、分步练习 `practice[]`、误区、声学与专业说明、检测任务配置 `detection`、上下关与易混关导航 `nav`） |
| `GET /api/search?q=` | 搜索汉字、拼音、关卡名或标签，返回匹配的已开放关卡 `results` 与无结果时的相近关 `near` |
| `GET /api/article-categories` | 发音原理文章分类列表（气 / 声 / 口型等） |
| `GET /api/articles?category=` | 原理文章摘要目录 |
| `GET /api/articles/{slug}` | 原理文章详情（Markdown 正文、示范音频、短练习、参考资料及关联关卡） |
| `GET /api/media/{mediaId}` | 公开示范音频、构形图片/动图/视频、3D 模型资源读取入口（支持 Range） |

### 音频、标定与检测

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| `POST /api/audio/uploads` | `multipart/form-data {file, purpose: recording / calibration}` → `{audioId, duration, format}`；转码为 16kHz 单声道 16-bit PCM 并计算哈希 |
| `GET /api/audio/{audioId}/file` | 本人私有录音音频回放（支持 Range） |
| `GET /api/audio/{audioId}/f0` | 本人录音的原始 F0 序列 `{algorithmVersion, hopMs, frames[{t, hz?}], voicedRanges[]}` |
| `GET /api/audio/{audioId}/formants` | 本人录音的原始共振峰数据 `{algorithmVersion, frames[{t, f1?, f2?}], vowelSegments[]}` |
| `GET /api/audio/{audioId}/formants.png` | 本人录音的共振峰散点/元音空间图片 |
| `GET /api/audio/{audioId}/spectrogram.png` | 本人录音的语谱图（Praat Spectrogram）与送气段波形图片 |
| `GET /api/pitch-calibration` | 获取音域标定朗读文本与当前标定状态 |
| `POST /api/pitch-calibration` | `{audioId}`；计算并保存个人音高音域与元音空间；未提取到有效特征时返回 `200 CALIBRATION_FAIL` 及重录建议 |
| `POST /api/recordings` | `{audioId, levelId, submissionId}`；支持未标定用户直接提交；同步窗口内完成返回 `200 {recording, result}`，超出窗口返回 `202 {recording}` |
| `GET /api/recordings/{id}` | 查询本人录音检测状态与结果；处理中返回 `202`（含 `stage`），完成返回 `200 {recording, result}` |
| `DELETE /api/recordings/{id}` | 删除本人单条录音档案及其关联音频与特征数据 |

结果对象 `result` 核心字段：

| 字段 | 内容 |
| ---- | ---- |
| `quality` | 环境与信号质量辅助提示（音量、噪声、截幅、时长状态及 `retakeAdvice` 改善建议文案），不拦截评分 |
| `score` | 总分及声韵、声调等可用维度分 |
| `phenomena[]` | 可观察现象标签、音节/声韵调定位与通俗描述 |
| `fourSteps[]` | `{phenomenon, possibleCause, cue, practice: {levelId, stepRef}, wordingSource}` |
| `curve` | 基频（F0）对比曲线 `{status, scale, segments[{syllable, toneValue, user[], reference[]}]}` |
| `formants` | 元音空间与共振峰（F1/F2）对比数据 `{status, user, referenceRegion}` |

### 档案、学习进度与反馈

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| `GET /api/me/recordings?levelId=&cursor=` | 本人声音档案分页列表 |
| `DELETE /api/me/recordings` | 清空本人全部声音档案 |
| `GET /api/me/recordings/compare?a=&b=` | 本人同一关两条历史录音并排对比（返回双方音频、分数、声学曲线与主要差异） |
| `POST /api/learning-events` | 记录听辨题作答（`listen_quiz`）与练习步骤完成（`practice_done`）事件 |
| `GET /api/me/progress` | 返回各关完成状态（按 D-24 计算）与推荐下一关 `nextLevelId` |
| `POST /api/feedback` | 提交页面或关卡纠错反馈 |
| `POST /api/wishes` | 提交搜索无结果时的「希望增加」音/字记录 |

### 账号与个人资料

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| `POST /api/auth/register` | `{username, password, dialectBackground?}`；注册账号（用户名 3–32 字符，密码 ≥8 位，可选填方言区/母语背景） |
| `POST /api/auth/login` | `{username, password}`；登录并建立会话 |
| `POST /api/auth/logout` | 退出登录 |
| `PATCH /api/me/profile` | `{dialectBackground}`；设置或更新个人「方言区 / 母语背景」 |
| `DELETE /api/me/account` | `{password}`；验证当前密码后注销账号，清空本人全部录音档案、学习进度与音域数据 |

## 团队自用维护后台（`/admin`）

后台基于轻量级管理面板（`starlette-admin` / `sqladmin`）实现，供团队成员直接录入和修改：
- **关卡维护**：编辑 L01–L30 的文字说明、2D 声道剖面关键帧参数（提供预设帧）、听辨题、分步练习、检测配置与四步反馈模板，一键切换关卡「已开放 / 未开放」状态。
- **原理文章维护**：使用 Markdown 编辑发音原理文章与分类（气 / 声 / 口型）。
- **媒体上传**：上传示范音频、构形图片/动图/视频與 3D 模型文件。
- **反馈查看**：查看用户提交的纠错与「希望增加」记录并标记处理状态（待处理 / 已采纳 / 暂不采纳）。

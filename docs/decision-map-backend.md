# 决策图 · 后端 API 架构规划

> 范围：依据 SRS 规划后端模块与 API，不代表接口已经实现。
> 采用同进程模块化单体、SQLite、文件存储、外部评分 Provider，检测为「短同步 + 超时回落 202」。本文定义 API 契约，前端与目标架构据此设计；架构安排与实施步骤见 [03-后端架构与实施方案](architecture/03-后端架构与实施方案.md)。

## 范围与验证要求

同意后自动全部转存（含临时标定升级为个人音域）；临时数据保留 72 小时；访客进度仅前端本地；撤回时删除进度与音域；HTTP 使用标准状态码。本地物理删除最迟 24 小时，预览令牌默认 15 分钟，备份最长 7 天。上线前须核实第三方评分服务的留存和删除能力。

1.0 同意文案只有单一现行版本，不处理文案升级与重新同意；consentTextVersion 仍随每次决定留痕。

部署约束：单进程、单 worker；前端静态资源、`/api`、`/admin` 同源部署。限流计数、计算并发上限、评分执行器与定时清理均依赖单进程前提，扩容到多进程前须先把这些状态迁出进程内存。

依赖版本、密码哈希库、评分服务维度与延迟均须实现期验证，本文不凭需求断言已验证。

## 模块边界

| 模块 | 职责与数据所有权 |
| ---- | ---- |
| content | 关卡/文章身份、草稿、不可变公开版本、分类、媒体授权及发布引用、参考发音人与发布时预计算的参考曲线、地图骨架公开标记、搜索索引和导航 |
| acoustics | 私有上传 audioId、解码与转码规范化、内容哈希、F0/共振峰/频谱图提取与特征缓存，提供统一的私有音频读取权限判定 |
| scoring | Provider 适配、质量两维（信号维本地、朗读维依赖 Provider）、规则四步、评分结论缓存、标定计算、T 值换算与共振峰归一化 |
| detection | submissionId 幂等、录音状态机与处理阶段、进程内评分执行器、同步窗口与硬截止、不可变结果快照 |
| identity | 自研轻量认证（用户名/密码、服务端会话表）、sid 与账号安全绑定、同意决定历史、账号数据代次 dataEpoch、注销与会话失效 |
| archive / learning | 自动转存（含音域升级）、个人音域滚动更新、本人档案与比较、当前会话临时记录、同意后学习事件、进度只读派生 |
| feedback | 反馈/希望增加、处理状态、去除已删除私人资源引用 |
| admin | 单管理员管理界面，调用上述用例（见「后台治理用例」）；不直接修改公开版本，不读取私人录音 |
| platform | requestId、审计、标准 HTTP/envelope、限流/并发、权限与 CSRF、定时清理、删除日志 |

各模块管理自身数据，通过用例接口协作；同一个 SQLite 库中跨域必要原子操作（转存、撤回、注销、发布）在用例层统一编排。不新增微服务、消息队列或独立监听端口。重计算受全局并发上限约束，不能阻塞普通请求；调用 Provider 期间不持有数据库写事务。

## HTTP 与契约

JSON camelCase，统一响应：`{code, message, data, requestId, nextStep?}`；每次 HTTP 请求生成/校验 requestId 并写 `X-Request-Id`，幂等重放复用业务结果但使用本次请求 ID，可另引用原操作 ID。后端 OpenAPI 为真源，openapi-typescript 生成前端类型，CI 检查契约漂移。

| HTTP | code 示例 / 语义 |
| ---- | ---- |
| 200 | OK；QUALITY_FAIL（有效业务结果，不填分数与检测现象；含可解码但过短、静音、截幅、噪声、乱读）；CALIBRATION_FAIL（标定未得出有效音域，带重录指引） |
| 202 | PROCESSING：首次提交超过同步窗口、处理中重复提交或查询；带 recordingId、stage、查询入口和 Retry-After |
| 400 / 422 | DECODE_FAILED（无法解码）/ VALIDATION_ERROR（结构非法） |
| 401 | AUTH_REQUIRED / INVALID_CREDENTIALS |
| 403 | CONSENT_REQUIRED / FORBIDDEN / CSRF_FAILED |
| 404 | NOT_FOUND / LEVEL_NOT_PUBLISHED；资源不存在、非本人、已删或过期统一不可见 |
| 409 | CONTENT_VERSION_CHANGED / IDEMPOTENCY_CONFLICT / INVALID_STATE / USERNAME_TAKEN / CALIBRATION_REQUIRED（无有效音域，不受理检测） |
| 413 | FILE_TOO_LARGE |
| 429 | RATE_LIMITED，带 Retry-After |
| 500 | INTERNAL_ERROR |
| 502 | PROVIDER_ERROR：Provider 返回异常或不可解析 |
| 503 | PROVIDER_DOWN：Provider 不可达；DETECTION_OFF：管理员应急熔断（单关或全局）；SERVER_BUSY：计算队列已满，带 Retry-After |
| 504 | TIMEOUT：自受理起 30 秒仍未完成 |

所有 JSON 公共路径含认证采用上述契约。文件成功直接返回媒体类型，支持 206、304、416，不套 JSON envelope；失败保留真实 HTTP 状态。私人资源 `private, no-store`、预览 `no-store`；公开媒体 `no-cache` + ETag，每次再验证都检查当前发布引用，避免缓存让下架后继续可读。

CSRF：同源部署，写请求校验 Origin（缺失时校验 Referer）为本站，Cookie SameSite=Lax 兜底；不使用 CSRF 令牌，前端无需额外请求头（multipart 上传同样适用）。

## 检测处理模型

录音状态机：

    processing(stage) -> completed(scored | quality_fail)
    processing(stage) -> failed(retryable | terminal)
    failed(retryable) -> processing（同 submissionId 同负载重试，attempt+1）

- **stage**：queued → signal_check → scoring（调用 Provider）→ analyzing（曲线/共振峰）→ finalizing。
- **短同步窗口**：POST 受理后最多等待约 8 秒（可配置），完成即 200；未完成返回 202，评分在进程内执行器继续运行，客户端断开不取消。
- **硬截止**：自本次 attempt 受理起 30 秒未完成即标记 failed(retryable, TIMEOUT)，迟到的 Provider 结果丢弃；查询返回 504。可重试失败只在提交页面内由前端持原 submissionId 与原负载重试；离开页面后查看失败记录只提供重新录音（新 audioId、新 submissionId）。
- **标定前置**：受理时校验提交者存在有效音域（个人音域，或未过期的会话临时音域），否则 409 CALIBRATION_REQUIRED，不创建录音记录；受理时固定本次使用的音域快照，处理中音域变化或临时音域到期不影响本次结果。
- **重启恢复**：进程启动时把遗留的 processing 记录标记为 failed(retryable, TIMEOUT)。
- **评分管线顺序**：① 本地信号维质检（音量、噪声、截幅、时长），不合格直接 QUALITY_FAIL，不调用 Provider；② 调用 Provider 对本关评测文本评测；③ 依据 Provider 的乱读、漏读、增读、回读与替换信息判定朗读维，不合格丢弃 Provider 分数并按 QUALITY_FAIL 返回；④ 规则引擎生成现象与四步；⑤ 曲线与共振峰；⑥ 短事务写快照。
- **完成写入前重校验**：录音未删除、未过期；所有者 dataEpoch 未变化（撤回/注销会递增）；按此刻同意状态决定 archived 或 session。任一不满足即丢弃结果并清理产物，不复活数据。
- **缓存**：评分结论缓存键 = 所有者 + 规范化 PCM 哈希 + levelId + contentVersion + ruleVersion + Provider/模型版本；曲线另含音域快照与算法版本。失败不入缓存。

## 1.0 API 清单

### 平台与内容

| 方法与路径 | 权限 / 行为 |
| ---- | ---- |
| GET /api/health | 公开健康状态，不泄露内部配置 |
| GET /api/me/context | 访客可读；{authenticated, accountId?, username?, consent: {status: none / granted / rejected / revoked, consentTextVersion}, currentConsentTextVersion, calibration: {status: none / session / personal, expiresAt?}, dataEpoch?, pendingTransfer?, nextLevelId}；登录且同意时 nextLevelId 按 D-24 由服务端进度派生，否则为第一已发布关（前端用本地进度覆盖） |
| GET /api/levels | 已发布摘要（id、order、layer、type、targetSound、pinyin、representativeChar、title、oneLiner、demoMediaId、availability、completionKeys: {quizIds[], practiceStepIds[]}，供前端本地按 D-24 计算完成度）+ 骨架（仅 CMS 标记 skeletonPublic 的未发布关，只含 id/order/layer/targetSound、availability=closed）+ confusablePairs（仅双方均已发布）；availability 为 open / temporarily_unavailable（应急熔断）/ closed；tag 为 2.0 扩展 |
| GET /api/levels/{id} | 仅已发布详情，含 contentVersion、nav、构形 articulation（见下）、听辨题与答案（访客须本地判对）、练习、误区、专业折叠、detection（promptText、sampleMediaId、allowedMetrics、available）；规则阈值与四步内部模板不下发 |
| GET /api/search?q= | 仅已发布匹配与相近关；汉字经拼音拆分为声母/韵母映射到关卡，学习标签匹配「翘舌」类词；不持久化搜索日志 |
| GET /api/article-categories | 公开分类；基于已发布文章的分类快照 |
| GET /api/articles?category= | 已发布文章摘要目录 |
| GET /api/articles/{slug} | 单篇公开详情、contentVersion、Markdown、示范、练习、资料及有效关卡入口 |
| GET /api/media/{mediaId} | 公开示范与内容媒体（音频/图/动画/视频/字幕/模型）的唯一读取入口；校验已发布引用与授权；授权材料不可读；Range 与 ETag |
| POST /api/preview/tokens | 仅管理员；{kind, id}，签发绑定管理员会话/对象/草稿修订的 15 分钟令牌，返回 {token, expiresAt, url}；url 形如 `/preview/levels/{id}?token=…`、`/preview/articles/{slug}?token=…`，后台按钮直接在新窗口打开 |
| GET /api/preview/levels/{id}?token= | 管理员会话 + 对象预览令牌，与公开详情同结构，来源为草稿 |
| GET /api/preview/articles/{slug}?token= | 同上，文章草稿 |
| GET /api/preview/media/{mediaId}?token= | 同上，仅令牌绑定草稿引用的媒体；不授权私人录音。令牌统一以 query 传递，使 `<audio>`/`<img>` 可直接引用 |

关卡详情中的学习结构：

| 字段 | 结构 |
| ---- | ---- |
| quiz[] | {id, stimulusMediaId, prompt, options: [{text, mediaId?}], answerIndex, explanation?}；id 跨版本稳定，题目实质变化须换新 id |
| practice[] | {id, title, instruction, repeat?, durationSec?, bodyCue, mediaId?}；id 跨版本稳定 |
| articulation | {media: [{mediaId, kind: image / animation / video, altText}], description, sagittal: {keyframes[]}, model3dMediaId?} |

声道剖面参数 `sagittal.keyframes[]`（单帧为静态口型，多帧为过程，如塞音成阻→除阻、L30 的 m→a），按发音器官描述，元音与辅音共用：

| 字段 | 取值 | 说明 |
| ---- | ---- | ---- |
| label | 文本 | 帧说明，如「双唇闭合」「张口」 |
| holdMs | 整数 | 该帧停留时长，前端在帧间插值 |
| jaw | 0–1 | 下颌开合 |
| lips | {aperture: 0–1, rounding: 0–1, contact: none / bilabial / labiodental} | 开口度、圆唇度、接触方式 |
| tongueTip | {place: rest / dental / alveolar / postalveolar / retroflex, stricture: open / approximant / fricative / closure} | 舌尖位置与阻碍程度 |
| tongueBody | {height: 0–1, backness: 0–1, stricture: open / approximant / fricative / closure} | 舌面高低前后；j/q/x 用高前位加阻碍，g/k/h 用高后位加阻碍 |
| velum | raised / lowered | 软腭升降（m、n 为 lowered） |
| airflow | none / oral / nasal / burst / aspirated_burst / friction / affricate | 气流示意 |
| voicing | 布尔 | 声带振动示意 |

后台提供六个单韵母与各声母的预设帧供管理员起步微调；发布前置检查校验至少一帧、各值在取值范围内。

### 音频、标定与检测

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| POST /api/audio/uploads | multipart {file, purpose: recording / calibration} → {audioId, duration, format, expiresAt}；转码为评测所需规范格式并计算 PCM 哈希；登记 sid/账号归属；首次上传起 72 小时 |
| GET /api/audio/{audioId}/file | 仅私有音频（P09 回放、P10 并排播放）；校验归属与失效；Range/ETag；`private, no-store` |
| GET /api/audio/{audioId}/f0 | 本人录音音频的原始 F0 序列 {algorithmVersion, hopMs, frames[{t, hz?}], voicedRanges[]}；与 file 相同的归属/失效校验；按需计算并进特征缓存；计入特征计算限流；`private, no-store` |
| GET /api/audio/{audioId}/formants | 本人录音的原始共振峰 {algorithmVersion, frames[{t, f1?, f2?}], vowelSegments[]}；校验与缓存同上 |
| GET /api/audio/{audioId}/formants.png | 共振峰散点图片；校验与缓存同上；仅 purpose=recording 的音频可读（标定音频算完即删） |
| GET /api/audio/{audioId}/spectrogram.png | 频谱图图片（Praat Spectrogram，时间×频率热力图）；校验与缓存同上；仅 purpose=recording 的音频可读 |
| GET /api/pitch-calibration | {text, textVersion, status: none / session / personal, pitchRange?, vowelSpaceReady, expiresAt?, updatedAt?} |
| POST /api/pitch-calibration | {audioId, textVersion}；同步处理（受同一计算并发与 30 秒上限约束）；成功 200 返回音域；未得出有效 F0 或六个单韵母不全返回 200 CALIBRATION_FAIL；同意有效写个人音域，否则会话临时音域；标定音频用后即删 |
| POST /api/recordings | {audioId, levelId, contentVersion, submissionId}；无有效音域 409 CALIBRATION_REQUIRED；窗口内完成 200 返回 {recording, result}；未完成 202 返回 {recording}；版本变化 409；熔断 503 DETECTION_OFF；失败按真实状态码并带 {recordingId, retryable} |
| GET /api/recordings/{id} | 本会话/本人；processing 202（含 stage）；completed 200 返回 {recording, result}；failed 按记录的真实状态码并带 {recording}；已删/过期 404 |
| DELETE /api/recordings/{id} | 本会话/本人单删（临时或已存档）；立即逻辑失效，异步硬删独占音频与缓存；重复删除幂等；音域若引用该录音则重算 |

录音对象 recording：{recordingId, audioId, levelId, contentVersion, status: processing / completed / failed, stage?, error?: {code, retryable}, storage: session / archived, expiresAt?, createdAt}。audioId 供回放及 F0/共振峰读取；不返回 submissionId。

结果对象 result：

| 字段 | 内容 |
| ---- | ---- |
| 版本 | levelId、contentVersion、ruleVersion、providerVersion、algorithmVersion |
| 保存 | storage: session / archived、expiresAt?（仅 session） |
| quality | verdict: pass / fail；signal（音量、噪声、截幅、时长）；reading（漏读、增读、回读、替换、乱读）；retakeAdvice |
| score / phenomena | 仅 pass 时填写；phenomena 为本关已定稿标签 + 音节/声韵调定位 + 通俗表述 |
| fourSteps[] | {phenomenon, possibleCause, cue, practice: {levelId, stepRef}, wordingSource: rule_template} |
| curve | {status: ok / not_available, scale: T, segments[{syllable, toneValue, user[], reference[]}], rangeSnapshotId}；结果的主对比曲线，按受理时音域快照冻结 |
| formants | 仅单韵母关；{status, space: normalized, user, referenceRegion} |

### 当前会话

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| GET /api/session/recordings | 当前 sid（访客）或当前绑定会话内本账号的临时录音摘要 {recordingId, audioId, levelId, createdAt, expiresAt, verdict, score?}，以及同意后将转存的条数 |
| POST /api/session/reset | 删除当前会话全部临时录音、未引用上传与会话标定；访客同时轮换 sid；已登录者保留登录，不触及已存档 |

### 档案、学习与反馈

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| GET /api/me/recordings?levelId=&cursor= | 登录且同意，仅本人 archived；分页摘要 {recordingId, audioId, levelId, contentVersion, ruleVersion, createdAt, verdict, score?}，不含文件或 Provider 原始数据 |
| DELETE /api/me/recordings | 登录，清空本人已存档录音；音域按剩余数据重算；区别于撤回的全部进度/音域清理 |
| GET /api/me/recordings/compare?a=&b= | 本人同关 archived 两条：双方摘要（含 audioId）与曲线、各自音域快照；comparable {score, curve, reasons[]}；differences[] 仅含可比维度；跨所有者或跨关 404/422 |
| POST /api/learning-events | 登录且同意；{events: [{eventId, levelId, contentVersion, kind: listen_quiz / practice_done, detail}]}，单批 ≤50；listen_quiz 的 detail 为 {questionId, choiceIndex}，practice_done 的 detail 为 {stepId}；按 eventId 去重；服务端按公开版本校验并派生对错；返回 {accepted, duplicates, rejected[{eventId, code}]} |
| GET /api/me/progress | 登录且同意；{levels: [{levelId, completed, quiz: {passed, total}, practice: {done, total}}], nextLevelId}，按 D-24 派生 |
| POST /api/feedback | 公开提交，sid/账号及限流；{sourcePage, type, content?, articleSlug?, levelId?, recordingId?, subtype?, rating?}；结果引用校验本人并补记版本 |
| POST /api/wishes | 公开提交、限流；希望增加的音/字与 searchQuery? |

### 账号与同意

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| POST /api/auth/register | {username, password}；用户名 3–32（字母、数字、下划线、中文）全局唯一、密码 ≥8；不收邮箱/手机、不提供找回；注册不自动登录、不认领 |
| POST /api/auth/login | {username, password}；已登录时先按退出处理；成功后绑定当前 sid；已有有效同意时自动转存；响应 {context, transfer?} |
| POST /api/auth/logout | 失效认证会话，解绑并轮换 sid |
| GET /api/me/consent | 登录；状态、consentTextVersion 与只追加的决定时间线 |
| POST /api/me/consent | {decision: granted / rejected, consentTextVersion}；版本须等于现行版本；已是 granted 时再次 granted 不追加记录，只重跑转存（即转存重试入口）；响应 {consent, transfer: {status: completed / partial / none, transferredCount, calibrationUpgraded}} |
| DELETE /api/me/consent | 撤回；dataEpoch 递增，立即拒绝后续存档并按 D-17 删除；重复调用幂等 |
| DELETE /api/me/account | {password}；按撤回范围清理、匿名化审计、用户名保留单向哈希墓碑、全部会话失效 |

符合条件的录音自动全部转存，无逐条存档操作。修改密码不属于 1.0 范围。

内部或开发诊断端点（生产不对匿名挂载）：音频元数据、`/api/audio/quality`、`/api/asr/*`；`/api/audio/score` 属 2.0 模型对比。F0、共振峰、频谱图及其图片已作为本人可读的 audioId 资源对外提供（见上表）。后台 `/admin` 是管理界面入口，不是额外网络端口；治理动作不开放通用公开 REST CRUD。

## 后台治理用例

后台以 starlette-admin 表单编辑草稿，其余治理动作以自定义动作/页面调用以下用例；每个用例写审计。

| 分组 | 用例 |
| ---- | ---- |
| 认证 | 管理员登录/登出（独立凭据与会话，不复用学习账号） |
| 关卡 | 草稿保存；构形配置（内容媒体、替代文本、声道剖面关键帧，可从预设起步）；检测任务配置（朗读提示词、评测文本与题型、质检要求、允许指标、四步模板）；参考示范与参考发音人指定；骨架公开标记；发布前置检查（逐项缺失）；草稿与公开版本对比；发布 / 下架 / 回退 |
| 文章 | 草稿保存、预览（打开前端 `/preview` 真实页面，后台不另做渲染）、前置检查、发布 / 下架 / 回退；分类创建、改名、删除前迁移；下架关卡后受影响文章提示 |
| 媒体 | 上传、用途与授权登记、发布引用查看 |
| 检测 | 应急熔断开启/恢复（单关或全局，须填原因）；标定文本配置（须覆盖六个单韵母）；参考发音人标定登记 |
| 预览 | 签发预览令牌 |
| 反馈 | 反馈与希望增加的列表、处理（已采纳/暂不采纳）；只见文字与版本骨架 |
| 审计 | 按对象、操作、requestId 查询 |

## 架构决策

| # | 决策 | 现行结论 |
| ---- | ---- | ---- |
| #1 | 录音资源与学习事件 | /recordings 扁平资源；两步提交；学习事件独立、批量、1.0 不含 mini_quiz；档案集合归 /me，当前会话临时记录归 /session |
| #2 | 工具接口 | 结果的主对比曲线与共振峰随结果快照下发，前端只渲染；本人录音的音频文件、原始 F0、共振峰、频谱图及其图片统一按 audioId 对外读取，共用归属/失效校验；质量/ASR 为内部诊断；本地评分 2.0 |
| #3 | HTTP 语义 | 标准状态码 + JSON envelope + requestId；QUALITY_FAIL 与 CALIBRATION_FAIL 为 200；文件原生响应 |
| #4 | sid 会话 | 首次按需签发不可猜测、签名 HttpOnly Cookie；上传立即归属；登录绑定而非无条件归档；退出、切换账号与访客重置均轮换 |
| #5 | 任务读取 | 关卡详情内 detection 与 contentVersion/nav；提交校验展示版本；熔断时学习入口保留、检测明确提示 |
| #6 | 字段与类型 | JSON camelCase，OpenAPI → 自动生成 TS，CI 检查漂移；数据库内部命名不属于 JSON 契约 |
| #7 | 音域 | 标定是检测的强制前置：无有效音域（从未标定、临时标定过期、撤回后）时提交返回 409 CALIBRATION_REQUIRED；标定同时得出音高音域与元音空间；受理时固定音域快照；同意后个人音域按「标定基线 + 最近存档合格录音」滚动更新 |
| #8 | 账号 | 自研轻量认证：argon2 哈希 + 服务端会话表，便于用户名登录、sid 绑定、注销即全部会话失效 |
| #9 | CMS 库 | 自研内容治理 + starlette-admin 优先/sqladmin 备选；草稿 CRUD 与发布用例隔离，管理员认证独立配置 |
| #10 | 整合 | SQLite（WAL）+ SQLAlchemy + Alembic + 文件存储；迁移数据库需评估数据和并发 |
| #11 | audioId 数据流 | 上传落规范化音频、哈希与归属；私有音频只经 /audio/{id}/file 与内部用例读取；公开示范只经 /media |
| #12 | 两步提交与幂等 | 上传 multipart，评分 JSON；同一所有者 + submissionId 绑定同负载，差异 409；处理中 202；failed(retryable) 同键重试重新执行；不同键相同音频由版本化评分缓存保证重复性 |
| #13 | 缓存与 TTL | 特征与评分缓存按算法/版本入键；未引用上传、临时录音与会话标定统一 72 小时；删除清缓存 |
| #14 | 检测执行 | 短同步窗口（约 8 秒）+ 回落 202 + 进程内有界执行器；30 秒硬截止；重启把处理中记录置为可重试失败 |
| #15 | 部署 | 单进程单 worker、同源；进程内限流/调度/执行器依赖该前提 |
| #16 | 标准曲线 | 发布时由参考示范提取 F0，按参考发音人音域换算为 T 值并随关卡公开版本冻结；共振峰按标定元音空间归一化，仅单韵母关展示 |
| #17 | 多设备本地清除 | dataEpoch 随撤回递增；前端本地进度以 (accountId, dataEpoch) 标记，联网校验不一致即清除 |
| #18 | 同意文案 | 1.0 单一现行版本，不做升级与重新同意 |
| #19 | 完成度 | D-24：当前公开版本全部听辨题各至少答对一次 + 全部练习步骤各至少一次 practice_done；按稳定 questionId/stepId 计，旧版本事件在 id 仍存在时计入；录音不计入；服务端与前端本地同一规则 |
| #20 | 构形参数 | 声道剖面按发音器官关键帧描述（见「关卡详情中的学习结构」），不按部位/方法枚举预设；前端参数化绘制 |
| #21 | 预览令牌传递 | 令牌以 query 传递给预览页面、预览 JSON 与预览媒体；同时要求管理员会话 Cookie；响应 no-store |
| #22 | 重试边界 | 同键同负载重试仅限提交页面内；跨页面（刷新、从 P09/P10 进入）的失败记录只提供重新录音 |

## 自动转存、留存与并发不变量

1. 归属与 session/archived 独立；登录只绑定，首次同意前不转存；绑定后原访客资源归账号，sid 单独不再足以读取。转存仅当前可信绑定会话内该账号临时记录，且未过期/未删除/已完成检测，不扫描所有访客；未提交检测的孤儿上传不转存；处理中记录完成时重校验同意。质量不合格记录可存档但只含质量结论与重录指引。
2. 转存同时把未过期的会话临时标定升级为个人音域基线（若账号已有个人音域，以较新的标定为准）；被转存结果引用的音域快照随之转为长期。
3. 学习进度：访客/未同意只存在前端本地；不接收 sid 学习事件，不导入历史本地进度；登录且同意后的新事件按 eventId 去重与内容版本校验；完成度按 D-24（#19）派生。
4. 留存：私有上传/临时结果/会话标定及缓存首次上传起 72 小时，不续期；存档保留至用户删除。标定音频在算出音域后即删除；个人音域记录来源（标定与录音 ID）以便删除时重算。
5. 评分重复性：缓存键见「检测处理模型」；Provider 不保证天然确定性，不缓存失败，不跨用户共享私人缓存。历史结果的曲线不随音域更新重算。
6. 删除：立即逻辑失效；独占 audioId 同时失效，共用 audioId 仅在仍有本人有效引用时可读；本地硬删最迟 24 小时，失败重试告警。单删/清空后音域按剩余来源重算或回退到标定基线。撤回/注销删除全部账号临时与长期录音、事件/进度、音域及私人缓存，dataEpoch 递增使在途任务无法写回；审计仅留匿名骨架。
7. 内容：公开版本不可变、草稿分离；回退新建发布记录；历史私人结果引用旧版本仍可查看，不等于旧教学媒体继续公开。熔断与发布不改变已有幂等结果，但重放始终先校验资源仍有效且属于请求者。
8. 账号切换：已登录时再次登录等同先退出（轮换 sid）再登录；后续账号不可认领上一账号记录。
9. 本地删除边界：当前设备在撤回/注销时清除相关进度与音域；其他设备下次联网经 dataEpoch 比对后清除；服务端不能远程立即擦除离线浏览器存储。
10. 基础保护：sid/IP 或账号/IP 限流、全局计算并发上限与队列上限；Cookie 安全设置与 Origin/CSRF 校验；预览令牌绑定管理员权限，禁止私人录音访问。

## 2.0 / 3.0 预留

- 层级与关卡类型为数据配置，关卡 ID 可超出 L30；`tag` 参数在 levels、search、articles 统一。
- 曲线按音节分段（segments），直接承接 3.0 双字词与短句变调。
- 四步每条带 wordingSource；2.0 增加 `llm_confirmed`：按单条录音生成话术候选，管理员逐条确认后挂到该结果上（不改写原快照，单独留痕并引用结果版本）；未确认显示规则模板；录音删除或过期时候选与确认记录一并删除。
- learning-events.kind 可扩展 `mini_quiz`；推荐新增 `GET /api/me/recommendations`，1.0 以 context.nextLevelId 占位。

## 与需求及验收的对应

自动转存 D-14/FR-102/V1-AC18；72 小时 D-15/NFR-09/V1-AC19；本地进度 D-16/V1-AC20；撤回删除 D-17/V1-AC26；标准 HTTP D-18/V1-AC25；版本/幂等 V1-AC22–23；草稿预览 V1-AC24；录音权限 V1-AC21；比较 V1-AC27；短同步回落 D-19/V1-AC28；会话临时记录 FR-110/V1-AC29；标定前置、音域升级与多设备清除 D-20/D-21/V1-AC30；完成度 D-24/V1-AC31。实现前仍需核实 Provider 的实际维度与音节时间戳、声母关评测形式、管理界面扩展能力、第三方留存与清理条款，不能把需求层推断当作已验证实现。

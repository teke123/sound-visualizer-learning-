# 决策图 · 前端设计规划

> 范围：页面职责与路由、UI 与依赖选型、跨页组件、状态管理、API 消费与前端决策。
> 业务需求见 [SRS](srs/README.md)，模块边界见 [目标架构](architecture/02-目标架构.md)，API 契约见 [后端决策图](decision-map-backend.md)，前端分层、关键流程与实施计划见 [04-前端架构与实施方案](architecture/04-前端架构与实施方案.md)。本文描述目标设计。

## 页面与路由

1.0 大众端为 P01–P06、P08–P11，共 10 页；新页面从 P12 起编号。比较、标定、同意均为组件或对话框，不新增页面编号。

| 页面 | 路由 | 职责 | 数据来源 |
| ---- | ---- | ---- | ---- |
| P01 首页 | `/` | 四个主按钮、搜索框、已发布关入口、下一关推荐、边界句 | levels、me/context；进度门面（本地或 me/progress） |
| P02 搜索 | `/search?q=` | 找关、相近关推荐、希望增加 | GET /api/search?q=、POST /api/wishes |
| P03 发音地图 | `/map` | 三层闯关进度、未开放骨架、易混关并排入口 | levels + 进度门面 |
| P04 原理子站 | `/principles`、`/principles/:slug` | 分类目录与文章正文 | article-categories、articles、articles/{slug} |
| P05 关卡页 | `/learn/:id` | 结论、构形、示范、听辨、练习、误区、专业折叠、本关录音 | levels/{id}；学习事件 |
| P06 发音库 | `/library` | 已发布关目录、试听、任选两关比较 | levels |
| P08 检测中心 | `/test`、`/test/:levelId` | 选关、标定、录音与提交 | levels、levels/{id}.detection、audio/uploads、pitch-calibration、recordings |
| P09 结果 | `/result/:id` | 质量、曲线、分数、现象、四步、回放、反馈、下一步 | recordings/{id}、audio/{audioId}/file、audio/{audioId}/f0 与 formants（声学细节）、levels/{id}（示范） |
| P10 声音档案 | `/archive`、`/archive/compare?a=&b=` | 本人存档列表、删除、同关比较；未同意时显示无档案说明与本会话临时记录 | me/recordings、me/recordings/compare、session/recordings |
| P11 账号 | `/account`、`/account/login`、`/account/register` | 注册登录、同意、撤回、注销、本会话临时记录、重新标定 | auth/*、me/*、session/*、pitch-calibration |

| 辅助路由 | 说明 |
| ---- | ---- |
| `/learn` | 重定向到 `/library` |
| `/learn/:id#quiz`、`#practice`、`#record`、`#step-{stepId}` | 关卡页区块锚点；「跟着练」与四步练习跳转使用 |
| `?compare=L13,L14` | 在 P03/P05/P06 上打开比较对话框，可分享，后退即关闭 |
| `?redirect=` | 登录、注册完成后回跳（只接受站内路径） |
| `/preview/levels/:id?token=`、`/preview/articles/:slug?token=` | 管理员真实预览，不计入大众端页面 |
| 其余路径 | NotFound；关卡未发布、录音过期或被删同样落到统一的不可见状态 |

后台 `/admin` 为后端管理界面入口。P03 展示学习位置和进度，P06 展示目录与比较工具，具体发音讲解位于 P05；P04 讲普遍原理，参考资料位于文章 references 与关卡专业折叠区。

### 首页按钮与导航

| 入口 | 去向 |
| ---- | ---- |
| 搜一个音 | `/search` |
| 看懂发音 | `/principles`，目录页提供进入 `/map` 的入口 |
| 跟着练 | `/learn/{nextLevelId}#practice` |
| 录音比较 | `/test/{nextLevelId}`；录音后在 P09 与标准曲线对比 |
| 无已发布关 | 后三个按钮显示「暂无已发布内容」状态，不产生跳转 |

nextLevelId 由进度门面给出（见「进度与学习事件」）。桌面端顶部导航列出全部一级页面，并常驻搜索框；手机端使用底部 5 个标签：首页 / 地图 / 检测 / 档案 / 我的，原理、发音库和搜索从首页与顶栏进入。

## UI 与依赖

Vue 3 SPA 在 Vite 工程内嵌 Quasar v2，使用 @quasar/vite-plugin、@quasar/extras 与 sass。路由使用 vue-router，状态使用 Pinia 与 composables，通用浏览器能力使用 @vueuse/core。曲线由 echarts/vue-echarts 渲染；文章使用 markdown-it 及受控指令；openapi-typescript 依据后端 OpenAPI 生成类型；three.js 用于 3D 构形。HTTP 使用原生 fetch 封装，不引入额外请求库。

echarts、markdown-it、three.js 按路由或组件懒加载，不进入首屏包。依赖版本、Vite 插件兼容性、构建能力及浏览器支持须在实现前核实。响应式导航使用 QLayout 等组件；内容在手机端单列布局，保证触控目标与录音主路径可用。

## 组件与状态

| 归属 | 组件 / 状态 | 职责 |
| ---- | ---- | ---- |
| 外壳 | AppShell、TopNav、BottomTabs | 桌面顶部导航与手机底部标签 |
| 外壳 | PageState / usePageCopy | 加载、空、错误、无权限、不可见状态与统一文案；错误显示 requestId |
| 外壳 | BoundaryNotice | 首页与 P09 常驻边界句 |
| 关卡展示 | LevelCard | P01/P02/P06 共用卡片：名称、拼音、代表字、一句话结论、试听、进入 |
| 关卡展示 | LayerMap | P03 三层地图、骨架「未开放」、完成标记 |
| 关卡展示 | ConfusablePairList | 易混关并排入口，仅双方已发布 |
| 关卡展示 | LevelNav | 上一关 / 下一关 / 易混关；L30 回 L01、L09，目标未发布时禁用 |
| 关卡展示 | ComparePanel | 两关示范与构形并排；P03/P05/P06 共用，P06 可任选，易混对作快捷项 |
| 关卡学习 | LevelView | 关卡页纯展示组件，公开与预览共用 |
| 关卡学习 | ArticulationFigure | 内容媒体 / 声道剖面 SVG / 3D 三视图切换，缺席视图不显示切换项 |
| 关卡学习 | SagittalView | 按关键帧参数绘制声道剖面，帧间插值，播放 / 暂停 / 单帧 |
| 关卡学习 | DemoPlayer | 正式示范播放（正常 / 慢速、男声 / 女声、字幕） |
| 关卡学习 | QuizPanel | 听辨单选，立即判对，答错展示解释并可再答 |
| 关卡学习 | PracticeStepper | 3–5 步，每步可播放、暂停、重做、标记完成，显示次数或时长与停止提示 |
| 关卡学习 | MisconceptionList、ProFold | 误区；专业折叠（默认收起） |
| 文章 | ArticleView | Markdown 正文、受控指令、示范、练习、资料与关卡链接；公开与预览共用 |
| 搜索与反馈 | SearchBox、WishDialog | P01/P02 搜索；希望增加 |
| 搜索与反馈 | FeedbackWidget | 看懂了 / 还不明白、纠错 subtype、结果评价 rating 三种模式 |
| 检测 | RecorderPanel | 录音控制、实时波形、试听、重录、提交，P05/P08 共用 |
| 检测 | CalibrationPanel | 标定文本、录音、结果与重录指引；检测前强制，P11 可重新标定 |
| 检测 | RecordingTips、MicPermissionGuide | 环境与用途说明；按浏览器给出麦克风开启指引 |
| 检测 | ProcessingStage | 检查录音 / 评分中 / 分析曲线，含超时与重试 |
| 结果 | QualityVerdict、ScoreCard、PhenomenaList、FourStepsList | 质量结论与分数分开呈现；四步练习跳回 `/learn/:id#step-{stepId}` |
| 结果 | ToneCurveChart | 结果快照曲线（T 值、按音节分段），P09/P10 共用 |
| 结果 | FormantChart | 结果快照共振峰对比（单韵母关），不可用时显示原因 |
| 结果 | AcousticDetail | P09 折叠区：按 audioId 读取原始 F0（Hz）与共振峰图片，展开时才请求 |
| 结果 | SaveStatusBanner | 临时（到期时间）/ 已保存 / 登录并同意后保存的入口 |
| 账号档案 | LoginForm、RegisterForm | 登录页写明不提供找回、保存需同意 |
| 账号档案 | ConsentDialog | 保存说明、将转存条数、本地进度不导入说明；同意 / 拒绝 / 暂不 |
| 账号档案 | ConsentTimeline | 同意决定历史 |
| 账号档案 | SessionRecordsPanel | 本会话临时记录、单删、清空并重新开始 |
| 账号档案 | ArchiveList、ArchiveCompareView | 存档列表与同关两条比较（并排播放、曲线、可比范围、主要差异） |
| 账号档案 | DangerConfirmDialog | 删除、清空、撤回二次确认；注销输入密码 |

| Store / composable | 职责 |
| ---- | ---- |
| context store | `/api/me/context` 的唯一持有者：身份、同意、标定、dataEpoch、nextLevelId |
| levels store | 公开关卡摘要、骨架、易混对、availability，带新鲜度校验 |
| progress 门面 | 按身份与同意选择本地或服务端进度，统一给出完成状态与 nextLevelId |
| learningEvents outbox | 同意后学习事件的本地队列、批量上传与重试 |
| recorder store | 唯一 MediaRecorder 封装、麦克风授权、实时波形 |
| player store | 全局唯一音频播放，同一时刻只播一个 |
| useAssessmentFlow | 检测流程状态机（标定 → 录音 → 上传 → 提交 → 结果） |
| useRecordingResult | 按 recordingId 读取与轮询结果 |
| useApi | fetch 封装：envelope、错误类型、requestId、202 与 Retry-After |

初始化读取 `/api/me/context`，访客与未同意用户不查询受保护的 progress 接口。退出或切换账号清除账号相关状态，使用服务端轮换后的 sid。

`availability` 为 open、temporarily_unavailable、closed。正常已发布关可学习与检测；应急熔断时检测入口显示故障说明，学习入口保留；closed 仅在地图显示身份骨架。P01/P02/P06/P08 过滤骨架。

## 进度与学习事件

完成判定按 D-24：本关当前公开版本的全部听辨题各至少答对一次，且全部练习步骤各至少标记完成一次；录音不计入。nextLevelId = 公开顺序中第一个未完成的已发布关；全部完成或无进度时回落 L01，L01 未发布时回落第一已发布关。前端本地计算使用 levels 摘要中的 `completionKeys`，与服务端 me/progress 使用同一规则。

| 身份 | 进度来源 | 本地存储 |
| ---- | ---- | ---- |
| 访客 | 本地访客桶 | `guest`，退出登录后回到访客时继续使用 |
| 已登录、未同意（含已拒绝、已撤回） | 本地账号桶 | `(accountId, dataEpoch)`，退出时清除 |
| 已登录、已同意 | 服务端 me/progress | 仅 outbox 持久化，键为 `(accountId, dataEpoch)` |

- 每次听辨作答产生 `listen_quiz` 事件 `{questionId, choiceIndex}`，每次标记步骤完成产生 `practice_done` 事件 `{stepId}`；eventId 在产生时生成，重试沿用。
- 已同意时事件先写入 outbox，再按每批 ≤50 条上传；断网或失败时保留，联网、页面可见或进入新路由时重试；被 rejected 的事件丢弃。上传成功后刷新服务端进度。
- 同意时清除该账号的本地账号桶，并在 ConsentDialog 中说明本地进度不导入。
- context 刷新时 dataEpoch 与本地键不一致即清除该账号旧代次的本地桶与 outbox；撤回或注销成功后立即清除本设备该账号的全部本地数据。音域只在服务端，前端不缓存。

## 构形、文章与听辨

构形提供三种视图：CMS 内容媒体（图片/动画/视频，带 altText）、声道剖面 SVG、three.js 3D。1.0 必须具备媒体与剖面；3D 视图在组件中预留切换位，关卡无 `model3dMediaId` 时按缺席处理，2.0 按 SRS 补齐。

声道剖面由前端绘制：静态底图（上颚、牙齿、咽腔、喉）+ 可动部件（下颌、双唇、舌尖、舌面、软腭、气流、声带振动示意），按 `articulation.sagittal.keyframes[]` 的器官参数驱动，帧间插值；单帧为静态口型，多帧可播放过程（如 b 成阻→除阻、L30 的 m→a）。参数定义见后端决策图「关卡详情中的学习结构」。遵循 `prefers-reduced-motion`，默认停在首帧；每帧 label 与 articulation.description 作为文字说明。

P04 使用分类、文章目录及详情接口，正文支持受控 practice/audio/image/levels/pro 指令；渲染禁用原始 HTML 与脚本，媒体只接受 `/api/media/` 或预览媒体地址，关卡链接只渲染当前已发布关，未发布时显示不可用状态。

1.0 听辨题结构为 `{id, stimulusMediaId, prompt, options: [{text, mediaId?}], answerIndex, explanation?}`。播放题干音频，选项可带音频；选择后立即判对，答错展示解释并可再答。关卡小测属于 2.0（FR-607）。

## 录音、标定与结果

**标定强制**：开始录音前检查 context.calibration；status 为 none，或 session 且已到期，先进入 CalibrationPanel，不提供跳过。提交返回 409 CALIBRATION_REQUIRED 时（如临时标定在录音期间到期）同样进入标定，标定成功后用原 audioId 与原 submissionId 自动重新提交，无需重录。标定流程：读取 `/api/pitch-calibration` 文本 → 录音 → 上传 purpose=calibration → POST `{audioId, textVersion}`；CALIBRATION_FAIL 展示原因与重录指引。P11 提供重新标定。

**录音**：MediaRecorder 采集浏览器支持的格式（优先 webm/opus，其次 mp4/aac），实时波形用 canvas + AnalyserNode 绘制。录音 blob 只保存在内存，直到提交成功或用户放弃；有未提交录音时离开页面先提示。F0、共振峰、T 值换算和图片在后端计算，前端只渲染。

**提交**：上传 multipart 得到 audioId，再发送 `{audioId, levelId, contentVersion, submissionId}`；一次录音对应一个 audioId 与 submissionId，重录两者都重新生成。拿到 recordingId（200 或 202）后跳转 `/result/:id`。提交页面内遇到可重试失败，用原 submissionId 与原负载重试；离开页面后查看失败记录只提供重新录音。CONTENT_VERSION_CHANGED 时刷新任务、丢弃旧录音并提示按新内容重录；DETECTION_OFF 显示故障说明并保留学习入口。

**结果**：P09 读取 `/api/recordings/{id}`；202 时显示 stage，按 Retry-After 轮询，页面隐藏时暂停、恢复可见时立即查询；504 或 failed 显示失败原因与重新录音。质量不合格（QUALITY_FAIL）显示「本次不能评」与重录指引，不显示分数。主对比曲线与共振峰来自结果快照（ToneCurveChart、FormantChart），曲线 not_available 时说明原因，不伪造。本次录音回放、原始 F0 与共振峰图片统一通过 audioId 读取（`/api/audio/{audioId}/file`、`/f0`、`/formants`、`/formants.png`），原始特征位于折叠区，展开时才请求。示范按 levelId 读取当前公开版本；关卡已下架时示范与「回关卡练习」显示不可用。

**HTTP**：JSON 按 envelope、requestId 处理；QUALITY_FAIL 与 CALIBRATION_FAIL 为 HTTP 200 的业务结果；失败与限流保留真实状态码。媒体直接作为 `<audio>`/`<img>` 地址使用，Range 由浏览器处理。写请求同源发送，不需要 CSRF 令牌。

## 同意、留存与删除

- 同意状态为「未处理」的账号登录后立即弹出 ConsentDialog，展示将自动转存的条数（session/recordings 或 context.pendingTransfer）与本地进度不导入说明；可同意、拒绝或暂不。暂不不调用接口，之后在 P09、P10、P11 提供入口；已拒绝或已撤回的账号不再自动弹出。
- 同意界面明确：自动全部转存当前安全绑定会话中全部未过期、未删除的已完成录音与结果，以及会话临时标定。已有有效同意的账号登录同样触发转存；注册不构成登录或同意。
- 登录或同意响应中的 transfer 以提示呈现：completed 显示「已保存 N 条」，partial 提供「重试」（再次调用授予同意），none 不提示。转存后刷新 context 与当前页面的保存状态。
- 临时上传、录音、结果、标定与缓存从首次上传起最多 72 小时，不续期；P09 与临时记录显示到期时间，到期后显示不可恢复。已存档记录保留至删除，自动存档无逐条保存按钮。
- 本会话临时记录（SessionRecordsPanel）位于 P10（未登录或未同意时）与 P11，可单删、清空并重新开始会话。
- 撤回说明明确删除录音、结果、学习进度与音域；注销须输入密码。成功后清除本设备该账号的本地数据；其他设备在下次读取 context 时按 dataEpoch 清除。单条删除与清空档案按指定范围执行。P10 调用 compare 比较本人同关存档记录，跨版本或音域基准变化时提示可比范围，主要差异只列可比维度。

## 反馈与预览

`POST /api/feedback` 携带 sourcePage、type、content 及适用的 articleSlug、levelId、recordingId、subtype、rating；`POST /api/wishes` 携带希望增加的音/字与 searchQuery。匿名提交受限流保护，429 时显示等待时间。反馈不授权管理员读取私人录音。

后台签发的预览令牌默认 15 分钟，绑定管理员会话、对象和草稿修订。后台「预览」按钮（含文章 Markdown 预览）直接在新窗口打开前端 `/preview/...?token=`；预览页面以 query 中的令牌请求 `/api/preview/*`，媒体使用 `/api/preview/media/{mediaId}?token=`。预览复用 LevelView 与 ArticleView，关闭录音、听辨提交、反馈与学习事件，顶部显示「草稿预览」及到期时间；令牌失效时提示回后台重新签发。

## 前端决策

| # | 决策 | 结论 |
| ---- | ---- | ---- |
| FD-01 | 「录音比较」去向 | `/test/{nextLevelId}`，比较指与标准曲线对比 |
| FD-02 | 推荐起点 | 访客与未同意用户按本地进度计算下一关；无进度回落 L01/第一已发布关 |
| FD-03 | 本地进度分桶 | 访客桶保留；未同意账号用账号桶，退出清除；同意时清除账号桶，不导入 |
| FD-04 | 完成度 | D-24，前端本地与服务端同一规则，依赖 levels.completionKeys |
| FD-05 | 比较 | 单一 ComparePanel，P03/P05 易混入口直达，P06 任选两关 |
| FD-06 | 标定 | 检测强制前置，不可跳过；对话框内嵌检测流程，不单独路由；409 CALIBRATION_REQUIRED 后标定并自动重提交 |
| FD-07 | 同意弹出时机 | 未处理账号登录后立即弹出；可暂不；拒绝、撤回后不自动弹出 |
| FD-08 | 登录注册 | 独立子路由，带 redirect 回跳 |
| FD-09 | 临时记录位置 | P10 未同意态与 P11；同意弹窗显示条数 |
| FD-10 | 移动导航 | 底部 5 标签：首页 / 地图 / 检测 / 档案 / 我的 |
| FD-11 | 失败录音保留 | 仅内存，离开页面提醒；私人音频不写本地存储 |
| FD-12 | 预览渲染 | 全站一套渲染，后台预览打开前端 `/preview` |
| FD-13 | 地图专业说明 | P03 不承载专业说明与 IPA；专业折叠只在 P05 |
| FD-14 | 3D 视图 | 1.0 预留切换位，按缺席处理，2.0 补内容 |
| FD-15 | 重试边界 | 同键重试只在提交页面内；跨页面只提供重新录音 |
| FD-16 | 曲线数据源 | 主对比用结果快照；原始 F0/共振峰/图片按 audioId 读取，放在折叠区 |
| FD-17 | 不做 | P04 SEO 预渲染、多标签页状态同步，1.0 不考虑 |

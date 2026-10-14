# 决策图 · 前端设计规划

> 范围：页面职责、UI 与依赖选型、跨页组件、状态管理与 API 消费。
> 业务需求见 [SRS](srs/README.md)，模块边界见 [目标架构](architecture/02-目标架构.md)，API 契约见 [后端决策图](decision-map-backend.md)。本文描述目标设计。

## 页面与导航

1.0 大众端为 P01–P06、P08–P11，共 10 页；新页面从 P12 起编号。

| 页面 | 路由 | 职责 | 数据来源 |
| ---- | ---- | ---- | ---- |
| P01 首页 | `/` | 入口分流、下一已发布关 | levels、me/context；登录且同意后读取 me/progress |
| P02 搜索 | `/search` | 找关与相近关推荐 | GET /api/search?q= |
| P03 发音地图 | `/map` | 三层闯关进度与易混关并排 | levels + 本地或授权进度 |
| P04 原理子站 | `/principles`、`/principles/:slug` | 按气/声/口型分类的文章目录与正文 | article-categories、articles、articles/{slug} |
| P05 关卡页 | `/learn/:id` | 单关结论、构形、示范、听辨、练习与录音 | levels/{id}、learning-events |
| P06 发音库 | `/library` | 已发布关目录、试听、任意两关比较 | levels |
| P08 检测中心 | `/test` | 选关录音与标定 | levels、detection、pitch-calibration |
| P09 结果 | `/result/:id` | 分数、现象、四步反馈与曲线 | recordings/{id}、audioId 特征 |
| P10 声音档案 | `/archive` | 本人同关记录与前后变化 | me/recordings、me/recordings/compare |
| P11 账号 | `/account` | 账号、同意、撤回、注销与重新标定 | auth/*、me/*、pitch-calibration |

`/learn` 重定向到 `/library`。后台 `/admin` 为后端管理界面入口。管理员真实内容预览使用受保护的 `/preview` 路由，不计入大众端页面集合。

P03 展示学习位置和进度，P06 展示目录与比较工具。具体发音讲解位于 P05；P04 讲普遍原理，参考资料位于文章 references 与关卡专业折叠区。

## UI 与依赖

Vue SPA 在 Vite 工程内嵌 Quasar v2，使用 @quasar/vite-plugin、@quasar/extras 与 sass。路由使用 vue-router，状态使用 Pinia 与 composables，通用浏览器能力使用 @vueuse/core。曲线由 echarts/vue-echarts 渲染；文章使用 markdown-it 及受控指令；openapi-typescript 依据后端 OpenAPI 生成类型；three.js 用于 3D 构形。

依赖版本、Vite 插件兼容性、构建能力及浏览器支持须在实现前核实。响应式导航使用 QLayout 等组件；内容在手机端单列布局，保证触控目标与录音主路径可用。

## 组件与状态

| 组件或状态 | 职责 |
| ---- | ---- |
| PageState / usePageCopy | 加载、空、错误、正常状态与统一文案 |
| levels store | 公开关卡摘要、身份骨架与 availability |
| recording store | 唯一 MediaRecorder 封装及录音状态 |
| useAssessmentFlow / RecorderPanel | P05/P08 共用的录音、提交、查询与失败恢复 |
| DemoPlayer | P04/P05/P06/P08 共用的正式示范播放 |
| ToneCurveChart | P09/P10 共用的曲线与缺失状态 |
| QuizPanel | 1.0 听辨单选题 |
| CalibrationPanel | 标定文本、录音、标定状态与重新标定 |
| ConsentGate | 自动全部转存说明与同意流程 |
| ArticulationFigure | CMS 媒体、SVG、3D 构形视图切换 |
| ArticleView | Markdown 正文、示范、练习、资料与关卡链接 |

Pinia 按关卡、身份与同意、录音、进度等领域管理状态。初始化使用 `/api/me/context`，访客不查询受保护的 progress 接口。退出或切换账号清除账号相关上下文，并使用服务端轮换后的 sid。

`availability` 为 open、temporarily_unavailable、closed。正常已发布关可学习与检测；应急检测故障明确提示但保留学习入口；closed 仅展示地图身份骨架。P01/P06/P08 过滤未发布关。

## 构形、文章与听辨

构形提供三种视图：CMS 图片/动画/视频、前端参数化 SVG 声道剖面、three.js 3D。1.0 必须具备媒体与 SVG，3D 可渐进提供；2.0 按 SRS 验收 3D 动画。SVG 使用发音部位与方法枚举预设；CMS 提供 place、manner、description、mediaAsset、altText 等字段。构形材料与正式授权示范是发布前提；播放使用正式媒体。

P04 使用分类、文章目录及详情接口，正文支持受控 practice/audio/image/levels/pro 表达。渲染须限制可执行内容、校验媒体来源；草稿与私人录音权限由服务端统一控制。分类和关联关卡按公开版本展示。

1.0 听辨题为单选，包含 `{id, stimulusAudioId, prompt, options: [{text, audioId?}], answerIndex, explanation?}`。播放题干音频、显示选项，答错时展示解释。关卡小测属于 2.0（FR-607）。

登录且同意后，每题提交学习事件 `{eventId, levelId, contentVersion, kind: "listen_quiz", detail: {questionId, choiceIndex}}`；服务端验证题目与选项并派生正确性。1.0 事件 kind 为 listen_quiz 或 practice_done。访客与未同意用户只记录本地进度；同意后仅上传新事件，不导入本地历史。

## 录音、标定与结果

MediaRecorder 采集浏览器支持的格式并上传，前端仅通过 canvas + AnalyserNode 绘制实时波形。F0、共振峰、T 值换算和 PNG 在后端计算；前端渲染返回结果。录音格式适配与解码由后端承担。

提交分两步：multipart 上传得到 audioId，再发送 `{audioId, levelId, contentVersion, submissionId}`。版本冲突提示刷新任务；幂等冲突使用 409；处理中响应 202 并依据 recordingId 查询。P09 刷新或直接打开均读取 `/api/recordings/{id}`。

标定文本与状态读取 `/api/pitch-calibration`，录音标定提交 `{audioId, textVersion}`。未标定仍可质量检查与评分，曲线显示 needs_calibration 并提供向导；无有效 F0 显示 not_available。P11 提供重新标定入口，标定不得成为普通评分的强制门禁。

音频文件、F0、共振峰及图片统一通过 audioId 读取，服务端校验归属与有效期。媒体响应支持 Range，前端按媒体类型消费。JSON 按标准 HTTP、envelope、requestId 处理；QUALITY_FAIL 为 HTTP 200 的业务结果，失败与限流保留真实状态码。

## 同意、留存与删除

同意界面明确自动全部转存当前安全绑定会话中全部未过期、未删除的已完成录音与结果。已有有效同意账号登录同样触发；注册不构成登录或同意。处理中录音完成时重校验同意；质量不合格记录只保存质量结论及重录指引。未提交检测的孤儿上传不存档。

临时上传、录音、结果、标定与缓存从首次上传起最多 72 小时；读取、提交、重试与登录不续期，到期显示不可恢复。已存档记录保留至删除。自动存档无需逐条保存按钮。

撤回说明明确删除录音、结果、学习进度与音域；注销验证密码。当前设备同时清除相关本地数据；其他离线设备在下次联网校验身份和同意时清除。单条删除与清空档案按指定范围执行。P10 调用 compare 比较本人同关存档记录，跨版本提示可比范围。

## 反馈与预览

`POST /api/feedback` 携带 sourcePage、type、content 及适用的 articleSlug、levelId、recordingId、subtype、rating；`POST /api/wishes` 携带希望增加的音/字与 searchQuery。匿名提交受限流保护，反馈不授权管理员读取私人录音。

后台签发绑定管理员会话、对象和草稿修订的短期预览令牌，默认 15 分钟。真实 `/preview` 页面读取同结构草稿 JSON，媒体通过 `/api/preview/media/{mediaId}`。退出管理员会话或草稿修订变化时令牌失效。

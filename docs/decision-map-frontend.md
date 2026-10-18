# 决策图 · 前端设计规划

> 范围：页面职责与路由、UI 与依赖选型、组件划分、状态管理与关键交互决策。业务需求见 [SRS](srs/README.md)，API 契约见 [后端决策图](decision-map-backend.md)，前端架构与实施方案见 [04-前端架构与实施方案](architecture/04-前端架构与实施方案.md)。

## 页面与路由

1.0 页面为 P01–P06、P09–P11，共 9 页（D-03）；关卡学习与录音检测统一在 P05 完成，新页面从 P12 起编号。

| 页面 | 路由 | 职责 | 数据来源 |
| ---- | ---- | ---- | ---- |
| P01 首页 | `/` | 四个主按钮、搜索框、已开放关卡列表、下一关推荐 | `levels`、`me/context`、`me/progress` |
| P02 搜索 | `/search?q=` | 搜索汉字/拼音/关卡名、无结果时展示相近关与「希望增加」 | `GET /api/search?q=`、`POST /api/wishes` |
| P03 发音地图 | `/map` | 三层闯关定位图（单韵母/声母/拼读）、开放状态、个人进度、易混关并排比较入口 | `levels`、`me/progress` |
| P04 原理子站 | `/principles`、`/principles/:slug` | 气/声/口型分类目录与原理文章正文、示范播放、短练习与关联关卡入口 | `article-categories`、`articles`、`articles/{slug}` |
| P05 关卡页 | `/learn/:id` | 一句话结论、多视图构形、示范音频、听辨题、3–5 步练习、误区、声学说明、**内嵌本关录音检测区（含前端实时声学反馈）** | `levels/{id}`、`learning-events`、`audio/uploads`、`pitch-calibration`、`recordings` |
| P06 发音库 | `/library` | 按层索引已开放关卡卡片、示范试听、任选两关并排比较 | `levels` |
| P09 结果 | `/result/:id` | 多维声学可视化对比（基频 F0、共振峰 F1/F2、送气波形/VOT、语谱图）、分数、现象、四步反馈、录音环境质量提示、回放与重录 | `recordings/{id}`、`audio/{audioId}/*`、`levels/{id}` |
| P10 声音档案 | `/archive`、`/archive/compare?a=&b=` | 按关卡展示本人历史录音记录、删除单条或清空、同一关至少两次记录并排回放与曲线对比 | `me/recordings`、`me/recordings/compare` |
| P11 账号 | `/account`、`/account/login`、`/account/register` | 注册、登录、退出、**设置/修改「方言区 / 母语背景」**、个人音域标定、清空声音档案、验证密码注销账号 | `auth/*`、`me/*`、`pitch-calibration` |

| 辅助路由与锚点 | 说明 |
| ---- | ---- |
| `/learn/:id#quiz`、`#practice`、`#record`、`#step-{stepId}` | 关卡页内区块锚点；首页「跟着练」「录音比较」及 P09 四步练习回跳使用 |
| `?compare=L13,L14` | 在 P03 / P05 / P06 上打开关卡并排比较视图 |

### 首页四个主按钮与导航（FR-202）

| 入口 | 去向 |
| ---- | ---- |
| 搜一个音 | `/search`（P02） |
| 看懂发音 | `/principles`（P04），页内提供进入发音地图 `/map`（P03）的入口 |
| 跟着练 | `/learn/{nextLevelId}#practice`（下一关 P05 的练习区） |
| 录音比较 | `/learn/{nextLevelId}#record`（下一关 P05 的录音区，提交后进入 P09 查看对比结果） |

桌面端顶部导航列出核心页面并常驻搜索框；手机端底部标签栏方便单手切换首页、地图、发音库、档案与账号。

## UI 与技术依赖

- **核心框架**：Vue 3 + TypeScript + Vite，UI 组件库采用 Quasar v2，路由使用 `vue-router`，状态管理使用 Pinia 与 composables，通用工具使用 `@vueuse/core`。
- **声学与构形可视化**：
  - **前端实时声学反馈**：基于浏览器原生 Web Audio API（`AudioContext` + `AnalyserNode` / `AudioWorklet`）与 HTML5 Canvas，在录音过程中零延迟绘制实时波形、音量包络与实时音高（F0）曲线。
  - **事后声学对比图表**：使用 `echarts` / `vue-echarts` 渲染 P09 与 P10 的基频（F0）对比曲线、元音空间（F1/F2）散点与区域图。
  - **2D/3D 发音构形**：2D 声道剖面由前端 SVG/Canvas 根据 `sagittal.keyframes[]` 关键帧参数插值绘制；3D 口腔模型使用 `three.js` 按需懒加载。
- **契约与类型**：通过 `openapi-typescript` 从后端 OpenAPI 自动生成 TypeScript 类型，使用原生 `fetch` 封装统一请求客户端。

## 组件与状态划分

| 归属 | 组件 / Store | 职责 |
| ---- | ---- | ---- |
| 外壳 | `AppShell`、`PageState` | 响应式导航框架；加载、空状态、错误提示统一展示 |
| 关卡展示 | `LevelCard`、`LayerMap`、`ConfusablePairList`、`LevelNav`、`ComparePanel` | 关卡卡片、P03 三层闯关地图、易混音并排比较面板（P03/P05/P06 共用）、上下关导航 |
| 关卡学习 | `LevelView`、`ArticulationFigure`、`SagittalView`、`DemoPlayer`、`QuizPanel`、`PracticeStepper`、`MisconceptionList` | P05 结论、多视图构形（媒体 / 2D 声道剖面关键帧动画 / 3D 视图）、示范播放、听辨单选、3–5 步跟练、误区与声学说明 |
| 原理文章 | `ArticleView` | Markdown 正文渲染、示范音频播放、短练习与关联关卡链接 |
| 搜索与反馈 | `SearchBox`、`WishDialog`、`FeedbackWidget` | 搜索框、「希望增加」提交弹窗、纠错反馈组件 |
| 录音与实时反馈 | `RecorderPanel`、`RealtimeAcousticCanvas`、`CalibrationPanel`、`RecordingTips`、`MicPermissionGuide`、`ProcessingStage` | 录音控制、**录音端实时波形/音量/实时 F0 音高曲线绘制**、可选音域标定面板（支持跳过）、麦克风权限指引、202 处理阶段展示 |
| 检测结果 | `QualityVerdict`、`ScoreCard`、`PhenomenaList`、`FourStepsList`、`ToneCurveChart`、`FormantChart`、`AcousticDetail` | P09 录音环境质量温和提示、分数卡、可观察现象、四步反馈（带跳回 P05 练习锚点）、F0 对比曲线、F1/F2 元音空间图、送气段波形与语谱图展示 |
| 账号与档案 | `LoginForm`、`RegisterForm`、`DialectSelector`、`ArchiveList`、`ArchiveCompareView`、`DangerConfirmDialog` | 注册登录、**方言区/母语背景选择器**、P10 历史档案列表与同关并排对比、删除/清空/注销二次确认弹窗 |

| Store / Composable | 职责 |
| ---- | ---- |
| `context` store | 维护当前登录用户、方言区/母语背景、音域标定状态与 `nextLevelId` |
| `levels` store | 缓存关卡列表、开放状态、易混音对与 `completionKeys` |
| `progress` store | 管理用户听辨与练习完成进度，按 D-24 计算关卡完成状态与下一关 |
| `recorder` composable | 封装 `MediaRecorder` 与 Web Audio API 实时分析节点（输出实时时域波形、RMS 音量、实时 F0 基频帧） |
| `player` store | 全局音频播放控制，保证同一时刻只有一个音频播放 |
| `useAssessmentFlow` | P05 内嵌录音检测状态机（可选标定/跳过 → 录音与实时反馈 → 上传 → 提交 → 轮询/跳转 P09） |

## 录音、实时声学反馈与结果展示

1. **音域标定（支持跳过，D-20）**：
   - 未标定用户在 P05 准备录音时，展示标定提示入口，同时提供明显的「跳过标定，直接录音」按钮；用户可随时在 P05 或 P11 账号页完成或重新进行标定。
2. **录音与前端实时声学反馈（FR-907）**：
   - 开启麦克风后，音频流同时接入 `MediaRecorder`（用于录制上传文件）与 Web Audio `AudioContext` 分析管线。
   - **实时视觉渲染**：在 `RealtimeAcousticCanvas` 中以 ≥30 fps 实时绘制（1）时域波形与 RMS 音量指示条（直观提示音量是否过小或爆音）；（2）实时基频（F0）轨迹曲线（采用自相关 / YIN / McLeod 等时域基频算法提取有声段 Hz 值并平滑绘制，静音或清辅音段自然留空），让用户在发声瞬间看到自己的声调高低与起伏走向。
3. **提交与结果（P09）**：
   - 停止录音后可本地试听或重录；点击提交后上传音频并调用 `POST /api/recordings`。
   - 同步完成（200）或轮询完成（202 → 200）后在 P09 渲染完整结果：顶部/旁侧展示非阻断式的录音环境质量提示（若有音量偏小、底噪偏大等），主体区域展示分数、现象描述、基频 F0 对比曲线、共振峰 F1/F2 元音空间图、送气段波形（VOT）/语谱图以及四步反馈。

## 前端关键决策（FD）

| 编号 | 决策 | 结论 |
| ---- | ---- | ---- |
| FD-01 | 录音入口 | 统一内嵌于关卡页 P05（`/learn/:id#record`），不设独立检测中心页面 |
| FD-02 | 音域标定 | 支持跳过直接录音（D-20）；标定面板以对话框形式在 P05 或 P11 唤起 |
| FD-03 | 实时声学反馈 | 录音期间在前端利用 Web Audio API 零延迟绘制实时波形、音量与实时 F0 音高轨迹 |
| FD-04 | 质量提示展示 | P09 始终展示评分与声学图像；环境质量问题作为温和提示呈现，不拦截结果 |
| FD-05 | 关卡并排比较 | 单一 `ComparePanel` 组件，在 P03、P05 易混入口与 P06 任意两关比较中共用 |
| FD-06 | 方言/母语背景 | 注册表单与 P11 账号页均支持选填/修改「方言区 / 母语背景」 |
| FD-07 | 3D 构形视图 | `ArticulationFigure` 支持媒体、2D 声道剖面与 3D 视图切换，按关卡实际配置的资源展示 |

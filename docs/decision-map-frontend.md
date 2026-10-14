# 决策图 · 前端设计规划

> 范围:页面集合与职责、UI 库与开源包选型、跨页组件与状态架构、前端侧契约消费。
> 上下文:SRS(docs/srs/)、目标架构 §6(ADR-10 页面登记表)、后端 API 决策图
> (docs/decision-map.md,已定案,端点清单以其为准+本次会话回填)。

## 进度

- 骨架现状盘点完成(2026-10-15):路由与 pages.ts 已对齐 P01–P11,views 为
  带意图注释的占位骨架;可保留资产:PageState+usePageCopy 四态、levels store
  三值 availability、recording store「唯一 MediaRecorder 封装」意图。
- **#1–#4 已定案**(2026-10-15 第一次 grilling);琐碎项见「零票定案」。
- **#5–#8 已定案**(2026-10-15 第二次 grilling):P07 退役(页面集合 10 页)、
  P04 升级为博客式原理子站、构形三视图切换、小测移出 1.0。
- **全部票据已定案,决策图完成**。产出:SRS 修订清单(文末,待需求方落文档)、
  后端决策图回填(已同步)。下一步:/to-prd 排实现或直接按路线图开工。

## 页面清单定案(1.0 = 10 页;P07 空缺,编号不复用,新增从 P12 起)

| 页 | 路由 | 职责 | 主要 FR | 数据源 |
| ---- | ---- | ---- | ---- | ---- |
| P01 首页 | `/` | 入口分流 | FR-202 四主按钮/203/204/205/206 | GET /api/levels + /api/me/progress |
| P02 搜索 | `/search` | 找到一关(薄视图) | FR-301~305 | levels 客户端过滤(?q=) |
| P03 发音地图 | `/map` | 闯关进度:我在哪层、下一关、易混并排 | FR-401~404 | levels + progress |
| P04 原理子站 | `/principles` + `/principles/:slug` | 博客式发音原理文章(不枚举具体音) | FR-501~505 + 原 802~804 的 references | GET /api/content/principles |
| P05 关卡页 | `/learn/:id` | 单关看听辨练录 | FR-601~610(小测移出) | GET /api/levels/{id} + learning-events |
| P06 发音库 | `/library` | 已发布关目录卡片+试听+任意两关比较;不承载进度 | FR-701~703 | GET /api/levels |
| P08 检测中心 | `/test` | 选关录+标定 | FR-901~908、FR-1006 | levels + detection 子对象 |
| P09 结果 | `/result/:id` | 看懂差距 | FR-1001~1010 | GET /api/recordings/{id} + f0/formants |
| P10 声音档案 | `/archive` | 前后变化 | FR-1101~1103、FR-104 | GET /api/recordings?levelId= |
| P11 账号 | `/account` | 账号与同意 | FR-106~108 | /api/auth/* + /api/me/* |

结构调整累计(#1 + 第二次会话):

- AdminView + /admin 路由退役(管理界面 = 后端 starlette-admin,vite 代理直通);
  /learn(无 id)重定向 /library,目录职责归 P06;/feedback/:id 改 /result/:id。
- **P07 专业资料页退役**:资料元数据并入 P04 文章 references 与 P05 专业折叠区。
- **P04 = 博客式原理子站**:不枚举具体发音;具体音的讲解全部住在 P05,
  从 P06 卡片/搜索/地图进入。内部子路由 /principles(文章目录,按
  气/声/口型三分类)+ /principles/:slug(文章页)。
- **P03/P06 职责切清**:P03 = 三层闯关进度图 + 10 组易混并排(FR-403);
  P06 = 目录卡片(名称/拼音/汉字/试听/进入)+ 任意两关比较(FR-703)。
  两页不做成同一形态:P03 不做试听目录,P06 不做进度。

跨页复用组件:RecorderPanel(P05/P08,useAssessmentFlow 的壳)、
ToneCurveChart(P09/P10)、DemoPlayer(P05/P06/P08/P04)、
QuizPanel(P05 听辨)、CalibrationPanel(音域标定向导)、
ConsentGate(存档前同意流)、ArticulationFigure(P05 构形,三视图切换容器)、
ArticleView(P04 Markdown 渲染)。

依赖定案(#2/#4/#5/#6 修订后):加 quasar v2 + @quasar/vite-plugin v2 +
@quasar/extras + sass、markdown-it(#7 原理文章渲染)、openapi-typescript(dev);
移除 element-plus、@element-plus/icons-vue、pitchy;
**three 保留**(#6 修订:三视图之一);保留 vue-router、pinia、@vueuse/core、
echarts、vue-echarts。

## 零票定案(琐碎,不值得开票)

- pitchy 移除:F0 全走后端(ADR-8);录音中只画波形(canvas + AnalyserNode 原生)。
- TTS 合成示范兜底退役:FR-1207 媒体齐全方可发布,已发布关必有正式示范;
  useSpeechDemo/TTS_DISCLAIMER 退役。
- units store 退役:GET /api/levels + levels store 承担(后端决策图 #5)。
- 数据层维持 Pinia + composables,不引 vue-query:10 页规模,现有模式是资产。
- 搜索客户端过滤(30 关规模),不新增搜索端点;levels 列表响应须带一句话
  结论/学习标签等摘要字段(FR-302,已回填后端契约备注)。
- 录音格式:MediaRecorder 原生 webm 上传,后端 soundfile→ffmpeg 回落转换
  (backend/audio/decoding.py 意图已覆盖),前端不做 WAV 编码。
- P09 结果恢复:直接 GET /api/recordings/{id}(后端决策图 #1),原「内存结果
  恢复」复杂度删除;刷新/直开本页不再是特殊流。
- 移动端主路径(NFR-06)由 Quasar 响应式体系承担(QLayout 抽屉导航、触控
  目标);内容布局仍需单列化 media query。
- **反馈拆两个端点**:POST /api/feedback(sourcePage + levelId?,type=
  understood|unclear|result_match|error_report)+ POST /api/wishes
  (希望增加的音/字,含触发它的搜索词);均匿名挂 sid、统一 envelope,
  管理界面「反馈处理」动作承接。
- **learning-events kind 收窄**:listen_quiz | practice_done
  (mini_quiz 随小测移出 1.0,后端决策图已回填)。

## #1: 页面集合三项结构调整 ✔ 已定案 2026-10-15

Blocked by: —
Type: Grilling

### Question

前端 AdminView+/admin 路由与后端 starlette-admin 挂载冲突;/learn(无 id)
30 关总览与 P06 发音库职责重叠;/feedback/:id 命名与页义不符。三项是否调整?

### Answer

**三项都做**:AdminView+/admin 退役;/learn 无 id 重定向 /library(P05 只留
/learn/:id);/feedback/:id 改 /result/:id。页面集合 = SRS 4.1 的 11 页,无重复职责。
(第二次会话又退役 P07,见页面清单与 #7。)

## #2: P05 构形与 P09 可视化的技术范围 ✔ 已定案 2026-10-15(构形部分被 #6 修订)

Blocked by: —
Type: Grilling

### Question

FR-603 只要「图或动画」,图即可合规。three.js(约 600KB,3D 口型动画)与
pitchy(前端测音高)去留?

### Answer

**移除 pitchy**(F0 全走后端,录音中只画波形)。P09 曲线对比用 ECharts、共振峰
用后端 PNG(#11/#13),不做前端声学计算。构形部分 three.js 的去留与形态
由 #6 修订定案(最终:保留,三视图之一)。

## #3: 音域标定(FR-1006)的入口与触发 ✔ 已定案 2026-10-15

Blocked by: —
Type: Grilling

### Question

后端 T 值换算发生在评分时,标定必须先于提交录音;且只有开放音高维度的关需要。
入口放哪?

### Answer

**提交流程内嵌门禁**:useAssessmentFlow 提交前检查「本关 allowed_metrics 含
音高 && 当前无音域」→ 弹 CalibrationPanel 向导(读设定文本→录→POST
/api/pitch-calibration)→ 完成后继续提交。触发点唯一、口径统一,只在需要的
关出现;重新标定入口放 P11 账号页(后端决策图 #7 已预留)。

## #4: UI 组件库:Element Plus → Quasar v2 ✔ 已定案 2026-10-15

Blocked by: —
Type: Grilling(含调研,2026-10 生态现状)

### Question

NFR-06 要求 iOS Safari/Android Chrome 完成主路径。主流库里真为「一套代码
同时优化 PC+移动端」设计的只有 Quasar(Vuetify/PrimeVue 桌面倾斜,TDesign
双包,EP/Naive/Arco 桌面优先)。换不换?何时换?

### Answer

**换 Quasar v2,趁骨架期换**(1–3 天机械替换成本,越晚越贵)。动因:录音练声
是手机原生场景,移动端体验是产品能力不是装饰;Quasar 组件内置移动交互
(QLayout 抽屉、触控目标),将来可直接打包 Capacitor App。接受代价:Material
风格 + 框架级约定,冻结日(2026-10-27)风险由需求方自担,必要时顺延。

## #5: Quasar 迁移形态与 Vite 8 兼容性 ✔ 已定案 2026-10-15

Blocked by: #4
Type: Research(2026-10-15 查证)

### Question

现有 Vite 8 工程(package.json: vite ^8.1.5)内嵌 Quasar(@quasar/vite-plugin
+ sass)vs 迁到 Quasar CLI 工程?vite 插件对 Vite 8 的兼容性未验证。

### Answer

**留在现有 Vite 8 工程内嵌接入,不迁 Quasar CLI。**

- @quasar/vite-plugin **v2 的 peer dependency 即 Vite 8+**(官方文档与 npm
  均确认,2026-10 时点);装 quasar@2 + @quasar/vite-plugin@2 + sass 即可。
- 插件形态的已知限制:不支持 SSR/SSG 构建、不支持 RTL 语言包——本项目纯
  SPA + 中文,均不碰。
- 剩余工作为机械替换,归实现(PRD 层),不再开票:el-* → q-* 组件映射
  (App.vue→QLayout、ElMessage→Notify、pages.ts 图标名→material-icons、
  PageState/PageFeedback 换装),12 views 换装后 type-check+build 过。

## #6: P05 构形的呈现形态 ✔ 已定案 2026-10-15(推翻 #2 的「图即可」保守案)

Blocked by: #2
Type: Grilling

### Question

构形按什么做?①CMS 直接放图/动图/视频;②前端参数化 SVG 声道剖面图
(部位×方法预设表);③three.js 3D 建模。

### Answer

**三视图同时存在、可来回切换**(ArticulationFigure 容器组件,segmented
control 切换),发音动作指导多角度呈现:

- 视图 A:CMS 媒体(图/动图/视频)——构形材料可用仍是发布前提(FR-1203);
- 视图 B:SVG 参数化声道剖面图——前端内置「发音部位×方法」预设表
  (29 关有限枚举,语音学标准数据),CMS 只填枚举字段;
- 视图 C:three.js 3D 建模。
- 构形字段 = {place, manner, description, mediaAsset?, altText};
  three 保留在 1.0 依赖。
- 风险注记:3D 建模人力消耗大,切换框架先行就位,视图 C 可渐进填充
  (冻结前允许先 A+B 可用、C 渐进)。

## #7: P04 内容与公开反馈的 API 缺口(后端契约补丁) ✔ 已定案 2026-10-15

Blocked by: —
Type: Grilling

### Question

后端决策图端点清单缺:①P04 原理内容读取;②(原)P07 资料列表;③公开反馈
提交(FR-1501~1504)。形状定什么?定案后回填后端决策图。

### Answer

**P07 退役后缺口收窄为三件事,已回填后端决策图:**

- `GET /api/content/{key}`:通用内容端点,CMS 一张 content 表
  (key/版本/状态)。key=principles 返回**扁平文章列表**:
  `{nodes: [{slug, title, category(气|声|口型,可扩展), order,
  body(Markdown), references[]}]}`。
  正文 Markdown + 五指令:`:::practice / :::audio{id} / :::image{id|alt} /
  :::levels{L01,L04} / :::pro`——分别落 FR-502/505/502/503;
  references 承接原 P07 资料元数据(标题/来源/许可/适用边界/关联关,
  FR-802~804)。缺材料的节点不发布(FR-504 段落级缺席)。
  前端 markdown-it + directive 插件渲染。
- `POST /api/feedback`:页面情境反馈,type=understood|unclear|
  result_match|error_report,带 sourcePage + levelId?。
- `POST /api/wishes`:希望增加的音/字,含触发搜索词(FR-304/1503)。
- 两者匿名挂 sid、统一 envelope;管理界面「反馈处理」动作承接(FR-1407)。
- 放弃的方案:伪装成关卡 L00(污染关卡体系);专用 /api/principles 端点
  (无复用);结构化 blocks 数组(内容组写作门槛高,Markdown 更顺手)。

## #8: P05 听辨题契约(小测移出 1.0) ✔ 已定案 2026-10-15

Blocked by: #7
Type: Grilling

### Question

关卡字段「听辨与小测」无 schema。听辨题与小测题的数据结构、对错上报口径?

### Answer

**只做听辨,小测整个移出 1.0(推迟 2.0)。**

- 听辨题(关卡 content JSON,单选):
  `{id, stimulusAudioId, prompt, options: [{text, audioId?}],
  answerIndex, explanation?}`——播 stimulus 音频→文本选项→答错展示解释。
- 上报:一题一事件,`POST /api/learning-events`
  `{levelId, kind: "listen_quiz", detail: {questionId, choiceIndex, correct}}`;
  访客挂 sid,进度派生按 correct 汇总(ADR-11),不做整卷、不覆写。
- learning-events kind 收窄为 listen_quiz | practice_done。
- SRS 连锁修订:FR-607 小测→2.0;FR-1203 发布前置本就不含小测,发布链不动;
  附录 A「听辨与小测」字段组 1.0 只录听辨题。多选/判断等题型 2.0 再扩 kind。

## SRS 修订清单(2026-10-15 已按用户指示落 docs/srs/)

| 条目 | 修订 |
| ---- | ---- |
| FR-607 小测 | 1.0 移除,推迟 2.0;08-验收对应条目同步删 |
| FR-801~804(P07) | 页面退役;资料元数据并入 P04 文章 references 与 P05 专业折叠;边界句由 P09/P01 承担 |
| FR-701~703(P06) | 补职责注记:目录+比较工具页,不承载进度(与 P03 切清) |
| FR-501~505(P04) | 页面形态改为博客式原理子站(文章列表+文章页,三分类),不枚举具体音 |
| 附录 A 听辨与小测 | 1.0 只录听辨题 |
| D-03 页面结构 | 1.0 = P01–P06、P08–P11 共 10 页;P07 空缺不复用,新增从 P12 起 |

## 后端决策图回填(已同步 docs/decision-map.md,2026-10-15)

- 端点清单 +3:GET /api/content/{key}、POST /api/feedback、POST /api/wishes;
- learning-events 注释改为 kind: listen_quiz | practice_done。

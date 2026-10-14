# 决策图 · 后端 API 架构规划

> 范围:声学(检测)、账号、CMS 三域的 API 端点设计;开源包引入评估。
> 上下文:SRS(docs/srs/)、目标架构(docs/architecture/02)、重构路线图(03,1.0 冻结 2026-10-27)。
> 已由 ADR 定案、不再开 ticket:同步处理+幂等键(ADR-9)、讯飞为主评分+Provider 协议(ADR-2)、
> T 值换算归后端(ADR-8)、录音存文件系统(ADR-6)、三态 CMS+独立检测开关(ADR-3)。

## 进度

- **声学域:已全部定案**(2026-10-15,#1–#7、#11–#13),端点清单见下节。
- **账号域:#8 已定案**(2026-10-15):fastapi-users + sid 保留 + 升级补丁,
  范围补充 G1–G6 见 #8 答案;账号端点清单待 #10 后成文。
- **CMS 域:#9 已定案**(2026-10-15):自研域逻辑 + sqladmin/starlette-admin。
- **#10 已定案**(2026-10-15):同进程整合,SQLite 维持,G3 修订(管理员走
  管理界面自带登录)。
- **全部票据已定案,决策图完成**(2026-10-15);下一步转实现规划(/to-prd
  或直接按路线图 03 开工)。
- **前端会话回填**(2026-10-15,来源 docs/decision-map-frontend.md #7/#8):
  端点清单 +3(GET /api/content/{key}、POST /api/feedback、POST /api/wishes);
  learning-events kind 收窄为 listen_quiz | practice_done(小测移出 1.0)。

## 声学端点清单(定案汇总)

统一响应 envelope(全部 HTTP 200,决策图 #3):`{ code, message, data, nextStep? }`;
JSON camelCase + openapi-typescript 自动生成契约(#6);匿名会话 Cookie `sid`(#4)。

```
# 音频上传面(公开;匿名自动挂 sid;audioId 不可猜测;未引用 7 天 TTL)
POST   /api/audio/uploads                     # multipart → {audioId, duration, format}
GET    /api/audio/{audioId}                   # 元数据
GET    /api/audio/{audioId}/file              # 原音频回放
GET    /api/audio/{audioId}/f0                # F0 数据(首取算+缓存,#13)
GET    /api/audio/{audioId}/formants          # 共振峰数值(独立缓存)
GET    /api/audio/{audioId}/formants/image    # 共振峰图片 PNG(matplotlib Agg)

# 音域标定(#7)
GET    /api/pitch-calibration/text            # 管理员设定的标定朗读文本
POST   /api/pitch-calibration                 # {audioId} → 计算并保存音域(会话/用户)

# 检测主链路(#1/#12:两步提交)
POST   /api/recordings                        # {audioId, levelId, submissionId} → 同步质量+结果
GET    /api/recordings/{id}                   # P09 重进(会话或归属校验)
GET    /api/recordings?levelId=…              # 档案/同关比较列表(P10)
GET    /api/recordings/{id}/audio             # 录音回放
DELETE /api/recordings/{id}                   # 单删(硬删+审计)
DELETE /api/recordings                        # 清空档案
GET    /api/recordings/{id}/f0|formants|formants/image        # 与上传面同 service

# 学习事件(进度派生源,#1;kind 收窄见前端 #8 回填:mini_quiz 移出 1.0)
POST   /api/learning-events                   # {levelId, kind: listen_quiz|practice_done, detail}
GET    /api/me/progress                       # 进度派生只读

# 关卡读取(#5)
GET    /api/levels                            # 已发布列表 + availability
GET    /api/levels/{id}                       # 详情 + detection 子对象(朗读文本/示范 audioId/开放维度)

# 内容页与公开反馈(前端决策图 #7 回填,2026-10-15)
GET    /api/content/{key}                     # 原理子站等富内容(key=principles:扁平文章列表,Markdown 指令正文+references)
POST   /api/feedback                          # 页面情境反馈(type: understood|unclear|result_match|error_report;带 sourcePage+levelId?)
POST   /api/wishes                            # 希望增加的音/字(含触发搜索词);两者匿名挂 sid、统一 envelope

# 工具/诊断(#2:保留公开,Phase 0 加限流)
POST   /api/audio/quality                     # 信号维质检(原 /api/audio/features 被 #11 模型取代)
POST   /api/audio/score                       # 2.0 本地对比(LocalAcousticProvider)
GET/POST /api/asr/status | load | diagnose    # 诊断+JSONL 实验日志
```

```
# 账号域·fastapi-users 挂载(/api/auth/*,envelope 豁免:原生 401/400,#8)
POST   /api/auth/register            # {username,password}(FR-107;用户名 3–32 唯一/密码≥8)
POST   /api/auth/login               # 登录;sid 消费中间件认领访客数据(#8 补丁)
POST   /api/auth/logout              # 退出
GET    /api/auth/me                  # 当前用户(users 路由自带)

# 账号域·自研(统一 envelope;登录会话鉴权)
GET    /api/me/consent               # 同意状态+时间线(FR-106 账号页)
POST   /api/me/consent               # 授予同意(写 CONSENT_RECORD,FR-102)
DELETE /api/me/consent               # 撤回同意(FR-104:立即停止新增保存)
DELETE /api/me/account               # 注销:清空档案+匿名化+会话失效(FR-108)
GET    /api/me/progress              # 进度派生只读(与声学清单同一条)

# 管理界面(#10:非 REST 域,/admin 挂载,自带单管理员登录)
# 发布/下架/检测开关/版本回退/审计/反馈处理/媒体上传 = 界面自定义动作
# 调 domain 纯函数;替代原 cms_routes 的 /api/admin/units/*
```

## #1: 声学·录音提交端点的资源模型 ✔ 已定案 2026-10-15

Blocked by: —
Type: Grilling

### Question

录音提交主端点如何建模?架构时序图写 `POST /api/recordings`,但现有占位代码是
`/api/learning-records`(把录音、检测结果、学习事件混在一个资源里)。
需要定:资源命名、层级(扁平 vs 挂在 level 下)、学习事件是否分离。

### Answer

**采用 A:扁平 `/api/recordings` 资源 + 学习事件独立。**

- `POST /api/recordings`:multipart(audio + level_id + submission_id 幂等键),
  同步返回「录音元数据 + 质量两维 + (合格时)完整检测结果」;
- `GET /api/recordings/{id}`:P09 刷新/重进,返回同一结果对象;
- `GET /api/recordings/{id}/audio`:档案重听,归属/会话校验;
- `GET /api/recordings?level_id=…`:档案与同关比较列表(P10);
- `DELETE /api/recordings/{id}`、`DELETE /api/recordings`(清空档案);
- `POST /api/learning-events`(kind=listen_quiz|mini_quiz|practice_done)独立资源,
  解决 G-09 进度派生口径;进度无覆写入口,GET /api/me/progress 派生读取。
- ASSESSMENT_RESULT 1:1 内嵌于 recording 表示,不建独立资源;
  P09 路由 `/feedback/:id` 的 id 即 recording_id。
- 现有 `/api/learning-records`、`/api/users/{uid}/learning-records` 占位端点废弃。

## #2: 声学·工具端点(/api/audio/*、/api/asr/*)在 1.0 的去留

Blocked by: —
Type: Grilling

### Question

现有占位路由暴露了声学工具端点(features/quality/score)与 ASR 诊断端点。
架构文档把 audio/ 定位为内部工具层,前端 1.0 只需要检测闭环一个入口。
这些端点对外暴露、收进 admin、还是 1.0 不挂路由?

### Answer

**保持公开——定位是前端声学可视化的正式数据源,不是调试端点。**

- 前端需要展示 F0 曲线、共振峰(F1/F2)等声学信息(产品核心:「看得见的声音」);
  `/api/audio/features` 等工具端点承担这一数据供给,1.0 保持公开路由。
- 已同步修改文档:SRS 02 附录 A「专业折叠」补回声学参考值字段组、
  FR-1005 补共振峰对比;架构 §1/§4/§5 补「前端声学信息一律出自后端」。
- 附带条件(Phase 0 收口时处理):
  - 契约纳入 OpenAPI 草案(与主链路端点同标准),前端类型同步;
  - `/api/audio/features`、`/api/asr/diagnose` 触发重计算(parselmouth/torch),
    需加简单限流或并发=1,防匿名算力滥用(上传 20 MiB 上限已有);
  - 特征展示的数据流(上传式 vs 结果内嵌 vs 示范预计算)见 #11。

## #3: 声学·质量不合格与处理失败的 HTTP 语义

Blocked by: #1
Type: Grilling

### Question

FR-1001/FR-1301:质量不合格时停止评分、只给重录指引;FR-906:处理失败要说明环节。
「质量不合格」是有效业务结果还是 HTTP 错误(200 带 quality 对象 vs 4xx)?
外部评分服务异常、解码失败、超时各映射什么状态码与错误体?

### Answer

**C:一律 HTTP 200 + body 内 `code` 区分(统一响应 envelope)。**

- 所有业务结果与处理失败都回 200,由 body 的 `code` 字段区分成功与失败:
  - 成功(质量合格):code=OK,data 含完整结果对象;
  - 质量不合格(业务结果):code=QUALITY_FAIL,result 缺省,data 带
    quality 两维结论 + 重录指引;
  - 处理失败按环节映射 code:DECODE_FAILED / PROVIDER_DOWN / TIMEOUT /
    LEVEL_NOT_PUBLISHED / DETECTION_OFF / IDEMPOTENCY_CONFLICT / FILE_TOO_LARGE。
- 统一 envelope:`{ code, message, data, next_step? }`——next_step 承载
  FR-906「说明环节与下一步」的机器可读口径,前端按 code 分支渲染。
- 一致性:GET /api/recordings/{id} 与 POST 同口径(200+code),幂等重放
  返回原响应。
- 实现注记:FastAPI 请求校验默认回 422/413,要全 200 需注册全局
  exception handler 统一包装;监控/告警/前端埋点改看 code,不看状态码;
  OpenAPI 里要为 200 声明多种 code 的响应模型,文档成本略增。

## #4: 声学·访客会话与「当次可见」的落地机制

Blocked by: —
Type: Grilling

### Question

FR-101/FR-103:访客录音结果仅本会话可见。GET 结果、GET 音频如何对访客鉴权?
访客 session 如何产生(匿名 Cookie?签名 token?),与将来账号体系如何衔接?
这是声学 API 形状的前置,也是账号域的接口点。

### Answer

**A:匿名会话 Cookie。**

- 首次任意请求由服务端自动签发 `sid`(随机 ID,HttpOnly + 签名 Cookie),
  无须登录、无须前端配合;
- 访客的上传(audio_id)与录音(recording)记录挂当前 sid;
  `GET /api/recordings/{id}`、`/audio` 校验「sid 匹配 或 已登录且归属」;
- 将来登录(纵切 C):同一 Cookie 升级为认证会话,会话内访客录音可
  认领到账号;存档裁决仍只在服务端(NFR-15);
- 清 Cookie = 会话终结,「结果当次可见」语义准确;sid 不可猜测,
  防遍历他人访客录音。
- **2026-10-15 修订(#8)**:登录机制改由 fastapi-users 承担;sid 保留为
  访客锚点不变;「同一 Cookie 升级」改为「登录时中间件消费 sid + 认领
  数据 + 清除 sid Cookie」的补丁,对外语义不变。

## #5: 声学·检测任务配置的读取端点

Blocked by: —
Type: Grilling

### Question

FR-902:录音前要听示范、看朗读内容(提示词、allowed_metrics、质检要求)。
这些 DETECTION_TASK 数据并入 GET /api/levels/{id} 返回,还是独立
GET /api/levels/{id}/detection-task?前端 P05/P08 共用。

### Answer

**A:并入 `GET /api/levels/{id}`,检测开放时带 `detection` 子对象。**

- 关卡详情一次返回内容 + detection 子对象(仅 availability=open 时存在):
  `prompt_text`(朗读文本,FR-902)、`sample_audio`(示范音频,含
  audio_id/url/duration)、`allowed_metrics`(本关开放维度)、
  `reliability_note`(易混关「仅供参考」提示文案);
- 示范音频带 audio_id → 前端直接调特征端点(/f0、/formants、
  /formants/image),P04 原理 / P05 构形 / P06 比较全通(#11 联动);
- 质检阈值、四步模板、可靠性规则是内部规则,**不下发**(防前端自行预判);
- LearningContext 依赖与 404/409 语义不变,不新增端点。

## #6: 声学·JSON 字段命名与契约同步机制

Blocked by: #1
Type: Grilling

### Question

后端 FastAPI 默认 snake_case,前端 TS 惯用 camelCase。架构要求
「OpenAPI ↔ src/types/index.ts 唯一登记」。选哪种、如何强制(pydantic alias / CI 校验)?

### Answer

**A:camelCase(pydantic 全局 alias)+ openapi-typescript 自动生成。**

- 后端:Pydantic BaseModel 基类统一 `alias_generator=to_camel、
  populate_by_name=True`,全项目一次配置,零逐字段手写;
- 前端:`npx openapi-typescript` 从后端 openapi.json 生成
  `src/types/api.d.ts`,替代架构文档的「手抄一次」;
- CI:重新导出 openapi.json → 重新生成类型 → `git diff --exit-code`,
  漂移即红(ADR-4 双源教训的机械护栏);
- 架构文档 §1「契约唯一登记处」相应升级为自动生成口径。

## #7: 声学·音域标定与参考曲线的数据流

Blocked by: #4
Type: Grilling

### Question

FR-1006:首次用本关自然朗读标定音域,之后随档案滚动更新。访客无档案时调域从哪来?
标定是否要在响应中显式标记(本次曲线仅供参考)?参考曲线(ref_t)预计算存 CMS 还是运行时算?

### Answer

**显式标定流程:读设定文本 → 专门端点算音域。**

- 新增音域标定流程(替代「首次本关自然朗读隐式标定」):
  - `GET /api/pitch-calibration/text`:返回管理员设定的标定朗读文本;
  - 用户录这段文本 → `POST /api/audio/uploads` 拿 audioId(复用两步模型);
  - `POST /api/pitch-calibration {audioId}`:计算音域(F0 调域)并保存到
    当前会话(访客)或用户档案(登录),返回音域值与有效性说明。
- 曲线对比前检查音域:无音域 → 引导先标定;有音域 → T 值换算,
  响应 `result.curve.calibration` 标 `first`(刚标定)/`rolling`(滚动更新);
- 标定文本由管理员设定(CMS/配置),内容要求能覆盖用户自然音域
  (高低起伏足够);
- SRS FR-1006 与架构 §4 已同步改为显式标定口径;
- 后续可再加「重新标定」入口(同一端点重调即覆盖)。

## #8: 账号·自研 vs 开源账号包 ✔ 已定案 2026-10-15

Blocked by: #4
Type: Research

### Question

FR-107 只要轻量用户名密码+会话。候选:自研(约 200 行)、fastapi-users、
authlib 等。评估引入成本(依赖、迁移、定制同意/撤回语义) vs 自研成本。

### Answer

**引入 fastapi-users;匿名 sid 保留,升级以补丁实现。** 研究资产:
docs/research/08-账号包评估.md。

- 选型:fastapi-users 12.x(CookieTransport + DatabaseStrategy,对齐 ADR-5
  服务端会话);authlib 排除(FastAPI 集成仅 OAuth,无本地账密);
  托管认证排除(违反 ADR-1)。
- 放宽一条:fastapi-users 挂载路由(/api/auth/*)不套统一 envelope,
  按其原生 401/400 语义,OpenAPI 如实登记——#3 的 envelope 豁免域。
- **sid 不放弃**:访客上传/录音/学习事件仍挂 sid,GET 结果仍按
  「sid 匹配或归属」校验(#4 原语义)。
- Cookie 升级补丁:登录/注册路由外包中间件——读 sid → 认领 sid 名下
  录音/学习事件到账号 → 清除 sid Cookie;fastapi-users 本体不改。
- 定制任务(细则归 #10):username 登录(默认 email,需定制 UserManager)、
  管理员 = 其 is_superuser + 种子脚本。
- 范围补充(G1–G6):不做密码找回(不收邮箱,忘密码=重新注册)、
  补 FR-108 账号注销、1.0 不做注册防刷、用户名 3–32 唯一/密码≥8、
  会话 30 天滑动。

## #9: CMS·自研 vs 开源内容管理 ✔ 已定案 2026-10-15

Blocked by: —
Type: Research

### Question

D-09:单一管理员、录入+发布+版本管理。候选:自研 FastAPI CRUD(现状 cms_routes)、
Directus/Payload/Strapi 等开源 headless CMS。关键约束:三态状态机+检测开关+
整关版本快照+审计是定制域逻辑,开源 CMS 的通用能力未必覆盖。

### Answer

**自研域逻辑 + 管理界面现成轮子(sqladmin/starlette-admin)。**
研究资产:docs/research/09-CMS包评估.md。

- 域逻辑(状态机/发布前置/关卡依赖/检测开关校验/版本快照/审计)留在
  Python domain 层——FR-1204 的 allowed_metrics 校验可直接调评分域;
- 管理界面用 sqladmin 或 starlette-admin(实现期二选一,倾向
  starlette-admin:行动作/字段规则更全),挂在 /admin,框架自带单管理员
  登录,不与 fastapi-users 用户体系混流;
- #8 已把 SQLAlchemy 带进栈,管理界面轮子近乎零边际成本;
- Directus(共享 Postgres 库,结构最干净的开源形态)/Strapi/Payload
  均排除:省下的是 CRUD 壳,新增跨语言 TS hooks + 第二运行时,净负;
- 大众端 /api/levels 仍由我们后端出(LearningContext 每请求重校验),
  开源 CMS 当不了内容真源(ADR-4 双源教训)。

## #10: 账号/CMS 开源包与模块化单体的整合方式 ✔ 已定案 2026-10-15

Blocked by: #9(#8 已定案:fastapi-users 同进程挂载,细则见 #8 答案)
Type: Grilling

### Question

若引入开源包,以什么形态整合(同进程库 / 独立服务+反向代理 / 仅借鉴)?
SQLite 单库与 uploads/ 文件存储是否保留?
账号侧已定向:#8 定案 fastapi-users 同进程挂载 /api/auth/*,sid 消费
中间件、username 定制、is_superuser 管理员在本票一并细化。

### Answer

**同进程库整合;数据库维持 SQLite。**

- 形态:全部同进程——fastapi-users 挂 /api/auth/*(envelope 豁免,#8),
  管理界面(starlette-admin 优先,sqladmin 备选)挂 /admin;无独立服务、
  无反向代理、无跨语言 hooks,ADR-1 模块化单体不变。
- 数据库:SQLite 维持(负载远低于瓶颈;SQLAlchemy 接入层使将来换
  Postgres = 一行 URL + 一个 compose 服务),ADR-1 不改写。
- uploads/ 文件存储保留(ADR-6):媒体/录音落盘,库里只存元数据。
- 管理界面鉴权:框架自带登录(env 配置单管理员,D-09),不与
  fastapi-users 用户体系混流。
- **G3 修订**:管理员账号 = 管理界面自带登录,USER 表不再需要
  is_superuser 字段,也无种子脚本。
- cms_routes.py 的 /api/admin/units/* REST 占位退役:治理动作(发布/
  下架/检测开关/版本回退/反馈处理/媒体)由管理界面自定义动作调
  domain/level_state 纯函数。
- fastapi-users 实现期定制清单:username 登录(UserManager 定制)、
  CookieTransport + DatabaseStrategy、sid 消费中间件(登录/注册外包)。

## #11: 声学·前端声学可视化(F0/共振峰)的数据流

Blocked by: #2
Type: Grilling

### Question

前端要展示 F0 曲线、共振峰(F1/F2)等信息,数据从哪来?候选通道:
① 前端上传音频调 `POST /api/audio/features`(现有公开端点,按需计算);
② 检测结果对象内嵌特征(P09 用户录音的共振峰对比);
③ 示范/原理音频的特征在 CMS 发布时预计算,关卡详情/媒体端点带出
(P04 原理 / P05 构形 / P06 比较)。
各页面分别用哪种?用户录音的特征是否进结果快照(影响存储与版本口径)?

### Answer

**编号中心(audio_id)模型:上传持久化,特征按编号分开取。**

- `POST /api/audio/...` 上传音频 → 后端持久保存(uploads/)并分配
  `audio_id` → 响应回传编号(及基础元数据);
- 前端之后按 `audio_id` 分别调用独立端点:
  - F0 数据(时间序列);
  - 共振峰数值数据(F1/F2 时间序列);
  - 共振峰图片(服务端渲染的图,如语谱图+共振峰轨迹 PNG);
  - (配套)原音频回放端点。
- 特征计算与缓存按 audio_id 落库,同一编号重复取数不重算;
- 与检测主链路的关系、计算时机(上传时算 vs 首取时算)、图片渲染
  技术选型:见 #12(衔接检测流)、#13(渲染与时机)。

## #12: 声学·audio_id 上传面与检测主链路(POST /api/recordings)的衔接

Blocked by: #11
Type: Grilling

### Question

编号中心模型定了之后,检测提交怎么走?
① 检测仍一步 multipart(POST /api/recordings 直接带音频),audio_id 面只
服务原理/示范/任意音频可视化;② 检测改为两步:先上传拿 audio_id,
再 POST /api/recordings {audio_id, level_id, submission_id}。
两步解耦了存储与评估,但多一次往返、孤儿上传与幂等语义更复杂。

### Answer

**B:检测也改两步——先上传拿 audio_id,再提交评估。**

- 第一步 `POST /api/audio/uploads`(multipart 音频)→ 持久保存,
  返回 `{audio_id, duration, format, …}`;
- 第二步 `POST /api/recordings`(JSON:`{audio_id, level_id, submission_id}`)
  → 同步走完整评估流水线,返回质量+结果;
- 架构时序图 §4 相应改为两步;ADR-9 的「同步+幂等」语义保留在第二步。
- 衍生约束(实现时必须处理,细则见 #13/#14):
  - 未提交评估的孤儿音频要有清理策略(#13);
  - 幂等重放:同 submission_id 重放第二步时,以 submission_id 为准返回
    原结果(默认忽略 audio_id 差异,如需 409 再议);
  - audio_id 用不可猜测的随机 ID(UUID),防止匿名遍历他人音频;
  - 录音的可见性/归属控制仍在 recording 层(第二步校验),
    上传面本身公开但不登记归属。

## #13: 声学·特征计算时机与共振峰图片渲染选型

Blocked by: #11
Type: Grilling

### Question

- 计算时机:上传时同步算全部特征(上传慢但取数快)vs 首次取某类特征时
  算并缓存(上传快,按需)?图片渲染(matplotlib Agg / 手写 SVG)选哪个?
- 匿名上传持久保存的保留策略(NFR-09/隐私):TTL 清理?上限?

### Answer

**A:首取时算 + 按 audio_id 落库缓存。**

- 上传只落文件+元数据,毫秒级返回 audio_id(上传在录音体验路径上,不背计算);
- 每类特征(F0 / 共振峰数值 / 共振峰图片)独立缓存:首次 GET 时计算并
  落库,同编号后续请求直接读缓存,用不到的不算;
- 图片渲染选型:matplotlib(Agg 后端,语谱图 + 共振峰轨迹叠加 PNG),
  按惯例定,不再开题;
- 匿名上传保留策略(默认,可推翻):未被检测提交引用的上传 7 天 TTL
  清理;被 POST /api/recordings 引用后转正,生命周期跟随录音
  (session/archived)。

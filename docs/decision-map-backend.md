# 决策图 · 后端 API 架构规划

> 范围：依据 SRS 规划后端模块与 API，不代表接口已经实现。
> 采用同进程模块化单体、SQLite、文件存储、外部评分 Provider 与同步检测。本文定义 API 契约，前端与目标架构据此设计。

## 范围与验证要求

同意后自动全部转存；临时数据保留 72 小时；访客进度仅前端本地；撤回时删除进度与音域；HTTP 使用标准状态码。本地物理删除最迟 24 小时，预览令牌默认 15 分钟，备份最长 7 天。上线前须核实第三方评分服务的留存和删除能力。

管理库提供认证扩展，不等于无需配置的管理员登录；用户名认证及公开路由需适配，不能假定 fastapi-users 原生路径/JSON 恰好满足产品。依赖版本、密码哈希库、评分服务维度与延迟均须实现期验证，本文不凭需求断言已验证。

## 模块边界

| 模块 | 职责与数据所有权 |
| ---- | ---- |
| content | 关卡/文章身份、草稿、不可变公开版本、分类、媒体授权及发布引用、搜索和导航 |
| acoustics | 私有上传 audioId、解码、F0/共振峰、渲染和特征缓存，提供统一读取权限判定 |
| scoring | Provider 适配、质量两维、规则四步、评分结论缓存、音域标定/T 值换算 |
| detection | submissionId 幂等、处理状态、录音与不可变结果快照，引用版本和 audioId |
| identity | 账号认证、sid 与账号安全绑定、同意决定历史、注销与会话失效 |
| archive / learning | 自动转存、本人档案比较、同意后学习事件、进度只读派生 |
| feedback | 反馈/希望增加、处理状态、去除已删除私人资源引用 |
| admin | 单管理员管理界面，调用上述用例；不直接修改公开版本，不读取私人录音 |
| platform | requestId、审计、标准 HTTP/envelope、限流/并发、权限与 CSRF、定时清理 |

各模块管理自身数据，通过用例接口协作；同一个 SQLite 库中跨域必要原子操作可统一编排。不新增微服务、消息队列或独立监听端口。清理任务与同步评分处于同一部署形态，但重计算须受并发限制，不能阻塞全部普通请求。

## HTTP 与契约

JSON camelCase，统一响应：`{code, message, data, requestId, nextStep?}`；每次 HTTP 请求生成/校验 requestId 并写 `X-Request-Id`，幂等重放复用业务结果但使用本次请求 ID，可另引用原操作 ID。后端 OpenAPI 为真源，openapi-typescript 生成前端类型，CI 检查契约漂移。

| HTTP | code 示例 / 语义 |
| ---- | ---- |
| 200 | OK；QUALITY_FAIL（有效业务结果，不填分数与检测现象） |
| 202 | PROCESSING：同 submissionId 首次尚未完成，带 recordingId、查询入口和 Retry-After |
| 400 / 422 | DECODE_FAILED / VALIDATION_ERROR，输入不可处理或结构非法 |
| 401 | AUTH_REQUIRED / INVALID_CREDENTIALS |
| 403 | CONSENT_REQUIRED / FORBIDDEN |
| 404 | NOT_FOUND / LEVEL_NOT_PUBLISHED；资源不存在、非本人、已删或过期统一不可见 |
| 409 | CONTENT_VERSION_CHANGED / IDEMPOTENCY_CONFLICT / INVALID_STATE |
| 413 | FILE_TOO_LARGE |
| 429 | RATE_LIMITED，带 Retry-After |
| 500 | INTERNAL_ERROR |
| 502 / 503 / 504 | PROVIDER_ERROR / PROVIDER_DOWN 或 DETECTION_OFF / TIMEOUT |

所有 JSON 公共路径含认证适配采用上述契约，库默认路由不自动成为公开契约。文件成功直接返回媒体类型，支持 206、304、416，不套 JSON envelope；失败保留真实 HTTP 状态。私人资源 private/no-store、预览 no-store；公开媒体每次再验证当前发布引用，避免缓存让下架继续可读。

## 1.0 API 清单

### 平台与内容

| 方法与路径 | 权限 / 行为 |
| ---- | ---- |
| GET /api/health | 公开健康状态，不泄露内部配置 |
| GET /api/me/context | 访客可读；登录/同意状态、音域状态、nextLevelId，访客推荐不读取服务端进度 |
| GET /api/levels | 已发布摘要 + 地图公开骨架；availability 为 open / temporarily_unavailable（应急熔断）/ closed；未发布仅 id/order/layer/targetSound/availability=closed；P01/P06/P08 自行过滤；tag 为 2.0 扩展，不在 1.0 启用分流 |
| GET /api/levels/{id} | 仅已发布详情，含 contentVersion、nav、detection（promptText/sampleAudio/allowedMetrics/reliabilityNote）；规则阈值与四步内部模板不下发 |
| GET /api/search?q= | 仅已发布匹配与相近关，不默认持久化搜索日志 |
| GET /api/article-categories | 公开分类；基于已发布文章的分类快照 |
| GET /api/articles?category= | 已发布文章摘要目录 |
| GET /api/articles/{slug} | 单篇公开详情、contentVersion、Markdown、示范、练习、资料及有效关卡入口 |
| GET /api/media/{mediaId} | 公共内容媒体（图/动画/视频/字幕/模型）；已发布引用与授权校验；非公开授权材料拒绝；音视频 Range 与 ETag |
| POST /api/preview/tokens | 仅管理员；{kind, id}，签发绑定管理员会话/对象/草稿修订的 15 分钟令牌，后台按钮调用 |
| GET /api/preview/levels/{id} | 管理员会话 + 对象预览令牌，公开详情同结构，但来源草稿 |
| GET /api/preview/articles/{slug} | 同上，文章草稿 |
| GET /api/preview/media/{mediaId} | 同上，仅令牌绑定草稿引用的媒体，音视频 Range；不授权私人录音 |

### 音频、标定与检测

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| POST /api/audio/uploads | multipart 音频 → {audioId, duration, format, expiresAt}；上传登记 sid/账号归属，用途不可由客户端升级成 public，首次上传起 72 小时 |
| GET /api/audio/{audioId} | 元数据；私有校验归属/失效，示范校验发布引用 |
| GET /api/audio/{audioId}/file | 原音频；同一权限，支持 Range/ETag |
| GET /api/audio/{audioId}/f0 | F0 时间序列；同一权限、首次算及独立缓存 |
| GET /api/audio/{audioId}/formants | F1/F2 时间序列；同一权限 |
| GET /api/audio/{audioId}/formants/image | 直接 PNG；同一权限，matplotlib Agg 渲染 |
| GET /api/pitch-calibration | {text, textVersion, status, range, expiresAt?}，当前会话或本人音域 |
| POST /api/pitch-calibration | {audioId, textVersion}；归属/文本版本校验，已登录且同意保存，否则临时标定；不阻塞未标定的普通评分 |
| POST /api/recordings | JSON {audioId, levelId, contentVersion, submissionId}；同步返回录音身份、质量与结果；同意有效自动存档，否则临时 |
| GET /api/recordings/{id} | 本会话/本人结果；处理中 202、完成原结论、失败对应真实状态；已删/过期 404 |
| DELETE /api/recordings/{id} | 本会话/本人单删，硬删关联音频与缓存；重复删除无新增副作用；共享音频须无剩余有效引用再物理删 |

### 档案、学习与反馈

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| GET /api/me/recordings?levelId= | 登录且同意，仅本人 archived；分页摘要，不含文件或 Provider 原始数据 |
| DELETE /api/me/recordings | 登录，仅清空本人已存档录音；区别于撤回的全部进度/音域清理 |
| GET /api/me/recordings/compare?a=&b= | 1.0 必做：本人同关 archived 两次的主要差异提示；跨版本标明可比范围 |
| POST /api/learning-events | 登录且同意；{eventId, levelId, contentVersion, kind: listen_quiz / practice_done, detail}，服务端按公开版本校验题目/选项与完成事件，派生对错，不信任客户端 correct |
| GET /api/me/progress | 登录且同意；只读派生与 nextLevelId，仅此一条定义 |
| POST /api/feedback | 公开提交，sid/账号及限流；{sourcePage, type, content?, articleSlug?, levelId?, recordingId?, subtype?, rating?}，结果引用校验本人并记录版本 |
| POST /api/wishes | 公开提交、限流；希望增加的音/字与 searchQuery?，后台处理 |

### 账号与同意

| 方法与路径 | 请求 / 语义 |
| ---- | ---- |
| POST /api/auth/register | {username, password}；用户名 3–32，密码≥8；不收邮箱/手机、不提供找回；注册不自动认领 |
| POST /api/auth/login | {username, password}；认证成功安全绑定当前 sid，已有有效同意触发自动转存；未同意保持临时 |
| POST /api/auth/logout | 失效认证会话，解绑并轮换 sid，阻断账号间继承 |
| GET /api/me/consent | 登录；状态、consentTextVersion 与只追加的决定时间线 |
| POST /api/me/consent | {decision: granted / rejected, consentTextVersion}；授予时转存本会话全部未过期记录，返回 transferredCount；拒绝不存档 |
| DELETE /api/me/consent | 撤回、立即拒绝后续存档并按 D-17 删除；重复调用幂等 |
| DELETE /api/me/account | {password}，验证当前密码；完整删除、匿名化审计及所有会话失效 |

符合条件的录音自动全部转存，无逐条存档操作。音频、F0、共振峰及图片统一通过 audioId 读取。修改密码不属于 1.0 范围。

`/api/audio/quality` 与 `/api/asr/*` 只作内部或开发诊断，生产匿名路由不挂载；`/api/audio/score` 属 2.0 模型对比，1.0 不公开。后台 `/admin` 是管理界面入口，不是额外网络端口；治理动作不开放通用公开 REST CRUD。

## 架构决策

| # | 决策 | 现行结论 |
| ---- | ---- | ---- |
| #1 | 录音资源与学习事件 | /recordings 扁平资源；两步提交；学习事件独立、1.0 不含 mini_quiz；档案集合归 /me |
| #2 | 工具接口 | audioId 读取提供可视化；质量与 ASR 诊断内用，本地评分 2.0；模型加载仅供内部或开发使用 |
| #3 | HTTP 语义 | 标准状态码 + JSON envelope + requestId；QUALITY_FAIL 200；文件原生响应 |
| #4 | sid 会话 | 首次按需签发不可猜测、签名 HttpOnly Cookie；上传立即归属；登录绑定而非无条件归档；退出轮换 |
| #5 | 任务读取 | 关卡详情内 detection 与 contentVersion/nav；提交校验展示版本；学习入口保留，应急检测故障明确提示 |
| #6 | 字段与类型 | JSON camelCase，OpenAPI → 自动生成 TS，CI 检查漂移；数据库内部命名不属于 JSON 契约 |
| #7 | 音域 | 显式文本标定，GET 查询状态；未标定只缺曲线不取消评分；临时会话标定/同意后个人音域分开 |
| #8 | 账号库 | fastapi-users 同进程承担认证基础；产品用户名/JSON/公开路径与 sid/同意由适配层实现；版本及兼容性实现期验证 |
| #9 | CMS 库 | 自研内容治理 + starlette-admin 优先/sqladmin 备选；草稿 CRUD 与发布用例隔离，配置管理员认证扩展 |
| #10 | 整合 | SQLite + SQLAlchemy + 文件存储保留；管理员认证不依赖用户 is_superuser（库内部字段按实际模型处理）；迁移数据库需评估数据和并发，非改一行即完成 |
| #11 | audioId 数据流 | 上传落元数据/文件与归属；F0、共振峰、图片按编号取；所有读取共享归属/发布/删除判定 |
| #12 | 两步提交与幂等 | 上传 multipart，评分 JSON；同一所有者+submissionId 绑定同负载，差异 409；处理中 202；不同键相同音频由版本化评分缓存保证重复性 |
| #13 | 缓存、渲染与 TTL | 首取独立缓存，算法版本入键；Agg 图片；未引用上传及临时录音统一 72 小时，删除清缓存 |

## 自动转存、留存与并发不变量

1. 归属与 session/archived 独立；登录只绑定，首次同意前不转存；绑定后原访客资源归账号，sid 单独不再足以读取，必须有对应账号认证。转存仅当前可信绑定会话内该账号临时记录，且未过期/未删除，不扫描所有访客。已有同意账号登录自动转存，处理中的记录完成后仍重校验同意。
2. 学习进度：访客/未同意只存在前端本地；不接收 sid 学习事件，不导入历史本地进度；登录且同意后的新事件按 eventId 去重与内容版本校验。
3. 留存：私有上传/临时结果/标定及缓存首次上传起 72 小时，不续期；存档引用延长至用户删除。音域若转为用户长期保存，须有效同意且可追溯来源；原始标定音频完成用途后不因音域持久化无限保留。
4. 评分重复性：缓存键含所有者、音频内容哈希、公开内容版本、规则版本、Provider/模型版本；曲线再含音域快照及特征算法版本。Provider 不保证天然确定性，不缓存瞬时服务失败为最终评分，不跨用户共享私人录音缓存。
5. 删除：立即失效被删录音；其独占 audioId 同时失效，共用 audioId 仅在仍有本人有效引用时可读，再按引用安全硬删文件/特征/评分缓存；本地最迟 24 小时，失败重试告警。撤回/注销删除全部账号临时与长期录音、事件/进度、音域及绑定私人缓存；审计仅留匿名骨架；在途操作不可复活数据。
6. 内容：公开版本不可变、草稿分离；回退新建发布记录；历史私人结果引用旧版本仍可查看，不等于旧教学媒体继续公开。内容发布或检测熔断不能改变已有幂等结果，但重放始终先校验资源仍有效且属于请求者。
7. 基础保护：sid/IP 或账号/IP 限流、全局计算并发上限；Cookie 安全设置与 Origin/CSRF 校验；预览令牌绑定管理员权限，禁止私人录音访问。

## 与需求及验收的对应

自动转存 D-14/FR-102/V1-AC18；72 小时 D-15/NFR-09/V1-AC19；本地进度 D-16/V1-AC20；撤回删除 D-17/V1-AC26；标准 HTTP D-18/V1-AC25；版本/幂等 V1-AC22–23；草稿预览 V1-AC24；录音权限 V1-AC21；比较 V1-AC27。实现前仍需核实 Provider 的实际维度、中文用户名认证适配、管理界面扩展能力、第三方留存与清理条款，不能把需求层推断当作已验证实现。

本地删除边界：当前设备在撤回/注销时清除相关进度与音域；其他离线设备在下次联网重新校验账号与同意后清除，服务端不能远程立即擦除离线浏览器存储。自动转存不包括未提交检测的孤儿上传；处理中录音完成时重校验同意，质量不合格记录只保留质量结论与重录指引。

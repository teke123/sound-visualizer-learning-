# 交接文档：OpenAPI 契约流水线（后端响应模型 → 前端生成类型 → 漂移检查）

> 写给下一个会话。任务目标：按项目文档规定（docs/decision-map-backend.md「HTTP 与契约」、
> docs/architecture/04 §2）打通「后端 OpenAPI 为真源 → openapi-typescript 生成前端类型 →
> CI 检查契约漂移」这条流水线。
> 前置背景：前端（Vue 3 + Quasar，P01–P11 全部页面）已完整实现并与真实后端联调通过；
> 本任务进行到一半，后端模型已写完并验证，前端切换未开始。

---

## 1. 环境与关键事实（先读这节）

- **Python 必须用 `py -3.13`**。系统默认 `python` 是 3.9 且没有依赖；后端依赖装在 3.13 上
  （fastapi/uvicorn/sqlalchemy/numpy 等已就绪）。后端启动方式：`cd backend && py -3.13 main.py`（8000 端口）。
- **8000 端口上跑着旧代码的后端进程**（未含本次新增的响应模型）。下一步需要先杀掉重启，
  重启后 `/openapi.json` 才会带 schema。杀法：`netstat -ano | grep :8000` 找 PID → `taskkill //F //PID <pid>`。
- 后端目前用 **mock 评分 Provider**（讯飞未接），提交录音会同步返回结果，方便自测。
- 前端开发：`npm run dev`（代理 /api → 127.0.0.1:8000）；后端不可用时 `npm run dev:mock` 走 MSW。
- e2e 脚本 `backend/e2e_test.py` 是 **httpx 直连运行中的服务** 的自测脚本（`py -3.13 e2e_test.py`，
  需后端已启动；还有 `e2e_async_test.py`）。
- 工作树里有大量**未提交改动**（整个前端实现 + 本次后端 schema 改动）。建议接手后先看
  `git status` / `git diff` 了解全貌，考虑先分块提交一版再继续。

## 2. 已完成的工作（本次任务，后端侧）

1. **新建 `backend/app/api/schemas.py`**（约 400 行）：泛型 `Envelope[T]`（对应
   `{code, message, data, requestId, nextStep?}` 统一响应体）+ 全部公开端点的 data 负载模型，
   命名与前端手写类型一致（`MeContext`、`LevelsResponse`、`LevelDetail`、`AssessmentResult`、
   `ArchiveCompareResponse` 等，共 157 个 schema 条目）。可空性按**真实行为**声明
   （例如 `LoginContextPartial` 只含 authenticated/accountId/username/dataEpoch —— login 响应
   本来就是部分字段；`LevelsResponse.skeletons` 有默认值 `[]` —— 后端空列表时会省略该键）。
2. **六个公开路由文件全部标注 `response_model=Envelope[X]`**：
   `routes_platform.py`、`routes_auth.py`、`routes_audio.py`、`routes_me.py`、
   `routes_feedback.py`、`routes_preview.py`（含相应 import）。
   `/api/recordings` 的 POST/GET 额外用 `responses={202: {"model": Envelope[RecordingOnly]}}`
   文档化了 202 PROCESSING 形状。
3. **零运行时行为变化**：`envelope()` 返回的是 `JSONResponse`，FastAPI 对直返 Response 的
   路由**不做** response_model 校验/过滤——response_model 只进 OpenAPI 文档。这是刻意选择
   （避免字段过滤静默丢数据、避免改变已联调通过的行为）。
4. 已修 `routes_audio.py` 缺 `from typing import Union` 的问题（标定 POST 的响应模型是
   `Union[CalibrationOkResult, CalibrationFailResult]`）。
5. 已离线验证：`py -3.13 -c "import main; main.app.openapi()"` 生成 157 个 schema，
   `/api/levels` 200 响应指向 `Envelope_LevelsResponse_`，recordings 202 已文档化。
   **但运行中的旧进程还没重启，线上 /openapi.json 尚未更新。**

admin 路由（`routes_admin.py`）**没有**做响应模型——前端不消费它，属低优先级后续项。

## 3. 盘点契约时发现、**尚未修复**的两个前端漂移

这是本任务顺手抓出来的真实 bug（生成类型切换后会自然以编译错误形式暴露）：

1. **搜索相近关从不显示**：后端搜索响应是 `{results, near, query}`（`backend/app/content/usecases.py`
   `search_levels`），前端 `src/pages/SearchPage.vue` 读的是 `res.data.suggestions ?? []` →
   永远空。需改读 `near`（`src/api/generated/types.ts` 里手写的 `SearchResponse.suggestions`
   也是错的，切生成类型时一并解决）。
2. **同意时间线日期显示 '—'**：后端 timeline 条目字段是 `createdAt`
   （见 `routes_me.py` /me/consent），前端 `src/components/ConsentTimeline.vue` 与手写类型用的
   是 `decidedAt`。需把组件改读 `createdAt`。

另外 MSW mock（`src/mocks/handlers.ts`、`fixtures.ts`）的 search 与 consent 响应也要同步改成
`near` / `createdAt`，保持 dev:mock 与真实契约同形。

## 4. 接下来的工作（按顺序）

### 第一步：重启后端并确认线上 OpenAPI
```
netstat -ano | grep :8000   # 找 PID
taskkill //F //PID <pid>
cd backend && py -3.13 main.py   # 建议后台运行
curl -s http://127.0.0.1:8000/openapi.json | py -3.13 -c "import json,sys; d=json.load(sys.stdin); print(len(d['components']['schemas']))"
# 期望 >150
```

### 第二步：后端回归（证明 response_model 零行为变化）
```
cd backend && py -3.13 e2e_test.py        # 应全 PASS
py -3.13 e2e_async_test.py                # 如适用
```

### 第三步：schema 真实性测试（新文件，建议 backend/test_openapi_shapes.py）
用 TestClient（`from fastapi.testclient import TestClient; client = TestClient(main.app)`，
注意 TestClient 走 ASGI、不占 8000；写请求记得带 `Origin` 头过 CSRF——参考 e2e_test.py 的
`HEADERS = {"Origin": "http://localhost:5173"}`）。逐端点发真实请求，把响应的 `data` 用
`Envelope[X].model_validate({"code":..., "data":...})` 校验。覆盖面建议至少：
health / me/context / levels / levels/L01 / search / articles 系列 / 上传+标定+提交录音全链路 /
recordings GET / session/recordings / 注册登录 / consent 三件套 / me/recordings(+compare) /
learning-events / me/progress / feedback / wishes。
这一步的意义：response_model 目前只是文档，此测试把「文档与实际响应一致」变成可回归的断言。
注意标定/录音需要能过质检的合成语音——`backend/app/seed_support.py` 有 `synthesize_text`/`write_wav`
（e2e_test.py 已在用，直接抄它的用法）。

### 第四步：前端切到生成类型
```
npm i -D openapi-typescript
curl -s http://127.0.0.1:8000/openapi.json -o src/api/generated/openapi.json
npx openapi-typescript src/api/generated/openapi.json -o src/api/generated/schema.d.ts
```
然后把 `src/api/generated/types.ts` 改成**转发层**（保持全部消费方 import 路径不变，这是唯一接缝）：
```ts
import type { components } from './schema'
export type LevelSummary = components['schemas']['LevelSummary']
export type LevelDetail = components['schemas']['LevelDetail']
export type MeContext = components['schemas']['MeContext']
// …其余同名映射；Envelope/内部专用类型如需保留手写也可以
```
预期会在两处报编译错（正是第 3 节的两个漂移）：SearchResponse 的 `suggestions` → 改 `near`；
ConsentTimeline 的 `decidedAt` → 改 `createdAt`（组件 `formatDateTime(decision.decidedAt)` 处）。
还要留意可空性差异：Pydantic `Optional + 默认值` 会生成 `field?: T | null`，个别消费处
可能要补 `?? undefined` / `?? []` 兜底（此前联调已大多处理过）。
`Envelope[X]` 在生成文件里叫 `Envelope_X_`（FastAPI 泛型命名），前端 client.ts 自己解析
envelope、不依赖它，可不映射。

### 第五步：脚本与漂移检查（package.json）
```
"api:dump":  "curl -s http://127.0.0.1:8000/openapi.json -o src/api/generated/openapi.json",
"api:types": "openapi-typescript src/api/generated/openapi.json -o src/api/generated/schema.d.ts",
"api:check": "openapi-typescript src/api/generated/openapi.json -o src/api/generated/schema.check.d.ts && node -e \"const fs=require('fs');const a=fs.readFileSync('src/api/generated/schema.d.ts','utf8');const b=fs.readFileSync('src/api/generated/schema.check.d.ts','utf8');if(a!==b){console.error('API 契约漂移：请重新生成（npm run api:dump && npm run api:types）');process.exit(1)}fs.unlinkSync('src/api/generated/schema.check.d.ts')\""
```
`openapi.json` 与 `schema.d.ts` **都要提交进仓库**（它们是漂移比对的锚点）。CI / 他人工作流：
后端改契约后跑 `api:dump && api:types` 提交，否则 `api:check` 失败。
（Windows 下 curl 在 Git Bash 可用；若要跨平台可换成 node 脚本下载。）

### 第六步：全量回归
- 前端：`npm run build`（含 vue-tsc）、`npx vitest run`（现有 27 个单测；
  `src/stores/__tests__/completion.spec.ts` 等不依赖 DTO，应不受影响）。
- MSW 同步：改 `src/mocks/handlers.ts` 的 search 响应（`suggestions` → `near` + `query`）
  与 consent GET（timeline 条目 `decidedAt` → `createdAt`），`npm run dev:mock` 下抽查
  搜索无结果页与账号页时间线。
- 浏览器抽查（`npm run dev` + 真后端）：首页 / 关卡页 / 搜索「妈」/ P10 时间线与相近关两处修复点。

## 5. 验收标准

1. `/openapi.json` 含全部公开端点的具体响应 schema（>150 个 components.schemas）。
2. `py -3.13 e2e_test.py` 全 PASS（证明 response_model 标注零行为变化）。
3. 新增的 schema 真实性测试全 PASS。
4. 前端 `types.ts` 为生成类型转发层；`npm run build` 与 `vitest` 全绿。
5. 两个漂移修复可见效果：搜索无结果时出现「相近关」卡片；账号页同意时间线显示真实日期。
6. `npm run api:check` 在无漂移时通过；手改 `schema.d.ts` 一个字符后应失败。

## 6. 注意事项与已知取舍

- response_model 目前**仅文档作用**（路由直返 JSONResponse，FastAPI 跳过校验）。将来若想开
  运行时校验，需让 envelope 返回 Pydantic 模型实例——注意 FastAPI 会**过滤模型外字段**，
  模型漏写会静默丢数据，切换前先用第三步的测试兜底。
- `Envelope[T]` 泛型在 OpenAPI 里展开为 `Envelope_X_` 形式的独立 schema，正常现象。
- `schemas.py` 里 `pass_` 字段用 `Field(None, alias="pass")` 规避 Python 保留字，schema 里
  显示为 `pass`（Quality 的信号检查项）。生成 TS 会得到 `pass?: boolean | null`。
- 标定 POST 的响应是 Union（成功 / CALIBRATION_FAIL 两种形状），生成类型为 anyOf；前端
  `features/calibration.ts` 已按 `res.code === 'CALIBRATION_FAIL'` 分流，兼容。
- 后端是另一名协作者（后端 Agent）的工作成果，本次只在 `app/api/` 加了 schemas.py 与
  response_model 标注 + import；如后端 Agent 继续工作，注意与其同步 `schemas.py` 的归属
  （谁改契约谁更新模型 + 重新生成前端类型）。

---

## 7. 完成记录（2026-10-15 第二次会话，任务已全部完成）

第 1–6 步全部执行完毕，验收标准逐条核对通过。除计划内工作外，还发现并处理了以下问题。

### 7.1 后端侧新修复（schemas.py 与一处真实 bug）

- **health 路由 500**：health 是唯一不走 `envelope()`、直返裸 dict 的路由，原来的
  `response_model=Envelope[HealthData]` 会让 FastAPI 真的执行校验并 500。已改为
  `response_model=HealthData`（裸形状，注释说明）。
- **schema 与实现不符（schema 真实性测试抓出）**：
  - `LevelsResponse.skeletons` → 实际键名是 **`skeleton`**（单数）；
  - `FormantsResponse.vowelSegments`：元素是 `[start, end]` 浮点对，不是 dict；
  - `Phenomenon.position`：裸 dict → 精确建模为 `PhenomenonPosition{syllableIndex, part}`；
  - `ArticleDetail.demo`：裸 dict → `ArticleDemo{mediaId, text?}`。
- **`write_score_cache` 裸 INSERT 撞 UNIQUE 约束（真实 bug，已修）**：登录绑定会把 sid 的
  score_cache 迁移到用户名下，用户再提交**内容相同**的音频（pcm_sha256 一致）时管线收尾
  INSERT 同键缓存即崩溃，录音滞留 processing 直到调度器 TIMEOUT。e2e 没踩中是因为它第二次
  提交用了不同（女声）音频。已按 `migrate_score_cache_owner` 的查重模式改为幂等更新。
  **请后端 Agent 知悉此改动（app/scoring/usecases.py）。**

### 7.2 新增测试与脚本

- **`backend/test_openapi_shapes.py`**：58 项断言全绿。TestClient 直走 ASGI；校验用
  `extra="forbid"` 的严格子类，实现多吐字段即视为漂移；按契约处理 202（轮询到 200）。
  与 e2e 不同，它动态读取 L30 contentVersion，**不要求重置数据库**。
- **package.json** 新增 `api:dump` / `api:types` / `api:check`（漂移时退出码 1，已双向验证）。
  `openapi.json` 与 `schema.d.ts` 已入库。

### 7.3 前端侧改动

- `src/api/generated/types.ts` 已改为生成类型转发层（唯一手写保留：`Envelope`、请求侧
  `LearningEvent` / `FeedbackPayload`，以及从生成组件派生的字面量联合）。
- 两处漂移修复落地并经浏览器实测：搜索无命中显示相近关（`near`）；同意时间线显示真实日期
  （`createdAt`）。MSW（handlers/state/fixtures）已同步 `near` / `createdAt` / `skeleton` /
  `query` / `rangeSnapshot`。
- 生成类型的可空性（`field?: T | null`）在约 20 个消费处补了 `?? []` / `?.` 兜底。
- **AccountPage 加载时机 bug（顺手修）**：原来只在 `onMounted` 拉同意状态，直接刷新页面时
  context 未就绪会早退、授权后也不重取，时间线永远空。已改为 watch
  `[authenticated, consentStatus]`（immediate）。
- `npm i -D openapi-typescript` 需 **`--legacy-peer-deps`**（其 peer 声明停在 TS 5.x，本项目
  TS 6）。注意：该标志会把仅 peer 依赖的 `@vue/devtools-api` 从 lockfile 剔除导致 build 失败，
  已显式加为 devDependency（`@vue/devtools-api@^8.1.5`），后续 `npm ci` 无需再加标志。

### 7.4 已知但未处理的既有问题（留给后端 Agent）

- **`e2e_test.py` 不幂等**：admin 段的发布/回滚会把 L30 留在 v3，而提交固定用
  `contentVersion: 1`，连续第二轮跑会 `CONTENT_VERSION_CHANGED` 失败。完整跑前先
  `py -3.13 seed.py --reset`（本会话即按此流程：reset → 77/77）。
- **`wait_sync_window` 小窗口竞态**：`SVS_SYNC_WINDOW=0` 时 `asyncio.wait_for` 超时会取消
  执行器 future，若线程尚未启动，管线被取消、录音滞留 processing 直到 TIMEOUT。
  `e2e_async_test.py` 202 模式的可用跑法：`SVS_SYNC_WINDOW=0.05` 启动后端 + 清空
  score_cache（`delete from score_cache`），3/3 通过。根治需改 `wait_sync_window`
  的取消语义，属后端 Agent 范畴。

### 7.5 最终验证结果

`py -3.13 e2e_test.py` 77/77；`py -3.13 test_openapi_shapes.py` 58/58；
`npm run build`（含 vue-tsc）与 `vitest` 27/27 全绿；`api:check` 无漂移通过、手改
schema.d.ts 后退出码 1；浏览器实测（dev+真后端）：搜索「123」出相近关卡片、注册→登录→
同意后时间线显示 `2026/10/15 10:57:55` 真实日期；dev:mock 下搜索相近关同样正常。
后端进程（8000）与 vite dev（5173）保持运行中。

# 研究资产 · #9 CMS 域：自研 vs 开源内容管理

> 开票与定案 2026-10-15。决策图：docs/decision-map.md #9。
> 前提变化：用户放宽数据库约束（可换 PostgreSQL），SQLite 不再是硬边界。

## 结论

**自研域逻辑 + 现成管理界面轮子（sqladmin / starlette-admin，实现期二选一，
倾向 starlette-admin：自定义行动作与字段规则更完整，发布/下架/检测开关等
治理动作可以不绕路地挂在列表行上）。**

## 候选评估

| 候选 | 形态 | 判定 | 依据 |
| ---- | ---- | ---- | ---- |
| sqladmin / starlette-admin | FastAPI 同进程管理界面 | ✅ 采用 | Python 生态；#8 引入 fastapi-users[sqlalchemy] 后 SQLAlchemy 已在栈内，近乎零边际成本；CRUD 壳白嫖，域逻辑留 Python |
| Directus | Node 服务，可 introspect 共享库 | ❌ | 换 Postgres 后结构上最干净的开源形态（单库无双源），但状态机/发布前置/检测开关校验须写 TS hooks；FR-1204 的 allowed_metrics 校验要跨进程调我们的评分域；两运行时共写一库 |
| Strapi v5 | 独立 Node 服务 | ❌ | 内容真源须搬入，我们后端变代理/同步层；单管理员使其角色/工作流卖点闲置；TS 全家桶 |
| Payload 3.0 | 装进 Next.js 的库 | ❌ | 绑 Next.js（我们前端是 Vue SPA）；同代理/同步问题 |

## 核心论据（与数据库选型无关）

CMS 域的真复杂度是定制治理逻辑，不是 CRUD：

- 三态发布状态机 + FR-1203 发布前置（内容完整性/授权/示范可播）；
- 关卡依赖（L30 待 L01+L09 均已发布）；
- FR-1204 检测开关校验——`allowed_metrics ⊆ ScoringProvider.stable_metrics()`，
  必须调用我们自己的评分域，开源 CMS 里只能跨进程或双源；
- 整关版本快照 + 回退（FR-1208/1408）+ 审计；
- 大众端 `/api/levels` 必须由我们后端出（LearningContext 每请求重校验 NFR-18
  + detection 子对象组装 + openapi-typescript 契约 #6）——开源 CMS 当不了真源。

开源包省下的是最薄的部分（表单/列表），新增的是跨语言 hooks + 第二运行时 +
部署面；「省代码」为负。管理界面轮子（同进程）是唯一净收益的引入。

## 管理界面整合要点（细则归 #10）

- 挂载：`/admin`，框架自带登录（env 配置单管理员，D-09），与 fastapi-users
  用户体系不混流——管理员不需要用户侧登录；
- 发布/下架/检测开关/版本回退：管理界面自定义动作/ModelView 钩子，调
  `domain/level_state.py` 纯函数——治理逻辑仍单点在 Python；
- 媒体上传仍落 uploads/（ADR-6），库里登记元数据；
- 内容编辑即 LEVEL.content JSON 字段组（Pydantic 校验 + 结构化表单）。

## 参考

- Strapi v5 数据库文档与官方 SQLite-in-production 劝退博文（2026-02）
- Directus 数据库配置文档；GitHub 讨论 #10856（introspect 现有库）
- Payload 3.0 发布说明与 SQLite(Drizzle/libSQL) 适配器文档
- sqladmin（smithyhq/sqladmin）、starlette-admin（jowilf）文档

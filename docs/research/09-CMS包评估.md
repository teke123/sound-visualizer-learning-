# 研究资产 · #9 CMS 域：自研 vs 开源内容管理

> CMS 选型；接口与治理边界见 [后端决策图](../decision-map-backend.md)。
> 数据库采用 SQLite；后续迁移 PostgreSQL 需独立评估。

## 结论

**自研域逻辑 + 现成管理界面轮子（sqladmin / starlette-admin，实现期二选一，
倾向 starlette-admin：自定义行动作与字段规则更完整，发布/下架/检测开关等
治理动作可以不绕路地挂在列表行上）。**

## 候选评估

| 候选 | 形态 | 判定 | 依据 |
| ---- | ---- | ---- | ---- |
| sqladmin / starlette-admin | FastAPI 同进程管理界面 | ✅ 采用 | Python 生态；SQLAlchemy 已在栈内，近乎零边际成本；CRUD 壳白嫖，域逻辑留 Python |
| Directus | Node 服务，可 introspect 共享库 | ❌ | 换 Postgres 后结构上最干净的开源形态（单库无双源），但状态机/发布前置/检测开关校验须写 TS hooks；FR-1204 的 allowed_metrics 校验要跨进程调我们的评分域；两运行时共写一库 |
| Strapi v5 | 独立 Node 服务 | ❌ | 内容真源须搬入，我们后端变代理/同步层；单管理员使其角色/工作流卖点闲置；TS 全家桶 |
| Payload 3.0 | 装进 Next.js 的库 | ❌ | 绑 Next.js（我们前端是 Vue SPA）；同代理/同步问题 |

## 核心论据（与数据库选型无关）

CMS 域的真复杂度是定制治理逻辑，不是 CRUD：

- 三态发布状态机 + FR-1203 发布前置（内容完整性/授权/示范可播）；
- 关卡导航依赖（L30 提供回 L01/L09 入口，仅目标已发布才有效，不增设发布阻塞）；
- FR-1204 检测开关校验——`allowed_metrics ⊆ ScoringProvider.stable_metrics()`，
  必须调用我们自己的评分域，开源 CMS 里只能跨进程或双源；
- 整关版本快照 + 回退（FR-1208/1408）+ 审计；
- 大众端 `/api/levels` 必须由我们后端出（LearningContext 每请求重校验 NFR-18
  + detection 子对象组装 + openapi-typescript 契约 #6）——开源 CMS 当不了真源。

开源包省下的是最薄的部分（表单/列表），新增的是跨语言 hooks + 第二运行时 +
部署面；「省代码」为负。管理界面轮子（同进程）是唯一净收益的引入。

## 管理界面整合要点（细则归 #10）

- 挂载：`/admin`，通过框架认证扩展配置单管理员登录（D-09），与学习侧
  用户体系不混流——管理员不需要用户侧登录；
- 发布/下架/检测开关/版本回退：管理界面自定义动作/ModelView 钩子，调
  `domain/level_state.py` 纯函数——治理逻辑仍单点在 Python；
- 媒体上传仍落 uploads/（ADR-6），库里登记元数据；
- 内容编辑仅作用于关卡/文章草稿字段组（校验 + 结构化表单）；公开版本不可变，发布/回退由用例原子完成，不直接编辑 LEVEL 公开内容。

## 参考

- Strapi v5 数据库文档与官方 SQLite-in-production 劝退博文（2026-02）
- Directus 数据库配置文档；GitHub 讨论 #10856（introspect 现有库）
- Payload 3.0 发布说明与 SQLite(Drizzle/libSQL) 适配器文档
- sqladmin（smithyhq/sqladmin）、starlette-admin（jowilf）文档

## 内容治理范围

三态内容状态与应急检测熔断分离，正常发布要求检测就绪；草稿、公开版本与分类公开快照分开。后台须提供缺失项检查、草稿对比、真实前端预览令牌、草稿媒体授权、回退、分类迁移、下架影响提示、标定文本、反馈/希望增加处理和审计。管理库不等于这些业务自动具备，需验证扩展或自定义页面。常规表单仅覆盖录入，禁止绕过用例修改公开版本。媒体元数据/发布引用必须登记，但不扩展独立媒体库产品界面。

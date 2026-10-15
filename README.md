# 看得见的声音 - 智能发音学习平台

## 项目简介

以浏览器为入口、以发音关卡学习与检测为主线的普通话发音学习系统。
学习者看懂口型、听清示范、完成听辨与练习；在已发布且检测已开放的关上提交录音，
得到录音质量结论、曲线对比、分数、可观察现象和规则引擎四步反馈。

> 需求口径：`docs/srs/`（软件需求规格说明书，需求 ID 全局唯一）。
> API 契约：`docs/decision-map-backend.md`（OpenAPI 为真源，`/docs` 可交互查看）。
> 架构：`docs/architecture/`（后端实施方案见 03 篇）。

## 快速开始

### 1. 安装前端依赖
```bash
npm install
```

### 2. 启动前端开发服务器
```bash
npm run dev
```
前端将在 http://localhost:5173 启动

### 3. 安装后端依赖

使用 Python 3.11+（开发环境 3.13 实测通过）。Python 依赖统一在 `backend/requirements.txt`。

```bash
cd backend
pip install -r requirements.txt
```

### 4. 初始化内容并启动后端服务器
```bash
cd backend
python seed.py          # 首次运行：30 关种子内容 + 合成示范音频 + 发布
env -u PYTHONPATH python3 main.py
```

后端将在 http://localhost:8000 启动（API 文档 `/docs`，管理后台 `/admin`，
默认管理员 admin / admin12345，可用环境变量 `SVS_ADMIN_USERNAME` / `SVS_ADMIN_PASSWORD` 覆盖）。
评分 Provider 默认为进程内测试替身（`SVS_PROVIDER=mock`）；接入讯飞评测须
配置 `XFYUN_APP_ID / XFYUN_API_KEY / XFYUN_API_SECRET` 并先完成
docs/architecture/03 的 M0 实测验证。

### 5. 一键启动前后端
```bash
./start-dev.sh
```
脚本会先后台启动后端（端口 8000）与前端（端口 5173），并在退出时自动清理。

## 页面清单（口径：docs/srs/02 4.1）

| 页号 | 页面 | 路由 | 用途 |
| ---- | ---- | ---- | ---- |
| P01 | 首页 | `/` | 四个主按钮（搜一个音 / 看懂发音 / 跟着练 / 录音比较）、搜索、已发布关入口 |
| P02 | 搜索 | `/search` | 汉字、拼音、关卡名搜索；无结果给相近关与「希望增加」 |
| P03 | 发音地图 | `/map` | 单韵母 → 声母 → 拼读三层闯关定位；易混关并排入口 |
| P04 | 发音原理 | `/principles` | 气 → 声 → 口型三步；专业句默认折叠 |
| P05 | 关卡页 | `/learn`、`/learn/:id` | 一句话结论、构形、示范、听辨小测、练习、误区、录音（若开放） |
| P06 | 发音库 | `/library` | 已发布关目录；相近关比较 |
| P07 | 专业资料 | `/materials` | 授权资料：来源、许可、适用边界 |
| P08 | 检测中心 | `/test` | 已发布且检测开放的关：听示范、按要求朗读、提交 |
| P09 | 结果 | `/feedback/:id` | 质量、曲线对比、分数、现象、四步反馈、可靠性、重录 |
| P10 | 声音档案 | `/archive` | 同意后保存；同关两次比较；可删 |
| P11 | 账号 | `/account` | 注册登录、同意状态、撤回、删除档案 |
| — | 后台（CMS） | `/admin` | 关卡录入、发布 / 下架（三态）、检测开关、版本回退、反馈处理 |

## 项目结构

```
├── src/
│   ├── api/              # API 客户端（唯一网络层）
│   ├── components/       # 通用组件（PageState / PageFeedback / LevelRoadmap / SiteFooter）
│   ├── composables/      # 组合式函数（文案位 / 同意提示 / 示范播放）
│   ├── data/pages.ts     # 页号 P01–P11 唯一登记处
│   ├── router/           # 路由配置
│   ├── stores/           # Pinia（levels / units / recording / user）
│   ├── types/            # 前后端契约类型登记处
│   ├── utils/            # 工具（声调曲线处理意图）
│   └── views/            # 页面组件（与上表一一对应）
├── backend/
│   ├── main.py           # FastAPI 组装（/api、/admin、调度任务、启动恢复）
│   ├── seed.py           # 种子脚本：30 关内容/文章/标定文本/合成音频/发布
│   ├── e2e_test.py       # 端到端闭环自测（访客/账号/后台）
│   ├── app/
│   │   ├── platform/     # requestId/envelope/错误映射、CSRF、限流、执行器、调度、审计、删除日志
│   │   ├── content/      # 关卡/文章/版本/发布/下架/回退、媒体授权、搜索、标准曲线
│   │   ├── acoustics/    # 上传/转码(16k PCM)/哈希、信号质检、F0/共振峰（含 tone_py 内核）
│   │   ├── scoring/      # Provider 协议+Mock+讯飞适配、朗读维判定、规则四步、标定/T值、评分缓存
│   │   ├── detection/    # 录音状态机、两步提交幂等、202 回落、30s 硬截止、结果快照
│   │   ├── identity/     # 注册/登录/sid 绑定/同意决定/dataEpoch/注销
│   │   ├── archive/      # 自动转存、个人音域滚动更新、档案与比较、学习事件与 D-24 进度
│   │   ├── feedback/     # 反馈与希望增加
│   │   ├── api/          # 路由层（校验→用例→响应映射）
│   │   └── admin_ui/     # 自建轻量管理台单页（调用同一用例）
│   └── requirements.txt
├── docs/
│   ├── srs/              # 软件需求规格说明书（当前需求口径）
│   └── architecture/     # 架构建议与重构路线图
└── package.json
```

## 关键口径（重构对齐后）

- **评分主链路**：1.0 调用外部普通话评分服务（科大讯飞语音评测，FR-1205）；
  本地 Wav2Vec2 + Praat 栈定位为曲线 / 质检工具与 2.0 专属纠音模型对比（FR-1605）。
- **质量两维闸门**：录音质量（信号维）+ 是否按要求朗读（文本维，来自评分服务
  音节粒度检错）；任一维不合格即停止评分（FR-1301）。
- **CMS 三态**：草稿 → 已发布 → 已下架（→ 已发布），检测开关独立（SRS 05 附录 C）。
- **数据控制**：可不登录先学；保存进度 / 录音须服务端记录的本人同意，可拒绝、
  可撤回、可删（D-08、NFR-15）。

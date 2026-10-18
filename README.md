# 看得见的声音 - 智能发音学习平台

## 项目简介

以浏览器为入口、以发音关卡学习与检测为主线的普通话发音学习系统。
学习者注册登录后看懂口型与声学说明、听清多发音人真人示范（`FV1~FV3` 女声 1~3、`MV1~MV3` 男声 1~3）、完成听辨与练习；在关卡页（P05）
直接提交录音，得到声学可视化对比（基频曲线、共振峰元音空间、送气段 VOT 波形/语谱图）、
分数、可观察现象、规则引擎四步反馈和录音质量提示。

> 需求口径：`docs/srs/`（软件需求规格说明书，需求 ID 全局唯一）。
> API 契约：`docs/decision-map-backend.md`（OpenAPI 为真源，`/docs` 可交互查看）。
> 架构：`docs/architecture/`（后端实施方案见 03 篇）。

## 环境变量与真人语料库配置（团队协同必读）

本项目使用现代汉语标准音节真人录音库（含 `FV1`、`FV2`、`FV3` 三位女声与 `MV1`、`MV2`、`MV3` 三位男声的 WAV 文件，命名规则 `<pinyin><tone>_<SPK>.wav`）初始化关卡示范音、听辨题、原理文章示范、参考发音人音域/元音空间基线以及标准音高曲线。

**切勿在代码中硬编码本地绝对路径**。后端与种子脚本会自动读取仓库根目录（或 `backend/` 目录）下的 `.env` 文件及系统环境变量：

1. 复制环境变量模板：
   ```bash
   cp .env.example .env
   ```
2. 编辑 `.env`，将 `CORPUS_DIR` 指向你本机的真人语音库目录（支持绝对路径或相对于本仓库根目录的相对路径）：
   ```ini
   # 示例 1：相对路径（推荐把「录音」文件夹放在仓库同级目录）
   CORPUS_DIR=../录音

   # 示例 2：本机绝对路径
   # CORPUS_DIR=D:/桌面/项目实践声音/录音
   ```
   > `.env` 已配置在 `.gitignore` 中，不会被提交到 Git 仓库。

### 环境变量一览

| 变量名 | 默认值 | 说明 |
| ---- | ---- | ---- |
| `CORPUS_DIR`（或 `SVS_CORPUS_DIR`） | 无（`seed.py` 必填） | 真人标准音节语料库根目录（内含 `FV1`~`FV3`、`MV1`~`MV3` 子文件夹） |
| `SVS_ENV` | `dev` | 运行环境：`dev` 或 `prod`（`prod` 下 Cookie 启用 `Secure`） |
| `SVS_HOST` / `SVS_PORT` | `127.0.0.1` / `8000` | 后端监听地址与端口 |
| `SVS_DATA_DIR` | `backend/data` | SQLite 数据库、规范化媒体与私有录音存储目录 |
| `SVS_ADMIN_USERNAME` / `SVS_ADMIN_PASSWORD` | `admin` / `admin12345` | 维护后台 `/admin` 登录口令 |
| `SVS_PROVIDER` | `mock` | 评分服务：`mock`（进程内确定性替身）或 `xfyun`（科大讯飞评测） |
| `XFYUN_APP_ID` / `XFYUN_API_KEY` / `XFYUN_API_SECRET` | 空 | `SVS_PROVIDER=xfyun` 时的讯飞流式评测凭据 |

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

### 4. 初始化真人语料种子并启动后端服务器
确保已在 `.env` 中配置 `CORPUS_DIR` 后执行：
```bash
cd backend
python seed.py --reset  # 清库并导入 FV1~3/MV1~3 真人示范、参考发音人基线与 30 关标准曲线
env -u PYTHONPATH python3 main.py
```

后端将在 http://localhost:8000 启动（API 文档 `/docs`，管理后台 `/admin`，
默认管理员 admin / admin12345，可用环境变量 `SVS_ADMIN_USERNAME` / `SVS_ADMIN_PASSWORD` 覆盖）。

### 5. 一键启动前后端
```bash
./start-dev.sh
```
脚本会先后台启动后端（端口 8000）与前端（端口 5173），并在退出时自动清理。Windows 下可直接运行 `start-dev.bat`。

## 页面清单（口径：docs/srs/02 4.1）

| 页号 | 页面 | 路由 | 用途 |
| ---- | ---- | ---- | ---- |
| P01 | 首页 | `/` | 四个主按钮（搜一个音 / 看懂发音 / 跟着练 / 录音比较）、搜索、已开放关入口 |
| P02 | 搜索 | `/search` | 汉字、拼音、关卡名搜索；无结果给相近关与「希望增加」 |
| P03 | 发音地图 | `/map` | 单韵母 → 声母 → 拼读三层闯关定位；易混关并排入口 |
| P04 | 发音原理 | `/principles`、`/principles/:slug` | 气 → 声 → 口型三步；原理文章、短练习与关联关卡 |
| P05 | 关卡页 | `/learn/:id` | 一句话结论、构形与声学说明、6 发音人示范切换、听辨题、练习、误区、本关录音检测 |
| P06 | 发音库 | `/library` | 已开放关目录；相近关比较 |
| P09 | 结果 | `/result/:id` | 声学可视化对比、分数、现象、四步反馈、录音质量提示、重录 |
| P10 | 声音档案 | `/archive` | 自动保存；同关多次记录比较；可删 |
| P11 | 账号 | `/account` | 注册登录、退出、音域标定、清空档案、注销账号 |
| — | 维护后台 | `/admin` | 团队自用内容维护：关卡/文章/媒体编辑、开放切换、反馈查看 |

## 项目结构

```
├── .env.example          # 环境变量配置模板（复制为 .env 配置 CORPUS_DIR 等）
├── src/
│   ├── api/              # API 客户端（唯一网络层：client、endpoints、生成契约类型 generated/）
│   ├── components/       # 通用组件（DemoPlayer、PageState、RecorderPanel、QualityVerdict 等）
│   ├── copy/             # 文案位（页面文案按页号登记）
│   ├── features/         # 组合式功能模块（auth / calibration / assessment / result / archive 等）
│   ├── mocks/            # MSW mock（dev:mock 模式，形状与后端契约同步）
│   ├── pages/            # 页面组件（与上表一一对应）
│   ├── renderers/        # 渲染器（关卡 / 文章 / 声调曲线 / 共振峰 / 送气段波形 / 声道剖面）
│   ├── router/           # 路由配置
│   ├── stores/           # Pinia（levels / context / progress / completion / recorder / player / outbox）
│   └── utils/            # 工具（UUID、安全存储、时间格式化、前端实时声学计算）
├── backend/
│   ├── main.py           # FastAPI 组装（/api、/admin、启动恢复）
│   ├── seed.py           # 种子脚本：导入真人语料库（FV1~3/MV1~3）、计算参考发音人基线与标准曲线
│   ├── e2e_test.py       # 端到端闭环自测（账号/关卡录音/后台）
│   ├── app/
│   │   ├── platform/     # requestId/envelope/错误映射、限流、执行器
│   │   ├── content/      # 关卡/文章/媒体、开放开关、搜索、标准曲线
│   │   ├── acoustics/    # 上传/哈希、信号质检、F0/共振峰/VOT（含 tone_py 内核）
│   │   ├── scoring/      # Provider 协议+Mock+讯飞适配、规则四步、标定/T值、评分缓存
│   │   ├── detection/    # 录音状态机、两步提交幂等、202 回落、30s 硬截止
│   │   ├── identity/     # 注册/登录/退出/注销
│   │   ├── archive/      # 档案与比较、个人音域、学习事件与 D-24 进度
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

- **真人示范与声学基线**：30 关全部接入 `FV1~FV3`、`MV1~MV3` 六位真人标准发音人示范，参考发音人五度音域（对数分位数）与单韵母共振峰靶区（按男女声道长度自适应 ceiling + 稳态中段中位数）均由真实录音实测标定。
- **评分主链路**：1.0 调用外部普通话评分服务（科大讯飞语音评测，FR-1205）；
  本地声学栈（Praat/parselmouth、tone_py）负责 F0 / 共振峰 / VOT 等声学特征提取与
  可视化数据，并作为 2.0 专属纠音模型对比（FR-1604）的基座。
- **录音质量提示**：音量、噪声、截幅、时长等信号质量指标照常检测，但仅作为
  结果页的友好提示展示，不拦截评分与可视化（FR-1301）。
- **后台定位**：团队自用的简单内容维护工具，关卡一个「开放 / 未开放」开关，
  保存即生效（D-09）。
- **账号与数据**：注册登录即默认同意服务条款；进度与录音自动保存到账号，
  可删除单条录音、清空档案、注销账号（D-08、NFR-15）。

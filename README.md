# 看得见的声音 - 智能发音学习平台

## 项目简介

普通话发音学习系统。

## 环境变量与录音数据

本项目使用 Tone Perfect 现代汉语标准音节真人录音库

配置环境变量：

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


### 环境变量一览

| 变量名                                                   | 默认值                    | 说明                                                   |
| ----------------------------------------------------- | ---------------------- | ---------------------------------------------------- |
| `CORPUS_DIR`（或 `SVS_CORPUS_DIR`）                      | 无（`seed.py` 必填）        | 标准音节语料库根目录（内含 `FV1`~`FV3`、`MV1`~`MV3` 子文件夹）          |
| `SVS_ENV`                                             | `dev`                  | 运行环境：`dev` 或 `prod`（`prod` 下 Cookie 启用 `Secure`）     |
| `SVS_HOST` / `SVS_PORT`                               | `127.0.0.1` / `8000`   | 后端监听地址与端口                                            |
| `SVS_DATA_DIR`                                        | `backend/data`         | SQLite 数据库、规范化媒体与私有录音存储目录                            |
| `SVS_ADMIN_USERNAME` / `SVS_ADMIN_PASSWORD`           | `admin` / `admin12345` | 维护后台 `/admin` 登录口令                                   |
| `SVS_PROVIDER`                                        | `xfyun`                | 评分服务：`xfyun`（科大讯飞评测，默认）或 `mock`（进程内确定性替身，测试/离线时显式指定） |
| `XFYUN_APP_ID` / `XFYUN_API_KEY` / `XFYUN_API_SECRET` | 空                      | 讯飞流式评测凭据（默认 Provider 即需要；缺失时评分将全部失败）                 |
| `SVS_F0_RESCUE` / `SVS_F0_CORRECT` / `SVS_F0_INTERP`  | `1`                    | F0 管线纠偏开关（弱周期恢复 / 跳变候选纠偏 / 短毛刺插值，置 0 关闭以便对比评测）       |

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

使用 Python 3.11+。

```bash
cd backend
pip install -r requirements.txt
```

### 4. 初始化真人语料种子并启动后端服务器
确保已在 `.env` 中配置 `CORPUS_DIR` 后执行：
```bash
cd backend
python seed.py --reset  
env -u PYTHONPATH python3 main.py
```

后端将在 http://localhost:8000 启动（API 文档 `/docs`，管理后台 `/admin`，
默认管理员 admin / admin12345）。

### 5. 一键启动前后端

Windows 可以尝试运行仓库根目录下的 start-dev.bat
```bash
./start-dev.sh
```
脚本会启动后端（端口 8000）与前端（端口 5173）。

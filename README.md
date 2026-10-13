# 看得见的声音 - 智能发音学习平台

音频后端的当前模块、接口状态和流程见 [音频模块架构](docs/AUDIO_ARCHITECTURE.md)。
`/api/audio/analyze` 已删除；quality、features、score 为返回 HTTP 501 的占位接口。
ASR 已统一到主应用，前端录音结果链路待重新接入。

## 项目简介

基于多模态可视化技术的智能发音学习系统，通过3D口腔动画、声调曲线对比、AI发音评估等功能，帮助用户快速掌握标准普通话发音。

## 技术栈

### 前端
- **Vue 3** + TypeScript + Vite
- **Three.js** - 3D口腔动画可视化
- **ECharts** - 声调曲线图表
- **Element Plus** - UI组件库
- **Web Audio API** - 实时音频录制和可视化

### 后端
- **FastAPI** - Python Web框架
- **Librosa** - 音频分析库
- **PyTorch** - 深度学习框架（Wav2Vec2/HuBERT）
- **WebSocket** - 实时音频流传输

## 快速开始

### 1. 安装前端依赖
```bash
cd pronunciation-learning
npm install
```

### 2. 启动前端开发服务器
```bash
npm run dev
```
前端将在 http://localhost:5173 启动

### 3. 安装后端依赖

使用 Python 3.10 或 3.11。运行服务、测试、样本生成和文档转换的 Python 依赖统一在 `backend/requirements.txt`。

```bash
cd backend
pip install -r requirements.txt
```

### 4. 启动后端服务器
```bash
env -u PYTHONPATH python3 main.py
```
> - macOS/Linux 使用 `python3`；若使用 `python main.py` 提示命令不存在，请改用 `python3`。
> - **必须使用 `env -u PYTHONPATH` 启动**：在 CodeBuddy 等 IDE 的集成终端中，
>   PYTHONPATH 会被注入 IDE 的 Python shim，拦截 librosa 写缓存时的 unlink 操作，
>   导致 `/api/audio/analyze` 返回 500。`./start-dev.sh` 已自动处理该问题。
后端将在 http://localhost:8000 启动

### 5. 一键启动前后端
```bash
./start-dev.sh
```
脚本会先后台启动后端（端口 8000）与前端（端口 5173），并在退出时自动清理。

## 功能模块

### P01 发音地图
- 63个拼音字母的二维矩阵布局
- 颜色区分：声母(蓝)、韵母(绿)、声调(橙)
- 点击跳转到发音学习页面

### P02 发音库
- 12个发音单元的卡片网格布局
- 显示学习进度和状态
- 搜索和筛选功能

### P03 发音学习
- 目标发音展示和文字描述
- 示范音频播放
- 实时录音和波形可视化
- 常见误区提示

### P04 反馈系统
- 综合评分环形进度条
- 声调曲线对比图（ECharts）
- 3D口腔动画（Three.js）
- 改进建议列表

### P05 学习进度
- 进度概览卡片
- 学习趋势图表
- 单元进度表格

### P06 发音对比
- 双录音区域对比
- 相似度评分

### P07 学习记录
- 练习历史表格
- 重听和重练功能

### P08 后台管理
- 内容管理
- 媒体管理
- 数据统计

### P09 音频录制
- 底部固定控制栏
- 实时波形显示

### P10 进度管理
- 概览、单元、趋势、成就标签页

## 项目结构

```
pronunciation-learning/
├── src/
│   ├── api/              # API接口
│   ├── assets/           # 静态资源
│   ├── components/       # 通用组件
│   ├── composables/      # Vue组合式函数
│   ├── router/           # 路由配置
│   ├── stores/           # Pinia状态管理
│   ├── types/            # TypeScript类型定义
│   ├── utils/            # 工具函数
│   └── views/            # 页面组件
│       ├── HomeView.vue          # 首页
│       ├── PronunciationMap.vue  # P01 发音地图
│       ├── PronunciationLibrary.vue # P02 发音库
│       ├── LearningView.vue      # P03 发音学习
│       ├── FeedbackView.vue      # P04 反馈系统
│       ├── ProgressView.vue      # P05 学习进度
│       ├── ComparisonView.vue    # P06 发音对比
│       ├── HistoryView.vue       # P07 学习记录
│       ├── AdminView.vue         # P08 后台管理
│       └── ProgressManagement.vue # P10 进度管理
├── backend/
│   ├── main.py           # FastAPI后端
│   └── requirements.txt  # Python依赖
├── package.json
└── README.md
```

## GitHub参考项目

1. **VocalTractLab** - 3D声道建模
   - https://github.com/egonelbre/VocalTractLab

2. **Wav2Vec2/HuBERT** - 预训练语音模型
   - https://github.com/pytorch/audio

3. **Librosa** - 音频分析库
   - https://github.com/librosa/librosa

4. **Parselmouth** - Praat Python接口
   - https://github.com/YannickJadw/Parselmouth

5. **PitchDetect** - 浏览器音高检测
   - https://github.com/cwilso/PitchDetect

## 开发计划

### 第一阶段：基础架构（第1-2周）✅
- [x] Vue 3 + TypeScript + Vite项目搭建
- [x] Vue Router路由配置
- [x] Pinia状态管理
- [x] Element Plus UI集成
- [x] Three.js集成
- [x] FastAPI后端搭建

### 第二阶段：核心功能（第3-8周）
- [x] 发音地图页面
- [x] 发音库页面
- [x] 发音学习页面
- [x] 反馈系统页面
- [ ] 完整音频分析流程
- [ ] 3D口腔动画优化

### 第三阶段：高级功能（第9-16周）
- [ ] Wav2Vec2/HuBERT模型集成
- [ ] 实时WebSocket音频流
- [ ] 发音对比功能
- [ ] 学习进度管理

### 第四阶段：完善优化（第17-24周）
- [ ] 后台管理系统
- [ ] 性能优化
- [ ] 用户体验优化
- [ ] 测试和文档

## 许可证

MIT License

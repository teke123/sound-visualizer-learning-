# 用于 LLM 发音建议的声学材料

该功能从学习者录音和声母、韵母时间对齐中提取声学测量，生成结构化数值与六类复合图像。产品在关卡评分任务的 `finalizing` 阶段生成 `pronunciationEvidence`；结果页展示图像并提供数据下载。发音建议输入由测量数值、所选图像、关卡目标、评分检错和用户语言背景组成。

## 输入

产品分析使用 44.1 kHz 单声道录音、评分服务返回的音节及音素时间戳、受理录音时保存的个人音域快照和已有元音空间标定。音域由项目现有的标定与自适应机制提供。个人元音空间中的 `overall` 用于 F1/F2 的 z 分数换算，`i/u/a` 锚点用于元音图的背景三角形；数据含 `speaker_max_formant` 时用于 Burg 共振峰分析上限。

当前产品的标准参考字段为 `null`。命令行可显式输入一条参考录音及其对齐结果，供独立分析使用。

## 图像

图像按录音包含的声母、韵尾和学习目标选择，单次最多四张。

| 文件 | 图中数据 | 适用内容 |
| --- | --- | --- |
| `P01_overview_prosody.png` | 波形、相对强度、音素与时长、0–5 kHz 宽带和窄带语谱、F1/F2/F3、事件边界、五度值和对应 Hz 轴。 | 所有录音 |
| `P02_tone_vowel_norm.png` | 每音节 21 点五度曲线、Chao 调值、个人音域数值、固定 Bark 坐标元音轨迹与 i/u/a 三角形。 | 所有录音 |
| `P03_plosive_affricate.png` | 局部波形、0–12 kHz 宽带和 0–5 kHz 窄带语谱、高频摩擦与中频气流包络；除阻、摩擦结束、浊音起点、VOT 和分段时长。 | 塞音、塞擦音 |
| `P04_sibilant_spectrum.png` | 摩擦频谱、谱峰、重心、标准差、偏度、峰度及相对元音电平差。 | 擦音、塞擦音 |
| `P05_nasal_dynamics.png` | 鼻音及元音的宽带、窄带语谱，F1/F2/F3、鼻尾起点和时长、ΔF2、A1−P0 与中低频能量差。 | 鼻声母、鼻韵尾 |
| `P06_approximant_transition.png` | 边音或 r 的宽带、窄带语谱，F1/F2/F3 过渡、F3 谷值或 ΔF1、谐噪比与高频电平。 | l、r |

`general` 优先选总览、声调元音图，再按音素类别补充局部图；`tone` 选总览与声调元音图；`vowel` 选总览与声调元音图，鼻韵尾增加鼻音图；`initial` 选总览及对应声母图；`nasal` 选总览、鼻音图和声调元音图。

## 数值与图像的关系

一条录音共用一组基频、强度、共振峰、声门脉冲、语谱和事件时间点。各图按相同时间锚点显示数据。`measurements` 记录目标音、音素与音节时长、声调 21 点 Hz/五度值、元音 11 点 F1/F2/F3、稳态共振峰、轨迹长度、塞音 VOT、塞擦音分段、摩擦频谱矩、鼻音过渡和边音/r 特征。测量状态位于 `reliability`，参考对比项的有效性位于 `can_use`。

`llm_input` 包含提示词、目标、上下文、图像文件名和 `measurements`。提示词要求 LLM 按“观察事实、定位练习环节、给出一个可执行练习、说明复练目标”组织建议，引用有效测量和评分检错。

## 独立运行

在 `backend/` 目录执行：

```sh
python -m app.acoustics.pronunciation_figures --audio learner.wav --alignment alignment.json --output output --goal initial
```

输出目录包含 `measurements.json`、所选 PNG 和 `llm_input.json`。`--all-figures` 生成全部适用图像；`--vowel-space` 可传入个人元音空间 JSON；`--pitch-range LOW HIGH` 提供个人音域；`--reference`、`--reference-alignment` 和 `--reference-pitch-range` 用于显式参考录音。

测量参数与调用流程详见 [音频分析图像功能说明](音频分析图像功能说明.md)。

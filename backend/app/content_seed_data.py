# -*- coding: utf-8 -*-
"""“看得见的声音”内容种子数据（示例种子，纯字面量）。

本文件只包含 Python 字面量（dict/list/str/int/float/bool/None），
不 import 任何模块、不做任何文件读写，供后端 seed 脚本直接导入。

包含：
- LEVELS：30 个关卡（L01–L30）
- GLOBAL_FOUR_STEP_FALLBACKS：四步反馈全局兜底模板
- CALIBRATION_TEXT：录音校准文本
- ARTICLE_CATEGORIES：文章分类
- ARTICLES：原理文章
"""

LEVELS = [
    {
        "id": "L01",
        "order": 1,
        "layer": "vowel",
        "type": "单韵母",
        "targetSound": "a",
        "pinyin": "a",
        "representativeChar": "啊",
        "title": "单韵母 a · 把嘴张大",
        "oneLiner": "把嘴张大、舌头放平，发出最响亮的 a。",
        "goal": "学会把嘴充分张开、稳定地发出清晰的 a，并能听出 a 和 o 的区别。",
        "applicableIssues": "适合说话嘴张不开、a 听起来偏扁偏窄的学习者。",
        "tags": ["张大嘴", "开口音", "低舌位"],
        "skeletonPublic": True,
        "confusables": ["L02", "L30"],
        "articulation": {
            "description": "发 a 时，下巴放松地往下打开，像打哈欠的前半段；嘴角自然向两边摊开，舌头平放在口腔底部。嘴开得越大，声音越亮、越通畅。口型保持不动，a 就能稳稳地延长。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "张口发 a（可延长）",
                    "holdMs": 700,
                    "jaw": 0.9,
                    "lips": {"aperture": 0.85, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.25, "backness": 0.45, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L01_demo_normal_male", "speed": "normal", "voice": "male", "text": "啊"},
            {"ref": "L01_demo_normal_female", "speed": "normal", "voice": "female", "text": "啊"},
        ],
        "quizzes": [
            {
                "id": "L01-Q1",
                "prompt": "听一听，这是哪个单韵母？",
                "options": [{"text": "a"}, {"text": "o"}],
                "answerIndex": 0,
                "stimulusRef": "L01_quiz_Q1",
                "stimulusText": "a",
                "explanation": "刚才那个音嘴巴张得很大、声音很亮，是 a。嘴只张一半就容易跑成 o。",
            },
            {
                "id": "L01-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "妈 mā"}, {"text": "摸 mō"}],
                "answerIndex": 0,
                "stimulusRef": "L01_quiz_Q2",
                "stimulusText": "妈 mā",
                "explanation": "两个字的声母都是 m，区别在韵母：嘴张大的是“妈”，嘴唇收圆的是“摸”。",
            },
        ],
        "practice": [
            {"id": "L01-P1", "title": "打个哈欠再发音", "instruction": "像打哈欠的前半段那样把嘴张到最大，保持 2 秒，再发 a，读完停 1 秒。", "repeat": 5, "durationSec": None, "bodyCue": "下巴完全放松地下沉，喉咙敞开没有紧绷感。", "stopNote": "不舒服就停止"},
            {"id": "L01-P2", "title": "长音稳住", "instruction": "发 a 并拉长到 5 秒左右，音量保持均匀，一口气算一组。", "repeat": None, "durationSec": 30, "bodyCue": "小腹微微托住气息，口型从头到尾保持张大。", "stopNote": "头晕就坐下休息"},
            {"id": "L01-P3", "title": "a 和 o 换口型", "instruction": "先发 a 再滑到 o，来回 5 次，体会嘴从“摊开”到“收圆”。", "repeat": 5, "durationSec": None, "bodyCue": "变化只发生在嘴唇，下巴和舌头基本不动。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "a 听起来又扁又闷，像 e，通常是嘴没张开、舌头抬高了。", "fix": "可以先用手指轻轻抵住下巴，帮自己把嘴撑开再发音，习惯后再放开手。"},
            {"phenomenon": "越想读得响就越用力，脖子跟着使劲，声音反而发紧。", "fix": "可以试试先小声发 a，只在嘴巴张开度上做文章，响度自然会来。"},
        ],
        "professional": {
            "description": "a 是央低不圆唇元音 [a]，发音时口大开，舌位低而略偏前，软腭抬起关闭鼻腔通道，声带振动。它是普通话开口度最大的单元音，第一共振峰最高，常作为元音共振峰的锚点。",
            "acousticRefs": [
                {"name": "F1（第一共振峰）", "value": "约 700–1000 Hz", "note": "开口度越大 F1 越高，因人而异"},
                {"name": "F2（第二共振峰）", "value": "约 1100–1400 Hz", "note": "舌位越前 F2 越高，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：啊",
            "evaluationText": "啊",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "final", "formants"],
            "reliabilityNote": "本关以口型要点与共振峰参考为主，评分和曲线供学习参考，数值因人而异。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与嘴张开不足、声音不够稳定有关。", "cue": "先打个哈欠把嘴张开，再稳定发出 a。", "practiceStepId": "L01-P1"},
                {"tag": "final_error", "phenomenon": "本次韵母听起来跑到了相近的音上，比如 a 读起来更像 o。", "possibleCause": "可能与嘴唇收拢、下巴没打开有关。", "cue": "下巴再往下放一点，嘴角向两边展开。", "practiceStepId": "L01-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“啊”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音太快、音高没站稳有关。", "cue": "轻轻起音，把音高站平稳，像轻轻叹气一样平。", "practiceStepId": "L01-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与没吸好气就开口有关。", "cue": "先吸一口气，把“啊”读满 2 秒再停。", "practiceStepId": "L01-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音，比如“啊”后面又跟了一声。", "possibleCause": "可能与习惯性回读、想再读一次有关。", "cue": "只读一次，读完安静保持 1 秒。", "practiceStepId": "L01-P2"},
                {"tag": "formant_deviation", "phenomenon": "本次 a 的共振峰位置偏离常见参考区，开口度或舌位与参考不同。", "possibleCause": "可能与嘴张得不够大、舌位偏高有关。", "cue": "把嘴张到最大再发音，听听声音有没有变亮。", "practiceStepId": "L01-P1"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L02",
        "order": 2,
        "layer": "vowel",
        "type": "单韵母",
        "targetSound": "o",
        "pinyin": "o",
        "representativeChar": "噢",
        "title": "单韵母 o · 嘴唇拢圆",
        "oneLiner": "嘴唇收圆留个小孔，发出圆润的 o。",
        "goal": "学会把嘴唇拢圆、口型保持稳定地发 o，并听出 o 和 a、e 的区别。",
        "applicableIssues": "适合 o 容易读成 e（嘴唇没圆起来）的学习者。",
        "tags": ["圆唇", "拢嘴", "稳定口型"],
        "skeletonPublic": True,
        "confusables": ["L01", "L03"],
        "articulation": {
            "description": "发 o 时，嘴巴半开，嘴唇向中间收拢成一个圆圆的小孔，像含着一根粗吸管；舌头后半部分微微抬起，舌位不前不后。发音全程嘴唇保持圆形不变，声音就圆润稳定。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "圆唇发 o（可延长）",
                    "holdMs": 700,
                    "jaw": 0.45,
                    "lips": {"aperture": 0.3, "rounding": 0.85, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.45, "backness": 0.6, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L02_demo_normal_male", "speed": "normal", "voice": "male", "text": "噢"},
            {"ref": "L02_demo_normal_female", "speed": "normal", "voice": "female", "text": "噢"},
        ],
        "quizzes": [
            {
                "id": "L02-Q1",
                "prompt": "听一听，这是哪个单韵母？",
                "options": [{"text": "e"}, {"text": "o"}],
                "answerIndex": 1,
                "stimulusRef": "L02_quiz_Q1",
                "stimulusText": "o",
                "explanation": "嘴唇圆起来、声音圆润的是 o；嘴角展开、声音偏扁的是 e。刚才这个音是圆唇的。",
            },
            {
                "id": "L02-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "摸 mō"}, {"text": "妈 mā"}],
                "answerIndex": 0,
                "stimulusRef": "L02_quiz_Q2",
                "stimulusText": "摸 mō",
                "explanation": "嘴唇收圆的是“摸”，直接张大嘴的是“妈”。",
            },
        ],
        "practice": [
            {"id": "L02-P1", "title": "含吸管练习", "instruction": "想象嘴里含着一根粗吸管，把嘴唇拢圆，保持 3 秒再发 o。", "repeat": 5, "durationSec": None, "bodyCue": "两颊放松，嘴唇像圆圈一样围住，基本看不见牙齿。", "stopNote": "不舒服就停止"},
            {"id": "L02-P2", "title": "圆唇长音", "instruction": "圆着嘴发 o 并拉长到 5 秒左右，口型不许变扁。", "repeat": None, "durationSec": 30, "bodyCue": "嘴唇维持圆孔大小，气流匀匀地出来。", "stopNote": "嘴唇发酸就休息"},
            {"id": "L02-P3", "title": "o 和 e 切换", "instruction": "先圆唇发 o，再咧嘴发 e，来回 5 次，体会嘴唇收圆与展开。", "repeat": 5, "durationSec": None, "bodyCue": "变化的只是嘴唇圆扁，舌头几乎不动。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "o 读着读着嘴型变扁，听起来像 e。", "fix": "可以对着镜子，在嘴前比一个圆圈，让口型始终对准圆圈再发音。"},
            {"phenomenon": "为了圆唇使劲噘嘴，声音反而发闷。", "fix": "可以先把嘴自然半张，再轻轻拢圆，噘得太用力反而堵住声音。"},
        ],
        "professional": {
            "description": "o 是后半高圆唇元音 [o]，单发时唇拢圆、舌面后部抬起，软腭抬起关闭鼻腔，声带振动。在 bo、po、mo、fo 等音节中，唇形与声母动作相连，圆唇度常略减。",
            "acousticRefs": [
                {"name": "F1（第一共振峰）", "value": "约 400–600 Hz", "note": "圆唇会使 F1 略降，因人而异"},
                {"name": "F2（第二共振峰）", "value": "约 700–1000 Hz", "note": "圆唇同时拉低 F2，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：噢",
            "evaluationText": "噢",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "final", "formants"],
            "reliabilityNote": "本关以唇形要点与共振峰参考为主，评分和曲线供学习参考，数值因人而异。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与唇形没做足、口型中途变化有关。", "cue": "先摆好圆唇口型再出声，全程保持圆形。", "practiceStepId": "L02-P1"},
                {"tag": "final_error", "phenomenon": "本次韵母听起来跑到了相近的音上，比如 o 读起来更像 e。", "possibleCause": "可能与嘴唇没收圆、嘴角咧开了有关。", "cue": "嘴角向中间收拢，嘴唇圆圆地留个小孔。", "practiceStepId": "L02-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“噢”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音没站稳、读得太急有关。", "cue": "轻轻起音，像画一条平稳的直线。", "practiceStepId": "L02-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气没吸够就开口有关。", "cue": "先吸一口气，把“噢”读满 2 秒再停。", "practiceStepId": "L02-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完保持口型安静 1 秒。", "practiceStepId": "L02-P2"},
                {"tag": "formant_deviation", "phenomenon": "本次 o 的共振峰位置偏离常见参考区，唇形或舌位与参考不同。", "possibleCause": "可能与圆唇程度不够、舌位偏前有关。", "cue": "嘴唇再收圆一点，听听声音是不是更圆润。", "practiceStepId": "L02-P1"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L03",
        "order": 3,
        "layer": "vowel",
        "type": "单韵母",
        "targetSound": "e",
        "pinyin": "e",
        "representativeChar": "鹅",
        "title": "单韵母 e · 嘴角展开",
        "oneLiner": "嘴角向两边展开，自然发出不圆唇的 e。",
        "goal": "学会嘴唇放松展开、稳定地发 e，并听出 e 和 o 的圆扁区别。",
        "applicableIssues": "适合 e 容易读成 o（嘴唇误圆）或读得太靠前的学习者。",
        "tags": ["展唇", "中舌位", "微笑口型"],
        "skeletonPublic": True,
        "confusables": ["L02"],
        "articulation": {
            "description": "发 e 时，嘴巴半开，嘴角轻轻向两边展开，像浅浅微笑；舌头往后缩一点点，后半部分微微抬起。嘴唇全程保持展开不圆，声音自然地从喉咙送出来。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "展唇发 e（可延长）",
                    "holdMs": 700,
                    "jaw": 0.4,
                    "lips": {"aperture": 0.45, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.45, "backness": 0.65, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L03_demo_normal_male", "speed": "normal", "voice": "male", "text": "鹅"},
            {"ref": "L03_demo_normal_female", "speed": "normal", "voice": "female", "text": "鹅"},
        ],
        "quizzes": [
            {
                "id": "L03-Q1",
                "prompt": "听一听，这是哪个单韵母？",
                "options": [{"text": "e"}, {"text": "o"}],
                "answerIndex": 0,
                "stimulusRef": "L03_quiz_Q1",
                "stimulusText": "e",
                "explanation": "刚才这个音嘴角是展开的、不圆唇，是 e；嘴唇拢圆的是 o。",
            },
            {
                "id": "L03-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "鹅 ē"}, {"text": "喔 ō"}],
                "answerIndex": 0,
                "stimulusRef": "L03_quiz_Q2",
                "stimulusText": "鹅 ē",
                "explanation": "展唇、声音略扁的是“鹅”；圆唇、声音圆润的是“喔”。",
            },
        ],
        "practice": [
            {"id": "L03-P1", "title": "微笑式展唇", "instruction": "嘴角像浅微笑一样向两边展开，保持 3 秒再发 e。", "repeat": 5, "durationSec": None, "bodyCue": "嘴角微微有拉伸感，嘴唇不用劲。", "stopNote": "不舒服就停止"},
            {"id": "L03-P2", "title": "e 长音", "instruction": "展唇发 e 并拉长到 5 秒左右，口型不许变圆。", "repeat": None, "durationSec": 30, "bodyCue": "喉咙放松，声音像从胸口平稳送出。", "stopNote": "不舒服就停止"},
            {"id": "L03-P3", "title": "e/o 圆扁对比", "instruction": "展唇发 e、圆唇发 o 交替进行 6 次，体会嘴唇一扁一圆。", "repeat": 6, "durationSec": None, "bodyCue": "舌头基本不动，变化都在嘴唇。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "e 听起来像 o，通常是嘴唇不自觉地圆起来了。", "fix": "可以照着镜子盯嘴角，发音全程保持嘴角展开。"},
            {"phenomenon": "发 e 时喉咙挤、声音发紧。", "fix": "可以先打个哈欠保持喉咙敞开，再轻轻带出 e。"},
        ],
        "professional": {
            "description": "e 是后半高不圆唇元音 [ɤ]（“鹅”的韵母），舌面后部抬起向软腭，嘴角展开，软腭抬起，声带振动。它与 o 舌位相近，差别主要在唇形：e 展唇，o 圆唇。",
            "acousticRefs": [
                {"name": "F1（第一共振峰）", "value": "约 400–600 Hz", "note": "半高舌位对应的中低 F1，因人而异"},
                {"name": "F2（第二共振峰）", "value": "约 1000–1400 Hz", "note": "不圆唇使 F2 高于 o，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：鹅",
            "evaluationText": "鹅",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "final", "formants"],
            "reliabilityNote": "本关以唇形要点与共振峰参考为主，评分和曲线供学习参考，数值因人而异。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与展唇不够、舌位偏移有关。", "cue": "先摆好微笑口型，再自然发出 e。", "practiceStepId": "L03-P1"},
                {"tag": "final_error", "phenomenon": "本次韵母听起来跑到了相近的音上，比如 e 读起来更像 o。", "possibleCause": "可能与嘴唇不自觉收圆有关。", "cue": "嘴角向两边展开，别让嘴唇变圆。", "practiceStepId": "L03-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“鹅”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音太冲、音高没站稳有关。", "cue": "轻轻起音，音高像滑出一条平线。", "practiceStepId": "L03-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与准备不足就开口有关。", "cue": "吸口气，把“鹅”读满 2 秒再停。", "practiceStepId": "L03-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L03-P2"},
                {"tag": "formant_deviation", "phenomenon": "本次 e 的共振峰位置偏离常见参考区，唇形或舌位与参考不同。", "possibleCause": "可能与展唇不足、舌位太前有关。", "cue": "嘴角展开、舌头稍向后缩一点再发。", "practiceStepId": "L03-P1"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L04",
        "order": 4,
        "layer": "vowel",
        "type": "单韵母",
        "targetSound": "i",
        "pinyin": "i",
        "representativeChar": "一",
        "title": "单韵母 i · 咧嘴抬高舌头",
        "oneLiner": "嘴角咧开、舌前部抬高，发出又细又亮的 i。",
        "goal": "学会舌面前部抬高、嘴角展开地发 i，并听出 i 和 ü 的圆扁区别。",
        "applicableIssues": "适合 i、ü 不分（嘴唇圆扁不分）的学习者。",
        "tags": ["高舌位", "前舌位", "展唇", "细音"],
        "skeletonPublic": True,
        "confusables": ["L06"],
        "articulation": {
            "description": "发 i 时，嘴巴开得很小，嘴角向两边咧开像微笑；舌头前部明显抬高，靠近上腭但不贴住，舌尖轻轻待在下面。声音又细又亮，像一根细线。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "展唇高舌发 i（可延长）",
                    "holdMs": 700,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.9, "backness": 0.1, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L04_demo_normal_male", "speed": "normal", "voice": "male", "text": "一"},
            {"ref": "L04_demo_normal_female", "speed": "normal", "voice": "female", "text": "一"},
        ],
        "quizzes": [
            {
                "id": "L04-Q1",
                "prompt": "听一听，这是哪个单韵母？",
                "options": [{"text": "i"}, {"text": "ü"}],
                "answerIndex": 0,
                "stimulusRef": "L04_quiz_Q1",
                "stimulusText": "i",
                "explanation": "咧嘴、声音细亮的是 i；嘴唇撮圆的是 ü。",
            },
            {
                "id": "L04-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "衣 yī"}, {"text": "迂 yū"}],
                "answerIndex": 0,
                "stimulusRef": "L04_quiz_Q2",
                "stimulusText": "衣 yī",
                "explanation": "两个字的舌头位置一样，区别在嘴唇：咧嘴是“衣”，撮圆是“迂”。",
            },
        ],
        "practice": [
            {"id": "L04-P1", "title": "咧嘴亮音", "instruction": "嘴角咧开、舌前部抬高发 i，保持 3 秒再放开。", "repeat": 5, "durationSec": None, "bodyCue": "舌前部贴近上腭有轻微紧张感，嘴角有拉伸。", "stopNote": "不舒服就停止"},
            {"id": "L04-P2", "title": "i 长音", "instruction": "保持口型不变，发 i 拉长到 5 秒左右。", "repeat": None, "durationSec": 30, "bodyCue": "气息从窄缝里匀匀通过，声音细而稳。", "stopNote": "不舒服就停止"},
            {"id": "L04-P3", "title": "i/ü 圆唇切换", "instruction": "舌头不动，嘴唇由咧变撮，i 变成 ü 再变回 i，来回 6 次。", "repeat": 6, "durationSec": None, "bodyCue": "舌头位置保持不变，只有嘴唇在动。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "i 发得发闷，像 e，通常是舌位没抬高。", "fix": "可以先把舌尖轻抵下齿背、舌面拱起，再发音。"},
            {"phenomenon": "i 和 ü 分不清，两个字听起来一样。", "fix": "可以照镜子看嘴唇：咧嘴是 i，撮圆是 ü，舌头其实没变。"},
        ],
        "professional": {
            "description": "i 是前高不圆唇元音 [i]，舌面前部抬至接近硬腭，唇形扁平展开，软腭抬起，声带振动。其第二共振峰在普通话单元音中最高。",
            "acousticRefs": [
                {"name": "F1（第一共振峰）", "value": "约 250–350 Hz", "note": "舌位越高 F1 越低，因人而异"},
                {"name": "F2（第二共振峰）", "value": "约 2100–2600 Hz", "note": "前元音 F2 高，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：一",
            "evaluationText": "一",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "final", "formants"],
            "reliabilityNote": "本关以舌位唇形要点与共振峰参考为主，评分和曲线供学习参考，数值因人而异。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与舌位没抬高、嘴角没咧开有关。", "cue": "先咧嘴抬舌摆好口型，再发出细亮的 i。", "practiceStepId": "L04-P1"},
                {"tag": "final_error", "phenomenon": "本次韵母听起来跑到了相近的音上，比如 i 读起来更像 ü 或 e。", "possibleCause": "可能与嘴唇撮圆、舌位下沉有关。", "cue": "嘴角向两边咧开，舌前部再抬高一点。", "practiceStepId": "L04-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“一”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音不稳、读得太快有关。", "cue": "轻轻起音，音高保持平直。", "practiceStepId": "L04-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“一”读满 2 秒再停。", "practiceStepId": "L04-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L04-P2"},
                {"tag": "formant_deviation", "phenomenon": "本次 i 的共振峰位置偏离常见参考区，舌位或唇形与参考不同。", "possibleCause": "可能与舌位偏低、唇形不扁有关。", "cue": "舌面再拱高一点，声音会更细更亮。", "practiceStepId": "L04-P1"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L05",
        "order": 5,
        "layer": "vowel",
        "type": "单韵母",
        "targetSound": "u",
        "pinyin": "u",
        "representativeChar": "乌",
        "title": "单韵母 u · 撮圆嘴唇往后缩",
        "oneLiner": "嘴唇撮成小圆孔、舌头往后缩，发出低沉的 u。",
        "goal": "学会双唇收圆前突、舌位后高地发 u，并区分 u 和 ü、o。",
        "applicableIssues": "适合 u、ü 不分，或 u 读得像 o 的学习者。",
        "tags": ["圆唇", "后舌位", "高舌位"],
        "skeletonPublic": True,
        "confusables": ["L06"],
        "articulation": {
            "description": "发 u 时，嘴唇向前突出，撮成一个留有小孔的圆圈；舌头整体往后上方缩，嘴巴开口很小。声音低而浑圆，像小火车“呜呜”叫。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "圆唇后舌发 u（可延长）",
                    "holdMs": 700,
                    "jaw": 0.1,
                    "lips": {"aperture": 0.15, "rounding": 1.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.95, "backness": 0.95, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L05_demo_normal_male", "speed": "normal", "voice": "male", "text": "乌"},
            {"ref": "L05_demo_normal_female", "speed": "normal", "voice": "female", "text": "乌"},
        ],
        "quizzes": [
            {
                "id": "L05-Q1",
                "prompt": "听一听，这是哪个单韵母？",
                "options": [{"text": "u"}, {"text": "o"}],
                "answerIndex": 0,
                "stimulusRef": "L05_quiz_Q1",
                "stimulusText": "u",
                "explanation": "口型又小又圆、声音低沉的是 u；嘴巴半开的是 o。",
            },
            {
                "id": "L05-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "乌 wū"}, {"text": "窝 wō"}],
                "answerIndex": 0,
                "stimulusRef": "L05_quiz_Q2",
                "stimulusText": "乌 wū",
                "explanation": "口型更小更圆、声音更低的是“乌”；嘴巴半开的是“窝”。",
            },
        ],
        "practice": [
            {"id": "L05-P1", "title": "小火车呜呜", "instruction": "撮圆嘴唇发 u，像火车鸣笛一样每次拉长 3 秒。", "repeat": 6, "durationSec": None, "bodyCue": "嘴唇前突有收紧感，脸颊轻微内收。", "stopNote": "不舒服就停止"},
            {"id": "L05-P2", "title": "u 长音", "instruction": "保持圆口型发 u 拉长到 5 秒左右，圆孔不许变大。", "repeat": None, "durationSec": 30, "bodyCue": "气流从圆孔匀匀吹出，喉咙放松。", "stopNote": "不舒服就停止"},
            {"id": "L05-P3", "title": "u/ü 舌位切换", "instruction": "嘴唇保持圆，舌头从后滑到前，u 变成 ü 再变回来，来回 6 次。", "repeat": 6, "durationSec": None, "bodyCue": "嘴唇不动，舌头在口腔里前后移动。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "u 听起来像 e 或 o，通常是嘴唇没撮圆。", "fix": "可以先做吹蜡烛的口型再发音，保持小圆孔。"},
            {"phenomenon": "u、ü 混着用，“乌”“迂”听起来一样。", "fix": "可以记住口诀：圆唇加舌头靠后是 u，圆唇加舌头靠前是 ü。"},
        ],
        "professional": {
            "description": "u 是后高圆唇元音 [u]，舌面后部抬至最高，双唇撮圆前突，开口度最小，软腭抬起，声带振动，第一、第二共振峰都低。",
            "acousticRefs": [
                {"name": "F1（第一共振峰）", "value": "约 250–400 Hz", "note": "高舌位对应低 F1，因人而异"},
                {"name": "F2（第二共振峰）", "value": "约 600–850 Hz", "note": "圆唇与后位共同压低 F2，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：乌",
            "evaluationText": "乌",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "final", "formants"],
            "reliabilityNote": "本关以唇形舌位要点与共振峰参考为主，评分和曲线供学习参考，数值因人而异。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与圆唇不够、舌位没后缩有关。", "cue": "先撮圆嘴唇再发音，声音要低而圆。", "practiceStepId": "L05-P1"},
                {"tag": "final_error", "phenomenon": "本次韵母听起来跑到了相近的音上，比如 u 读起来更像 o 或 ü。", "possibleCause": "可能与开口偏大、舌位偏前有关。", "cue": "圆孔再收小一点，舌头向后缩一点。", "practiceStepId": "L05-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“乌”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音太重、音高没站稳有关。", "cue": "轻轻起音，像平稳的一条线读到底。", "practiceStepId": "L05-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“乌”读满 2 秒再停。", "practiceStepId": "L05-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完保持口型安静 1 秒。", "practiceStepId": "L05-P2"},
                {"tag": "formant_deviation", "phenomenon": "本次 u 的共振峰位置偏离常见参考区，唇形或舌位与参考不同。", "possibleCause": "可能与圆唇度不足、舌位偏前有关。", "cue": "嘴唇撮得更圆更小，声音会更低沉。", "practiceStepId": "L05-P1"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L06",
        "order": 6,
        "layer": "vowel",
        "type": "单韵母",
        "targetSound": "ü",
        "pinyin": "ü",
        "representativeChar": "迂",
        "title": "单韵母 ü · i 的舌头 u 的嘴",
        "oneLiner": "舌头像发 i 一样在前抬起，嘴唇像 u 一样撮圆，就是 ü。",
        "goal": "学会“i 的舌头 + u 的嘴唇”组合出 ü，并稳定区分 u 和 ü。",
        "applicableIssues": "适合 ü 读成 u 或 i、ü 不分的学习者。",
        "tags": ["圆唇", "前舌位", "撮口"],
        "skeletonPublic": True,
        "confusables": ["L04", "L05"],
        "articulation": {
            "description": "发 ü 时，先把嘴咧开发个 i，舌头保持不动；再把嘴唇慢慢撮圆，声音就变成了 ü。舌头在前、嘴唇是圆的，这就是 ü 的诀窍，就像说“鱼”时开头的音。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "撮唇前舌发 ü（可延长）",
                    "holdMs": 700,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.15, "rounding": 0.9, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.9, "backness": 0.1, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L06_demo_normal_male", "speed": "normal", "voice": "male", "text": "迂"},
            {"ref": "L06_demo_normal_female", "speed": "normal", "voice": "female", "text": "迂"},
        ],
        "quizzes": [
            {
                "id": "L06-Q1",
                "prompt": "听一听，这是哪个单韵母？",
                "options": [{"text": "u"}, {"text": "ü"}],
                "answerIndex": 1,
                "stimulusRef": "L06_quiz_Q1",
                "stimulusText": "ü",
                "explanation": "舌位在前、声音更细的是 ü；舌位在后、声音更低的是 u。",
            },
            {
                "id": "L06-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "鱼 yú"}, {"text": "五 wǔ"}],
                "answerIndex": 0,
                "stimulusRef": "L06_quiz_Q2",
                "stimulusText": "鱼 yú",
                "explanation": "两个字嘴唇都圆，但“鱼”的舌头靠前、声音更细亮，“五”的舌头靠后、声音更低沉。",
            },
        ],
        "practice": [
            {"id": "L06-P1", "title": "i 变 ü 魔法", "instruction": "持续发 i，保持舌头不动，嘴唇慢慢由咧变圆，听声音变成 ü 再变回 i。", "repeat": 6, "durationSec": None, "bodyCue": "舌头稳住不动，只动嘴唇。", "stopNote": "不舒服就停止"},
            {"id": "L06-P2", "title": "ü 长音", "instruction": "撮口发 ü 并拉长到 5 秒左右，圆孔保持小而稳。", "repeat": None, "durationSec": 30, "bodyCue": "两颊微收，嘴唇圆圆地拢住。", "stopNote": "不舒服就停止"},
            {"id": "L06-P3", "title": "u/ü 来回切换", "instruction": "嘴唇保持圆，舌头前后移动，u、ü 交替各 3 秒，来回 6 次。", "repeat": 6, "durationSec": None, "bodyCue": "口腔后部与前部交替松紧，嘴唇始终圆着。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "ü 读成了 i，通常是嘴唇忘了撮圆。", "fix": "可以用手指轻轻捏一下两颊，帮嘴唇收圆，习惯后再放开。"},
            {"phenomenon": "ü 读成了 u，通常是舌头后缩了。", "fix": "可以先发 i 把舌位定好，不动舌头，再把嘴唇撮圆。"},
        ],
        "professional": {
            "description": "ü 是前高圆唇元音 [y]，舌位与 i 相同，唇形与 u 相似，软腭抬起，声带振动。普通话里 ü 只出现在 j、q、x、n、l 和 y 开头的音节里。",
            "acousticRefs": [
                {"name": "F1（第一共振峰）", "value": "约 250–350 Hz", "note": "高舌位对应低 F1，因人而异"},
                {"name": "F2（第二共振峰）", "value": "约 1700–2100 Hz", "note": "圆唇使 F2 略低于 i，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：迂",
            "evaluationText": "迂",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "final", "formants"],
            "reliabilityNote": "本关以唇形舌位要点与共振峰参考为主，评分和曲线供学习参考，数值因人而异。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与圆唇和前舌没有同时做够有关。", "cue": "先咧嘴定舌位，再撮圆嘴唇发出 ü。", "practiceStepId": "L06-P1"},
                {"tag": "final_error", "phenomenon": "本次韵母听起来跑到了相近的音上，比如 ü 读起来更像 u 或 i。", "possibleCause": "可能与舌位后缩或嘴唇没圆有关。", "cue": "舌头保持在前，嘴唇撮圆，两件事同时做。", "practiceStepId": "L06-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“迂”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音不稳、口型变化牵动音高有关。", "cue": "口型定好再出声，音高平稳到底。", "practiceStepId": "L06-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足、口型没准备好有关。", "cue": "先摆好撮口，吸口气把“迂”读满 2 秒。", "practiceStepId": "L06-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L06-P2"},
                {"tag": "formant_deviation", "phenomenon": "本次 ü 的共振峰位置偏离常见参考区，舌位或唇形与参考不同。", "possibleCause": "可能与舌位偏后、圆唇不足有关。", "cue": "用“先 i 后圆唇”的顺序再做一次。", "practiceStepId": "L06-P1"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L07",
        "order": 7,
        "layer": "initial",
        "type": "声母",
        "targetSound": "b",
        "pinyin": "b",
        "representativeChar": "波",
        "title": "声母 b · 双唇一碰弹出来",
        "oneLiner": "两片嘴唇轻轻一碰再放开，憋住的气一下弹出 b。",
        "goal": "学会双唇闭合蓄气、快速打开发出不送气的 b，并听出 b 和 p 的送气区别。",
        "applicableIssues": "适合 b、p 不分，或 b 读得太响像 p 的学习者。",
        "tags": ["双唇", "不送气", "塞音"],
        "skeletonPublic": True,
        "confusables": ["L08"],
        "articulation": {
            "description": "先把上下嘴唇轻轻闭拢，挡住气流，同时喉咙里憋一小口气；然后嘴唇突然打开，气一下冲出来，就是 b。b 送出的气很少，手放在嘴前几乎感觉不到风。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "双唇闭合蓄气（成阻）",
                    "holdMs": 140,
                    "jaw": 0.05,
                    "lips": {"aperture": 0.0, "rounding": 0.0, "contact": "bilabial"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.4, "backness": 0.4, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "双唇打开除阻（不送气）",
                    "holdMs": 100,
                    "jaw": 0.4,
                    "lips": {"aperture": 0.5, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.4, "backness": 0.4, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "burst",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L07_demo_normal_male", "speed": "normal", "voice": "male", "text": "波"},
            {"ref": "L07_demo_normal_female", "speed": "normal", "voice": "female", "text": "波"},
        ],
        "quizzes": [
            {
                "id": "L07-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "波 bō"}, {"text": "坡 pō"}],
                "answerIndex": 0,
                "stimulusRef": "L07_quiz_Q1",
                "stimulusText": "波 bō",
                "explanation": "气流弱、几乎不带风的是“波”；像吹纸片一样送气的是“坡”。",
            },
            {
                "id": "L07-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "爸 bà"}, {"text": "怕 pà"}],
                "answerIndex": 0,
                "stimulusRef": "L07_quiz_Q2",
                "stimulusText": "爸 bà",
                "explanation": "把纸巾放在嘴前：读“爸”纸巾基本不动，读“怕”纸巾会飘。刚才气流很弱，是“爸”。",
            },
        ],
        "practice": [
            {"id": "L07-P1", "title": "纸巾测气流", "instruction": "把纸巾举在嘴前约 5 厘米，读“波”，目标是纸巾基本不动。", "repeat": 5, "durationSec": None, "bodyCue": "嘴唇轻碰即开，只用一点点气流。", "stopNote": "不舒服就停止"},
            {"id": "L07-P2", "title": "闭唇蓄气再弹发", "instruction": "双唇轻闭憋气 1 秒，突然打开读“波”，体会先挡后放。", "repeat": 6, "durationSec": None, "bodyCue": "闭唇时嘴里有股气被轻轻挡住的感觉。", "stopNote": "不舒服就停止"},
            {"id": "L07-P3", "title": "波/坡最小对比", "instruction": "“波—坡”交替读 8 组，用手背感受气流的弱与强。", "repeat": 8, "durationSec": None, "bodyCue": "读“坡”时手背有风，读“波”时几乎没风。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "b 读起来像 p，除阻后跟了一股明显的气。", "fix": "可以把纸巾放在嘴前练“读‘波’纸巾不动”，慢慢把气流收小。"},
            {"phenomenon": "b 结尾带了一点“嗯”的鼻音，听起来混进了 m。", "fix": "闭唇时想象气只能从嘴出、鼻子不哼气，除阻要干脆。"},
        ],
        "professional": {
            "description": "b 是双唇不送气清塞音 [p]，成阻于双唇，成阻期软腭抬起关闭鼻腔通道，除阻瞬间爆破，声带不振动，嗓音起始时间（VOT）很短。",
            "acousticRefs": [
                {"name": "VOT（除阻到声带起振）", "value": "约 5–20 ms", "note": "不送气塞音 VOT 很短，因人而异"},
                {"name": "成阻段时长", "value": "约 50–120 ms", "note": "受语速影响大，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：波",
            "evaluationText": "波",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以听感对比与气流提示为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与双唇动作没做足、气流没收住有关。", "cue": "先闭唇蓄气，再干脆地弹开发“波”。", "practiceStepId": "L07-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 p，除阻后跟了一股明显的送气。", "possibleCause": "可能与送气习惯过强、气流没收住有关。", "cue": "纸巾放嘴前，读“波”时让它几乎不动。", "practiceStepId": "L07-P1"},
                {"tag": "final_error", "phenomenon": "本次“波”的韵母听起来跑到了相近的音上，比如 o 读成 e。", "possibleCause": "可能与嘴唇没收圆有关。", "cue": "弹开嘴唇后马上拢圆，把 o 读完整。", "practiceStepId": "L07-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“波”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音太冲、音高没站稳有关。", "cue": "轻轻起音，音高平稳地拖到底。", "practiceStepId": "L07-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足、动作没做完有关。", "cue": "吸口气，把“波”完整读完再停。", "practiceStepId": "L07-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L07-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L08",
        "order": 8,
        "layer": "initial",
        "type": "声母",
        "targetSound": "p",
        "pinyin": "p",
        "representativeChar": "坡",
        "title": "声母 p · 双唇一碰吹口气",
        "oneLiner": "双唇一碰再放开，跟着送出一股明显的气，就是 p。",
        "goal": "学会双唇闭合后送气除阻，发出气流充足的 p，并听出 p 和 b 的区别。",
        "applicableIssues": "适合 b、p 不分，或 p 读得像 b（送气不足）的学习者。",
        "tags": ["双唇", "送气", "塞音"],
        "skeletonPublic": True,
        "confusables": ["L07"],
        "articulation": {
            "description": "动作的前半段和 b 一样：双唇闭拢，把气挡住。不同的是松开时要用力送气，像吹掉纸上的灰尘，跟出来一股明显的风。手背放在嘴前能明显感到气流。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "双唇闭合蓄气（成阻）",
                    "holdMs": 140,
                    "jaw": 0.05,
                    "lips": {"aperture": 0.0, "rounding": 0.0, "contact": "bilabial"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.4, "backness": 0.4, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "双唇打开送气除阻",
                    "holdMs": 180,
                    "jaw": 0.45,
                    "lips": {"aperture": 0.6, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.4, "backness": 0.4, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "aspirated_burst",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L08_demo_normal_male", "speed": "normal", "voice": "male", "text": "坡"},
            {"ref": "L08_demo_normal_female", "speed": "normal", "voice": "female", "text": "坡"},
        ],
        "quizzes": [
            {
                "id": "L08-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "坡 pō"}, {"text": "波 bō"}],
                "answerIndex": 0,
                "stimulusRef": "L08_quiz_Q1",
                "stimulusText": "坡 pō",
                "explanation": "松开嘴唇时送出一股明显气流的是“坡”；几乎不带风的是“波”。",
            },
            {
                "id": "L08-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "怕 pà"}, {"text": "爸 bà"}],
                "answerIndex": 0,
                "stimulusRef": "L08_quiz_Q2",
                "stimulusText": "怕 pà",
                "explanation": "“怕”像轻轻吹蜡烛，除阻后有明显的送气；“爸”干脆无风。",
            },
        ],
        "practice": [
            {"id": "L08-P1", "title": "纸巾飘起来", "instruction": "把纸巾举在嘴前约 5 厘米，读“坡”，目标是纸巾明显飘动。", "repeat": 5, "durationSec": None, "bodyCue": "弹开嘴唇时送出一股风，小腹轻轻用力。", "stopNote": "不舒服就停止"},
            {"id": "L08-P2", "title": "蓄足气弹发", "instruction": "双唇闭拢憋足气，打开时干脆送气读“坡”。", "repeat": 6, "durationSec": None, "bodyCue": "气流在嘴唇打开的一瞬间冲出。", "stopNote": "不舒服就停止"},
            {"id": "L08-P3", "title": "坡/波最小对比", "instruction": "“坡—波”交替读 8 组，用手背区分有风与无风。", "repeat": 8, "durationSec": None, "bodyCue": "读“坡”手背感到一阵风，读“波”没有。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "p 读起来像 b，风送不出来。", "fix": "可以先用“吹灰尘”的动作找气流，再把声音接上。"},
            {"phenomenon": "送气拖得太长，听起来像先吹气再说话。", "fix": "气流短促一点，一闪而过就进入后面的韵母。"},
        ],
        "professional": {
            "description": "p 是双唇送气清塞音 [pʰ]，成阻同 b，除阻后有明显送气段，声带在送气段之后才起振，VOT 显著长于 b。",
            "acousticRefs": [
                {"name": "VOT（送气段）", "value": "约 60–110 ms", "note": "送气段明显长于不送气 b，因人而异"},
                {"name": "送气摩擦时长", "value": "约 60–100 ms", "note": "语速越快越短，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：坡",
            "evaluationText": "坡",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以听感对比与气流提示为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与送气不足、双唇动作幅度小有关。", "cue": "闭唇憋气，打开时干脆送一口风。", "practiceStepId": "L08-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 b，除阻后没有明显的送气。", "possibleCause": "可能与气流没送出来、动作太轻有关。", "cue": "手背放嘴前，读“坡”时要能感到风。", "practiceStepId": "L08-P1"},
                {"tag": "final_error", "phenomenon": "本次“坡”的韵母听起来跑到了相近的音上，比如 o 读成 e。", "possibleCause": "可能与嘴唇没收圆有关。", "cue": "送气之后马上把嘴唇拢圆读 o。", "practiceStepId": "L08-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“坡”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与送气用力过猛牵动音高有关。", "cue": "风归风、调归调，音高保持平稳。", "practiceStepId": "L08-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“坡”完整读完再停。", "practiceStepId": "L08-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L08-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L09",
        "order": 9,
        "layer": "initial",
        "type": "声母",
        "targetSound": "m",
        "pinyin": "m",
        "representativeChar": "摸",
        "title": "声母 m · 闭嘴哼鸣",
        "oneLiner": "闭上嘴、气从鼻子走，哼出来的就是 m。",
        "goal": "学会双唇闭合、气流改走鼻腔发出 m，体会“嘴闭着也能响”。",
        "applicableIssues": "适合 m 读成 b（忘了走鼻子）的学习者。",
        "tags": ["鼻音", "双唇", "浊音"],
        "skeletonPublic": True,
        "confusables": ["L30"],
        "articulation": {
            "description": "把上下嘴唇闭拢，喉咙后部的小门（软腭）放下来，让气从鼻子里出来，同时嗓子发声，就哼出了 m。嘴一直闭着，声音却嗡嗡响，鼻翼会有轻微震动。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "闭唇鼻音 m（可延长）",
                    "holdMs": 500,
                    "jaw": 0.05,
                    "lips": {"aperture": 0.0, "rounding": 0.0, "contact": "bilabial"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.35, "backness": 0.4, "stricture": "open"},
                    "velum": "lowered",
                    "airflow": "nasal",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L09_demo_normal_male", "speed": "normal", "voice": "male", "text": "摸"},
            {"ref": "L09_demo_normal_female", "speed": "normal", "voice": "female", "text": "摸"},
        ],
        "quizzes": [
            {
                "id": "L09-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "妈 mā"}, {"text": "爸 bà"}],
                "answerIndex": 0,
                "stimulusRef": "L09_quiz_Q1",
                "stimulusText": "妈 mā",
                "explanation": "开头闭嘴、从鼻子起音的是“妈”；嘴唇一碰就弹开的是“爸”。",
            },
            {
                "id": "L09-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "摸 mō"}, {"text": "波 bō"}],
                "answerIndex": 0,
                "stimulusRef": "L09_quiz_Q2",
                "stimulusText": "摸 mō",
                "explanation": "开头能听到“嗡”的鼻音是“摸”；没有鼻音、气流直接弹出的是“波”。",
            },
        ],
        "practice": [
            {"id": "L09-P1", "title": "哼鸣找鼻音", "instruction": "闭上嘴哼一个舒服的音，手指轻放在鼻翼两侧感受震动，再张开嘴收音。", "repeat": 5, "durationSec": None, "bodyCue": "鼻翼甚至眉心有麻麻的震动感。", "stopNote": "不舒服就停止"},
            {"id": "L09-P2", "title": "m 延长再张嘴", "instruction": "闭唇把 m 哼长 4 秒，再张嘴收住，中间不打断。", "repeat": None, "durationSec": 30, "bodyCue": "嘴巴一直闭着，气从鼻子匀匀外出。", "stopNote": "不舒服就停止"},
            {"id": "L09-P3", "title": "m/b 对比", "instruction": "“妈—爸”交替读 8 组，体会鼻子走气与弹开的区别。", "repeat": 8, "durationSec": None, "bodyCue": "读“妈”时鼻子出气，读“爸”时嘴前有小小的气流。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "m 开头没有鼻音，听起来像 b。", "fix": "可以先闭嘴哼一声“嗯——”，再直接张嘴接上韵母。"},
            {"phenomenon": "m 哼得太长，整个字被拖得含糊。", "fix": "鼻音只占开头一小段，很快就把嘴张开进入后面的音。"},
        ],
        "professional": {
            "description": "m 是双唇浊鼻音 [m]，双唇成阻，软腭下降打开鼻腔通道，气流全部经鼻腔流出，声带振动，可以任意延长。",
            "acousticRefs": [
                {"name": "鼻音段时长", "value": "约 100–250 ms", "note": "随语速和语境变化，因人而异"},
                {"name": "鼻音低频共振区", "value": "约 250–500 Hz 能量集中", "note": "鼻腔共振使低频突出，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：摸",
            "evaluationText": "摸",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以鼻音震动感与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与鼻音太短、张嘴太快有关。", "cue": "闭嘴哼半拍，再张嘴读“摸”。", "practiceStepId": "L09-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 b，开头的鼻音不明显。", "possibleCause": "可能与软腭没放下来、气没走鼻子有关。", "cue": "先哼一声“嗯”，找到鼻翼震动再张嘴。", "practiceStepId": "L09-P1"},
                {"tag": "final_error", "phenomenon": "本次“摸”的韵母听起来跑到了相近的音上，比如 o 读成 e。", "possibleCause": "可能与张嘴后嘴唇没收圆有关。", "cue": "嘴一张开就拢圆，把 o 读完整。", "practiceStepId": "L09-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“摸”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与哼鸣起音不稳有关。", "cue": "哼鸣时音高就站好，张嘴后保持不变。", "practiceStepId": "L09-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停下有关。", "cue": "闭嘴哼鸣到张嘴收音，一口气完成。", "practiceStepId": "L09-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L09-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L10",
        "order": 10,
        "layer": "initial",
        "type": "声母",
        "targetSound": "f",
        "pinyin": "f",
        "representativeChar": "佛",
        "title": "声母 f · 上牙轻碰下唇",
        "oneLiner": "上牙轻搭下唇，气流从缝里挤出去，吹出 f。",
        "goal": "学会唇齿轻接触、窄缝摩擦发出清晰的 f。",
        "applicableIssues": "适合 f、h 不分（把“飞机”说成“灰机”）的学习者。",
        "tags": ["唇齿音", "擦音", "送气摩擦"],
        "skeletonPublic": True,
        "confusables": ["L17"],
        "articulation": {
            "description": "把上牙齿轻轻搭在下嘴唇的内侧边缘，留一条细缝；气从这条缝里挤出去，发出“夫——”一样的摩擦声。接触要轻，用力咬死声音反而不出来。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "唇齿缝隙摩擦 f（可延长）",
                    "holdMs": 450,
                    "jaw": 0.25,
                    "lips": {"aperture": 0.2, "rounding": 0.0, "contact": "labiodental"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.35, "backness": 0.4, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "friction",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L10_demo_normal_male", "speed": "normal", "voice": "male", "text": "佛"},
            {"ref": "L10_demo_normal_female", "speed": "normal", "voice": "female", "text": "佛"},
        ],
        "quizzes": [
            {
                "id": "L10-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "发 fā"}, {"text": "花 huā"}],
                "answerIndex": 0,
                "stimulusRef": "L10_quiz_Q1",
                "stimulusText": "发 fā",
                "explanation": "上牙碰下唇、有“夫”的摩擦声是“发”；从喉咙里呵气出来的是“花”。",
            },
            {
                "id": "L10-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "飞 fēi"}, {"text": "灰 huī"}],
                "answerIndex": 0,
                "stimulusRef": "L10_quiz_Q2",
                "stimulusText": "飞 fēi",
                "explanation": "想象飞机起飞：“飞”开头有牙齿和嘴唇的细细摩擦，“灰”是喉咙呵出的宽气。",
            },
        ],
        "practice": [
            {"id": "L10-P1", "title": "找缝隙", "instruction": "上齿轻搭下唇，先只吹气不出声，听到“夫夫”风声后再加声音读“佛”。", "repeat": 6, "durationSec": None, "bodyCue": "下唇有轻轻发痒的感觉，气流细细一条。", "stopNote": "不舒服就停止"},
            {"id": "L10-P2", "title": "f 长摩擦", "instruction": "保持唇齿缝发 f 的摩擦音，匀匀拉长 4 秒。", "repeat": None, "durationSec": 30, "bodyCue": "缝的位置不动，风声稳定不忽大忽小。", "stopNote": "不舒服就停止"},
            {"id": "L10-P3", "title": "飞/灰对比", "instruction": "“飞—灰”交替读 8 组，手背放在嘴前感受 f 的细风。", "repeat": 8, "durationSec": None, "bodyCue": "f 的气流细而凉，h 的气流宽而暖。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "f 读成了 h，像从喉咙呵气。", "fix": "可以照镜子看上牙有没有碰到下唇，轻碰一下再发音。"},
            {"phenomenon": "咬唇太用力，摩擦声发闷。", "fix": "上齿只是轻轻搭在下唇边上，留缝才能擦出声音。"},
        ],
        "professional": {
            "description": "f 是唇齿清擦音 [f]，下唇与上齿构成窄缝，气流通过缝隙产生湍流摩擦，声带不振动，软腭抬起关闭鼻腔。",
            "acousticRefs": [
                {"name": "摩擦段时长", "value": "约 80–200 ms", "note": "随语速变化，因人而异"},
                {"name": "摩擦噪声频带", "value": "约 1000–8000 Hz 宽带分布", "note": "能量较弱、频谱分散，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：佛",
            "evaluationText": "佛",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以唇齿接触与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与唇齿接触位置不稳、摩擦不匀有关。", "cue": "上齿轻搭下唇，匀匀擦出“夫”再读字。", "practiceStepId": "L10-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 h，缺少唇齿摩擦。", "possibleCause": "可能与上齿没碰到下唇、气流从喉咙出来有关。", "cue": "照镜子确认上牙搭在下唇上再发音。", "practiceStepId": "L10-P1"},
                {"tag": "final_error", "phenomenon": "本次“佛”的韵母听起来跑到了相近的音上，比如 o 读成 e。", "possibleCause": "可能与嘴唇没收圆有关。", "cue": "摩擦结束后马上把嘴唇拢圆读 o。", "practiceStepId": "L10-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“佛”的二声不够一致，音高走向出现偏差。", "possibleCause": "可能与只顾摩擦、忘了声调上扬有关。", "cue": "擦出 f 的同时想着声调往上抬。", "practiceStepId": "L10-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“佛”完整读完再停。", "practiceStepId": "L10-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L10-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L11",
        "order": 11,
        "layer": "initial",
        "type": "声母",
        "targetSound": "d",
        "pinyin": "d",
        "representativeChar": "得",
        "title": "声母 d · 舌尖一弹",
        "oneLiner": "舌尖顶住上牙床，一弹发出干脆的 d。",
        "goal": "学会舌尖抵上齿龈、快速除阻发出不送气的 d，并听出 d 和 t 的区别。",
        "applicableIssues": "适合 d、t 不分，或 d 送气过重的学习者。",
        "tags": ["舌尖", "不送气", "塞音"],
        "skeletonPublic": True,
        "confusables": ["L12"],
        "articulation": {
            "description": "舌尖抵住上牙后面隆起的牙床，把气挡住；憋一小口气后舌尖猛然弹开，气冲出来就是 d。d 的气流很弱，干脆利落，像用指尖轻敲一下门。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖抵齿龈蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.2,
                    "lips": {"aperture": 0.35, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "alveolar", "stricture": "closure"},
                    "tongueBody": {"height": 0.45, "backness": 0.45, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "舌尖弹开除阻（不送气）",
                    "holdMs": 90,
                    "jaw": 0.45,
                    "lips": {"aperture": 0.5, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "alveolar", "stricture": "open"},
                    "tongueBody": {"height": 0.45, "backness": 0.45, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "burst",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L11_demo_normal_male", "speed": "normal", "voice": "male", "text": "得"},
            {"ref": "L11_demo_normal_female", "speed": "normal", "voice": "female", "text": "得"},
        ],
        "quizzes": [
            {
                "id": "L11-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "低 dī"}, {"text": "踢 tī"}],
                "answerIndex": 0,
                "stimulusRef": "L11_quiz_Q1",
                "stimulusText": "低 dī",
                "explanation": "气流弱、轻巧干脆的是“低”；跟着一股明显气流的是“踢”。",
            },
            {
                "id": "L11-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "兜 dōu"}, {"text": "偷 tōu"}],
                "answerIndex": 0,
                "stimulusRef": "L11_quiz_Q2",
                "stimulusText": "兜 dōu",
                "explanation": "“兜”轻巧不送气；“偷”像偷着吹一口气，送气明显。",
            },
        ],
        "practice": [
            {"id": "L11-P1", "title": "敲门式弹发", "instruction": "舌尖抵上牙床，弹开发“得”，像轻敲门一样干脆。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖轻触即离，动作小而快。", "stopNote": "不舒服就停止"},
            {"id": "L11-P2", "title": "舌尖定位", "instruction": "舌尖抵住上牙床数 2 秒再弹发，确保接触点不后缩。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖的接触点在上牙后方的牙龈丘上。", "stopNote": "不舒服就停止"},
            {"id": "L11-P3", "title": "兜/偷最小对比", "instruction": "“兜—偷”交替读 8 组，用纸巾感受有无气流。", "repeat": 8, "durationSec": None, "bodyCue": "读“兜”纸巾不动，读“偷”纸巾微动。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "d 读起来像 t，弹开时跟了一股气。", "fix": "可以放纸巾在嘴前，练“读‘兜’纸巾不动”。"},
            {"phenomenon": "舌尖位置太靠后，d 听起来像 g。", "fix": "可以先用舌尖舔一下上牙再往后挪一点点，就是正确位置。"},
        ],
        "professional": {
            "description": "d 是舌尖中不送气清塞音 [t]，舌尖抵上齿龈成阻，成阻期软腭抬起，除阻爆破，声带不振动，VOT 很短。",
            "acousticRefs": [
                {"name": "VOT（除阻到声带起振）", "value": "约 5–20 ms", "note": "不送气塞音 VOT 很短，因人而异"},
                {"name": "成阻段时长", "value": "约 40–100 ms", "note": "受语速影响大，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：得",
            "evaluationText": "得",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以舌尖定位与气流对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与舌尖位置不准、弹发不干脆有关。", "cue": "舌尖抵上牙床，轻快地弹开发“得”。", "practiceStepId": "L11-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 t，除阻后带了送气。", "possibleCause": "可能与气流没收住、弹开太用力有关。", "cue": "纸巾放嘴前，读“得”时让它基本不动。", "practiceStepId": "L11-P1"},
                {"tag": "final_error", "phenomenon": "本次“得”的韵母听起来跑到了相近的音上，比如 e 读得太开。", "possibleCause": "可能与弹开后口型没收住有关。", "cue": "弹开后嘴巴放松半开，e 轻轻带出。", "practiceStepId": "L11-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“得”的二声不够一致，音高走向出现偏差。", "possibleCause": "可能与弹发用力牵动音高有关。", "cue": "动作轻一点，声调想着往上抬。", "practiceStepId": "L11-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“得”完整读完再停。", "practiceStepId": "L11-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L11-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L12",
        "order": 12,
        "layer": "initial",
        "type": "声母",
        "targetSound": "t",
        "pinyin": "t",
        "representativeChar": "特",
        "title": "声母 t · 舌尖一弹送口气",
        "oneLiner": "舌尖顶住上牙床，弹开时送出一口气，就是 t。",
        "goal": "学会舌尖抵上齿龈、送气除阻发出 t，并听出 t 和 d 的区别。",
        "applicableIssues": "适合 d、t 不分，或 t 读得像 d（送气不足）的学习者。",
        "tags": ["舌尖", "送气", "塞音"],
        "skeletonPublic": True,
        "confusables": ["L11"],
        "articulation": {
            "description": "前半段和 d 一样：舌尖抵住上牙后面的牙床，把气挡住。不同的是弹开时要用劲送气，像轻轻吹灭生日蜡烛，跟出一股明显的风。手背能清楚感到气流。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖抵齿龈蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.2,
                    "lips": {"aperture": 0.35, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "alveolar", "stricture": "closure"},
                    "tongueBody": {"height": 0.45, "backness": 0.45, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "舌尖弹开送气除阻",
                    "holdMs": 170,
                    "jaw": 0.5,
                    "lips": {"aperture": 0.55, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "alveolar", "stricture": "open"},
                    "tongueBody": {"height": 0.45, "backness": 0.45, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "aspirated_burst",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L12_demo_normal_male", "speed": "normal", "voice": "male", "text": "特"},
            {"ref": "L12_demo_normal_female", "speed": "normal", "voice": "female", "text": "特"},
        ],
        "quizzes": [
            {
                "id": "L12-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "踢 tī"}, {"text": "低 dī"}],
                "answerIndex": 0,
                "stimulusRef": "L12_quiz_Q1",
                "stimulusText": "踢 tī",
                "explanation": "弹开时送出一股明显气流的是“踢”；轻巧无风的是“低”。",
            },
            {
                "id": "L12-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "偷 tōu"}, {"text": "兜 dōu"}],
                "answerIndex": 0,
                "stimulusRef": "L12_quiz_Q2",
                "stimulusText": "偷 tōu",
                "explanation": "“偷”有一股送气跟着出来，“兜”没有。可以用纸巾验证：读“偷”纸巾会动。",
            },
        ],
        "practice": [
            {"id": "L12-P1", "title": "纸巾微动", "instruction": "把纸巾举在嘴前约 5 厘米，读“特”，目标是纸巾轻轻动一下。", "repeat": 5, "durationSec": None, "bodyCue": "舌尖弹开的同时送出一小股风。", "stopNote": "不舒服就停止"},
            {"id": "L12-P2", "title": "送气弹发", "instruction": "舌尖抵住上牙床憋气 1 秒，弹开时干脆送气读“特”。", "repeat": 6, "durationSec": None, "bodyCue": "气流集中在弹开的一瞬间。", "stopNote": "不舒服就停止"},
            {"id": "L12-P3", "title": "踢/低最小对比", "instruction": "“踢—低”交替读 8 组，用手背感受有风与无风。", "repeat": 8, "durationSec": None, "bodyCue": "读“踢”有风感，读“低”几乎没有。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "t 读起来像 d，风送不出来。", "fix": "可以先用“吹蜡烛”的感觉把气送出去，再接上声音。"},
            {"phenomenon": "舌尖翘得太往后，t 听起来像 q。", "fix": "舌尖只抵上牙后面一点点的牙床，不要往后缩。"},
        ],
        "professional": {
            "description": "t 是舌尖中送气清塞音 [tʰ]，成阻同 d，除阻后有明显送气段，声带在送气段之后起振，VOT 显著长于 d。",
            "acousticRefs": [
                {"name": "VOT（送气段）", "value": "约 60–110 ms", "note": "送气段明显长于不送气 d，因人而异"},
                {"name": "送气摩擦时长", "value": "约 60–100 ms", "note": "随语速变化，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：特",
            "evaluationText": "特",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以舌尖定位与气流对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与送气不足、舌尖位置不准有关。", "cue": "舌尖抵住上牙床，弹开时送一口气。", "practiceStepId": "L12-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 d，缺少明显的送气。", "possibleCause": "可能与气流没送出、弹开太轻有关。", "cue": "手背放嘴前，读“特”时要感到风。", "practiceStepId": "L12-P1"},
                {"tag": "final_error", "phenomenon": "本次“特”的韵母听起来跑到了相近的音上，比如 e 读得太开。", "possibleCause": "可能与送气后口型没收住有关。", "cue": "送气后嘴巴半开放松，e 轻轻收尾。", "practiceStepId": "L12-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“特”的四声不够一致，音高走向出现偏差。", "possibleCause": "可能与送气用力、声调没降下去有关。", "cue": "风送出去后，声调干脆地从高落到低。", "practiceStepId": "L12-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“特”完整读完再停。", "practiceStepId": "L12-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L12-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L13",
        "order": 13,
        "layer": "initial",
        "type": "声母",
        "targetSound": "n",
        "pinyin": "n",
        "representativeChar": "讷",
        "title": "声母 n · 舌尖顶牙床走鼻子",
        "oneLiner": "舌尖顶住上牙床，气从鼻子出来，就是 n。",
        "goal": "学会舌尖抵上齿龈、气流走鼻腔发出 n，并和 l 区分。",
        "applicableIssues": "适合 n、l 不分（“男”“兰”不分）的学习者。",
        "tags": ["鼻音", "舌尖", "浊音"],
        "skeletonPublic": True,
        "confusables": ["L14"],
        "articulation": {
            "description": "舌尖抵住上牙后面的牙床，嘴巴微微张开；软腭放下来，让气从鼻子里出来，同时嗓子发声，就得到 n。捏住鼻子就发不出 n，这是检验它的好办法。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖抵齿龈鼻音 n（可延长）",
                    "holdMs": 500,
                    "jaw": 0.3,
                    "lips": {"aperture": 0.35, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "alveolar", "stricture": "closure"},
                    "tongueBody": {"height": 0.45, "backness": 0.45, "stricture": "open"},
                    "velum": "lowered",
                    "airflow": "nasal",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L13_demo_normal_male", "speed": "normal", "voice": "male", "text": "讷"},
            {"ref": "L13_demo_normal_female", "speed": "normal", "voice": "female", "text": "讷"},
        ],
        "quizzes": [
            {
                "id": "L13-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "男 nán"}, {"text": "兰 lán"}],
                "answerIndex": 0,
                "stimulusRef": "L13_quiz_Q1",
                "stimulusText": "男 nán",
                "explanation": "开头从鼻子起音、带点“嗯”的是“男”；气流从舌头两边走、没鼻音的是“兰”。",
            },
            {
                "id": "L13-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "牛 niú"}, {"text": "流 liú"}],
                "answerIndex": 0,
                "stimulusRef": "L13_quiz_Q2",
                "stimulusText": "牛 niú",
                "explanation": "捏住鼻子发不出的是“牛”，因为它的开头气走鼻腔。",
            },
        ],
        "practice": [
            {"id": "L13-P1", "title": "捏鼻检验", "instruction": "读“男”时捏一下鼻子：如果发不出来，说明气走对了鼻腔。", "repeat": 5, "durationSec": None, "bodyCue": "鼻翼震动，舌尖一直贴住上牙床。", "stopNote": "不舒服就停止"},
            {"id": "L13-P2", "title": "n 延长哼鸣", "instruction": "舌尖抵住上牙床，把 n 哼长 4 秒再放开收音。", "repeat": None, "durationSec": 30, "bodyCue": "气从鼻子匀匀外出，嘴巴保持微张。", "stopNote": "不舒服就停止"},
            {"id": "L13-P3", "title": "n/l 对比", "instruction": "“男—兰”“牛—流”交替读 8 组，手指放鼻翼对比震动。", "repeat": 8, "durationSec": None, "bodyCue": "读 n 时鼻翼震，读 l 时鼻翼安静。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "n 读成了 l，鼻子没走气，字听起来发飘。", "fix": "可以先闭嘴哼“嗯”找到鼻音，再抬起舌尖接着发音。"},
            {"phenomenon": "n 和 l 有时换着用，自己也没察觉。", "fix": "可以用捏鼻法自检：捏住鼻子还能读出来的就是 l。"},
        ],
        "professional": {
            "description": "n 是舌尖中浊鼻音 [n]，舌尖抵上齿龈成阻，软腭下降打开鼻腔通道，气流经鼻腔流出，声带振动，可延长。与 l 的差别在气流通道：n 走鼻腔，l 走舌两侧。",
            "acousticRefs": [
                {"name": "鼻音段时长", "value": "约 100–250 ms", "note": "随语速和语境变化，因人而异"},
                {"name": "鼻音低频共振区", "value": "约 250–500 Hz 能量集中", "note": "鼻腔共振特征，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：讷",
            "evaluationText": "讷",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以鼻音震动与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与鼻音太短、舌尖位置不稳有关。", "cue": "舌尖贴住上牙床，鼻子哼出声再读字。", "practiceStepId": "L13-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 l，缺少鼻腔气流。", "possibleCause": "可能与软腭没放下、气从口出了有关。", "cue": "先哼“嗯”找到鼻音，再抬舌尖接韵母。", "practiceStepId": "L13-P1"},
                {"tag": "final_error", "phenomenon": "本次“讷”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与鼻音结束太晚、韵母没读完整有关。", "cue": "鼻音一小段就放开，把韵母读清楚。", "practiceStepId": "L13-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“讷”的四声不够一致，音高走向出现偏差。", "possibleCause": "可能与鼻音哼鸣牵动音高有关。", "cue": "哼鸣稳住音高，放开后干脆下降。", "practiceStepId": "L13-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "从鼻音到韵母一口气读完。", "practiceStepId": "L13-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L13-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L14",
        "order": 14,
        "layer": "initial",
        "type": "声母",
        "targetSound": "l",
        "pinyin": "l",
        "representativeChar": "勒",
        "title": "声母 l · 舌尖顶住气走两边",
        "oneLiner": "舌尖顶住上牙床，气从舌头两边溜出去，就是 l。",
        "goal": "学会舌尖抵上齿龈、气流从舌侧通过发出 l，并和 n 区分。",
        "applicableIssues": "适合 n、l 不分的学习者。",
        "tags": ["边音", "舌尖", "浊音"],
        "skeletonPublic": True,
        "confusables": ["L13"],
        "articulation": {
            "description": "舌尖轻轻顶住上牙后面的牙床，但这次气不走鼻子，而是从舌头的两边绕出去，同时嗓子出声，就是 l。读 l 时捏住鼻子照样能读，声音清亮、不嗡嗡。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖抵齿龈边音 l（可延长）",
                    "holdMs": 500,
                    "jaw": 0.3,
                    "lips": {"aperture": 0.35, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "alveolar", "stricture": "approximant"},
                    "tongueBody": {"height": 0.45, "backness": 0.45, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L14_demo_normal_male", "speed": "normal", "voice": "male", "text": "勒"},
            {"ref": "L14_demo_normal_female", "speed": "normal", "voice": "female", "text": "勒"},
        ],
        "quizzes": [
            {
                "id": "L14-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "兰 lán"}, {"text": "男 nán"}],
                "answerIndex": 0,
                "stimulusRef": "L14_quiz_Q1",
                "stimulusText": "兰 lán",
                "explanation": "气流从舌边走、声音清亮无鼻音的是“兰”；从鼻子起音的是“男”。",
            },
            {
                "id": "L14-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "梨 lí"}, {"text": "泥 ní"}],
                "answerIndex": 0,
                "stimulusRef": "L14_quiz_Q2",
                "stimulusText": "梨 lí",
                "explanation": "“梨”开头清亮、鼻翼不震；“泥”开头有“嗯”的鼻音。",
            },
        ],
        "practice": [
            {"id": "L14-P1", "title": "清亮 l", "instruction": "舌尖顶住上牙床读“勒”，保持声音清亮、不嗡嗡。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖贴住，舌两侧有气流通过的感觉。", "stopNote": "不舒服就停止"},
            {"id": "L14-P2", "title": "l 延长", "instruction": "舌尖保持接触，把 l 拉长 4 秒，鼻翼全程不震。", "repeat": None, "durationSec": 30, "bodyCue": "声音清亮稳定，气从口出来。", "stopNote": "不舒服就停止"},
            {"id": "L14-P3", "title": "n/l 捏鼻对比", "instruction": "捏住鼻子分别读“兰”和“男”，能顺利读出的是“兰”。", "repeat": 8, "durationSec": None, "bodyCue": "读 l 时鼻翼安静，读 n 时鼻翼发麻。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "l 读出来带鼻音，和 n 混在一起。", "fix": "可以捏住鼻子读 l，读得越顺说明气越没走鼻子。"},
            {"phenomenon": "舌尖没顶住牙床，l 听起来又软又糊。", "fix": "可以先把舌尖实实在在贴在上牙床上，再让气从两边出。"},
        ],
        "professional": {
            "description": "l 是舌尖中浊边音 [l]，舌尖抵上齿龈，气流沿舌体两侧流出，软腭抬起关闭鼻腔，声带振动，可延长。与 n 的对立在于软腭状态与气流通道。",
            "acousticRefs": [
                {"name": "边音段时长", "value": "约 80–200 ms", "note": "随语速变化，因人而异"},
                {"name": "F3（第三共振峰）", "value": "约 2600–3400 Hz", "note": "边音 F3 相对清晰，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：勒",
            "evaluationText": "勒",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以舌侧气流与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与舌尖接触不实、混入鼻音有关。", "cue": "舌尖贴实上牙床，让气从舌两边走。", "practiceStepId": "L14-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 n，混入了鼻音。", "possibleCause": "可能与软腭放下、气走了鼻腔有关。", "cue": "捏住鼻子读“勒”，保持声音清亮。", "practiceStepId": "L14-P1"},
                {"tag": "final_error", "phenomenon": "本次“勒”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与边音拖太长、韵母没读完整有关。", "cue": "边音一小段就放开，把韵母读清楚。", "practiceStepId": "L14-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“勒”的四声不够一致，音高走向出现偏差。", "possibleCause": "可能与边音起音不稳有关。", "cue": "起音稳住音高，然后干脆下降。", "practiceStepId": "L14-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "从边音到韵母一口气读完。", "practiceStepId": "L14-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L14-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L15",
        "order": 15,
        "layer": "initial",
        "type": "声母",
        "targetSound": "g",
        "pinyin": "g",
        "representativeChar": "哥",
        "title": "声母 g · 舌根一顶",
        "oneLiner": "舌根顶住软腭，一弹发出低沉的 g。",
        "goal": "学会舌根抵住软腭、快速除阻发出不送气的 g，并听出 g 和 k 的区别。",
        "applicableIssues": "适合 g、k 不分，或 g 送气过重的学习者。",
        "tags": ["舌根", "不送气", "塞音"],
        "skeletonPublic": True,
        "confusables": ["L16"],
        "articulation": {
            "description": "舌头后半部分（舌根）向上顶住口腔上壁最靠喉咙的地方（软腭），把气挡住；然后舌根突然放下，气冲出来就是 g。全程舌尖放松，嘴巴自然微张。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌根抵软腭蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.3,
                    "lips": {"aperture": 0.35, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.55, "backness": 0.9, "stricture": "closure"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "舌根放下除阻（不送气）",
                    "holdMs": 90,
                    "jaw": 0.45,
                    "lips": {"aperture": 0.5, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.5, "backness": 0.85, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "burst",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L15_demo_normal_male", "speed": "normal", "voice": "male", "text": "哥"},
            {"ref": "L15_demo_normal_female", "speed": "normal", "voice": "female", "text": "哥"},
        ],
        "quizzes": [
            {
                "id": "L15-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "哥 gē"}, {"text": "科 kē"}],
                "answerIndex": 0,
                "stimulusRef": "L15_quiz_Q1",
                "stimulusText": "哥 gē",
                "explanation": "除阻干脆、几乎不带风的是“哥”；跟着一股明显送气的是“科”。",
            },
            {
                "id": "L15-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "股 gǔ"}, {"text": "苦 kǔ"}],
                "answerIndex": 0,
                "stimulusRef": "L15_quiz_Q2",
                "stimulusText": "股 gǔ",
                "explanation": "“股”干脆短促；“苦”开头有一段送气，像轻轻咳一口气。",
            },
        ],
        "practice": [
            {"id": "L15-P1", "title": "漱口式抬舌根", "instruction": "像漱口一样感受舌根抬起来贴住上壁，再弹开发“哥”。", "repeat": 5, "durationSec": None, "bodyCue": "舌根与软腭有接触又分开的感觉，喉咙保持放松。", "stopNote": "不舒服就停止"},
            {"id": "L15-P2", "title": "干脆弹发", "instruction": "舌根抵软腭憋气 1 秒，突然放开读“哥”，气流收小。", "repeat": 6, "durationSec": None, "bodyCue": "放开的一瞬间气冲出，随后马上进入韵母。", "stopNote": "不舒服就停止"},
            {"id": "L15-P3", "title": "哥/科最小对比", "instruction": "“哥—科”交替读 8 组，手背感受气流的弱与强。", "repeat": 8, "durationSec": None, "bodyCue": "读“哥”几乎无风，读“科”有风。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "g 读起来像 k，除阻后跟了一股气。", "fix": "可以用手背或纸巾测风，练“读‘哥’无风”。"},
            {"phenomenon": "舌位太靠前，g 听起来像 d。", "fix": "可以先打个哈欠，感觉舌根后缩的位置再发音。"},
        ],
        "professional": {
            "description": "g 是舌根（舌面后）不送气清塞音 [k]，舌面后部抵软腭成阻，成阻期软腭抬起，除阻爆破，声带不振动。",
            "acousticRefs": [
                {"name": "VOT（除阻到声带起振）", "value": "约 10–30 ms", "note": "舌根塞音 VOT 略长于双唇、舌尖，因人而异"},
                {"name": "成阻段时长", "value": "约 50–120 ms", "note": "受语速影响大，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：哥",
            "evaluationText": "哥",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以舌根定位与气流对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与舌根位置不准、气流没收住有关。", "cue": "舌根贴住软腭，干脆弹开发“哥”。", "practiceStepId": "L15-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 k，带了明显送气。", "possibleCause": "可能与送气习惯过强有关。", "cue": "纸巾放嘴前，读“哥”时让它基本不动。", "practiceStepId": "L15-P1"},
                {"tag": "final_error", "phenomenon": "本次“哥”的韵母听起来跑到了相近的音上，比如 e 读得太开。", "possibleCause": "可能与除阻后口型没收住有关。", "cue": "舌根弹开后嘴巴半开，e 平稳带出。", "practiceStepId": "L15-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“哥”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与用力弹发牵动音高有关。", "cue": "动作干脆，音高保持平稳。", "practiceStepId": "L15-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“哥”完整读完再停。", "practiceStepId": "L15-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L15-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L16",
        "order": 16,
        "layer": "initial",
        "type": "声母",
        "targetSound": "k",
        "pinyin": "k",
        "representativeChar": "科",
        "title": "声母 k · 舌根一顶送口气",
        "oneLiner": "舌根顶住软腭，弹开时送出一口气，就是 k。",
        "goal": "学会舌根抵软腭、送气除阻发出 k，并听出 k 和 g 的区别。",
        "applicableIssues": "适合 g、k 不分，或 k 读得像 g（送气不足）的学习者。",
        "tags": ["舌根", "送气", "塞音"],
        "skeletonPublic": True,
        "confusables": ["L15"],
        "articulation": {
            "description": "前半段和 g 一样：舌根顶住软腭，把气挡住。不同的是舌根放开时要送出一股明显的气，像轻轻咳一声的风。手背放在嘴前能感到明显的气流。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌根抵软腭蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.3,
                    "lips": {"aperture": 0.35, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.55, "backness": 0.9, "stricture": "closure"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "舌根放下送气除阻",
                    "holdMs": 180,
                    "jaw": 0.5,
                    "lips": {"aperture": 0.55, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.5, "backness": 0.85, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "aspirated_burst",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L16_demo_normal_male", "speed": "normal", "voice": "male", "text": "科"},
            {"ref": "L16_demo_normal_female", "speed": "normal", "voice": "female", "text": "科"},
        ],
        "quizzes": [
            {
                "id": "L16-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "科 kē"}, {"text": "哥 gē"}],
                "answerIndex": 0,
                "stimulusRef": "L16_quiz_Q1",
                "stimulusText": "科 kē",
                "explanation": "舌根放开时送出一股明显气流的是“科”；干脆无风的是“哥”。",
            },
            {
                "id": "L16-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "苦 kǔ"}, {"text": "股 gǔ"}],
                "answerIndex": 0,
                "stimulusRef": "L16_quiz_Q2",
                "stimulusText": "苦 kǔ",
                "explanation": "“苦”开头有一段送气，像轻轻咳风；“股”没有。",
            },
        ],
        "practice": [
            {"id": "L16-P1", "title": "纸巾飘起来", "instruction": "把纸巾举在嘴前约 5 厘米，读“科”，目标是纸巾明显飘动。", "repeat": 5, "durationSec": None, "bodyCue": "舌根弹开时送出一股风，风感清晰。", "stopNote": "不舒服就停止"},
            {"id": "L16-P2", "title": "咳风式弹发", "instruction": "舌根抵软腭憋气 1 秒，弹开时像轻咳一样送气读“科”。", "repeat": 6, "durationSec": None, "bodyCue": "气流集中在放开的一瞬间。", "stopNote": "不舒服就停止"},
            {"id": "L16-P3", "title": "科/哥最小对比", "instruction": "“科—哥”交替读 8 组，用手背感受有风与无风。", "repeat": 8, "durationSec": None, "bodyCue": "读“科”有风，读“哥”没有。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "k 读起来像 g，风送不出来。", "fix": "可以先做轻咳带风的动作，再把声音接上去。"},
            {"phenomenon": "送气太猛像真的咳嗽，字被咳散了。", "fix": "风短促一点，一闪而过就进入后面的韵母。"},
        ],
        "professional": {
            "description": "k 是舌根送气清塞音 [kʰ]，成阻同 g，除阻后有明显送气段，声带在送气段之后起振，VOT 显著长于 g。",
            "acousticRefs": [
                {"name": "VOT（送气段）", "value": "约 70–120 ms", "note": "送气段明显长于不送气 g，因人而异"},
                {"name": "送气摩擦时长", "value": "约 60–110 ms", "note": "随语速变化，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：科",
            "evaluationText": "科",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以舌根定位与气流对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与送气不足、舌根位置不准有关。", "cue": "舌根抵住软腭，弹开时干脆送风。", "practiceStepId": "L16-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 g，缺少明显送气。", "possibleCause": "可能与气流没送出有关。", "cue": "手背放嘴前，读“科”时要感到风。", "practiceStepId": "L16-P1"},
                {"tag": "final_error", "phenomenon": "本次“科”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与送气后口型没收住有关。", "cue": "送气后嘴巴半开，e 平稳带出。", "practiceStepId": "L16-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“科”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与送气用力牵动音高有关。", "cue": "风归风、调归调，音高保持平稳。", "practiceStepId": "L16-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“科”完整读完再停。", "practiceStepId": "L16-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L16-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L17",
        "order": 17,
        "layer": "initial",
        "type": "声母",
        "targetSound": "h",
        "pinyin": "h",
        "representativeChar": "喝",
        "title": "声母 h · 喉咙里呵气",
        "oneLiner": "舌根靠近软腭留条缝，呵出的气擦出 h。",
        "goal": "学会舌根接近软腭、窄缝摩擦发出 h，并与 f 区分。",
        "applicableIssues": "适合 f、h 不分（“灰机”与“飞机”）的学习者。",
        "tags": ["舌根", "擦音", "呵气"],
        "skeletonPublic": True,
        "confusables": ["L10"],
        "articulation": {
            "description": "像给眼镜片哈气一样：舌根抬起来靠近软腭，但不要贴住，中间留一条缝；气从缝里挤出去，擦出“喝”的声音。嘴巴自然张开，喉咙放松，风是宽宽暖暖的。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌根近软腭摩擦 h（可延长）",
                    "holdMs": 450,
                    "jaw": 0.35,
                    "lips": {"aperture": 0.45, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.55, "backness": 0.9, "stricture": "fricative"},
                    "velum": "raised",
                    "airflow": "friction",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L17_demo_normal_male", "speed": "normal", "voice": "male", "text": "喝"},
            {"ref": "L17_demo_normal_female", "speed": "normal", "voice": "female", "text": "喝"},
        ],
        "quizzes": [
            {
                "id": "L17-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "花 huā"}, {"text": "发 fā"}],
                "answerIndex": 0,
                "stimulusRef": "L17_quiz_Q1",
                "stimulusText": "花 huā",
                "explanation": "从喉咙呵出宽气的是“花”；上牙碰下唇擦出细声的是“发”。",
            },
            {
                "id": "L17-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "湖 hú"}, {"text": "服 fú"}],
                "answerIndex": 0,
                "stimulusRef": "L17_quiz_Q2",
                "stimulusText": "湖 hú",
                "explanation": "“湖”是喉咙里的呵气声，气流宽；“服”开头有牙齿和嘴唇的细细摩擦。",
            },
        ],
        "practice": [
            {"id": "L17-P1", "title": "哈气暖手", "instruction": "对手心哈气发出 h，感受宽而暖的气流，再接上韵母读“喝”。", "repeat": 5, "durationSec": None, "bodyCue": "喉咙放松，气流宽宽地从喉咙送出。", "stopNote": "不舒服就停止"},
            {"id": "L17-P2", "title": "h 长摩擦", "instruction": "保持舌根与软腭的缝，发 h 的摩擦音拉长 4 秒。", "repeat": None, "durationSec": 30, "bodyCue": "风声匀匀不断，缝的位置不动。", "stopNote": "不舒服就停止"},
            {"id": "L17-P3", "title": "花/发对比", "instruction": "“花—发”交替读 8 组，手背感受宽暖与细凉的差别。", "repeat": 8, "durationSec": None, "bodyCue": "h 的风宽而暖，f 的风细而凉。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "h 读成了 f，像用嘴唇摩擦。", "fix": "可以照镜子确认牙齿和嘴唇没接触，风从喉咙出。"},
            {"phenomenon": "舌根贴死了软腭，h 听起来像 g 被卡住。", "fix": "留一条缝，像哈气别像咳嗽，声音就顺了。"},
        ],
        "professional": {
            "description": "h 是舌根清擦音 [x]，舌面后部接近软腭形成窄缝，气流通过缝隙产生摩擦，声带不振动，软腭抬起。",
            "acousticRefs": [
                {"name": "摩擦段时长", "value": "约 80–200 ms", "note": "随语速变化，因人而异"},
                {"name": "摩擦噪声频带中心", "value": "约 1000–2500 Hz", "note": "能量低于唇齿擦音 f，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：喝",
            "evaluationText": "喝",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以呵气位置与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与缝隙位置不稳、气流不匀有关。", "cue": "先哈一口气找到位置，再匀匀擦出 h。", "practiceStepId": "L17-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 f，摩擦位置跑到嘴唇了。", "possibleCause": "可能与下唇碰上齿、舌根没抬有关。", "cue": "牙齿和嘴唇分开，风从喉咙呵出来。", "practiceStepId": "L17-P1"},
                {"tag": "final_error", "phenomenon": "本次“喝”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与摩擦后口型没到位有关。", "cue": "呵气结束马上半张开嘴，e 稳稳带出。", "practiceStepId": "L17-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“喝”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与呵气用力、音高没站稳有关。", "cue": "呵气轻一点，音高保持平稳。", "practiceStepId": "L17-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“喝”完整读完再停。", "practiceStepId": "L17-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L17-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L18",
        "order": 18,
        "layer": "initial",
        "type": "声母",
        "targetSound": "j",
        "pinyin": "j",
        "representativeChar": "鸡",
        "title": "声母 j · 舌面挤一下",
        "oneLiner": "舌面前部贴住硬腭前部，先挡后擦，发出细密的 j。",
        "goal": "学会舌面抵前腭、先塞后擦发出不送气的 j，并和 q 区分。",
        "applicableIssues": "适合 j、q 不分，或 j、zh 不分的学习者。",
        "tags": ["舌面音", "不送气", "塞擦音"],
        "skeletonPublic": True,
        "confusables": ["L19"],
        "articulation": {
            "description": "舌头中间偏前的部分（舌面）大面积贴到硬腭前部，先把气挡住；然后稍微松开一条细缝，气挤出去擦出声音，就是 j。嘴角略向两边展开，舌尖自然下垂不翘。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌面抵前腭蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.85, "backness": 0.15, "stricture": "closure"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "松缝挤擦除阻（不送气塞擦）",
                    "holdMs": 110,
                    "jaw": 0.2,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.85, "backness": 0.15, "stricture": "fricative"},
                    "velum": "raised",
                    "airflow": "affricate",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L18_demo_normal_male", "speed": "normal", "voice": "male", "text": "鸡"},
            {"ref": "L18_demo_normal_female", "speed": "normal", "voice": "female", "text": "鸡"},
        ],
        "quizzes": [
            {
                "id": "L18-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "鸡 jī"}, {"text": "七 qī"}],
                "answerIndex": 0,
                "stimulusRef": "L18_quiz_Q1",
                "stimulusText": "鸡 jī",
                "explanation": "挤出去气流很少、声音细密的是“鸡”；跟着明显送气的是“七”。",
            },
            {
                "id": "L18-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "机 jī"}, {"text": "妻 qī"}],
                "answerIndex": 0,
                "stimulusRef": "L18_quiz_Q2",
                "stimulusText": "机 jī",
                "explanation": "用纸巾试：读“机”纸巾基本不动，读“妻”纸巾会飘。",
            },
        ],
        "practice": [
            {"id": "L18-P1", "title": "先挡后擦", "instruction": "舌面贴住硬腭前部挡气 1 秒，松出细缝挤发“鸡”。", "repeat": 6, "durationSec": None, "bodyCue": "舌面先贴后松，气流从细缝里挤出。", "stopNote": "不舒服就停止"},
            {"id": "L18-P2", "title": "微笑口型读鸡", "instruction": "嘴角略展、舌尖下垂，读“鸡”，保持动作干净。", "repeat": 6, "durationSec": None, "bodyCue": "舌面拱起在前，舌尖完全不参与。", "stopNote": "不舒服就停止"},
            {"id": "L18-P3", "title": "鸡/七最小对比", "instruction": "“鸡—七”交替读 8 组，纸巾放在嘴前测气流。", "repeat": 8, "durationSec": None, "bodyCue": "读“鸡”纸巾不动，读“七”纸巾微动。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "j 读起来像 zh，舌尖翘起来了。", "fix": "可以先把舌尖轻抵下齿背，让舌面去做事。"},
            {"phenomenon": "j 送气太足，听起来像 q。", "fix": "可以放纸巾在嘴前，练“读‘鸡’纸巾不动”。"},
        ],
        "professional": {
            "description": "j 是舌面不送气清塞擦音 [tɕ]，舌面前部抵硬腭前部成阻，除阻时转为窄缝摩擦，声带不振动，只与 i、ü 类韵母相拼。",
            "acousticRefs": [
                {"name": "塞擦段总时长", "value": "约 60–140 ms", "note": "成阻加摩擦段，不送气较短，因人而异"},
                {"name": "摩擦段高频能量", "value": "约 3000 Hz 以上明显", "note": "舌面擦音高频突出，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：鸡",
            "evaluationText": "鸡",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以舌面定位与气流对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与舌面位置不准、挤擦不干净有关。", "cue": "舌面贴住前腭，先挡后擦读“鸡”。", "practiceStepId": "L18-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 q，挤开后送气明显。", "possibleCause": "可能与送气习惯过强有关。", "cue": "纸巾放嘴前，读“鸡”时让它基本不动。", "practiceStepId": "L18-P1"},
                {"tag": "final_error", "phenomenon": "本次“鸡”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与舌位滑动、口型变化有关。", "cue": "挤擦之后舌头位置基本不动，i 稳稳延长。", "practiceStepId": "L18-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“鸡”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与挤擦用力牵动音高有关。", "cue": "动作轻巧一点，音高保持平直。", "practiceStepId": "L18-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "吸口气，把“鸡”完整读完再停。", "practiceStepId": "L18-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L18-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L19",
        "order": 19,
        "layer": "initial",
        "type": "声母",
        "targetSound": "q",
        "pinyin": "q",
        "representativeChar": "七",
        "title": "声母 q · 舌面挤开送口气",
        "oneLiner": "舌面贴住前腭再挤开，跟一股明显的气，就是 q。",
        "goal": "学会舌面抵前腭、送气塞擦发出 q，并听出 q 和 j 的区别。",
        "applicableIssues": "适合 j、q 不分，或 q 读得像 j（送气不足）的学习者。",
        "tags": ["舌面音", "送气", "塞擦音"],
        "skeletonPublic": True,
        "confusables": ["L18"],
        "articulation": {
            "description": "动作前半段和 j 一样：舌面贴住硬腭前部，把气挡住。不同的是松开细缝时要用劲送气，擦出的声音后面跟一股明显的风。手背放在嘴前能清楚感到气流。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌面抵前腭蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.85, "backness": 0.15, "stricture": "closure"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "松缝挤开送气除阻",
                    "holdMs": 190,
                    "jaw": 0.2,
                    "lips": {"aperture": 0.3, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.85, "backness": 0.15, "stricture": "fricative"},
                    "velum": "raised",
                    "airflow": "affricate",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L19_demo_normal_male", "speed": "normal", "voice": "male", "text": "七"},
            {"ref": "L19_demo_normal_female", "speed": "normal", "voice": "female", "text": "七"},
        ],
        "quizzes": [
            {
                "id": "L19-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "七 qī"}, {"text": "鸡 jī"}],
                "answerIndex": 0,
                "stimulusRef": "L19_quiz_Q1",
                "stimulusText": "七 qī",
                "explanation": "挤开后跟出明显送气的是“七”；细密无风的是“鸡”。",
            },
            {
                "id": "L19-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "亲 qīn"}, {"text": "金 jīn"}],
                "answerIndex": 0,
                "stimulusRef": "L19_quiz_Q2",
                "stimulusText": "亲 qīn",
                "explanation": "“亲”开头有送气的摩擦风声，“金”开头短促干净。",
            },
        ],
        "practice": [
            {"id": "L19-P1", "title": "纸巾飘起来", "instruction": "把纸巾举在嘴前约 5 厘米，读“七”，目标是纸巾明显飘动。", "repeat": 5, "durationSec": None, "bodyCue": "挤开的一瞬间送出一股风。", "stopNote": "不舒服就停止"},
            {"id": "L19-P2", "title": "挤开送口气", "instruction": "舌面抵前腭憋气 1 秒，松缝时干脆送气读“七”。", "repeat": 6, "durationSec": None, "bodyCue": "先挡、后擦、再送气，三步连成一气。", "stopNote": "不舒服就停止"},
            {"id": "L19-P3", "title": "七/鸡最小对比", "instruction": "“七—鸡”交替读 8 组，用手背感受有风与无风。", "repeat": 8, "durationSec": None, "bodyCue": "读“七”有风感，读“鸡”没有。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "q 读起来像 j，风送不出来。", "fix": "可以先发“嗤”的风声找气流，再接上声音。"},
            {"phenomenon": "舌尖跟着翘，q 听起来像 ch。", "fix": "舌尖轻抵下齿背，只让舌面工作。"},
        ],
        "professional": {
            "description": "q 是舌面送气清塞擦音 [tɕʰ]，成阻与摩擦位置同 j，除阻后有明显送气段，声带在送气段之后起振。",
            "acousticRefs": [
                {"name": "VOT（含送气段）", "value": "约 90–160 ms", "note": "送气塞擦音 VOT 长，因人而异"},
                {"name": "塞擦段总时长", "value": "约 100–200 ms", "note": "成阻加摩擦加送气，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：七",
            "evaluationText": "七",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以舌面定位与气流对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与送气不足、舌面位置不准有关。", "cue": "舌面贴住前腭，挤开时送一口风。", "practiceStepId": "L19-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 j，缺少明显送气。", "possibleCause": "可能与气流没收出来有关。", "cue": "手背放嘴前，读“七”时要感到风。", "practiceStepId": "L19-P1"},
                {"tag": "final_error", "phenomenon": "本次“七”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与送气后舌位滑动有关。", "cue": "送气后舌头稳住，i 轻轻延长。", "practiceStepId": "L19-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“七”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与送气用力牵动音高有关。", "cue": "风送出去，音高保持平稳。", "practiceStepId": "L19-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "吸口气，把“七”完整读完再停。", "practiceStepId": "L19-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L19-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L20",
        "order": 20,
        "layer": "initial",
        "type": "声母",
        "targetSound": "x",
        "pinyin": "x",
        "representativeChar": "西",
        "title": "声母 x · 舌面擦出细音",
        "oneLiner": "舌面抬到硬腭前留一条缝，气擦出细细的 x。",
        "goal": "学会舌面接近前腭、持续摩擦发出清晰的 x。",
        "applicableIssues": "适合 x、s 不分或 x、sh 不分的学习者。",
        "tags": ["舌面音", "擦音", "细音"],
        "skeletonPublic": True,
        "confusables": [],
        "articulation": {
            "description": "舌面抬起来靠近硬腭前部，中间留一条扁扁的缝；气从缝里匀匀挤出，擦出像水壶冒气一样“西——”的细声。舌尖放松下垂，嘴角略向两边展开。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌面近前腭摩擦 x（可延长）",
                    "holdMs": 450,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.85, "backness": 0.15, "stricture": "fricative"},
                    "velum": "raised",
                    "airflow": "friction",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L20_demo_normal_male", "speed": "normal", "voice": "male", "text": "西"},
            {"ref": "L20_demo_normal_female", "speed": "normal", "voice": "female", "text": "西"},
        ],
        "quizzes": [
            {
                "id": "L20-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "西 xī"}, {"text": "思 sī"}],
                "answerIndex": 0,
                "stimulusRef": "L20_quiz_Q1",
                "stimulusText": "西 xī",
                "explanation": "从舌面细缝出来、声音更细的是“西”；舌尖平伸擦出的是“思”。",
            },
            {
                "id": "L20-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "小 xiǎo"}, {"text": "少 shǎo"}],
                "answerIndex": 0,
                "stimulusRef": "L20_quiz_Q2",
                "stimulusText": "小 xiǎo",
                "explanation": "舌尖不翘、声音细的是“小”；舌尖上翘的是“少”。",
            },
        ],
        "practice": [
            {"id": "L20-P1", "title": "水壶冒气", "instruction": "保持舌面细缝，发 x 的摩擦音匀匀拉长 4 秒。", "repeat": None, "durationSec": 30, "bodyCue": "舌面拱起，气流细细匀匀地挤过缝。", "stopNote": "不舒服就停止"},
            {"id": "L20-P2", "title": "舌尖看家", "instruction": "舌尖轻抵下齿背，舌面拱起读“西”，确认舌尖不翘。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖安静待在下面，舌面在干活。", "stopNote": "不舒服就停止"},
            {"id": "L20-P3", "title": "西/思/诗三连", "instruction": "“西—思—诗”交替读 6 组，体会舌面、平舌、翘舌三种位置。", "repeat": 6, "durationSec": None, "bodyCue": "三个音的摩擦位置一个比一个靠后或靠上。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "x 读成了 s，舌面没有拱起来。", "fix": "可以先把舌尖抵住下齿背，舌面自然就拱起来了。"},
            {"phenomenon": "x 读成了 sh，舌尖翘上去了。", "fix": "可以照镜子确认舌尖下垂，只动舌面。"},
        ],
        "professional": {
            "description": "x 是舌面清擦音 [ɕ]，舌面前部接近硬腭前部形成窄缝，气流摩擦而出，声带不振动，只与 i、ü 类韵母相拼。",
            "acousticRefs": [
                {"name": "摩擦段时长", "value": "约 100–250 ms", "note": "随语速变化，因人而异"},
                {"name": "摩擦噪声频带", "value": "约 3000–6000 Hz 能量集中", "note": "高频擦音特征明显，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：西",
            "evaluationText": "西",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以舌面定位与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与舌面没拱起、缝隙不稳有关。", "cue": "舌面拱起留细缝，匀匀擦出“西”。", "practiceStepId": "L20-P2"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 s 或 sh，摩擦位置跑到了舌尖。", "possibleCause": "可能与舌面没抬起、舌尖代偿有关。", "cue": "舌尖抵下齿背，只用舌面擦出声音。", "practiceStepId": "L20-P2"},
                {"tag": "final_error", "phenomenon": "本次“西”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与摩擦后舌位滑动有关。", "cue": "擦完之后舌位不动，i 稳稳延长。", "practiceStepId": "L20-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“西”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与摩擦用力、音高没站稳有关。", "cue": "气流轻一点，音高保持平直。", "practiceStepId": "L20-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“西”完整读完再停。", "practiceStepId": "L20-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L20-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L21",
        "order": 21,
        "layer": "initial",
        "type": "声母",
        "targetSound": "zh",
        "pinyin": "zh",
        "representativeChar": "知",
        "title": "声母 zh · 舌尖翘起挤一下",
        "oneLiner": "舌尖翘起来顶住硬腭前部，先挡后擦，发出 zh。",
        "goal": "学会舌尖上翘抵硬腭前部，发出不送气的 zh，并与 z 区分。",
        "applicableIssues": "适合平翘舌不分（zh、z 混用）的学习者。",
        "tags": ["翘舌", "不送气", "塞擦音"],
        "skeletonPublic": True,
        "confusables": ["L25"],
        "articulation": {
            "description": "把舌尖卷起来一点，翘向硬腭前部（上牙床再往里一点的位置）顶住；挡气后松出一条缝挤出去，就是 zh。嘴唇略撮，舌头中间微微凹陷，像个小勺子。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖翘抵前腭蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.3,
                    "lips": {"aperture": 0.4, "rounding": 0.1, "contact": "none"},
                    "tongueTip": {"place": "postalveolar", "stricture": "closure"},
                    "tongueBody": {"height": 0.5, "backness": 0.55, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "松缝挤擦除阻（不送气塞擦）",
                    "holdMs": 110,
                    "jaw": 0.35,
                    "lips": {"aperture": 0.4, "rounding": 0.1, "contact": "none"},
                    "tongueTip": {"place": "postalveolar", "stricture": "fricative"},
                    "tongueBody": {"height": 0.5, "backness": 0.55, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "affricate",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L21_demo_normal_male", "speed": "normal", "voice": "male", "text": "知"},
            {"ref": "L21_demo_normal_female", "speed": "normal", "voice": "female", "text": "知"},
        ],
        "quizzes": [
            {
                "id": "L21-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "知 zhī"}, {"text": "资 zī"}],
                "answerIndex": 0,
                "stimulusRef": "L21_quiz_Q1",
                "stimulusText": "知 zhī",
                "explanation": "舌尖上翘、声音发闷一点的是“知”；舌尖平伸、声音尖一点的是“资”。",
            },
            {
                "id": "L21-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "主 zhǔ"}, {"text": "组 zǔ"}],
                "answerIndex": 0,
                "stimulusRef": "L21_quiz_Q2",
                "stimulusText": "主 zhǔ",
                "explanation": "翘舌的“主”听起来靠后靠闷，平舌的“组”听起来靠前尖锐。",
            },
        ],
        "practice": [
            {"id": "L21-P1", "title": "翘舌定位", "instruction": "舌尖轻舔上牙床，再往里挪一点顶住硬腭前部，保持 1 秒再读“知”。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖卷起，舌面中央微微凹陷。", "stopNote": "不舒服就停止"},
            {"id": "L21-P2", "title": "挡气挤发", "instruction": "翘舌挡气 1 秒，松出细缝挤发“知”，气流收小。", "repeat": 6, "durationSec": None, "bodyCue": "先挡后擦，一气呵成。", "stopNote": "不舒服就停止"},
            {"id": "L21-P3", "title": "知/资最小对比", "instruction": "“知—资”交替读 8 组，体会舌尖翘与平。", "repeat": 8, "durationSec": None, "bodyCue": "读“知”舌尖在上，读“资”舌尖在下。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "zh 读成了 z，翘舌没做出来。", "fix": "可以先用舌尖舔到硬腭再发音，位置感觉到了再加快。"},
            {"phenomenon": "舌头卷过头，zh 听起来含糊像 r。", "fix": "只翘到“刚好过牙床”的位置，卷太多反而堵住声音。"},
        ],
        "professional": {
            "description": "zh 是舌尖后不送气清塞擦音 [tʂ]，舌尖翘起抵硬腭前部（龈后区）成阻，除阻转窄缝摩擦，声带不振动，唇略圆。",
            "acousticRefs": [
                {"name": "塞擦段总时长", "value": "约 70–150 ms", "note": "成阻加摩擦段，因人而异"},
                {"name": "摩擦谱重心", "value": "约 2500–4500 Hz", "note": "低于舌面擦音 x，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：知",
            "evaluationText": "知",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以翘舌定位与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与翘舌幅度不够、挤擦不干净有关。", "cue": "舌尖翘到牙床后面一点，先挡后擦。", "practiceStepId": "L21-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 z，翘舌没有做出来。", "possibleCause": "可能与舌尖没上翘、位置太平有关。", "cue": "舌尖先舔到硬腭再发音，别急着出声。", "practiceStepId": "L21-P1"},
                {"tag": "final_error", "phenomenon": "本次“知”的韵母（整体认读的 zhi）听起来跑到了相近的音上。", "possibleCause": "可能与翘舌后舌头滑动有关。", "cue": "擦完之后舌尖位置保持，声音稳稳延长。", "practiceStepId": "L21-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“知”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与翘舌用力牵动音高有关。", "cue": "动作稳一点，音高保持平直。", "practiceStepId": "L21-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "吸口气，把“知”完整读完再停。", "practiceStepId": "L21-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L21-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L22",
        "order": 22,
        "layer": "initial",
        "type": "声母",
        "targetSound": "ch",
        "pinyin": "ch",
        "representativeChar": "吃",
        "title": "声母 ch · 舌尖翘起送口气",
        "oneLiner": "舌尖翘起挤开，跟一股明显的气，就是 ch。",
        "goal": "学会翘舌位送气塞擦发出 ch，并听出 ch 和 c 的区别。",
        "applicableIssues": "适合平翘舌不分，或 ch、c 混用的学习者。",
        "tags": ["翘舌", "送气", "塞擦音"],
        "skeletonPublic": True,
        "confusables": ["L26"],
        "articulation": {
            "description": "位置和 zh 一样：舌尖翘向硬腭前部顶住，把气挡住。不同的是松开细缝时用劲送气，像“呲——”地喷出一股风。手背放在嘴前能明显感到气流。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖翘抵前腭蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.3,
                    "lips": {"aperture": 0.4, "rounding": 0.1, "contact": "none"},
                    "tongueTip": {"place": "postalveolar", "stricture": "closure"},
                    "tongueBody": {"height": 0.5, "backness": 0.55, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "松缝挤开送气除阻",
                    "holdMs": 190,
                    "jaw": 0.35,
                    "lips": {"aperture": 0.45, "rounding": 0.1, "contact": "none"},
                    "tongueTip": {"place": "postalveolar", "stricture": "fricative"},
                    "tongueBody": {"height": 0.5, "backness": 0.55, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "affricate",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L22_demo_normal_male", "speed": "normal", "voice": "male", "text": "吃"},
            {"ref": "L22_demo_normal_female", "speed": "normal", "voice": "female", "text": "吃"},
        ],
        "quizzes": [
            {
                "id": "L22-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "吃 chī"}, {"text": "次 cì"}],
                "answerIndex": 0,
                "stimulusRef": "L22_quiz_Q1",
                "stimulusText": "吃 chī",
                "explanation": "翘舌加明显送气的是“吃”；平舌、风声尖细的是“次”。",
            },
            {
                "id": "L22-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "插 chā"}, {"text": "擦 cā"}],
                "answerIndex": 0,
                "stimulusRef": "L22_quiz_Q2",
                "stimulusText": "插 chā",
                "explanation": "“插”舌尖上翘、气流偏闷偏厚；“擦”舌尖平伸、声音尖一点。",
            },
        ],
        "practice": [
            {"id": "L22-P1", "title": "纸巾飘起来", "instruction": "把纸巾举在嘴前约 5 厘米，翘舌读“吃”，目标是纸巾明显飘动。", "repeat": 5, "durationSec": None, "bodyCue": "挤开的一瞬间送出一股明显的风。", "stopNote": "不舒服就停止"},
            {"id": "L22-P2", "title": "翘舌挡气挤发", "instruction": "舌尖翘抵硬腭前部憋气 1 秒，松缝送气读“吃”。", "repeat": 6, "durationSec": None, "bodyCue": "翘舌保持不动，风从缝隙喷出。", "stopNote": "不舒服就停止"},
            {"id": "L22-P3", "title": "吃/次最小对比", "instruction": "“吃—次”交替读 8 组，体会舌尖翘与平、风声厚与尖。", "repeat": 8, "durationSec": None, "bodyCue": "读“吃”舌尖在上风厚，读“次”舌尖平风尖。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "ch 读成了 c，翘舌没做出来。", "fix": "可以先练舌尖舔硬腭，确认位置后再加送气。"},
            {"phenomenon": "送气太猛像吐气，字被冲散。", "fix": "风短促一点，擦出声就进入韵母。"},
        ],
        "professional": {
            "description": "ch 是舌尖后送气清塞擦音 [tʂʰ]，成阻与摩擦位置同 zh，除阻后有明显送气段，声带在送气段之后起振。",
            "acousticRefs": [
                {"name": "VOT（含送气段）", "value": "约 100–170 ms", "note": "送气塞擦音 VOT 长，因人而异"},
                {"name": "摩擦谱重心", "value": "约 2000–4000 Hz", "note": "翘舌擦音频谱偏厚，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：吃",
            "evaluationText": "吃",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以翘舌定位与气流对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与翘舌不够、送气不足有关。", "cue": "舌尖翘到牙床后，挤开时送一口风。", "practiceStepId": "L22-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 c，翘舌没做出来。", "possibleCause": "可能与舌尖没上翘有关。", "cue": "舌尖舔到硬腭前部再挤开送气。", "practiceStepId": "L22-P1"},
                {"tag": "final_error", "phenomenon": "本次“吃”的韵母（整体认读的 chi）听起来跑到了相近的音上。", "possibleCause": "可能与送气后舌头滑动有关。", "cue": "送气后舌尖位置保持，声音稳稳延长。", "practiceStepId": "L22-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“吃”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与送气用力牵动音高有关。", "cue": "风归风、调归调，音高保持平稳。", "practiceStepId": "L22-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "吸口气，把“吃”完整读完再停。", "practiceStepId": "L22-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L22-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L23",
        "order": 23,
        "layer": "initial",
        "type": "声母",
        "targetSound": "sh",
        "pinyin": "sh",
        "representativeChar": "诗",
        "title": "声母 sh · 舌尖翘起擦一擦",
        "oneLiner": "舌尖翘向硬腭前部留条缝，气擦出厚厚的 sh。",
        "goal": "学会翘舌接近前腭、持续摩擦发出 sh，并与 s 区分。",
        "applicableIssues": "适合平翘舌不分（sh、s 混用）的学习者。",
        "tags": ["翘舌", "擦音"],
        "skeletonPublic": True,
        "confusables": ["L27"],
        "articulation": {
            "description": "舌尖翘向硬腭前部，但不顶住，留一条缝；气从缝里匀匀挤出，擦出“诗——”一样宽厚的风声。和 zh 的区别是：sh 全程不闭合，只有缝。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖翘近前腭摩擦 sh（可延长）",
                    "holdMs": 450,
                    "jaw": 0.3,
                    "lips": {"aperture": 0.4, "rounding": 0.1, "contact": "none"},
                    "tongueTip": {"place": "postalveolar", "stricture": "fricative"},
                    "tongueBody": {"height": 0.5, "backness": 0.55, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "friction",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L23_demo_normal_male", "speed": "normal", "voice": "male", "text": "诗"},
            {"ref": "L23_demo_normal_female", "speed": "normal", "voice": "female", "text": "诗"},
        ],
        "quizzes": [
            {
                "id": "L23-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "诗 shī"}, {"text": "思 sī"}],
                "answerIndex": 0,
                "stimulusRef": "L23_quiz_Q1",
                "stimulusText": "诗 shī",
                "explanation": "翘舌擦出的风声宽厚的是“诗”；平舌擦出的声音尖细的是“思”。",
            },
            {
                "id": "L23-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "山 shān"}, {"text": "三 sān"}],
                "answerIndex": 0,
                "stimulusRef": "L23_quiz_Q2",
                "stimulusText": "山 shān",
                "explanation": "“山”开头风声厚一点，“三”开头哨音尖一点。",
            },
        ],
        "practice": [
            {"id": "L23-P1", "title": "翘舌长摩擦", "instruction": "保持翘舌缝隙，发 sh 的风声匀匀拉长 4 秒。", "repeat": None, "durationSec": 30, "bodyCue": "舌尖悬在硬腭前部下方，风声宽而匀。", "stopNote": "不舒服就停止"},
            {"id": "L23-P2", "title": "哨音定位", "instruction": "舌尖先轻抵硬腭再稍稍离开，找到“诗”的风声位置后读字。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖卷起不贴死，缝里出风。", "stopNote": "不舒服就停止"},
            {"id": "L23-P3", "title": "诗/思最小对比", "instruction": "“诗—思”交替读 8 组，体会风声的厚与尖。", "repeat": 8, "durationSec": None, "bodyCue": "读“诗”舌尖翘，读“思”舌尖平。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "sh 读成了 s，翘舌没做出来。", "fix": "可以把舌尖往上卷一点，风声立刻会变厚。"},
            {"phenomenon": "翘舌时嘴唇也跟着用力突出，声音发闷。", "fix": "嘴唇放松微撮就好，主要动作在舌尖。"},
        ],
        "professional": {
            "description": "sh 是舌尖后清擦音 [ʂ]，舌尖翘起接近硬腭前部形成窄缝，气流摩擦而出，声带不振动，唇常略圆。",
            "acousticRefs": [
                {"name": "摩擦段时长", "value": "约 100–250 ms", "note": "随语速变化，因人而异"},
                {"name": "摩擦噪声频带", "value": "约 2000–4000 Hz 能量集中", "note": "低于平舌 s 的高频，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：诗",
            "evaluationText": "诗",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以翘舌定位与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与翘舌幅度不够、缝隙不稳有关。", "cue": "舌尖翘向硬腭前部，匀匀擦出风声。", "practiceStepId": "L23-P2"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 s，翘舌没有做出来。", "possibleCause": "可能与舌尖没上翘、位置太平有关。", "cue": "舌尖往上卷一点，风声会变厚。", "practiceStepId": "L23-P2"},
                {"tag": "final_error", "phenomenon": "本次“诗”的韵母（整体认读的 shi）听起来跑到了相近的音上。", "possibleCause": "可能与摩擦后舌位滑动有关。", "cue": "擦完之后舌尖位置保持，声音稳稳延长。", "practiceStepId": "L23-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“诗”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与摩擦用力、音高没站稳有关。", "cue": "风声轻一点，音高保持平直。", "practiceStepId": "L23-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“诗”完整读完再停。", "practiceStepId": "L23-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L23-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L24",
        "order": 24,
        "layer": "initial",
        "type": "声母",
        "targetSound": "r",
        "pinyin": "r",
        "representativeChar": "日",
        "title": "声母 r · 翘起舌头带嗓音",
        "oneLiner": "像发 sh 一样翘舌，但嗓子一起振动，就是 r。",
        "goal": "学会翘舌位加声带振动发出 r，并和 l 区分。",
        "applicableIssues": "适合 r 读成 l（“热”“乐”不分）或读成 z 的学习者。",
        "tags": ["翘舌", "浊音", "带嗓音"],
        "skeletonPublic": True,
        "confusables": [],
        "articulation": {
            "description": "位置和 sh 差不多：舌尖翘向硬腭前部，留条缝。不同的是发 r 时嗓子要一起出声，手摸喉咙能感到震动，听起来比 sh“嗡”一些、暖一些。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "翘舌带嗓摩擦 r（可延长）",
                    "holdMs": 450,
                    "jaw": 0.3,
                    "lips": {"aperture": 0.4, "rounding": 0.1, "contact": "none"},
                    "tongueTip": {"place": "postalveolar", "stricture": "fricative"},
                    "tongueBody": {"height": 0.5, "backness": 0.55, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "friction",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L24_demo_normal_male", "speed": "normal", "voice": "male", "text": "日"},
            {"ref": "L24_demo_normal_female", "speed": "normal", "voice": "female", "text": "日"},
        ],
        "quizzes": [
            {
                "id": "L24-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "热 rè"}, {"text": "乐 lè"}],
                "answerIndex": 0,
                "stimulusRef": "L24_quiz_Q1",
                "stimulusText": "热 rè",
                "explanation": "翘舌带嗓音、声音偏闷的是“热”；舌尖抵牙床、声音清亮的是“乐”。",
            },
            {
                "id": "L24-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "肉 ròu"}, {"text": "漏 lòu"}],
                "answerIndex": 0,
                "stimulusRef": "L24_quiz_Q2",
                "stimulusText": "肉 ròu",
                "explanation": "“肉”开头舌头翘起、声音发嗡；“漏”开头舌尖点一下、声音清亮。",
            },
        ],
        "practice": [
            {"id": "L24-P1", "title": "sh 变 r", "instruction": "持续发 sh 的风声，然后加上嗓音震动，听声音变成 r。", "repeat": 6, "durationSec": None, "bodyCue": "喉咙开始震动，风声里混进“嗡”的嗓音。", "stopNote": "不舒服就停止"},
            {"id": "L24-P2", "title": "r 长音", "instruction": "保持翘舌和嗓音，把 r 拉长 4 秒，手摸喉咙确认震动。", "repeat": None, "durationSec": 30, "bodyCue": "喉咙持续震动，舌尖位置不动。", "stopNote": "不舒服就停止"},
            {"id": "L24-P3", "title": "热/乐最小对比", "instruction": "“热—乐”“肉—漏”交替读 8 组，手摸喉咙与鼻翼对比。", "repeat": 8, "durationSec": None, "bodyCue": "读“热”舌头翘在上方，读“乐”舌尖点牙床。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "r 读成了 l，翘舌没做出来。", "fix": "可以先发 sh 找到翘舌位置，再加上嗓音。"},
            {"phenomenon": "嗓音震动不够，r 听起来像清清的 sh。", "fix": "可以手摸喉咙，确认发音全程都在“嗡”。"},
        ],
        "professional": {
            "description": "r 是舌尖后浊擦音/近音 [ʐ]（也常记为 [ɻ]），舌位同 sh，声带振动，摩擦较弱。其声学特征是第三共振峰（F3）明显降低。",
            "acousticRefs": [
                {"name": "F3（第三共振峰）", "value": "较相邻元音下降约 150–350 Hz", "note": "翘舌音的典型特征，因人而异"},
                {"name": "摩擦段时长", "value": "约 60–150 ms", "note": "浊擦音摩擦较弱，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：日",
            "evaluationText": "日",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以嗓音震动与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与翘舌不够、嗓音没加上有关。", "cue": "先发 sh 的风声，再让喉咙嗡起来。", "practiceStepId": "L24-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 l 或 sh，翘舌加嗓音少了一样。", "possibleCause": "可能与舌尖没翘、声带没振有关。", "cue": "翘着舌头发 sh，同时手摸喉咙确认在震。", "practiceStepId": "L24-P1"},
                {"tag": "final_error", "phenomenon": "本次“日”的韵母（整体认读的 ri）听起来跑到了相近的音上。", "possibleCause": "可能与摩擦后舌位滑动有关。", "cue": "擦完之后舌尖位置保持，声音稳稳延长。", "practiceStepId": "L24-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“日”的四声不够一致，音高走向出现偏差。", "possibleCause": "可能与嗓音起音不稳有关。", "cue": "嗓音一站稳就从高往降。", "practiceStepId": "L24-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "吸口气，把“日”完整读完再停。", "practiceStepId": "L24-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L24-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L25",
        "order": 25,
        "layer": "initial",
        "type": "声母",
        "targetSound": "z",
        "pinyin": "z",
        "representativeChar": "资",
        "title": "声母 z · 舌尖平伸挤一下",
        "oneLiner": "舌尖平抵上齿背，先挡后擦，发出尖细的 z。",
        "goal": "学会舌尖平抵上齿背，发出不送气的 z，并与 zh 区分。",
        "applicableIssues": "适合平翘舌不分（z、zh 混用）的学习者。",
        "tags": ["平舌", "不送气", "塞擦音"],
        "skeletonPublic": True,
        "confusables": ["L21"],
        "articulation": {
            "description": "舌尖平平地伸出来，轻抵上牙齿的背面，把气挡住；然后松开一条细缝，气挤出去擦出尖细的声音，就是 z。舌尖全程不翘，牙齿微微对齐。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖平抵齿背蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "dental", "stricture": "closure"},
                    "tongueBody": {"height": 0.4, "backness": 0.35, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "松缝挤擦除阻（不送气塞擦）",
                    "holdMs": 110,
                    "jaw": 0.2,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "dental", "stricture": "fricative"},
                    "tongueBody": {"height": 0.4, "backness": 0.35, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "affricate",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L25_demo_normal_male", "speed": "normal", "voice": "male", "text": "资"},
            {"ref": "L25_demo_normal_female", "speed": "normal", "voice": "female", "text": "资"},
        ],
        "quizzes": [
            {
                "id": "L25-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "资 zī"}, {"text": "知 zhī"}],
                "answerIndex": 0,
                "stimulusRef": "L25_quiz_Q1",
                "stimulusText": "资 zī",
                "explanation": "舌尖平伸、声音尖一点的是“资”；舌尖上翘、声音闷一点的是“知”。",
            },
            {
                "id": "L25-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "早 zǎo"}, {"text": "找 zhǎo"}],
                "answerIndex": 0,
                "stimulusRef": "L25_quiz_Q2",
                "stimulusText": "早 zǎo",
                "explanation": "“早”开头声音靠前尖细，“找”开头翘舌发闷。",
            },
        ],
        "practice": [
            {"id": "L25-P1", "title": "平舌定位", "instruction": "舌尖轻抵上齿背，照镜子确认舌尖不翘，再读“资”。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖平贴在上牙背面，位置很靠前。", "stopNote": "不舒服就停止"},
            {"id": "L25-P2", "title": "平伸挤发", "instruction": "舌尖抵齿背憋气 1 秒，松出细缝挤发“资”。", "repeat": 6, "durationSec": None, "bodyCue": "先挡后擦，风声尖细短促。", "stopNote": "不舒服就停止"},
            {"id": "L25-P3", "title": "资/知最小对比", "instruction": "“资—知”交替读 8 组，体会舌尖一平一翘。", "repeat": 8, "durationSec": None, "bodyCue": "读“资”舌尖在下前，读“知”舌尖卷起在上。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "z 读成了 zh，舌头不自觉翘起来。", "fix": "可以照镜子练，看到舌尖平平抵住上牙背面再发音。"},
            {"phenomenon": "送气太足，z 听起来像 c。", "fix": "可以放纸巾在嘴前，练“读‘资’纸巾不动”。"},
        ],
        "professional": {
            "description": "z 是舌尖前不送气清塞擦音 [ts]，舌尖平抵上齿背成阻，除阻转窄缝摩擦，声带不振动，俗称“平舌音”。",
            "acousticRefs": [
                {"name": "塞擦段总时长", "value": "约 60–130 ms", "note": "成阻加摩擦段，因人而异"},
                {"name": "摩擦谱重心", "value": "约 4000 Hz 以上偏高", "note": "平舌擦音高频突出，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：资",
            "evaluationText": "资",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以平舌定位与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与舌尖位置不准、挤擦不干净有关。", "cue": "舌尖平抵上齿背，先挡后擦读“资”。", "practiceStepId": "L25-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 zh，舌头翘起来了。", "possibleCause": "可能与舌尖上翘、位置后移有关。", "cue": "照镜子看舌尖，平平地贴住上牙背面。", "practiceStepId": "L25-P1"},
                {"tag": "final_error", "phenomenon": "本次“资”的韵母（整体认读的 zi）听起来跑到了相近的音上。", "possibleCause": "可能与摩擦后舌位滑动有关。", "cue": "擦完之后舌尖位置保持，声音稳稳延长。", "practiceStepId": "L25-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“资”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与挤擦用力牵动音高有关。", "cue": "动作轻一点，音高保持平直。", "practiceStepId": "L25-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "吸口气，把“资”完整读完再停。", "practiceStepId": "L25-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L25-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L26",
        "order": 26,
        "layer": "initial",
        "type": "声母",
        "targetSound": "c",
        "pinyin": "c",
        "representativeChar": "次",
        "title": "声母 c · 舌尖平伸送口气",
        "oneLiner": "舌尖平抵上齿背，挤开时跟一股明显的气，就是 c。",
        "goal": "学会平舌位送气塞擦发出 c，并听出 c 和 ch、z 的区别。",
        "applicableIssues": "适合平翘舌不分，或 c、z 送气混淆的学习者。",
        "tags": ["平舌", "送气", "塞擦音"],
        "skeletonPublic": True,
        "confusables": ["L22"],
        "articulation": {
            "description": "位置和 z 一样：舌尖平抵上齿背。不同的是松开细缝时用劲送气，像轻轻“呲”一下，跟出一股明显的风。声音比 z 更响、风更大。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖平抵齿背蓄气（成阻）",
                    "holdMs": 130,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "dental", "stricture": "closure"},
                    "tongueBody": {"height": 0.4, "backness": 0.35, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "none",
                    "voicing": False,
                },
                {
                    "label": "松缝挤开送气除阻",
                    "holdMs": 180,
                    "jaw": 0.2,
                    "lips": {"aperture": 0.3, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "dental", "stricture": "fricative"},
                    "tongueBody": {"height": 0.4, "backness": 0.35, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "affricate",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L26_demo_normal_male", "speed": "normal", "voice": "male", "text": "次"},
            {"ref": "L26_demo_normal_female", "speed": "normal", "voice": "female", "text": "次"},
        ],
        "quizzes": [
            {
                "id": "L26-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "次 cì"}, {"text": "吃 chī"}],
                "answerIndex": 0,
                "stimulusRef": "L26_quiz_Q1",
                "stimulusText": "次 cì",
                "explanation": "平舌、风声尖细的是“次”；翘舌、风声宽厚的是“吃”。",
            },
            {
                "id": "L26-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "从 cóng"}, {"text": "虫 chóng"}],
                "answerIndex": 0,
                "stimulusRef": "L26_quiz_Q2",
                "stimulusText": "从 cóng",
                "explanation": "“从”开头平舌尖细，“虫”开头翘舌厚实。",
            },
        ],
        "practice": [
            {"id": "L26-P1", "title": "纸巾飘起来", "instruction": "把纸巾举在嘴前约 5 厘米，平舌读“次”，目标是纸巾明显飘动。", "repeat": 5, "durationSec": None, "bodyCue": "挤开的一瞬间送出一股尖细的风。", "stopNote": "不舒服就停止"},
            {"id": "L26-P2", "title": "平伸送气挤发", "instruction": "舌尖平抵齿背憋气 1 秒，松缝时干脆送气读“次”。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖位置不动，风从细缝喷出。", "stopNote": "不舒服就停止"},
            {"id": "L26-P3", "title": "次/吃最小对比", "instruction": "“次—吃”交替读 8 组，体会平舌尖风与翘舌厚风。", "repeat": 8, "durationSec": None, "bodyCue": "读“次”舌尖平，读“吃”舌尖翘。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "c 读成了 ch，舌头翘起来了。", "fix": "可以照镜子确认舌尖平抵上牙背面。"},
            {"phenomenon": "送气不足，c 听起来像 z。", "fix": "可以先“呲”一声把风送出来，再接上声音。"},
        ],
        "professional": {
            "description": "c 是舌尖前送气清塞擦音 [tsʰ]，成阻与摩擦位置同 z，除阻后有明显送气段，声带在送气段之后起振。",
            "acousticRefs": [
                {"name": "VOT（含送气段）", "value": "约 90–150 ms", "note": "送气塞擦音 VOT 长，因人而异"},
                {"name": "摩擦噪声频带", "value": "约 4000–8000 Hz 能量集中", "note": "平舌送气擦音高频突出，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：次",
            "evaluationText": "次",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以平舌定位与气流对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与送气不足、舌尖位置不准有关。", "cue": "舌尖平抵上齿背，挤开时送一口风。", "practiceStepId": "L26-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 ch 或 z，翘舌或送气出了偏差。", "possibleCause": "可能与舌尖上翘、气流没收出来有关。", "cue": "舌尖放平，挤开时让纸巾飘起来。", "practiceStepId": "L26-P1"},
                {"tag": "final_error", "phenomenon": "本次“次”的韵母（整体认读的 ci）听起来跑到了相近的音上。", "possibleCause": "可能与送气后舌位滑动有关。", "cue": "送气后舌尖位置保持，声音稳稳延长。", "practiceStepId": "L26-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“次”的四声不够一致，音高走向出现偏差。", "possibleCause": "可能与送气用力牵动音高有关。", "cue": "风送出去后，声调干脆下降。", "practiceStepId": "L26-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与动作没做完就停有关。", "cue": "吸口气，把“次”完整读完再停。", "practiceStepId": "L26-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L26-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L27",
        "order": 27,
        "layer": "initial",
        "type": "声母",
        "targetSound": "s",
        "pinyin": "s",
        "representativeChar": "思",
        "title": "声母 s · 舌尖平伸擦细音",
        "oneLiner": "舌尖平平伸向上齿背留条缝，擦出漏气一样的 s。",
        "goal": "学会舌尖平伸、持续摩擦发出尖细的 s，并与 sh 区分。",
        "applicableIssues": "适合平翘舌不分（s、sh 混用）的学习者。",
        "tags": ["平舌", "擦音"],
        "skeletonPublic": True,
        "confusables": ["L23"],
        "articulation": {
            "description": "舌尖平平伸向上牙背面，但不顶住，留一条细缝；气从缝里匀匀挤出去，像轻轻漏气一样“嘶——”。和 z 的区别是：s 全程不闭合，只有缝。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "舌尖平伸齿背摩擦 s（可延长）",
                    "holdMs": 450,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "dental", "stricture": "fricative"},
                    "tongueBody": {"height": 0.4, "backness": 0.35, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "friction",
                    "voicing": False,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L27_demo_normal_male", "speed": "normal", "voice": "male", "text": "思"},
            {"ref": "L27_demo_normal_female", "speed": "normal", "voice": "female", "text": "思"},
        ],
        "quizzes": [
            {
                "id": "L27-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "思 sī"}, {"text": "诗 shī"}],
                "answerIndex": 0,
                "stimulusRef": "L27_quiz_Q1",
                "stimulusText": "思 sī",
                "explanation": "平舌擦出的声音尖细像漏气的是“思”；翘舌擦出的风声宽厚的是“诗”。",
            },
            {
                "id": "L27-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "素 sù"}, {"text": "树 shù"}],
                "answerIndex": 0,
                "stimulusRef": "L27_quiz_Q2",
                "stimulusText": "素 sù",
                "explanation": "“素”开头哨音尖一点，“树”开头风声闷一点。",
            },
        ],
        "practice": [
            {"id": "L27-P1", "title": "漏气长音", "instruction": "保持舌尖细缝，发 s 的漏气声匀匀拉长 4 秒。", "repeat": None, "durationSec": 30, "bodyCue": "舌尖靠近上牙背面，气流细细一条。", "stopNote": "不舒服就停止"},
            {"id": "L27-P2", "title": "细缝定位", "instruction": "舌尖先轻抵上齿背再稍稍离开，找到尖细风声后读“思”。", "repeat": 6, "durationSec": None, "bodyCue": "舌尖平伸不翘，缝很窄。", "stopNote": "不舒服就停止"},
            {"id": "L27-P3", "title": "思/诗最小对比", "instruction": "“思—诗”交替读 8 组，体会风声尖与厚。", "repeat": 8, "durationSec": None, "bodyCue": "读“思”舌尖平，读“诗”舌尖翘。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "s 读成了 sh，舌头翘起来了。", "fix": "可以让舌尖放松放平，风声自然变尖。"},
            {"phenomenon": "缝隙太宽，风声松散不尖。", "fix": "舌尖再靠近上牙一点，把缝收窄，声音就集中了。"},
        ],
        "professional": {
            "description": "s 是舌尖前清擦音 [s]，舌尖接近上齿背形成窄缝，气流摩擦而出，声带不振动，俗称“平舌音”，高频摩擦噪声突出。",
            "acousticRefs": [
                {"name": "摩擦段时长", "value": "约 100–250 ms", "note": "随语速变化，因人而异"},
                {"name": "摩擦噪声频带", "value": "约 5000 Hz 以上能量突出", "note": "s 是普通话频率最高的擦音之一，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：思",
            "evaluationText": "思",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以平舌定位与听感对比为主，声母判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与缝隙不稳、舌尖位置不准有关。", "cue": "舌尖平伸留细缝，匀匀擦出“思”。", "practiceStepId": "L27-P2"},
                {"tag": "initial_error", "phenomenon": "本次声母听起来更像 sh，舌头翘起来了。", "possibleCause": "可能与舌尖上翘、位置后移有关。", "cue": "舌尖放平，风声立刻会变尖。", "practiceStepId": "L27-P2"},
                {"tag": "final_error", "phenomenon": "本次“思”的韵母（整体认读的 si）听起来跑到了相近的音上。", "possibleCause": "可能与摩擦后舌位滑动有关。", "cue": "擦完之后舌尖位置保持，声音稳稳延长。", "practiceStepId": "L27-P1"},
                {"tag": "tone_error", "phenomenon": "本次声调与“思”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与摩擦用力、音高没站稳有关。", "cue": "气流轻一点，音高保持平直。", "practiceStepId": "L27-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“思”完整读完再停。", "practiceStepId": "L27-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L27-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L28",
        "order": 28,
        "layer": "initial",
        "type": "声母",
        "targetSound": "y",
        "pinyin": "y",
        "representativeChar": "医",
        "title": "声母 y · 咧嘴轻轻一带",
        "oneLiner": "y 就是很快滑过去的 i，咧开嘴角一带而过。",
        "goal": "学会用 i 的舌位唇形快速起音，带出 y 开头的字。",
        "applicableIssues": "适合 y、w 起音含糊，或“眼、远”不分的学习者。",
        "tags": ["半元音", "展唇", "前舌位"],
        "skeletonPublic": True,
        "confusables": [],
        "articulation": {
            "description": "y 的位置和 i 一样：嘴角展开，舌头前部抬高。区别是 y 只在开头轻轻一带，像滑梯的坡，很快滑到后面的韵母上。单独拉长 y，听起来就是“衣——”。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "展唇高舌起音 y（滑向韵母）",
                    "holdMs": 450,
                    "jaw": 0.15,
                    "lips": {"aperture": 0.25, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.9, "backness": 0.1, "stricture": "approximant"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L28_demo_normal_male", "speed": "normal", "voice": "male", "text": "医"},
            {"ref": "L28_demo_normal_female", "speed": "normal", "voice": "female", "text": "医"},
        ],
        "quizzes": [
            {
                "id": "L28-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "衣 yī"}, {"text": "乌 wū"}],
                "answerIndex": 0,
                "stimulusRef": "L28_quiz_Q1",
                "stimulusText": "衣 yī",
                "explanation": "咧嘴起音、声音细亮的是“衣”；撮圆起音、声音低沉的是“乌”。",
            },
            {
                "id": "L28-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "眼 yǎn"}, {"text": "远 yuǎn"}],
                "answerIndex": 0,
                "stimulusRef": "L28_quiz_Q2",
                "stimulusText": "眼 yǎn",
                "explanation": "咧嘴起音的是“眼”；圆唇起音的是“远”。起音的嘴唇形状决定后面接哪个音。",
            },
        ],
        "practice": [
            {"id": "L28-P1", "title": "衣 拉长再加速", "instruction": "拉长发“衣——”，保持舌位唇形，再越读越短，变成快速的“医”。", "repeat": 6, "durationSec": None, "bodyCue": "嘴角展开，舌前部抬起后顺势滑开。", "stopNote": "不舒服就停止"},
            {"id": "L28-P2", "title": "y 开头连读", "instruction": "连读“医生、月亮、衣服”，体会 y 轻轻一带就滑进韵母。", "repeat": 6, "durationSec": None, "bodyCue": "起音轻而快，没有卡顿。", "stopNote": "不舒服就停止"},
            {"id": "L28-P3", "title": "眼/远对比", "instruction": "“眼—远”交替读 8 组，照镜子看嘴角咧开与撮圆。", "repeat": 8, "durationSec": None, "bodyCue": "读“眼”嘴角展开，读“远”嘴唇收圆。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "y 读得带很重的摩擦，听起来像 r。", "fix": "可以想着“衣”的清爽感觉，一带而过不磨蹭。"},
            {"phenomenon": "y 起音圆了嘴唇，“眼”听起来像“远”。", "fix": "可以照镜子盯着嘴角，起音时保持咧开。"},
        ],
        "professional": {
            "description": "y 是汉语拼音的零声母写法，实际为前高展唇半元音 [j]，功能上是 i 的音节首滑音，声带振动，与后续韵母连续过渡。",
            "acousticRefs": [
                {"name": "F1（第一共振峰）", "value": "约 250–350 Hz", "note": "同 i 的高舌位特征，因人而异"},
                {"name": "F2（第二共振峰）", "value": "约 2000–2500 Hz", "note": "前滑音 F2 高，起音后向韵母滑动，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：医",
            "evaluationText": "医",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以起音唇形与听感对比为主，判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与起音含糊、唇形不到位有关。", "cue": "咧嘴抬舌，轻轻一带读“医”。", "practiceStepId": "L28-P1"},
                {"tag": "initial_error", "phenomenon": "本次起音听起来像 r（摩擦过重）或圆唇的 w。", "possibleCause": "可能与带摩擦、嘴唇撮圆有关。", "cue": "嘴角展开，像清爽的“衣”一样起音。", "practiceStepId": "L28-P1"},
                {"tag": "final_error", "phenomenon": "本次“医”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与起音后舌位滑动有关。", "cue": "一带而过之后舌位稳住，i 轻轻延长。", "practiceStepId": "L28-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“医”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音太快、音高没站稳有关。", "cue": "起音轻一点，音高保持平直。", "practiceStepId": "L28-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“医”完整读完再停。", "practiceStepId": "L28-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L28-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L29",
        "order": 29,
        "layer": "initial",
        "type": "声母",
        "targetSound": "w",
        "pinyin": "w",
        "representativeChar": "乌",
        "title": "声母 w · 撮圆嘴唇轻轻一带",
        "oneLiner": "w 就是很快滑过去的 u，撮圆嘴唇一带而过。",
        "goal": "学会用 u 的圆唇舌位快速起音，带出 w 开头的字。",
        "applicableIssues": "适合 w 起音含糊，或 w、h 不分（“王”“黄”混）的学习者。",
        "tags": ["半元音", "圆唇", "后舌位"],
        "skeletonPublic": True,
        "confusables": [],
        "articulation": {
            "description": "w 的位置和 u 一样：嘴唇撮圆前突，舌头后缩抬高。它只在开头轻轻一带，很快滑到后面的韵母。单独拉长 w，听起来就是“乌——”。注意别让上牙碰到下唇。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "圆唇后舌起音 w（滑向韵母）",
                    "holdMs": 450,
                    "jaw": 0.1,
                    "lips": {"aperture": 0.15, "rounding": 1.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.95, "backness": 0.95, "stricture": "approximant"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L29_demo_normal_male", "speed": "normal", "voice": "male", "text": "乌"},
            {"ref": "L29_demo_normal_female", "speed": "normal", "voice": "female", "text": "乌"},
        ],
        "quizzes": [
            {
                "id": "L29-Q1",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "乌 wū"}, {"text": "衣 yī"}],
                "answerIndex": 0,
                "stimulusRef": "L29_quiz_Q1",
                "stimulusText": "乌 wū",
                "explanation": "撮圆起音、声音低沉的是“乌”；咧嘴起音、声音细亮的是“衣”。",
            },
            {
                "id": "L29-Q2",
                "prompt": "听词辨音：读到的是哪个字？",
                "options": [{"text": "王 wáng"}, {"text": "黄 huáng"}],
                "answerIndex": 0,
                "stimulusRef": "L29_quiz_Q2",
                "stimulusText": "王 wáng",
                "explanation": "圆唇轻轻起音的是“王”；喉咙先呵一口气出来的是“黄”。",
            },
        ],
        "practice": [
            {"id": "L29-P1", "title": "乌 拉长再加速", "instruction": "拉长发“乌——”，保持圆唇舌位，再越读越短，变成快速的“乌”。", "repeat": 6, "durationSec": None, "bodyCue": "嘴唇撮圆前突，一带而过不拖泥带水。", "stopNote": "不舒服就停止"},
            {"id": "L29-P2", "title": "w 开头连读", "instruction": "连读“乌鸦、问题、晚安”，体会圆唇起音的轻滑。", "repeat": 6, "durationSec": None, "bodyCue": "起音圆而轻，没有摩擦杂音。", "stopNote": "不舒服就停止"},
            {"id": "L29-P3", "title": "王/黄对比", "instruction": "“王—黄”交替读 8 组，手背放在嘴前感受 h 的呵气。", "repeat": 8, "durationSec": None, "bodyCue": "读“王”无风声，读“黄”开头有一股暖气。", "stopNote": "不舒服就停止"},
        ],
        "misconceptions": [
            {"phenomenon": "w 读得像 v，上牙碰到了下唇。", "fix": "可以照镜子确认双唇撮圆、牙齿完全不碰嘴唇。"},
            {"phenomenon": "w、h 混用，“王”读出“黄”的味儿。", "fix": "记住“王”是圆唇直接起音，“黄”要先呵一口气。"},
        ],
        "professional": {
            "description": "w 是汉语拼音的零声母写法，实际为后高圆唇半元音 [w]，功能上是 u 的音节首滑音，声带振动，注意与唇齿擦音 [v] 相区别。",
            "acousticRefs": [
                {"name": "F1（第一共振峰）", "value": "约 250–400 Hz", "note": "同 u 的高后舌位特征，因人而异"},
                {"name": "F2（第二共振峰）", "value": "约 600–850 Hz", "note": "圆唇后位使 F2 低，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：乌",
            "evaluationText": "乌",
            "sampleVoice": "male",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关以圆唇起音与听感对比为主，判别结果供学习参考，不作个体判定。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与起音唇形不到位、牙齿碰唇有关。", "cue": "双唇撮圆，轻轻一带读“乌”。", "practiceStepId": "L29-P1"},
                {"tag": "initial_error", "phenomenon": "本次起音听起来像 v（咬唇）或 h（先呵气）。", "possibleCause": "可能与上齿碰下唇、喉咙先行送气有关。", "cue": "只动双唇撮圆，牙齿不碰嘴唇直接出声。", "practiceStepId": "L29-P1"},
                {"tag": "final_error", "phenomenon": "本次“乌”的韵母听起来跑到了相近的音上。", "possibleCause": "可能与起音后口型变化有关。", "cue": "一带而过之后圆唇保持，u 轻轻延长。", "practiceStepId": "L29-P2"},
                {"tag": "tone_error", "phenomenon": "本次声调与“乌”的一声不够一致，音高走向出现偏差。", "possibleCause": "可能与起音太快、音高没站稳有关。", "cue": "起音轻一点，音高保持平直。", "practiceStepId": "L29-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或中途停住。", "possibleCause": "可能与气量不足有关。", "cue": "吸口气，把“乌”完整读完再停。", "practiceStepId": "L29-P2"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音节。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒。", "practiceStepId": "L29-P2"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
    {
        "id": "L30",
        "order": 30,
        "layer": "syllable",
        "type": "拼读",
        "targetSound": "m+a",
        "pinyin": "ma",
        "representativeChar": "妈",
        "title": "拼读「妈」· 一个 m 一个 a 变出四声",
        "oneLiner": "一个 m 加一个 a，再用声调变出妈、麻、马、骂四个字。",
        "goal": "学会把 m 和 a 顺滑地拼成 ma，并用四个声调稳定读出“妈、麻、马、骂”。",
        "applicableIssues": "适合刚开始学拼读、四声调型不稳的学习者。",
        "tags": ["拼读", "四声", "声调", "滑音连读"],
        "skeletonPublic": True,
        "confusables": ["L01", "L09"],
        "articulation": {
            "description": "先像发 m 一样闭住嘴轻轻哼一声，紧接着张开嘴发 a，中间不停顿，就拼出了“妈”。同一个 ma，音高走法不同就是不同的字：高又平的是妈，往上升的是麻，先降后升的是马，从高落下的是骂。",
            "media": [],
            "sagittal": {
                "keyframes": [
                {
                    "label": "闭唇鼻音 m 起音",
                    "holdMs": 250,
                    "jaw": 0.05,
                    "lips": {"aperture": 0.0, "rounding": 0.0, "contact": "bilabial"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.3, "backness": 0.4, "stricture": "open"},
                    "velum": "lowered",
                    "airflow": "nasal",
                    "voicing": True,
                },
                {
                    "label": "张口发 a 拼出 ma",
                    "holdMs": 500,
                    "jaw": 0.9,
                    "lips": {"aperture": 0.85, "rounding": 0.0, "contact": "none"},
                    "tongueTip": {"place": "rest", "stricture": "open"},
                    "tongueBody": {"height": 0.25, "backness": 0.45, "stricture": "open"},
                    "velum": "raised",
                    "airflow": "oral",
                    "voicing": True,
                },
                ]
            },
        },
        "demos": [
            {"ref": "L30_demo_normal_male", "speed": "normal", "voice": "male", "text": "妈麻马骂"},
            {"ref": "L30_demo_normal_female", "speed": "normal", "voice": "female", "text": "妈麻马骂"},
            {"ref": "L30_demo_slow_female", "speed": "slow", "voice": "female", "text": "妈麻马骂"},
        ],
        "quizzes": [
            {
                "id": "L30-Q1",
                "prompt": "听一听，是哪个声调的 ma？",
                "options": [{"text": "mā 妈"}, {"text": "mà 骂"}],
                "answerIndex": 0,
                "stimulusRef": "L30_quiz_Q1",
                "stimulusText": "mā 妈",
                "explanation": "高而平、像画一条直线的是一声“妈”；从高处落下来的是四声“骂”。",
            },
            {
                "id": "L30-Q2",
                "prompt": "听一听，是哪个声调的 ma？",
                "options": [{"text": "mǎ 马"}, {"text": "má 麻"}],
                "answerIndex": 1,
                "stimulusRef": "L30_quiz_Q2",
                "stimulusText": "má 麻",
                "explanation": "一路往上抬的是二声“麻”；先降下去再拐上来的是三声“马”。",
            },
            {
                "id": "L30-Q3",
                "prompt": "三个声调里，听到的是哪一个？",
                "options": [{"text": "mā 妈"}, {"text": "má 麻"}, {"text": "mà 骂"}],
                "answerIndex": 2,
                "stimulusRef": "L30_quiz_Q3",
                "stimulusText": "mà 骂",
                "explanation": "从高处干脆落下的是四声“骂”；高平是一声“妈”，上扬是二声“麻”。",
            },
        ],
        "practice": [
            {"id": "L30-P1", "title": "闭嘴到张嘴一气呵成", "instruction": "闭唇哼 m 不停顿，直接张嘴滑到 a，连读“妈”6 次。", "repeat": 6, "durationSec": None, "bodyCue": "嘴一开声音立刻变亮，中间没有断开。", "stopNote": "不舒服就停止"},
            {"id": "L30-P2", "title": "四声手势跟读", "instruction": "手跟着画：一声横、二声上扬、三声打钩、四声下劈，边画边读妈、麻、马、骂。", "repeat": 8, "durationSec": None, "bodyCue": "手到哪声音到哪，音高和手势同步。", "stopNote": "不舒服就停止"},
            {"id": "L30-P3", "title": "一声四声对比", "instruction": "“妈—骂”交替读 8 组，体会高平与全降的差别。", "repeat": 8, "durationSec": None, "bodyCue": "一声稳住不动，四声果断落下。", "stopNote": "不舒服就停止"},
            {"id": "L30-P4", "title": "四声连读", "instruction": "慢速连读“妈麻马骂”两遍，再逐渐加速，声调不断档。", "repeat": None, "durationSec": 60, "bodyCue": "换声调时喉咙灵活切换，气息不断。", "stopNote": "头晕就坐下休息"},
        ],
        "misconceptions": [
            {"phenomenon": "四个声调听起来都差不多平，像都在一个音高上。", "fix": "可以先把一声定得高、四声降到底，夸张地读出差距，再慢慢收小。"},
            {"phenomenon": "三声“马”只降不升，听着像半个三声。", "fix": "可以在三声结尾轻轻带回一点上扬，像温和应答时的“好——”。"},
        ],
        "professional": {
            "description": "普通话四声在 ma 音节上的调值常记为：阴平 55（妈）、阳平 35（麻）、上声 214（马）、去声 51（骂）。声母 m 为双唇鼻音，韵母 a 为央低元音，四声由喉部音高（基频 F0）随时间的变化实现。",
            "acousticRefs": [
                {"name": "阴平基频", "value": "约 190–260 Hz 平稳", "note": "女声整体偏高，因人而异"},
                {"name": "阳平基频走向", "value": "起点比阴平低约一成，升至接近阴平高度", "note": "上升幅度因人而异"},
                {"name": "上声基频走向", "value": "先降后升，最低点约 110–180 Hz", "note": "单读时常带回升，因人而异"},
                {"name": "去声基频走向", "value": "从接近阴平高度降至个人音域底部", "note": "下降幅度覆盖全调域，因人而异"},
            ],
            "sources": [
                {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
                {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "声学参考值为常见范围，因人而异，不构成个体正常/异常判定"},
            ],
        },
        "detection": {
            "promptText": "请自然朗读：妈麻马骂",
            "evaluationText": "妈麻马骂",
            "sampleVoice": "female",
            "allowedMetrics": ["score", "pitch_curve", "tone", "initial", "final"],
            "reliabilityNote": "本关声调曲线对比已初步验证，四声判定供学习参考，个体音域差异较大。",
            "fourStepTemplates": [
                {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，四个字的读音与参考示范差距较明显。", "possibleCause": "可能与拼读不连贯、声调不完整有关。", "cue": "先慢后快，把“妈麻马骂”逐字读完整。", "practiceStepId": "L30-P1"},
                {"tag": "initial_error", "phenomenon": "本次声母 m 不够清晰，闭唇鼻音太短或丢失。", "possibleCause": "可能与闭唇停留太短、直接张嘴有关。", "cue": "先闭嘴哼半拍再张开，鼻翼能摸到震动。", "practiceStepId": "L30-P1"},
                {"tag": "final_error", "phenomenon": "本次韵母 a 开口不足，听起来位置偏前偏窄。", "possibleCause": "可能与张嘴幅度不够有关。", "cue": "张大发 a，像打哈欠一样打开再收。", "practiceStepId": "L30-P1"},
                {"tag": "tone_error", "phenomenon": "本次某个字的声调与参考不一致，四声中有字读错。", "possibleCause": "可能与调型记忆不稳、读得太快有关。", "cue": "放慢速度，边画手势边读四声。", "practiceStepId": "L30-P2"},
                {"tag": "missing_syllable", "phenomenon": "本次“妈麻马骂”没有读全，有字漏读。", "possibleCause": "可能与读得太快、跳字有关。", "cue": "一个字一个字读完整，四个字缺一不可。", "practiceStepId": "L30-P4"},
                {"tag": "extra_syllable", "phenomenon": "本次检测到回读或多读了一个字。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一遍四个字，读完安静等 1 秒。", "practiceStepId": "L30-P4"},
                {"tag": "tone_shape_flat", "phenomenon": "四条音高曲线都较平，调域（最高与最低的差距）偏窄。", "possibleCause": "可能与音高变化幅度没拉开、朗读太轻有关。", "cue": "夸张一点：一声读得高而平，四声从高猛降。", "practiceStepId": "L30-P2"},
                {"tag": "tone_start_high", "phenomenon": "某个声调的起点明显高于参考位置。", "possibleCause": "可能与起音习惯偏高、开口前没定调有关。", "cue": "开口前先在心里唱一遍目标调再出声。", "practiceStepId": "L30-P4"},
                {"tag": "tone_start_low", "phenomenon": "某个声调的起点明显低于参考位置。", "possibleCause": "可能与起音太随意、气没准备好有关。", "cue": "深吸一口气，起音稍微抬高一点再读。", "practiceStepId": "L30-P4"},
                {"tag": "tone_rise_insufficient", "phenomenon": "二声“麻”的上升幅度不足，曲线后半段没有抬起来。", "possibleCause": "可能与气息后半段不足有关。", "cue": "结尾再往上抬一点，像疑问的“啊？”。", "practiceStepId": "L30-P4"},
                {"tag": "tone_fall_insufficient", "phenomenon": "四声“骂”的下降幅度不足，结尾没收住。", "possibleCause": "可能与收音太轻、没敢降下去有关。", "cue": "像下楼梯一步踩到底，果断降到底再停。", "practiceStepId": "L30-P3"},
                {"tag": "tone_end_unstable", "phenomenon": "音节结尾音高不稳，出现微微上扬或晃动。", "possibleCause": "可能与收音时喉咙松了、习惯性拖音有关。", "cue": "读完稳住 1 秒，结尾不晃也不拖。", "practiceStepId": "L30-P4"},
            ],
        },
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
        "changeNote": "初版",
    },
]

# 四步反馈全局兜底模板：关卡未覆盖某标签时回退使用，practiceStepId 为 None（后端回退到本关第一步）。
GLOBAL_FOUR_STEP_FALLBACKS = [
    {"tag": "low_overall_score", "phenomenon": "整体相似度分数偏低，读音与参考示范的差距比较明显。", "possibleCause": "可能与口型没做足、发音不稳或环境噪音有关。", "cue": "按本关口型要点先摆好动作，再放慢读一遍。", "practiceStepId": None},
    {"tag": "initial_error", "phenomenon": "本次声母与参考不一致，听起来跑到了相近的音上。", "possibleCause": "可能与发音部位或送气习惯有关。", "cue": "对照本关的部位要点，把开头的动作做清楚。", "practiceStepId": None},
    {"tag": "final_error", "phenomenon": "本次韵母与参考不一致，听起来跑到了相近的音上。", "possibleCause": "可能与口型幅度、舌位偏移有关。", "cue": "把韵母的口型做完整，读完保持 1 秒再收。", "practiceStepId": None},
    {"tag": "tone_error", "phenomenon": "本次声调与参考不一致，音高走向出现偏差。", "possibleCause": "可能与起音太快、调型没站稳有关。", "cue": "先在心里唱一遍目标调，再轻声起音读出来。", "practiceStepId": None},
    {"tag": "missing_syllable", "phenomenon": "本次没有检测到完整读音，声音过短或漏读了字。", "possibleCause": "可能与气量不足、读得太快有关。", "cue": "吸一口气，把评测文字逐字读完整再停。", "practiceStepId": None},
    {"tag": "extra_syllable", "phenomenon": "本次检测到多读或回读了一个音。", "possibleCause": "可能与习惯性回读有关。", "cue": "只读一次，读完安静等 1 秒再提交。", "practiceStepId": None},
    {"tag": "tone_shape_flat", "phenomenon": "音高曲线整体偏平，调域（最高与最低的差距）偏窄。", "possibleCause": "可能与音高变化幅度没拉开、朗读太轻有关。", "cue": "夸张一点读：高的读高、降的降到底，先拉开差距。", "practiceStepId": None},
    {"tag": "tone_start_high", "phenomenon": "声调的起点明显高于参考位置。", "possibleCause": "可能与起音习惯偏高有关。", "cue": "开口前先在心里定好起音高度再出声。", "practiceStepId": None},
    {"tag": "tone_start_low", "phenomenon": "声调的起点明显低于参考位置。", "possibleCause": "可能与起音太随意、气没准备好有关。", "cue": "深吸一口气，起音抬高一点再读。", "practiceStepId": None},
    {"tag": "tone_rise_insufficient", "phenomenon": "上升调（如二声）的上升幅度不足，曲线后半段没有抬起来。", "possibleCause": "可能与气息后半段不足有关。", "cue": "结尾再往上抬一点，像疑问的“啊？”。", "practiceStepId": None},
    {"tag": "tone_fall_insufficient", "phenomenon": "下降调（如四声）的下降幅度不足，结尾没收住。", "possibleCause": "可能与收音太轻、没敢降下去有关。", "cue": "像下楼梯一步踩到底，果断降到底再停。", "practiceStepId": None},
    {"tag": "tone_end_unstable", "phenomenon": "音节结尾音高不稳，出现微微上扬或晃动。", "possibleCause": "可能与收音时喉咙松了、习惯性拖音有关。", "cue": "读完稳住 1 秒，结尾不晃也不拖。", "practiceStepId": None},
    {"tag": "formant_deviation", "phenomenon": "本次读音的共振峰位置偏离常见参考区。", "possibleCause": "可能与口型幅度、舌位唇形偏差有关。", "cue": "对照本关口型要点再发一次，声音特征会更接近。", "practiceStepId": None},
]

# 录音校准文本（覆盖六个单韵母且有音高起伏，勿随意改动版本号）。
CALIBRATION_TEXT = {
    "textVersion": "v1",
    "text": "妈、坡、车、米、布、女、妈、麻、马、骂",
    "syllables": ["妈", "坡", "车", "米", "布", "女", "妈", "麻", "马", "骂"],
}

ARTICLE_CATEGORIES = ["气", "声", "口型"]

ARTICLES = [
    {
        "slug": "breath-where-from",
        "title": "气从哪里来",
        "category": "气",
        "summary": "说话的声音靠气流推动。这一篇带你找到气息的源头，让说话更省力、声音更稳。",
        "markdown": """## 声音的第一推动力

我们张嘴就能说话，好像声音是“喉咙里自己冒出来的”。其实每一次说话都是一口气在推：肺里的气向上流过喉咙里的声带，声带振动发出嗓音，再经过口腔的塑造，变成一个个字。

所以气不够的时候，声音就容易发飘、发紧，说几句话就累。

## 气放在哪里

吸气时不要使劲抬肩膀，而是想象腰腹一圈像气球一样轻轻鼓起；呼气时这一圈慢慢回收，把气变成细细的一股送出来。这样的一口气，够我们从容说完一整句话。

::audio{ref="article_breath_1" text="啊（平稳延长）"}

## 试一次

把手放在腰的两侧，用鼻子慢慢吸气，感觉手掌被轻轻推开；再用嘴匀匀地把气送出来，发一个长长的“啊”。声音稳，说明气稳；声音抖，多半是气流忽大忽小。

## 带着稳稳的气去闯关

先把气息稳住，再去关卡里练具体的音，会事半功倍。下面几关都和开口、圆唇的长音有关，正好用得上这一篇的练习。

::levels{ids="L01,L05,L30"}

```pro
声道与气流
气流自肺经气管、喉部进入声道（咽腔—口腔—鼻腔）。声带振动产生嗓音，气流同时受下颌、唇、舌的调制形成不同语音。说话呼吸的特点是呼气期长、吸气期短，腰腹式呼吸能提供更平稳的气压支撑，使长音和长句更稳定。
```""",
        "demoRef": "article_breath_1",
        "demoText": "啊（平稳延长）",
        "practice": [
            {"title": "闻花香", "instruction": "想象闻一朵花，用鼻子慢慢吸气 3 秒，腰腹鼓起，再用嘴匀匀呼气 5 秒，重复 5 次。"},
            {"title": "数枣", "instruction": "一口气匀速数“一个枣、两个枣、三个枣……”，看能数到几，每天多加一个。"},
        ],
        "references": [
            {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "呼吸练习为一般性动作建议，如有呼吸系统不适请咨询医生"},
        ],
        "relatedLevelIds": ["L01", "L05", "L30"],
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
    },
    {
        "slug": "steady-breath-line",
        "title": "把一口气变成一条线",
        "category": "气",
        "summary": "长音不稳多半是气流不稳。两个小练习，帮你把一口气变成均匀的一条线。",
        "markdown": """## 为什么声音会抖

拉长一个音的时候，有人声音匀匀的像一条直线，有人却忽大忽小像波浪。差别通常不在嗓子，而在送气：气流忽强忽弱，声音就跟着晃。

把气变成均匀的一条线，长音自然就稳了。

## 练习一：匀速吹气

撮圆嘴唇，像吹热汤一样匀匀吹气 5 秒，目标是气流细而稳，一秒钟不多不少。可以用手背感受：风应该一直一样大。

## 练习二：长音走直线

::audio{ref="article_breath_2" text="啊（5 秒长音）"}

吸好气，发一个“啊——”拉长 5 秒，想象声音是笔画出来的一条直线。如果中间晃了，别停，下一口气再画一遍。

## 到关卡里用起来

下面的关卡都有“长音”步骤，正好用这条“线”去完成：声音从头到尾一样稳，才算过关。

::levels{ids="L02,L06,L30"}

```pro
气流与长音的稳定性
持续元音的基频和振幅起伏，与呼气压的波动直接相关。腹式呼吸通过膈肌与腹肌的对抗提供较恒定的呼气压，可减小基频微扰（jitter）与振幅微扰（shimmer），使长音更平稳。
```""",
        "demoRef": "article_breath_2",
        "demoText": "啊（5 秒长音）",
        "practice": [
            {"title": "吹一条线", "instruction": "撮唇匀速吹气 5 秒，手背感受风力恒定，重复 5 次。"},
            {"title": "长音直线", "instruction": "分别用 a、o、i 各拉一个 5 秒长音，追求从头到尾一样稳。"},
        ],
        "references": [
            {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "练习强度为一般性建议，头晕时立即坐下休息"},
        ],
        "relatedLevelIds": ["L02", "L06", "L30"],
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
    },
    {
        "slug": "what-is-tone",
        "title": "声调：中文里的音乐",
        "category": "声",
        "summary": "同样的音，音高走向不同就是不同的字。认识普通话四个声调的“形状”。",
        "markdown": """## 一个音，四个字

先听一句话：

::audio{ref="article_voice_1" text="妈、麻、马、骂"}

这四个字的声母都是 m，韵母都是 a，唯一不同的是音高的走法——这就是声调。声调是中文的“音乐”：音节像音符，声调决定它怎么唱。

## 四个声调的形状

- 一声（妈）：高而平，像一条水平线。
- 二声（麻）：从中往上升，像提问时上扬的尾音。
- 三声（马）：先降后升，像画一个对钩。
- 四声（骂）：从高处落下，像果断地跺一下脚。

## 用耳朵先认识它们

不用急着读准，先多听几遍，能听出“平、升、拐弯、降”四种走向，就已经赢在起点了。想动手练，去下面的拼读关卡。

::levels{ids="L30,L09"}

```pro
普通话声调的调值
汉语语音学传统用五度标记法描写调值：阴平 55、阳平 35、上声 214、去声 51。声调由音节基频（F0）随时间的轮廓实现，与声母韵母相对独立。上声在词语中常发生连读变调（如两个上声相连时前字变阳平）。
```""",
        "demoRef": "article_voice_1",
        "demoText": "妈、麻、马、骂",
        "practice": [
            {"title": "听调举手", "instruction": "请家人随机读妈麻马骂中的一个字，听到一声举左手、四声举右手，二声三声分别握拳和比钩。"},
            {"title": "跟读四声", "instruction": "跟着示范音频慢速跟读“妈麻马骂”3 遍，注意音高的走向。"},
        ],
        "references": [
            {"title": "《汉语拼音方案》", "source": "1958 年全国人民代表大会批准公布", "license": "公开法令文本，仅作教学参考引用", "boundary": "调值为教学通说，个体音域差异较大，不构成个体正常/异常判定"},
        ],
        "relatedLevelIds": ["L30", "L09"],
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
    },
    {
        "slug": "tone-gesture-map",
        "title": "用手势带出四个声调",
        "category": "声",
        "summary": "一声平、二声升、三声拐弯、四声降。用手比着读，声调立刻清楚。",
        "markdown": """## 手是最好的调音师

读声调最容易犯的错，是嘴上念着“三声”，音高却没拐弯。这时候不妨用手来带：手往哪走，音高就往哪走，身体的感觉比道理管用。

## 四个手势

- 一声：手掌在肩膀高度横向划一条平线——“妈”。
- 二声：手掌从胸前向斜上方推——“麻”。
- 三声：手掌先向下切再往上挑，画个对钩——“马”。
- 四声：手掌从高处果断下劈——“骂”。

跟着示范，边画边读：

::audio{ref="article_voice_2" text="妈麻马骂（跟手势读）"}

## 为什么有用

手势把看不见的音高变成了看得见的动作，读的时候眼睛跟着手，喉咙自然跟着调整。很多播音员练习声调也用类似的动作提示。

## 去拼读关试试

下面的关卡会把四个声调放进同一个音节里反复对比，带上你的手势去闯关吧。

::levels{ids="L30,L01"}

```pro
声调的动作提示与习得
研究表明，伴随 pitch 方向的手势（音高手势）能帮助学习者建立调型的空间表征，对声调范畴感知和产出均有促进作用。手势提示是教学辅助手段，并非声学测量方法。
```""",
        "demoRef": "article_voice_2",
        "demoText": "妈麻马骂（跟手势读）",
        "practice": [
            {"title": "手势四声", "instruction": "边画四个手势边读“妈麻马骂”，每天 3 遍，先慢后快。"},
            {"title": "单字换调", "instruction": "用“妈”轮流换四个声调读，每换一个调换一个手势。"},
        ],
        "references": [
            {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "手势为一般教学辅助方法，效果因人而异"},
        ],
        "relatedLevelIds": ["L30", "L01"],
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
    },
    {
        "slug": "find-comfortable-pitch",
        "title": "找到自己舒服的音高",
        "category": "声",
        "summary": "声音发紧、越说越累，常常是音高不合适。三个小办法找到属于自己的“舒服调”。",
        "markdown": """## 舒服的音高在哪

每个人都有自己舒服的音高区间，大概就在平时自然说话的位置。可惜的是，紧张或者模仿别人的时候，我们常常不自觉地压低或抬高嗓子，说话很快就累，声音也不好听。

## 三个小办法

1. 叹气起音：轻轻叹一声“唉——”，叹气结束的那个音高，就很接近你的自然音区。
2. 早晨的“嗯”：早上醒来舒适地哼一声“嗯”，那也是舒服的位置。
3. 说给自己听：想象和熟人聊天，自然说一句“今天天气不错”，别表演。

::audio{ref="article_voice_3" text="啊（自然起音并延长）"}

## 保持住，别滑走

找到舒服音高后，读长句时也尽量保持在附近，不要越说越高或越压越低。嗓子不较劲，声音才耐久。

## 到关卡里验证

下面的关卡都带音高曲线，读一句看看自己的曲线是不是平稳地待在舒服区间。

::levels{ids="L01,L30,L28"}

```pro
嗓音音高与喉部状态
自然言语的基频由声带长度、张力与质量决定，因性别、年龄差异很大。刻意压低或抬高音高会增加喉部肌肉负荷，长期可能导致嗓音疲劳。如出现持续嗓音不适，建议咨询专业医生。
```""",
        "demoRef": "article_voice_3",
        "demoText": "啊（自然起音并延长）",
        "practice": [
            {"title": "叹气找调", "instruction": "轻轻叹“唉——”三次，记住结尾的音高，在这个高度说一句“你好，我在这里”。"},
            {"title": "舒服长音", "instruction": "用叹气找到的音高发“啊——”5 秒，全程保持同一高度。"},
        ],
        "references": [
            {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "本文为一般性嗓音使用建议，持续嗓音不适请咨询医生"},
        ],
        "relatedLevelIds": ["L01", "L30", "L28"],
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
    },
    {
        "slug": "mouth-shape-changes-sound",
        "title": "口型一变，声音就变",
        "category": "口型",
        "summary": "同样的嗓子，嘴张大是 a，撮圆是 u。口型是看得见、也听得见的动作。",
        "markdown": """## 嘴巴是声音的调音台

嗓子发出的声音只是一团“原材料”，真正把它调成 a、o、i、u 的，是嘴巴：下巴的开合、嘴唇的圆扁、舌头的高低前后，三样一变，声音就完全不同。

先听一组对比：

::audio{ref="article_mouth_1" text="啊、噢、衣、乌"}

四个音用的是同一副嗓子，唯一变化的就是口型。

## 两个最容易体会的旋钮

- 开合：嘴张到最大是“啊”，几乎合上是“乌”。
- 圆扁：嘴角展开是“衣”，嘴唇撮圆是“乌”。

## 照着镜子玩一遍

对着镜子，慢慢把嘴从张到最大收到最小，再从咧嘴滑到撮圆，同时发声——你会听到声音像调光台灯一样连续变化。玩过这一遍，“口型决定声音”就不再是知识，而是体验。

## 去关卡里精修

下面四个关卡分别练四种口型，带着这篇的体验去，会觉得每个音都有明确的手感。

::levels{ids="L01,L02,L04,L05"}

```pro
 vowel 的口型参数与声学
元音的音色由声道形状决定，可用下颌开度、唇形（圆/展）、舌位（高低、前后）描述，声学上对应共振峰 F1（主要受开度与舌高影响）与 F2（主要受舌位前后与唇形影响）的变化。
```""",
        "demoRef": "article_mouth_1",
        "demoText": "啊、噢、衣、乌",
        "practice": [
            {"title": "口型滑音", "instruction": "对镜子连续发声，把嘴从“啊”慢慢收到“乌”，来回 5 次，听声音连续变化。"},
            {"title": "圆扁开关", "instruction": "保持舌头不动，嘴角咧开发 i，再撮圆变成 ü，来回 5 次。"},
        ],
        "references": [
            {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "口型描述为教学简化模型，个体解剖差异客观存在"},
        ],
        "relatedLevelIds": ["L01", "L02", "L04", "L05"],
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
    },
    {
        "slug": "mirror-three-checkpoints",
        "title": "对着镜子练：看哪三个地方",
        "category": "口型",
        "summary": "下巴、嘴唇、（看得见的）舌尖，镜子能帮你发现一半的发音问题。",
        "markdown": """## 镜子是最好的陪练

很多发音问题，自己听不出来，但一照镜子就看见了：嘴没张开、嘴唇没圆、舌尖翘错了地方。练习时在旁边放一面小镜子，时不时瞄一眼，效率会高很多。

## 检查点一：下巴

发“啊”这类开口音时，下巴应该明显下沉。镜子里的嘴几乎没动，声音多半是扁的。

## 检查点二：嘴唇

圆唇音（乌、鱼、波）嘴唇要收圆，展唇音（衣、鹅）嘴角要展开。对着镜子看：该圆的圆了吗？该展的展了吗？

## 检查点三：看得见的舌尖

平翘舌（资/知、思/诗）最值得照镜子：发平舌时能看见舌尖平伸贴近上牙，发翘舌时舌尖卷起离开下牙。一个“看得见”，一个“藏起来”，对比非常直观。

跟着示范做一轮：

::audio{ref="article_mouth_2" text="啊、摸、知"}

## 提示

镜子只负责“看见”，听感还要靠耳朵。看一眼、听一句，两边对照，进步最快。

::levels{ids="L01,L09,L21"}

```pro
视觉反馈与发音学习
发音教学的视觉反馈（镜面观察、声道动画）能帮助学习者建立正确的发音部位表征，尤其对唇形、下颌开度、舌位前后等可观察或可图示的特征有效。视觉反馈是辅助手段，最终仍需以听辨和产出的准确性为准。
```""",
        "demoRef": "article_mouth_2",
        "demoText": "啊、摸、知",
        "practice": [
            {"title": "三处巡检", "instruction": "对着镜子各读“啊、乌、知”三遍，每次检查下巴、嘴唇、舌尖是否到位。"},
            {"title": "平翘对照", "instruction": "对着镜子交替读“思—诗”各 6 次，观察舌尖从平伸到卷起的变化。"},
        ],
        "references": [
            {"title": "《语音学教程》（林焘、王理嘉）", "source": "北京大学出版社", "license": "公开出版物，仅作教学参考引用", "boundary": "镜面观察为一般练习建议，不能替代专业听辨评测"},
        ],
        "relatedLevelIds": ["L01", "L09", "L21"],
        "author": "内容组（示例种子）",
        "license": "内部演示授权",
    },
]

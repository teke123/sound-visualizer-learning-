import type { PublishedUnit } from './coreUnits'

/**
 * 发音库页面的静态数据源。
 *
 * 为什么需要它：后端未启动时 /library 拿不到任何数据，页面卡片区会一片空白。
 * 这份数据从 backend/database.py 的 CORE_UNITS 前 12 条搬运而来（顺序与
 * coreUnits.ts 的 CORE_UNIT_IDS 一致），让页面在无后端时也能展示内容。
 *
 * 后端接口稳定后，页面应改回读取接口数据。
 */

/** 只列出每个单元真正不同的字段 */
const RAW_UNITS = [
  {
    id: 'a',
    pinyin: 'a',
    character: '啊',
    category: '韵母',
    conclusion: 'a 是开放元音：嘴巴自然张大，舌头平放，声音响亮通畅',
    detail: '上下齿距离约两指宽，舌位最低最前，气流不受阻碍。口腔开口度与 F1 共振峰直接相关。',
  },
  {
    id: 'i',
    pinyin: 'i',
    character: '一',
    category: '韵母',
    conclusion: 'i 是高前元音：舌面抬向硬腭，嘴角向两侧展开',
    detail: '舌头前部抬高接近硬腭，上下齿几乎并拢，双唇呈微笑状。F2 共振峰高（约2400Hz）。',
  },
  {
    id: 'u_u',
    pinyin: 'u/ü',
    character: '五/鱼',
    category: '韵母',
    conclusion: 'u 和 ü 都是圆唇元音，但舌位不同：u 舌位靠后，ü 舌位靠前',
    detail: 'u 舌根抬高、唇最圆；ü 舌面抬向硬腭同时保持圆唇。可用 wu/yū 对比感受。',
  },
  {
    id: 'm',
    pinyin: 'm',
    character: '妈',
    category: '声母',
    conclusion: 'm 是双唇鼻音：双唇闭合，软腭下垂，声音从鼻腔透出',
    detail: '双唇自然闭合，声带振动，气流大部分从鼻腔流出。手放鼻前可感受到气流。',
  },
  {
    id: 'b_p',
    pinyin: 'b/p',
    character: '八/趴',
    category: '声母',
    conclusion: 'b 与 p 的差别是送气：b 不送气，p 送气（有显著气流喷出）',
    detail: '两者都是双唇清塞音。把手背放嘴前发 ba（无气流）与 pa（有气流）对比感受。',
  },
  {
    id: 'd_t',
    pinyin: 'd/t',
    character: '大/他',
    category: '声母',
    conclusion: 'd 与 t 的差别是送气：d 不送气，t 送气',
    detail: '舌尖抵住上齿龈后突然放开。发 da 时无明显气流，发 ta 时有明显气流冲出。',
  },
  {
    id: 'n_l',
    pinyin: 'n/l',
    character: '那/辣',
    category: '声母',
    conclusion: 'n 是鼻音、l 是边音：发 n 时气流走鼻腔，发 l 时气流从舌两侧流出',
    detail: 'n：舌尖抵上齿龈、软腭下垂（可捏鼻验证）；l：舌尖抵上齿龈但软腭抬起，气流从舌侧通过。',
  },
  {
    id: 'g_k',
    pinyin: 'g/k',
    character: '歌/可',
    category: '声母',
    conclusion: 'g 与 k 的差别是送气：g 不送气，k 送气',
    detail: '舌根抬起抵住软腭。发 ga 无气流、发 ka 有明显气流。',
  },
  {
    id: 'j_q_x',
    pinyin: 'j/q/x',
    character: '机/七/西',
    category: '声母',
    conclusion: 'j、q、x 是舌面音：舌面前部抬起接近硬腭；j 不送气、q 送气、x 是擦音',
    detail: 'j/q 成阻部位相同（一送气一不送气），x 留窄缝摩擦成声。注意不要发成 z/c/s 或 zh/ch/sh。',
  },
  {
    id: 'z_zh',
    pinyin: 'z/zh',
    character: '字/只',
    category: '声母',
    conclusion: 'z（平舌）舌尖抵下齿背，zh（翘舌）舌尖卷向上颚前部',
    detail: 'z/c/s 舌尖平放抵下齿背；zh/ch/sh/r 舌尖卷起抵硬腭前部。这是最常见的辨音难点。',
  },
  {
    id: 'ma_tone',
    pinyin: 'mā/má/mǎ/mà',
    character: '妈/麻/马/骂',
    category: '声调',
    conclusion: '四声是音高走向的变化：阴平高平、阳平上升、上声先降后升、去声急降',
    detail: '妈mā（55高平）、麻má（35上升）、马mǎ（214先降后升）、骂mà（51急降）。可用手划轨迹辅助。',
  },
  {
    id: 'ma',
    pinyin: 'mā',
    character: '妈',
    category: '声母',
    conclusion: '「妈」完整闭环单元：声母m + 韵母a + 第一声，完成学习-录音-结果-练习-再录音',
    detail: '先发双唇鼻音 m，随即滑向开口元音 a，音高保持高平。',
  },
]

/** 补上所有单元都相同的字段，拼成完整的 PublishedUnit */
export const STATIC_UNITS: PublishedUnit[] = RAW_UNITS.map((u, i) => ({
  ...u,
  description: '',
  mistakes: [],
  steps: [],
  related: [],
  status: 'published',
  verified: true,
  order: i + 1,
}))

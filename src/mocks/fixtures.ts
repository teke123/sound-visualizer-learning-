/**
 * MSW 固定样例数据（用固定样例关卡 L01、L07、L30–L33（ma 四声）
 * —— 外加 L08/L13/L14 支撑易混对 —— 开发与验收结构）。
 */
import type {
  ArticleCategory,
  ArticleDetail,
  ArticleSummary,
  LevelDetail,
  LevelSkeleton,
  LevelSummary,
} from '@/api'


/* --------------------------------- 关卡 ---------------------------------- */

interface LevelSeed {
  id: string
  order: number
  layer: LevelSummary['layer']
  type: LevelSummary['type']
  targetSound: string
  pinyin: string
  representativeChar?: string
  title: string
  promptText: string
}

/** ma 四声拼读关：构形内容走真实形态（2D 交互动画 + 三维模型），与后端种子同口径 */
const MA_LEVEL_IDS = new Set(['L30', 'L31', 'L32', 'L33'])

const SEEDS: LevelSeed[] = [
  {
    id: 'L01',
    order: 1,
    layer: 'vowel',
    type: '单韵母',
    targetSound: 'a',
    pinyin: 'ā',
    representativeChar: '啊',
    title: '单韵母 a：把嘴张大',
    promptText: '请朗读：「啊」',
  },
  {
    id: 'L07',
    order: 7,
    layer: 'initial',
    type: '声母',
    targetSound: 'b',
    pinyin: 'b',
    representativeChar: '波',
    title: '声母 b：双唇一抿就放开',
    promptText: '请朗读：「波」',
  },
  {
    id: 'L08',
    order: 8,
    layer: 'initial',
    type: '声母',
    targetSound: 'p',
    pinyin: 'p',
    representativeChar: '坡',
    title: '声母 p：和 b 差在一口气',
    promptText: '请朗读：「坡」',
  },
  {
    id: 'L13',
    order: 13,
    layer: 'initial',
    type: '声母',
    targetSound: 'n',
    pinyin: 'n',
    representativeChar: '呢',
    title: '声母 n：舌尖顶住上齿龈',
    promptText: '请朗读：「呢」',
  },
  {
    id: 'L14',
    order: 14,
    layer: 'initial',
    type: '声母',
    targetSound: 'l',
    pinyin: 'l',
    representativeChar: '勒',
    title: '声母 l：舌尖轻抵、气从两边走',
    promptText: '请朗读：「勒」',
  },
  {
    id: 'L30',
    order: 30,
    layer: 'syllable',
    type: '拼读',
    targetSound: 'mā',
    pinyin: 'mā',
    representativeChar: '妈',
    title: '拼读「妈」：m 和 a 连起来',
    promptText: '请朗读：「妈」',
  },
  {
    id: 'L31',
    order: 31,
    layer: 'syllable',
    type: '拼读',
    targetSound: 'má',
    pinyin: 'má',
    representativeChar: '麻',
    title: '拼读「麻」：阳平从中间升上去',
    promptText: '请朗读：「麻」',
  },
  {
    id: 'L32',
    order: 32,
    layer: 'syllable',
    type: '拼读',
    targetSound: 'mǎ',
    pinyin: 'mǎ',
    representativeChar: '马',
    title: '拼读「马」：上声先降后升',
    promptText: '请朗读：「马」',
  },
  {
    id: 'L33',
    order: 33,
    layer: 'syllable',
    type: '拼读',
    targetSound: 'mà',
    pinyin: 'mà',
    representativeChar: '骂',
    title: '拼读「骂」：去声从高处落下来',
    promptText: '请朗读：「骂」',
  },
]

export const PUBLISHED_IDS = SEEDS.map((seed) => seed.id)

/** 地图骨架：其余关卡仅身份 + 未开放（模拟 skeletonPublic 标记） */
export const SKELETONS: LevelSkeleton[] = [
  { id: 'L02', order: 2, layer: 'vowel', targetSound: 'o', availability: 'closed' },
  { id: 'L03', order: 3, layer: 'vowel', targetSound: 'e', availability: 'closed' },
  { id: 'L04', order: 4, layer: 'vowel', targetSound: 'i', availability: 'closed' },
  { id: 'L05', order: 5, layer: 'vowel', targetSound: 'u', availability: 'closed' },
  { id: 'L06', order: 6, layer: 'vowel', targetSound: 'ü', availability: 'closed' },
  { id: 'L15', order: 15, layer: 'initial', targetSound: 'g', availability: 'closed' },
  { id: 'L21', order: 21, layer: 'initial', targetSound: 'zh', availability: 'closed' },
]

/** 易混对（双方均已开放才展示） */
export const CONFUSABLE_PAIRS = [
  { a: 'L07', b: 'L08' },
  { a: 'L13', b: 'L14' },
]

export const LEVEL_SUMMARIES: LevelSummary[] = SEEDS.map((seed) => ({
  id: seed.id,
  order: seed.order,
  layer: seed.layer,
  type: seed.type,
  targetSound: seed.targetSound,
  pinyin: seed.pinyin,
  representativeChar: seed.representativeChar,
  title: seed.title,
  demoMediaId: `aud-${seed.id}-demo`,
  availability: 'open' as const,
}))

export const LEVEL_DETAILS: Record<string, LevelDetail> = Object.fromEntries(
  SEEDS.map((seed, index) => {
    const prev = SEEDS[index - 1]
    const next = SEEDS[index + 1]
    const isVowel = seed.layer === 'vowel'
    return [
      seed.id,
      {
        id: seed.id,
        order: seed.order,
        layer: seed.layer,
        type: seed.type,
        targetSound: seed.targetSound,
        pinyin: seed.pinyin,
        representativeChar: seed.representativeChar,
        title: seed.title,
        nav: {
          prev: prev?.id ?? null,
          next: next?.id ?? null,
          confusables:
            seed.id === 'L07' ? ['L08'] : seed.id === 'L08' ? ['L07'] : seed.id === 'L13' ? ['L14'] : seed.id === 'L14' ? ['L13'] : [],
        },
        articulation: MA_LEVEL_IDS.has(seed.id)
          ? {
              // ma 四声关：真实内容形态 —— 2D 正中矢状面交互动画（内置组件渲染）+ 三维模型
              media: [
                {
                  mediaId: `anim-${seed.id}-ma-sagittal`,
                  kind: 'animation' as const,
                  component: 'ma-sagittal',
                  altText: 'ma 正中矢状面发音动画（可播放、可调速）',
                },
              ],
              model3dMediaId: `model3d-${seed.id}-mouth`,
            }
          : {
              media: [
                {
                  mediaId: `img-${seed.id}-mouth`,
                  kind: 'image' as const,
                  altText: `${seed.title}：口型正视图示意`,
                },
              ],
              model3dMediaId: `model3d-${seed.id}-mouth`,
            },
        demos: (['FV1', 'FV2', 'FV3', 'MV1', 'MV2', 'MV3'] as const).map((spk) => ({
          mediaId: `aud-${seed.id}-demo-${spk}`,
          speed: 'normal' as const,
          voice: spk,
        })),
        quizzes: [
          {
            id: `${seed.id}-q1`,
            stimulusMediaId: `aud-${seed.id}-quiz1`,
            prompt: '占位题干。',
            options: [{ text: '占位选项 A' }, { text: '占位选项 B' }],
            answerIndex: 0,
            explanation: '占位解析。',
          },
        ],
        practice: [
          `跟着示范音读「${seed.representativeChar ?? seed.targetSound}」三遍，注意听自己的发音和示范像不像。`,
          `放慢速度再读两遍，体会${seed.type === '声母' ? '气流' : '口型'}的变化。`,
        ],
        professional: {
          description: '占位专业与声学说明。',
        },
        detection: {
          promptText: seed.promptText,
          sampleMediaId: `aud-${seed.id}-demo`,
          allowedMetrics: isVowel
            ? ['score', 'tone_curve', 'formants', 'phenomena', 'four_steps']
            : ['score', 'tone_curve', 'phenomena', 'four_steps'],
        },
      } satisfies LevelDetail,
    ]
  }),
)

/* --------------------------------- 文章 ---------------------------------- */

export const ARTICLE_CATEGORIES: ArticleCategory[] = [
  { id: 1, name: '气' },
  { id: 2, name: '声' },
  { id: 3, name: '口型' },
]

export const ARTICLES: ArticleDetail[] = [
  {
    slug: 'where-air-comes-from',
    title: '气从哪里来：说话的动力',
    category: '气',
    summary: '说话的声音，起点是一口平稳呼出的气。',
    demo: { mediaId: 'aud-L01-demo', text: '啊' },
    markdown: [
      '## 一口气，一串音',
      '',
      '说话前，肺里存着一口气；说话时，这口气稳定地流出来。气流就像水流，没有它，再好的口型也发不出声。',
      '',
      '::: practice',
      '1. 坐直，用鼻子慢慢吸气 4 拍',
      '2. 用嘴匀速吹气 8 拍，手掌放在嘴前感受气流稳定',
      '3. 换成轻轻发「嘶——」，保持气流不断',
      ':::',
      '',
      '::: audio mediaId=aud-L01-demo',
      '示范：平稳送气后发出的 a',
      ':::',
      '',
      '::: pro',
      '语音学上把这称为呼气动能与声门下压的配合；平稳的声门下压是稳定音高与音量的前提。',
      ':::',
    ].join('\n'),
    practice: [
      { title: '匀速吹气', instruction: '坐直慢吸 4 拍，匀速吹气 8 拍' },
      { title: '嘶音保持', instruction: '轻发「嘶——」10 秒保持气流稳定' },
    ],
    references: [
      { title: '呼吸与发声（示例资料）', source: '教学团队', license: '仅本站教学使用' },
    ],
    relatedLevels: [{ levelId: 'L01', available: true }],
  },
  {
    slug: 'how-voice-works',
    title: '声音怎么响：喉咙里的小马达',
    category: '声',
    summary: '声带一开一合，气流就变成了带着音高的声音。',
    demo: { mediaId: 'aud-L07-demo', text: '波' },
    markdown: [
      '## 摸得到的振动',
      '',
      '把手轻轻放在喉咙上，说「啊——」。手指能感到轻微的抖动：这是声带在一张一合地振动。振得快，音高就高；振得慢，音高就低。',
      '',
      '::: audio mediaId=aud-L07-demo',
      '示范：声带振动的 b（不送气）',
      ':::',
      '',
      '::: image mediaId=img-L07-mouth alt=双唇闭合示意',
      '图：双唇闭合的口型',
      ':::',
      '',
      '::: levels ids=L01,L07',
      ':::',
    ].join('\n'),
    practice: [
      { title: '感受振动', instruction: '手放喉咙发「啊——」，感受振动' },
      { title: '对比清浊', instruction: '对比发「嘶」（不振动）与「啊」（振动）' },
    ],
    references: [
      { title: '发声原理（示例资料）', source: '教学团队', license: '仅本站教学使用' },
    ],
    relatedLevels: [{ levelId: 'L07', available: true }],
  },
  {
    slug: 'mouth-shapes',
    title: '嘴和舌头怎么摆：声音的调色盘',
    category: '口型',
    summary: '同样的气流，过不同的口型，就成了不同的音。',
    demo: { mediaId: 'aud-L13-demo', text: '呢' },
    markdown: [
      '## 看得见的差别',
      '',
      '嘴巴张大是 a，拢圆是 u；舌尖顶上去是 n、l，舌面抬起来是 j、q、x。口腔形状一变，声音跟着变——这是「看得见的声音」的由来。',
      '',
      '::: image mediaId=img-L13-mouth alt=舌尖抵上齿龈示意',
      '图：n 的舌尖位置',
      ':::',
      '',
      '::: audio mediaId=aud-L13-demo',
      '示范：n',
      ':::',
      '',
      '::: practice',
      '1. 张大发 a → 拢圆发 u，来回 5 次',
      '2. 舌尖抵上齿龈发 n，再轻抵发 l，各 5 次',
      ':::',
    ].join('\n'),
    practice: [
      { title: '口型轮换', instruction: 'a / u 口型来回 5 次' },
      { title: '舌尖位置', instruction: 'n / l 舌尖位置轮换各 5 次' },
    ],
    references: [
      { title: '普通话口型图集（示例）', source: '教学团队', license: '仅本站教学使用' },
    ],
    relatedLevels: [
      { levelId: 'L01', available: true },
      { levelId: 'L13', available: true },
      { levelId: 'L14', available: true },
    ],
  },
]

export const ARTICLE_SUMMARIES: ArticleSummary[] = ARTICLES.map((article) => ({
  slug: article.slug,
  title: article.title,
  category: article.category,
  summary: article.summary,
}))

/* -------------------------------- 标定文本 ------------------------------- */

export const CALIBRATION_TEXT = {
  text: '啊哦鹅衣乌迂，呢勒波坡妈。学习普通话，声音看得见。',
  textVersion: 'cal-v1',
}


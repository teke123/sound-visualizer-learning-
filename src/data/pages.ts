/**
 * 页面登记表（P01–P11）——页号、路由与文案位的唯一登记处
 * ---------------------------------------------------------------------------
 * 口径来源：《docs/srs/02-内容模型与信息架构》4.1 页面清单与编号、4.2 一级导航：
 * P01 首页 / P02 搜索 / P03 发音地图 / P04 发音原理 / P05 关卡页（/learn）、
 * P06 发音库 / P07 专业资料 / P08 检测中心（/test）、P09 结果、P10 声音档案、P11 账号。
 *
 * 规则：
 *   - 页号 P01–P11（后台 /admin 用 'ADMIN'，不计入编号序列）；
 *   - 每条路由的 meta.pageCode 由 router 经 PAGE_CODE_BY_ROUTE_NAME 自动写入，
 *     页面/验收清单不要再手写页号，避免「文档一套、代码一套」；
 *   - 文案位（key 固定）：页面只消费 PAGE_COPY[code]，不要在页面里散写提示语；
 *     文案定稿口径 = SRS（FR-202 四主按钮文案、07 章边界句等）。
 */

export interface PageCopySlots {
  /** 一句话说明：这一页用来做什么 */
  subtitle: string
  /** 加载中 */
  loading: string
  /** 空状态（尚未有内容，但页面本身可用） */
  empty: string
  /** 加载失败（后端不可用） */
  error: string
  /** 未开放（按 SRS 分级开放规则，不算整版失败，也不得写成「敬请期待」凑数） */
  unopened: string
  /** 主要动作按钮 */
  cta: string
}

export interface PageDef {
  /** 页号 P01–P11（后台 /admin 用 'ADMIN'） */
  code: string
  /** 路由 path（多段路由用数组） */
  paths: string[]
  /** 路由 name（与 router 保持一致） */
  name: string
  /** 同一页号下的其它路由 name（如关卡页：levels 列表 + level 单关） */
  routeNames?: string[]
  /** 页面标题 */
  title: string
  /** 是否进入一级导航（SRS 4.2） */
  nav: boolean
  /** 图标（Element Plus 图标名） */
  icon: string
  copy: PageCopySlots
}

export const PAGES: PageDef[] = [
  {
    code: 'P01',
    paths: ['/'],
    name: 'home',
    title: '首页',
    nav: true,
    icon: 'HomeFilled',
    copy: {
      subtitle: '看懂口型、听清示范、跟着练、录音比较。',
      loading: '正在准备练习内容…',
      empty: '还没有已发布的关卡。',
      error: '没连上服务器，请检查后端是否启动。',
      unopened: '这一部分还没开放。',
      cta: '开始',
    },
  },
  {
    code: 'P02',
    paths: ['/search'],
    name: 'search',
    title: '搜索',
    nav: true,
    icon: 'Search',
    copy: {
      subtitle: '输入汉字、拼音或关卡名，找到你要练的那一关。',
      loading: '正在找…',
      empty: '没找到这个音，看看下方的相近关卡，或告诉我们希望增加。',
      error: '搜索失败，稍后再试一次。',
      unopened: '这个音还没开放。',
      cta: '搜索',
    },
  },
  {
    code: 'P03',
    paths: ['/map'],
    name: 'map',
    title: '发音地图',
    nav: true,
    icon: 'MapLocation',
    copy: {
      subtitle: '单韵母、声母、拼读三层闯关，看看你学到哪一层。',
      loading: '地图正在展开…',
      empty: '地图上还没有已发布的关卡。',
      error: '地图加载失败，稍后再试。',
      unopened: '这一层还没开放。',
      cta: '去这一关',
    },
  },
  {
    code: 'P04',
    paths: ['/principles'],
    name: 'principles',
    title: '发音原理',
    nav: true,
    icon: 'Reading',
    copy: {
      subtitle: '气从哪里来、声音怎么响、嘴和舌头怎么摆。',
      loading: '正在准备讲解…',
      empty: '这一部分的内容还在准备。',
      error: '内容加载失败。',
      unopened: '这一节还没开放。',
      cta: '看一看',
    },
  },
  {
    code: 'P05',
    paths: ['/learn', '/learn/:id'],
    name: 'levels',
    routeNames: ['levels', 'level'],
    title: '关卡页',
    nav: true,
    icon: 'Flag',
    copy: {
      subtitle: '一句话结论、构形、示范、听辨与练习，都在这一关里。',
      loading: '正在打开这一关…',
      empty: '这一关还没有内容。',
      error: '关卡加载失败，请检查后端是否启动。',
      unopened: '这一关还没开放，先去前面已开放的关卡。',
      cta: '开始练',
    },
  },
  {
    code: 'P06',
    paths: ['/library'],
    name: 'library',
    title: '发音库',
    nav: true,
    icon: 'Collection',
    copy: {
      subtitle: '按单韵母、声母、拼读查看已发布关卡的目录。',
      loading: '正在加载发音库…',
      empty: '还没有已发布的关卡。',
      error: '发音库加载失败。',
      unopened: '该关未发布，不公开展示。',
      cta: '查看',
    },
  },
  {
    code: 'P07',
    paths: ['/materials'],
    name: 'materials',
    title: '专业资料',
    nav: true,
    icon: 'Document',
    copy: {
      subtitle: '需要看依据时查阅：有来源、许可与适用边界。',
      loading: '正在加载资料…',
      empty: '资料还在整理，来源与许可齐全后才会发布。',
      error: '资料加载失败。',
      unopened: '这部分资料还没开放。',
      cta: '查看来源',
    },
  },
  {
    code: 'P08',
    paths: ['/test'],
    name: 'test',
    title: '检测中心',
    nav: true,
    icon: 'Microphone',
    copy: {
      subtitle: '选一个已开放检测的关，按要求朗读并提交。',
      loading: '正在准备检测任务…',
      empty: '还没有开放检测的关卡，可以先跟着练。',
      error: '任务加载失败，请检查后端是否启动。',
      unopened: '这一关还不能检测，先跟着练。',
      cta: '开始录音',
    },
  },
  {
    code: 'P09',
    paths: ['/feedback/:id'],
    name: 'feedback',
    title: '结果',
    nav: false,
    icon: 'DataAnalysis',
    copy: {
      subtitle: '录音质量、曲线对比、分数、现象与四步反馈都在这里。',
      loading: '正在看你的录音…',
      empty: '还没有录音结果。',
      error: '结果加载失败，可以重新录一次。',
      unopened: '这一关只学习、不检测。',
      cta: '再练一次',
    },
  },
  {
    code: 'P10',
    paths: ['/archive'],
    name: 'archive',
    title: '声音档案',
    nav: true,
    icon: 'FolderOpened',
    copy: {
      subtitle: '同意保存后，可以看同一关的前后变化，也可以随时删除。',
      loading: '正在打开档案…',
      empty: '还没有保存的录音。登录并同意后，录音才会保存到这里。',
      error: '档案加载失败。',
      unopened: '档案功能未开放。',
      cta: '去看看',
    },
  },
  {
    code: 'P11',
    paths: ['/account'],
    name: 'account',
    title: '账号',
    nav: true,
    icon: 'User',
    copy: {
      subtitle: '注册、登录、退出，管理保存同意与删除档案。',
      loading: '正在加载账号信息…',
      empty: '未登录。不登录也能学习；要保存进度和录音，需要先登录并同意。',
      error: '账号服务加载失败。',
      unopened: '账号功能未开放。',
      cta: '登录 / 注册',
    },
  },
]

/** 后台（CMS）：不属于 P01–P11，单独登记避免与页面编号混编 */
export const ADMIN_PAGE: PageDef = {
  code: 'ADMIN',
  paths: ['/admin'],
  name: 'admin',
  title: '后台管理',
  nav: false,
  icon: 'Setting',
  copy: {
    subtitle: '关卡录入、发布治理、检测开关、版本与反馈处理。',
    loading: '正在加载后台数据…',
    empty: '暂无数据。',
    error: '后台接口异常。',
    unopened: '未开放。',
    cta: '刷新',
  },
}

export const ALL_PAGES: PageDef[] = [...PAGES, ADMIN_PAGE]

const PAGE_BY_CODE = new Map(ALL_PAGES.map(p => [p.code, p]))

export function getPage(code: string): PageDef | undefined {
  return PAGE_BY_CODE.get(code)
}

/** 路由 name → 页号，写进 router meta.pageCode，供面包屑 / 埋点 / 验收清单统一取用 */
export const PAGE_CODE_BY_ROUTE_NAME: Record<string, string> = ALL_PAGES.reduce(
  (acc, p) => {
    for (const n of [p.name, ...(p.routeNames ?? [])]) acc[n] = p.code
    return acc
  },
  {} as Record<string, string>,
)

/** 一级导航（SRS 4.2：全部页面进入一级导航；结果页 P09 为流程页不进） */
export const NAV_PAGES: PageDef[] = PAGES.filter(p => p.nav)

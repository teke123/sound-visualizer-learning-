/**
 * 受控 Markdown 渲染（FR-501–506 / decision-map-frontend「构形、文章与听辨」）：
 * - 禁用原始 HTML 与脚本（html: false）
 * - 自定义容器指令白名单：practice / audio / image / levels / pro
 * - 媒体只接受由 mediaResolver 生成的 /api/media 或 /api/preview/media 地址
 * - markdown-it 动态加载，不进首屏包（§9）
 */

type DirectiveName = 'audio' | 'image' | 'levels' | 'practice' | 'pro'
const DIRECTIVE_NAMES: readonly DirectiveName[] = ['audio', 'image', 'levels', 'practice', 'pro']

export interface MarkdownRenderOptions {
  mediaResolver: (mediaId: string) => string
}

function parseAttrs(raw: string): Record<string, string> {
  const attrs: Record<string, string> = {}
  for (const part of raw.split(/\s+/)) {
    if (!part) continue
    const eq = part.indexOf('=')
    if (eq > 0) attrs[part.slice(0, eq)] = part.slice(eq + 1).replace(/^["']|["']$/g, '')
  }
  return attrs
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

interface MarkdownItLike {
  render(src: string): string
  renderInline(src: string): string
  block: { ruler: { before<B>(before: string, name: string, fn: B): void } }
  renderer: { rules: Record<string, (tokens: unknown[], idx: number) => string> }
}

let mdPromise: Promise<MarkdownItLike> | null = null

async function loadMarkdownIt(): Promise<MarkdownItLike> {
  if (!mdPromise) {
    mdPromise = import('markdown-it').then(({ default: MarkdownIt }) => {
      const md = new MarkdownIt({ html: false, linkify: false, breaks: false }) as unknown as MarkdownItLike & {
        renderer: { rules: Record<string, ((tokens: Array<{ attrs: [string, string][]; children?: unknown[]; content?: string }>, idx: number) => string)> }
      }

      md.block.ruler.before('paragraph', 'vv_directive', function directiveRule(
        state: {
          src: string
          bMarks: number[]
          eMarks: number[]
          tShift: number[]
          line: number
          lineMax: number
          parentType: string
          blkIndent: number
          tokens: Array<{ type: string; block: boolean; meta: Record<string, unknown>; content: string; map?: [number, number] }>
          push(type: string, tag: string, nesting: number): void
        },
        startLine: number,
        endLine: number,
        silent: boolean,
      ): boolean {
        const startPos = state.bMarks[startLine]! + state.tShift[startLine]!
        const lineText = state.src.slice(startPos, state.eMarks[startLine]!)
        const openMatch = /^:::+[ \t]*(audio|image|levels|practice|pro)[ \t]*(.*)$/.exec(lineText)
        if (!openMatch) return false
        const name = openMatch[1] as DirectiveName
        let closeLine = -1
        for (let line = startLine + 1; line < endLine; line += 1) {
          const text = state.src.slice(state.bMarks[line]! + state.tShift[line]!, state.eMarks[line]!)
          if (/^:::+[ \t]*$/.test(text)) {
            closeLine = line
            break
          }
        }
        if (closeLine < 0) return false
        if (silent) return true

        const contentStart = state.bMarks[startLine + 1]! + state.tShift[startLine + 1]!
        const contentEnd = state.eMarks[closeLine - 1] ?? state.bMarks[closeLine]!
        const content = closeLine > startLine + 1 ? state.src.slice(contentStart, contentEnd) : ''

        const token = {
          type: 'vv_directive',
          block: true,
          meta: { name, attrs: parseAttrs(openMatch[2] ?? ''), content },
          content: '',
          map: [startLine, closeLine] as [number, number],
        }
        state.tokens.push(token as never)
        state.line = closeLine + 1
        return true
      } as never)

      return md
    })
  }
  return mdPromise
}

/** 是否为受控媒体地址（/api/media 或 /api/preview/media 开头） */
export function isControlledMediaUrl(url: string): boolean {
  return url.startsWith('/api/media/') || url.startsWith('/api/preview/media/')
}

export async function renderArticleMarkdown(source: string, options: MarkdownRenderOptions): Promise<string> {
  const md = await loadMarkdownIt()

  md.renderer.rules.vv_directive = ((tokens: Array<{ meta: { name: DirectiveName; attrs: Record<string, string>; content: string } }>, idx: number) => {
    const { name, attrs, content } = tokens[idx]!.meta
    switch (name) {
      case 'audio': {
        const mediaId = attrs.mediaId ?? ''
        const subtitle = md.renderInline(content).trim()
        return (
          `<div class="md-directive md-audio">` +
          `<button type="button" class="md-audio-btn" data-media-id="${escapeHtml(mediaId)}">▶ 播放示范</button>` +
          (subtitle ? `<span class="md-audio-text">${subtitle}</span>` : '') +
          `</div>`
        )
      }
      case 'image': {
        const mediaId = attrs.mediaId ?? ''
        const alt = attrs.alt ?? ''
        const caption = md.renderInline(content).trim()
        return (
          `<figure class="md-directive md-image">` +
          `<img src="${escapeHtml(options.mediaResolver(mediaId))}" alt="${escapeHtml(alt)}" loading="lazy">` +
          (caption ? `<figcaption>${caption}</figcaption>` : '') +
          `</figure>`
        )
      }
      case 'levels': {
        const ids = (attrs.ids ?? '').split(',').map((id) => id.trim()).filter(Boolean)
        const chips = ids
          .map((id) => `<span class="md-level-chip" data-level-id="${escapeHtml(id)}" role="link" tabindex="0">${escapeHtml(id)}</span>`)
          .join('')
        return `<div class="md-directive md-levels">相关关卡：${chips || '—'}</div>`
      }
      case 'practice':
        return (
          `<details class="md-directive md-practice"><summary>短练习（跟着做）</summary>` +
          `<div class="md-practice-body">${md.render(content)}</div></details>`
        )
      case 'pro':
        return (
          `<details class="md-directive md-pro"><summary>专业内容</summary>` +
          `<div class="md-pro-body">${md.render(content)}</div></details>`
        )
      default:
        return ''
    }
  }) as never

  // 普通图片只允许受控媒体地址
  md.renderer.rules.image = ((tokens: Array<{ attrs: [string, string][]; children?: Array<{ content: string }> }>, idx: number) => {
    const token = tokens[idx]!
    const src = token.attrs.find(([key]) => key === 'src')?.[1] ?? ''
    const alt = token.children?.map((child) => child.content).join('') ?? ''
    if (!isControlledMediaUrl(src)) return ''
    return `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" loading="lazy">`
  }) as never

  // 外链统一新窗口打开
  md.renderer.rules.link_open = ((tokens: Array<{ attrs: [string, string][] }>, idx: number) => {
    const token = tokens[idx]!
    const href = token.attrs.find(([key]) => key === 'href')?.[1] ?? '#'
    const safeHref = /^https?:\/\//.test(href) ? href : '#'
    return `<a href="${escapeHtml(safeHref)}" target="_blank" rel="noopener noreferrer">`
  }) as never

  return md.render(source)
}

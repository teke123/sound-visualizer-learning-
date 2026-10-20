export interface CurvePlotPoint {
  x: number
  y: number | null
  conf: number
  src: string | null
}

type Series = Array<[number, number] | null>

/** Keep each style in disconnected runs, sharing only the transition endpoint. */
export function splitByConfidence(pts: CurvePlotPoint[]): { solid: Series; dotted: Series } {
  const solid: Series = []
  const dotted: Series = []
  let prev: CurvePlotPoint | null = null
  let active: Series | null = null
  for (const p of pts) {
    if (p.y === null) {
      solid.push(null)
      dotted.push(null)
      prev = null
      active = null
      continue
    }
    if (prev && prev.y !== null) {
      const target = Math.min(prev.conf, p.conf) < 0.5 ? dotted : solid
      if (target !== active) {
        active?.push(null)
        target.push(null, [prev.x, prev.y])
        active = target
      }
      target.push([p.x, p.y])
    }
    prev = p
  }
  return { solid, dotted }
}


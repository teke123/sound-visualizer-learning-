export interface PcmWindow {
  samples: Float32Array
  t: number
}

/** Consume actual PCM samples; display cadence never changes the analysis grid. */
export class PcmWindows {
  private readonly ring: Float32Array
  private write = 0
  private filled = 0
  private previousSample: number | null = null
  private nextEnd: number | null = null
  private readonly hop: number

  constructor(
    private readonly sampleRate: number,
    private readonly windowSize: number,
    private readonly recordingStartSample: number,
  ) {
    this.ring = new Float32Array(windowSize)
    this.hop = Math.round(sampleRate * 0.01)
  }

  push(chunk: Float32Array, startSample: number): PcmWindow[] {
    const out: PcmWindow[] = []
    for (let i = Math.max(0, this.recordingStartSample - startSample); i < chunk.length; i++) {
      const absolute = startSample + i
      if (this.previousSample !== null && absolute !== this.previousSample + 1) {
        this.filled = 0
        this.nextEnd = null
      }
      this.previousSample = absolute
      this.ring[this.write] = chunk[i]!
      this.write = (this.write + 1) % this.windowSize
      this.filled = Math.min(this.filled + 1, this.windowSize)
      if (this.filled < this.windowSize) continue
      const end = absolute + 1
      if (this.nextEnd !== null && end < this.nextEnd) continue
      this.nextEnd = end + this.hop
      const samples = new Float32Array(this.windowSize)
      const tail = this.ring.subarray(this.write)
      samples.set(tail)
      samples.set(this.ring.subarray(0, this.write), tail.length)
      out.push({ samples, t: (end - this.windowSize / 2 - this.recordingStartSample) / this.sampleRate })
    }
    return out
  }
}


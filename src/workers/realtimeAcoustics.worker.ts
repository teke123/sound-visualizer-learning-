import { PcmWindows } from '../utils/pcmWindows'
import { RealtimePitchTracker } from '../utils/realtimeAcoustics'

type Message =
  | { type: 'init'; sampleRate: number; windowSize: number; startSample: number }
  | { type: 'pcm'; samples: Float32Array; startSample: number }
  | { type: 'flush' }

const scope = globalThis as unknown as {
  onmessage: ((event: MessageEvent<Message>) => void) | null
  postMessage(message: unknown): void
}
let windows: PcmWindows | null = null
let tracker: RealtimePitchTracker | null = null

scope.onmessage = ({ data }) => {
  if (data.type === 'flush') {
    scope.postMessage({ type: 'flushed' })
    return
  }
  if (data.type === 'init') {
    windows = new PcmWindows(data.sampleRate, data.windowSize, data.startSample)
    tracker = new RealtimePitchTracker(data.sampleRate, { fftSize: data.windowSize })
    return
  }
  if (!windows || !tracker) return
  const frames = windows.push(data.samples, data.startSample).map(({ samples, t }) => tracker!.push(samples, t))
  // Keep historical frames in the canvas, not twice in the long-lived worker.
  tracker.frames.length = 0
  if (frames.length) scope.postMessage(frames)
}


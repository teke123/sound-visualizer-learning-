/**
 * recorder store：唯一 MediaRecorder 封装（授权、格式选择、实时波形、时长上限、释放）。
 * 采集参数关闭回声消除 / 降噪 / 自动增益（若浏览器允许），避免改变音高与能量；
 * iOS：AudioContext 在首次手势时 resume（docs/architecture/04 §8）。
 */
import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'

export type RecorderStatus =
  | 'idle'
  | 'requesting'
  | 'ready'
  | 'denied'
  | 'unsupported'
  | 'recording'
  | 'recorded'

/** 按 isTypeSupported 依次选择 webm/opus → mp4/aac（§8） */
const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4;codecs=mp4a.40.2',
  'audio/mp4',
  'audio/aac',
]

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  return MIME_CANDIDATES.find((mime) => {
    try {
      return MediaRecorder.isTypeSupported(mime)
    } catch {
      return false
    }
  })
}

export const RECORD_MAX_MS = { recording: 15_000, calibration: 40_000 } as const

export const useRecorderStore = defineStore('recorder', () => {
  const status = ref<RecorderStatus>('idle')
  const denied = ref(false)
  const mimeType = ref<string | undefined>(undefined)
  const blob = shallowRef<Blob | null>(null)
  const blobUrl = ref<string | null>(null)
  const elapsedMs = ref(0)
  const error = ref<string | null>(null)
  /** 实时波形采样（RMS 0–1），RecorderPanel 用 canvas 绘制 */
  const waveform = ref<number[]>([])

  let stream: MediaStream | null = null
  let recorder: MediaRecorder | null = null
  let audioContext: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let sampleBuffer: Uint8Array<ArrayBuffer> | null = null
  let timerHandle: number | null = null
  let rafHandle: number | null = null
  let autoStopAt = 0
  let onAutoStop: (() => void) | null = null

  const supported = computed(() => typeof MediaRecorder !== 'undefined' && pickMimeType() !== undefined)
  const hasPendingTake = computed(() => blob.value !== null)

  function stopWaveformLoop() {
    if (rafHandle !== null) cancelAnimationFrame(rafHandle)
    rafHandle = null
  }

  function stopTimer() {
    if (timerHandle !== null) window.clearInterval(timerHandle)
    timerHandle = null
  }

  function releaseMic() {
    stream?.getTracks().forEach((track) => track.stop())
    stream = null
    if (audioContext && audioContext.state !== 'closed') void audioContext.close()
    audioContext = null
    analyser = null
    sampleBuffer = null
  }

  function discardTake() {
    if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
    blob.value = null
    blobUrl.value = null
    elapsedMs.value = 0
    waveform.value = []
  }

  /** 请求麦克风授权；成功后保持待机（不立刻录音） */
  async function request(): Promise<boolean> {
    error.value = null
    if (!supported.value) {
      status.value = 'unsupported'
      return false
    }
    if (status.value === 'ready' || status.value === 'recorded') return true
    status.value = 'requesting'
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
      denied.value = false
      mimeType.value = pickMimeType()
      // AudioContext 需在用户手势内创建/resume（iOS Safari）
      audioContext = new AudioContext()
      if (audioContext.state === 'suspended') await audioContext.resume()
      const source = audioContext.createMediaStreamSource(stream)
      analyser = audioContext.createAnalyser()
      analyser.fftSize = 1024
      source.connect(analyser)
      sampleBuffer = new Uint8Array(new ArrayBuffer(analyser.fftSize))
      status.value = 'ready'
      return true
    } catch (err) {
      const name = (err as DOMException)?.name
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        denied.value = true
        status.value = 'denied'
      } else {
        error.value = name === 'NotFoundError' ? '未找到可用的麦克风设备' : '无法访问麦克风'
        status.value = 'idle'
      }
      releaseMic()
      return false
    }
  }

  function sampleWaveform() {
    if (!analyser || !sampleBuffer) return
    analyser.getByteTimeDomainData(sampleBuffer)
    let sum = 0
    for (let i = 0; i < sampleBuffer.length; i += 1) {
      const v = (sampleBuffer[i]! - 128) / 128
      sum += v * v
    }
    const rms = Math.sqrt(sum / sampleBuffer.length)
    waveform.value.push(rms)
    if (waveform.value.length > 240) waveform.value.shift()
    if (status.value === 'recording') {
      rafHandle = requestAnimationFrame(sampleWaveform)
    }
  }

  /** 开始录音；maxMs 到上限自动停止（§6.2：关卡 15 秒、标定 40 秒） */
  async function start(options: { maxMs: number; onAutoStop?: () => void }): Promise<boolean> {
    if (status.value !== 'ready') {
      const ok = await request()
      if (!ok) return false
    }
    discardTake()
    if (!stream || !mimeType.value) return false
    autoStopAt = Date.now() + options.maxMs
    onAutoStop = options.onAutoStop ?? null
    const chunks: BlobPart[] = []
    recorder = new MediaRecorder(stream, { mimeType: mimeType.value })
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    recorder.onstop = () => {
      stopTimer()
      stopWaveformLoop()
      const type = mimeType.value ?? 'audio/webm'
      blob.value = new Blob(chunks, { type })
      blobUrl.value = URL.createObjectURL(blob.value)
      status.value = 'recorded'
    }
    recorder.start(250)
    status.value = 'recording'
    elapsedMs.value = 0
    waveform.value = []
    timerHandle = window.setInterval(() => {
      elapsedMs.value = Date.now() - (autoStopAt - options.maxMs)
      if (Date.now() >= autoStopAt) {
        stop()
      }
    }, 100)
    rafHandle = requestAnimationFrame(sampleWaveform)
    return true
  }

  function stop() {
    if (status.value !== 'recording' || !recorder) return
    autoStopAt = Date.now() // 防止 interval 再次触发
    if (recorder.state !== 'inactive') recorder.stop()
    recorder = null
    onAutoStop?.()
    onAutoStop = null
  }

  /** 重录：丢弃 blob，回到待机 */
  function reRecord() {
    discardTake()
    status.value = stream ? 'ready' : 'idle'
  }

  /** 离开录音组件 / 页面隐藏超时：停止录音并释放麦克风，避免指示灯常亮（§8） */
  function release() {
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null
      recorder.stop()
    }
    recorder = null
    stopTimer()
    stopWaveformLoop()
    discardTake()
    releaseMic()
    status.value = 'idle'
  }

  return {
    status,
    denied,
    supported,
    mimeType,
    blob,
    blobUrl,
    elapsedMs,
    waveform,
    error,
    hasPendingTake,
    request,
    start,
    stop,
    reRecord,
    release,
    discardTake,
  }
})

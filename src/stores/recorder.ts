/**
 * recorder store：唯一录音封装（授权、设备识别、时长上限、释放）。
 * 采集参数关闭回声消除 / 降噪 / 自动增益（若浏览器允许），避免改变音高与能量；
 * 不在浏览器端强制采样率，以声卡硬件原生采样率采集，由后端统一重采样到 44.1 kHz；
 * 输出为 AudioWorklet 原始 PCM 封装的无损 WAV（不走 MediaRecorder 的 Opus/AAC 有损编码）。
 * iOS：AudioContext 在首次手势时 resume。
 *
 * 职责边界（FR-907）：本 store 只管录音状态机与产出音频 Blob；
 * 实时分析通过 AudioWorklet 输出带采样位置的 PCM，由 Worker 分析、画布渲染。
 */
import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { ANALYSIS_FFT_SIZE } from '@/utils/realtimeAcoustics'
import { detectActiveAudioInput } from '@/utils/deviceCheck'
import { encodeWav } from '@/utils/wavEncoder'

export type RecorderStatus =
  | 'idle'
  | 'requesting'
  | 'ready'
  | 'denied'
  | 'unsupported'
  | 'recording'
  | 'recorded'

type PcmListener = (samples: Float32Array, startSample: number) => void

/** 录音上限：正式录音 15s；标定短文 40s；标定单条元音 10s（目标发音约 0.5–1s） */
export const RECORD_MAX_MS = { recording: 15_000, calibration: 40_000, calibrationVowel: 10_000 } as const

export const useRecorderStore = defineStore('recorder', () => {
  const status = ref<RecorderStatus>('idle')
  const denied = ref(false)
  const blob = shallowRef<Blob | null>(null)
  const blobUrl = ref<string | null>(null)
  const elapsedMs = ref(0)
  const error = ref<string | null>(null)
  /** 当前输入设备（授权后识别；蓝牙输入供界面提示更换设备） */
  const inputLabel = ref('')
  const inputBluetooth = ref(false)

  let stream: MediaStream | null = null
  let audioContext: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let capture: AudioWorkletNode | null = null
  let recordingStartSample = 0
  let timerHandle: number | null = null
  let autoStopAt = 0
  let onAutoStop: (() => void) | null = null

  /** 录音中的 PCM 累积（Worklet 帧序；stop 时封装为 WAV） */
  const pcmListeners = new Set<PcmListener>()
  let pcmChunks: Float32Array[] = []
  let capturing = false

  // 内部累积监听只注册一次（request 可能多次重入，重复注册会重复累积同一帧）
  pcmListeners.add((samples) => {
    if (capturing) pcmChunks.push(samples)
  })

  const supported = computed(
    () =>
      typeof navigator !== 'undefined' &&
      !!navigator.mediaDevices?.getUserMedia &&
      typeof AudioContext !== 'undefined' &&
      typeof AudioWorkletNode !== 'undefined',
  )
  const hasPendingTake = computed(() => blob.value !== null)

  function stopTimer() {
    if (timerHandle !== null) window.clearInterval(timerHandle)
    timerHandle = null
  }

  function releaseMic() {
    capturing = false
    capture?.disconnect()
    capture = null
    stream?.getTracks().forEach((track) => track.stop())
    stream = null
    if (audioContext && audioContext.state !== 'closed') void audioContext.close()
    audioContext = null
    analyser = null
  }

  function discardTake() {
    if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
    blob.value = null
    blobUrl.value = null
    elapsedMs.value = 0
    pcmChunks = []
    capturing = false
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
      // 不设 sampleRate 约束：以硬件原生采样率采集（通常 44.1/48 kHz），
      // 重采样统一交给后端处理；channelCount 单声道。
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: { ideal: 1 },
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
      denied.value = false
      const device = detectActiveAudioInput(stream)
      inputLabel.value = device.label
      inputBluetooth.value = device.bluetooth
      // AudioContext 需在用户手势内创建/resume（iOS Safari）；采样率跟随硬件
      audioContext = new AudioContext()
      if (audioContext.state === 'suspended') await audioContext.resume()
      const source = audioContext.createMediaStreamSource(stream)
      analyser = audioContext.createAnalyser()
      // 频谱预览；F0 分析窗口在 Worker 中从 PCM 环形缓冲生成。
      analyser.fftSize = ANALYSIS_FFT_SIZE
      source.connect(analyser)
      await audioContext.audioWorklet.addModule(new URL('../audio/pcmCapture.worklet.js', import.meta.url))
      capture = new AudioWorkletNode(audioContext, 'pcm-capture')
      analyser.connect(capture)
      // Processor 的输出保持静音；连接 destination 维持音频处理图运行。
      capture.connect(audioContext.destination)
      capture.port.onmessage = (event: MessageEvent<{ samples: Float32Array; startSample: number }>) => {
        const { samples, startSample } = event.data
        for (const listener of pcmListeners) listener(samples, startSample)
      }
      // 常开采集：录音时累积 PCM，同时供实时分析画布订阅
      capture.port.postMessage({ enabled: true })
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

  /** 实时分析入口：录音就绪后非空；释放麦克风后置空（画布组件据此停画） */
  function getAnalyser(): AnalyserNode | null {
    return analyser
  }

  function getRecordingStartSample(): number {
    return recordingStartSample
  }

  /** 订阅原始 PCM（AudioWorklet 帧流）；返回取消订阅函数 */
  function subscribePcm(onChunk: PcmListener): () => void {
    pcmListeners.add(onChunk)
    return () => {
      pcmListeners.delete(onChunk)
    }
  }

  /** 开始录音；maxMs 到上限自动停止（§6.2：关卡 15 秒、标定 40 秒） */
  async function start(options: { maxMs: number; onAutoStop?: () => void }): Promise<boolean> {
    if (status.value !== 'ready') {
      const ok = await request()
      if (!ok) return false
    }
    discardTake()
    if (!stream || !audioContext) return false
    autoStopAt = Date.now() + options.maxMs
    onAutoStop = options.onAutoStop ?? null
    pcmChunks = []
    capturing = true
    recordingStartSample = Math.round(audioContext.currentTime * audioContext.sampleRate)
    status.value = 'recording'
    elapsedMs.value = 0
    timerHandle = window.setInterval(() => {
      elapsedMs.value = Date.now() - (autoStopAt - options.maxMs)
      if (Date.now() >= autoStopAt) {
        stop()
      }
    }, 100)
    return true
  }

  function stop() {
    if (status.value !== 'recording') return
    autoStopAt = Date.now() // 防止 interval 再次触发
    capturing = false
    stopTimer()
    const sampleRate = audioContext?.sampleRate ?? 44100
    blob.value = encodeWav(pcmChunks, sampleRate)
    pcmChunks = []
    blobUrl.value = URL.createObjectURL(blob.value)
    status.value = 'recorded'
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
    if (status.value === 'recording') {
      onAutoStop = null
      stopTimer()
    }
    discardTake()
    releaseMic()
    status.value = 'idle'
  }

  return {
    status,
    denied,
    supported,
    blob,
    blobUrl,
    elapsedMs,
    error,
    inputLabel,
    inputBluetooth,
    hasPendingTake,
    request,
    start,
    stop,
    reRecord,
    release,
    discardTake,
    getAnalyser,
    getRecordingStartSample,
    subscribePcm,
  }
})

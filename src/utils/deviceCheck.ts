/**
 * 录音输入设备识别：蓝牙耳机（AirPods 等）一旦被网页调用麦克风，蓝牙链路
 * 会从高质量听音模式（A2DP）切换到双向通话的免提协议（HFP），采集被限制到
 * 8/16 kHz 窄带并伴随高强度有损压缩——擦音、送气等高频特征全部丢失。
 *
 * 通过授权后 MediaStreamTrack 的设备名称识别蓝牙输入设备，供录音界面
 * 提示用户更换设备（仅提示，不阻断，符合 FR-1301 不设阻断式门禁的约定）。
 */

/** 常见蓝牙输入设备名称关键词（小写匹配，覆盖中英文系统命名） */
const BLUETOOTH_LABEL_KEYWORDS = [
  'bluetooth',
  'airpods',
  'hands-free',
  'handsfree',
  'hfp',
  'freebuds',
  'buds',
  '蓝牙',
]

export interface AudioInputInfo {
  /** 系统中的输入设备名称（如「AirPods Hands-Free AG Audio」） */
  label: string
  /** 是否蓝牙输入设备（HFP 窄带，声学质量不满足分析要求） */
  bluetooth: boolean
}

export function isBluetoothInput(label: string): boolean {
  const lower = label.toLowerCase()
  return BLUETOOTH_LABEL_KEYWORDS.some((keyword) => lower.includes(keyword))
}

/** 从已授权的麦克风流读取当前输入设备信息 */
export function detectActiveAudioInput(stream: MediaStream): AudioInputInfo {
  const label = stream.getAudioTracks()[0]?.label ?? ''
  return { label, bluetooth: isBluetoothInput(label) }
}

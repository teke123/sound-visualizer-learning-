/** 蓝牙输入设备识别单测：中英文系统命名均需命中，非蓝牙设备不误报 */
import { describe, expect, it } from 'vitest'
import { detectActiveAudioInput, isBluetoothInput } from '../deviceCheck'

describe('isBluetoothInput', () => {
  it('识别常见蓝牙设备命名', () => {
    expect(isBluetoothInput('AirPods Hands-Free AG Audio')).toBe(true)
    expect(isBluetoothInput('耳机 (AirPods)')).toBe(true)
    expect(isBluetoothInput('Bluetooth Hands-Free Audio')).toBe(true)
    expect(isBluetoothInput('蓝牙耳机 (Bluetooth)')).toBe(true)
    expect(isBluetoothInput('FreeBuds Pro 3 Hands-Free')).toBe(true)
    expect(isBluetoothInput('Galaxy Buds2 Pro')).toBe(true)
  })

  it('非蓝牙设备不误报', () => {
    expect(isBluetoothInput('Built-in Microphone')).toBe(false)
    expect(isBluetoothInput('内置麦克风')).toBe(false)
    expect(isBluetoothInput('USB Microphone (Blue Yeti)')).toBe(false)
    expect(isBluetoothInput('外部麦克风 (Realtek Audio)')).toBe(false)
  })
})

describe('detectActiveAudioInput', () => {
  it('读取麦克风流上的活动输入设备名称', () => {
    const stream = { getAudioTracks: () => [{ label: 'AirPods Hands-Free AG Audio' }] } as unknown as MediaStream
    const info = detectActiveAudioInput(stream)
    expect(info.label).toBe('AirPods Hands-Free AG Audio')
    expect(info.bluetooth).toBe(true)
  })

  it('无音轨时返回空标签且不判蓝牙', () => {
    const stream = { getAudioTracks: () => [] } as unknown as MediaStream
    const info = detectActiveAudioInput(stream)
    expect(info.label).toBe('')
    expect(info.bluetooth).toBe(false)
  })
})

/**
 * 录音 store（重构占位）
 * ---------------------------------------------------------------------------
 * 意图：全项目唯一的一处 MediaRecorder 封装，管理：
 *  - 录音状态机（空闲/录音中/已停止）与计时；
 *  - 录音 Blob 生命周期（含 objectURL 的创建与 revoke）；
 *  - analyzeRecording(unitId)：调用后端分析接口（新契约定稿后接入）。
 *
 * 「录音 -> 分析 -> 存档」是一条事务：分析成功才允许存档（userStore.addLearningRecord），
 * 该编排放调用方（页面/面板）编排，store 只提供原语。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useRecordingStore = defineStore('recording', () => {
  const isRecording = ref(false)
  const isAnalyzing = ref(false)
  const hasRecording = ref(false)
  const audioUrl = ref('')
  const formattedDuration = ref('00:00')
  const error = ref('')

  function clearRecording(): void {
    // TODO(重构): 释放 objectURL 并复位状态
  }

  function stopRecording(): void {
    // TODO(重构): 停止 MediaRecorder，产出 Blob 与 objectURL
  }

  return { isRecording, isAnalyzing, hasRecording, audioUrl, formattedDuration, error, clearRecording, stopRecording }
})

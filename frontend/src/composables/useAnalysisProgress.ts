import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { analysisApi } from '@/api/analysis'

/**
 * 分析进度管理 composable
 * 负责WebSocket进度推送、轮询任务状态、步骤更新、任务缓存
 */
export function useAnalysisProgress() {
  const currentTaskId = ref('')
  const analysisStatus = ref<'idle' | 'running' | 'completed' | 'failed'>('idle')
  const progressInfo = ref({
    progress: 0,
    currentStep: '',
    currentStepDescription: '',
    message: '',
    elapsedTime: 0,
    remainingTime: 0,
    totalTime: 0
  })
  const pollingTimer = ref<any>(null)
  const analysisSteps = ref<any[]>([])

  // WebSocket 进度连接
  let wsProgress: WebSocket | null = null

  const connectProgressWS = (taskId: string) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('auth-token') || localStorage.getItem('token') || ''
    const wsUrl = `${protocol}//${window.location.host}/api/ws/progress?token=${token}`
    try {
      wsProgress = new WebSocket(wsUrl)
      wsProgress.onopen = () => {
        console.log('📡 WebSocket progress 已连接')
        wsProgress?.send(JSON.stringify({ type: 'subscribe', task_id: taskId }))
      }
      wsProgress.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'progress_update' && msg.data) {
            updateStepsFromProgress(msg.data)
          } else if (msg.type === 'completed' && msg.data) {
            updateStepsFromProgress(msg.data)
          }
        } catch (e) {
          console.error('📡 WebSocket 消息解析失败:', e)
        }
      }
      wsProgress.onclose = () => {
        console.log('📡 WebSocket progress 已断开')
        wsProgress = null
      }
      wsProgress.onerror = (error) => {
        console.error('📡 WebSocket progress 错误:', error)
      }
    } catch (error) {
      console.error('📡 WebSocket 连接失败:', error)
    }
  }

  const disconnectProgressWS = () => {
    if (wsProgress) {
      wsProgress.close()
      wsProgress = null
    }
  }

  const updateStepsFromProgress = (data: any) => {
    if (data.steps && data.steps.length > 0) {
      const newSteps = generateStepsFromBackend(data.steps)
      newSteps.forEach((newStep: any) => {
        const existingStep = analysisSteps.value.find(s => s.key === newStep.key)
        if (existingStep) {
          newStep.isExpanded = existingStep.isExpanded
        }
      })
      analysisSteps.value = newSteps
      console.log('📋 步骤已更新:', newSteps.length, '个步骤')
    }
  }

  const toggleStepExpand = (stepKey: string) => {
    const step = analysisSteps.value.find(s => s.key === stepKey)
    if (step) {
      step.isExpanded = !step.isExpanded
    }
  }

  const generateStepsFromBackend = (backendSteps: any[]) => {
    if (!backendSteps || !Array.isArray(backendSteps)) {
      return []
    }
    return backendSteps.map((step: any, index: number) => {
      const operations = (step.operations || []).map((op: any) => ({
        id: op.id || `op_${index}`,
        name: op.name || op.operation_name || '未知操作',
        status: op.status || 'pending',
        result: op.result || null
      }))
      return {
        key: step.key || step.id || `step_${index}`,
        title: step.title || step.name || `Step ${index + 1}`,
        description: step.description || '',
        status: step.status || 'pending',
        progress: step.progress || 0,
        operations,
        isExpanded: index === 0
      }
    })
  }

  const updateAnalysisSteps = (status: any) => {
    if (analysisSteps.value.length === 0) return
    let currentStepIndex = 0
    if (status.current_step !== undefined) {
      currentStepIndex = status.current_step
    } else {
      const progress = status.progress_percentage || status.progress || 0
      if (progress > 0) {
        currentStepIndex = Math.max(1, Math.floor((progress / 100) * (analysisSteps.value.length - 1)))
      }
    }
    currentStepIndex = Math.max(0, Math.min(currentStepIndex, analysisSteps.value.length - 1))
    analysisSteps.value.forEach((step, index) => {
      step.status = index < currentStepIndex ? 'completed' : index === currentStepIndex ? 'running' : 'pending'
    })
  }

  const updateProgressInfo = (status: any) => {
    if (status.progress !== undefined) {
      progressInfo.value.progress = status.progress
    }
    if (status.steps && Array.isArray(status.steps) && analysisSteps.value.length === 0) {
      analysisSteps.value = generateStepsFromBackend(status.steps)
    }
    updateAnalysisSteps(status)
    progressInfo.value.message = status.message || '分析正在进行中...'
  }

  const startPollingTaskStatus = (
    onCompleted: (result: any) => void,
    onFailed: (error: string) => void
  ) => {
    if (pollingTimer.value) clearInterval(pollingTimer.value)
    if (!currentTaskId.value) {
      console.error('❌ 任务ID为空，无法开始轮询')
      return
    }
    console.log('🔄 开始轮询任务状态:', currentTaskId.value)
    connectProgressWS(currentTaskId.value)

    pollingTimer.value = setInterval(async () => {
      try {
        if (!currentTaskId.value) {
          if (pollingTimer.value) clearInterval(pollingTimer.value)
          return
        }
        const response = await analysisApi.getTaskStatus(currentTaskId.value)
        const status = response.data

        if (status.status === 'completed') {
          console.log('🎉 分析完成，正在获取完整结果...')
          try {
            const resultData = await analysisApi.getTaskResult(currentTaskId.value)
            onCompleted(resultData.success ? resultData.data : status.result_data)
          } catch (error) {
            console.error('❌ 获取分析结果异常:', error)
            onCompleted(status.result_data)
          }
          analysisStatus.value = 'completed'
          progressInfo.value.progress = 100
          progressInfo.value.currentStep = '分析完成'
          progressInfo.value.message = '分析已完成！'
          if (pollingTimer.value) {
            clearInterval(pollingTimer.value)
            pollingTimer.value = null
          }
          disconnectProgressWS()
          ElMessage.success('分析完成！')

        } else if (status.status === 'failed') {
          const errorMessage = status.error_message || '分析过程中发生错误'
          onFailed(errorMessage)
          analysisStatus.value = 'failed'
          progressInfo.value.currentStep = '分析失败'
          progressInfo.value.message = errorMessage
          if (pollingTimer.value) {
            clearInterval(pollingTimer.value)
            pollingTimer.value = null
          }
          disconnectProgressWS()
          clearTaskCache()
          ElMessage({
            type: 'error',
            message: errorMessage.replace(/\n/g, '<br>'),
            dangerouslyUseHTMLString: true,
            duration: 10000,
            showClose: true
          })

        } else if (status.status === 'running' || status.status === 'pending') {
          analysisStatus.value = 'running'
          if (status.status === 'pending') {
            if (status.progress !== undefined) {
              progressInfo.value.progress = status.progress
            }
            progressInfo.value.message = '分析任务正在处理，请稍候...'
          } else {
            updateProgressInfo(status)
          }
        }
      } catch (error) {
        console.error('获取任务状态失败:', error)
      }
    }, 2000)
  }

  // 任务缓存
  const TASK_CACHE_KEY = 'trading_analysis_task'
  const TASK_CACHE_DURATION = 30 * 60 * 1000 // 30分钟

  const saveTaskToCache = (taskId: string, taskData: any) => {
    const cacheData = { taskId, taskData, timestamp: Date.now() }
    localStorage.setItem(TASK_CACHE_KEY, JSON.stringify(cacheData))
    console.log('💾 任务状态已缓存:', taskId)
  }

  const getTaskFromCache = () => {
    try {
      const cached = localStorage.getItem(TASK_CACHE_KEY)
      if (!cached) return null
      const cacheData = JSON.parse(cached)
      if (Date.now() - cacheData.timestamp > TASK_CACHE_DURATION) {
        localStorage.removeItem(TASK_CACHE_KEY)
        console.log('🗑️ 缓存已过期，已清理')
        return null
      }
      console.log('📦 从缓存恢复任务:', cacheData.taskId)
      return cacheData
    } catch (error) {
      console.error('❌ 读取缓存失败:', error)
      localStorage.removeItem(TASK_CACHE_KEY)
      return null
    }
  }

  const clearTaskCache = () => {
    localStorage.removeItem(TASK_CACHE_KEY)
  }

  const restoreTaskFromCache = async () => {
    const cached = getTaskFromCache()
    if (cached?.taskId) {
      currentTaskId.value = cached.taskId
      analysisStatus.value = 'running'
      progressInfo.value.message = '恢复任务中...'
      setTimeout(async () => {
        try {
          const response = await analysisApi.getTaskStatus(currentTaskId.value)
          const status = response.data
          if (status.status === 'running') {
            analysisStatus.value = 'running'
            updateProgressInfo(status)
          }
        } catch (error) {
          console.error('页面恢复查询状态失败:', error)
        }
      }, 500)
    }
  }

  const formatTime = (seconds: number) => {
    if (!seconds || seconds <= 0) return '计算中...'
    if (seconds < 60) return `${Math.floor(seconds)}秒`
    if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = Math.floor(seconds % 60)
      return remainingSeconds > 0 ? `${minutes}分${remainingSeconds}秒` : `${minutes}分钟`
    }
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}小时${minutes}分钟`
  }

  const getProgressStatus = () => {
    if (analysisStatus.value === 'completed') return 'success'
    if (analysisStatus.value === 'failed') return 'exception'
    return ''
  }

  const resetProgress = () => {
    clearTaskCache()
    analysisStatus.value = 'idle'
    currentTaskId.value = ''
    progressInfo.value = {
      progress: 0, currentStep: '', currentStepDescription: '',
      message: '', elapsedTime: 0, remainingTime: 0, totalTime: 0
    }
    if (pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
    }
    disconnectProgressWS()
  }

  onUnmounted(() => {
    if (pollingTimer.value) clearInterval(pollingTimer.value)
    disconnectProgressWS()
  })

  return {
    currentTaskId,
    analysisStatus,
    progressInfo,
    analysisSteps,
    pollingTimer,
    startPollingTaskStatus,
    updateProgressInfo,
    connectProgressWS,
    disconnectProgressWS,
    toggleStepExpand,
    formatTime,
    getProgressStatus,
    saveTaskToCache,
    getTaskFromCache,
    clearTaskCache,
    restoreTaskFromCache,
    resetProgress
  }
}

import { ref } from 'vue'
import { configApi } from '@/api/config'
import { recommendModels, validateModels, type ModelRecommendationResponse } from '@/api/modelCapabilities'

/**
 * 模型配置 composable
 * 负责模型设置、推荐、适用性检查
 */
export function useModelConfig() {
  const availableModels = ref<any[]>([])
  const modelRecommendation = ref<{
    title: string
    message: string
    type: 'success' | 'warning' | 'info' | 'error'
    quickModel?: string
    deepModel?: string
  } | null>(null)

  const initializeModelSettings = async (modelSettings: { quickAnalysisModel: string; deepAnalysisModel: string }) => {
    try {
      const defaultModels = await configApi.getDefaultModels()
      modelSettings.quickAnalysisModel = defaultModels.quick_analysis_model
      modelSettings.deepAnalysisModel = defaultModels.deep_analysis_model

      const llmConfigs = await configApi.getLLMConfigs()
      availableModels.value = llmConfigs.filter((config: any) => config.enabled)

      console.log('✅ 加载模型配置成功:', {
        quick: modelSettings.quickAnalysisModel,
        deep: modelSettings.deepAnalysisModel,
        available: availableModels.value.length
      })
    } catch (error) {
      console.error('加载默认模型配置失败:', error)
      modelSettings.quickAnalysisModel = 'qwen-turbo'
      modelSettings.deepAnalysisModel = 'qwen-max'
    }
  }

  const checkModelSuitability = async (
    researchDepth: number,
    modelSettings: { quickAnalysisModel: string; deepAnalysisModel: string }
  ) => {
    try {
      const response = await recommendModels({
        research_depth: researchDepth,
        quick_model: modelSettings.quickAnalysisModel,
        deep_model: modelSettings.deepAnalysisModel
      })

      if (response.success && response.data) {
        const responseData = response.data
        const quickModel = responseData.quick_model || '未知'
        const deepModel = responseData.deep_model || '未知'

        const quickModelInfo = availableModels.value.find(m => m.model_name === quickModel)
        const deepModelInfo = availableModels.value.find(m => m.model_name === deepModel)

        const quickDisplayName = quickModelInfo?.model_display_name || quickModel
        const deepDisplayName = deepModelInfo?.model_display_name || deepModel

        const reason = responseData.reason || ''

        const depthDescriptions: Record<number, string> = {
          1: '快速浏览，获取基本信息',
          2: '基础分析，了解主要指标',
          3: '标准分析，全面评估股票',
          4: '深度研究，挖掘投资机会',
          5: '全面分析，专业投资决策'
        }

        const message = `${depthDescriptions[researchDepth] || '标准分析'}\n\n推荐模型配置：\n• 快速模型：${quickDisplayName}\n• 深度模型：${deepDisplayName}\n\n${reason}`

        modelRecommendation.value = {
          title: '💡 模型推荐',
          message,
          type: 'info',
          quickModel,
          deepModel
        }
      } else {
        setGeneralRecommendation(researchDepth)
      }
    } catch (error) {
      console.error('获取模型推荐失败:', error)
      setGeneralRecommendation(researchDepth)
    }
  }

  const setGeneralRecommendation = (researchDepth: number) => {
    const generalDescriptions: Record<number, string> = {
      1: '快速分析：使用基础模型即可，注重速度和成本',
      2: '基础分析：快速模型用基础级，深度模型用标准级',
      3: '标准分析：快速模型用基础级，深度模型用标准级以上',
      4: '深度分析：快速模型用标准级，深度模型用高级以上，需要推理能力',
      5: '全面分析：快速模型用标准级，深度模型用专业级以上，强推理能力'
    }
    modelRecommendation.value = {
      title: '💡 模型推荐',
      message: generalDescriptions[researchDepth] || generalDescriptions[3],
      type: 'info'
    }
  }

  const applyRecommendedModels = (modelSettings: { quickAnalysisModel: string; deepAnalysisModel: string }) => {
    if (modelRecommendation.value?.quickModel && modelRecommendation.value?.deepModel) {
      modelSettings.quickAnalysisModel = modelRecommendation.value.quickModel
      modelSettings.deepAnalysisModel = modelRecommendation.value.deepModel
      modelRecommendation.value = null
      return true
    }
    return false
  }

  return {
    availableModels,
    modelRecommendation,
    initializeModelSettings,
    checkModelSuitability,
    applyRecommendedModels
  }
}

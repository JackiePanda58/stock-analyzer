import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { validateStockCode, getStockCodeFormatHelp } from '@/utils/stockValidator'
import { normalizeMarketForAnalysis, getMarketByStockCode } from '@/utils/market'
import { ANALYSTS, convertAnalystNamesToIds } from '@/constants/analysts'
import type { SingleAnalysisRequest } from '@/api/analysis'

type MarketType = 'A股' | '美股' | '港股'

interface AnalysisForm {
  stockCode: string
  symbol: string
  market: MarketType
  analysisDate: Date
  researchDepth: number
  selectedAnalysts: string[]
  includeSentiment: boolean
  includeRisk: boolean
  language: 'zh-CN' | 'en-US'
}

/**
 * 分析表单 composable
 * 负责表单状态、验证、分析师选择、深度选项
 */
export function useAnalysisForm() {
  const stockCodeError = ref<string>('')
  const stockCodeHelp = ref<string>('')

  const depthOptions = [
    { icon: '⚡', name: '1级 - 快速分析', description: '基础数据概览，快速决策', time: '2-5分钟' },
    { icon: '📈', name: '2级 - 基础分析', description: '常规投资决策', time: '3-6分钟' },
    { icon: '🎯', name: '3级 - 标准分析', description: '技术+基本面，推荐', time: '4-8分钟' },
    { icon: '🔍', name: '4级 - 深度分析', description: '多轮辩论，深度研究', time: '6-11分钟' },
    { icon: '🏆', name: '5级 - 全面分析', description: '最全面的分析报告', time: '8-16分钟' }
  ]

  const analysisForm = reactive<AnalysisForm>({
    stockCode: '',
    symbol: '',
    market: 'A股',
    analysisDate: new Date(),
    researchDepth: 3,
    selectedAnalysts: ['市场分析师', '基本面分析师'],
    includeSentiment: true,
    includeRisk: true,
    language: 'zh-CN'
  })

  const modelSettings = ref({
    quickAnalysisModel: 'qwen-turbo',
    deepAnalysisModel: 'qwen-max'
  })

  const disabledDate = (time: Date) => {
    return time.getTime() > Date.now()
  }

  const onStockCodeInput = () => {
    stockCodeError.value = ''
    stockCodeHelp.value = getStockCodeFormatHelp(analysisForm.market)
  }

  const onMarketChange = () => {
    if (analysisForm.stockCode.trim()) {
      validateStockCodeInput()
    } else {
      stockCodeHelp.value = getStockCodeFormatHelp(analysisForm.market)
    }
  }

  const validateStockCodeInput = () => {
    const code = analysisForm.stockCode.trim()
    if (!code) {
      stockCodeError.value = ''
      stockCodeHelp.value = ''
      return
    }
    const validation = validateStockCode(code, analysisForm.market)
    if (!validation.valid) {
      stockCodeError.value = validation.message || '股票代码格式不正确'
      stockCodeHelp.value = ''
    } else {
      stockCodeError.value = ''
      stockCodeHelp.value = `✓ ${validation.market}代码格式正确`
      if (validation.market && validation.market !== analysisForm.market) {
        analysisForm.market = validation.market
        ElMessage.success(`已自动识别为${validation.market}`)
      }
      if (validation.normalizedCode) {
        analysisForm.stockCode = validation.normalizedCode
      }
    }
  }

  const toggleAnalyst = (analystName: string) => {
    if (analystName === '社媒分析师' && analysisForm.market === 'A股') return
    const index = analysisForm.selectedAnalysts.indexOf(analystName)
    if (index > -1) {
      analysisForm.selectedAnalysts.splice(index, 1)
    } else {
      analysisForm.selectedAnalysts.push(analystName)
    }
  }

  const buildAnalysisRequest = (): SingleAnalysisRequest | null => {
    const stockCode = analysisForm.stockCode.trim()
    if (!stockCode) {
      ElMessage.warning('请输入股票代码')
      return null
    }
    const validation = validateStockCode(stockCode, analysisForm.market)
    if (!validation.valid) {
      ElMessage.error(validation.message || '股票代码格式不正确')
      stockCodeError.value = validation.message || '股票代码格式不正确'
      return null
    }
    analysisForm.symbol = validation.normalizedCode || stockCode.toUpperCase()
    if (analysisForm.selectedAnalysts.length === 0) {
      ElMessage.warning('请至少选择一个分析师')
      return null
    }
    const analysisDate = analysisForm.analysisDate instanceof Date
      ? analysisForm.analysisDate
      : new Date(analysisForm.analysisDate)

    return {
      symbol: analysisForm.symbol,
      stock_code: analysisForm.symbol,
      parameters: {
        market_type: analysisForm.market,
        analysis_date: analysisDate.toISOString().split('T')[0],
        research_depth: Number(analysisForm.researchDepth) || 3,
        selected_analysts: convertAnalystNamesToIds(analysisForm.selectedAnalysts),
        include_sentiment: analysisForm.includeSentiment,
        include_risk: analysisForm.includeRisk,
        language: analysisForm.language,
        quick_analysis_model: modelSettings.value.quickAnalysisModel,
        deep_analysis_model: modelSettings.value.deepAnalysisModel
      }
    }
  }

  const getDepthDescription = (depth: number) => {
    const descriptions = ['快速', '基础', '标准', '深度', '全面']
    return descriptions[depth - 1] || '标准'
  }

  return {
    analysisForm,
    modelSettings,
    stockCodeError,
    stockCodeHelp,
    depthOptions,
    disabledDate,
    onStockCodeInput,
    onMarketChange,
    validateStockCodeInput,
    toggleAnalyst,
    buildAnalysisRequest,
    getDepthDescription
  }
}

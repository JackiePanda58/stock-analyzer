<template>
  <div class="analysis-result">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">
            <el-icon class="title-icon"><Document /></el-icon>
            分析报告
          </h1>
          <p class="page-description">
            AI 驱动的多维度股票投资价值评估
          </p>
        </div>
        <div class="header-actions">
          <el-button @click="goBack" :icon="ArrowLeft">返回</el-button>
          <el-button type="primary" :icon="Download" @click="exportReport">导出报告</el-button>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-container">
      <el-result icon="error" title="加载失败" :sub-title="error">
        <template #extra>
          <el-button type="primary" @click="loadAnalysis">重新加载</el-button>
        </template>
      </el-result>
    </div>

    <!-- 分析结果 -->
    <div v-else-if="result" class="result-container">
      <!-- 股票信息卡片 -->
      <el-card class="stock-info-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="card-title">📊 {{ result.stock_name }}</span>
            <el-tag :type="getRecommendationType(result.recommendation)" size="large">
              {{ result.recommendation }}
            </el-tag>
          </div>
        </template>
        
        <el-row :gutter="24">
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">股票代码</div>
              <div class="info-value">{{ result.symbol || result.stock_code }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">当前价格</div>
              <div class="info-value price">
                ¥{{ result.current_price?.toFixed(2) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">涨跌幅</div>
              <div class="info-value" :class="getPriceChangeClass(result.price_change_percent)">
                {{ result.price_change_percent > 0 ? '+' : '' }}{{ result.price_change_percent?.toFixed(2) }}%
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">分析日期</div>
              <div class="info-value">{{ formatDate(result.analysis_date) }}</div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 综合评分雷达图 -->
      <el-row :gutter="24" class="score-section">
        <el-col :span="12">
          <el-card class="score-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span class="card-title">🎯 综合评分</span>
              </div>
            </template>
            <div class="radar-chart-container">
              <v-chart
                class="radar-chart"
                :option="radarOption"
                autoresize
              />
            </div>
            <div class="total-score">
              <div class="score-value">{{ result.overall_score?.toFixed(1) }}</div>
              <div class="score-label">综合得分</div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="12">
          <el-card class="score-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span class="card-title">📈 评分详情</span>
              </div>
            </template>
            <div class="score-details">
              <div class="score-item">
                <div class="score-item-header">
                  <span class="score-item-label">📊 技术分析</span>
                  <span class="score-item-value" :class="getScoreClass(result.technical_score)">
                    {{ result.technical_score }}
                  </span>
                </div>
                <el-progress
                  :percentage="result.technical_score * 10"
                  :status="getScoreStatus(result.technical_score)"
                  :stroke-width="8"
                />
                <div class="score-item-desc">{{ result.technical_analysis?.substring(0, 100) }}...</div>
              </div>
              
              <div class="score-item">
                <div class="score-item-header">
                  <span class="score-item-label">💰 基本面分析</span>
                  <span class="score-item-value" :class="getScoreClass(result.fundamental_score)">
                    {{ result.fundamental_score }}
                  </span>
                </div>
                <el-progress
                  :percentage="result.fundamental_score * 10"
                  :status="getScoreStatus(result.fundamental_score)"
                  :stroke-width="8"
                />
                <div class="score-item-desc">{{ result.fundamental_analysis?.substring(0, 100) }}...</div>
              </div>
              
              <div class="score-item">
                <div class="score-item-header">
                  <span class="score-item-label">😊 情绪分析</span>
                  <span class="score-item-value" :class="getScoreClass(result.sentiment_score)">
                    {{ result.sentiment_score }}
                  </span>
                </div>
                <el-progress
                  :percentage="result.sentiment_score * 10"
                  :status="getScoreStatus(result.sentiment_score)"
                  :stroke-width="8"
                />
                <div class="score-item-desc">{{ result.sentiment_analysis?.substring(0, 100) }}...</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 详细分析标签页 -->
      <el-card class="detail-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="card-title">📋 详细分析</span>
          </div>
        </template>
        
        <el-tabs v-model="activeTab" class="detail-tabs">
          <el-tab-pane name="summary" label="📝 投资摘要">
            <div class="tab-content">
              <div class="summary-section">
                <h3>核心观点</h3>
                <p class="summary-text">{{ result.summary }}</p>
              </div>
              
              <div class="summary-section">
                <h3>投资建议</h3>
                <el-alert
                  :title="getRecommendationTitle(result.recommendation)"
                  :type="getRecommendationType(result.recommendation)"
                  :closable="false"
                  show-icon
                >
                  <template #default>
                    <p>{{ result.recommendation_detail || '基于多维度分析，该股票当前适合' + result.recommendation + '。' }}</p>
                  </template>
                </el-alert>
              </div>
              
              <div class="summary-section">
                <h3>风险提示</h3>
                <el-alert
                  title="风险因素"
                  type="warning"
                  :closable="false"
                  show-icon
                >
                  <template #default>
                    <p>{{ result.risk_assessment }}</p>
                  </template>
                </el-alert>
              </div>
            </div>
          </el-tab-pane>
          
          <el-tab-pane name="technical" label="📊 技术分析">
            <div class="tab-content">
              <div v-if="klineData" class="chart-section">
                <h3>K 线与指标</h3>
                <KLineChart :data="klineData" />
              </div>
              <div class="analysis-text">
                <div v-html="formatAnalysisText(result.technical_analysis)"></div>
              </div>
            </div>
          </el-tab-pane>
          
          <el-tab-pane name="fundamental" label="💰 基本面分析">
            <div class="tab-content">
              <div v-if="financialData" class="financial-section">
                <h3>财务指标</h3>
                <el-row :gutter="16">
                  <el-col :span="6">
                    <div class="metric-card">
                      <div class="metric-label">市盈率 (PE)</div>
                      <div class="metric-value">{{ financialData.pe_ratio }}</div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="metric-card">
                      <div class="metric-label">市净率 (PB)</div>
                      <div class="metric-value">{{ financialData.pb_ratio }}</div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="metric-card">
                      <div class="metric-label">ROE</div>
                      <div class="metric-value">{{ financialData.roe }}%</div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="metric-card">
                      <div class="metric-label">毛利率</div>
                      <div class="metric-value">{{ financialData.gross_margin }}%</div>
                    </div>
                  </el-col>
                </el-row>
              </div>
              <div class="analysis-text">
                <div v-html="formatAnalysisText(result.fundamental_analysis)"></div>
              </div>
            </div>
          </el-tab-pane>
          
          <el-tab-pane name="sentiment" label="😊 情绪分析">
            <div class="tab-content">
              <div class="sentiment-section">
                <h3>市场情绪</h3>
                <div class="sentiment-indicator">
                  <div class="sentiment-bar">
                    <div
                      class="sentiment-fill"
                      :style="{ width: (result.sentiment_score * 10) + '%' }"
                      :class="getSentimentClass(result.sentiment_score)"
                    ></div>
                  </div>
                  <div class="sentiment-label">
                    <span>悲观</span>
                    <span>{{ getSentimentLabel(result.sentiment_score) }}</span>
                    <span>乐观</span>
                  </div>
                </div>
              </div>
              <div class="analysis-text">
                <div v-html="formatAnalysisText(result.sentiment_analysis)"></div>
              </div>
            </div>
          </el-tab-pane>
          
          <el-tab-pane name="news" label="📰 新闻分析">
            <div class="tab-content">
              <div v-if="result.news_analysis" class="analysis-text">
                <div v-html="formatAnalysisText(result.news_analysis)"></div>
              </div>
              <el-empty v-else description="暂无新闻分析" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <!-- 数据来源与元数据 -->
      <el-card class="meta-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="card-title">ℹ️ 分析元数据</span>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="数据来源">
            <el-tag v-for="(source, index) in result.data_sources" :key="index" size="small" style="margin-right: 4px">
              {{ source }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="LLM 提供商">{{ result.llm_provider }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ result.llm_model }}</el-descriptions-item>
          <el-descriptions-item label="分析耗时">{{ (result.analysis_duration / 1000).toFixed(2) }}s</el-descriptions-item>
          <el-descriptions-item label="Token 消耗">
            {{ result.token_usage?.total_tokens || 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="分析 ID">{{ result.analysis_id }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Document,
  ArrowLeft,
  Download,
  TrendCharts,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import KLineChart from '@/components/Chart/KLineChart.vue'
import type { AnalysisResult } from '@/api/analysis'
import { analysisApi } from '@/api/analysis'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  RadarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
])

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const result = ref<AnalysisResult | null>(null)
const activeTab = ref('summary')
const klineData = ref(null)
const financialData = ref(null)

// 雷达图配置
const radarOption = computed(() => ({
  radar: {
    indicator: [
      { name: '技术分析', max: 10 },
      { name: '基本面', max: 10 },
      { name: '情绪', max: 10 },
      { name: '风险', max: 10 },
      { name: '成长', max: 10 },
    ],
    radius: '65%',
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: [
            result.value?.technical_score || 0,
            result.value?.fundamental_score || 0,
            result.value?.sentiment_score || 0,
            10 - (result.value?.risk_score || 5),
            result.value?.growth_score || 5,
          ],
          name: '综合评分',
          areaStyle: {
            color: 'rgba(64, 158, 255, 0.5)',
          },
          lineStyle: {
            color: '#409EFF',
          },
        },
      ],
    },
  ],
  tooltip: {
    trigger: 'item',
  },
}))

// 加载分析结果
const loadAnalysis = async () => {
  loading.value = true
  error.value = ''
  
  try {
    const analysisId = route.params.taskId as string
    const data = await analysisApi.getResult(analysisId)
    result.value = data
    
    // 加载 K 线数据
    // await loadKlineData(data.symbol)
    
    // 加载财务数据
    // await loadFinancialData(data.symbol)
  } catch (err: any) {
    error.value = err.message || '加载失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

// 返回上一页
const goBack = () => {
  router.back()
}

// 导出报告
const exportReport = () => {
  ElMessage.info('导出功能开发中...')
  // TODO: 实现 PDF/Excel 导出
}

// 格式化日期
const formatDate = (date: string) => {
  return new Date(date).toLocaleDateString('zh-CN')
}

// 获取推荐类型
const getRecommendationType = (recommendation: string) => {
  const map: Record<string, any> = {
    '买入': 'success',
    '强烈推荐': 'success',
    '持有': 'warning',
    '观望': 'info',
    '卖出': 'danger',
    '强烈卖出': 'danger',
  }
  return map[recommendation] || 'info'
}

// 获取推荐标题
const getRecommendationTitle = (recommendation: string) => {
  const map: Record<string, string> = {
    '买入': '建议买入',
    '强烈推荐': '强烈推荐买入',
    '持有': '建议持有',
    '观望': '建议观望',
    '卖出': '建议卖出',
    '强烈卖出': '强烈建议卖出',
  }
  return map[recommendation] || '投资建议'
}

// 获取价格变化样式
const getPriceChangeClass = (change: number) => {
  if (change > 0) return 'positive'
  if (change < 0) return 'negative'
  return 'neutral'
}

// 获取评分样式
const getScoreClass = (score: number) => {
  if (score >= 8) return 'excellent'
  if (score >= 6) return 'good'
  if (score >= 4) return 'average'
  return 'poor'
}

// 获取评分状态
const getScoreStatus = (score: number) => {
  if (score >= 8) return 'success'
  if (score >= 6) return 'warning'
  return 'exception'
}

// 获取情绪样式
const getSentimentClass = (score: number) => {
  if (score >= 7) return 'positive'
  if (score >= 4) return 'neutral'
  return 'negative'
}

// 获取情绪标签
const getSentimentLabel = (score: number) => {
  if (score >= 8) return '非常乐观'
  if (score >= 6) return '乐观'
  if (score >= 4) return '中性'
  if (score >= 2) return '悲观'
  return '非常悲观'
}

// 格式化分析文本
const formatAnalysisText = (text: string) => {
  if (!text) return ''
  return text
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/• /g, '• ')
}

onMounted(() => {
  loadAnalysis()
})
</script>

<style scoped lang="scss">
.analysis-result {
  padding: 24px;
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.page-header {
  margin-bottom: 24px;
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    
    .title-section {
      .page-title {
        display: flex;
        align-items: center;
        font-size: 28px;
        font-weight: 600;
        color: #303133;
        margin: 0 0 8px 0;
        
        .title-icon {
          margin-right: 12px;
          font-size: 32px;
          color: #409EFF;
        }
      }
      
      .page-description {
        font-size: 14px;
        color: #909399;
        margin: 0;
      }
    }
    
    .header-actions {
      display: flex;
      gap: 12px;
    }
  }
}

.loading-container,
.error-container {
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.result-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.stock-info-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    
    .card-title {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
    }
  }
  
  .info-item {
    padding: 12px;
    text-align: center;
    
    .info-label {
      font-size: 13px;
      color: #909399;
      margin-bottom: 8px;
    }
    
    .info-value {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
      
      &.price {
        color: #F56C6C;
      }
      
      &.positive {
        color: #F56C6C;
      }
      
      &.negative {
        color: #67C23A;
      }
      
      &.neutral {
        color: #909399;
      }
    }
  }
}

.score-section {
  .score-card {
    .card-header {
      .card-title {
        font-size: 16px;
        font-weight: 600;
        color: #303133;
      }
    }
    
    .radar-chart-container {
      height: 300px;
    }
    
    .radar-chart {
      width: 100%;
      height: 100%;
    }
    
    .total-score {
      text-align: center;
      margin-top: 16px;
      
      .score-value {
        font-size: 36px;
        font-weight: bold;
        color: #409EFF;
      }
      
      .score-label {
        font-size: 14px;
        color: #909399;
        margin-top: 4px;
      }
    }
    
    .score-details {
      display: flex;
      flex-direction: column;
      gap: 20px;
      
      .score-item {
        .score-item-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
          
          .score-item-label {
            font-size: 14px;
            color: #606266;
          }
          
          .score-item-value {
            font-size: 18px;
            font-weight: 600;
            
            &.excellent {
              color: #67C23A;
            }
            
            &.good {
              color: #409EFF;
            }
            
            &.average {
              color: #E6A23C;
            }
            
            &.poor {
              color: #F56C6C;
            }
          }
        }
        
        .score-item-desc {
          font-size: 13px;
          color: #909399;
          margin-top: 8px;
          line-height: 1.5;
        }
      }
    }
  }
}

.detail-card {
  .card-header {
    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
  }
  
  .detail-tabs {
    .tab-content {
      padding: 16px 0;
      
      .summary-section {
        margin-bottom: 24px;
        
        h3 {
          font-size: 16px;
          font-weight: 600;
          color: #303133;
          margin: 0 0 12px 0;
        }
        
        .summary-text {
          font-size: 14px;
          color: #606266;
          line-height: 1.8;
          white-space: pre-wrap;
        }
      }
      
      .chart-section {
        margin-bottom: 24px;
        
        h3 {
          font-size: 16px;
          font-weight: 600;
          color: #303133;
          margin: 0 0 12px 0;
        }
      }
      
      .analysis-text {
        font-size: 14px;
        color: #606266;
        line-height: 1.8;
        
        :deep(strong) {
          color: #303133;
          font-weight: 600;
        }
      }
      
      .financial-section {
        margin-bottom: 24px;
        
        h3 {
          font-size: 16px;
          font-weight: 600;
          color: #303133;
          margin: 0 0 16px 0;
        }
        
        .metric-card {
          padding: 16px;
          background: linear-gradient(135deg, #f5f7fa 0%, #e8ebef 100%);
          border-radius: 8px;
          text-align: center;
          
          .metric-label {
            font-size: 13px;
            color: #909399;
            margin-bottom: 8px;
          }
          
          .metric-value {
            font-size: 20px;
            font-weight: 600;
            color: #303133;
          }
        }
      }
      
      .sentiment-section {
        h3 {
          font-size: 16px;
          font-weight: 600;
          color: #303133;
          margin: 0 0 16px 0;
        }
        
        .sentiment-indicator {
          padding: 20px;
          
          .sentiment-bar {
            height: 24px;
            background: linear-gradient(to right, #F56C6C 0%, #E6A23C 50%, #67C23A 100%);
            border-radius: 12px;
            position: relative;
            overflow: hidden;
            
            .sentiment-fill {
              position: absolute;
              top: 0;
              left: 0;
              height: 100%;
              border-radius: 12px;
              transition: width 0.3s ease;
              
              &.positive {
                background: rgba(103, 194, 58, 0.8);
              }
              
              &.neutral {
                background: rgba(230, 162, 60, 0.8);
              }
              
              &.negative {
                background: rgba(245, 108, 108, 0.8);
              }
            }
          }
          
          .sentiment-label {
            display: flex;
            justify-content: space-between;
            margin-top: 8px;
            font-size: 13px;
            color: #909399;
          }
        }
      }
    }
  }
}

.meta-card {
  .card-header {
    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
  }
}

.positive {
  color: #F56C6C;
}

.negative {
  color: #67C23A;
}

.neutral {
  color: #909399;
}
</style>

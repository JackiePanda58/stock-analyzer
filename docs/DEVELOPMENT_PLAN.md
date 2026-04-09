# TradingAgents-CN 开发计划

**版本**: 1.0  
**日期**: 2026-04-09  
**状态**: 进行中

---

## 📊 当前状态

### ✅ 已完成功能

#### 后端 (FastAPI - 端口 8080)
- ✅ 股票数据 API (A 股/美股/港股)
- ✅ 自选股管理
- ✅ 分析任务提交
- ✅ JWT 认证
- ✅ Redis 缓存
- ✅ SQLite 用量追踪
- ✅ WebSocket 实时推送 (端口 8030)

#### 前端 (Vue3 + Vite - 端口 62879)
- ✅ 单股分析页面 (3436 行)
- ✅ 批量分析页面
- ✅ 分析历史页面
- ✅ 17 个视图组件
- ✅ Element Plus UI
- ✅ ECharts 图表

### ⚠️ 待完成功能

#### 高优先级 (P0)
1. **分析结果展示页面** - 查看智能分析报告
2. **K 线图表组件** - 技术分析可视化
3. **实时行情推送** - WebSocket 集成
4. **用户认证流程** - 登录/注册/Token 刷新

#### 中优先级 (P1)
5. **Dashboard 仪表盘** - 市场概览
6. **选股器** - 条件筛选
7. **模拟交易** - Paper Trading
8. **学习中心** - 投资知识

#### 低优先级 (P2)
9. **任务队列管理** - 分析任务调度
10. **系统设置** - 模型配置
11. **报表导出** - PDF/Excel

---

## 🎯 下一阶段开发计划

### 阶段 1: 核心功能完善 (本周)

#### 1.1 分析结果展示页面
**文件**: `frontend/src/views/Analysis/AnalysisResult.vue`

**功能**:
- 智能分析报告展示
- 多维度评分可视化 (雷达图)
- 买入/持有/卖出建议
- 风险提示
- 数据来源说明

**技术实现**:
```vue
<template>
  <div class="analysis-result">
    <!-- 头部：股票信息 + 总体建议 -->
    <ResultHeader :stock="stockInfo" :recommendation="result.recommendation" />
    
    <!-- 评分雷达图 -->
    <ScoreRadarChart :scores="result.scores" />
    
    <!-- 详细分析 -->
    <el-tabs>
      <el-tab-pane label="技术分析">
        <TechnicalAnalysis :data="result.technical_analysis" />
      </el-tab-pane>
      <el-tab-pane label="基本面分析">
        <FundamentalAnalysis :data="result.fundamental_analysis" />
      </el-tab-pane>
      <el-tab-pane label="情绪分析">
        <SentimentAnalysis :data="result.sentiment_analysis" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
```

#### 1.2 K 线图表组件
**文件**: `frontend/src/components/Chart/KLineChart.vue`

**功能**:
- K 线图 (蜡烛图)
- 均线 (MA5/MA10/MA20)
- 成交量
- MACD/KDJ指标
- 缩放/平移

**依赖**: `echarts`, `vue-echarts`

#### 1.3 WebSocket 实时推送
**文件**: `frontend/src/utils/websocket.ts`

**功能**:
- 连接管理
- 心跳检测
- 自动重连
- 消息分发

```typescript
class WebSocketClient {
  private ws: WebSocket | null = null
  private reconnectTimer: number | null = null
  
  connect(url: string) {
    this.ws = new WebSocket(url)
    this.ws.onopen = this.handleOpen
    this.ws.onmessage = this.handleMessage
    this.ws.onclose = this.handleClose
    this.ws.onerror = this.handleError
  }
  
  subscribe(channel: string, callback: (data: any) => void) {
    // 订阅频道
  }
  
  unsubscribe(channel: string) {
    // 取消订阅
  }
}
```

---

### 阶段 2: 用户体验优化 (下周)

#### 2.1 Dashboard 仪表盘
**文件**: `frontend/src/views/Dashboard/index.vue`

**功能**:
- 市场指数卡片 (上证/深证/恒生/纳指)
- 自选股列表
- 最新分析报告
- 系统状态

#### 2.2 选股器
**文件**: `frontend/src/views/Screening/index.vue`

**功能**:
- 条件筛选 (PE/PB/市值/涨幅)
- 技术形态筛选
- 结果排序
- 导出功能

---

### 阶段 3: 高级功能 (下下周)

#### 3.1 模拟交易
**文件**: `frontend/src/views/PaperTrading/index.vue`

**功能**:
- 虚拟账户
- 买入/卖出
- 持仓管理
- 收益统计

#### 3.2 学习中心
**文件**: `frontend/src/views/Learning/index.vue`

**功能**:
- 投资知识库
- 技术分析教程
- 视频课程
- 测验

---

## 📋 技术债务

### 后端
- [ ] 统一错误处理中间件
- [ ] API 文档 (Swagger/OpenAPI)
- [ ] 单元测试覆盖率 > 80%
- [ ] 性能优化 (缓存策略)

### 前端
- [ ] TypeScript 类型完善
- [ ] 组件单元测试
- [ ] 响应式布局优化
- [ ] 加载状态统一处理

---

## 🚀 发布计划

| 版本 | 日期 | 功能 |
|------|------|------|
| v1.0.0 | 2026-04-15 | 核心分析功能 + 结果展示 |
| v1.1.0 | 2026-04-22 | Dashboard + 选股器 |
| v1.2.0 | 2026-04-29 | 模拟交易 + 学习中心 |
| v2.0.0 | 2026-05-15 | 多用户 + 付费功能 |

---

## 📝 下一步行动

### 立即执行
1. 创建 `AnalysisResult.vue` 组件
2. 创建 `KLineChart.vue` 组件
3. 实现 WebSocket 客户端

### 本周完成
1. 分析结果页面联调后端 API
2. K 线图数据对接
3. 实时推送测试

---

**使用技能**: `frontend-patterns`, `create-prd`, `product-strategy`

<template>
  <div class="kline-chart">
    <v-chart
      ref="chartRef"
      class="kline-chart-container"
      :option="chartOption"
      :autoresize="true"
      @datazoom="handleDataZoom"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  AxisPointerComponent,
  ToolboxComponent,
  DataZoomComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  AxisPointerComponent,
  ToolboxComponent,
  DataZoomComponent,
  TooltipComponent,
  LegendComponent,
])

interface KLineDataPoint {
  date: string
  open: number
  close: number
  low: number
  high: number
  volume: number
  amount?: number
}

interface Props {
  data?: KLineDataPoint[] | null
  showMA?: boolean
  showVolume?: boolean
  showMACD?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  data: () => [],
  showMA: true,
  showVolume: true,
  showMACD: false,
})

const chartRef = ref<any>(null)

// 计算 MA 均线
const calculateMA = (dayCount: number, data: any[]) => {
  const result = []
  for (let i = 0, len = data.length; i < len; i++) {
    if (i < dayCount) {
      result.push('-')
      continue
    }
    let sum = 0
    for (let j = 0; j < dayCount; j++) {
      sum += data[i - j][1] // 收盘价
    }
    result.push(+(sum / dayCount).toFixed(2))
  }
  return result
}

// 图表配置
const chartOption = computed(() => {
  if (!props.data || props.data.length === 0) {
    return {}
  }

  const dates = props.data.map(item => item.date)
  const values = props.data.map(item => [
    item.open,
    item.close,
    item.low,
    item.high,
  ])
  const volumes = props.data.map(item => item.volume)
  const closes = props.data.map(item => item.close)

  // 计算 MA
  const ma5 = calculateMA(5, values)
  const ma10 = calculateMA(10, values)
  const ma20 = calculateMA(20, values)

  return {
    backgroundColor: '#ffffff',
    animation: false,
    legend: {
      data: ['K 线', 'MA5', 'MA10', 'MA20', '成交量'],
      top: 10,
      left: 'center',
      textStyle: {
        color: '#666',
      },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
      borderWidth: 1,
      borderColor: '#ccc',
      padding: 10,
      textStyle: {
        color: '#000',
      },
      position: (key: any, params: any, dom: any, rect: any, size: any) => {
        return [key[0] - 100, key[1] - 80]
      },
      formatter: (params: any) => {
        let html = `<div style="font-weight:bold;">${params[0].axisValue}</div>`
        params.forEach((param: any) => {
          const color = param.color || '#999'
          const name = param.seriesName || param.name
          const value = param.value
          if (param.seriesType === 'candlestick') {
            html += `<div style="color:${color};">
              ${name}: O:${value[1]} C:${value[2]} L:${value[3]} H:${value[4]}
            </div>`
          } else if (param.seriesType === 'bar') {
            html += `<div style="color:${color};">${name}: ${value}</div>`
          } else if (value !== '-') {
            html += `<div style="color:${color};">${name}: ${value}</div>`
          }
        })
        return html
      },
    },
    axisPointer: {
      link: [
        { xAxisIndex: 'all' },
      ],
      label: {
        backgroundColor: '#777',
      },
    },
    toolbox: {
      feature: {
        dataZoom: {
          yAxisIndex: false,
        },
        brush: {
          type: ['lineX', 'clear'],
        },
      },
    },
    brush: {
      xAxisIndex: 'all',
      link: 'all',
      toolBox: ['rect', 'polygon', 'keep', 'clear'],
      outOfBrush: {
        colorAlpha: 0.1,
      },
    },
    grid: [
      {
        left: '10%',
        right: '8%',
        top: '15%',
        height: '50%',
      },
      {
        left: '10%',
        right: '8%',
        top: '70%',
        height: '15%',
      },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
        axisPointer: {
          z: 100,
        },
        gridIndex: 0,
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: false,
        axisLabel: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        splitArea: {
          show: true,
          areaStyle: {
            color: ['rgba(250,250,250,0.3)', 'rgba(200,200,200,0.3)'],
          },
        },
        gridIndex: 0,
        splitLine: {
          lineStyle: {
            color: '#eee',
          },
        },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100,
        minValueSpan: 20,
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        bottom: 10,
        start: 50,
        end: 100,
        height: 20,
        borderColor: 'transparent',
        backgroundColor: '#e2e2e2',
        fillerColor: 'rgba(167,183,204,0.5)',
        handleStyle: {
          color: '#409EFF',
        },
      },
    ],
    series: [
      {
        name: 'K 线',
        type: 'candlestick',
        data: values,
        itemStyle: {
          color: '#F56C6C',
          color0: '#67C23A',
          borderColor: '#F56C6C',
          borderColor0: '#67C23A',
        },
        xAxisIndex: 0,
        yAxisIndex: 0,
      },
      {
        name: 'MA5',
        type: 'line',
        data: ma5,
        smooth: true,
        lineStyle: {
          opacity: 0.5,
          color: '#E6A23C',
        },
        xAxisIndex: 0,
        yAxisIndex: 0,
      },
      {
        name: 'MA10',
        type: 'line',
        data: ma10,
        smooth: true,
        lineStyle: {
          opacity: 0.5,
          color: '#409EFF',
        },
        xAxisIndex: 0,
        yAxisIndex: 0,
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        smooth: true,
        lineStyle: {
          opacity: 0.5,
          color: '#909399',
        },
        xAxisIndex: 0,
        yAxisIndex: 0,
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: (params: any) => {
            const dataIndex = params.dataIndex
            const open = values[dataIndex][0]
            const close = values[dataIndex][1]
            return open > close ? '#67C23A' : '#F56C6C'
          },
        },
      },
    ],
  }
})

// 处理数据缩放
const handleDataZoom = (params: any) => {
  // 可以在这里添加数据预加载逻辑
  console.log('Data zoom:', params)
}

// 暴露方法供外部调用
const zoomTo = (start: number, end: number) => {
  if (chartRef.value) {
    chartRef.value.dispatchAction({
      type: 'dataZoom',
      start,
      end,
    })
  }
}

defineExpose({
  zoomTo,
})
</script>

<style scoped lang="scss">
.kline-chart {
  width: 100%;
  height: 500px;
  
  .kline-chart-container {
    width: 100%;
    height: 100%;
  }
}
</style>

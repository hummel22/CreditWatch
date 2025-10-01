<script setup>
import { computed } from 'vue'
import Highcharts from 'highcharts'
import drilldownModule from 'highcharts/modules/drilldown'
import { Chart } from 'highcharts-vue'

if (!Highcharts.__creditwatchDrilldownInitialized) {
  drilldownModule(Highcharts)
  Highcharts.__creditwatchDrilldownInitialized = true
}

const props = defineProps({
  series: {
    type: Array,
    default: () => []
  },
  drilldownSeries: {
    type: Array,
    default: () => []
  },
  ariaLabel: {
    type: String,
    default: 'Pie chart with drilldown'
  }
})

const formatter = new Intl.NumberFormat(undefined, {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

const chartOptions = computed(() => {
  const primarySeries = (props.series || []).map((point) => ({
    name: point.name ?? point.label,
    y: Number(point.y ?? point.value ?? 0),
    color: point.color,
    drilldown: point.drilldown,
    displayValue: point.displayValue || formatter.format(Number(point.y ?? point.value ?? 0))
  }))

  const drilldownSeries = (props.drilldownSeries || []).map((series) => ({
    ...series,
    data: (series.data || []).map((entry) => ({
      name: entry.name ?? entry.label,
      y: Number(entry.y ?? entry.value ?? 0),
      displayValue: entry.displayValue || formatter.format(Number(entry.y ?? entry.value ?? 0))
    }))
  }))

  return {
    chart: {
      type: 'pie',
      backgroundColor: 'transparent'
    },
    title: { text: undefined },
    subtitle: { text: undefined },
    accessibility: {
      announceNewData: {
        enabled: true
      }
    },
    legend: {
      enabled: false
    },
    credits: {
      enabled: false
    },
    tooltip: {
      useHTML: true,
      formatter() {
        const point = this.point || {}
        const label = point.name || point.category
        const value = point.displayValue || formatter.format(Number(point.y || 0))
        return `<strong>${label}</strong><br/><span>${value}</span>`
      }
    },
    plotOptions: {
      series: {
        borderWidth: 0,
        dataLabels: {
          enabled: true,
          formatter() {
            const point = this.point || {}
            const label = point.name || point.category
            const value = point.displayValue || formatter.format(Number(point.y || 0))
            return `<span style="font-weight:600;">${label}</span><br/><span style="color:var(--color-text-tertiary,#64748b);">${value}</span>`
          },
          style: {
            textOutline: 'none',
            fontSize: '11px'
          }
        }
      }
    },
    series: [
      {
        name: 'Annual fees',
        colorByPoint: true,
        data: primarySeries
      }
    ],
    drilldown: {
      activeAxisLabelStyle: {
        color: 'var(--color-text-heading, #0f172a)'
      },
      activeDataLabelStyle: {
        color: 'var(--color-text-heading, #0f172a)'
      },
      series: drilldownSeries.map((series) => ({
        type: 'column',
        ...series,
        data: series.data.map((entry) => ({
          name: entry.name,
          y: entry.y,
          displayValue: entry.displayValue
        }))
      }))
    }
  }
})
</script>

<template>
  <div class="drilldown-pie-chart" role="img" :aria-label="ariaLabel">
    <Chart :options="chartOptions" :highcharts="Highcharts" class="drilldown-pie-chart__chart" />
  </div>
</template>

<style scoped>
.drilldown-pie-chart {
  width: 100%;
  display: flex;
  justify-content: center;
}

.drilldown-pie-chart__chart {
  width: 100%;
}
</style>

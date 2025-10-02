<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Highcharts from 'highcharts'
import accessibilityModule from 'highcharts/modules/accessibility'

if (!Highcharts.__creditwatchAccessibilityInitialized) {
  accessibilityModule(Highcharts)
  Highcharts.__creditwatchAccessibilityInitialized = true
}

const FALLBACK_COLORS = [
  '#22c55e',
  '#6366f1',
  '#0ea5e9',
  '#f97316',
  '#ec4899',
  '#a855f7',
  '#14b8a6',
  '#4f46e5'
]

const props = defineProps({
  points: {
    type: Array,
    default: () => []
  },
  series: {
    type: Array,
    default: () => []
  },
  ariaLabel: {
    type: String,
    default: 'Line chart'
  },
  yMax: {
    type: Number,
    default: null
  }
})

const normalizedSeries = computed(() =>
  (props.series || []).map((entry, index) => ({
    key: entry?.key || `series-${index + 1}`,
    label:
      typeof entry?.label === 'string' && entry.label.trim()
        ? entry.label.trim()
        : `Series ${index + 1}`,
    color: entry?.color || FALLBACK_COLORS[index % FALLBACK_COLORS.length]
  }))
)

const normalizedPoints = computed(() =>
  (props.points || []).map((point, index) => ({
    label:
      typeof point?.label === 'string' && point.label.trim()
        ? point.label.trim()
        : `Point ${index + 1}`,
    values: point?.values && typeof point.values === 'object' ? point.values : {}
  }))
)

const accessibleRows = computed(() =>
  normalizedPoints.value.map((point) => ({
    label: point.label,
    values: normalizedSeries.value.map((series) => ({
      label: series.label,
      value: Number(point.values?.[series.key] ?? 0)
    }))
  }))
)

const yAxisMax = computed(() => {
  if (typeof props.yMax === 'number' && Number.isFinite(props.yMax) && props.yMax > 0) {
    return props.yMax
  }
  let max = 0
  for (const point of accessibleRows.value) {
    for (const entry of point.values) {
      if (Number.isFinite(entry.value) && entry.value > max) {
        max = entry.value
      }
    }
  }
  return max > 0 ? max : null
})

const formatter = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2
})

const chartOptions = computed(() => {
  const categories = normalizedPoints.value.map((point) => point.label)

  const chartSeries = normalizedSeries.value.map((series) => ({
    type: 'line',
    name: series.label,
    color: series.color,
    data: normalizedPoints.value.map((point) => {
      const raw = Number(point.values?.[series.key] ?? 0)
      const value = Number.isFinite(raw) ? raw : 0
      return value
    }),
    tooltip: {
      valueSuffix: ''
    }
  }))

  return {
    chart: {
      type: 'line',
      backgroundColor: 'transparent',
      height: 320
    },
    title: { text: undefined },
    subtitle: { text: undefined },
    credits: { enabled: false },
    legend: {
      itemStyle: {
        color: 'var(--color-text-secondary, #475569)'
      }
    },
    xAxis: {
      categories,
      title: { text: undefined },
      labels: {
        style: {
          color: 'var(--color-text-secondary, #64748b)'
        }
      }
    },
    yAxis: {
      min: 0,
      max: yAxisMax.value ?? undefined,
      title: { text: undefined },
      labels: {
        formatter() {
          return formatter.format(this.value)
        },
        style: {
          color: 'var(--color-text-secondary, #64748b)'
        }
      }
    },
    tooltip: {
      shared: true,
      formatter() {
        const header = `<strong>${this.x}</strong>`
        const points = (this.points || [])
          .map((point) => {
            const value = formatter.format(point.y)
            const colorSwatch = `<span style="background:${point.color};width:0.75rem;height:0.75rem;border-radius:9999px;display:inline-block;margin-right:0.5rem;"></span>`
            return `<div style="display:flex;align-items:center;gap:0.5rem;">${colorSwatch}<span>${point.series.name}: ${value}</span></div>`
          })
          .join('')
        return `${header}<div style="margin-top:0.5rem;display:flex;flex-direction:column;gap:0.25rem;">${points}</div>`
      }
    },
    plotOptions: {
      series: {
        marker: {
          enabled: true,
          radius: 3
        }
      }
    },
    accessibility: {
      description: props.ariaLabel,
      keyboardNavigation: {
        enabled: true
      }
    },
    series: chartSeries
  }
})

const chartContainer = ref(null)
let chartInstance = null

function renderChart() {
  if (!chartContainer.value) {
    return
  }

  const options = chartOptions.value

  if (chartInstance) {
    chartInstance.update(options, true, true)
  } else {
    chartInstance = Highcharts.chart(chartContainer.value, options)
  }
}

onMounted(() => {
  renderChart()
})

watch(
  chartOptions,
  () => {
    renderChart()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }
})
</script>

<template>
  <figure class="simple-line-chart" role="img" :aria-label="ariaLabel">
    <div ref="chartContainer" class="simple-line-chart__chart" />
    <table class="sr-only">
      <caption>{{ ariaLabel }}</caption>
      <thead>
        <tr>
          <th scope="col">Period</th>
          <th v-for="seriesEntry in normalizedSeries" :key="seriesEntry.key" scope="col">
            {{ seriesEntry.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in accessibleRows" :key="row.label">
          <th scope="row">{{ row.label }}</th>
          <td v-for="entry in row.values" :key="entry.label">{{ formatter.format(entry.value) }}</td>
        </tr>
      </tbody>
    </table>
  </figure>
</template>

<style scoped>
.simple-line-chart {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.simple-line-chart__chart {
  width: 100%;
}

.sr-only {
  border: 0 !important;
  clip: rect(0 0 0 0) !important;
  height: 1px !important;
  margin: -1px !important;
  overflow: hidden !important;
  padding: 0 !important;
  position: absolute !important;
  width: 1px !important;
}
</style>

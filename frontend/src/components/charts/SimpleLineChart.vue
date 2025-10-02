<script setup>
import { computed } from 'vue'
import VueApexCharts from 'vue3-apexcharts'

const ApexChart = VueApexCharts

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
  },
  yMin: {
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
  if (typeof props.yMax === 'number' && Number.isFinite(props.yMax)) {
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

const yAxisMin = computed(() => {
  if (typeof props.yMin === 'number' && Number.isFinite(props.yMin)) {
    return props.yMin
  }
  let min = 0
  for (const point of accessibleRows.value) {
    for (const entry of point.values) {
      if (Number.isFinite(entry.value) && entry.value < min) {
        min = entry.value
      }
    }
  }
  return min < 0 ? min : 0
})

const formatter = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2
})

const apexSeries = computed(() =>
  normalizedSeries.value.map((series) => ({
    name: series.label,
    data: normalizedPoints.value.map((point) => {
      const raw = Number(point.values?.[series.key] ?? 0)
      return Number.isFinite(raw) ? raw : 0
    })
  }))
)

const chartOptions = computed(() => ({
  chart: {
    type: 'line',
    height: 320,
    background: 'transparent',
    toolbar: { show: false },
    animations: { enabled: false }
  },
  stroke: {
    width: 2,
    curve: 'straight'
  },
  markers: {
    size: 4
  },
  dataLabels: {
    enabled: false
  },
  colors: normalizedSeries.value.map((series) => series.color),
  legend: {
    labels: {
      colors: 'var(--color-text-secondary, #475569)'
    }
  },
  xaxis: {
    categories: normalizedPoints.value.map((point) => point.label),
    labels: {
      style: {
        colors: 'var(--color-text-secondary, #64748b)'
      }
    },
    axisBorder: {
      color: 'var(--color-border-subtle, #e2e8f0)'
    },
    axisTicks: {
      color: 'var(--color-border-subtle, #e2e8f0)'
    }
  },
  yaxis: {
    min: yAxisMin.value ?? undefined,
    max: yAxisMax.value ?? undefined,
    labels: {
      formatter(value) {
        return formatter.format(value)
      },
      style: {
        colors: 'var(--color-text-secondary, #64748b)'
      }
    }
  },
  grid: {
    borderColor: 'var(--color-border-subtle, #e2e8f0)'
  },
  tooltip: {
    shared: true,
    y: {
      formatter(value) {
        return formatter.format(value)
      }
    }
  }
}))
</script>

<template>
  <figure class="simple-line-chart" role="img" :aria-label="ariaLabel">
    <ApexChart
      type="line"
      height="320"
      class="simple-line-chart__chart"
      :options="chartOptions"
      :series="apexSeries"
    />
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

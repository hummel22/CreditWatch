<script setup>
import { computed, ref, watchEffect } from 'vue'
import VueApexCharts from 'vue3-apexcharts'

const ApexChart = VueApexCharts

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
  },
  showLegend: {
    type: Boolean,
    default: true
  }
})

const formatter = new Intl.NumberFormat(undefined, {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

const normalizedSeries = computed(() =>
  (props.series || [])
    .map((point, index) => {
      const value = Number(point.y ?? point.value ?? 0)
      const safeValue = Number.isFinite(value) && value > 0 ? value : 0
      if (safeValue <= 0) {
        return null
      }
      const label =
        typeof point?.name === 'string' && point.name.trim()
          ? point.name.trim()
          : typeof point?.label === 'string' && point.label.trim()
            ? point.label.trim()
            : `Segment ${index + 1}`
      return {
        name: label,
        value: safeValue,
        color: point?.color,
        drilldownId: point?.drilldown,
        displayValue:
          point?.displayValue ||
          formatter.format(Number(point.y ?? point.value ?? 0))
      }
    })
    .filter((entry) => entry !== null)
)

const drilldownMap = computed(() => {
  const map = new Map()
  for (const series of props.drilldownSeries || []) {
    const id = typeof series?.id === 'string' ? series.id : series?.name
    if (!id) {
      continue
    }
    const data = (series.data || [])
      .map((entry, index) => {
        const value = Number(entry.y ?? entry.value ?? 0)
        const safeValue = Number.isFinite(value) && value > 0 ? value : 0
        if (safeValue <= 0) {
          return null
        }
        const rawLabel =
          typeof entry?.name === 'string' && entry.name.trim()
            ? entry.name.trim()
            : typeof entry?.label === 'string' && entry.label.trim()
              ? entry.label.trim()
              : `Entry ${index + 1}`
        return {
          name: rawLabel,
          value: safeValue,
          displayValue:
            entry?.displayValue ||
            formatter.format(Number(entry.y ?? entry.value ?? 0))
        }
      })
      .filter((entry) => entry !== null)

    map.set(id, {
      id,
      name: series?.name || id,
      data
    })
  }
  return map
})

const currentDrilldownId = ref('')

const activeDrilldown = computed(() => {
  if (!currentDrilldownId.value) {
    return null
  }
  const drilldown = drilldownMap.value.get(currentDrilldownId.value) ?? null
  if (!drilldown || drilldown.data.length === 0) {
    return null
  }
  return drilldown
})

const hasDrilldown = computed(() => activeDrilldown.value !== null)

const apexPieSeries = computed(() => normalizedSeries.value.map((entry) => entry.value))

const pieOptions = computed(() => {
  const entries = normalizedSeries.value
  const colors = entries
    .map((entry) => (typeof entry.color === 'string' ? entry.color : null))
    .filter((color) => color)
  const legendOptions = props.showLegend
    ? {
        show: true,
        position: 'bottom',
        labels: {
          colors: 'var(--color-text-secondary, #475569)'
        }
      }
    : { show: false }
  return {
    chart: {
      type: 'pie',
      height: 320,
      background: 'transparent',
      toolbar: { show: false },
      animations: { enabled: false }
    },
    labels: entries.map((entry) => entry.name),
    ...(colors.length === entries.length ? { colors } : {}),
    legend: legendOptions,
    dataLabels: {
      formatter(val, opts) {
        const entry = entries[opts.seriesIndex]
        if (!entry) {
          return `${val.toFixed(1)}%`
        }
        return `${entry.name}: ${entry.displayValue}`
      },
      style: {
        colors: ['var(--color-text-heading, #0f172a)'],
        fontSize: '12px'
      },
      dropShadow: {
        enabled: false
      }
    },
    tooltip: {
      y: {
        formatter(value, { seriesIndex }) {
          const entry = entries[seriesIndex]
          if (!entry) {
            return formatter.format(value)
          }
          return entry.displayValue
        }
      }
    },
    stroke: {
      show: false
    }
  }
})

const activeDrilldownSeries = computed(() => {
  if (!activeDrilldown.value) {
    return []
  }
  return [
    {
      name: activeDrilldown.value.name,
      data: activeDrilldown.value.data.map((entry) => entry.value)
    }
  ]
})

const activeDrilldownOptions = computed(() => {
  const drilldown = activeDrilldown.value
  if (!drilldown) {
    return {}
  }
  const categories = drilldown.data.map((entry) => entry.name)
  const parent = normalizedSeries.value.find(
    (entry) => entry.drilldownId === currentDrilldownId.value
  )
  const baseColor = parent?.color || 'var(--color-accent, #6366f1)'
  return {
    chart: {
      type: 'bar',
      height: 320,
      background: 'transparent',
      toolbar: { show: false },
      animations: { enabled: false }
    },
    colors: [baseColor],
    plotOptions: {
      bar: {
        borderRadius: 4,
        columnWidth: '55%'
      }
    },
    dataLabels: {
      enabled: true,
      formatter(val, opts) {
        const entry = drilldown.data[opts.dataPointIndex]
        if (!entry) {
          return formatter.format(val)
        }
        return entry.displayValue
      },
      style: {
        colors: ['var(--color-text-heading, #0f172a)'],
        fontSize: '12px'
      }
    },
    xaxis: {
      categories,
      labels: {
        style: {
          colors: 'var(--color-text-secondary, #64748b)'
        }
      }
    },
    yaxis: {
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
      y: {
        formatter(value, { dataPointIndex }) {
          const entry = drilldown.data[dataPointIndex]
          if (!entry) {
            return formatter.format(value)
          }
          return entry.displayValue
        }
      }
    }
  }
})

function handleDataPointSelection(event, chartContext, config) {
  const index = config?.dataPointIndex
  if (typeof index !== 'number' || index < 0) {
    return
  }
  const entry = normalizedSeries.value[index]
  if (!entry?.drilldownId) {
    return
  }
  const drilldown = drilldownMap.value.get(entry.drilldownId)
  if (drilldown && drilldown.data.length) {
    currentDrilldownId.value = entry.drilldownId
  }
}

function resetDrilldown() {
  currentDrilldownId.value = ''
}

watchEffect(() => {
  if (currentDrilldownId.value && !drilldownMap.value.has(currentDrilldownId.value)) {
    currentDrilldownId.value = ''
  }
})
</script>

<template>
  <div class="drilldown-pie-chart" role="img" :aria-label="ariaLabel">
    <div v-if="hasDrilldown" class="drilldown-pie-chart__controls">
      <button type="button" class="drilldown-pie-chart__back" @click="resetDrilldown">
        ← Back
      </button>
    </div>
    <ApexChart
      v-if="!hasDrilldown"
      type="pie"
      height="320"
      class="drilldown-pie-chart__chart"
      :options="pieOptions"
      :series="apexPieSeries"
      @dataPointSelection="handleDataPointSelection"
    />
    <ApexChart
      v-else
      type="bar"
      height="320"
      class="drilldown-pie-chart__chart"
      :options="activeDrilldownOptions"
      :series="activeDrilldownSeries"
    />
  </div>
</template>

<style scoped>
.drilldown-pie-chart {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.drilldown-pie-chart__chart {
  width: 100%;
}

.drilldown-pie-chart__controls {
  display: flex;
  justify-content: flex-start;
}

.drilldown-pie-chart__back {
  background: none;
  border: none;
  color: var(--color-primary, #4f46e5);
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.drilldown-pie-chart__back:focus {
  outline: 2px solid var(--color-primary, #4f46e5);
  outline-offset: 2px;
}
</style>

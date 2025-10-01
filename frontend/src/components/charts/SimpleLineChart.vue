<script setup>
import { computed } from 'vue'

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

const CHART_HEIGHT = 100
const TOP_PADDING = 8
const BOTTOM_PADDING = 12

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

const computedMax = computed(() => {
  if (typeof props.yMax === 'number' && Number.isFinite(props.yMax) && props.yMax > 0) {
    return props.yMax
  }
  let max = 0
  for (const point of normalizedPoints.value) {
    for (const series of normalizedSeries.value) {
      const raw = Number(point.values?.[series.key] ?? 0)
      const value = Number.isFinite(raw) ? raw : 0
      if (value > max) {
        max = value
      }
    }
  }
  return max > 0 ? max : 0
})

const xPositions = computed(() => {
  const count = normalizedPoints.value.length
  if (count <= 1) {
    return [0]
  }
  const step = 100 / (count - 1)
  return normalizedPoints.value.map((_, index) => index * step)
})

function valueToY(value, max) {
  if (!(max > 0)) {
    return CHART_HEIGHT - BOTTOM_PADDING
  }
  const clamped = Math.min(Math.max(value, 0), max)
  const drawableHeight = CHART_HEIGHT - TOP_PADDING - BOTTOM_PADDING
  return TOP_PADDING + (1 - clamped / max) * drawableHeight
}

const chartSeries = computed(() => {
  const max = computedMax.value
  return normalizedSeries.value.map((series, seriesIndex) => {
    const coords = normalizedPoints.value.map((point, pointIndex) => {
      const raw = Number(point.values?.[series.key] ?? 0)
      const value = Number.isFinite(raw) ? raw : 0
      const x = xPositions.value[pointIndex] ?? 0
      const y = valueToY(value, max)
      return { x, y, value }
    })
    const path = coords
      .map((coord, index) => `${index === 0 ? 'M' : 'L'} ${coord.x} ${coord.y}`)
      .join(' ')
    return {
      ...series,
      coords,
      path,
      index: seriesIndex
    }
  })
})

const hasTimeline = computed(
  () => normalizedPoints.value.length > 0 && normalizedSeries.value.length > 0
)

const accessibleRows = computed(() =>
  normalizedPoints.value.map((point) => ({
    label: point.label,
    values: normalizedSeries.value.map((series) => ({
      label: series.label,
      value: new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(
        Number(point.values?.[series.key] ?? 0)
      )
    }))
  }))
)
</script>

<template>
  <figure class="simple-line-chart" role="img" :aria-label="ariaLabel">
    <div v-if="hasTimeline" class="simple-line-chart__canvas">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <line
          class="simple-line-chart__axis"
          x1="0"
          :y1="100 - BOTTOM_PADDING"
          x2="100"
          :y2="100 - BOTTOM_PADDING"
        />
        <template v-for="series in chartSeries" :key="series.key">
          <path
            class="simple-line-chart__path"
            :d="series.path"
            fill="none"
            :stroke="series.color"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <g>
            <circle
              v-for="(coord, index) in series.coords"
              :key="`${series.key}-${index}`"
              class="simple-line-chart__point"
              :cx="coord.x"
              :cy="coord.y"
              r="1.8"
              :fill="series.color"
            >
              <title>{{ series.label }} – {{ normalizedPoints[index].label }}: {{ coord.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) }}</title>
            </circle>
          </g>
        </template>
      </svg>
    </div>
    <p v-else class="simple-line-chart__empty">No timeline data available</p>
    <ul class="simple-line-chart__legend" aria-hidden="true">
      <li v-for="series in chartSeries" :key="series.key">
        <span class="simple-line-chart__swatch" :style="{ backgroundColor: series.color }"></span>
        <span class="simple-line-chart__legend-label">{{ series.label }}</span>
      </li>
    </ul>
    <table class="sr-only">
      <caption>{{ ariaLabel }}</caption>
      <thead>
        <tr>
          <th scope="col">Period</th>
          <th v-for="series in chartSeries" :key="series.key" scope="col">{{ series.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in accessibleRows" :key="row.label">
          <th scope="row">{{ row.label }}</th>
          <td v-for="entry in row.values" :key="entry.label">{{ entry.value }}</td>
        </tr>
      </tbody>
    </table>
  </figure>
</template>

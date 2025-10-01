<script setup>
import { computed } from 'vue'

const FALLBACK_COLORS = [
  '#4f46e5',
  '#6366f1',
  '#22c55e',
  '#0ea5e9',
  '#f97316',
  '#ec4899',
  '#a855f7',
  '#14b8a6'
]

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  size: {
    type: Number,
    default: 160
  },
  total: {
    type: Number,
    default: null
  },
  ariaLabel: {
    type: String,
    default: 'Pie chart'
  },
  showLegend: {
    type: Boolean,
    default: true
  }
})

const normalizedData = computed(() =>
  (props.data || []).map((item, index) => {
    const value = Number(item?.value ?? 0)
    return {
      label:
        typeof item?.label === 'string' && item.label.trim()
          ? item.label.trim()
          : `Segment ${index + 1}`,
      value: Number.isFinite(value) ? value : 0,
      color: item?.color || FALLBACK_COLORS[index % FALLBACK_COLORS.length]
    }
  })
)

const totalValue = computed(() => {
  if (typeof props.total === 'number' && Number.isFinite(props.total)) {
    return props.total
  }
  return normalizedData.value.reduce((acc, item) => acc + item.value, 0)
})

const segments = computed(() => {
  const total = totalValue.value
  if (total <= 0) {
    return []
  }
  let offset = 0
  return normalizedData.value
    .filter((item) => item.value > 0)
    .map((item) => {
      const percent = (item.value / total) * 100
      const segment = {
        ...item,
        start: offset,
        end: offset + percent,
        percent
      }
      offset += percent
      return segment
    })
})

const figureStyle = computed(() => {
  const base = {
    width: `${props.size}px`,
    height: `${props.size}px`
  }
  if (!segments.value.length) {
    return {
      ...base,
      background: 'conic-gradient(var(--chart-empty-color, #e2e8f0) 0 100%)'
    }
  }
  const stops = segments.value
    .map((segment) => `${segment.color} ${segment.start}% ${segment.end}%`)
    .join(', ')
  return {
    ...base,
    background: `conic-gradient(${stops})`
  }
})

const formattedSegments = computed(() => {
  const total = totalValue.value
  return normalizedData.value.map((item) => {
    const percent = total > 0 ? (item.value / total) * 100 : 0
    return {
      ...item,
      percent
    }
  })
})
</script>

<template>
  <figure class="simple-pie-chart" role="img" :aria-label="ariaLabel">
    <div class="simple-pie-chart__figure" :style="figureStyle">
      <div class="simple-pie-chart__center">
        <slot name="center">
          <span class="simple-pie-chart__value">${{ totalValue.toFixed(2) }}</span>
        </slot>
      </div>
    </div>
    <figcaption v-if="showLegend" class="simple-pie-chart__legend" aria-hidden="true">
      <ul>
        <li v-for="segment in formattedSegments" :key="segment.label">
          <span class="simple-pie-chart__legend-swatch" :style="{ backgroundColor: segment.color }"></span>
          <span class="simple-pie-chart__legend-label">
            {{ segment.label }}
            <span class="simple-pie-chart__legend-value">
              – ${{ segment.value.toFixed(2) }}
              <span v-if="segment.percent > 0">({{ segment.percent.toFixed(1) }}%)</span>
            </span>
          </span>
        </li>
      </ul>
    </figcaption>
  </figure>
</template>

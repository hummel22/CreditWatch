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

const VIEWBOX_SIZE = 240
const CENTER = VIEWBOX_SIZE / 2
const RADIUS = CENTER - 28
const LABEL_RADIUS = RADIUS + 18
const VALUE_RADIUS = RADIUS * 0.6

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  size: {
    type: Number,
    default: 240
  },
  ariaLabel: {
    type: String,
    default: 'Pie chart'
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

const totalValue = computed(() =>
  normalizedData.value.reduce((acc, item) => acc + item.value, 0)
)

const hasData = computed(() => totalValue.value > 0)

function polarToCartesian(angle, radius) {
  const radians = (angle * Math.PI) / 180
  return {
    x: CENTER + radius * Math.cos(radians),
    y: CENTER + radius * Math.sin(radians)
  }
}

function getAnchor(x) {
  if (Math.abs(x - CENTER) < 4) {
    return 'middle'
  }
  return x > CENTER ? 'start' : 'end'
}

const segments = computed(() => {
  if (!hasData.value) {
    return []
  }
  let angleCursor = -90
  return normalizedData.value
    .filter((item) => item.value > 0)
    .map((item) => {
      const sweep = (item.value / totalValue.value) * 360
      const startAngle = angleCursor
      const endAngle = startAngle + sweep
      const largeArc = sweep > 180 ? 1 : 0
      const start = polarToCartesian(startAngle, RADIUS)
      const end = polarToCartesian(endAngle, RADIUS)
      const midAngle = startAngle + sweep / 2
      const labelPoint = polarToCartesian(midAngle, LABEL_RADIUS)
      const valuePoint = polarToCartesian(midAngle, VALUE_RADIUS)
      angleCursor = endAngle
      return {
        ...item,
        path: `M ${CENTER} ${CENTER} L ${start.x} ${start.y} A ${RADIUS} ${RADIUS} 0 ${largeArc} 1 ${end.x} ${end.y} Z`,
        labelPoint,
        valuePoint,
        labelAnchor: getAnchor(labelPoint.x),
        valueAnchor: getAnchor(valuePoint.x)
      }
    })
})

const formattedSegments = computed(() =>
  segments.value.map((segment) => ({
    ...segment,
    displayValue: `$${segment.value.toFixed(2)}`
  }))
)
</script>

<template>
  <figure class="simple-pie-chart" role="img" :aria-label="ariaLabel">
    <svg
      class="simple-pie-chart__figure"
      :width="size"
      :height="size"
      :viewBox="`0 0 ${VIEWBOX_SIZE} ${VIEWBOX_SIZE}`"
    >
      <g v-if="formattedSegments.length">
        <path
          v-for="segment in formattedSegments"
          :key="segment.label"
          :d="segment.path"
          :fill="segment.color"
        />
        <g v-for="segment in formattedSegments" :key="`${segment.label}-labels`">
          <text
            class="simple-pie-chart__value"
            :x="segment.valuePoint.x"
            :y="segment.valuePoint.y"
            :text-anchor="segment.valueAnchor"
          >
            {{ segment.displayValue }}
          </text>
          <text
            class="simple-pie-chart__label"
            :x="segment.labelPoint.x"
            :y="segment.labelPoint.y"
            :text-anchor="segment.labelAnchor"
          >
            {{ segment.label }}
          </text>
        </g>
      </g>
      <g v-else>
        <circle :cx="CENTER" :cy="CENTER" :r="RADIUS" class="simple-pie-chart__empty" />
        <text class="simple-pie-chart__empty-text" :x="CENTER" :y="CENTER">No data</text>
      </g>
    </svg>
  </figure>
</template>

<style scoped>
.simple-pie-chart {
  width: 100%;
  display: flex;
  justify-content: center;
}

.simple-pie-chart__figure {
  max-width: 100%;
}

.simple-pie-chart__value {
  font-size: 12px;
  font-weight: 600;
  fill: var(--color-text-heading, #0f172a);
}

.simple-pie-chart__label {
  font-size: 10px;
  fill: var(--color-text-tertiary, #64748b);
}

.simple-pie-chart__empty {
  fill: none;
  stroke: var(--color-border-subtle, #e2e8f0);
  stroke-width: 12;
}

.simple-pie-chart__empty-text {
  font-size: 12px;
  fill: var(--color-text-tertiary, #94a3b8);
  text-anchor: middle;
  dominant-baseline: middle;
}
</style>

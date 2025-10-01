<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  ariaLabel: {
    type: String,
    default: 'Timeline bar chart'
  },
  maxValue: {
    type: Number,
    default: null
  }
})

const VIEWBOX_WIDTH = 640
const VIEWBOX_HEIGHT = 320
const PADDING = { top: 20, right: 32, bottom: 48, left: 72 }

const normalizedData = computed(() =>
  (props.data || []).map((item, index) => {
    const rawValue = Number(item?.value ?? 0)
    const value = Number.isFinite(rawValue) && rawValue > 0 ? rawValue : 0
    return {
      label:
        typeof item?.label === 'string' && item.label.trim()
          ? item.label.trim()
          : `Item ${index + 1}`,
      fullLabel:
        typeof item?.fullLabel === 'string' && item.fullLabel.trim()
          ? item.fullLabel.trim()
          : undefined,
      value,
      color: item?.color || '#6366f1',
      displayValue:
        typeof item?.displayValue === 'string'
          ? item.displayValue
          : new Intl.NumberFormat(undefined, {
              style: 'currency',
              currency: 'USD',
              minimumFractionDigits: 0
            }).format(value)
    }
  })
)

const computedMax = computed(() => {
  if (typeof props.maxValue === 'number' && Number.isFinite(props.maxValue) && props.maxValue > 0) {
    return props.maxValue
  }
  const max = normalizedData.value.reduce((acc, item) => Math.max(acc, item.value), 0)
  return max > 0 ? max : 0
})

const innerWidth = VIEWBOX_WIDTH - PADDING.left - PADDING.right
const innerHeight = VIEWBOX_HEIGHT - PADDING.top - PADDING.bottom

const bars = computed(() => {
  const data = normalizedData.value
  if (!data.length || computedMax.value <= 0) {
    return []
  }
  const band = innerWidth / data.length
  const barWidth = Math.max(Math.min(band * 0.6, 48), 24)
  return data.map((item, index) => {
    const height = (item.value / computedMax.value) * innerHeight
    const x = PADDING.left + index * band + (band - barWidth) / 2
    const y = PADDING.top + (innerHeight - height)
    const labelX = PADDING.left + index * band + band / 2
    return {
      ...item,
      x,
      y,
      height,
      width: barWidth,
      labelX
    }
  })
})

const yTicks = computed(() => {
  const max = computedMax.value
  if (max <= 0) {
    return []
  }
  const steps = 4
  const increment = max / steps
  return Array.from({ length: steps + 1 }, (_, index) => {
    const value = increment * index
    const y = PADDING.top + (innerHeight - (value / max) * innerHeight)
    return {
      value,
      y,
      label: new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
    }
  })
})

const hasData = computed(() => bars.value.length > 0)
</script>

<template>
  <figure class="timeline-bar-chart" role="img" :aria-label="ariaLabel">
    <svg
      class="timeline-bar-chart__figure"
      :viewBox="`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`"
      preserveAspectRatio="xMidYMid meet"
    >
      <g v-if="hasData">
        <line
          class="timeline-bar-chart__axis"
          :x1="PADDING.left"
          :y1="PADDING.top + innerHeight"
          :x2="PADDING.left + innerWidth"
          :y2="PADDING.top + innerHeight"
        />
        <g class="timeline-bar-chart__grid">
          <g v-for="tick in yTicks" :key="tick.value">
            <line
              :x1="PADDING.left"
              :y1="tick.y"
              :x2="PADDING.left + innerWidth"
              :y2="tick.y"
            />
            <text
              class="timeline-bar-chart__tick-label"
              :x="PADDING.left - 12"
              :y="tick.y + 4"
              text-anchor="end"
            >
              {{ tick.label }}
            </text>
          </g>
        </g>
        <g>
          <g v-for="bar in bars" :key="bar.label">
            <rect
              class="timeline-bar-chart__bar"
              :x="bar.x"
              :y="bar.y"
              :width="bar.width"
              :height="bar.height"
              :fill="bar.color"
              rx="6"
            />
            <text
              v-if="bar.value > 0"
              class="timeline-bar-chart__value"
              :x="bar.x + bar.width / 2"
              :y="bar.y - 8"
              text-anchor="middle"
            >
              {{ bar.displayValue }}
            </text>
            <text
              class="timeline-bar-chart__label"
              :x="bar.labelX"
              :y="PADDING.top + innerHeight + 24"
              text-anchor="middle"
            >
              {{ bar.label }}
            </text>
            <text
              v-if="bar.fullLabel"
              class="timeline-bar-chart__sublabel"
              :x="bar.labelX"
              :y="PADDING.top + innerHeight + 40"
              text-anchor="middle"
            >
              {{ bar.fullLabel }}
            </text>
          </g>
        </g>
      </g>
      <g v-else>
        <text class="timeline-bar-chart__empty" x="50%" y="55%" text-anchor="middle">No data available</text>
      </g>
    </svg>
  </figure>
</template>

<style scoped>
.timeline-bar-chart {
  width: 100%;
}

.timeline-bar-chart__figure {
  width: 100%;
  height: auto;
}

.timeline-bar-chart__axis {
  stroke: var(--color-border, rgba(148, 163, 184, 0.5));
  stroke-width: 2;
}

.timeline-bar-chart__grid line {
  stroke: rgba(148, 163, 184, 0.2);
  stroke-width: 1;
}

.timeline-bar-chart__tick-label {
  font-size: 12px;
  fill: var(--color-text-tertiary, #64748b);
}

.timeline-bar-chart__bar {
  transition: height 0.3s ease;
}

.timeline-bar-chart__value {
  font-size: 12px;
  font-weight: 600;
  fill: var(--color-text-heading, #0f172a);
}

.timeline-bar-chart__label {
  font-size: 12px;
  font-weight: 600;
  fill: var(--color-text-secondary, #475569);
}

.timeline-bar-chart__sublabel {
  font-size: 10px;
  fill: var(--color-text-tertiary, #94a3b8);
}

.timeline-bar-chart__empty {
  font-size: 14px;
  fill: var(--color-text-tertiary, #94a3b8);
}
</style>

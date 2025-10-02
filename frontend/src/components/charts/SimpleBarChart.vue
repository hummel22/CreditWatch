<script setup>
import { computed } from 'vue'

const FALLBACK_COLORS = [
  '#6366f1',
  '#4f46e5',
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
  ariaLabel: {
    type: String,
    default: 'Bar chart'
  },
  maxValue: {
    type: Number,
    default: null
  },
  orientation: {
    type: String,
    default: 'vertical',
    validator: (value) => ['vertical', 'horizontal'].includes(value)
  }
})

const normalizedData = computed(() =>
  (props.data || []).map((item, index) => {
    const rawValue = Number(item?.value ?? 0)
    const value = Number.isFinite(rawValue) ? rawValue : 0
    return {
      label:
        typeof item?.label === 'string' && item.label.trim()
          ? item.label.trim()
          : `Item ${index + 1}`,
      value,
      color: item?.color || FALLBACK_COLORS[index % FALLBACK_COLORS.length],
      displayValue:
        typeof item?.displayValue === 'string'
          ? item.displayValue
          : new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)
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

const bars = computed(() => {
  const max = computedMax.value
  return normalizedData.value.map((item) => ({
    ...item,
    percent: (() => {
      if (!(max > 0)) {
        return 0
      }
      const percent = (item.value / max) * 100
      if (!Number.isFinite(percent)) {
        return 0
      }
      return Math.min(Math.max(percent, 0), 100)
    })()
  }))
})

const hasAnyValue = computed(() => bars.value.some((bar) => bar.value > 0))

const isHorizontal = computed(() => props.orientation === 'horizontal')
</script>

<template>
  <figure class="simple-bar-chart" role="img" :aria-label="ariaLabel">
    <div
      class="simple-bar-chart__grid"
      :class="{
        'simple-bar-chart__grid--empty': !hasAnyValue,
        'simple-bar-chart__grid--horizontal': isHorizontal
      }"
    >
      <template v-if="isHorizontal">
        <div v-for="bar in bars" :key="bar.label" class="simple-bar-chart__row">
          <span class="simple-bar-chart__label simple-bar-chart__label--horizontal" :title="bar.label">
            {{ bar.label }}
          </span>
          <div class="simple-bar-chart__bar-track">
            <div
              class="simple-bar-chart__bar simple-bar-chart__bar--horizontal"
              :style="{ width: `${bar.percent}%`, backgroundColor: bar.color }"
            >
              <span class="sr-only">{{ bar.label }}: {{ bar.displayValue }}</span>
            </div>
          </div>
          <span class="simple-bar-chart__value simple-bar-chart__value--horizontal">{{ bar.displayValue }}</span>
        </div>
      </template>
      <template v-else>
        <div v-for="bar in bars" :key="bar.label" class="simple-bar-chart__column">
          <div class="simple-bar-chart__bar" :style="{ height: `${bar.percent}%`, backgroundColor: bar.color }">
            <span class="sr-only">{{ bar.label }}: {{ bar.displayValue }}</span>
          </div>
          <span class="simple-bar-chart__label" :title="bar.label">{{ bar.label }}</span>
          <span class="simple-bar-chart__value">{{ bar.displayValue }}</span>
        </div>
      </template>
      <p v-if="!bars.length" class="simple-bar-chart__empty">No data available</p>
    </div>
  </figure>
</template>

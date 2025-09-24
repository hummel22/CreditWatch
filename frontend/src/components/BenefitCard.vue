<script setup>
import { computed } from 'vue'

const props = defineProps({
  benefit: {
    type: Object,
    required: true
  },
  cardContext: {
    type: Object,
    default: null
  },
  showEdit: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits([
  'toggle',
  'delete',
  'add-redemption',
  'view-history',
  'edit',
  'view-windows'
])

const typeLabel = computed(() => {
  const type = props.benefit.type || 'standard'
  return type.charAt(0).toUpperCase() + type.slice(1)
})

const statusTag = computed(() => {
  const type = props.benefit.type
  if (type === 'standard') {
    return props.benefit.is_used
      ? { label: 'Utilized', tone: 'success' }
      : { label: 'Available', tone: 'warning' }
  }
  if (type === 'incremental') {
    const used = props.benefit.cycle_redemption_total || 0
    const target = Number(props.benefit.value ?? 0)
    if (used >= target && target > 0) {
      return { label: 'Completed', tone: 'success' }
    }
    if (used > 0) {
      return { label: 'In progress', tone: 'info' }
    }
    return { label: 'Not started', tone: 'warning' }
  }
  return { label: 'Tracking', tone: 'info' }
})

const frequencyLabel = computed(() => {
  const frequency = props.benefit.frequency
  if (!frequency) {
    return ''
  }
  return frequency.charAt(0).toUpperCase() + frequency.slice(1)
})

const currentWindowLabel = computed(() => props.benefit.current_window_label || '')

const cardLabel = computed(() => {
  if (!props.cardContext) {
    return ''
  }
  const name = props.cardContext.name || props.cardContext.card_name || ''
  const company = props.cardContext.company || props.cardContext.company_name || ''
  if (name && company) {
    return `${name} · ${company}`
  }
  return name || company || ''
})

const expirationLabel = computed(() => {
  if (!props.benefit.expiration_date) {
    return 'No expiration set'
  }
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  }).format(new Date(props.benefit.expiration_date))
})

const incrementalProgress = computed(() => {
  if (props.benefit.type !== 'incremental') {
    return null
  }
  const used = Number(props.benefit.cycle_redemption_total ?? 0)
  const target = Number(props.benefit.value ?? 0)
  const remaining = props.benefit.remaining_value ?? Math.max(target - used, 0)
  const percent = target > 0 ? Math.min((used / target) * 100, 100) : used > 0 ? 100 : 0
  const statusText = target <= 0
    ? `${used > 0 ? `$${used.toFixed(2)} logged` : 'No goal set'}`
    : remaining <= 0
      ? 'Complete'
      : `$${remaining.toFixed(2)} remaining`
  return {
    used,
    target,
    remaining,
    percent,
    statusText
  }
})

const redemptionSummary = computed(() => {
  if (props.benefit.type === 'incremental') {
    return ''
  }
  if (props.benefit.type === 'cumulative') {
    const used = props.benefit.cycle_redemption_total || 0
    if (props.benefit.expected_value != null) {
      return `Recorded $${used.toFixed(2)} this cycle · Expected $${props.benefit.expected_value.toFixed(2)}`
    }
    return `Recorded $${used.toFixed(2)} this cycle`
  }
  return `Worth $${Number(props.benefit.value ?? 0).toFixed(2)}`
})

const showHistoryButton = computed(
  () => props.benefit.type !== 'standard' || props.benefit.redemption_count > 0
)

const isRecurringBenefit = computed(() =>
  ['monthly', 'quarterly', 'semiannual'].includes(props.benefit.frequency)
)
</script>

<template>
  <article class="benefit-card" :class="{ used: benefit.is_used }">
    <header class="benefit-header">
      <div class="benefit-header__primary">
        <div class="benefit-name">{{ benefit.name }}</div>
        <div v-if="cardLabel" class="benefit-card__context">{{ cardLabel }}</div>
        <div class="benefit-meta-row">
          <div class="benefit-meta">
            <div class="benefit-meta-line">
              <span class="benefit-type">{{ typeLabel }}</span>
              <span v-if="frequencyLabel" class="benefit-frequency">{{ frequencyLabel }}</span>
            </div>
            <span v-if="currentWindowLabel" class="benefit-window">{{ currentWindowLabel }}</span>
          </div>
          <div class="tag" :class="statusTag.tone">
            <span>{{ statusTag.label }}</span>
          </div>
        </div>
      </div>
      <div class="benefit-icons">
        <button
          v-if="isRecurringBenefit"
          class="icon-button ghost"
          type="button"
          @click="emit('view-windows', benefit)"
          title="View recurring history"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M4 16h2V9H4v7zm5 0h2V4H9v12zm5 0h2v-5h-2v5z" />
          </svg>
          <span class="sr-only">View recurring history</span>
        </button>
        <button
          v-if="showEdit"
          class="icon-button ghost"
          type="button"
          @click="emit('edit', benefit)"
          title="Edit benefit"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M15.58 2.42a1.5 1.5 0 0 0-2.12 0l-9 9V17h5.59l9-9a1.5 1.5 0 0 0 0-2.12zM7 15H5v-2l6.88-6.88 2 2z" />
          </svg>
          <span class="sr-only">Edit benefit</span>
        </button>
        <button class="icon-button danger" type="button" @click="emit('delete')" title="Remove benefit">
          <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M7 3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1h3.5a.5.5 0 0 1 0 1h-.8l-.62 11a2 2 0 0 1-2 1.9H6.92a2 2 0 0 1-2-1.9L4.3 5H3.5a.5.5 0 0 1 0-1H7zm1 1h4V3H8zM6.3 5l.6 10.8a1 1 0 0 0 1 1h4.2a1 1 0 0 0 1-1L13.7 5z" />
          </svg>
          <span class="sr-only">Remove benefit</span>
        </button>
      </div>
    </header>

    <section class="benefit-body">
      <p v-if="benefit.description">{{ benefit.description }}</p>
      <p class="benefit-expiration">Expires: {{ expirationLabel }}</p>
      <div
        v-if="incrementalProgress"
        class="benefit-progress-chart"
        role="img"
        :aria-label="`Used $${incrementalProgress.used.toFixed(2)} of $${incrementalProgress.target.toFixed(2)}`"
      >
        <div class="benefit-progress-chart__track">
          <div
            class="benefit-progress-chart__fill"
            :style="{ width: `${incrementalProgress.percent}%` }"
            aria-hidden="true"
          ></div>
        </div>
        <div class="benefit-progress-chart__legend">
          <span class="benefit-progress-chart__value">
            Used ${{ incrementalProgress.used.toFixed(2) }} of ${{ incrementalProgress.target.toFixed(2) }}
          </span>
          <span class="benefit-progress-chart__status">{{ incrementalProgress.statusText }}</span>
        </div>
      </div>
      <p v-else class="benefit-progress">{{ redemptionSummary }}</p>
    </section>

    <footer class="benefit-footer">
      <div>
        <strong v-if="benefit.type !== 'cumulative'">
          ${{ Number(benefit.value ?? 0).toFixed(2) }}
        </strong>
        <strong v-else>
          <template v-if="benefit.expected_value != null">
            Expected ${{ Number(benefit.expected_value).toFixed(2) }}
          </template>
          <template v-else>
            ${{ benefit.cycle_redemption_total.toFixed(2) }}
          </template>
        </strong>
      </div>
      <div class="benefit-actions">
        <button
          v-if="benefit.type === 'standard'"
          class="primary-button"
          type="button"
          @click="emit('add-redemption', benefit)"
          title="Redeem benefit"
        >
          Redeem
        </button>
        <button
          v-if="benefit.type === 'standard'"
          class="primary-button secondary"
          type="button"
          :aria-pressed="benefit.is_used"
          title="Mark benefit as done"
          @click="emit('toggle', !benefit.is_used)"
        >
          Done
        </button>
        <button
          v-if="benefit.type !== 'standard'"
          class="icon-button accent"
          type="button"
          @click="emit('add-redemption', benefit)"
          title="Add redemption"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1z" />
          </svg>
          <span class="sr-only">Add redemption</span>
        </button>
        <button
          v-if="showHistoryButton"
          class="icon-button ghost"
          type="button"
          @click="emit('view-history', benefit)"
          title="View history"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path stroke-linecap="round" d="M4 6h12M4 10h12M4 14h12" />
          </svg>
          <span class="sr-only">View history</span>
        </button>
      </div>
    </footer>
  </article>
</template>

<style scoped>

.benefit-icons {
  display: flex;
  gap: 0.3rem;
  align-items: center;
  margin-left: auto;
  flex-shrink: 0;
}

.benefit-icons .icon-button {
  width: 1.6rem;
  height: 1.6rem;
}

.benefit-icons .icon-button svg {
  width: 0.9rem;
  height: 0.9rem;
}

.benefit-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.benefit-header {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.benefit-header__primary {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex: 1;
  min-width: 0;
}

.benefit-name {
  overflow-wrap: anywhere;
}

.benefit-card__context {
  font-size: 0.72rem;
  color: #64748b;
  font-weight: 500;
}

.benefit-meta-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}

.benefit-meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.75rem;
  color: #475569;
}

.benefit-meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}

.benefit-expiration {
  font-size: 0.85rem;
  margin: 0;
  color: #94a3b8;
}

.benefit-type {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #0ea5e9;
  font-weight: 600;
  font-size: 0.72rem;
}

.benefit-window {
  font-size: 0.72rem;
  color: #64748b;
  font-weight: 500;
  display: block;
}

.benefit-progress {
  font-size: 0.85rem;
  margin: 0.25rem 0 0;
  color: #0f172a;
}

.benefit-progress-chart {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.4rem;
}

.benefit-progress-chart__track {
  width: 100%;
  height: 0.45rem;
  background: rgba(148, 163, 184, 0.25);
  border-radius: 999px;
  overflow: hidden;
}

.benefit-progress-chart__fill {
  height: 100%;
  background: linear-gradient(90deg, #38bdf8, #6366f1);
  border-radius: 999px;
  transition: width 0.3s ease;
}

.benefit-progress-chart__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: #0f172a;
}

.benefit-progress-chart__status {
  color: #6366f1;
}

strong {
  font-weight: 700;
  color: #0f172a;
}
</style>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  benefit: {
    type: Object,
    required: true
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

const timeWindowLabel = computed(() => {
  if (props.benefit.current_window_label) {
    return props.benefit.current_window_label
  }
  if (props.benefit.frequency === 'yearly') {
    if (props.benefit.cycle_label) {
      return props.benefit.cycle_label.includes('-')
        ? `Cycle ${props.benefit.cycle_label}`
        : `Year ${props.benefit.cycle_label}`
    }
    return 'Yearly cycle'
  }
  const frequency = props.benefit.frequency
  if (!frequency) {
    return ''
  }
  return frequency.charAt(0).toUpperCase() + frequency.slice(1)
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

const redemptionSummary = computed(() => {
  if (props.benefit.type === 'incremental') {
    const used = props.benefit.cycle_redemption_total || 0
    const target = Number(props.benefit.value ?? 0)
    const remaining = props.benefit.remaining_value ?? Math.max(target - used, 0)
    return `Used $${used.toFixed(2)} of $${target.toFixed(2)} this cycle (${remaining <= 0 ? 'complete' : `$${remaining.toFixed(2)} remaining`})`
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

const occurrencesPerYear = {
  monthly: 12,
  quarterly: 4,
  semiannual: 2,
  yearly: 1
}

const frequencyLabels = {
  monthly: 'month',
  quarterly: 'quarter',
  semiannual: 'half-year',
  yearly: 'year'
}

const annualPotential = computed(() => {
  const occurrences = occurrencesPerYear[props.benefit.frequency] || 1
  if (props.benefit.type === 'cumulative') {
    return props.benefit.expected_value ?? props.benefit.cycle_redemption_total ?? 0
  }
  const perPeriod = Number(props.benefit.value ?? 0)
  return perPeriod * occurrences
})

const periodPotential = computed(() => {
  const occurrences = occurrencesPerYear[props.benefit.frequency] || 1
  if (!occurrences) {
    return annualPotential.value
  }
  if (props.benefit.type === 'cumulative') {
    return annualPotential.value / occurrences
  }
  return Number(props.benefit.value ?? 0)
})

const recurringActualCopy = computed(() => {
  if (!isRecurringBenefit.value) {
    return ''
  }
  const windowLabel = props.benefit.current_window_label || `Current ${frequencyLabels[props.benefit.frequency] || 'period'}`
  const windowAmount = Number(props.benefit.current_window_total ?? 0)
  const cycleAmount = Number(props.benefit.cycle_redemption_total ?? 0)
  const cycleLabel = props.benefit.cycle_label
    ? props.benefit.cycle_label.includes('-')
      ? `Cycle ${props.benefit.cycle_label}`
      : `Year ${props.benefit.cycle_label}`
    : 'Cycle total'
  return `${windowLabel}: $${windowAmount.toFixed(2)} logged • ${cycleLabel}: $${cycleAmount.toFixed(2)}`
})

const recurringPotentialCopy = computed(() => {
  if (!isRecurringBenefit.value || !annualPotential.value) {
    return ''
  }
  const label = frequencyLabels[props.benefit.frequency] || 'period'
  return `Potential annual $${annualPotential.value.toFixed(2)} • Per ${label} $${periodPotential.value.toFixed(2)}`
})
</script>

<template>
  <article class="benefit-card" :class="{ used: benefit.is_used }">
    <header class="benefit-header">
      <div class="benefit-header__primary">
        <div class="benefit-name">{{ benefit.name }}</div>
        <div class="benefit-meta-row">
          <div class="benefit-meta">
            <span class="benefit-type">{{ typeLabel }}</span>
            <span v-if="timeWindowLabel" class="benefit-window">{{ timeWindowLabel }}</span>
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
      <p class="benefit-progress">{{ redemptionSummary }}</p>
      <p v-if="recurringActualCopy" class="benefit-recurring">{{ recurringActualCopy }}</p>
      <p v-if="recurringPotentialCopy" class="benefit-recurring potential">{{ recurringPotentialCopy }}</p>
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
            ${{ benefit.cycle_redemption_total.toFixed(2) }} tracked
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
  align-items: flex-start;
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
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.benefit-header__primary {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex: 1;
}

.benefit-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.benefit-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: #475569;
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
}

.benefit-progress {
  font-size: 0.85rem;
  margin: 0.25rem 0 0;
  color: #0f172a;
}

.benefit-recurring {
  font-size: 0.78rem;
  margin: 0.1rem 0 0;
  color: #6366f1;
}

.benefit-recurring.potential {
  color: #94a3b8;
}

strong {
  font-weight: 700;
  color: #0f172a;
}
</style>

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
    if (props.benefit.redemption_total >= props.benefit.value) {
      return { label: 'Completed', tone: 'success' }
    }
    if (props.benefit.redemption_total > 0) {
      return { label: 'In progress', tone: 'info' }
    }
    return { label: 'Not started', tone: 'warning' }
  }
  return { label: 'Tracking', tone: 'info' }
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
    const used = props.benefit.redemption_total || 0
    const remaining = props.benefit.remaining_value ?? Math.max(props.benefit.value - used, 0)
    return `Used $${used.toFixed(2)} of $${props.benefit.value.toFixed(2)} (${remaining <= 0 ? 'complete' : `$${remaining.toFixed(2)} remaining`})`
  }
  if (props.benefit.type === 'cumulative') {
    const used = props.benefit.redemption_total || 0
    return `Recorded $${used.toFixed(2)} this cycle`
  }
  return `Worth $${props.benefit.value.toFixed(2)}`
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
      <div>
        <div class="benefit-name">{{ benefit.name }}</div>
        <div class="benefit-type">{{ typeLabel }}</div>
        <div class="benefit-frequency">{{ benefit.frequency }}</div>
      </div>
      <div class="benefit-header__meta">
        <div class="tag" :class="statusTag.tone">
          <span>{{ statusTag.label }}</span>
        </div>
        <div class="benefit-icons">
          <button
            v-if="isRecurringBenefit"
            class="icon-button ghost"
            type="button"
            @click="emit('view-windows', benefit)"
            title="View recurring history"
          >
            <span aria-hidden="true">📊</span>
            <span class="sr-only">View recurring history</span>
          </button>
          <button
            class="icon-button ghost"
            type="button"
            @click="emit('edit', benefit)"
            title="Edit benefit"
          >
            <span aria-hidden="true">✏️</span>
            <span class="sr-only">Edit benefit</span>
          </button>
          <button class="icon-button danger" type="button" @click="emit('delete')" title="Remove benefit">
            <span aria-hidden="true">🗑️</span>
            <span class="sr-only">Remove benefit</span>
          </button>
        </div>
      </div>
    </header>

    <section class="benefit-body">
      <p v-if="benefit.description">{{ benefit.description }}</p>
      <p class="benefit-expiration">Expires: {{ expirationLabel }}</p>
      <p class="benefit-progress">{{ redemptionSummary }}</p>
    </section>

    <footer class="benefit-footer">
      <div>
        <strong v-if="benefit.type !== 'cumulative'">
          ${{ benefit.value.toFixed(2) }}
        </strong>
        <strong v-else>${{ benefit.redemption_total.toFixed(2) }}</strong>
      </div>
      <div class="benefit-actions">
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
          <span aria-hidden="true">+</span>
          <span class="sr-only">Add redemption</span>
        </button>
        <button
          v-if="showHistoryButton"
          class="primary-button secondary"
          type="button"
          @click="emit('view-history', benefit)"
        >
          View history
        </button>
      </div>
    </footer>
  </article>
</template>

<style scoped>
.benefit-icons {
  display: flex;
  gap: 0.35rem;
}

.benefit-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.benefit-expiration {
  font-size: 0.85rem;
  margin: 0;
  color: #94a3b8;
}

.benefit-type {
  font-size: 0.75rem;
  color: #0ea5e9;
  font-weight: 600;
}

.benefit-header__meta {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.benefit-progress {
  font-size: 0.85rem;
  margin: 0.25rem 0 0;
  color: #0f172a;
}

strong {
  font-weight: 700;
  color: #0f172a;
}
</style>

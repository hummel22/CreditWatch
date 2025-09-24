<script setup>
import { computed } from 'vue'

const props = defineProps({
  benefit: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['toggle', 'delete', 'add-redemption', 'view-history'])

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

const showHistoryButton = computed(() => props.benefit.type !== 'standard' || props.benefit.redemption_count > 0)
</script>

<template>
  <article class="benefit-card" :class="{ used: benefit.is_used }">
    <header class="benefit-header">
      <div>
        <div class="benefit-name">{{ benefit.name }}</div>
        <div class="benefit-type">{{ typeLabel }}</div>
        <div class="benefit-frequency">{{ benefit.frequency }}</div>
      </div>
      <div class="tag" :class="statusTag.tone">
        <span>{{ statusTag.label }}</span>
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
          @click="emit('toggle', !benefit.is_used)"
        >
          {{ benefit.is_used ? 'Reset' : 'Mark used' }}
        </button>
        <button
          v-if="benefit.type !== 'standard'"
          class="primary-button secondary"
          type="button"
          @click="emit('add-redemption', benefit)"
        >
          Add redemption
        </button>
        <button
          v-if="showHistoryButton"
          class="primary-button secondary"
          type="button"
          @click="emit('view-history', benefit)"
        >
          View history
        </button>
        <button class="primary-button danger" type="button" @click="emit('delete')">
          Remove
        </button>
      </div>
    </footer>
  </article>
</template>

<style scoped>
.benefit-actions {
  display: flex;
  gap: 0.5rem;
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

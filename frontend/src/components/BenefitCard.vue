<script setup>
import { computed } from 'vue'

const props = defineProps({
  benefit: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['toggle', 'delete'])

const statusTag = computed(() =>
  props.benefit.is_used
    ? { label: 'Utilized', tone: 'success' }
    : { label: 'Available', tone: 'warning' }
)

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
</script>

<template>
  <article class="benefit-card" :class="{ used: benefit.is_used }">
    <header class="benefit-header">
      <div>
        <div class="benefit-name">{{ benefit.name }}</div>
        <div class="benefit-frequency">{{ benefit.frequency }}</div>
      </div>
      <div class="tag" :class="statusTag.tone">
        <span>{{ statusTag.label }}</span>
      </div>
    </header>

    <section class="benefit-body">
      <p v-if="benefit.description">{{ benefit.description }}</p>
      <p class="benefit-expiration">Expires: {{ expirationLabel }}</p>
    </section>

    <footer class="benefit-footer">
      <div>
        <strong>${{ benefit.value.toFixed(2) }}</strong>
      </div>
      <div class="benefit-actions">
        <button
          class="primary-button secondary"
          type="button"
          @click="emit('toggle', !benefit.is_used)"
        >
          {{ benefit.is_used ? 'Reset' : 'Mark used' }}
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

strong {
  font-weight: 700;
  color: #0f172a;
}
</style>

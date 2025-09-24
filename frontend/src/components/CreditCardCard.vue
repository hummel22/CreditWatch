<script setup>
import { computed, reactive } from 'vue'
import BenefitCard from './BenefitCard.vue'

const props = defineProps({
  card: {
    type: Object,
    required: true
  },
  frequencies: {
    type: Array,
    default: () => ['monthly', 'quarterly', 'yearly']
  }
})

const emit = defineEmits(['add-benefit', 'toggle-benefit', 'delete-benefit', 'delete-card'])

const form = reactive({
  name: '',
  description: '',
  frequency: props.frequencies[0] || 'monthly',
  value: '',
  expiration_date: ''
})

const baseline = computed(() =>
  Math.max(props.card.annual_fee, props.card.potential_value, props.card.utilized_value, 1)
)

const utilizedPercent = computed(
  () => Math.min(100, Math.round((props.card.utilized_value / baseline.value) * 100))
)

const feePercent = computed(
  () => Math.min(100, Math.round((props.card.annual_fee / baseline.value) * 100))
)

const netStatus = computed(() => {
  const difference = props.card.utilized_value - props.card.annual_fee
  return difference >= 0
    ? { tone: 'success', label: `Ahead by $${difference.toFixed(2)}` }
    : { tone: 'warning', label: `Short by $${Math.abs(difference).toFixed(2)}` }
})

function resetForm() {
  form.name = ''
  form.description = ''
  form.frequency = props.frequencies[0] || 'monthly'
  form.value = ''
  form.expiration_date = ''
}

function submitForm() {
  if (!form.name || !form.value) {
    return
  }
  emit('add-benefit', {
    cardId: props.card.id,
    payload: {
      name: form.name,
      description: form.description || null,
      frequency: form.frequency,
      value: Number(form.value),
      expiration_date: form.expiration_date || null
    }
  })
  resetForm()
}
</script>

<template>
  <article class="card">
    <header class="card-header">
      <div>
        <div class="card-title">{{ card.card_name }}</div>
        <div class="annual-fee">
          <span>Ending {{ card.last_four }}</span>
          <span>•</span>
          <span>{{ card.account_name }}</span>
        </div>
      </div>
      <span class="card-meta">Fee due {{ new Date(card.fee_due_date).toLocaleDateString() }}</span>
    </header>

    <section>
      <div class="summary-row">
        <span>Annual fee: <strong>${{ card.annual_fee.toFixed(2) }}</strong></span>
        <span>Potential value: <strong>${{ card.potential_value.toFixed(2) }}</strong></span>
        <span>Utilized: <strong>${{ card.utilized_value.toFixed(2) }}</strong></span>
      </div>
      <div class="value-bar" aria-hidden="true">
        <div class="value-bar__fee" :style="{ width: feePercent + '%' }"></div>
        <div class="value-bar__used" :style="{ width: utilizedPercent + '%' }"></div>
      </div>
      <div class="tag" :class="netStatus.tone">{{ netStatus.label }}</div>
    </section>

    <section>
      <h3 class="section-title">Benefits</h3>
      <div v-if="card.benefits.length" class="benefits-grid">
        <BenefitCard
          v-for="benefit in card.benefits"
          :key="benefit.id"
          :benefit="benefit"
          @toggle="(value) => emit('toggle-benefit', { id: benefit.id, value })"
          @delete="emit('delete-benefit', benefit.id)"
        />
      </div>
      <p v-else class="empty-state">No benefits tracked yet. Start by adding one below.</p>
    </section>

    <section>
      <h3 class="section-title">Add a benefit</h3>
      <form @submit.prevent="submitForm">
        <div class="field-group">
          <input v-model="form.name" type="text" placeholder="Benefit name" required />
          <input v-model="form.value" type="number" min="0" step="0.01" placeholder="Value" required />
        </div>
        <textarea v-model="form.description" rows="2" placeholder="Description (optional)"></textarea>
        <div class="field-group">
          <select v-model="form.frequency">
            <option v-for="option in frequencies" :key="option" :value="option">
              {{ option.charAt(0).toUpperCase() + option.slice(1) }}
            </option>
          </select>
          <input v-model="form.expiration_date" type="date" />
        </div>
        <div class="card-actions">
          <button class="primary-button" type="submit">Add benefit</button>
          <button class="primary-button danger" type="button" @click="emit('delete-card', card.id)">
            Remove card
          </button>
        </div>
      </form>
    </section>
  </article>
</template>

<style scoped>
.card-actions {
  display: flex;
  gap: 0.75rem;
}

.card-actions button:last-child {
  margin-left: auto;
}

strong {
  font-weight: 700;
  color: #0f172a;
}
</style>

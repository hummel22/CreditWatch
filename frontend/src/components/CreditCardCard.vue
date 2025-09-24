<script setup>
import { computed, reactive, ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'
import BenefitCard from './BenefitCard.vue'

const props = defineProps({
  card: {
    type: Object,
    required: true
  },
  frequencies: {
    type: Array,
    default: () => ['monthly', 'quarterly', 'semiannual', 'yearly']
  }
})

const emit = defineEmits(['add-benefit', 'toggle-benefit', 'delete-benefit', 'delete-card'])

const benefitModalOpen = ref(false)
const benefitsExpanded = ref(true)

const defaultFrequency = computed(() => props.frequencies[0] || 'monthly')

const form = reactive({
  name: '',
  description: '',
  frequency: defaultFrequency.value,
  value: '',
  expiration_date: ''
})

watch(
  () => props.frequencies,
  (options) => {
    if (!options.includes(form.frequency)) {
      form.frequency = defaultFrequency.value
    }
  },
  { immediate: true }
)

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
  form.frequency = defaultFrequency.value
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
  closeBenefitModal()
}

function openBenefitModal() {
  benefitModalOpen.value = true
}

function closeBenefitModal() {
  benefitModalOpen.value = false
  resetForm()
}

function toggleBenefits() {
  benefitsExpanded.value = !benefitsExpanded.value
}
</script>

<template>
  <article class="card">
    <header class="card-header">
      <div>
        <div class="card-title">{{ card.card_name }}</div>
        <div class="card-subtitle">
          <span v-if="card.company_name" class="company-pill">{{ card.company_name }}</span>
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

    <section class="benefits-section">
      <div class="section-header">
        <h3 class="section-title">Benefits</h3>
        <div class="section-actions">
          <button class="primary-button secondary small" type="button" @click="openBenefitModal">
            Add benefit
          </button>
          <button
            class="link-button"
            type="button"
            @click="toggleBenefits"
            :aria-expanded="benefitsExpanded"
          >
            {{ benefitsExpanded ? 'Hide benefits' : 'Show benefits' }}
          </button>
        </div>
      </div>
      <div v-if="benefitsExpanded">
        <div v-if="card.benefits.length" class="benefits-grid">
          <BenefitCard
            v-for="benefit in card.benefits"
            :key="benefit.id"
            :benefit="benefit"
            @toggle="(value) => emit('toggle-benefit', { id: benefit.id, value })"
            @delete="emit('delete-benefit', benefit.id)"
          />
        </div>
        <p v-else class="empty-state empty-benefits">
          No benefits tracked yet.
          <button class="link-button inline" type="button" @click="openBenefitModal">Add one now</button>
          .
        </p>
      </div>
    </section>

    <footer class="card-footer">
      <button class="primary-button danger" type="button" @click="emit('delete-card', card.id)">
        Remove card
      </button>
    </footer>

    <BaseModal :open="benefitModalOpen" title="Add a benefit" @close="closeBenefitModal">
      <form @submit.prevent="submitForm">
        <div class="field-group">
          <input v-model="form.name" type="text" placeholder="Benefit name" required />
          <input v-model="form.value" type="number" min="0" step="0.01" placeholder="Value" required />
        </div>
        <textarea v-model="form.description" rows="3" placeholder="Description (optional)"></textarea>
        <div class="field-group">
          <select v-model="form.frequency">
            <option v-for="option in frequencies" :key="option" :value="option">
              {{ option.charAt(0).toUpperCase() + option.slice(1) }}
            </option>
          </select>
          <input v-model="form.expiration_date" type="date" />
        </div>
        <div class="modal-actions">
          <button class="primary-button secondary" type="button" @click="closeBenefitModal">
            Cancel
          </button>
          <button class="primary-button" type="submit">Save benefit</button>
        </div>
      </form>
    </BaseModal>
  </article>
</template>

<style scoped>
.card-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.75rem;
}

.card-subtitle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  color: #475569;
  font-size: 0.9rem;
}

.company-pill {
  background: rgba(99, 102, 241, 0.14);
  color: #4f46e5;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.empty-benefits {
  margin-top: 1rem;
}

strong {
  font-weight: 700;
  color: #0f172a;
}
</style>

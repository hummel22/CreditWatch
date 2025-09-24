<script setup>
import { computed, reactive, ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'
import BenefitCard from './BenefitCard.vue'
import {
  computeCardCycle,
  computeFrequencyWindows,
  formatDateInput
} from '../utils/dates'

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

const emit = defineEmits([
  'add-benefit',
  'toggle-benefit',
  'delete-benefit',
  'delete-card',
  'add-redemption',
  'view-history',
  'update-benefit',
  'edit-card',
  'view-card-history',
  'view-benefit-windows'
])

const benefitModalOpen = ref(false)
const benefitsExpanded = ref(true)
const formMode = ref('create')
const editingBenefitId = ref(null)
const autoExpiration = ref(true)

const defaultFrequency = computed(() => props.frequencies[0] || 'monthly')
const benefitTypes = ['standard', 'incremental', 'cumulative']
const defaultYearAlignment = computed(() =>
  props.card.year_tracking_mode === 'anniversary' ? 'anniversary' : 'calendar'
)

const form = reactive({
  name: '',
  description: '',
  frequency: defaultFrequency.value,
  type: 'standard',
  value: '',
  expected_value: '',
  expiration_date: '',
  yearlyAlignment: defaultYearAlignment.value
})

const typeDescriptions = {
  standard: 'Standard benefits are toggled once per cycle.',
  incremental: 'Incremental benefits accrue value as you log redemptions until reaching the goal.',
  cumulative: 'Cumulative benefits build value as you add redemptions.'
}

const currentTypeDescription = computed(() => typeDescriptions[form.type])

const currentCycle = computed(() => computeCardCycle(props.card))

const cycleSubtitle = computed(() =>
  currentCycle.value.mode === 'anniversary' ? 'AF year' : 'Calendar year'
)

const cycleCoverage = computed(() => {
  const start = new Date(currentCycle.value.start)
  const end = new Date(currentCycle.value.end)
  end.setDate(end.getDate() - 1)
  const sameYear = start.getFullYear() === end.getFullYear()
  const startFormatter = new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: sameYear ? undefined : 'numeric'
  })
  const endFormatter = new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
  return `${startFormatter.format(start)} – ${endFormatter.format(end)}`
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

watch(
  () => form.type,
  (type) => {
    if (type === 'cumulative') {
      form.value = ''
    } else {
      form.expected_value = ''
    }
  }
)

watch(
  () => props.card.year_tracking_mode,
  () => {
    if (formMode.value === 'create') {
      form.yearlyAlignment = defaultYearAlignment.value
      applyFrequencyDefaults()
    }
  }
)

watch(
  () => form.frequency,
  (frequency) => {
    if (frequency !== 'yearly') {
      form.yearlyAlignment = defaultYearAlignment.value
    }
    applyFrequencyDefaults()
  }
)

watch(
  () => form.yearlyAlignment,
  () => {
    if (form.frequency === 'yearly') {
      applyFrequencyDefaults()
    }
  }
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

function computeWindowExpiration(frequency) {
  const cycle = currentCycle.value
  if (!cycle) {
    return ''
  }
  const windows = computeFrequencyWindows(cycle, frequency)
  if (!windows.length) {
    return ''
  }
  const today = Date.now()
  const activeWindow =
    windows.find((window) => {
      const start = window.start.getTime()
      const end = window.end.getTime()
      return today >= start && today < end
    }) || windows[windows.length - 1]
  if (!activeWindow || !(activeWindow.end instanceof Date)) {
    return ''
  }
  const windowEnd = new Date(activeWindow.end.getTime() - 24 * 60 * 60 * 1000)
  return formatDateInput(windowEnd)
}

function computeDefaultExpiration(frequency) {
  if (frequency === 'monthly' || frequency === 'quarterly' || frequency === 'semiannual') {
    return computeWindowExpiration(frequency)
  }
  if (frequency === 'yearly') {
    if (form.yearlyAlignment === 'anniversary') {
      const end = new Date(currentCycle.value.end)
      end.setDate(end.getDate() - 1)
      return formatDateInput(end)
    }
    const currentYearEnd = new Date(new Date().getFullYear(), 11, 31)
    return formatDateInput(currentYearEnd)
  }
  return ''
}

function applyFrequencyDefaults() {
  if (!autoExpiration.value) {
    return
  }
  form.expiration_date = computeDefaultExpiration(form.frequency)
}

function resetForm() {
  form.name = ''
  form.description = ''
  form.frequency = defaultFrequency.value
  form.type = 'standard'
  form.value = ''
  form.expected_value = ''
  form.expiration_date = ''
  form.yearlyAlignment = defaultYearAlignment.value
  autoExpiration.value = true
  applyFrequencyDefaults()
}

function handleExpirationInput() {
  autoExpiration.value = false
}

function openNewBenefitModal() {
  formMode.value = 'create'
  editingBenefitId.value = null
  resetForm()
  benefitModalOpen.value = true
}

function populateForm(benefit) {
  formMode.value = 'edit'
  editingBenefitId.value = benefit.id
  autoExpiration.value = false
  form.name = benefit.name
  form.description = benefit.description || ''
  form.frequency = benefit.frequency
  form.type = benefit.type || 'standard'
  form.value =
    benefit.type === 'cumulative' || benefit.value === null
      ? ''
      : String(benefit.value)
  form.expected_value =
    benefit.type === 'cumulative' && benefit.expected_value != null
      ? benefit.expected_value.toString()
      : ''
  form.expiration_date = benefit.expiration_date || ''
  form.yearlyAlignment = defaultYearAlignment.value
  if (benefit.frequency === 'yearly' && benefit.expiration_date) {
    const expirationDate = new Date(`${benefit.expiration_date}T00:00:00`)
    const cycleAtExpiration = computeCardCycle(props.card, expirationDate)
    const cycleEnd = new Date(cycleAtExpiration.end)
    cycleEnd.setDate(cycleEnd.getDate() - 1)
    const cycleEndString = formatDateInput(cycleEnd)
    const calendarEnd = new Date(expirationDate.getFullYear(), 11, 31)
    const calendarEndString = formatDateInput(calendarEnd)
    if (benefit.expiration_date === cycleEndString) {
      form.yearlyAlignment = 'anniversary'
    } else if (benefit.expiration_date === calendarEndString) {
      form.yearlyAlignment = 'calendar'
    }
  }
  benefitModalOpen.value = true
}

function closeBenefitModal() {
  benefitModalOpen.value = false
  formMode.value = 'create'
  editingBenefitId.value = null
  resetForm()
}

function toggleBenefits() {
  benefitsExpanded.value = !benefitsExpanded.value
}

function submitForm() {
  if (!form.name) {
    return
  }
  if (form.type !== 'cumulative' && !form.value) {
    return
  }
  const payload = {
    name: form.name,
    description: form.description || null,
    frequency: form.frequency,
    type: form.type,
    expiration_date: form.expiration_date || null
  }
  if (form.type !== 'cumulative') {
    payload.value = Number(form.value)
  } else {
    const rawExpected =
      typeof form.expected_value === 'string'
        ? form.expected_value.trim()
        : form.expected_value
    if (rawExpected === '' || rawExpected === null || rawExpected === undefined) {
      payload.expected_value = null
    } else {
      const parsed = Number(rawExpected)
      payload.expected_value = Number.isNaN(parsed) ? null : parsed
    }
  }
  if (formMode.value === 'edit' && editingBenefitId.value) {
    emit('update-benefit', {
      cardId: props.card.id,
      benefitId: editingBenefitId.value,
      payload
    })
  } else {
    emit('add-benefit', {
      cardId: props.card.id,
      payload
    })
  }
  closeBenefitModal()
}

function handleBenefitEdit(benefit) {
  populateForm(benefit)
}

function handleBenefitHistory(benefit) {
  emit('view-benefit-windows', { card: props.card, benefit })
}

function handleCardHistory() {
  emit('view-card-history', props.card)
}

function handleCardEdit() {
  emit('edit-card', props.card)
}

function handleCardDelete() {
  emit('delete-card', props.card.id)
}
</script>

<template>
  <article class="card">
    <header class="card-header">
      <div class="card-header__info">
        <div class="card-title">{{ card.card_name }}</div>
        <div class="card-subtitle">
          <span v-if="card.company_name" class="company-pill">{{ card.company_name }}</span>
          <span>Ending {{ card.last_four }}</span>
          <span>•</span>
          <span>{{ card.account_name }}</span>
        </div>
        <div class="card-due">Fee due {{ new Date(card.fee_due_date).toLocaleDateString() }}</div>
      </div>
      <div class="card-header__meta">
        <div class="card-cycle">
          <div class="card-cycle__label">{{ cycleSubtitle }}</div>
          <div class="card-cycle__value">{{ currentCycle.label }}</div>
          <div class="card-cycle__range">{{ cycleCoverage }}</div>
        </div>
        <div class="card-toolbar">
          <button class="icon-button ghost" type="button" @click="handleCardHistory" title="View card history">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linecap="round" d="M4 6h12M4 10h12M4 14h12" />
            </svg>
            <span class="sr-only">View card history</span>
          </button>
          <button class="icon-button ghost" type="button" @click="handleCardEdit" title="Edit card">
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M15.58 2.42a1.5 1.5 0 0 0-2.12 0l-9 9V17h5.59l9-9a1.5 1.5 0 0 0 0-2.12zM7 15H5v-2l6.88-6.88 2 2z" />
            </svg>
            <span class="sr-only">Edit card</span>
          </button>
          <button class="icon-button danger" type="button" @click="handleCardDelete" title="Remove card">
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M7 3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1h3.5a.5.5 0 0 1 0 1h-.8l-.62 11a2 2 0 0 1-2 1.9H6.92a2 2 0 0 1-2-1.9L4.3 5H3.5a.5.5 0 0 1 0-1H7zm1 1h4V3H8zM6.3 5l.6 10.8a1 1 0 0 0 1 1h4.2a1 1 0 0 0 1-1L13.7 5z" />
            </svg>
            <span class="sr-only">Remove card</span>
          </button>
        </div>
      </div>
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
          <button class="primary-button secondary small" type="button" @click="openNewBenefitModal">
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
            @add-redemption="emit('add-redemption', { card, benefit })"
            @view-history="emit('view-history', { card, benefit })"
            @edit="handleBenefitEdit"
            @view-windows="handleBenefitHistory"
          />
        </div>
        <p v-else class="empty-state empty-benefits">
          No benefits tracked yet.
          <button class="link-button inline" type="button" @click="openNewBenefitModal">Add one now</button>
          .
        </p>
      </div>
    </section>

    <BaseModal
      :open="benefitModalOpen"
      :title="formMode === 'edit' ? 'Edit benefit' : 'Add a benefit'"
      @close="closeBenefitModal"
    >
      <form @submit.prevent="submitForm">
        <div class="field-group">
          <input v-model="form.name" type="text" placeholder="Benefit name" required />
          <select v-model="form.type">
            <option v-for="option in benefitTypes" :key="option" :value="option">
              {{ option.charAt(0).toUpperCase() + option.slice(1) }}
            </option>
          </select>
        </div>
        <textarea v-model="form.description" rows="3" placeholder="Description (optional)"></textarea>
        <div class="field-group">
          <input
            v-if="form.type !== 'cumulative'"
            v-model="form.value"
            type="number"
            min="0"
            step="0.01"
            placeholder="Value"
            :required="form.type !== 'cumulative'"
          />
          <input
            v-else
            v-model="form.expected_value"
            type="number"
            min="0"
            step="0.01"
            placeholder="Expected value (optional)"
          />
          <select v-model="form.frequency">
            <option v-for="option in frequencies" :key="option" :value="option">
              {{ option.charAt(0).toUpperCase() + option.slice(1) }}
            </option>
          </select>
          <input v-model="form.expiration_date" type="date" @input="handleExpirationInput" />
        </div>
        <div v-if="form.frequency === 'yearly'" class="yearly-options">
          <label class="radio-option">
            <input v-model="form.yearlyAlignment" type="radio" value="calendar" />
            <span>Calendar year</span>
          </label>
          <label class="radio-option">
            <input v-model="form.yearlyAlignment" type="radio" value="anniversary" />
            <span>Align with AF year</span>
          </label>
        </div>
        <p class="helper-text">{{ currentTypeDescription }}</p>
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
.card-subtitle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  color: #475569;
  font-size: 0.9rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.card-header__info {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.card-due {
  font-size: 0.85rem;
  color: #64748b;
}

.card-header__meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.card-cycle {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.15rem;
}

.card-cycle__label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.72rem;
  color: #6366f1;
  font-weight: 600;
}

.card-cycle__value {
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
}

.card-cycle__range {
  font-size: 0.8rem;
  color: #64748b;
}

.card-toolbar {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.card-toolbar .icon-button {
  width: 1.65rem;
  height: 1.65rem;
}

.card-toolbar .icon-button svg {
  width: 0.95rem;
  height: 0.95rem;
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

.yearly-options {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.25rem 0 0.5rem;
}

.radio-option {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.9rem;
  color: #475569;
}

.radio-option input {
  accent-color: #6366f1;
}

.helper-text {
  margin: 0.25rem 0 0.75rem;
  font-size: 0.85rem;
  color: #475569;
}
</style>

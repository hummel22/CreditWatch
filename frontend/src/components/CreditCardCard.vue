<script setup>
import { computed, reactive, ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'
import BenefitCard from './BenefitCard.vue'
import { computeCardCycle, computeFrequencyWindows, computeCycleForMode, formatDateInput, parseDate } from '../utils/dates'
import { sortBenefits } from '../utils/benefits'

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
  'view-benefit-windows',
  'export-template'
])

const benefitModalOpen = ref(false)
const benefitsExpanded = ref(true)
const formMode = ref('create')
const editingBenefitId = ref(null)
const autoExpiration = ref(true)

const defaultFrequency = computed(() => props.frequencies[0] || 'monthly')
const benefitTypes = ['standard', 'incremental', 'cumulative']
const WINDOW_COUNTS = {
  monthly: 12,
  quarterly: 4,
  semiannual: 2
}
const defaultAlignment = computed(() =>
  props.card.year_tracking_mode === 'anniversary' ? 'anniversary' : 'calendar'
)

const sortedBenefits = computed(() => sortBenefits(props.card.benefits))

const form = reactive({
  name: '',
  description: '',
  frequency: defaultFrequency.value,
  type: 'standard',
  value: '',
  expected_value: '',
  expiration_date: '',
  windowTrackingMode: null,
  useCustomValues: false,
  window_values: [],
  excludeFromBenefitsPage: false,
  excludeFromNotifications: false
})

const typeDescriptions = {
  standard: 'Standard benefits are toggled once per cycle.',
  incremental: 'Incremental benefits accrue value as you log redemptions until reaching the goal.',
  cumulative: 'Cumulative benefits build value as you add redemptions.'
}

const currentTypeDescription = computed(() => typeDescriptions[form.type])

const currentCycle = computed(() => computeCardCycle(props.card))

const canUseCustomWindowValues = computed(
  () => form.type !== 'cumulative' && Object.prototype.hasOwnProperty.call(WINDOW_COUNTS, form.frequency)
)

const windowOptions = computed(() => {
  if (!canUseCustomWindowValues.value) {
    return []
  }
  const cycle = formCycle.value
  if (!cycle) {
    return []
  }
  const windows = computeFrequencyWindows(cycle, form.frequency)
  return windows.map((window, index) => ({
    index: typeof window.index === 'number' ? window.index : index + 1,
    label: window.label
  }))
})

const windowValueDescriptor = computed(() => {
  if (form.frequency === 'monthly') {
    return 'month'
  }
  if (form.frequency === 'quarterly') {
    return 'quarter'
  }
  if (form.frequency === 'semiannual') {
    return 'half-year'
  }
  return 'window'
})

const valuePlaceholder = computed(() => {
  if (form.type === 'cumulative') {
    return 'Expected value (optional)'
  }
  if (canUseCustomWindowValues.value) {
    return `Value per ${windowValueDescriptor.value}`
  }
  if (form.frequency === 'yearly') {
    return 'Value per year'
  }
  return 'Value'
})

const supportsAlignmentOverride = computed(() =>
  ['monthly', 'quarterly', 'semiannual', 'yearly'].includes(form.frequency)
)

const alignmentSelection = computed({
  get() {
    return form.windowTrackingMode || defaultAlignment.value
  },
  set(value) {
    if (value === defaultAlignment.value) {
      form.windowTrackingMode = null
    } else {
      form.windowTrackingMode = value
    }
  }
})

const formCycle = computed(() => computeCycleForMode(props.card, alignmentSelection.value))

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
      form.useCustomValues = false
      form.window_values = []
    } else {
      form.expected_value = ''
      if (form.useCustomValues) {
        normaliseFormWindowValues()
      }
    }
  }
)

watch(
  () => props.card.year_tracking_mode,
  () => {
    if (formMode.value === 'create') {
      form.windowTrackingMode = null
      applyFrequencyDefaults()
    }
  }
)

watch(
  () => form.frequency,
  (frequency) => {
    if (!supportsAlignmentOverride.value) {
      form.windowTrackingMode = null
    }
    applyFrequencyDefaults()
    if (!canUseCustomWindowValues.value) {
      form.useCustomValues = false
      form.window_values = []
    } else if (form.useCustomValues) {
      normaliseFormWindowValues()
    }
  }
)

watch(
  () => form.useCustomValues,
  (enabled) => {
    if (enabled) {
      normaliseFormWindowValues()
    } else {
      form.window_values = []
    }
  }
)

watch(
  () => windowOptions.value.length,
  () => {
    if (form.useCustomValues) {
      normaliseFormWindowValues()
    }
  }
)

watch(
  () => form.value,
  () => {
    if (form.useCustomValues && canUseCustomWindowValues.value) {
      normaliseFormWindowValues()
    }
  }
)

watch(alignmentSelection, () => {
  if (autoExpiration.value) {
    applyFrequencyDefaults()
  }
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

function computeDefaultExpiration(frequency) {
  const cycle = formCycle.value
  if (!cycle) {
    return ''
  }
  if (['monthly', 'quarterly', 'semiannual'].includes(frequency)) {
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
  if (frequency === 'yearly') {
    const end = new Date(cycle.end)
    end.setDate(end.getDate() - 1)
    return formatDateInput(end)
  }
  return ''
}

function applyFrequencyDefaults() {
  if (!autoExpiration.value) {
    return
  }
  form.expiration_date = computeDefaultExpiration(form.frequency)
}

function normaliseFormWindowValues() {
  if (!form.useCustomValues || !canUseCustomWindowValues.value) {
    form.window_values = []
    return
  }
  const count = WINDOW_COUNTS[form.frequency] || 0
  const values = Array.isArray(form.window_values) ? [...form.window_values] : []
  const trimmed = values.slice(0, count)
  const baseValue =
    form.value !== '' && form.value != null ? form.value.toString() : ''
  while (trimmed.length < count) {
    trimmed.push(baseValue)
  }
  if (baseValue !== '') {
    for (let index = 0; index < trimmed.length; index += 1) {
      if (trimmed[index] === '') {
        trimmed[index] = baseValue
      }
    }
  }
  form.window_values = trimmed
}

function resetForm() {
  form.name = ''
  form.description = ''
  form.frequency = defaultFrequency.value
  form.type = 'standard'
  form.value = ''
  form.expected_value = ''
  form.expiration_date = ''
  form.windowTrackingMode = null
  form.useCustomValues = false
  form.window_values = []
  form.excludeFromBenefitsPage = false
  form.excludeFromNotifications = false
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
  form.windowTrackingMode = benefit.window_tracking_mode || null
  form.useCustomValues = Array.isArray(benefit.window_values) && benefit.window_values.length > 0
  form.window_values = form.useCustomValues
    ? benefit.window_values.map((value) => value.toString())
    : []
  form.excludeFromBenefitsPage = Boolean(benefit.exclude_from_benefits_page)
  form.excludeFromNotifications = Boolean(benefit.exclude_from_notifications)
  if (benefit.frequency === 'yearly' && benefit.expiration_date) {
    const expirationDate = new Date(`${benefit.expiration_date}T00:00:00`)
    const cycleAtExpiration = computeCardCycle(props.card, expirationDate)
    const cycleEnd = new Date(cycleAtExpiration.end)
    cycleEnd.setDate(cycleEnd.getDate() - 1)
    const cycleEndString = formatDateInput(cycleEnd)
    const calendarEnd = new Date(expirationDate.getFullYear(), 11, 31)
    const calendarEndString = formatDateInput(calendarEnd)
    if (!form.windowTrackingMode) {
      if (benefit.expiration_date === cycleEndString) {
        form.windowTrackingMode = 'anniversary'
      } else if (benefit.expiration_date === calendarEndString) {
        form.windowTrackingMode = 'calendar'
      }
    }
  }
  if (form.windowTrackingMode === defaultAlignment.value) {
    form.windowTrackingMode = null
  }
  if (!canUseCustomWindowValues.value) {
    form.useCustomValues = false
    form.window_values = []
  } else if (form.useCustomValues) {
    normaliseFormWindowValues()
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
  if (supportsAlignmentOverride.value) {
    if (form.windowTrackingMode) {
      payload.window_tracking_mode = form.windowTrackingMode
    } else if (formMode.value === 'edit') {
      payload.window_tracking_mode = null
    }
  } else if (formMode.value === 'edit') {
    payload.window_tracking_mode = null
  }
  if (form.type !== 'cumulative') {
    payload.value = Number(form.value)
    if (form.useCustomValues && canUseCustomWindowValues.value) {
      payload.window_values = form.window_values.map((value) => Number(value || 0))
    } else if (formMode.value === 'edit') {
      payload.window_values = null
    }
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
  payload.exclude_from_benefits_page = form.excludeFromBenefitsPage
  payload.exclude_from_notifications = form.excludeFromNotifications
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

function handleCardExport() {
  emit('export-template', props.card)
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
        <div class="card-due">
          Fee due {{ new Date(card.fee_due_date).toLocaleDateString() }}
          <span v-if="card.is_cancelled" class="card-status card-status--cancelled">Cancelled</span>
        </div>
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
          <button class="icon-button ghost" type="button" @click="handleCardExport" title="Export as template">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
              <rect x="6" y="5" width="9" height="11" rx="1.6" />
              <path d="M4 11V6.6A1.6 1.6 0 0 1 5.6 5H11" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span class="sr-only">Export as template</span>
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
            v-for="benefit in sortedBenefits"
            :key="benefit.id"
            :benefit="benefit"
            :card-context="card"
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
            :placeholder="valuePlaceholder"
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
        <div
          v-if="form.type !== 'cumulative' && canUseCustomWindowValues"
          class="custom-window-toggle"
        >
          <label class="checkbox-option">
            <input v-model="form.useCustomValues" type="checkbox" />
            <span>Set custom values for each {{ windowValueDescriptor }}</span>
          </label>
        </div>
        <div
          v-if="form.useCustomValues && canUseCustomWindowValues"
          class="window-values-grid"
        >
          <label v-for="window in windowOptions" :key="window.index">
            <span>{{ window.label }}</span>
            <input
              v-model="form.window_values[window.index - 1]"
              type="number"
              min="0"
              step="0.01"
            />
          </label>
        </div>
        <div v-if="supportsAlignmentOverride" class="alignment-options">
          <label class="radio-option">
            <input v-model="alignmentSelection" type="radio" value="calendar" />
            <span>Calendar year</span>
          </label>
          <label class="radio-option">
            <input v-model="alignmentSelection" type="radio" value="anniversary" />
            <span>Align with AF year</span>
          </label>
        </div>
        <label class="checkbox-option">
          <input v-model="form.excludeFromBenefitsPage" type="checkbox" />
          <span>Hide from benefits overview</span>
        </label>
        <label class="checkbox-option">
          <input v-model="form.excludeFromNotifications" type="checkbox" />
          <span>Exclude from notifications</span>
        </label>
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

.card-status {
  display: inline-flex;
  align-items: center;
  margin-left: 0.5rem;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border: 1px solid transparent;
}

.card-status--cancelled {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
  border-color: rgba(239, 68, 68, 0.32);
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

.custom-window-toggle {
  margin-top: 0.75rem;
}

.checkbox-option {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: #475569;
}

.checkbox-option input {
  width: 1rem;
  height: 1rem;
  accent-color: #6366f1;
}

.window-values-grid {
  margin-top: 0.75rem;
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fill, minmax(8rem, 1fr));
}

.window-values-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.8rem;
  color: #475569;
}

.window-values-grid input {
  padding: 0.4rem 0.5rem;
  border: 1px solid #cbd5f5;
  border-radius: 0.4rem;
  font-size: 0.9rem;
  color: #0f172a;
}

.alignment-options {
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

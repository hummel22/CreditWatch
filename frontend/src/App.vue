<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import axios from 'axios'
import BaseModal from './components/BaseModal.vue'
import CreditCardList from './components/CreditCardList.vue'
import {
  buildCardCycles,
  computeCardCycle,
  computeFrequencyWindows,
  isWithinRange,
  parseDate
} from './utils/dates'

const cards = ref([])
const loading = ref(false)
const error = ref('')
const frequencies = ref(['monthly', 'quarterly', 'semiannual', 'yearly'])
const preconfiguredCards = ref([])

const showCardModal = ref(false)

const newCard = reactive({
  card_name: '',
  company_name: '',
  last_four: '',
  account_name: '',
  annual_fee: '',
  fee_due_date: '',
  year_tracking_mode: 'calendar'
})

const selectedTemplateSlug = ref('')
const selectedTemplate = computed(() =>
  preconfiguredCards.value.find((card) => card.slug === selectedTemplateSlug.value)
)

watch(
  selectedTemplate,
  (template) => {
    if (template) {
      newCard.card_name = template.card_type
      newCard.company_name = template.company_name
      newCard.annual_fee = template.annual_fee.toString()
    }
  }
)

const redemptionModal = reactive({
  open: false,
  mode: 'create',
  cardId: null,
  benefitId: null,
  benefit: null,
  redemptionId: null,
  card: null,
  label: '',
  amount: '',
  occurred_on: ''
})

const historyModal = reactive({
  open: false,
  cardId: null,
  benefitId: null,
  benefit: null,
  entries: [],
  loading: false,
  windowLabel: '',
  windowRange: null
})

const editCardModal = reactive({
  open: false,
  cardId: null,
  form: {
    card_name: '',
    company_name: '',
    last_four: '',
    account_name: '',
    annual_fee: '',
    fee_due_date: '',
    year_tracking_mode: 'calendar'
  }
})

const cardHistoryModal = reactive({
  open: false,
  cardId: null,
  card: null,
  years: [],
  loading: false
})

const benefitWindowsModal = reactive({
  open: false,
  cardId: null,
  benefitId: null,
  card: null,
  benefit: null,
  windows: [],
  loading: false
})

const totals = computed(() => {
  const annualFees = cards.value.reduce((acc, card) => acc + card.annual_fee, 0)
  const utilized = cards.value.reduce((acc, card) => acc + card.utilized_value, 0)
  const potential = cards.value.reduce((acc, card) => acc + card.potential_value, 0)
  return {
    annualFees,
    utilized,
    potential,
    net: utilized - annualFees
  }
})

async function loadFrequencies() {
  try {
    const response = await axios.get('/api/frequencies')
    if (Array.isArray(response.data) && response.data.length) {
      frequencies.value = response.data
    }
  } catch (err) {
    console.warn('Unable to load frequencies from API, using defaults.', err)
  }
}

async function loadCards() {
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/cards')
    cards.value = response.data
  } catch (err) {
    error.value = 'Unable to load cards. Ensure the backend is running.'
  } finally {
    loading.value = false
  }
}

async function loadPreconfiguredCards() {
  try {
    const response = await axios.get('/api/preconfigured/cards')
    if (Array.isArray(response.data)) {
      preconfiguredCards.value = response.data
    }
  } catch (err) {
    console.warn('Unable to load preconfigured cards.', err)
  }
}

function resetNewCard() {
  newCard.card_name = ''
  newCard.company_name = ''
  newCard.last_four = ''
  newCard.account_name = ''
  newCard.annual_fee = ''
  newCard.fee_due_date = ''
  newCard.year_tracking_mode = 'calendar'
  selectedTemplateSlug.value = ''
}

function closeCardModal() {
  showCardModal.value = false
  resetNewCard()
}

async function handleCreateCard() {
  if (!newCard.card_name || !newCard.company_name || newCard.last_four.length !== 4) {
    error.value = 'Please provide a card name, company, and the last four digits.'
    return
  }
  try {
    const payload = {
      card_name: newCard.card_name,
      company_name: newCard.company_name,
      last_four: newCard.last_four,
      account_name: newCard.account_name,
      annual_fee: Number(newCard.annual_fee || 0),
      fee_due_date: newCard.fee_due_date,
      year_tracking_mode: newCard.year_tracking_mode
    }
    const response = await axios.post('/api/cards', payload)
    const template = selectedTemplate.value
    if (template) {
      for (const benefit of template.benefits) {
        const benefitPayload = {
          name: benefit.name,
          description: benefit.description || null,
          frequency: benefit.frequency,
          type: benefit.type,
          value: benefit.type === 'cumulative' ? undefined : benefit.value,
          expiration_date: null
        }
        if (benefitPayload.value === undefined) {
          delete benefitPayload.value
        }
        await axios.post(`/api/cards/${response.data.id}/benefits`, benefitPayload)
      }
      await loadCards()
    } else {
      cards.value.push(response.data)
    }
    closeCardModal()
    error.value = ''
  } catch (err) {
    error.value = 'Could not create the card. Check the form data and try again.'
  }
}

async function handleAddBenefit({ cardId, payload }) {
  try {
    const body = { ...payload }
    if (body.value === undefined) {
      delete body.value
    }
    await axios.post(`/api/cards/${cardId}/benefits`, body)
    const refreshed = await axios.get('/api/cards')
    cards.value = refreshed.data
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to add the benefit. Please try again.'
  }
}

async function handleToggleBenefit({ id, value }) {
  try {
    await axios.post(`/api/benefits/${id}/usage`, { is_used: value })
    const refreshed = await axios.get('/api/cards')
    cards.value = refreshed.data
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to update the benefit usage.'
  }
}

async function handleDeleteBenefit(benefitId) {
  try {
    await axios.delete(`/api/benefits/${benefitId}`)
    const refreshed = await axios.get('/api/cards')
    cards.value = refreshed.data
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to remove the benefit.'
  }
}

async function handleDeleteCard(cardId) {
  try {
    await axios.delete(`/api/cards/${cardId}`)
    await loadCards()
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to delete the card.'
  }
}

function handleAddRedemption(payload) {
  const benefit = payload?.benefit || payload
  const cardId = payload?.card?.id || benefit.credit_card_id
  const card = findCard(cardId) || payload?.card || null
  const trackedBenefit = findBenefit(cardId, benefit.id) || benefit
  redemptionModal.open = true
  redemptionModal.mode = 'create'
  redemptionModal.cardId = cardId
  redemptionModal.benefitId = trackedBenefit.id
  redemptionModal.benefit = trackedBenefit
  redemptionModal.redemptionId = null
  redemptionModal.label = ''
  redemptionModal.amount = ''
  redemptionModal.occurred_on = new Date().toISOString().slice(0, 10)
  redemptionModal.card = card
}

function closeRedemptionModal() {
  redemptionModal.open = false
  redemptionModal.mode = 'create'
  redemptionModal.cardId = null
  redemptionModal.benefitId = null
  redemptionModal.redemptionId = null
  redemptionModal.benefit = null
  redemptionModal.card = null
  redemptionModal.label = ''
  redemptionModal.amount = ''
  redemptionModal.occurred_on = ''
}

async function submitRedemption() {
  if (!redemptionModal.benefitId || !redemptionModal.amount) {
    return
  }
  try {
    const amount = Number(redemptionModal.amount)
    if (!Number.isFinite(amount) || amount <= 0) {
      return
    }
    const body = {
      label: redemptionModal.label || 'Redemption',
      amount,
      occurred_on: redemptionModal.occurred_on
    }
    if (redemptionModal.mode === 'edit' && redemptionModal.redemptionId) {
      await axios.put(`/api/redemptions/${redemptionModal.redemptionId}`, body)
    } else {
      await axios.post(`/api/benefits/${redemptionModal.benefitId}/redemptions`, body)
    }
    await loadCards()
    await refreshOpenModals()
    closeRedemptionModal()
  } catch (err) {
    error.value = 'Unable to record the redemption.'
  }
}

function handleEditRedemption(entry) {
  if (!historyModal.benefitId || !historyModal.cardId) {
    return
  }
  const card = findCard(historyModal.cardId)
  const benefit = findBenefit(historyModal.cardId, historyModal.benefitId)
  if (!benefit) {
    return
  }
  redemptionModal.open = true
  redemptionModal.mode = 'edit'
  redemptionModal.cardId = historyModal.cardId
  redemptionModal.card = card
  redemptionModal.benefitId = benefit.id
  redemptionModal.benefit = benefit
  redemptionModal.redemptionId = entry.id
  redemptionModal.label = entry.label
  redemptionModal.amount = Number(entry.amount).toString()
  redemptionModal.occurred_on = entry.occurred_on
}

async function handleDeleteRedemption(entry) {
  try {
    await axios.delete(`/api/redemptions/${entry.id}`)
    await loadCards()
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to delete the redemption.'
  }
}

async function handleViewHistory(payload) {
  const benefit = payload?.benefit || payload
  const cardId = payload?.card?.id || benefit.credit_card_id
  const card = findCard(cardId) || payload?.card || null
  const trackedBenefit = findBenefit(cardId, benefit.id) || benefit
  historyModal.open = true
  historyModal.cardId = cardId
  historyModal.benefitId = trackedBenefit.id
  historyModal.benefit = trackedBenefit
  historyModal.entries = []
  historyModal.windowLabel = ''
  historyModal.windowRange = null
  historyModal.loading = true
  try {
    await populateHistoryModal(card, trackedBenefit)
  } catch (err) {
    error.value = 'Unable to load redemption history.'
  } finally {
    historyModal.loading = false
  }
}

async function handleUpdateBenefit({ cardId, benefitId, payload }) {
  try {
    const body = { ...payload }
    if (body.value === undefined) {
      delete body.value
    }
    await axios.put(`/api/benefits/${benefitId}`, body)
    await loadCards()
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to update the benefit.'
  }
}

function handleEditCard(card) {
  editCardModal.open = true
  editCardModal.cardId = card.id
  editCardModal.form.card_name = card.card_name
  editCardModal.form.company_name = card.company_name
  editCardModal.form.last_four = card.last_four
  editCardModal.form.account_name = card.account_name
  editCardModal.form.annual_fee = card.annual_fee.toString()
  editCardModal.form.fee_due_date = card.fee_due_date
  editCardModal.form.year_tracking_mode = card.year_tracking_mode || 'calendar'
}

function closeEditCardModal() {
  editCardModal.open = false
  editCardModal.cardId = null
  editCardModal.form.card_name = ''
  editCardModal.form.company_name = ''
  editCardModal.form.last_four = ''
  editCardModal.form.account_name = ''
  editCardModal.form.annual_fee = ''
  editCardModal.form.fee_due_date = ''
  editCardModal.form.year_tracking_mode = 'calendar'
}

async function submitEditCard() {
  if (!editCardModal.cardId) {
    return
  }
  try {
    const payload = {
      card_name: editCardModal.form.card_name,
      company_name: editCardModal.form.company_name,
      last_four: editCardModal.form.last_four,
      account_name: editCardModal.form.account_name,
      annual_fee: Number(editCardModal.form.annual_fee || 0),
      fee_due_date: editCardModal.form.fee_due_date,
      year_tracking_mode: editCardModal.form.year_tracking_mode
    }
    await axios.put(`/api/cards/${editCardModal.cardId}`, payload)
    await loadCards()
    await refreshOpenModals()
    closeEditCardModal()
  } catch (err) {
    error.value = 'Unable to update the credit card.'
  }
}

async function handleViewCardHistory(card) {
  cardHistoryModal.open = true
  cardHistoryModal.cardId = card.id
  cardHistoryModal.card = card
  cardHistoryModal.years = []
  cardHistoryModal.loading = true
  try {
    await populateCardHistory(card)
  } catch (err) {
    error.value = 'Unable to load card history.'
  } finally {
    cardHistoryModal.loading = false
  }
}

function closeCardHistoryModal() {
  cardHistoryModal.open = false
  cardHistoryModal.cardId = null
  cardHistoryModal.card = null
  cardHistoryModal.years = []
}

async function handleViewBenefitWindows(payload) {
  const benefit = payload?.benefit || payload
  const cardId = payload?.card?.id || benefit.credit_card_id
  const card = findCard(cardId) || payload?.card || null
  const trackedBenefit = findBenefit(cardId, benefit.id) || benefit
  benefitWindowsModal.open = true
  benefitWindowsModal.cardId = cardId
  benefitWindowsModal.benefitId = trackedBenefit.id
  benefitWindowsModal.card = card
  benefitWindowsModal.benefit = trackedBenefit
  benefitWindowsModal.windows = []
  benefitWindowsModal.loading = true
  try {
    await populateBenefitWindows(card, trackedBenefit)
  } catch (err) {
    error.value = 'Unable to load benefit window history.'
  } finally {
    benefitWindowsModal.loading = false
  }
}

function closeBenefitWindowsModal() {
  benefitWindowsModal.open = false
  benefitWindowsModal.cardId = null
  benefitWindowsModal.benefitId = null
  benefitWindowsModal.card = null
  benefitWindowsModal.benefit = null
  benefitWindowsModal.windows = []
}

function formatCycleRange(start, end) {
  const effectiveEnd = new Date(end)
  effectiveEnd.setDate(effectiveEnd.getDate() - 1)
  const sameYear = start.getFullYear() === effectiveEnd.getFullYear()
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
  return `${startFormatter.format(start)} – ${endFormatter.format(effectiveEnd)}`
}

async function fetchBenefitRedemptions(benefitId) {
  const response = await axios.get(`/api/benefits/${benefitId}/redemptions`)
  return Array.isArray(response.data) ? response.data : []
}

async function populateHistoryModal(card, benefit) {
  const resolvedCard = card || findCard(benefit.credit_card_id)
  if (!resolvedCard) {
    historyModal.entries = []
    historyModal.windowLabel = ''
    historyModal.windowRange = null
    return
  }
  const cycle = computeCardCycle(resolvedCard)
  const windows = computeFrequencyWindows(cycle, benefit.frequency)
  const today = new Date()
  const currentWindow =
    windows.find((window) => isWithinRange(today, window.start, window.end)) ||
    windows[windows.length - 1] ||
    null
  historyModal.windowRange = currentWindow
  historyModal.windowLabel = currentWindow ? currentWindow.label : ''
  const entries = await fetchBenefitRedemptions(benefit.id)
  historyModal.entries = currentWindow
    ? entries.filter((entry) =>
        isWithinRange(entry.occurred_on, currentWindow.start, currentWindow.end)
      )
    : entries
}

async function populateBenefitWindows(card, benefit) {
  const resolvedCard = card || findCard(benefit.credit_card_id)
  if (!resolvedCard) {
    benefitWindowsModal.windows = []
    return
  }
  const cycle = computeCardCycle(resolvedCard)
  const windows = computeFrequencyWindows(cycle, benefit.frequency)
  const entries = await fetchBenefitRedemptions(benefit.id)
  benefitWindowsModal.windows = windows.map((window) => {
    const windowEntries = entries.filter((entry) =>
      isWithinRange(entry.occurred_on, window.start, window.end)
    )
    const total = windowEntries.reduce((acc, entry) => acc + Number(entry.amount), 0)
    const remaining =
      benefit.type === 'incremental'
        ? Math.max((benefit.value ?? 0) - total, 0)
        : null
    return {
      label: window.label,
      start: window.start,
      end: window.end,
      entries: windowEntries,
      total,
      remaining
    }
  })
}

async function populateCardHistory(card) {
  const resolvedCard = card || (cardHistoryModal.cardId ? findCard(cardHistoryModal.cardId) : null)
  if (!resolvedCard) {
    cardHistoryModal.years = []
    return
  }
  const benefitRedemptions = new Map()
  let earliest = parseDate(resolvedCard.created_at) || new Date()
  const tasks = resolvedCard.benefits.map(async (benefit) => {
    const entries = await fetchBenefitRedemptions(benefit.id)
    benefitRedemptions.set(benefit.id, entries)
    for (const entry of entries) {
      const occurred = parseDate(entry.occurred_on)
      if (occurred && occurred < earliest) {
        earliest = occurred
      }
    }
    if (benefit.used_at) {
      const usedAt = parseDate(benefit.used_at)
      if (usedAt && usedAt < earliest) {
        earliest = usedAt
      }
    }
  })
  await Promise.all(tasks)
  const cycles = buildCardCycles(resolvedCard, earliest)
  cardHistoryModal.years = cycles.map((cycle) => {
    const benefits = resolvedCard.benefits.map((benefit) => {
      const entries = benefitRedemptions.get(benefit.id) || []
      const windowEntries = entries.filter((entry) =>
        isWithinRange(entry.occurred_on, cycle.start, cycle.end)
      )
      const total = windowEntries.reduce((acc, entry) => acc + Number(entry.amount), 0)
      let potential = 0
      let utilized = 0
      let remaining = null
      let statusLabel = ''
      let statusTone = ''
      if (benefit.type === 'standard') {
        potential = benefit.value ?? 0
        const used = Boolean(
          benefit.used_at && isWithinRange(benefit.used_at, cycle.start, cycle.end)
        )
        utilized = used ? potential : 0
        statusLabel = used ? 'Utilized' : 'Available'
        statusTone = used ? 'success' : 'warning'
      } else if (benefit.type === 'incremental') {
        potential = benefit.value ?? 0
        utilized = Math.min(total, potential)
        const isComplete = potential > 0 && utilized >= potential
        if (isComplete) {
          statusLabel = 'Completed'
          statusTone = 'success'
        } else if (total > 0) {
          statusLabel = 'In progress'
          statusTone = 'info'
        } else {
          statusLabel = 'Not started'
          statusTone = 'warning'
        }
        remaining = potential > 0 ? Math.max(potential - total, 0) : null
      } else {
        potential = total
        utilized = total
        if (total > 0) {
          statusLabel = 'Tracking'
          statusTone = 'info'
        } else {
          statusLabel = 'No activity'
          statusTone = 'warning'
        }
      }
      return {
        id: benefit.id,
        name: benefit.name,
        type: benefit.type,
        frequency: benefit.frequency,
        description: benefit.description,
        potential,
        utilized,
        total,
        remaining,
        status: { label: statusLabel, tone: statusTone },
        entries: windowEntries
      }
    })
    const potentialTotal = benefits.reduce((acc, item) => acc + item.potential, 0)
    const utilizedTotal = benefits.reduce((acc, item) => acc + item.utilized, 0)
    return {
      label: cycle.label,
      subtitle: cycle.mode === 'anniversary' ? 'AF year' : 'Calendar year',
      range: formatCycleRange(cycle.start, cycle.end),
      potential: potentialTotal,
      utilized: utilizedTotal,
      net: utilizedTotal - resolvedCard.annual_fee,
      benefits
    }
  })
  cardHistoryModal.card = resolvedCard
}

async function refreshOpenModals() {
  if (historyModal.open && historyModal.cardId && historyModal.benefitId) {
    const card = findCard(historyModal.cardId)
    const benefit = findBenefit(historyModal.cardId, historyModal.benefitId)
    if (card && benefit) {
      historyModal.loading = true
      historyModal.benefit = benefit
      try {
        await populateHistoryModal(card, benefit)
      } finally {
        historyModal.loading = false
      }
    } else {
      closeHistoryModal()
    }
  }
  if (benefitWindowsModal.open && benefitWindowsModal.cardId && benefitWindowsModal.benefitId) {
    const card = findCard(benefitWindowsModal.cardId)
    const benefit = findBenefit(benefitWindowsModal.cardId, benefitWindowsModal.benefitId)
    if (card && benefit) {
      benefitWindowsModal.loading = true
      benefitWindowsModal.card = card
      benefitWindowsModal.benefit = benefit
      try {
        await populateBenefitWindows(card, benefit)
      } finally {
        benefitWindowsModal.loading = false
      }
    } else {
      closeBenefitWindowsModal()
    }
  }
  if (cardHistoryModal.open && cardHistoryModal.cardId) {
    const card = findCard(cardHistoryModal.cardId)
    if (card) {
      cardHistoryModal.loading = true
      try {
        await populateCardHistory(card)
      } finally {
        cardHistoryModal.loading = false
      }
    } else {
      closeCardHistoryModal()
    }
  }
}

function findCard(cardId) {
  return cards.value.find((card) => card.id === cardId) || null
}

function findBenefit(cardId, benefitId) {
  const card = findCard(cardId)
  if (!card) {
    return null
  }
  return card.benefits.find((benefit) => benefit.id === benefitId) || null
}

function closeHistoryModal() {
  historyModal.open = false
  historyModal.cardId = null
  historyModal.benefitId = null
  historyModal.benefit = null
  historyModal.entries = []
  historyModal.windowLabel = ''
  historyModal.windowRange = null
}

onMounted(async () => {
  await loadFrequencies()
  await loadPreconfiguredCards()
  await loadCards()
})
</script>

<template>
  <main>
    <div class="container">
      <header>
        <h1 class="page-title">CreditWatch</h1>
        <p class="page-subtitle">
          Track every card, benefit, and annual fee so you always know if your cards pay for themselves.
        </p>
      </header>

      <section class="section-card">
        <div class="section-header">
          <h2 class="section-title">Add a credit card</h2>
          <button class="primary-button" type="button" @click="showCardModal = true">New card</button>
        </div>
        <p class="section-description">
          Keep your issuer, account, and fee details in one place so you always know a card's value.
        </p>
      </section>

      <BaseModal :open="showCardModal" title="Add a credit card" @close="closeCardModal">
        <form @submit.prevent="handleCreateCard">
          <div class="field-group">
            <select v-model="selectedTemplateSlug">
              <option value="">Select a preconfigured card (optional)</option>
              <option
                v-for="card in preconfiguredCards"
                :key="card.slug"
                :value="card.slug"
              >
                {{ card.card_type }} · {{ card.company_name }}
              </option>
            </select>
          </div>
          <p v-if="selectedTemplate" class="helper-text">
            Benefits from the selected template will be added automatically after the card
            is created.
          </p>
          <div class="field-group">
            <input v-model="newCard.card_name" type="text" placeholder="Card name" required />
            <input
              v-model="newCard.company_name"
              type="text"
              placeholder="Company name (e.g., Chase, Amex)"
              required
            />
          </div>
          <div class="field-group">
            <input
              v-model="newCard.last_four"
              type="text"
              maxlength="4"
              minlength="4"
              placeholder="Last four digits"
              required
            />
            <input v-model="newCard.account_name" type="text" placeholder="Account name" required />
          </div>
          <div class="field-group">
            <input v-model="newCard.annual_fee" type="number" min="0" step="0.01" placeholder="Annual fee" />
            <input v-model="newCard.fee_due_date" type="date" required />
          </div>
          <div class="radio-group">
            <label class="radio-option">
              <input v-model="newCard.year_tracking_mode" type="radio" value="calendar" />
              <span>Calendar year</span>
            </label>
            <label class="radio-option">
              <input v-model="newCard.year_tracking_mode" type="radio" value="anniversary" />
              <span>Align with AF year</span>
            </label>
          </div>
          <div class="modal-actions">
            <button class="primary-button secondary" type="button" @click="closeCardModal">Cancel</button>
            <button class="primary-button" type="submit">Save card</button>
          </div>
        </form>
      </BaseModal>

      <BaseModal :open="editCardModal.open" title="Edit credit card" @close="closeEditCardModal">
        <form @submit.prevent="submitEditCard">
          <div class="field-group">
            <input v-model="editCardModal.form.card_name" type="text" placeholder="Card name" required />
            <input
              v-model="editCardModal.form.company_name"
              type="text"
              placeholder="Company name"
              required
            />
          </div>
          <div class="field-group">
            <input
              v-model="editCardModal.form.last_four"
              type="text"
              maxlength="4"
              minlength="4"
              placeholder="Last four digits"
              required
            />
            <input v-model="editCardModal.form.account_name" type="text" placeholder="Account name" required />
          </div>
          <div class="field-group">
            <input
              v-model="editCardModal.form.annual_fee"
              type="number"
              min="0"
              step="0.01"
              placeholder="Annual fee"
            />
            <input v-model="editCardModal.form.fee_due_date" type="date" required />
          </div>
          <div class="radio-group">
            <label class="radio-option">
              <input v-model="editCardModal.form.year_tracking_mode" type="radio" value="calendar" />
              <span>Calendar year</span>
            </label>
            <label class="radio-option">
              <input v-model="editCardModal.form.year_tracking_mode" type="radio" value="anniversary" />
              <span>Align with AF year</span>
            </label>
          </div>
          <div class="modal-actions">
            <button class="primary-button secondary" type="button" @click="closeEditCardModal">Cancel</button>
            <button class="primary-button" type="submit">Save changes</button>
          </div>
        </form>
      </BaseModal>

      <section class="section-card">
        <h2 class="section-title">Portfolio overview</h2>
        <div class="summary-row">
          <span>Total annual fees: <strong>${{ totals.annualFees.toFixed(2) }}</strong></span>
          <span>Total potential: <strong>${{ totals.potential.toFixed(2) }}</strong></span>
          <span>Total utilized: <strong>${{ totals.utilized.toFixed(2) }}</strong></span>
          <span>Net position: <strong>${{ totals.net.toFixed(2) }}</strong></span>
        </div>
      </section>

      <section>
        <h2 class="section-title">Your cards</h2>
        <p v-if="loading" class="empty-state">Loading your cards...</p>
        <p v-else-if="!cards.length" class="empty-state">
          No cards yet. Add your first credit card to begin tracking benefits.
        </p>
        <div v-else>
          <CreditCardList
            :cards="cards"
            :frequencies="frequencies"
            @add-benefit="handleAddBenefit"
            @toggle-benefit="handleToggleBenefit"
            @delete-benefit="handleDeleteBenefit"
            @delete-card="handleDeleteCard"
            @add-redemption="handleAddRedemption"
            @view-history="handleViewHistory"
            @update-benefit="handleUpdateBenefit"
            @edit-card="handleEditCard"
            @view-card-history="handleViewCardHistory"
            @view-benefit-windows="handleViewBenefitWindows"
          />
        </div>
      </section>

      <p v-if="error" class="empty-state" style="margin-top: 2rem; color: #b91c1c; border-color: rgba(248,113,113,0.35);">
        {{ error }}
      </p>
    </div>
  </main>

  <BaseModal
    :open="redemptionModal.open"
    :title="
      redemptionModal.benefit
        ? `${redemptionModal.mode === 'edit' ? 'Edit' : 'Add'} redemption · ${redemptionModal.benefit.name}`
        : 'Redemption'
    "
    @close="closeRedemptionModal"
  >
    <form @submit.prevent="submitRedemption">
      <input
        v-model="redemptionModal.label"
        type="text"
        placeholder="Description"
      />
      <div class="field-group">
        <input
          v-model="redemptionModal.amount"
          type="number"
          min="0"
          step="0.01"
          placeholder="Amount"
          required
        />
        <input v-model="redemptionModal.occurred_on" type="date" required />
      </div>
      <div class="modal-actions">
        <button class="primary-button secondary" type="button" @click="closeRedemptionModal">
          Cancel
        </button>
        <button class="primary-button" type="submit">
          {{ redemptionModal.mode === 'edit' ? 'Save changes' : 'Save redemption' }}
        </button>
      </div>
    </form>
  </BaseModal>

  <BaseModal
    :open="historyModal.open"
    :title="historyModal.benefit ? `Redemption history · ${historyModal.benefit.name}` : 'Redemption history'"
    @close="closeHistoryModal"
  >
    <div v-if="historyModal.loading" class="history-loading">Loading history...</div>
    <template v-else>
      <p v-if="historyModal.windowLabel" class="history-window-label">
        Current window: {{ historyModal.windowLabel }}
      </p>
      <table v-if="historyModal.entries.length" class="history-table">
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Description</th>
            <th scope="col">Amount</th>
            <th scope="col" class="actions-column">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in historyModal.entries" :key="entry.id">
            <td>{{ new Date(entry.occurred_on).toLocaleDateString() }}</td>
            <td>{{ entry.label }}</td>
            <td>${{ Number(entry.amount).toFixed(2) }}</td>
            <td class="history-actions">
              <button
                class="icon-button ghost"
                type="button"
                title="Edit redemption"
                @click="handleEditRedemption(entry)"
              >
                <span aria-hidden="true">✏️</span>
                <span class="sr-only">Edit redemption</span>
              </button>
              <button
                class="icon-button danger"
                type="button"
                title="Delete redemption"
                @click="handleDeleteRedemption(entry)"
              >
                <span aria-hidden="true">🗑️</span>
                <span class="sr-only">Delete redemption</span>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty-state">No redemptions recorded yet.</p>
    </template>
  </BaseModal>

  <BaseModal
    :open="cardHistoryModal.open"
    :title="cardHistoryModal.card ? `Card history · ${cardHistoryModal.card.card_name}` : 'Card history'"
    @close="closeCardHistoryModal"
  >
    <div v-if="cardHistoryModal.loading" class="history-loading">Loading history...</div>
    <div v-else-if="cardHistoryModal.years.length" class="card-history-grid">
      <section v-for="year in cardHistoryModal.years" :key="year.label" class="history-card">
        <header class="history-card__header">
          <div>
            <h3 class="history-card__title">{{ year.label }}</h3>
            <p class="history-card__subtitle">{{ year.subtitle }} · {{ year.range }}</p>
          </div>
          <div class="history-card__summary">
            <span>Potential: <strong>${{ year.potential.toFixed(2) }}</strong></span>
            <span>Utilized: <strong>${{ year.utilized.toFixed(2) }}</strong></span>
            <span>Net: <strong>${{ year.net.toFixed(2) }}</strong></span>
          </div>
        </header>
        <div class="history-benefits">
          <article v-for="benefit in year.benefits" :key="benefit.id" class="history-benefit-card">
            <div class="history-benefit-header">
              <div>
                <h4 class="history-benefit-name">{{ benefit.name }}</h4>
                <p class="history-benefit-subtitle">{{ benefit.type }} · {{ benefit.frequency }}</p>
              </div>
              <span class="tag" :class="benefit.status.tone">{{ benefit.status.label }}</span>
            </div>
            <p v-if="benefit.description" class="history-benefit-description">{{ benefit.description }}</p>
            <p class="history-benefit-summary">
              <template v-if="benefit.type === 'incremental'">
                Used <strong>${{ benefit.utilized.toFixed(2) }}</strong>
                of ${{ (benefit.potential ?? 0).toFixed(2) }}
                <span v-if="benefit.remaining !== null">
                  ·
                  {{ benefit.remaining > 0
                    ? `Remaining $${benefit.remaining.toFixed(2)}`
                    : 'Complete' }}
                </span>
              </template>
              <template v-else-if="benefit.type === 'standard'">
                Value <strong>${{ benefit.potential.toFixed(2) }}</strong> · {{ benefit.status.label }}
              </template>
              <template v-else>
                Recorded <strong>${{ benefit.utilized.toFixed(2) }}</strong>
              </template>
            </p>
            <ul v-if="benefit.entries.length" class="history-benefit-entries">
              <li v-for="entry in benefit.entries" :key="entry.id">
                {{ new Date(entry.occurred_on).toLocaleDateString() }} · {{ entry.label }}
                <span>${{ Number(entry.amount).toFixed(2) }}</span>
              </li>
            </ul>
            <p v-else class="history-benefit-empty">No activity recorded.</p>
          </article>
        </div>
      </section>
    </div>
    <p v-else class="empty-state">No history available yet.</p>
  </BaseModal>

  <BaseModal
    :open="benefitWindowsModal.open"
    :title="
      benefitWindowsModal.benefit
        ? `Recurring windows · ${benefitWindowsModal.benefit.name}`
        : 'Recurring windows'
    "
    @close="closeBenefitWindowsModal"
  >
    <div v-if="benefitWindowsModal.loading" class="history-loading">Loading windows...</div>
    <div v-else-if="benefitWindowsModal.windows.length" class="window-grid">
      <article v-for="window in benefitWindowsModal.windows" :key="window.label" class="window-card">
        <h3 class="window-title">{{ window.label }}</h3>
        <p class="window-range">{{ formatCycleRange(window.start, window.end) }}</p>
        <p class="window-total">Total used: <strong>${{ window.total.toFixed(2) }}</strong></p>
        <p v-if="window.remaining !== null" class="window-remaining">
          Remaining: <strong>${{ window.remaining.toFixed(2) }}</strong>
        </p>
        <ul v-if="window.entries.length" class="history-benefit-entries">
          <li v-for="entry in window.entries" :key="entry.id">
            {{ new Date(entry.occurred_on).toLocaleDateString() }} · {{ entry.label }}
            <span>${{ Number(entry.amount).toFixed(2) }}</span>
          </li>
        </ul>
        <p v-else class="history-benefit-empty">No activity recorded.</p>
      </article>
    </div>
    <p v-else class="empty-state">No recurring windows recorded yet.</p>
  </BaseModal>
</template>

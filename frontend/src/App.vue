<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import axios from 'axios'
import BaseModal from './components/BaseModal.vue'
import CreditCardList from './components/CreditCardList.vue'

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
  fee_due_date: ''
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
  benefit: null,
  label: '',
  amount: '',
  occurred_on: ''
})

const historyModal = reactive({
  open: false,
  benefit: null,
  entries: [],
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
      fee_due_date: newCard.fee_due_date
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
  } catch (err) {
    error.value = 'Unable to add the benefit. Please try again.'
  }
}

async function handleToggleBenefit({ id, value }) {
  try {
    await axios.post(`/api/benefits/${id}/usage`, { is_used: value })
    const refreshed = await axios.get('/api/cards')
    cards.value = refreshed.data
  } catch (err) {
    error.value = 'Unable to update the benefit usage.'
  }
}

async function handleDeleteBenefit(benefitId) {
  try {
    await axios.delete(`/api/benefits/${benefitId}`)
    const refreshed = await axios.get('/api/cards')
    cards.value = refreshed.data
  } catch (err) {
    error.value = 'Unable to remove the benefit.'
  }
}

async function handleDeleteCard(cardId) {
  try {
    await axios.delete(`/api/cards/${cardId}`)
    cards.value = cards.value.filter((card) => card.id !== cardId)
  } catch (err) {
    error.value = 'Unable to delete the card.'
  }
}

function handleAddRedemption(benefit) {
  redemptionModal.open = true
  redemptionModal.benefit = benefit
  redemptionModal.label = ''
  redemptionModal.amount = ''
  const today = new Date().toISOString().slice(0, 10)
  redemptionModal.occurred_on = today
}

function closeRedemptionModal() {
  redemptionModal.open = false
  redemptionModal.benefit = null
}

async function submitRedemption() {
  if (!redemptionModal.benefit || !redemptionModal.amount) {
    return
  }
  try {
    const amount = Number(redemptionModal.amount)
    if (!Number.isFinite(amount) || amount <= 0) {
      return
    }
    await axios.post(`/api/benefits/${redemptionModal.benefit.id}/redemptions`, {
      label: redemptionModal.label || 'Redemption',
      amount,
      occurred_on: redemptionModal.occurred_on
    })
    await loadCards()
    closeRedemptionModal()
  } catch (err) {
    error.value = 'Unable to record the redemption.'
  }
}

async function handleViewHistory(benefit) {
  historyModal.open = true
  historyModal.benefit = benefit
  historyModal.entries = []
  historyModal.loading = true
  try {
    const response = await axios.get(`/api/benefits/${benefit.id}/redemptions`)
    historyModal.entries = Array.isArray(response.data) ? response.data : []
  } catch (err) {
    error.value = 'Unable to load redemption history.'
  } finally {
    historyModal.loading = false
  }
}

function closeHistoryModal() {
  historyModal.open = false
  historyModal.benefit = null
  historyModal.entries = []
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
          <div class="modal-actions">
            <button class="primary-button secondary" type="button" @click="closeCardModal">Cancel</button>
            <button class="primary-button" type="submit">Save card</button>
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
    :title="redemptionModal.benefit ? `Add redemption · ${redemptionModal.benefit.name}` : 'Add redemption'"
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
        <button class="primary-button" type="submit">Save redemption</button>
      </div>
    </form>
  </BaseModal>

  <BaseModal
    :open="historyModal.open"
    :title="historyModal.benefit ? `Redemption history · ${historyModal.benefit.name}` : 'Redemption history'"
    @close="closeHistoryModal"
  >
    <div v-if="historyModal.loading" class="history-loading">Loading history...</div>
    <table v-else-if="historyModal.entries.length" class="history-table">
      <thead>
        <tr>
          <th scope="col">Date</th>
          <th scope="col">Description</th>
          <th scope="col">Amount</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="entry in historyModal.entries" :key="entry.id">
          <td>{{ new Date(entry.occurred_on).toLocaleDateString() }}</td>
          <td>{{ entry.label }}</td>
          <td>${{ Number(entry.amount).toFixed(2) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty-state">No redemptions recorded yet.</p>
  </BaseModal>
</template>

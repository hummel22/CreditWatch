<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import BaseModal from './components/BaseModal.vue'
import CreditCardList from './components/CreditCardList.vue'

const cards = ref([])
const loading = ref(false)
const error = ref('')
const frequencies = ref(['monthly', 'quarterly', 'semiannual', 'yearly'])

const showCardModal = ref(false)

const newCard = reactive({
  card_name: '',
  company_name: '',
  last_four: '',
  account_name: '',
  annual_fee: '',
  fee_due_date: ''
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

function resetNewCard() {
  newCard.card_name = ''
  newCard.company_name = ''
  newCard.last_four = ''
  newCard.account_name = ''
  newCard.annual_fee = ''
  newCard.fee_due_date = ''
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
    cards.value.push(response.data)
    closeCardModal()
    error.value = ''
  } catch (err) {
    error.value = 'Could not create the card. Check the form data and try again.'
  }
}

async function handleAddBenefit({ cardId, payload }) {
  try {
    await axios.post(`/api/cards/${cardId}/benefits`, payload)
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

onMounted(async () => {
  await loadFrequencies()
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
          />
        </div>
      </section>

      <p v-if="error" class="empty-state" style="margin-top: 2rem; color: #b91c1c; border-color: rgba(248,113,113,0.35);">
        {{ error }}
      </p>
    </div>
  </main>
</template>

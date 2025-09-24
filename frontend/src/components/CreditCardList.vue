<script setup>
import CreditCardCard from './CreditCardCard.vue'

const props = defineProps({
  cards: {
    type: Array,
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
  'view-history'
])
</script>

<template>
  <div class="card-grid">
    <CreditCardCard
      v-for="card in cards"
      :key="card.id"
      :card="card"
      :frequencies="frequencies"
      @add-benefit="emit('add-benefit', $event)"
      @toggle-benefit="emit('toggle-benefit', $event)"
      @delete-benefit="emit('delete-benefit', $event)"
      @delete-card="emit('delete-card', $event)"
      @add-redemption="emit('add-redemption', $event)"
      @view-history="emit('view-history', $event)"
    />
  </div>
</template>

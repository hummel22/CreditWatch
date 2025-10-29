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
  },
  benefitEditRequest: {
    type: Object,
    default: null
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
  'export-template',
  'benefit-modal-closed'
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
      @update-benefit="emit('update-benefit', $event)"
      @edit-card="emit('edit-card', $event)"
      @view-card-history="emit('view-card-history', $event)"
      @view-benefit-windows="emit('view-benefit-windows', $event)"
      @export-template="emit('export-template', $event)"
      @benefit-modal-closed="emit('benefit-modal-closed')"
      :benefit-edit-request="props.benefitEditRequest"
    />
  </div>
</template>

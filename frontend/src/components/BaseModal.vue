<script setup>
import { computed } from 'vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  zIndex: {
    type: Number,
    default: 1000
  }
})

const emit = defineEmits(['close'])

const titleId = `modal-${Math.random().toString(36).slice(2, 10)}`
const labelledBy = computed(() => (props.title ? titleId : undefined))
</script>

<template>
  <teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop"
      :style="{ zIndex }"
      @click.self="emit('close')"
    >
      <div
        class="modal-panel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="labelledBy"
        tabindex="-1"
      >
        <header class="modal-header">
          <div class="modal-header__content">
            <slot name="header">
              <h2 v-if="title" :id="titleId" class="modal-title">{{ title }}</h2>
            </slot>
          </div>
          <button class="icon-button" type="button" aria-label="Close dialog" @click="emit('close')">
            ×
          </button>
        </header>
        <section class="modal-body">
          <slot />
        </section>
        <footer v-if="$slots.footer" class="modal-footer">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
}

.modal-panel {
  width: min(520px, 100%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 30px 60px rgba(15, 23, 42, 0.25);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  gap: 1rem;
}

.modal-header__content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.modal-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
  color: #0f172a;
}

.icon-button {
  background: none;
  border: none;
  color: #475569;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 999px;
  transition: background-color 0.2s ease;
}

.icon-button:hover {
  background-color: rgba(148, 163, 184, 0.2);
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem 1.5rem;
  border-top: 1px solid rgba(226, 232, 240, 0.8);
}
</style>

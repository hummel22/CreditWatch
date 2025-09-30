<script setup>
import { computed, reactive, ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'
import apiClient from '../utils/apiClient'

const bugs = ref([])
const loading = ref(false)
const error = ref('')
const viewFilter = ref('open')
const searchQuery = ref('')
const sortState = reactive({ column: 'created_at', direction: 'desc' })
const actionMessage = ref('')
const actionError = ref('')
const completingBugIds = ref([])

const newBugModal = reactive({
  open: false,
  description: '',
  loading: false,
  error: ''
})

const editBugModal = reactive({
  open: false,
  bugId: null,
  description: '',
  loading: false,
  error: ''
})

const deleteBugModal = reactive({
  open: false,
  bugId: null,
  description: '',
  loading: false,
  error: ''
})

const exportModal = reactive({
  open: false,
  loading: false,
  error: '',
  content: ''
})

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric'
})

function formatDate(value) {
  if (!value) {
    return '—'
  }
  const instance = new Date(value)
  if (Number.isNaN(instance.getTime())) {
    return '—'
  }
  return dateFormatter.format(instance)
}

function resolveErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail) && detail.length) {
    const [first] = detail
    if (typeof first === 'string' && first.trim()) {
      return first
    }
    if (first?.msg) {
      return first.msg
    }
  }
  if (err?.message && typeof err.message === 'string') {
    return err.message
  }
  return fallback
}

function clearActionFeedback() {
  actionMessage.value = ''
  actionError.value = ''
}

function isCompleting(id) {
  return completingBugIds.value.includes(id)
}

function markCompleting(id) {
  if (!completingBugIds.value.includes(id)) {
    completingBugIds.value = [...completingBugIds.value, id]
  }
}

function unmarkCompleting(id) {
  completingBugIds.value = completingBugIds.value.filter((value) => value !== id)
}

function getSortValue(bug, column) {
  if (!bug) {
    return null
  }
  if (column === 'description') {
    return (bug.description || '').toLowerCase()
  }
  if (column === 'created_at' || column === 'completed_at') {
    const instance = bug[column] ? new Date(bug[column]) : null
    return instance && !Number.isNaN(instance.getTime()) ? instance.getTime() : 0
  }
  return bug[column]
}

const processedBugs = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  let results = Array.isArray(bugs.value) ? [...bugs.value] : []
  if (query) {
    results = results.filter((bug) => bug?.description?.toLowerCase().includes(query))
  }
  results.sort((a, b) => {
    const aValue = getSortValue(a, sortState.column)
    const bValue = getSortValue(b, sortState.column)
    if (aValue === bValue) {
      return 0
    }
    if (aValue === undefined || aValue === null) {
      return sortState.direction === 'asc' ? -1 : 1
    }
    if (bValue === undefined || bValue === null) {
      return sortState.direction === 'asc' ? 1 : -1
    }
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      const comparison = aValue.localeCompare(bValue)
      return sortState.direction === 'asc' ? comparison : -comparison
    }
    const comparison = aValue < bValue ? -1 : 1
    return sortState.direction === 'asc' ? comparison : -comparison
  })
  return results
})

function sortDirectionFor(column) {
  if (sortState.column !== column) {
    return 'none'
  }
  return sortState.direction === 'asc' ? 'ascending' : 'descending'
}

function toggleSort(column) {
  if (sortState.column === column) {
    sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc'
    return
  }
  sortState.column = column
  sortState.direction = column === 'description' ? 'asc' : 'desc'
}

async function fetchBugs() {
  loading.value = true
  error.value = ''
  clearActionFeedback()
  completingBugIds.value = []
  try {
    const params = {}
    if (viewFilter.value === 'open') {
      params.completed = false
    } else if (viewFilter.value === 'completed') {
      params.completed = true
    }
    const response = await apiClient.get('/api/bugs', { params })
    bugs.value = Array.isArray(response.data) ? response.data : []
  } catch (err) {
    error.value = resolveErrorMessage(err, 'Unable to load bugs.')
    bugs.value = []
  } finally {
    loading.value = false
  }
}

watch(
  viewFilter,
  () => {
    fetchBugs()
  },
  { immediate: true }
)

function openNewBugModal() {
  newBugModal.description = ''
  newBugModal.error = ''
  newBugModal.open = true
}

function closeNewBugModal() {
  newBugModal.open = false
  newBugModal.description = ''
  newBugModal.error = ''
}

async function createBug() {
  const description = newBugModal.description.trim()
  if (!description) {
    newBugModal.error = 'Description is required.'
    return
  }
  newBugModal.loading = true
  newBugModal.error = ''
  clearActionFeedback()
  try {
    const response = await apiClient.post('/api/bugs', { description })
    const created = response.data
    if (created) {
      bugs.value = [created, ...bugs.value]
      actionMessage.value = 'Bug created successfully.'
      closeNewBugModal()
    }
  } catch (err) {
    newBugModal.error = resolveErrorMessage(err, 'Unable to create bug.')
  } finally {
    newBugModal.loading = false
  }
}

function openEditBugModal(bug) {
  if (!bug) {
    return
  }
  editBugModal.bugId = bug.id
  editBugModal.description = bug.description || ''
  editBugModal.error = ''
  editBugModal.open = true
}

function closeEditBugModal() {
  editBugModal.open = false
  editBugModal.bugId = null
  editBugModal.description = ''
  editBugModal.error = ''
}

async function updateBug() {
  const description = editBugModal.description.trim()
  if (!description) {
    editBugModal.error = 'Description is required.'
    return
  }
  if (!editBugModal.bugId) {
    return
  }
  editBugModal.loading = true
  editBugModal.error = ''
  clearActionFeedback()
  try {
    const response = await apiClient.put(`/api/bugs/${editBugModal.bugId}`, {
      description
    })
    const updated = response.data
    if (updated) {
      const index = bugs.value.findIndex((bug) => bug.id === updated.id)
      if (index !== -1) {
        const next = [...bugs.value]
        next.splice(index, 1, updated)
        bugs.value = next
      }
      actionMessage.value = 'Bug updated successfully.'
      closeEditBugModal()
    }
  } catch (err) {
    editBugModal.error = resolveErrorMessage(err, 'Unable to update bug.')
  } finally {
    editBugModal.loading = false
  }
}

function openDeleteBugModal(bug) {
  if (!bug) {
    return
  }
  deleteBugModal.bugId = bug.id
  deleteBugModal.description = bug.description || ''
  deleteBugModal.error = ''
  deleteBugModal.open = true
}

function closeDeleteBugModal() {
  deleteBugModal.open = false
  deleteBugModal.bugId = null
  deleteBugModal.description = ''
  deleteBugModal.error = ''
}

async function deleteBug() {
  if (!deleteBugModal.bugId) {
    return
  }
  deleteBugModal.loading = true
  deleteBugModal.error = ''
  clearActionFeedback()
  try {
    await apiClient.delete(`/api/bugs/${deleteBugModal.bugId}`)
    bugs.value = bugs.value.filter((bug) => bug.id !== deleteBugModal.bugId)
    actionMessage.value = 'Bug deleted successfully.'
    closeDeleteBugModal()
  } catch (err) {
    deleteBugModal.error = resolveErrorMessage(err, 'Unable to delete bug.')
  } finally {
    deleteBugModal.loading = false
  }
}

async function completeBug(bug) {
  if (!bug || bug.is_completed || isCompleting(bug.id)) {
    return
  }
  markCompleting(bug.id)
  clearActionFeedback()
  try {
    const response = await apiClient.put(`/api/bugs/${bug.id}`, { is_completed: true })
    const updated = response.data
    if (updated) {
      const index = bugs.value.findIndex((item) => item.id === updated.id)
      if (index !== -1) {
        const next = [...bugs.value]
        next.splice(index, 1, updated)
        bugs.value = next
      }
      actionMessage.value = 'Bug marked as complete. Refresh to update the list.'
    }
  } catch (err) {
    actionError.value = resolveErrorMessage(err, 'Unable to mark bug as complete.')
  } finally {
    unmarkCompleting(bug?.id)
  }
}

async function openExportModal() {
  exportModal.open = true
  exportModal.loading = true
  exportModal.error = ''
  exportModal.content = ''
  try {
    const response = await apiClient.get('/api/bugs', { params: { completed: false } })
    const items = Array.isArray(response.data) ? response.data : []
    if (!items.length) {
      exportModal.content = 'No open bugs.'
    } else {
      exportModal.content = items.map((item, index) => `${index + 1}. ${item.description}`).join('\n')
    }
  } catch (err) {
    exportModal.error = resolveErrorMessage(err, 'Unable to load open bugs.')
  } finally {
    exportModal.loading = false
  }
}

function closeExportModal() {
  exportModal.open = false
  exportModal.loading = false
  exportModal.error = ''
  exportModal.content = ''
}
</script>

<template>
  <section class="section-card bug-tracker content-constrained">
    <div class="section-header">
      <div>
        <h2 class="section-title">Bug tracker</h2>
        <p class="section-description">
          Capture and review outstanding bugs so you know what's blocking the roadmap.
        </p>
      </div>
      <div class="section-actions">
        <div class="bug-view-toggle" role="group" aria-label="Bug status filter">
          <button
            type="button"
            class="toggle-button"
            :class="{ active: viewFilter === 'open' }"
            @click="viewFilter = 'open'"
          >
            Open
          </button>
          <button
            type="button"
            class="toggle-button"
            :class="{ active: viewFilter === 'completed' }"
            @click="viewFilter = 'completed'"
          >
            Completed
          </button>
        </div>
        <input
          v-model="searchQuery"
          type="search"
          class="section-search-input"
          placeholder="Search bug descriptions"
          aria-label="Search bugs"
        />
        <button class="primary-button secondary" type="button" @click="openExportModal">
          Export open bugs
        </button>
        <button class="primary-button" type="button" @click="openNewBugModal">
          New bug
        </button>
      </div>
    </div>

    <p v-if="error" class="helper-text error-text" role="alert">{{ error }}</p>
    <p v-if="actionMessage" class="helper-text success-text" role="status">{{ actionMessage }}</p>
    <p v-if="actionError" class="helper-text error-text" role="alert">{{ actionError }}</p>

    <div v-if="loading" class="empty-state">Loading bugs...</div>
    <template v-else>
      <p v-if="!processedBugs.length" class="empty-state">
        No bugs to display. Add a new bug to get started.
      </p>
      <div v-else class="bug-table-wrapper">
        <table class="bug-table">
          <thead>
            <tr>
              <th scope="col" :aria-sort="sortDirectionFor('created_at')">
                <button type="button" class="table-sort-button" @click="toggleSort('created_at')">
                  Created
                  <span class="sort-indicator" aria-hidden="true">
                    {{ sortDirectionFor('created_at') === 'ascending' ? '▲' : sortDirectionFor('created_at') === 'descending' ? '▼' : '' }}
                  </span>
                </button>
              </th>
              <th scope="col" :aria-sort="sortDirectionFor('completed_at')">
                <button type="button" class="table-sort-button" @click="toggleSort('completed_at')">
                  Completed
                  <span class="sort-indicator" aria-hidden="true">
                    {{ sortDirectionFor('completed_at') === 'ascending' ? '▲' : sortDirectionFor('completed_at') === 'descending' ? '▼' : '' }}
                  </span>
                </button>
              </th>
              <th scope="col" :aria-sort="sortDirectionFor('description')">
                <button type="button" class="table-sort-button" @click="toggleSort('description')">
                  Description
                  <span class="sort-indicator" aria-hidden="true">
                    {{ sortDirectionFor('description') === 'ascending' ? '▲' : sortDirectionFor('description') === 'descending' ? '▼' : '' }}
                  </span>
                </button>
              </th>
              <th scope="col" class="actions-column">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="bug in processedBugs" :key="bug.id">
              <td>{{ formatDate(bug.created_at) }}</td>
              <td>{{ formatDate(bug.completed_at) }}</td>
              <td>
                <span class="bug-description" :class="{ completed: bug.is_completed }">
                  {{ bug.description }}
                </span>
              </td>
              <td class="actions-column">
                <div class="bug-actions">
                  <button
                    class="icon-button ghost"
                    type="button"
                    aria-label="Edit bug"
                    @click="openEditBugModal(bug)"
                  >
                    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8">
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M4 13.5V16h2.5l7.35-7.35-2.5-2.5L4 13.5zM12.85 5.15l2 2"
                      />
                    </svg>
                  </button>
                  <button
                    class="icon-button danger"
                    type="button"
                    aria-label="Delete bug"
                    @click="openDeleteBugModal(bug)"
                  >
                    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8">
                      <path stroke-linecap="round" d="M4 6h12" />
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M7 6V4.5A1.5 1.5 0 0 1 8.5 3h3A1.5 1.5 0 0 1 13 4.5V6m1 0v9a1.5 1.5 0 0 1-1.5 1.5h-6A1.5 1.5 0 0 1 5 15V6h9z"
                      />
                      <path stroke-linecap="round" d="M8.5 9v5M11.5 9v5" />
                    </svg>
                  </button>
                  <button
                    class="primary-button small"
                    type="button"
                    :disabled="bug.is_completed || isCompleting(bug.id)"
                    @click="completeBug(bug)"
                  >
                    {{ bug.is_completed ? 'Completed' : isCompleting(bug.id) ? 'Marking…' : 'Complete' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>

  <BaseModal :open="newBugModal.open" title="New bug" @close="closeNewBugModal">
    <form @submit.prevent="createBug">
      <label class="modal-field-label" for="new-bug-description">Description</label>
      <textarea
        id="new-bug-description"
        v-model="newBugModal.description"
        rows="4"
        placeholder="Describe the bug, reproduction steps, or expected behaviour"
        required
      ></textarea>
      <p v-if="newBugModal.error" class="helper-text error-text">{{ newBugModal.error }}</p>
      <div class="modal-actions">
        <button class="primary-button secondary" type="button" @click="closeNewBugModal">
          Cancel
        </button>
        <button class="primary-button" type="submit" :disabled="newBugModal.loading">
          {{ newBugModal.loading ? 'Saving…' : 'Create bug' }}
        </button>
      </div>
    </form>
  </BaseModal>

  <BaseModal :open="editBugModal.open" title="Edit bug" @close="closeEditBugModal">
    <form @submit.prevent="updateBug">
      <label class="modal-field-label" for="edit-bug-description">Description</label>
      <textarea
        id="edit-bug-description"
        v-model="editBugModal.description"
        rows="4"
        placeholder="Update the bug details"
        required
      ></textarea>
      <p v-if="editBugModal.error" class="helper-text error-text">{{ editBugModal.error }}</p>
      <div class="modal-actions">
        <button class="primary-button secondary" type="button" @click="closeEditBugModal">
          Cancel
        </button>
        <button class="primary-button" type="submit" :disabled="editBugModal.loading">
          {{ editBugModal.loading ? 'Saving…' : 'Save changes' }}
        </button>
      </div>
    </form>
  </BaseModal>

  <BaseModal :open="deleteBugModal.open" title="Delete bug" @close="closeDeleteBugModal">
    <p>Are you sure you want to delete this bug?</p>
    <p class="bug-delete-preview">“{{ deleteBugModal.description }}”</p>
    <p v-if="deleteBugModal.error" class="helper-text error-text">{{ deleteBugModal.error }}</p>
    <template #footer>
      <button class="primary-button secondary" type="button" @click="closeDeleteBugModal">
        Cancel
      </button>
      <button class="primary-button danger" type="button" :disabled="deleteBugModal.loading" @click="deleteBug">
        {{ deleteBugModal.loading ? 'Deleting…' : 'Delete bug' }}
      </button>
    </template>
  </BaseModal>

  <BaseModal :open="exportModal.open" title="Export open bugs" @close="closeExportModal">
    <p class="helper-text subtle-text">
      Copy the list below to share the current open bug queue with your team.
    </p>
    <div v-if="exportModal.loading" class="empty-state">Preparing export…</div>
    <p v-else-if="exportModal.error" class="helper-text error-text">{{ exportModal.error }}</p>
    <textarea
      v-else
      class="export-textarea"
      :value="exportModal.content"
      rows="10"
      readonly
    ></textarea>
    <template #footer>
      <button class="primary-button" type="button" @click="closeExportModal">Close</button>
    </template>
  </BaseModal>
</template>

<style scoped>
.bug-tracker {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-actions {
  align-items: stretch;
}

.bug-view-toggle {
  display: inline-flex;
  background: rgba(148, 163, 184, 0.15);
  border-radius: 12px;
  padding: 0.25rem;
}

.toggle-button {
  border: none;
  background: transparent;
  color: #475569;
  padding: 0.35rem 0.85rem;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.toggle-button.active {
  background: #ffffff;
  color: #1e293b;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.18);
}

.toggle-button:not(.active):hover {
  background: rgba(255, 255, 255, 0.45);
}

.bug-table-wrapper {
  overflow-x: auto;
}

.bug-table {
  width: 100%;
  border-collapse: collapse;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 16px;
  overflow: hidden;
}

.bug-table th,
.bug-table td {
  padding: 0.85rem 1rem;
  text-align: left;
  border-bottom: 1px solid rgba(226, 232, 240, 0.7);
}

.bug-table thead th {
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  color: #475569;
  background: rgba(248, 250, 252, 0.85);
}

.bug-table tbody tr:last-child td {
  border-bottom: none;
}

.table-sort-button {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: transparent;
  border: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.table-sort-button:focus-visible {
  outline: 2px solid rgba(99, 102, 241, 0.6);
  outline-offset: 2px;
}

.sort-indicator {
  font-size: 0.7rem;
}

.bug-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.bug-description {
  white-space: pre-wrap;
  line-height: 1.5;
}

.bug-description.completed {
  color: #64748b;
  text-decoration: line-through;
}

.modal-field-label {
  font-weight: 600;
  color: #1e293b;
}

.bug-delete-preview {
  font-style: italic;
  color: #475569;
}

.export-textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  padding: 0.75rem;
  background: #f8fafc;
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.actions-column {
  width: 220px;
}

@media (max-width: 800px) {
  .section-actions {
    justify-content: flex-start;
  }

  .actions-column {
    width: 100%;
  }

  .bug-actions {
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .primary-button.small {
    width: 100%;
  }
}
</style>

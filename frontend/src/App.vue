<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import apiClient from './utils/apiClient'
import BaseModal from './components/BaseModal.vue'
import BenefitCard from './components/BenefitCard.vue'
import CreditCardList from './components/CreditCardList.vue'
import {
  buildCardCycles,
  computeCardCycle,
  computeFrequencyWindows,
  isWithinRange,
  parseDate
} from './utils/dates'
import { compareBenefits } from './utils/benefits'

const cards = ref([])
const loading = ref(false)
const error = ref('')
const frequencies = ref(['monthly', 'quarterly', 'semiannual', 'yearly'])
const preconfiguredCards = ref([])

const currentView = ref('dashboard')
const navDrawerOpen = ref(false)
const navItems = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'benefits', label: 'Benefits' },
  { id: 'admin', label: 'Admin' }
]

const notificationSettings = reactive({
  id: null,
  base_url: '',
  webhook_id: '',
  default_target: '',
  enabled: true
})

const notificationSettingsMeta = reactive({
  created_at: null,
  updated_at: null
})

const notificationSettingsLoading = ref(false)
const notificationSettingsSaving = ref(false)
const notificationSettingsLoaded = ref(false)
const notificationSettingsError = ref('')
const notificationSettingsSuccess = ref('')

const notificationTests = reactive({
  custom: {
    title: '',
    message: '',
    target_override: ''
  },
  daily: {
    target_date: new Date().toISOString().slice(0, 10),
    target_override: ''
  }
})

const notificationTestsLoading = reactive({
  custom: false,
  daily: false
})

const notificationTestErrors = reactive({
  custom: '',
  daily: ''
})

const notificationTestResults = reactive({
  custom: null,
  daily: null
})

const backupSettings = reactive({
  drive_folder_id: '',
  service_account_email: '',
  is_configured: false,
  last_backup_at: null,
  last_backup_filename: '',
  last_backup_size: null,
  last_backup_error: '',
  next_backup_at: null,
  last_result_at: null,
  last_result_message: '',
  last_result_success: null
})

const backupForm = reactive({
  drive_folder_id: '',
  service_account_json: ''
})

const backupState = reactive({
  loading: false,
  saving: false,
  running: false,
  importing: false,
  error: '',
  success: '',
  runMessage: '',
  runSuccess: null,
  importError: '',
  importSuccess: ''
})

const backupImportFile = ref(null)
const backupFileInput = ref(null)

const isDashboardView = computed(() => currentView.value === 'dashboard')
const isBenefitsView = computed(() => currentView.value === 'benefits')
const isAdminView = computed(() => currentView.value === 'admin')
const isBackupConfigured = computed(() => backupSettings.is_configured)

function setView(view) {
  currentView.value = view
}

function toggleNavDrawer() {
  navDrawerOpen.value = !navDrawerOpen.value
}

function closeNavDrawer() {
  navDrawerOpen.value = false
}

function handleNavSelection(view) {
  setView(view)
  closeNavDrawer()
}

watch(currentView, () => {
  error.value = ''
  navDrawerOpen.value = false
})

watch(
  () => [
    notificationSettings.base_url,
    notificationSettings.webhook_id,
    notificationSettings.default_target,
    notificationSettings.enabled
  ],
  () => {
    if (!notificationSettingsLoaded.value) {
      return
    }
    notificationSettingsError.value = ''
    notificationSettingsSuccess.value = ''
  }
)

watch(
  () => [backupForm.drive_folder_id, backupForm.service_account_json],
  () => {
    if (!backupState.loading) {
      backupState.error = ''
      backupState.success = ''
    }
  }
)

function resetNotificationSettingsState() {
  notificationSettings.id = null
  notificationSettings.base_url = ''
  notificationSettings.webhook_id = ''
  notificationSettings.default_target = ''
  notificationSettings.enabled = true
  notificationSettingsMeta.created_at = null
  notificationSettingsMeta.updated_at = null
}

function applyNotificationSettings(data) {
  if (!data || typeof data !== 'object') {
    resetNotificationSettingsState()
    return
  }
  notificationSettings.id = data.id ?? null
  notificationSettings.base_url = data.base_url ?? ''
  notificationSettings.webhook_id = data.webhook_id ?? ''
  notificationSettings.default_target = data.default_target ?? ''
  notificationSettings.enabled = data.enabled !== false
  notificationSettingsMeta.created_at = data.created_at ?? null
  notificationSettingsMeta.updated_at = data.updated_at ?? null
}

function clearNotificationSettingsMessages() {
  notificationSettingsError.value = ''
  notificationSettingsSuccess.value = ''
}

function extractErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail) {
    return detail
  }
  if (Array.isArray(detail) && detail.length) {
    const [first] = detail
    if (typeof first === 'string' && first) {
      return first
    }
    if (first?.msg) {
      return first.msg
    }
  }
  if (err?.message) {
    return err.message
  }
  return fallback
}

function resetBackupSettings() {
  backupSettings.drive_folder_id = ''
  backupSettings.service_account_email = ''
  backupSettings.is_configured = false
  backupSettings.last_backup_at = null
  backupSettings.last_backup_filename = ''
  backupSettings.last_backup_size = null
  backupSettings.last_backup_error = ''
  backupSettings.next_backup_at = null
  backupSettings.last_result_at = null
  backupSettings.last_result_message = ''
  backupSettings.last_result_success = null
  backupForm.drive_folder_id = ''
}

function applyBackupSettings(data) {
  if (!data || typeof data !== 'object') {
    resetBackupSettings()
    return
  }
  backupSettings.drive_folder_id = data.drive_folder_id ?? ''
  backupSettings.service_account_email = data.service_account_email ?? ''
  backupSettings.is_configured = data.is_configured === true
  backupSettings.last_backup_at = data.last_backup_at ?? null
  backupSettings.last_backup_filename = data.last_backup_filename ?? ''
  backupSettings.last_backup_size =
    typeof data.last_backup_size === 'number' ? data.last_backup_size : null
  backupSettings.last_backup_error = data.last_backup_error ?? ''
  backupSettings.next_backup_at = data.next_backup_at ?? null
  backupSettings.last_result_at = data.last_result_at ?? null
  backupSettings.last_result_message = data.last_result_message ?? ''
  if (data.last_result_success === true) {
    backupSettings.last_result_success = true
  } else if (data.last_result_success === false) {
    backupSettings.last_result_success = false
  } else {
    backupSettings.last_result_success = null
  }
  backupForm.drive_folder_id = backupSettings.drive_folder_id
}

function formatBackupSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return ''
  }
  if (bytes < 1024) {
    return `${bytes} B`
  }
  const units = ['KB', 'MB', 'GB']
  let size = bytes / 1024
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

async function loadNotificationSettings() {
  notificationSettingsLoading.value = true
  notificationSettingsLoaded.value = false
  notificationSettingsSuccess.value = ''
  try {
    const response = await apiClient.get('/api/admin/notifications/settings')
    if (response.data) {
      applyNotificationSettings(response.data)
      notificationSettingsError.value = ''
    } else {
      resetNotificationSettingsState()
      notificationSettingsError.value = ''
    }
  } catch (err) {
    resetNotificationSettingsState()
    notificationSettingsError.value =
      'Unable to load notification settings. Enter new details to configure notifications.'
  } finally {
    notificationSettingsLoading.value = false
    notificationSettingsLoaded.value = true
  }
}

async function loadBackupSettings() {
  backupState.loading = true
  backupState.error = ''
  try {
    const response = await apiClient.get('/api/admin/backups/settings')
    applyBackupSettings(response.data)
  } catch (err) {
    resetBackupSettings()
    backupState.error = extractErrorMessage(err, 'Unable to load backup settings.')
  } finally {
    backupState.loading = false
  }
}

async function saveNotificationSettings() {
  clearNotificationSettingsMessages()
  const baseUrl = notificationSettings.base_url.trim()
  const webhookId = notificationSettings.webhook_id.trim()
  const defaultTarget = notificationSettings.default_target.trim()
  if (!baseUrl || !webhookId) {
    notificationSettingsError.value =
      'Provide a Home Assistant URL and webhook ID before saving.'
    return
  }
  notificationSettingsSaving.value = true
  try {
    const payload = {
      base_url: baseUrl,
      webhook_id: webhookId,
      enabled: Boolean(notificationSettings.enabled)
    }
    payload.default_target = defaultTarget ? defaultTarget : null
    const response = await apiClient.put('/api/admin/notifications/settings', payload)
    applyNotificationSettings(response.data)
    notificationSettingsSuccess.value = 'Notification settings saved.'
  } catch (err) {
    notificationSettingsError.value = extractErrorMessage(
      err,
      'Unable to save notification settings.'
    )
  } finally {
    notificationSettingsSaving.value = false
  }
}

async function saveBackupSettings() {
  backupState.error = ''
  backupState.success = ''
  const folderId = backupForm.drive_folder_id.trim()
  const credentials = backupForm.service_account_json.trim()
  if (!folderId) {
    backupState.error = 'Provide the Google Drive folder ID before saving.'
    return
  }
  if (!isBackupConfigured.value && !credentials) {
    backupState.error = 'Paste the service account JSON credentials to configure backups.'
    return
  }
  const payload = { drive_folder_id: folderId }
  let method = 'patch'
  if (!isBackupConfigured.value) {
    payload.service_account_json = credentials
    method = 'put'
  } else if (credentials) {
    payload.service_account_json = credentials
  }
  backupState.saving = true
  try {
    const response =
      method === 'put'
        ? await apiClient.put('/api/admin/backups/settings', payload)
        : await apiClient.patch('/api/admin/backups/settings', payload)
    applyBackupSettings(response.data)
    backupForm.service_account_json = ''
    backupState.success = 'Backup settings saved.'
  } catch (err) {
    backupState.error = extractErrorMessage(err, 'Unable to save backup settings.')
  } finally {
    backupState.saving = false
  }
}

async function runBackupNow() {
  backupState.runMessage = ''
  backupState.runSuccess = null
  backupState.error = ''
  if (!isBackupConfigured.value) {
    backupState.error = 'Configure Google Drive backups before running a backup.'
    return
  }
  backupState.running = true
  try {
    const response = await apiClient.post('/api/admin/backups/run')
    const data = response.data || {}
    backupState.runMessage = data.message || 'Backup task completed.'
    backupState.runSuccess = data.success !== false
    await loadBackupSettings()
  } catch (err) {
    backupState.runMessage = extractErrorMessage(err, 'Unable to run the backup now.')
    backupState.runSuccess = false
  } finally {
    backupState.running = false
  }
}

function handleBackupFileChange(event) {
  const fileList = event?.target?.files || []
  backupImportFile.value = fileList.length ? fileList[0] : null
  backupState.importError = ''
  backupState.importSuccess = ''
}

async function importBackupDatabase() {
  backupState.importError = ''
  backupState.importSuccess = ''
  if (!backupImportFile.value) {
    backupState.importError = 'Select a .db file to import.'
    return
  }
  const formData = new FormData()
  formData.append('file', backupImportFile.value)
  backupState.importing = true
  try {
    await apiClient.post('/api/admin/backups/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    backupState.importSuccess = 'Database imported successfully.'
    backupImportFile.value = null
    if (backupFileInput.value) {
      backupFileInput.value.value = ''
    }
    await Promise.all([
      loadCards(),
      loadPreconfiguredCards(),
      loadNotificationSettings(),
      loadBackupSettings()
    ])
  } catch (err) {
    backupState.importError = extractErrorMessage(err, 'Unable to import the database file.')
  } finally {
    backupState.importing = false
  }
}

function resetNotificationTestState(kind) {
  if (!(kind in notificationTestErrors) || !(kind in notificationTestResults)) {
    return
  }
  notificationTestErrors[kind] = ''
  notificationTestResults[kind] = null
}

function resolveNotificationCategories(result) {
  if (!result || typeof result !== 'object' || !result.categories) {
    return []
  }
  return Object.entries(result.categories).filter(([, items]) =>
    Array.isArray(items) && items.length
  )
}

function formatNotificationCategoryLabel(key) {
  if (!key) {
    return ''
  }
  return key
    .toString()
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatNotificationDate(value) {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return date.toLocaleDateString()
}

function formatNotificationTimestamp(value) {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return date.toLocaleString()
}

async function sendCustomNotificationTest() {
  resetNotificationTestState('custom')
  const message = notificationTests.custom.message.trim()
  const title = notificationTests.custom.title.trim()
  const target = notificationTests.custom.target_override.trim()
  if (!message) {
    notificationTestErrors.custom = 'Enter a message to send a notification.'
    return
  }
  notificationTestsLoading.custom = true
  try {
    const payload = { message }
    if (title) {
      payload.title = title
    }
    if (target) {
      payload.target_override = target
    }
    const response = await apiClient.post('/api/admin/notifications/test/custom', payload)
    notificationTestResults.custom = response.data
  } catch (err) {
    notificationTestErrors.custom = extractErrorMessage(
      err,
      'Unable to send the custom notification.'
    )
  } finally {
    notificationTestsLoading.custom = false
  }
}

async function sendDailyNotificationTest() {
  resetNotificationTestState('daily')
  const targetDate = notificationTests.daily.target_date
  const override = notificationTests.daily.target_override.trim()
  if (!targetDate) {
    notificationTestErrors.daily = 'Select a date to simulate for the daily notification.'
    return
  }
  notificationTestsLoading.daily = true
  try {
    const payload = { target_date: targetDate }
    if (override) {
      payload.target_override = override
    }
    const response = await apiClient.post('/api/admin/notifications/test/daily', payload)
    notificationTestResults.daily = response.data
  } catch (err) {
    notificationTestErrors.daily = extractErrorMessage(
      err,
      'Unable to send the daily notification test.'
    )
  } finally {
    notificationTestsLoading.daily = false
  }
}

function normaliseCard(card) {
  if (!card || typeof card !== 'object') {
    return card
  }
  const normalized = {
    ...card,
    year_tracking_mode:
      card.year_tracking_mode === 'anniversary' ? 'anniversary' : 'calendar'
  }
  if (Array.isArray(card.benefits)) {
    normalized.benefits = card.benefits.map((benefit) => ({ ...benefit }))
  }
  return normalized
}

function normaliseCards(collection) {
  if (!Array.isArray(collection)) {
    return []
  }
  return collection.map((card) => normaliseCard(card))
}

function resolveDefaultFrequency() {
  return frequencies.value[0] || 'monthly'
}

function createAdminBenefit() {
  return {
    name: '',
    description: '',
    frequency: resolveDefaultFrequency(),
    type: 'standard',
    value: '',
    expected_value: '',
    useCustomValues: false,
    window_values: []
  }
}

const adminModal = reactive({
  open: false,
  mode: 'create',
  originalSlug: '',
  form: {
    slug: '',
    card_type: '',
    company_name: '',
    annual_fee: '',
    benefits: []
  }
})

const adminSaving = ref(false)

const benefitTypeDescriptions = {
  standard: 'Standard benefits are toggled once per cycle.',
  incremental: 'Incremental benefits accrue value as you log redemptions toward a goal.',
  cumulative: 'Cumulative benefits build value as you add redemptions.'
}

const WINDOW_COUNTS = {
  monthly: 12,
  quarterly: 4,
  semiannual: 2
}

const MONTH_LABELS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December'
]

function supportsCustomWindowValues(frequency) {
  return Boolean(WINDOW_COUNTS[frequency])
}

function resolveBenefitWindowCount(benefit) {
  if (!benefit) {
    return 1
  }
  if (typeof benefit.cycle_window_count === 'number' && benefit.cycle_window_count > 0) {
    return benefit.cycle_window_count
  }
  return supportsCustomWindowValues(benefit.frequency)
    ? WINDOW_COUNTS[benefit.frequency]
    : 1
}

function getWindowValueForIndex(benefit, index) {
  if (!benefit || typeof index !== 'number' || index < 1) {
    const base = Number(benefit?.value ?? 0)
    return Number.isFinite(base) ? base : 0
  }
  if (Array.isArray(benefit.window_values) && benefit.window_values.length >= index) {
    const value = Number(benefit.window_values[index - 1] ?? 0)
    return Number.isFinite(value) ? value : 0
  }
  const base = Number(benefit?.value ?? 0)
  return Number.isFinite(base) ? base : 0
}

function getCycleTargetValue(benefit) {
  if (!benefit) {
    return 0
  }
  if (benefit.cycle_target_value != null) {
    const parsed = Number(benefit.cycle_target_value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  if (benefit.type === 'cumulative') {
    const expected = Number(benefit.expected_value ?? 0)
    if (Number.isFinite(expected) && expected > 0) {
      return expected
    }
    const cycleTotal = Number(benefit.cycle_redemption_total ?? 0)
    return Number.isFinite(cycleTotal) ? cycleTotal : 0
  }
  const windowCount = resolveBenefitWindowCount(benefit)
  if (Array.isArray(benefit.window_values) && benefit.window_values.length) {
    return benefit.window_values.slice(0, windowCount).reduce((acc, value) => {
      const parsed = Number(value ?? 0)
      return acc + (Number.isFinite(parsed) ? parsed : 0)
    }, 0)
  }
  const base = Number(benefit.value ?? 0)
  if (!Number.isFinite(base)) {
    return 0
  }
  return base * windowCount
}

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

const benefitsCollection = computed(() => {
  const entries = []
  for (const card of cards.value) {
    if (!Array.isArray(card.benefits)) {
      continue
    }
    for (const benefit of card.benefits) {
      entries.push({ card, benefit })
    }
  }
  return entries.sort((a, b) => compareBenefits(a.benefit, b.benefit))
})

async function loadFrequencies() {
  try {
    const response = await apiClient.get('/api/frequencies')
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
    const response = await apiClient.get('/api/cards')
    cards.value = normaliseCards(response.data)
  } catch (err) {
    error.value = 'Unable to load cards. Ensure the backend is running.'
  } finally {
    loading.value = false
  }
}

async function loadPreconfiguredCards() {
  try {
    const response = await apiClient.get('/api/preconfigured/cards')
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

function resetAdminModal() {
  adminModal.originalSlug = ''
  adminModal.form.slug = ''
  adminModal.form.card_type = ''
  adminModal.form.company_name = ''
  adminModal.form.annual_fee = ''
  adminModal.form.benefits = []
}

function normaliseAdminBenefitWindows(benefit) {
  if (!benefit) {
    return
  }
  if (!supportsCustomWindowValues(benefit.frequency) || benefit.type === 'cumulative') {
    benefit.useCustomValues = false
    benefit.window_values = []
    return
  }
  if (!benefit.useCustomValues) {
    benefit.window_values = []
    return
  }
  const count = WINDOW_COUNTS[benefit.frequency] || 1
  const values = Array.isArray(benefit.window_values) ? [...benefit.window_values] : []
  const trimmed = values.slice(0, count)
  const baseValue =
    benefit.value !== '' && benefit.value != null ? benefit.value.toString() : ''
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
  benefit.window_values = trimmed
}

function handleAdminBenefitFrequencyChange(benefit) {
  normaliseAdminBenefitWindows(benefit)
}

function toggleAdminBenefitCustomValues(benefit, value) {
  benefit.useCustomValues = value
  normaliseAdminBenefitWindows(benefit)
}

function getBenefitValuePlaceholder(benefit) {
  if (!benefit || benefit.type === 'cumulative') {
    return 'Value'
  }
  if (!supportsCustomWindowValues(benefit.frequency)) {
    return benefit.frequency === 'yearly' ? 'Value per year' : 'Value'
  }
  if (benefit.frequency === 'monthly') {
    return 'Value per month'
  }
  if (benefit.frequency === 'quarterly') {
    return 'Value per quarter'
  }
  if (benefit.frequency === 'semiannual') {
    return 'Value per half-year'
  }
  return 'Value per window'
}

function handleAdminBenefitValueInput(benefit) {
  if (
    !benefit ||
    benefit.type === 'cumulative' ||
    !benefit.useCustomValues ||
    !supportsCustomWindowValues(benefit.frequency)
  ) {
    return
  }
  normaliseAdminBenefitWindows(benefit)
}

function getAdminWindowOptions(frequency) {
  if (frequency === 'monthly') {
    return MONTH_LABELS
  }
  if (frequency === 'quarterly') {
    return ['Quarter 1', 'Quarter 2', 'Quarter 3', 'Quarter 4']
  }
  if (frequency === 'semiannual') {
    return ['First half', 'Second half']
  }
  return []
}

function openAdminCreateModal() {
  adminModal.mode = 'create'
  resetAdminModal()
  adminModal.form.benefits.push(createAdminBenefit())
  error.value = ''
  adminModal.open = true
}

function openAdminEditModal(card) {
  adminModal.mode = 'edit'
  adminModal.originalSlug = card.slug
  adminModal.form.slug = card.slug
  adminModal.form.card_type = card.card_type
  adminModal.form.company_name = card.company_name
  adminModal.form.annual_fee = card.annual_fee.toString()
  adminModal.form.benefits = card.benefits.map((benefit) => ({
    name: benefit.name,
    description: benefit.description || '',
    frequency: benefit.frequency,
    type: benefit.type,
    value:
      benefit.type === 'cumulative'
        ? ''
        : benefit.value != null
          ? benefit.value.toString()
          : '',
    expected_value:
      benefit.type === 'cumulative' && benefit.expected_value != null
        ? benefit.expected_value.toString()
        : '',
    useCustomValues:
      Array.isArray(benefit.window_values) && benefit.window_values.length > 0,
    window_values: Array.isArray(benefit.window_values)
      ? benefit.window_values.map((value) => value.toString())
      : []
  }))
  if (!adminModal.form.benefits.length) {
    adminModal.form.benefits.push(createAdminBenefit())
  }
  for (const benefit of adminModal.form.benefits) {
    normaliseAdminBenefitWindows(benefit)
  }
  error.value = ''
  adminModal.open = true
}

function closeAdminModal() {
  adminModal.open = false
  adminSaving.value = false
  resetAdminModal()
}

function addAdminBenefit() {
  adminModal.form.benefits.push(createAdminBenefit())
}

function removeAdminBenefit(index) {
  adminModal.form.benefits.splice(index, 1)
  if (!adminModal.form.benefits.length) {
    adminModal.form.benefits.push(createAdminBenefit())
  }
}

function handleAdminBenefitTypeChange(benefit) {
  if (benefit.type === 'cumulative') {
    benefit.value = ''
    benefit.useCustomValues = false
    benefit.window_values = []
  } else {
    benefit.expected_value = ''
    normaliseAdminBenefitWindows(benefit)
  }
}

async function submitAdminCard() {
  if (!adminModal.form.card_type || !adminModal.form.company_name) {
    error.value = 'Please complete the card details.'
    return
  }
  adminSaving.value = true
  try {
    const payload = {
      slug: adminModal.form.slug || undefined,
      card_type: adminModal.form.card_type,
      company_name: adminModal.form.company_name,
      annual_fee: Number(adminModal.form.annual_fee || 0),
      benefits: adminModal.form.benefits.map((benefit) => {
        const base = {
          name: benefit.name,
          description: benefit.description || null,
          frequency: benefit.frequency,
          type: benefit.type
        }
        if (benefit.type !== 'cumulative') {
          base.value = Number(benefit.value || 0)
          if (benefit.useCustomValues && supportsCustomWindowValues(benefit.frequency)) {
            const count = WINDOW_COUNTS[benefit.frequency] || 0
            const windowValues = Array.isArray(benefit.window_values)
              ? benefit.window_values.slice(0, count).map((value) => Number(value || 0))
              : []
            if (windowValues.length) {
              base.window_values = windowValues
            }
          }
        } else {
          const rawExpected =
            typeof benefit.expected_value === 'string'
              ? benefit.expected_value.trim()
              : benefit.expected_value
          if (rawExpected === '' || rawExpected === null || rawExpected === undefined) {
            base.expected_value = null
          } else {
            const parsed = Number(rawExpected)
            base.expected_value = Number.isNaN(parsed) ? null : parsed
          }
        }
        return base
      })
    }
    if (adminModal.mode === 'edit') {
      await apiClient.put(
        `/api/admin/preconfigured/cards/${encodeURIComponent(adminModal.originalSlug)}`,
        payload
      )
    } else {
      await apiClient.post('/api/admin/preconfigured/cards', payload)
    }
    await loadPreconfiguredCards()
    closeAdminModal()
    error.value = ''
  } catch (err) {
    error.value = 'Unable to save the preconfigured card.'
  } finally {
    adminSaving.value = false
  }
}

async function handleDeletePreconfiguredCard(slug) {
  try {
    await apiClient.delete(`/api/admin/preconfigured/cards/${encodeURIComponent(slug)}`)
    await loadPreconfiguredCards()
  } catch (err) {
    error.value = 'Unable to delete the preconfigured card.'
  }
}

function closeCardModal() {
  showCardModal.value = false
  resetNewCard()
}

async function handleCreateCard() {
  const trimmedLastDigits = newCard.last_four.trim()
  if (
    !newCard.card_name ||
    !newCard.company_name ||
    !/^\d{4,5}$/.test(trimmedLastDigits)
  ) {
    error.value = 'Please provide a card name, company, and the last four or five digits.'
    return
  }
  try {
    const payload = {
      card_name: newCard.card_name,
      company_name: newCard.company_name,
      last_four: trimmedLastDigits,
      account_name: newCard.account_name,
      annual_fee: Number(newCard.annual_fee || 0),
      fee_due_date: newCard.fee_due_date,
      year_tracking_mode: newCard.year_tracking_mode
    }
    const response = await apiClient.post('/api/cards', payload)
    const createdCard = normaliseCard(response.data)
    const template = selectedTemplate.value
    if (template) {
      for (const benefit of template.benefits) {
        const benefitPayload = {
          name: benefit.name,
          description: benefit.description || null,
          frequency: benefit.frequency,
          type: benefit.type,
          expiration_date: null
        }
        if (benefit.type === 'cumulative') {
          if (benefit.expected_value != null) {
            benefitPayload.expected_value = benefit.expected_value
          }
        } else {
          benefitPayload.value = benefit.value
          if (
            Array.isArray(benefit.window_values) &&
            benefit.window_values.length &&
            supportsCustomWindowValues(benefit.frequency)
          ) {
            benefitPayload.window_values = benefit.window_values
          }
        }
        if (benefitPayload.value === undefined) {
          delete benefitPayload.value
        }
        await apiClient.post(`/api/cards/${response.data.id}/benefits`, benefitPayload)
      }
      await loadCards()
    } else {
      cards.value.push(createdCard)
    }
    newCard.last_four = trimmedLastDigits
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
    await apiClient.post(`/api/cards/${cardId}/benefits`, body)
    const refreshed = await apiClient.get('/api/cards')
    cards.value = normaliseCards(refreshed.data)
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to add the benefit. Please try again.'
  }
}

async function handleToggleBenefit({ id, value }) {
  try {
    await apiClient.post(`/api/benefits/${id}/usage`, { is_used: value })
    const refreshed = await apiClient.get('/api/cards')
    cards.value = normaliseCards(refreshed.data)
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to update the benefit usage.'
  }
}

async function handleDeleteBenefit(benefitId) {
  try {
    await apiClient.delete(`/api/benefits/${benefitId}`)
    const refreshed = await apiClient.get('/api/cards')
    cards.value = normaliseCards(refreshed.data)
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to remove the benefit.'
  }
}

async function handleDeleteCard(cardId) {
  try {
    await apiClient.delete(`/api/cards/${cardId}`)
    await loadCards()
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to delete the card.'
  }
}

function resolveDefaultRedemptionAmount(benefit) {
  if (!benefit || benefit.type === 'cumulative') {
    return ''
  }
  const baseValue = Number(
    benefit.current_window_value ?? getWindowValueForIndex(benefit, benefit.current_window_index ?? 1)
  )
  if (!Number.isFinite(baseValue) || baseValue <= 0) {
    return ''
  }
  const windowTotal = Number(
    benefit.current_window_total ?? benefit.cycle_redemption_total ?? 0
  )
  const remaining = Math.max(baseValue - windowTotal, 0)
  const suggested = remaining > 0 ? remaining : baseValue
  return suggested > 0 ? suggested.toFixed(2) : ''
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
  redemptionModal.amount = resolveDefaultRedemptionAmount(trackedBenefit)
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
      await apiClient.put(`/api/redemptions/${redemptionModal.redemptionId}`, body)
    } else {
      await apiClient.post(`/api/benefits/${redemptionModal.benefitId}/redemptions`, body)
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
    await apiClient.delete(`/api/redemptions/${entry.id}`)
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
    await apiClient.put(`/api/benefits/${benefitId}`, body)
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
  const trimmedLastDigits = editCardModal.form.last_four.trim()
  if (!/^\d{4,5}$/.test(trimmedLastDigits)) {
    error.value = 'Please provide the last four or five digits.'
    return
  }
  try {
    const payload = {
      card_name: editCardModal.form.card_name,
      company_name: editCardModal.form.company_name,
      last_four: trimmedLastDigits,
      account_name: editCardModal.form.account_name,
      annual_fee: Number(editCardModal.form.annual_fee || 0),
      fee_due_date: editCardModal.form.fee_due_date,
      year_tracking_mode: editCardModal.form.year_tracking_mode
    }
    await apiClient.put(`/api/cards/${editCardModal.cardId}`, payload)
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
  const response = await apiClient.get(`/api/benefits/${benefitId}/redemptions`)
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
    const windowIndex = typeof window.index === 'number' ? window.index : windows.indexOf(window) + 1
    const targetValue = getWindowValueForIndex(benefit, windowIndex)
    const remaining =
      benefit.type === 'incremental'
        ? Math.max(targetValue - total, 0)
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
        potential = getCycleTargetValue(benefit)
        const used = Boolean(
          benefit.used_at && isWithinRange(benefit.used_at, cycle.start, cycle.end)
        )
        utilized = used ? potential : 0
        statusLabel = used ? 'Utilized' : 'Available'
        statusTone = used ? 'success' : 'warning'
      } else if (benefit.type === 'incremental') {
        potential = getCycleTargetValue(benefit)
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
        potential = getCycleTargetValue(benefit)
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
  await loadBackupSettings()
  await loadNotificationSettings()
  await loadFrequencies()
  await loadPreconfiguredCards()
  await loadCards()
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <div class="header-bar">
          <div class="header-left">
            <button
              class="icon-button ghost nav-toggle"
              type="button"
              :aria-expanded="navDrawerOpen"
              aria-controls="primary-navigation"
              @click="toggleNavDrawer"
            >
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path stroke-linecap="round" d="M4 6h12M4 10h12M4 14h12" />
              </svg>
              <span class="sr-only">Toggle navigation</span>
            </button>
            <span class="header-logo">CreditWatch</span>
          </div>
          <div class="header-actions">
            <button
              v-if="!isAdminView"
              class="primary-button"
              type="button"
              @click="showCardModal = true"
            >
              New card
            </button>
            <button v-else class="primary-button" type="button" @click="openAdminCreateModal">
              New template
            </button>
          </div>
        </div>
      </div>
    </header>
    <div v-if="navDrawerOpen" class="nav-drawer-backdrop" @click="closeNavDrawer" aria-hidden="true"></div>
    <aside
      id="primary-navigation"
      class="nav-drawer"
      :class="{ open: navDrawerOpen }"
      aria-label="Primary navigation"
    >
      <div class="nav-drawer__header">
        <span class="nav-drawer__title">Menu</span>
        <button class="icon-button ghost" type="button" @click="closeNavDrawer">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path stroke-linecap="round" d="M5 5l10 10M15 5l-10 10" />
          </svg>
          <span class="sr-only">Close navigation</span>
        </button>
      </div>
      <nav class="nav-drawer__nav">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="nav-button"
          type="button"
          :class="{ active: currentView === item.id }"
          @click="handleNavSelection(item.id)"
        >
          {{ item.label }}
        </button>
      </nav>
    </aside>
    <main class="app-main">
      <section class="hero content-constrained">
        <p class="page-subtitle hero-tagline">
          Track every card, benefit, and annual fee so you always know if your cards pay for themselves.
        </p>
      </section>

      <template v-if="isDashboardView">
        <section class="section-card content-constrained">
          <h2 class="section-title">Portfolio overview</h2>
          <div class="summary-row">
            <span>Total annual fees: <strong>${{ totals.annualFees.toFixed(2) }}</strong></span>
            <span>Total potential: <strong>${{ totals.potential.toFixed(2) }}</strong></span>
            <span>Total utilized: <strong>${{ totals.utilized.toFixed(2) }}</strong></span>
            <span>Net position: <strong>${{ totals.net.toFixed(2) }}</strong></span>
          </div>
        </section>

        <section class="cards-section">
          <div class="content-constrained">
            <h2 class="section-title">Your cards</h2>
            <p v-if="loading" class="empty-state">Loading your cards...</p>
            <p v-else-if="!cards.length" class="empty-state">
              No cards yet. Add your first credit card to begin tracking benefits.
            </p>
          </div>
          <div v-if="!loading && cards.length" class="cards-grid-wrapper">
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
      </template>

      <template v-else-if="isBenefitsView">
        <section class="cards-section">
          <div class="content-constrained">
            <div class="section-header">
              <div>
                <h2 class="section-title">All benefits</h2>
                <p class="section-description">
                  Review every benefit across your cards in a single view.
                </p>
              </div>
            </div>
            <p v-if="loading" class="empty-state">Loading benefits...</p>
            <p v-else-if="!benefitsCollection.length" class="empty-state">
              No benefits to display yet. Add benefits to your cards to see them here.
            </p>
          </div>
          <div
            v-if="!loading && benefitsCollection.length"
            class="benefits-collection content-constrained"
          >
            <div class="benefits-collection-grid">
              <BenefitCard
                v-for="entry in benefitsCollection"
                :key="entry.benefit.id"
                :benefit="entry.benefit"
                :card-context="{ name: entry.card.card_name, company: entry.card.company_name }"
                :show-edit="false"
                @toggle="(value) => handleToggleBenefit({ id: entry.benefit.id, value })"
                @delete="() => handleDeleteBenefit(entry.benefit.id)"
                @add-redemption="() => handleAddRedemption({ card: entry.card, benefit: entry.benefit })"
                @view-history="() => handleViewHistory({ card: entry.card, benefit: entry.benefit })"
                @view-windows="() => handleViewBenefitWindows({ card: entry.card, benefit: entry.benefit })"
              />
            </div>
          </div>
        </section>
      </template>

      <template v-else>
        <section class="section-card admin-board content-constrained">
          <div class="section-header">
            <div>
              <h2 class="section-title">Database backups</h2>
              <p class="section-description">
                Configure automatic Google Drive backups and restore from an archived database file.
              </p>
            </div>
          </div>
          <div v-if="backupState.loading" class="empty-state">Loading backup settings...</div>
          <template v-else>
            <form class="admin-settings-form backup-settings-form" @submit.prevent="saveBackupSettings">
              <div class="field-group">
                <input
                  v-model="backupForm.drive_folder_id"
                  type="text"
                  placeholder="Google Drive folder ID"
                  required
                />
              </div>
              <textarea
                v-model="backupForm.service_account_json"
                rows="4"
                placeholder="Service account JSON (paste to set or rotate credentials)"
              ></textarea>
              <p class="helper-text subtle-text">
                Use a service account with access to the destination folder. Backups run one hour after the most recent change.
              </p>
              <div class="backup-settings-feedback">
                <p v-if="backupState.error" class="helper-text error-text">{{ backupState.error }}</p>
                <p v-else-if="backupState.success" class="helper-text success-text">{{ backupState.success }}</p>
              </div>
              <div class="backup-settings-actions">
                <button class="primary-button" type="submit" :disabled="backupState.saving">
                  {{ backupState.saving ? 'Saving…' : 'Save backup settings' }}
                </button>
              </div>
            </form>

            <div class="backup-status-grid">
              <div class="backup-status-card">
                <h3 class="backup-status-title">Configuration</h3>
                <p class="backup-status-line">
                  Status
                  <span class="tag" :class="isBackupConfigured ? 'success' : 'warning'">
                    {{ isBackupConfigured ? 'Configured' : 'Not configured' }}
                  </span>
                </p>
                <p class="backup-status-line">
                  Service account ·
                  <span class="backup-status-value">
                    {{ backupSettings.service_account_email || 'Not set' }}
                  </span>
                </p>
              </div>
              <div class="backup-status-card">
                <h3 class="backup-status-title">Schedule</h3>
                <p v-if="backupSettings.next_backup_at" class="backup-status-line">
                  Next backup {{ formatNotificationTimestamp(backupSettings.next_backup_at) }}
                </p>
                <p v-else-if="isBackupConfigured" class="backup-status-line subtle-text">
                  Waiting for recent changes before scheduling.
                </p>
                <p v-else class="backup-status-line subtle-text">
                  Configure backups to enable scheduling.
                </p>
              </div>
              <div class="backup-status-card">
                <h3 class="backup-status-title">Last backup</h3>
                <p v-if="backupSettings.last_backup_at" class="backup-status-line">
                  Saved {{ formatNotificationTimestamp(backupSettings.last_backup_at) }}
                </p>
                <p v-else class="backup-status-line subtle-text">No backups have been created yet.</p>
                <p v-if="backupSettings.last_backup_filename" class="backup-status-line">
                  File · <span class="backup-status-value">{{ backupSettings.last_backup_filename }}</span>
                </p>
                <p v-if="backupSettings.last_backup_size !== null" class="backup-status-line">
                  Size · <span class="backup-status-value">{{ formatBackupSize(backupSettings.last_backup_size) }}</span>
                </p>
                <p v-if="backupSettings.last_backup_error" class="helper-text error-text">
                  {{ backupSettings.last_backup_error }}
                </p>
              </div>
              <div class="backup-status-card">
                <h3 class="backup-status-title">Recent run</h3>
                <p v-if="backupSettings.last_result_at" class="backup-status-line">
                  {{ backupSettings.last_result_success === false ? 'Failed' : 'Completed' }}
                  {{ formatNotificationTimestamp(backupSettings.last_result_at) }}
                </p>
                <p v-if="backupSettings.last_result_message" class="backup-status-line">
                  {{ backupSettings.last_result_message }}
                </p>
                <p v-else class="backup-status-line subtle-text">No backup activity yet.</p>
              </div>
            </div>

            <div class="backup-actions-row">
              <button
                class="primary-button secondary"
                type="button"
                :disabled="backupState.running || !isBackupConfigured"
                @click="runBackupNow"
              >
                {{ backupState.running ? 'Running…' : 'Run backup now' }}
              </button>
              <p
                v-if="backupState.runMessage"
                :class="['helper-text', backupState.runSuccess === false ? 'error-text' : 'success-text']"
              >
                {{ backupState.runMessage }}
              </p>
            </div>

            <div class="backup-import-card">
              <h3 class="backup-import-title">Import database</h3>
              <p class="helper-text subtle-text">
                Upload a SQLite <code>.db</code> file to replace the current database. A backup will be scheduled automatically after import.
              </p>
              <div class="backup-import-controls">
                <input
                  ref="backupFileInput"
                  type="file"
                  accept=".db"
                  @change="handleBackupFileChange"
                />
                <button
                  class="primary-button secondary"
                  type="button"
                  :disabled="backupState.importing"
                  @click="importBackupDatabase"
                >
                  {{ backupState.importing ? 'Importing…' : 'Import database' }}
                </button>
              </div>
              <p v-if="backupState.importError" class="helper-text error-text">
                {{ backupState.importError }}
              </p>
              <p v-else-if="backupState.importSuccess" class="helper-text success-text">
                {{ backupState.importSuccess }}
              </p>
            </div>
          </template>
        </section>

        <section class="section-card admin-board content-constrained">
          <div class="section-header">
            <div>
              <h2 class="section-title">Home Assistant notifications</h2>
              <p class="section-description">
                Configure the webhook connection used to deliver reminder notifications.
              </p>
            </div>
          </div>
          <div v-if="notificationSettingsLoading" class="empty-state">
            Loading notification settings...
          </div>
          <template v-else>
            <form class="admin-settings-form" @submit.prevent="saveNotificationSettings">
              <div class="field-group">
                <input
                  v-model="notificationSettings.base_url"
                  type="url"
                  placeholder="Home Assistant URL (e.g., https://homeassistant.local:8123)"
                  required
                />
                <input
                  v-model="notificationSettings.webhook_id"
                  type="text"
                  placeholder="Webhook ID"
                  required
                />
              </div>
              <div class="field-group notification-field-group">
                <input
                  v-model="notificationSettings.default_target"
                  type="text"
                  placeholder="Default notification target (optional)"
                />
                <div class="notification-toggle">
                  <label class="checkbox-option">
                    <input v-model="notificationSettings.enabled" type="checkbox" />
                    <span>Enable notifications</span>
                  </label>
                </div>
              </div>
              <div class="notification-meta">
                <p
                  v-if="notificationSettingsLoaded && !notificationSettings.enabled"
                  class="helper-text warning-text"
                >
                  Notifications are currently disabled. Tests will still return the simulated result.
                </p>
                <p v-if="notificationSettingsMeta.updated_at" class="helper-text subtle-text">
                  Last updated {{ formatNotificationTimestamp(notificationSettingsMeta.updated_at) }}
                </p>
              </div>
              <div class="admin-settings-actions">
                <div class="notification-feedback">
                  <p v-if="notificationSettingsError" class="helper-text error-text">
                    {{ notificationSettingsError }}
                  </p>
                  <p v-else-if="notificationSettingsSuccess" class="helper-text success-text">
                    {{ notificationSettingsSuccess }}
                  </p>
                </div>
                <button class="primary-button" type="submit" :disabled="notificationSettingsSaving">
                  {{ notificationSettingsSaving ? 'Saving…' : 'Save settings' }}
                </button>
              </div>
            </form>
          </template>
        </section>

        <section class="section-card admin-board content-constrained">
          <div class="section-header">
            <div>
              <h2 class="section-title">Notification tests</h2>
              <p class="section-description">
                Validate the integration by sending test messages with the saved settings.
              </p>
            </div>
          </div>
          <p class="helper-text subtle-text">
            Tests run immediately using the configuration above and report whether Home Assistant accepted the payload.
          </p>
          <div class="notification-tests-grid">
            <form class="notification-test-card" @submit.prevent="sendCustomNotificationTest">
              <h3 class="notification-test-title">Send a custom message</h3>
              <p class="helper-text">
                Build a one-off notification payload to confirm delivery.
              </p>
              <input
                v-model="notificationTests.custom.title"
                type="text"
                placeholder="Title (optional)"
              />
              <textarea
                v-model="notificationTests.custom.message"
                rows="3"
                placeholder="Message body"
                required
              ></textarea>
              <input
                v-model="notificationTests.custom.target_override"
                type="text"
                placeholder="Target override (optional)"
              />
              <p v-if="notificationTestErrors.custom" class="helper-text error-text">
                {{ notificationTestErrors.custom }}
              </p>
              <div
                v-else-if="notificationTestResults.custom"
                class="notification-result"
                :class="notificationTestResults.custom.sent ? 'success' : 'error'"
              >
                <p>{{ notificationTestResults.custom.message }}</p>
                <div
                  v-for="[category, items] in resolveNotificationCategories(notificationTestResults.custom)"
                  :key="category"
                  class="notification-category"
                >
                  <h4>{{ formatNotificationCategoryLabel(category) }}</h4>
                  <ul>
                    <li
                      v-for="item in items"
                      :key="`${category}-${item.card_name}-${item.benefit_name}-${item.expiration_date || 'none'}`"
                    >
                      {{ item.benefit_name }} ({{ item.card_name }})
                      <span v-if="item.expiration_date">
                        – Expires {{ formatNotificationDate(item.expiration_date) }}
                      </span>
                    </li>
                  </ul>
                </div>
              </div>
              <div class="notification-test-actions">
                <button class="primary-button" type="submit" :disabled="notificationTestsLoading.custom">
                  {{ notificationTestsLoading.custom ? 'Sending…' : 'Send notification' }}
                </button>
              </div>
            </form>

            <form class="notification-test-card" @submit.prevent="sendDailyNotificationTest">
              <h3 class="notification-test-title">Simulate the daily summary</h3>
              <p class="helper-text">
                Pretend today is a specific date and send the reminder generated for that day.
              </p>
              <input v-model="notificationTests.daily.target_date" type="date" required />
              <input
                v-model="notificationTests.daily.target_override"
                type="text"
                placeholder="Target override (optional)"
              />
              <p v-if="notificationTestErrors.daily" class="helper-text error-text">
                {{ notificationTestErrors.daily }}
              </p>
              <div
                v-else-if="notificationTestResults.daily"
                class="notification-result"
                :class="notificationTestResults.daily.sent ? 'success' : 'error'"
              >
                <p>{{ notificationTestResults.daily.message }}</p>
                <div
                  v-for="[category, items] in resolveNotificationCategories(notificationTestResults.daily)"
                  :key="category"
                  class="notification-category"
                >
                  <h4>{{ formatNotificationCategoryLabel(category) }}</h4>
                  <ul>
                    <li
                      v-for="item in items"
                      :key="`${category}-${item.card_name}-${item.benefit_name}-${item.expiration_date || 'none'}`"
                    >
                      {{ item.benefit_name }} ({{ item.card_name }})
                      <span v-if="item.expiration_date">
                        – Expires {{ formatNotificationDate(item.expiration_date) }}
                      </span>
                    </li>
                  </ul>
                </div>
              </div>
              <div class="notification-test-actions">
                <button class="primary-button" type="submit" :disabled="notificationTestsLoading.daily">
                  {{ notificationTestsLoading.daily ? 'Sending…' : 'Send simulated reminder' }}
                </button>
              </div>
            </form>
          </div>
        </section>

        <section class="section-card admin-board content-constrained">
          <div class="section-header">
            <div>
              <h2 class="section-title">Preconfigured cards</h2>
              <p class="section-description">
                Manage the templates that seed new cards with benefits and annual fees.
              </p>
            </div>
            <button class="primary-button secondary" type="button" @click="openAdminCreateModal">
              Add template
            </button>
          </div>
          <div v-if="!preconfiguredCards.length" class="empty-state">
            No templates yet. Add one to get started.
          </div>
          <div v-else class="admin-table-wrapper">
            <table class="admin-table">
              <thead>
                <tr>
                  <th>Template</th>
                  <th>Company</th>
                  <th>Annual fee</th>
                  <th>Benefits</th>
                  <th class="actions-column">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="card in preconfiguredCards" :key="card.slug">
                  <td>
                    <div class="admin-table__name">
                      <span class="admin-card-name">{{ card.card_type }}</span>
                      <span class="admin-card-slug">{{ card.slug }}</span>
                    </div>
                  </td>
                  <td>{{ card.company_name }}</td>
                  <td>${{ card.annual_fee.toFixed(2) }}</td>
                  <td>{{ card.benefits.length }}</td>
                  <td class="admin-actions">
                    <button
                      class="icon-button ghost"
                      type="button"
                      @click="openAdminEditModal(card)"
                      title="Edit template"
                    >
                      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path
                          d="M15.58 2.42a1.5 1.5 0 0 0-2.12 0l-1.3 1.3 4.12 4.12 1.3-1.3a1.5 1.5 0 0 0 0-2.12zM3 13.59V17h3.41l8.6-8.6-4.12-4.12z"
                        />
                      </svg>
                      <span class="sr-only">Edit template</span>
                    </button>
                    <button
                      class="icon-button danger"
                      type="button"
                      @click="handleDeletePreconfiguredCard(card.slug)"
                      title="Delete template"
                    >
                      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path
                          d="M7 3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1h3.5a.5.5 0 0 1 0 1h-.8l-.62 11a2 2 0 0 1-2 1.9H6.92a2 2 0 0 1-2-1.9L4.3 5H3.5a.5.5 0 0 1 0-1H7zm1 1h4V3H8zM6.3 5l.6 10.8a1 1 0 0 0 1 1h4.2a1 1 0 0 0 1-1L13.7 5z"
                        />
                      </svg>
                      <span class="sr-only">Delete template</span>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <div v-if="error" class="content-constrained">
        <p class="empty-state error-message">
          {{ error }}
        </p>
      </div>
    </main>
  </div>

  <BaseModal :open="showCardModal" title="Add a credit card" @close="closeCardModal">
    <form @submit.prevent="handleCreateCard">
      <div class="field-group">
        <select v-model="selectedTemplateSlug">
          <option value="">Select a preconfigured card (optional)</option>
          <option v-for="card in preconfiguredCards" :key="card.slug" :value="card.slug">
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
          inputmode="numeric"
          maxlength="5"
          minlength="4"
          placeholder="Last four or five digits"
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
          inputmode="numeric"
          maxlength="5"
          minlength="4"
          placeholder="Last four or five digits"
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
              <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M15.58 2.42a1.5 1.5 0 0 0-2.12 0l-9 9V17h5.59l9-9a1.5 1.5 0 0 0 0-2.12zM7 15H5v-2l6.88-6.88 2 2z" />
              </svg>
              <span class="sr-only">Edit redemption</span>
            </button>
            <button
              class="icon-button danger"
              type="button"
              title="Delete redemption"
              @click="handleDeleteRedemption(entry)"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M7 3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1h3.5a.5.5 0 0 1 0 1h-.8l-.62 11a2 2 0 0 1-2 1.9H6.92a2 2 0 0 1-2-1.9L4.3 5H3.5a.5.5 0 0 1 0-1H7zm1 1h4V3H8zM6.3 5l.6 10.8a1 1 0 0 0 1 1h4.2a1 1 0 0 0 1-1L13.7 5z" />
              </svg>
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

  <BaseModal
    :open="adminModal.open"
    :title="adminModal.mode === 'edit' ? 'Edit template' : 'Add template'"
    @close="closeAdminModal"
  >
    <form @submit.prevent="submitAdminCard">
      <div class="field-group">
        <input v-model="adminModal.form.card_type" type="text" placeholder="Card name" required />
        <input v-model="adminModal.form.company_name" type="text" placeholder="Company name" required />
      </div>
      <div class="field-group">
        <input v-model="adminModal.form.slug" type="text" placeholder="Slug (optional)" />
        <input
          v-model="adminModal.form.annual_fee"
          type="number"
          min="0"
          step="0.01"
          placeholder="Annual fee"
        />
      </div>
      <div class="admin-benefit-editor">
        <div
          v-for="(benefit, index) in adminModal.form.benefits"
          :key="`admin-benefit-${index}`"
          class="admin-benefit-card"
        >
          <div class="field-group">
            <input v-model="benefit.name" type="text" placeholder="Benefit name" required />
            <select v-model="benefit.type" @change="handleAdminBenefitTypeChange(benefit)">
              <option value="standard">Standard</option>
              <option value="incremental">Incremental</option>
              <option value="cumulative">Cumulative</option>
            </select>
            <select
              v-model="benefit.frequency"
              @change="handleAdminBenefitFrequencyChange(benefit)"
            >
              <option v-for="option in frequencies" :key="option" :value="option">
                {{ option.charAt(0).toUpperCase() + option.slice(1) }}
              </option>
            </select>
          </div>
          <textarea
            v-model="benefit.description"
            rows="2"
            placeholder="Description (optional)"
          ></textarea>
          <div class="field-group admin-benefit-values">
            <input
              v-if="benefit.type !== 'cumulative'"
              v-model="benefit.value"
              type="number"
              min="0"
              step="0.01"
              :placeholder="getBenefitValuePlaceholder(benefit)"
              @input="handleAdminBenefitValueInput(benefit)"
              required
            />
            <input
              v-else
              v-model="benefit.expected_value"
              type="number"
              min="0"
              step="0.01"
              placeholder="Expected value (optional)"
            />
            <button
              class="icon-button ghost"
              type="button"
              title="Remove benefit"
              @click="removeAdminBenefit(index)"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  d="M5.5 5.5a.75.75 0 0 1 1.06 0L10 8.94l3.44-3.44a.75.75 0 1 1 1.06 1.06L11.06 10l3.44 3.44a.75.75 0 0 1-1.06 1.06L10 11.06l-3.44 3.44a.75.75 0 0 1-1.06-1.06L8.94 10 5.5 6.56a.75.75 0 0 1 0-1.06z"
                />
              </svg>
              <span class="sr-only">Remove benefit</span>
            </button>
          </div>
          <div
            v-if="benefit.type !== 'cumulative' && supportsCustomWindowValues(benefit.frequency)"
            class="admin-custom-toggle"
          >
            <label class="checkbox-option">
              <input
                :checked="benefit.useCustomValues"
                type="checkbox"
                @change="toggleAdminBenefitCustomValues(benefit, $event.target.checked)"
              />
              <span>
                Set custom values for each
                {{ benefit.frequency === 'monthly'
                  ? 'month'
                  : benefit.frequency === 'quarterly'
                    ? 'quarter'
                    : 'half-year' }}
              </span>
            </label>
          </div>
          <div
            v-if="benefit.type !== 'cumulative' && benefit.useCustomValues && supportsCustomWindowValues(benefit.frequency)"
            class="admin-window-values"
          >
            <label
              v-for="(label, windowIndex) in getAdminWindowOptions(benefit.frequency)"
              :key="`${benefit.frequency}-${windowIndex}`"
            >
              <span>{{ label }}</span>
              <input
                v-model="benefit.window_values[windowIndex]"
                type="number"
                min="0"
                step="0.01"
              />
            </label>
          </div>
          <p class="helper-text">{{ benefitTypeDescriptions[benefit.type] }}</p>
        </div>
        <button class="link-button inline" type="button" @click="addAdminBenefit">
          Add another benefit
        </button>
      </div>
      <div class="modal-actions">
        <button class="primary-button secondary" type="button" @click="closeAdminModal">
          Cancel
        </button>
        <button class="primary-button" type="submit" :disabled="adminSaving">
          {{ adminSaving ? 'Saving…' : 'Save template' }}
        </button>
      </div>
    </form>
  </BaseModal>
</template>

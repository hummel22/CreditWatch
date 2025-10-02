<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import apiClient from './utils/apiClient'
import BaseModal from './components/BaseModal.vue'
import BugTracker from './components/BugTracker.vue'
import BenefitCard from './components/BenefitCard.vue'
import CreditCardList from './components/CreditCardList.vue'
import DrilldownPieChart from './components/charts/DrilldownPieChart.vue'
import SimpleBarChart from './components/charts/SimpleBarChart.vue'
import SimpleLineChart from './components/charts/SimpleLineChart.vue'
import SimplePieChart from './components/charts/SimplePieChart.vue'
import TimelineBarChart from './components/charts/TimelineBarChart.vue'
import {
  buildCardCycles,
  computeCardCycle,
  computeBenefitCycle,
  computeFrequencyWindows,
  formatDateInput,
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
  { id: 'benefits-analysis', label: 'Benefits analysis' },
  { id: 'bugs', label: 'Bug Tracker' },
  { id: 'admin', label: 'Admin' }
]

const viewToPathMap = {
  dashboard: '/',
  benefits: '/benefits',
  'benefits-analysis': '/benefits-analysis',
  bugs: '/bugs',
  admin: '/admin'
}

const interfaceSettings = reactive({
  id: null,
  theme_mode: 'light'
})

const interfaceSettingsLoading = ref(false)
const interfaceSettingsSaving = ref(false)
const interfaceSettingsError = ref('')

const themeMode = computed(() =>
  interfaceSettings.theme_mode === 'dark' ? 'dark' : 'light'
)
const isDarkMode = computed(() => themeMode.value === 'dark')
const themeStatusLabel = computed(() => (isDarkMode.value ? 'Dark mode' : 'Light mode'))
const themeToggleLabel = computed(() =>
  isDarkMode.value ? 'Switch to light mode' : 'Switch to dark mode'
)
const themeToggleHint = computed(() =>
  interfaceSettingsSaving.value ? 'Saving…' : themeToggleLabel.value
)
const isThemeToggleDisabled = computed(
  () => interfaceSettingsLoading.value || interfaceSettingsSaving.value
)

function normalizePathname(pathname) {
  if (!pathname || pathname === '/') {
    return '/'
  }
  const trimmed = pathname.replace(/\/+$/, '')
  return trimmed || '/'
}

function resolveViewFromPath(pathname) {
  const normalizedPath = normalizePathname(pathname)
  for (const [view, path] of Object.entries(viewToPathMap)) {
    if (path === normalizedPath) {
      return view
    }
  }
  return 'dashboard'
}

function resolvePathFromView(view) {
  return viewToPathMap[view] ?? '/'
}

function applyTheme(mode) {
  if (typeof document === 'undefined') {
    return
  }
  const resolvedMode = mode === 'dark' ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', resolvedMode)
  if (document.body) {
    document.body.setAttribute('data-theme', resolvedMode)
  }
}

watch(
  themeMode,
  (mode) => {
    applyTheme(mode)
  },
  { immediate: true }
)

const notificationSettings = reactive({
  id: null,
  base_url: '',
  webhook_id: '',
  default_target: '',
  enabled: true,
  event_type_preferences: {}
})

const notificationTypeOptions = [
  {
    id: 'daily',
    label: 'Daily summary notifications',
    description:
      'Send the automated 8:00 AM reminder when benefits are approaching their expiration.',
  },
  {
    id: 'custom',
    label: 'Custom notifications',
    description:
      'Allow one-off messages triggered from this page to be delivered via Home Assistant.',
  },
]

const notificationSettingsMeta = reactive({
  created_at: null,
  updated_at: null
})

const notificationSettingsLoading = ref(false)
const notificationSettingsSaving = ref(false)
const notificationSettingsLoaded = ref(false)
const notificationSettingsError = ref('')
const notificationSettingsSuccess = ref('')

const backupSettings = reactive({
  id: null,
  server: '',
  share: '',
  directory: '',
  username: '',
  password: '',
  domain: ''
})

const backupSettingsMeta = reactive({
  has_password: false,
  last_backup_at: null,
  last_backup_filename: '',
  last_backup_error: '',
  next_backup_at: null,
  created_at: null,
  updated_at: null
})

const backupSettingsLoading = ref(false)
const backupSettingsSaving = ref(false)
const backupSettingsError = ref('')
const backupSettingsSuccess = ref('')

const backupImport = reactive({
  file: null,
  filename: '',
  loading: false,
  error: '',
  success: ''
})

const backupImportInputKey = ref(0)

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

const scrollPositions = reactive({
  dashboard: 0,
  benefits: 0,
  'benefits-analysis': 0,
  bugs: 0,
  admin: 0
})

function getScrollKey(view) {
  return typeof view === 'string' && view ? view : 'dashboard'
}

function getScrollTop() {
  if (typeof window === 'undefined') {
    return 0
  }
  if (typeof window.scrollY === 'number') {
    return window.scrollY
  }
  if (window.pageYOffset) {
    return window.pageYOffset
  }
  const element =
    typeof document !== 'undefined'
      ? document.documentElement || document.body
      : null
  return element?.scrollTop || 0
}

function captureScrollPosition(view = currentView.value) {
  if (typeof window === 'undefined') {
    return 0
  }
  const key = getScrollKey(view)
  const position = Math.max(getScrollTop(), 0)
  scrollPositions[key] = position
  return position
}

async function restoreScrollPosition(view = currentView.value, fallback = null) {
  if (typeof window === 'undefined') {
    return
  }
  const key = getScrollKey(view)
  const target = fallback ?? scrollPositions[key] ?? 0
  await nextTick()
  window.requestAnimationFrame(() => {
    window.scrollTo({ top: target, left: 0, behavior: 'auto' })
  })
}

const notificationHistoryModal = reactive({
  open: false,
  loading: false,
  entries: [],
  error: '',
  search: '',
  sortDirection: 'desc',
  limit: 50
})

const backupTestLoading = ref(false)
const backupTestMessage = ref('')
const backupTestError = ref('')

const backupRunLoading = ref(false)
const backupRunMessage = ref('')
const backupRunError = ref('')

const confirmDialog = reactive({
  open: false,
  title: '',
  message: '',
  confirmLabel: 'Confirm',
  cancelLabel: 'Cancel',
  resolve: null
})

const isDashboardView = computed(() => currentView.value === 'dashboard')
const isBenefitsView = computed(() => currentView.value === 'benefits')
const isBenefitsAnalysisView = computed(() => currentView.value === 'benefits-analysis')
const isBugTrackerView = computed(() => currentView.value === 'bugs')
const isAdminView = computed(() => currentView.value === 'admin')
const showNewCardButton = computed(
  () => isDashboardView.value || isBenefitsView.value || isBenefitsAnalysisView.value
)
const showAdminTemplateButton = computed(() => isAdminView.value)

function updateHistoryState(view, { replace = false } = {}) {
  if (typeof window === 'undefined') {
    return
  }
  const path = resolvePathFromView(view)
  const normalizedTargetPath = normalizePathname(path)
  const state = { view }
  if (replace) {
    window.history.replaceState(state, '', normalizedTargetPath)
    return
  }
  const currentPath = normalizePathname(window.location.pathname)
  if (currentPath !== normalizedTargetPath) {
    window.history.pushState(state, '', normalizedTargetPath)
  }
}

function setView(view, { updateHistory = true, replace = false } = {}) {
  const targetView = navItems.some((item) => item.id === view) ? view : 'dashboard'
  if (currentView.value !== targetView) {
    currentView.value = targetView
  } else if (!replace && (!updateHistory || typeof window === 'undefined')) {
    return
  }
  if (updateHistory) {
    updateHistoryState(targetView, { replace })
  }
}

function handlePopState(event) {
  const viewFromState = event.state?.view
  const view = navItems.some((item) => item.id === viewFromState)
    ? viewFromState
    : resolveViewFromPath(window.location.pathname)
  setView(view, { updateHistory: false })
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
  currentView,
  (view) => {
    if (view === 'benefits-analysis') {
      ensureBenefitsAnalysisData()
    }
  },
  { immediate: true }
)

onMounted(() => {
  const initialView = resolveViewFromPath(window.location.pathname)
  setView(initialView, { replace: true })
  window.addEventListener('popstate', handlePopState)
})

onUnmounted(() => {
  window.removeEventListener('popstate', handlePopState)
})

watch(
  () => [
    notificationSettings.base_url,
    notificationSettings.webhook_id,
    notificationSettings.default_target,
    notificationSettings.enabled,
    JSON.stringify(notificationSettings.event_type_preferences || {})
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
  () => [
    backupSettings.server,
    backupSettings.share,
    backupSettings.directory,
    backupSettings.username,
    backupSettings.domain,
    backupSettings.password
  ],
  () => {
    backupSettingsError.value = ''
    backupSettingsSuccess.value = ''
    backupTestError.value = ''
    backupTestMessage.value = ''
  }
)

function normaliseNotificationTypePreferences(value) {
  if (!value || typeof value !== 'object') {
    return {}
  }
  const cleaned = {}
  for (const [rawKey, rawValue] of Object.entries(value)) {
    const typeId = String(rawKey || '').trim()
    if (!typeId) {
      continue
    }
    if (rawValue === false) {
      cleaned[typeId] = false
      continue
    }
    if (rawValue === true) {
      continue
    }
    if (typeof rawValue === 'string') {
      const lowered = rawValue.trim().toLowerCase()
      if (['false', '0', 'no', 'off', 'disabled'].includes(lowered)) {
        cleaned[typeId] = false
        continue
      }
      if (['true', '1', 'yes', 'on', 'enabled'].includes(lowered)) {
        continue
      }
    }
    if (!rawValue) {
      cleaned[typeId] = false
    }
  }
  return cleaned
}

function resetNotificationSettingsState() {
  notificationSettings.id = null
  notificationSettings.base_url = ''
  notificationSettings.webhook_id = ''
  notificationSettings.default_target = ''
  notificationSettings.enabled = true
  notificationSettings.event_type_preferences = {}
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
  notificationSettings.event_type_preferences = normaliseNotificationTypePreferences(
    data.event_type_preferences,
  )
  notificationSettingsMeta.created_at = data.created_at ?? null
  notificationSettingsMeta.updated_at = data.updated_at ?? null
}

function clearNotificationSettingsMessages() {
  notificationSettingsError.value = ''
  notificationSettingsSuccess.value = ''
}

function buildNotificationTypePreferencesPayload() {
  const prefs = notificationSettings.event_type_preferences || {}
  const payload = {}
  for (const [key, value] of Object.entries(prefs)) {
    if (!key) {
      continue
    }
    if (value === false) {
      payload[key] = false
    } else if (value === true) {
      payload[key] = true
    }
  }
  return payload
}

function isNotificationTypeEnabled(typeId) {
  if (!typeId) {
    return true
  }
  const prefs = notificationSettings.event_type_preferences || {}
  if (!(typeId in prefs)) {
    return true
  }
  return Boolean(prefs[typeId])
}

function setNotificationTypeEnabled(typeId, enabled) {
  if (!typeId) {
    return
  }
  const current = notificationSettings.event_type_preferences || {}
  const next = { ...current }
  if (enabled) {
    delete next[typeId]
  } else {
    next[typeId] = false
  }
  notificationSettings.event_type_preferences = next
  if (notificationSettingsLoaded.value) {
    clearNotificationSettingsMessages()
  }
}

function resetBackupSettingsState() {
  backupSettings.id = null
  backupSettings.server = ''
  backupSettings.share = ''
  backupSettings.directory = ''
  backupSettings.username = ''
  backupSettings.password = ''
  backupSettings.domain = ''
  backupSettingsMeta.has_password = false
  backupSettingsMeta.last_backup_at = null
  backupSettingsMeta.last_backup_filename = ''
  backupSettingsMeta.last_backup_error = ''
  backupSettingsMeta.next_backup_at = null
  backupSettingsMeta.created_at = null
  backupSettingsMeta.updated_at = null
}

function applyBackupSettings(data) {
  if (!data || typeof data !== 'object') {
    resetBackupSettingsState()
    return
  }
  backupSettings.id = data.id ?? null
  backupSettings.server = data.server ?? ''
  backupSettings.share = data.share ?? ''
  backupSettings.directory = data.directory ?? ''
  backupSettings.username = data.username ?? ''
  backupSettings.password = ''
  backupSettings.domain = data.domain ?? ''
  backupSettingsMeta.has_password = Boolean(data.has_password)
  backupSettingsMeta.last_backup_at = data.last_backup_at ?? null
  backupSettingsMeta.last_backup_filename = data.last_backup_filename ?? ''
  backupSettingsMeta.last_backup_error = data.last_backup_error ?? ''
  backupSettingsMeta.next_backup_at = data.next_backup_at ?? null
  backupSettingsMeta.created_at = data.created_at ?? null
  backupSettingsMeta.updated_at = data.updated_at ?? null
}

function clearBackupSettingsMessages() {
  backupSettingsError.value = ''
  backupSettingsSuccess.value = ''
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

async function loadInterfaceSettings() {
  interfaceSettingsLoading.value = true
  interfaceSettingsError.value = ''
  try {
    const response = await apiClient.get('/api/interface/settings')
    if (response?.data) {
      interfaceSettings.id = response.data.id ?? null
      interfaceSettings.theme_mode = response.data.theme_mode ?? 'light'
    }
  } catch (err) {
    interfaceSettingsError.value = 'Unable to load theme preference.'
    console.error('Failed to load interface settings', err)
  } finally {
    interfaceSettingsLoading.value = false
  }
}

async function saveThemeMode(mode) {
  interfaceSettingsSaving.value = true
  interfaceSettingsError.value = ''
  try {
    const response = await apiClient.put('/api/interface/settings', {
      theme_mode: mode
    })
    if (response?.data) {
      interfaceSettings.id = response.data.id ?? interfaceSettings.id
      interfaceSettings.theme_mode = response.data.theme_mode ?? mode
    } else {
      interfaceSettings.theme_mode = mode
    }
  } catch (err) {
    interfaceSettingsError.value = 'Unable to save theme preference.'
    console.error('Failed to update interface settings', err)
    throw err
  } finally {
    interfaceSettingsSaving.value = false
  }
}

async function toggleThemeMode() {
  if (isThemeToggleDisabled.value) {
    return
  }
  const previousMode = interfaceSettings.theme_mode
  const nextMode = previousMode === 'dark' ? 'light' : 'dark'
  interfaceSettings.theme_mode = nextMode
  try {
    await saveThemeMode(nextMode)
  } catch (err) {
    interfaceSettings.theme_mode = previousMode
  }
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
  backupSettingsLoading.value = true
  backupSettingsSuccess.value = ''
  backupSettingsError.value = ''
  try {
    const response = await apiClient.get('/api/admin/backup/settings')
    if (response.data) {
      applyBackupSettings(response.data)
    } else {
      resetBackupSettingsState()
    }
  } catch (err) {
    resetBackupSettingsState()
    backupSettingsError.value =
      'Unable to load backup settings. Enter new details to configure backups.'
  } finally {
    backupSettingsLoading.value = false
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
    const typePreferences = buildNotificationTypePreferencesPayload()
    const payload = {
      base_url: baseUrl,
      webhook_id: webhookId,
      enabled: Boolean(notificationSettings.enabled),
      event_type_preferences: typePreferences
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
  clearBackupSettingsMessages()
  const server = backupSettings.server.trim()
  const share = backupSettings.share.trim()
  const directory = backupSettings.directory.trim()
  const username = backupSettings.username.trim()
  const domain = backupSettings.domain.trim()
  const password = backupSettings.password.trim()
  const hasExisting = backupSettings.id !== null
  if (!server || !share || !username) {
    backupSettingsError.value = 'Provide the SMB server, share, and username before saving.'
    return
  }
  if (!password && !hasExisting && !backupSettingsMeta.has_password) {
    backupSettingsError.value = 'Enter the SMB password to configure backups.'
    return
  }
  const payload = {
    server,
    share,
    username,
    directory: directory ? directory : ''
  }
  if (domain) {
    payload.domain = domain
  }
  if (password) {
    payload.password = password
  }
  backupSettingsSaving.value = true
  try {
    const response = hasExisting
      ? await apiClient.patch('/api/admin/backup/settings', payload)
      : await apiClient.put('/api/admin/backup/settings', payload)
    applyBackupSettings(response.data)
    backupSettingsSuccess.value = hasExisting
      ? 'Backup settings updated. A new backup will run within the next hour.'
      : 'Backup settings saved. Backups will start within the next hour.'
  } catch (err) {
    backupSettingsError.value = extractErrorMessage(err, 'Unable to save backup settings.')
  } finally {
    backupSettingsSaving.value = false
  }
}

async function testBackupConnection() {
  backupTestError.value = ''
  backupTestMessage.value = ''
  const server = backupSettings.server.trim()
  const share = backupSettings.share.trim()
  const directory = backupSettings.directory.trim()
  const username = backupSettings.username.trim()
  const domain = backupSettings.domain.trim()
  const password = backupSettings.password.trim()
  if (!server || !share || !username) {
    backupTestError.value = 'Provide the SMB server, share, and username before testing.'
    return
  }
  const payload = {
    server,
    share,
    directory: directory ? directory : '',
    username,
    use_stored_password: false
  }
  if (domain) {
    payload.domain = domain
  }
  if (password) {
    payload.password = password
  } else if (backupSettingsMeta.has_password) {
    payload.use_stored_password = true
  } else {
    backupTestError.value = 'Enter the SMB password to test the connection.'
    return
  }
  backupTestLoading.value = true
  try {
    const response = await apiClient.post('/api/admin/backup/test', payload)
    backupTestMessage.value = response.data?.detail || 'Connection successful.'
  } catch (err) {
    backupTestError.value = extractErrorMessage(
      err,
      'Unable to test the backup connection.'
    )
  } finally {
    backupTestLoading.value = false
  }
}

function handleBackupFileChange(event) {
  const files = event?.target?.files
  const [file] = files && files.length ? files : [null]
  backupImport.file = file
  backupImport.filename = file ? file.name : ''
  backupImport.error = ''
  backupImport.success = ''
}

async function submitBackupImport() {
  backupImport.error = ''
  backupImport.success = ''
  if (!backupImport.file) {
    backupImport.error = 'Select a .db file to import.'
    return
  }
  if (!/\.db$/i.test(backupImport.file.name || '')) {
    backupImport.error = 'Only .db files can be imported.'
    return
  }
  const formData = new FormData()
  formData.append('file', backupImport.file)
  backupImport.loading = true
  try {
    await apiClient.post('/api/admin/backup/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    backupImport.success = 'Database imported successfully. Refreshing data…'
    backupImport.file = null
    backupImport.filename = ''
    backupImportInputKey.value += 1
    await loadNotificationSettings()
    await loadCards({ preserveScroll: true })
    await loadBackupSettings()
  } catch (err) {
    backupImport.error = extractErrorMessage(err, 'Unable to import the database file.')
  } finally {
    backupImport.loading = false
  }
}

async function runBackupNow() {
  backupRunError.value = ''
  backupRunMessage.value = ''
  backupRunLoading.value = true
  try {
    const response = await apiClient.post('/api/admin/backup/run')
    if (response.data) {
      applyBackupSettings(response.data)
    }
    backupRunMessage.value = 'Backup completed successfully.'
  } catch (err) {
    backupRunError.value = extractErrorMessage(err, 'Unable to run the backup now.')
  } finally {
    backupRunLoading.value = false
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
  if (key === 'cancelled_cards') {
    return 'Cards to be Canceled'
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

function getNotificationItemType(item) {
  if (!item || typeof item !== 'object') {
    return 'unknown'
  }
  const summaryType = item.summary_type
  if (summaryType === 'cancelled_card' || summaryType === 'benefit') {
    return summaryType
  }
  if (Object.prototype.hasOwnProperty.call(item, 'fee_due_date') && !item.benefit_name) {
    return 'cancelled_card'
  }
  return 'benefit'
}

function formatNotificationItemTitle(item) {
  const type = getNotificationItemType(item)
  const cardName = item?.card_name || 'Card'
  if (type === 'cancelled_card') {
    return item?.account_name
      ? `Card to be Canceled – ${cardName} (${item.account_name})`
      : `Card to be Canceled – ${cardName}`
  }
  const benefitName = item?.benefit_name || 'Benefit'
  return `${benefitName} (${cardName})`
}

function formatNotificationItemDetail(item) {
  const type = getNotificationItemType(item)
  if (type === 'cancelled_card') {
    const dueDisplay = formatNotificationDate(item?.fee_due_date)
    const days = typeof item?.days_until_due === 'number' ? item.days_until_due : null
    if (days === null) {
      return dueDisplay ? `Annual fee due ${dueDisplay}` : ''
    }
    if (days > 0) {
      const plural = days === 1 ? '' : 's'
      return dueDisplay
        ? `Annual fee due in ${days} day${plural} (${dueDisplay})`
        : `Annual fee due in ${days} day${plural}`
    }
    if (days === 0) {
      return dueDisplay ? `Annual fee due today (${dueDisplay})` : 'Annual fee due today'
    }
    const overdue = Math.abs(days)
    const plural = overdue === 1 ? '' : 's'
    return dueDisplay
      ? `Annual fee overdue by ${overdue} day${plural} (${dueDisplay})`
      : `Annual fee overdue by ${overdue} day${plural}`
  }
  if (item?.expiration_date) {
    return `Expires ${formatNotificationDate(item.expiration_date)}`
  }
  return ''
}

function formatNotificationItemKey(category, item) {
  const type = getNotificationItemType(item)
  if (type === 'cancelled_card') {
    return `${category}-${item?.card_name || 'card'}-${item?.fee_due_date || 'due'}`
  }
  return `${category}-${item?.card_name || 'card'}-${item?.benefit_name || 'benefit'}-${
    item?.expiration_date || 'none'
  }`
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

function formatNotificationEventType(value) {
  if (!value) {
    return ''
  }
  return value
    .toString()
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

async function loadNotificationHistory() {
  notificationHistoryModal.loading = true
  notificationHistoryModal.error = ''
  notificationHistoryModal.entries = []
  try {
    const params = {
      limit: Math.max(1, Math.min(200, Number(notificationHistoryModal.limit) || 50)),
      sort_direction:
        notificationHistoryModal.sortDirection === 'asc' ? 'asc' : 'desc',
    }
    const trimmedSearch = notificationHistoryModal.search.trim()
    if (trimmedSearch) {
      params.search = trimmedSearch
    }
    const response = await apiClient.get('/api/admin/notifications/history', {
      params,
    })
    notificationHistoryModal.entries = Array.isArray(response.data) ? response.data : []
  } catch (err) {
    notificationHistoryModal.error = extractErrorMessage(
      err,
      'Unable to load notification history.'
    )
    notificationHistoryModal.entries = []
  } finally {
    notificationHistoryModal.loading = false
  }
}

async function openNotificationHistory() {
  notificationHistoryModal.open = true
  await loadNotificationHistory()
}

function closeNotificationHistory() {
  notificationHistoryModal.open = false
  notificationHistoryModal.loading = false
}

async function applyNotificationHistorySearch() {
  await loadNotificationHistory()
}

function clearNotificationHistorySearch() {
  if (!notificationHistoryModal.search) {
    return
  }
  notificationHistoryModal.search = ''
  loadNotificationHistory()
}

async function toggleNotificationHistorySort() {
  notificationHistoryModal.sortDirection =
    notificationHistoryModal.sortDirection === 'desc' ? 'asc' : 'desc'
  await loadNotificationHistory()
}

function requestConfirmation(options = {}) {
  return new Promise((resolve) => {
    confirmDialog.title = options.title || 'Confirm action'
    confirmDialog.message = options.message || 'Are you sure you want to continue?'
    confirmDialog.confirmLabel = options.confirmLabel || 'Confirm'
    confirmDialog.cancelLabel = options.cancelLabel || 'Cancel'
    confirmDialog.open = true
    confirmDialog.resolve = (value) => {
      confirmDialog.open = false
      confirmDialog.resolve = null
      resolve(Boolean(value))
    }
  })
}

function confirmDialogConfirm() {
  if (typeof confirmDialog.resolve === 'function') {
    confirmDialog.resolve(true)
  } else {
    confirmDialog.open = false
  }
}

function confirmDialogCancel() {
  if (typeof confirmDialog.resolve === 'function') {
    confirmDialog.resolve(false)
  } else {
    confirmDialog.open = false
  }
}

function handleConfirmDialogClose() {
  confirmDialogCancel()
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
  if (typeof card.display_order === 'number' && Number.isFinite(card.display_order)) {
    normalized.display_order = card.display_order
  } else if (card.display_order != null) {
    const parsed = Number(card.display_order)
    normalized.display_order = Number.isFinite(parsed) ? parsed : null
  } else {
    normalized.display_order = null
  }
  normalized.is_cancelled = Boolean(card.is_cancelled)
  normalized.cancelled_at = card.cancelled_at || null
  if (Array.isArray(card.benefits)) {
    normalized.benefits = card.benefits.map((benefit) => ({
      ...benefit,
      exclude_from_benefits_page: Boolean(benefit.exclude_from_benefits_page),
      exclude_from_notifications: Boolean(benefit.exclude_from_notifications)
    }))
  }
  return normalized
}

function normaliseCards(collection) {
  if (!Array.isArray(collection)) {
    return []
  }
  const normalised = collection.map((card) => normaliseCard(card))
  return normalised.sort((first, second) => {
    const firstOrder = Number.isFinite(first.display_order)
      ? first.display_order
      : Number.MAX_SAFE_INTEGER
    const secondOrder = Number.isFinite(second.display_order)
      ? second.display_order
      : Number.MAX_SAFE_INTEGER
    if (firstOrder !== secondOrder) {
      return firstOrder - secondOrder
    }
    return (first.id ?? 0) - (second.id ?? 0)
  })
}

function resolveDefaultFrequency() {
  return frequencies.value[0] || 'monthly'
}

let adminBenefitIdCounter = 0

function createAdminBenefit(overrides = {}) {
  adminBenefitIdCounter += 1
  return {
    id: `admin-benefit-${adminBenefitIdCounter}`,
    name: '',
    description: '',
    frequency: resolveDefaultFrequency(),
    type: 'standard',
    value: '',
    expected_value: '',
    useCustomValues: false,
    window_values: [],
    window_tracking_mode: '',
    exclude_from_benefits_page: false,
    exclude_from_notifications: false,
    ...overrides
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

const DAY_IN_MS = 24 * 60 * 60 * 1000

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

function supportsAlignmentOverride(frequency) {
  return ['monthly', 'quarterly', 'semiannual', 'yearly'].includes(frequency)
}

function resolveBenefitWindowCount(benefit) {
  const indexes = resolveActiveWindowIndexes(benefit)
  return indexes.length
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
  const indexes = resolveActiveWindowIndexes(benefit)
  if (!indexes.length) {
    return 0
  }
  if (Array.isArray(benefit.window_values) && benefit.window_values.length) {
    return indexes.reduce((acc, index) => acc + getWindowValueForIndex(benefit, index), 0)
  }
  const base = Number(benefit.value ?? 0)
  if (!Number.isFinite(base)) {
    return 0
  }
  return base * indexes.length
}

function resolveActiveWindowIndexes(benefit) {
  if (!benefit) {
    return []
  }
  if (Array.isArray(benefit.active_window_indexes) && benefit.active_window_indexes.length) {
    return benefit.active_window_indexes.filter((value) => typeof value === 'number' && value > 0)
  }
  if (typeof benefit.cycle_window_count === 'number' && benefit.cycle_window_count > 0) {
    return Array.from({ length: benefit.cycle_window_count }, (_, idx) => idx + 1)
  }
  if (supportsCustomWindowValues(benefit.frequency)) {
    const count = WINDOW_COUNTS[benefit.frequency]
    return Array.from({ length: count }, (_, idx) => idx + 1)
  }
  return []
}

const showCardModal = ref(false)

const cardSortModal = reactive({
  open: false,
  order: [],
  saving: false,
  error: ''
})

const cardSortDragState = reactive({
  activeIndex: null,
  overIndex: null
})

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
  occurred_on: '',
  markComplete: false
})

const historyModal = reactive({
  open: false,
  cardId: null,
  benefitId: null,
  benefit: null,
  entries: [],
  loading: false,
  windowLabel: '',
  windowRange: null,
  windowOverride: null
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
    year_tracking_mode: 'calendar',
    is_cancelled: false
  }
})

const exportTemplateModal = reactive({
  open: false,
  cardId: null,
  card: null,
  loading: false,
  error: '',
  success: '',
  form: {
    card_type: '',
    company_name: '',
    annual_fee: '',
    slug: '',
    override_existing: false,
    override_slug: ''
  }
})

watch(
  () => exportTemplateModal.form.override_existing,
  (value) => {
    if (!value) {
      exportTemplateModal.form.override_slug = ''
    }
  }
)

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
  deletedWindows: [],
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

const benefitSearchQuery = ref('')

const benefitsCollection = computed(() => {
  const entries = []
  for (const card of cards.value) {
    if (!Array.isArray(card.benefits)) {
      continue
    }
    for (const benefit of card.benefits) {
      if (benefit.exclude_from_benefits_page) {
        continue
      }
      entries.push({ card, benefit })
    }
  }
  return entries.sort((a, b) => compareBenefits(a.benefit, b.benefit))
})

const filteredBenefitsCollection = computed(() => {
  const query = benefitSearchQuery.value.trim().toLowerCase()
  if (!query) {
    return benefitsCollection.value
  }
  return benefitsCollection.value.filter(({ benefit }) => {
    const name = typeof benefit?.name === 'string' ? benefit.name.toLowerCase() : ''
    const description =
      typeof benefit?.description === 'string' ? benefit.description.toLowerCase() : ''
    return name.includes(query) || description.includes(query)
  })
})

const ANALYSIS_COLOR_PALETTE = [
  '#4f46e5',
  '#6366f1',
  '#0ea5e9',
  '#22c55e',
  '#14b8a6',
  '#f97316',
  '#ec4899',
  '#a855f7'
]

function getAnalysisColor(index) {
  if (typeof index !== 'number' || index < 0) {
    return ANALYSIS_COLOR_PALETTE[0]
  }
  return ANALYSIS_COLOR_PALETTE[index % ANALYSIS_COLOR_PALETTE.length]
}

function formatCurrency(value, options = {}) {
  const { minimumFractionDigits = 0, maximumFractionDigits = 0 } = options
  const parsed = Number(value ?? 0)
  const safeValue = Number.isFinite(parsed) ? parsed : 0
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits,
    maximumFractionDigits
  }).format(safeValue)
}

function getCardLabel(cardName) {
  if (typeof cardName !== 'string') {
    return 'Card'
  }
  const words = cardName.trim().split(/\s+/).filter(Boolean)
  if (!words.length) {
    return 'Card'
  }
  return words.slice(0, 2).join(' ')
}

const benefitsAnalysisState = reactive({
  loading: false,
  loaded: false,
  error: '',
  warning: ''
})

const benefitsAnalysisRedemptions = ref(new Map())

const benefitsAnalysisActiveCards = computed(() =>
  cards.value.filter((card) => !card.is_cancelled)
)

const benefitsAnalysisTotals = computed(() => {
  const annualFees = benefitsAnalysisActiveCards.value.reduce(
    (acc, card) => acc + Number(card.annual_fee ?? 0),
    0
  )
  const utilized = benefitsAnalysisActiveCards.value.reduce(
    (acc, card) => acc + Number(card.utilized_value ?? 0),
    0
  )
  const potential = benefitsAnalysisActiveCards.value.reduce(
    (acc, card) => acc + Number(card.potential_value ?? 0),
    0
  )
  return {
    annualFees,
    utilized,
    potential,
    net: utilized - annualFees
  }
})

const benefitsAnalysisFeePieChart = computed(() => {
  const series = []
  const drilldown = []

  benefitsAnalysisActiveCards.value.forEach((card, index) => {
    const fee = Number(card.annual_fee ?? 0)
    const safeFee = Number.isFinite(fee) && fee > 0 ? fee : 0
    if (safeFee <= 0) {
      return
    }

    const color = getAnalysisColor(index)
    const baseDrilldownId = card.id != null ? `card-${card.id}` : `card-${index}`
    const benefits = Array.isArray(card.benefits) ? card.benefits : []
    const cardLabel = getCardLabel(card.card_name)

    const drilldownData = benefits
      .map((benefit) => {
        const amount = getCycleTargetValue(benefit)
        const safeAmount = Number.isFinite(amount) && amount > 0 ? amount : 0
        if (safeAmount <= 0) {
          return null
        }
        const rawName = typeof benefit?.name === 'string' ? benefit.name.trim() : ''
        const label = rawName || 'Benefit'
        return {
          name: label,
          y: safeAmount,
          displayValue: formatCurrency(safeAmount, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
          })
        }
      })
      .filter((entry) => entry !== null)
      .sort((a, b) => b.y - a.y)

    const limitedDrilldownData = drilldownData.slice(0, 8)
    if (drilldownData.length > 8) {
      const remainder = drilldownData.slice(8).reduce((acc, entry) => acc + entry.y, 0)
      if (remainder > 0) {
        limitedDrilldownData.push({
          name: 'Other benefits',
          y: remainder,
          displayValue: formatCurrency(remainder, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
          })
        })
      }
    }

    series.push({
      name: cardLabel,
      y: safeFee,
      color,
      drilldown: limitedDrilldownData.length ? baseDrilldownId : undefined,
      displayValue: formatCurrency(safeFee, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    })

    if (limitedDrilldownData.length) {
      drilldown.push({
        id: baseDrilldownId,
        name: `${card.card_name} benefits`,
        data: limitedDrilldownData
      })
    }
  })

  const sortedSeries = series.sort((a, b) => b.y - a.y)

  return {
    series: sortedSeries,
    drilldown
  }
})

const benefitsAnalysisMonthlyFees = computed(() => {
  const monthly = Array.from({ length: 12 }, () => 0)
  for (const card of benefitsAnalysisActiveCards.value) {
    const fee = Number(card.annual_fee ?? 0)
    if (!Number.isFinite(fee) || fee <= 0) {
      continue
    }
    const dueDate = parseDate(card.fee_due_date)
    if (dueDate instanceof Date) {
      const monthIndex = dueDate.getMonth()
      if (monthIndex >= 0 && monthIndex < monthly.length) {
        monthly[monthIndex] += fee
      }
    }
  }
  return monthly
})

const benefitsAnalysisMonthlyFeeTimeline = computed(() =>
  MONTH_LABELS.map((label, index) => {
    const value = Number(benefitsAnalysisMonthlyFees.value[index] ?? 0)
    const safeValue = Number.isFinite(value) && value > 0 ? value : 0
    return {
      label: label.slice(0, 3),
      fullLabel: label,
      value: safeValue,
      color: '#6366f1',
      displayValue: formatCurrency(safeValue)
    }
  })
)

const benefitsAnalysisBenefitEntries = computed(() => {
  const entries = []
  for (const card of benefitsAnalysisActiveCards.value) {
    if (!Array.isArray(card.benefits)) {
      continue
    }
    for (const benefit of card.benefits) {
      entries.push({ card, benefit })
    }
  }
  return entries
})

const benefitsAnalysisMonthlyBenefits = computed(() => {
  const monthly = Array.from({ length: 12 }, () => 0)
  const redemptions = benefitsAnalysisRedemptions.value
  const currentYear = new Date().getFullYear()
  for (const entries of redemptions.values()) {
    if (!Array.isArray(entries)) {
      continue
    }
    for (const entry of entries) {
      const occurred = parseDate(entry?.occurred_on)
      const amount = Number(entry?.amount ?? 0)
      if (!occurred || !Number.isFinite(amount) || occurred.getFullYear() !== currentYear) {
        continue
      }
      const monthIndex = occurred.getMonth()
      if (monthIndex >= 0 && monthIndex < monthly.length) {
        monthly[monthIndex] += amount
      }
    }
  }
  for (const { benefit } of benefitsAnalysisBenefitEntries.value) {
    if (benefit?.type !== 'standard' || !benefit.is_used || !benefit.used_at) {
      continue
    }
    const entries = redemptions.get(benefit.id)
    if (entries && entries.length) {
      continue
    }
    const usedAt = parseDate(benefit.used_at)
    if (!usedAt || usedAt.getFullYear() !== currentYear) {
      continue
    }
    const amount = getCycleTargetValue(benefit)
    if (amount > 0) {
      const monthIndex = usedAt.getMonth()
      if (monthIndex >= 0 && monthIndex < monthly.length) {
        monthly[monthIndex] += amount
      }
    }
  }
  return monthly
})

const benefitsAnalysisLinePoints = computed(() =>
  MONTH_LABELS.map((label, index) => ({
    label: label.slice(0, 3),
    values: {
      benefits: Number(benefitsAnalysisMonthlyBenefits.value[index] ?? 0),
      fees: Number(benefitsAnalysisMonthlyFees.value[index] ?? 0)
    }
  }))
)

const benefitsAnalysisLineSeries = [
  { key: 'benefits', label: 'Benefits redeemed', color: '#22c55e' },
  { key: 'fees', label: 'Annual fees', color: '#6366f1' }
]

const benefitsAnalysisLineMax = computed(() => {
  const values = []
  for (const point of benefitsAnalysisLinePoints.value) {
    values.push(Number(point.values.benefits ?? 0))
    values.push(Number(point.values.fees ?? 0))
  }
  const max = values.reduce((acc, value) => Math.max(acc, value), 0)
  return max > 0 ? max : 0
})

const benefitsAnalysisUtilizedByCard = computed(() => {
  const entries = benefitsAnalysisActiveCards.value.map((card, index) => {
    const utilized = Number(card.utilized_value ?? 0)
    const value = Number.isFinite(utilized) ? utilized : 0
    return {
      label: card.card_name,
      value,
      color: getAnalysisColor(index),
      displayValue: formatCurrency(value)
    }
  })
  return entries
    .filter((entry) => entry.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
})

const utilizationPercentFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 0,
  minimumFractionDigits: 0
})

const benefitsAnalysisUtilizationRows = computed(() => {
  const entries = benefitsAnalysisActiveCards.value.map((card) => {
    const potential = Number(card.potential_value ?? 0)
    const utilized = Number(card.utilized_value ?? 0)
    const safePotential = Number.isFinite(potential) && potential > 0 ? potential : 0
    const safeUtilized = Number.isFinite(utilized) && utilized > 0 ? utilized : 0
    const rate = safePotential > 0 ? (safeUtilized / safePotential) * 100 : 0
    const clampedRate = Math.max(Math.min(Number.isFinite(rate) ? rate : 0, 100), 0)
    return {
      label: card.card_name,
      rate: clampedRate,
      formattedRate: `${utilizationPercentFormatter.format(clampedRate)}%`,
      accessibleLabel: `${utilizationPercentFormatter.format(clampedRate)}% utilization rate`
    }
  })
  return entries.sort((a, b) => b.rate - a.rate)
})

const BENEFIT_TYPE_LABELS = {
  standard: 'Standard',
  incremental: 'Incremental',
  cumulative: 'Cumulative'
}

const benefitsAnalysisBenefitsByType = computed(() => {
  const totals = new Map()
  for (const { benefit } of benefitsAnalysisBenefitEntries.value) {
    const type = benefit?.type || 'standard'
    const amount = getCycleTargetValue(benefit)
    const value = Number.isFinite(amount) ? amount : 0
    totals.set(type, (totals.get(type) ?? 0) + value)
  }
  const sorted = Array.from(totals.entries()).sort((a, b) => b[1] - a[1])
  return sorted.map(([type, value], index) => ({
    label: BENEFIT_TYPE_LABELS[type] || type.charAt(0).toUpperCase() + type.slice(1),
    value,
    color: getAnalysisColor(index),
    displayValue: formatCurrency(value)
  }))
})

const benefitsAnalysisMissedValue = computed(() =>
  benefitsAnalysisBenefitEntries.value.reduce(
    (acc, { benefit }) => acc + Number(benefit?.missed_window_value ?? 0),
    0
  )
)

const benefitsAnalysisHasCards = computed(
  () => benefitsAnalysisActiveCards.value.length > 0
)

const benefitsAnalysisHasBenefits = computed(
  () => benefitsAnalysisBenefitEntries.value.length > 0
)

function analysisCardUnits(minUnits, maxUnits) {
  const safeMin = Number.isFinite(Number(minUnits)) ? Number(minUnits) : 1
  const safeMax = Number.isFinite(Number(maxUnits)) ? Number(maxUnits) : safeMin
  const clampedMin = Math.max(1, Math.min(safeMin, 6))
  const clampedMax = Math.max(clampedMin, Math.min(safeMax, 6))
  return {
    '--analysis-card-min-units': clampedMin,
    '--analysis-card-max-units': clampedMax
  }
}

function invalidateBenefitsAnalysis() {
  benefitsAnalysisState.loaded = false
  benefitsAnalysisState.error = ''
  benefitsAnalysisState.warning = ''
  benefitsAnalysisRedemptions.value = new Map()
}

async function ensureBenefitsAnalysisData() {
  if (benefitsAnalysisState.loading || benefitsAnalysisState.loaded) {
    return
  }
  if (!benefitsAnalysisHasBenefits.value) {
    benefitsAnalysisRedemptions.value = new Map()
    benefitsAnalysisState.loaded = true
    benefitsAnalysisState.error = ''
    benefitsAnalysisState.warning = ''
    return
  }
  const benefitIds = Array.from(
    new Set(benefitsAnalysisBenefitEntries.value.map(({ benefit }) => benefit.id))
  )
  if (!benefitIds.length) {
    benefitsAnalysisRedemptions.value = new Map()
    benefitsAnalysisState.loaded = true
    benefitsAnalysisState.error = ''
    benefitsAnalysisState.warning = ''
    return
  }
  benefitsAnalysisState.loading = true
  benefitsAnalysisState.error = ''
  benefitsAnalysisState.warning = ''
  try {
    const tasks = benefitIds.map((benefitId) => fetchBenefitRedemptions(benefitId))
    const results = await Promise.allSettled(tasks)
    const map = new Map()
    let hadError = false
    results.forEach((result, index) => {
      const benefitId = benefitIds[index]
      if (result.status === 'fulfilled') {
        map.set(benefitId, Array.isArray(result.value) ? result.value : [])
      } else {
        hadError = true
      }
    })
    benefitsAnalysisRedemptions.value = map
    benefitsAnalysisState.loaded = true
    if (hadError) {
      benefitsAnalysisState.warning =
        'Some benefit history could not be loaded. Data may be incomplete.'
    }
  } catch (err) {
    benefitsAnalysisState.error = 'Unable to load benefit history for analysis.'
    benefitsAnalysisState.loaded = false
    benefitsAnalysisRedemptions.value = new Map()
  } finally {
    benefitsAnalysisState.loading = false
  }
}

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

async function refreshCards({ preserveScroll = true, data = null } = {}) {
  const activeView = currentView.value
  let previousScroll = null
  if (preserveScroll) {
    previousScroll = captureScrollPosition(activeView)
  }
  const payload =
    data !== null
      ? data
      : await apiClient
          .get('/api/cards')
          .then((response) => response.data)
  cards.value = normaliseCards(payload)
  invalidateBenefitsAnalysis()
  if (isBenefitsAnalysisView.value) {
    await ensureBenefitsAnalysisData()
  }
  if (preserveScroll) {
    await restoreScrollPosition(activeView, previousScroll)
  } else {
    captureScrollPosition(activeView)
  }
  return cards.value
}

async function loadCards(options = {}) {
  const { preserveScroll = false } = options
  loading.value = true
  error.value = ''
  try {
    await refreshCards({ ...options, preserveScroll })
  } catch (err) {
    error.value = 'Unable to load cards. Ensure the backend is running.'
  } finally {
    loading.value = false
  }
}

function openCardSortModal() {
  if (!cards.value.length) {
    return
  }
  cardSortModal.order = cards.value.map((card) => ({
    id: card.id,
    card_name: card.card_name
  }))
  cardSortModal.error = ''
  cardSortModal.open = true
  cardSortDragState.activeIndex = null
  cardSortDragState.overIndex = null
}

function closeCardSortModal() {
  cardSortModal.open = false
  cardSortModal.order = []
  cardSortModal.error = ''
  cardSortModal.saving = false
  cardSortDragState.activeIndex = null
  cardSortDragState.overIndex = null
}

function handleCardSortDragStart(index, event) {
  cardSortDragState.activeIndex = index
  cardSortDragState.overIndex = index
  if (event?.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function handleCardSortDragEnter(index) {
  if (cardSortDragState.activeIndex === null || index === cardSortDragState.activeIndex) {
    cardSortDragState.overIndex = index
    return
  }
  cardSortDragState.overIndex = index
  const updated = [...cardSortModal.order]
  const [moved] = updated.splice(cardSortDragState.activeIndex, 1)
  updated.splice(index, 0, moved)
  cardSortModal.order = updated
  cardSortDragState.activeIndex = index
}

function handleCardSortDragLeave(index) {
  if (cardSortDragState.overIndex === index) {
    cardSortDragState.overIndex = null
  }
}

function handleCardSortDragEnd() {
  cardSortDragState.activeIndex = null
  cardSortDragState.overIndex = null
}

async function submitCardSortOrder() {
  if (!cardSortModal.order.length) {
    closeCardSortModal()
    return
  }
  const payload = {
    card_ids: cardSortModal.order.map((entry) => entry.id)
  }
  cardSortModal.saving = true
  cardSortModal.error = ''
  try {
    const response = await apiClient.put('/api/cards/order', payload)
    await refreshCards({ preserveScroll: true, data: response.data })
    closeCardSortModal()
  } catch (err) {
    cardSortModal.error = extractErrorMessage(err, 'Unable to save card order.')
  } finally {
    cardSortModal.saving = false
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
  if (!supportsAlignmentOverride(benefit.frequency)) {
    benefit.window_tracking_mode = ''
  }
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
  adminModal.form.benefits = card.benefits.map((benefit) =>
    createAdminBenefit({
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
        : [],
      window_tracking_mode: benefit.window_tracking_mode || '',
      exclude_from_benefits_page: Boolean(benefit.exclude_from_benefits_page),
      exclude_from_notifications: Boolean(benefit.exclude_from_notifications)
    })
  )
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

function removeAdminBenefit(benefitId) {
  const index = adminModal.form.benefits.findIndex((benefit) => benefit.id === benefitId)
  if (index === -1) {
    return
  }
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
    benefit.window_tracking_mode = ''
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
        if (supportsAlignmentOverride(benefit.frequency)) {
          base.window_tracking_mode =
            benefit.window_tracking_mode && benefit.window_tracking_mode !== ''
              ? benefit.window_tracking_mode
              : null
        } else {
          base.window_tracking_mode = null
        }
        base.exclude_from_benefits_page = Boolean(
          benefit.exclude_from_benefits_page
        )
        base.exclude_from_notifications = Boolean(
          benefit.exclude_from_notifications
        )
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
        if (benefit.exclude_from_benefits_page) {
          benefitPayload.exclude_from_benefits_page = true
        }
        if (benefit.exclude_from_notifications) {
          benefitPayload.exclude_from_notifications = true
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
      await loadCards({ preserveScroll: true })
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
    await refreshCards({ preserveScroll: true })
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to add the benefit. Please try again.'
  }
}

async function handleToggleBenefit({ id, value }) {
  try {
    await apiClient.post(`/api/benefits/${id}/usage`, { is_used: value })
    await refreshCards({ preserveScroll: true })
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to update the benefit usage.'
  }
}

async function handleDeleteBenefit(benefitId) {
  const card =
    cards.value.find((entry) =>
      Array.isArray(entry.benefits) && entry.benefits.some((benefit) => benefit.id === benefitId)
    ) || null
  const benefit = card
    ? card.benefits.find((item) => item.id === benefitId)
    : null
  const confirmed = await requestConfirmation({
    title: 'Delete benefit',
    message: benefit
      ? `Delete the "${benefit.name}" benefit${card ? ` from ${card.card_name}` : ''}? This cannot be undone.`
      : 'Delete this benefit? This cannot be undone.',
    confirmLabel: 'Delete benefit'
  })
  if (!confirmed) {
    return
  }
  try {
    await apiClient.delete(`/api/benefits/${benefitId}`)
    await refreshCards({ preserveScroll: true })
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to remove the benefit.'
  }
}

async function handleDeleteCard(cardId) {
  const card = findCard(cardId)
  const confirmed = await requestConfirmation({
    title: 'Delete card',
    message: card
      ? `Delete ${card.card_name}? All associated benefits and history will be removed.`
      : 'Delete this card? All associated benefits and history will be removed.',
    confirmLabel: 'Delete card'
  })
  if (!confirmed) {
    return
  }
  try {
    await apiClient.delete(`/api/cards/${cardId}`)
    await loadCards({ preserveScroll: true })
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to delete the card.'
  }
}

function resolveDefaultRedemptionAmount(benefit, windowContext = null) {
  if (!benefit || benefit.type === 'cumulative') {
    return ''
  }

  if (windowContext) {
    const targetBase =
      windowContext.targetValue != null
        ? Number(windowContext.targetValue)
        : getWindowValueForIndex(benefit, windowContext.index)
    const baseValue = Number.isFinite(targetBase) ? targetBase : 0
    if (baseValue <= 0) {
      return ''
    }
    const windowTotal = Number(windowContext.total ?? 0)
    const remaining = Math.max(baseValue - windowTotal, 0)
    const suggested = remaining > 0 ? remaining : baseValue
    return suggested > 0 ? suggested.toFixed(2) : ''
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

function resolveRedemptionDateForWindow(windowContext) {
  const today = parseDate(new Date()) || new Date()
  if (!windowContext) {
    return today
  }
  const start = parseDate(windowContext.start)
  const end = parseDate(windowContext.end)
  let candidate = today
  if (start instanceof Date && !Number.isNaN(start.getTime()) && candidate < start) {
    candidate = start
  }
  if (end instanceof Date && !Number.isNaN(end.getTime())) {
    let lastDay = new Date(end.getTime() - DAY_IN_MS)
    if (start instanceof Date && !Number.isNaN(start.getTime()) && lastDay < start) {
      lastDay = start
    }
    if (candidate > lastDay) {
      candidate = lastDay
    }
  }
  return candidate
}

function handleAddRedemption(payload) {
  const benefit = payload?.benefit || payload
  const cardId = payload?.card?.id || benefit.credit_card_id
  const card = findCard(cardId) || payload?.card || null
  const trackedBenefit = findBenefit(cardId, benefit.id) || benefit
  const windowContext = payload?.window || null
  redemptionModal.open = true
  redemptionModal.mode = 'create'
  redemptionModal.cardId = cardId
  redemptionModal.benefitId = trackedBenefit.id
  redemptionModal.benefit = trackedBenefit
  redemptionModal.redemptionId = null
  redemptionModal.label = trackedBenefit.name || ''
  redemptionModal.amount = resolveDefaultRedemptionAmount(trackedBenefit, windowContext)
  const defaultDate = resolveRedemptionDateForWindow(windowContext)
  redemptionModal.occurred_on = formatDateInput(defaultDate)
  redemptionModal.card = card
  redemptionModal.markComplete =
    trackedBenefit.type === 'cumulative' ? Boolean(trackedBenefit.is_used) : false
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
  redemptionModal.markComplete = false
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
    const isCumulative = redemptionModal.benefit?.type === 'cumulative'
    const markComplete = isCumulative ? Boolean(redemptionModal.markComplete) : null
    const previousCompletion = isCumulative
      ? Boolean(redemptionModal.benefit?.is_used)
      : null
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
    if (markComplete !== null && markComplete !== previousCompletion) {
      await apiClient.put(`/api/benefits/${redemptionModal.benefitId}`, {
        is_used: markComplete
      })
      if (redemptionModal.benefit) {
        redemptionModal.benefit.is_used = markComplete
      }
    }
    await loadCards({ preserveScroll: true })
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
  redemptionModal.markComplete =
    benefit.type === 'cumulative' ? Boolean(benefit.is_used) : false
}

async function handleDeleteRedemption(entry) {
  try {
    await apiClient.delete(`/api/redemptions/${entry.id}`)
    await loadCards({ preserveScroll: true })
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
  historyModal.windowOverride = null
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
  const benefit = findBenefit(cardId, benefitId)
  const confirmed = await requestConfirmation({
    title: 'Confirm benefit update',
    message: benefit
      ? `Save changes to "${benefit.name}"?`
      : 'Save changes to this benefit?',
    confirmLabel: 'Save changes'
  })
  if (!confirmed) {
    return
  }
  try {
    const body = { ...payload }
    if (body.value === undefined) {
      delete body.value
    }
    await apiClient.put(`/api/benefits/${benefitId}`, body)
    await loadCards({ preserveScroll: true })
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
  editCardModal.form.is_cancelled = Boolean(card.is_cancelled)
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
  editCardModal.form.is_cancelled = false
}

function resetExportTemplateModal() {
  exportTemplateModal.cardId = null
  exportTemplateModal.card = null
  exportTemplateModal.loading = false
  exportTemplateModal.error = ''
  exportTemplateModal.success = ''
  exportTemplateModal.form.card_type = ''
  exportTemplateModal.form.company_name = ''
  exportTemplateModal.form.annual_fee = ''
  exportTemplateModal.form.slug = ''
  exportTemplateModal.form.override_existing = false
  exportTemplateModal.form.override_slug = ''
}

function handleExportTemplate(card) {
  resetExportTemplateModal()
  exportTemplateModal.open = true
  exportTemplateModal.cardId = card.id
  exportTemplateModal.card = card
  exportTemplateModal.form.card_type = card.card_name || ''
  exportTemplateModal.form.company_name = card.company_name || ''
  exportTemplateModal.form.annual_fee = Number(card.annual_fee || 0).toString()
}

function closeExportTemplateModal() {
  exportTemplateModal.open = false
  resetExportTemplateModal()
}

async function submitExportTemplate() {
  if (!exportTemplateModal.cardId) {
    return
  }
  exportTemplateModal.error = ''
  exportTemplateModal.success = ''
  const cardType = exportTemplateModal.form.card_type.trim()
  const company = exportTemplateModal.form.company_name.trim()
  const slug = exportTemplateModal.form.slug.trim()
  const overrideExisting = Boolean(exportTemplateModal.form.override_existing)
  if (!cardType || !company) {
    exportTemplateModal.error = 'Provide a template name and company.'
    return
  }
  const feeInput = (exportTemplateModal.form.annual_fee || '').toString().trim()
  const parsedFee = Number(feeInput || 0)
  if (Number.isNaN(parsedFee) || parsedFee < 0) {
    exportTemplateModal.error = 'Enter a valid annual fee that is zero or greater.'
    return
  }
  const payload = {
    card_type: cardType,
    company_name: company,
    annual_fee: parsedFee,
    override_existing: overrideExisting
  }
  if (slug) {
    payload.slug = slug
  }
  if (overrideExisting) {
    const overrideSlug = exportTemplateModal.form.override_slug
    if (!overrideSlug) {
      exportTemplateModal.error = 'Select the template you want to replace.'
      return
    }
    payload.override_slug = overrideSlug
  }
  exportTemplateModal.loading = true
  try {
    const response = await apiClient.post(
      `/api/cards/${exportTemplateModal.cardId}/export-template`,
      payload
    )
    exportTemplateModal.success = `Template saved as ${response.data?.slug || 'template'}.`
    await loadPreconfiguredCards()
  } catch (err) {
    exportTemplateModal.error = extractErrorMessage(
      err,
      'Unable to export this card as a template.'
    )
  } finally {
    exportTemplateModal.loading = false
  }
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
  const card = findCard(editCardModal.cardId)
  const confirmed = await requestConfirmation({
    title: 'Confirm card update',
    message: card
      ? `Save changes to ${card.card_name}?`
      : 'Save changes to this card?',
    confirmLabel: 'Save card'
  })
  if (!confirmed) {
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
      year_tracking_mode: editCardModal.form.year_tracking_mode,
      is_cancelled: Boolean(editCardModal.form.is_cancelled)
    }
    await apiClient.put(`/api/cards/${editCardModal.cardId}`, payload)
    await loadCards({ preserveScroll: true })
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
  benefitWindowsModal.deletedWindows = []
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
  benefitWindowsModal.deletedWindows = []
}

function handleRedeemWindow(window) {
  if (!benefitWindowsModal.benefit) {
    return
  }
  handleAddRedemption({
    card: benefitWindowsModal.card,
    benefit: benefitWindowsModal.benefit,
    window
  })
}

async function handleEditWindowRedemptions(window) {
  if (!benefitWindowsModal.cardId || !benefitWindowsModal.benefitId) {
    return
  }
  const card = benefitWindowsModal.card || findCard(benefitWindowsModal.cardId)
  const benefit =
    benefitWindowsModal.benefit ||
    findBenefit(benefitWindowsModal.cardId, benefitWindowsModal.benefitId)
  if (!benefit) {
    return
  }
  historyModal.open = true
  historyModal.cardId = benefitWindowsModal.cardId
  historyModal.benefitId = benefit.id
  historyModal.benefit = benefit
  historyModal.entries = []
  historyModal.windowLabel = ''
  historyModal.windowRange = null
  historyModal.windowOverride = {
    label: window.label,
    start: window.start,
    end: window.end,
    index: typeof window.index === 'number' ? window.index : null
  }
  historyModal.loading = true
  try {
    await populateHistoryModal(card, benefit, {
      windowOverride: historyModal.windowOverride
    })
  } catch (err) {
    error.value = 'Unable to load redemption history.'
  } finally {
    historyModal.loading = false
  }
}

async function handleDeleteWindow(window) {
  if (!benefitWindowsModal.benefitId) {
    return
  }
  const confirmed = await requestConfirmation({
    title: 'Delete window',
    message: `Exclude "${window.label}" from tracking? This removes the window from progress and history calculations.`,
    confirmLabel: 'Delete window'
  })
  if (!confirmed) {
    return
  }
  try {
    await apiClient.post(`/api/benefits/${benefitWindowsModal.benefitId}/window-deletions`, {
      window_start: formatDateInput(window.start),
      window_end: formatDateInput(window.end),
      window_index: typeof window.index === 'number' ? window.index : null,
      window_label: window.label
    })
    await loadCards({ preserveScroll: true })
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to delete the window.'
  }
}

async function handleRestoreWindow(exclusion) {
  const confirmed = await requestConfirmation({
    title: 'Restore window',
    message: 'Restore this window to tracking and recalculations?',
    confirmLabel: 'Restore window'
  })
  if (!confirmed) {
    return
  }
  try {
    await apiClient.delete(`/api/window-deletions/${exclusion.id}`)
    await loadCards({ preserveScroll: true })
    await refreshOpenModals()
  } catch (err) {
    error.value = 'Unable to restore the window.'
  }
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

function normaliseWindowExclusions(exclusions) {
  if (!Array.isArray(exclusions)) {
    return []
  }
  return exclusions
    .map((exclusion) => {
      const start = parseDate(exclusion.window_start)
      const end = parseDate(exclusion.window_end)
      return {
        ...exclusion,
        window_start: start,
        window_end: end
      }
    })
    .filter(
      (item) => item.window_start instanceof Date && item.window_end instanceof Date
    )
    .sort(
      (a, b) =>
        (a.window_start?.getTime() || 0) - (b.window_start?.getTime() || 0)
    )
}

function isWindowExcluded(window, exclusions) {
  if (!Array.isArray(exclusions) || !exclusions.length) {
    return false
  }
  return exclusions.some((exclusion) => {
    if (
      typeof exclusion.window_index === 'number' &&
      typeof window.index === 'number' &&
      exclusion.window_index === window.index
    ) {
      return true
    }
    if (
      exclusion.window_start instanceof Date &&
      exclusion.window_end instanceof Date &&
      window.start instanceof Date &&
      window.end instanceof Date &&
      exclusion.window_start.getTime() === window.start.getTime() &&
      exclusion.window_end.getTime() === window.end.getTime()
    ) {
      return true
    }
    if (exclusion.window_label && exclusion.window_label === window.label) {
      return true
    }
    return false
  })
}

async function fetchBenefitRedemptions(benefitId) {
  const response = await apiClient.get(`/api/benefits/${benefitId}/redemptions`)
  return Array.isArray(response.data) ? response.data : []
}

function resolveHistoryWindowSelection(windows, override) {
  if (!Array.isArray(windows) || windows.length === 0) {
    return null
  }
  if (!override) {
    const today = new Date()
    return (
      windows.find((window) => isWithinRange(today, window.start, window.end)) ||
      windows[windows.length - 1] ||
      null
    )
  }
  const overrideStart = parseDate(override.start)
  const overrideEnd = parseDate(override.end)
  const matchedWindow = windows.find((window) => {
    if (typeof override.index === 'number' && typeof window.index === 'number') {
      return window.index === override.index
    }
    const sameStart = overrideStart && window.start.getTime() === overrideStart.getTime()
    const sameEnd = overrideEnd && window.end.getTime() === overrideEnd.getTime()
    if (sameStart && sameEnd) {
      return true
    }
    return override.label ? window.label === override.label : false
  })
  if (matchedWindow) {
    return matchedWindow
  }
  if (overrideStart && overrideEnd) {
    return {
      start: overrideStart,
      end: overrideEnd,
      label: override.label || formatCycleRange(overrideStart, overrideEnd),
      index: override.index ?? null
    }
  }
  return null
}

async function populateHistoryModal(card, benefit, options = {}) {
  const resolvedCard = card || findCard(benefit.credit_card_id)
  if (!resolvedCard) {
    historyModal.entries = []
    historyModal.windowLabel = ''
    historyModal.windowRange = null
    historyModal.windowOverride = null
    return
  }
  const cycle = computeBenefitCycle(resolvedCard, benefit)
  const windows = computeFrequencyWindows(cycle, benefit.frequency)
  const override = options.windowOverride ?? historyModal.windowOverride
  const selectedWindow = resolveHistoryWindowSelection(windows, override)
  historyModal.windowRange = selectedWindow
  historyModal.windowLabel = selectedWindow ? selectedWindow.label : ''
  historyModal.windowOverride = override ?? null
  const entries = await fetchBenefitRedemptions(benefit.id)
  historyModal.entries = selectedWindow?.start && selectedWindow?.end
    ? entries.filter((entry) =>
        isWithinRange(entry.occurred_on, selectedWindow.start, selectedWindow.end)
      )
    : entries
}

async function populateBenefitWindows(card, benefit) {
  const resolvedCard = card || findCard(benefit.credit_card_id)
  if (!resolvedCard) {
    benefitWindowsModal.windows = []
    benefitWindowsModal.deletedWindows = []
    return
  }
  const cycle = computeBenefitCycle(resolvedCard, benefit)
  const windows = computeFrequencyWindows(cycle, benefit.frequency)
  const entries = await fetchBenefitRedemptions(benefit.id)
  const exclusions = normaliseWindowExclusions(benefit.window_exclusions)
  benefitWindowsModal.deletedWindows = exclusions
  const activeWindows = windows.filter((window) => !isWindowExcluded(window, exclusions))
  benefitWindowsModal.windows = activeWindows.map((window) => {
    const windowEntries = entries.filter((entry) =>
      isWithinRange(entry.occurred_on, window.start, window.end)
    )
    const total = windowEntries.reduce((acc, entry) => acc + Number(entry.amount), 0)
    const windowIndex = typeof window.index === 'number' ? window.index : windows.indexOf(window) + 1
    const targetValue = getWindowValueForIndex(benefit, windowIndex)
    const windowTarget = Number.isFinite(targetValue) ? targetValue : 0
    const remaining =
      benefit.type === 'incremental'
        ? Math.max(windowTarget - total, 0)
        : null
    const usedAt =
      benefit.type === 'standard' && benefit.used_at ? parseDate(benefit.used_at) : null
    const redeemed =
      (benefit.type === 'standard' &&
        ((usedAt && isWithinRange(usedAt, window.start, window.end)) || total > 0)) ||
      (benefit.type === 'incremental' && total > 0)
    return {
      label: window.label,
      start: window.start,
      end: window.end,
      index: windowIndex,
      targetValue: windowTarget,
      entries: windowEntries,
      total,
      remaining,
      redeemed
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
        await populateHistoryModal(card, benefit, {
          windowOverride: historyModal.windowOverride
        })
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
  historyModal.windowOverride = null
}

onMounted(async () => {
  await loadInterfaceSettings()
  await loadNotificationSettings()
  await loadBackupSettings()
  await loadFrequencies()
  await loadPreconfiguredCards()
  await loadCards({ preserveScroll: false })
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
              v-if="showNewCardButton"
              class="primary-button"
              type="button"
              @click="showCardModal = true"
            >
              New card
            </button>
            <button
              v-else-if="showAdminTemplateButton"
              class="primary-button"
              type="button"
              @click="openAdminCreateModal"
            >
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
      <div class="nav-drawer__footer">
        <button
          class="theme-toggle"
          type="button"
          role="switch"
          :aria-checked="isDarkMode"
          :aria-label="themeToggleLabel"
          :disabled="isThemeToggleDisabled"
          @click="toggleThemeMode"
        >
          <span class="theme-toggle__icon" aria-hidden="true">
            <svg
              v-if="isDarkMode"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                d="M17.25 12.5a6.75 6.75 0 0 1-6.75 6.75a6.74 6.74 0 0 1-6.55-5.27a.75.75 0 0 1 1.14-.79a4.5 4.5 0 0 0 5.98-5.98a.75.75 0 0 1-.79-1.14a6.74 6.74 0 0 1 7.44 10.43Z"
              />
            </svg>
            <svg
              v-else
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                d="M10 4.5a.75.75 0 0 1 .75-.75h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 10 4.5Zm5.5 5.5a.75.75 0 0 1 .75-.75v-.5a.75.75 0 0 1 1.5 0v.5a.75.75 0 0 1-.75.75Zm-5.5 5.5a.75.75 0 0 1 .75.75v.5a.75.75 0 0 1-1.5 0v-.5a.75.75 0 0 1 .75-.75Zm-5.5-5.5a.75.75 0 0 1-.75.75h-.5a.75.75 0 0 1 0-1.5h.5a.75.75 0 0 1 .75.75Zm9.22-3.97a.75.75 0 1 1 1.06-1.06l.36.36a.75.75 0 1 1-1.06 1.06Zm0 7.94a.75.75 0 1 1 1.06 1.06l-.36.36a.75.75 0 1 1-1.06-1.06Zm-7.94 0a.75.75 0 0 1 0 1.06l-.36.36a.75.75 0 0 1-1.06-1.06l.36-.36a.75.75 0 0 1 1.06 0Zm0-7.94l-.36-.36a.75.75 0 0 1 1.06-1.06l.36.36a.75.75 0 1 1-1.06 1.06ZM10 6.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 0 0 0-7Z"
              />
            </svg>
          </span>
          <span class="theme-toggle__labels">
            <span class="theme-toggle__status">{{ themeStatusLabel }}</span>
            <span class="theme-toggle__hint">{{ themeToggleHint }}</span>
          </span>
          <span
            class="theme-toggle__switch"
            :class="{ 'theme-toggle__switch--on': isDarkMode }"
            aria-hidden="true"
          >
            <span class="theme-toggle__thumb"></span>
          </span>
        </button>
        <p v-if="interfaceSettingsError" class="theme-toggle__error">
          {{ interfaceSettingsError }}
        </p>
      </div>
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
            <div class="section-header">
              <div>
                <h2 class="section-title">Your cards</h2>
              </div>
              <div v-if="!loading && cards.length" class="section-actions">
                <button
                  class="primary-button secondary"
                  type="button"
                  :disabled="cards.length < 2"
                  @click="openCardSortModal"
                >
                  Sort cards
                </button>
              </div>
            </div>
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
              @export-template="handleExportTemplate"
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
              <div class="section-actions">
                <input
                  v-model="benefitSearchQuery"
                  type="search"
                  class="section-search-input"
                  placeholder="Search benefits"
                  aria-label="Search benefits"
                />
              </div>
            </div>
            <p v-if="loading" class="empty-state">Loading benefits...</p>
            <p v-else-if="!benefitsCollection.length" class="empty-state">
              No benefits to display yet. Add benefits to your cards to see them here.
            </p>
            <p
              v-else-if="benefitsCollection.length && !filteredBenefitsCollection.length"
              class="empty-state"
            >
              No benefits match your search.
            </p>
          </div>
          <div
            v-if="!loading && filteredBenefitsCollection.length"
            class="benefits-collection content-constrained"
          >
            <div class="benefits-collection-grid">
              <BenefitCard
                v-for="entry in filteredBenefitsCollection"
                :key="entry.benefit.id"
                :benefit="entry.benefit"
                :card-context="entry.card"
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

      <template v-else-if="isBenefitsAnalysisView">
        <section class="cards-section analysis-section">
          <div class="content-constrained">
            <div class="section-header">
              <div>
                <h2 class="section-title">Benefits analysis</h2>
                <p class="section-description">
                  Explore annual fee trends and benefit performance across your cards.
                </p>
              </div>
              <div
                v-if="benefitsAnalysisState.loading"
                class="analysis-status helper-text subtle-text"
              >
                Loading analysis…
              </div>
            </div>
            <p v-if="benefitsAnalysisState.error" class="helper-text error-text">
              {{ benefitsAnalysisState.error }}
            </p>
            <p v-else-if="benefitsAnalysisState.warning" class="helper-text warning-text">
              {{ benefitsAnalysisState.warning }}
            </p>
            <p v-if="!benefitsAnalysisHasCards" class="empty-state">
              Add cards to view the benefits analysis.
            </p>
          </div>
          <div v-if="benefitsAnalysisHasCards" class="analysis-grid content-constrained">
            <article
              class="section-card analysis-card"
              :style="analysisCardUnits(1, 2)"
            >
              <header class="analysis-card__header">
                <h3 class="analysis-card__title">Annual fee total</h3>
                <p class="analysis-card__subtitle">
                  Combined annual fees across all active cards.
                </p>
              </header>
              <div class="analysis-highlight">
                ${{ benefitsAnalysisTotals.annualFees.toFixed(2) }}
              </div>
            </article>

            <article
              class="section-card analysis-card analysis-card--visual"
              :style="analysisCardUnits(3, 4)"
            >
              <header class="analysis-card__header">
                <h3 class="analysis-card__title">Annual fees by card</h3>
                <p class="analysis-card__subtitle">
                  Distribution of annual fees across your portfolio.
                </p>
              </header>
              <div
                v-if="benefitsAnalysisFeePieChart.series.length"
                class="analysis-card__visual"
              >
                <DrilldownPieChart
                  :series="benefitsAnalysisFeePieChart.series"
                  :drilldown-series="benefitsAnalysisFeePieChart.drilldown"
                  aria-label="Annual fees by card"
                />
              </div>
              <p v-else class="analysis-empty">No annual fees recorded yet.</p>
            </article>

            <article
              class="section-card analysis-card analysis-card--visual"
              :style="analysisCardUnits(2, 6)"
            >
              <header class="analysis-card__header">
                <h3 class="analysis-card__title">Annual fee timeline</h3>
                <p class="analysis-card__subtitle">
                  When annual fees are due throughout the year.
                </p>
              </header>
              <TimelineBarChart
                :data="benefitsAnalysisMonthlyFeeTimeline"
                aria-label="Annual fee amounts by month"
              />
            </article>

            <article
              class="section-card analysis-card"
              :style="analysisCardUnits(2, 4)"
            >
              <header class="analysis-card__header">
                <h3 class="analysis-card__title">Benefit performance trend</h3>
                <p class="analysis-card__subtitle">
                  Month-by-month view of redeemed benefits versus annual fees.
                </p>
              </header>
              <SimpleLineChart
                :points="benefitsAnalysisLinePoints"
                :series="benefitsAnalysisLineSeries"
                :y-max="benefitsAnalysisLineMax > 0 ? benefitsAnalysisLineMax : null"
                aria-label="Monthly benefits versus annual fees"
              />
            </article>

            <article
              class="section-card analysis-card"
              :style="analysisCardUnits(1, 2)"
            >
              <header class="analysis-card__header">
                <h3 class="analysis-card__title">Portfolio summary</h3>
                <p class="analysis-card__subtitle">
                  Snapshot of benefit value across your active cards.
                </p>
              </header>
              <ul class="analysis-summary">
                <li>
                  <span>Potential value</span>
                  <strong>${{ benefitsAnalysisTotals.potential.toFixed(2) }}</strong>
                </li>
                <li>
                  <span>Utilized value</span>
                  <strong>${{ benefitsAnalysisTotals.utilized.toFixed(2) }}</strong>
                </li>
                <li>
                  <span>Net position</span>
                  <strong
                    :class="
                      benefitsAnalysisTotals.net >= 0
                        ? 'analysis-positive'
                        : 'analysis-negative'
                    "
                  >
                    ${{ benefitsAnalysisTotals.net.toFixed(2) }}
                  </strong>
                </li>
                <li>
                  <span>Missed value this cycle</span>
                  <strong>${{ benefitsAnalysisMissedValue.toFixed(2) }}</strong>
                </li>
              </ul>
            </article>

            <article
              class="section-card analysis-card"
              :style="analysisCardUnits(1, 3)"
            >
              <header class="analysis-card__header">
                <h3 class="analysis-card__title">Utilization rate by card</h3>
                <p class="analysis-card__subtitle">
                  Redeemed value compared to potential for each card.
                </p>
              </header>
              <div v-if="benefitsAnalysisUtilizationRows.length" class="analysis-utilization-table-wrapper">
                <table class="analysis-utilization-table">
                  <tbody>
                    <tr v-for="row in benefitsAnalysisUtilizationRows" :key="row.label">
                      <th scope="row">
                        <span class="analysis-utilization-card-name">{{ row.label }}</span>
                      </th>
                      <td>
                        <div
                          class="analysis-utilization-progress"
                          role="img"
                          :aria-label="row.accessibleLabel"
                        >
                          <div class="analysis-utilization-progress__track">
                            <div
                              class="analysis-utilization-progress__fill"
                              :style="{ width: `${row.rate}%` }"
                            ></div>
                          </div>
                        </div>
                      </td>
                      <td class="analysis-utilization-rate">{{ row.formattedRate }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="analysis-empty">No utilization data available.</p>
            </article>

            <article
              class="section-card analysis-card"
              :style="analysisCardUnits(2, 3)"
            >
              <header class="analysis-card__header">
                <h3 class="analysis-card__title">Benefit mix by type</h3>
                <p class="analysis-card__subtitle">
                  Potential value grouped by benefit type.
                </p>
              </header>
              <div class="analysis-card__visual">
                <SimplePieChart
                  :data="benefitsAnalysisBenefitsByType"
                  aria-label="Benefit potential by type"
                />
              </div>
            </article>

            <article
              class="section-card analysis-card"
              :style="analysisCardUnits(1, 2)"
            >
              <header class="analysis-card__header">
                <h3 class="analysis-card__title">Top utilized cards</h3>
                <p class="analysis-card__subtitle">
                  Cards delivering the highest redeemed value this cycle.
                </p>
              </header>
              <SimpleBarChart
                :data="benefitsAnalysisUtilizedByCard"
                aria-label="Utilized benefits by card"
              />
            </article>

          </div>
        </section>
      </template>

      <template v-else-if="isBugTrackerView">
        <BugTracker />
      </template>

      <template v-else>
        <section class="section-card admin-board content-constrained">
          <div class="section-header">
            <div>
              <h2 class="section-title">Home Assistant notifications</h2>
              <p class="section-description">
                Configure the webhook connection used to deliver reminder notifications.
              </p>
            </div>
            <div class="section-actions">
              <button class="link-button" type="button" @click="openNotificationHistory">
                View history
              </button>
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
              <div class="notification-type-settings">
                <p class="field-label">Notification types</p>
                <div class="notification-type-list">
                  <label
                    v-for="option in notificationTypeOptions"
                    :key="option.id"
                    class="checkbox-option notification-type-option"
                  >
                    <input
                      :checked="isNotificationTypeEnabled(option.id)"
                      type="checkbox"
                      @change="setNotificationTypeEnabled(option.id, $event.target.checked)"
                    />
                    <div class="notification-type-copy">
                      <span class="notification-type-label">{{ option.label }}</span>
                      <p class="helper-text subtle-text">{{ option.description }}</p>
                    </div>
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
                      :key="formatNotificationItemKey(category, item)"
                    >
                      {{ formatNotificationItemTitle(item) }}
                      <span v-if="formatNotificationItemDetail(item)">
                        – {{ formatNotificationItemDetail(item) }}
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
                      :key="formatNotificationItemKey(category, item)"
                    >
                      {{ formatNotificationItemTitle(item) }}
                      <span v-if="formatNotificationItemDetail(item)">
                        – {{ formatNotificationItemDetail(item) }}
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
              <h2 class="section-title">Backups</h2>
              <p class="section-description">
                Configure automatic SMB backups and restore the database from saved exports.
              </p>
            </div>
          </div>
          <div v-if="backupSettingsLoading" class="empty-state">
            Loading backup configuration...
          </div>
          <template v-else>
            <div class="backup-grid">
              <form class="backup-settings-form" @submit.prevent="saveBackupSettings">
                <div class="field-group">
                  <input
                    v-model="backupSettings.server"
                    type="text"
                    placeholder="SMB server (e.g., 192.168.1.10)"
                    required
                  />
                  <input
                    v-model="backupSettings.share"
                    type="text"
                    placeholder="Share name (e.g., backups)"
                    required
                  />
                </div>
                <div class="field-group">
                  <input
                    v-model="backupSettings.directory"
                    type="text"
                    placeholder="Folder within the share (optional)"
                  />
                  <input v-model="backupSettings.username" type="text" placeholder="Username" required />
                </div>
                <div class="field-group">
                  <input
                    v-model="backupSettings.domain"
                    type="text"
                    placeholder="Domain or workgroup (optional)"
                  />
                  <input
                    v-model="backupSettings.password"
                    type="password"
                    placeholder="Password"
                    :required="!backupSettingsMeta.has_password"
                  />
                </div>
                <p
                  v-if="backupSettingsMeta.has_password && !backupSettings.password"
                  class="helper-text subtle-text"
                >
                  A password is already stored on the server. Enter a new password to replace it.
                </p>
                <div class="backup-messages">
                  <p v-if="backupSettingsError" class="helper-text error-text">
                    {{ backupSettingsError }}
                  </p>
                  <p v-else-if="backupSettingsSuccess" class="helper-text success-text">
                    {{ backupSettingsSuccess }}
                  </p>
                </div>
                <div class="backup-test-messages">
                  <p v-if="backupTestError" class="helper-text error-text">
                    {{ backupTestError }}
                  </p>
                  <p v-else-if="backupTestMessage" class="helper-text success-text">
                    {{ backupTestMessage }}
                  </p>
                </div>
                <div class="backup-actions">
                  <button
                    class="primary-button secondary"
                    type="button"
                    :disabled="backupTestLoading || backupSettingsSaving"
                    @click="testBackupConnection"
                  >
                    {{ backupTestLoading ? 'Testing…' : 'Test connection' }}
                  </button>
                  <button class="primary-button" type="submit" :disabled="backupSettingsSaving">
                    {{ backupSettingsSaving ? 'Saving…' : 'Save settings' }}
                  </button>
                </div>
              </form>
              <div class="backup-status-card">
                <div class="backup-status-details">
                  <dl class="backup-status-list">
                    <div class="backup-status-entry">
                      <dt>Last backup</dt>
                      <dd>
                        {{
                          backupSettingsMeta.last_backup_at
                            ? formatNotificationTimestamp(backupSettingsMeta.last_backup_at)
                            : 'No backups yet'
                        }}
                      </dd>
                    </div>
                    <div class="backup-status-entry">
                      <dt>Last file</dt>
                      <dd>
                        <span v-if="backupSettingsMeta.last_backup_filename">
                          {{ backupSettingsMeta.last_backup_filename }}
                        </span>
                        <span v-else>–</span>
                      </dd>
                    </div>
                    <div class="backup-status-entry">
                      <dt>Next scheduled</dt>
                      <dd>
                        <span v-if="backupSettingsMeta.next_backup_at">
                          {{ formatNotificationTimestamp(backupSettingsMeta.next_backup_at) }}
                        </span>
                        <span v-else>Waiting for the next change</span>
                      </dd>
                    </div>
                  </dl>
                  <p v-if="backupSettingsMeta.last_backup_error" class="helper-text error-text">
                    Last backup failed: {{ backupSettingsMeta.last_backup_error }}
                  </p>
                  <div class="backup-run-feedback">
                    <p v-if="backupRunError" class="helper-text error-text">
                      {{ backupRunError }}
                    </p>
                    <p v-else-if="backupRunMessage" class="helper-text success-text">
                      {{ backupRunMessage }}
                    </p>
                  </div>
                  <div class="backup-status-actions">
                    <button
                      class="primary-button secondary"
                      type="button"
                      :disabled="backupRunLoading || !backupSettings.id"
                      @click="runBackupNow"
                    >
                      {{ backupRunLoading ? 'Running…' : 'Run backup now' }}
                    </button>
                  </div>
                </div>
                <form class="backup-import-form" @submit.prevent="submitBackupImport">
                  <h3 class="backup-import-title">Import a backup</h3>
                  <p class="helper-text subtle-text">
                    Replace the current database with a saved <code>.db</code> file.
                  </p>
                  <input
                    :key="backupImportInputKey"
                    type="file"
                    accept=".db"
                    @change="handleBackupFileChange"
                  />
                  <p v-if="backupImport.filename" class="helper-text subtle-text">
                    Selected file: {{ backupImport.filename }}
                  </p>
                  <div class="backup-messages">
                    <p v-if="backupImport.error" class="helper-text error-text">
                      {{ backupImport.error }}
                    </p>
                    <p v-else-if="backupImport.success" class="helper-text success-text">
                      {{ backupImport.success }}
                    </p>
                  </div>
                  <div class="backup-import-actions">
                    <button class="primary-button secondary" type="submit" :disabled="backupImport.loading">
                      {{ backupImport.loading ? 'Importing…' : 'Import database' }}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </template>
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

  <BaseModal
    :open="cardSortModal.open"
    title="Sort credit cards"
    @close="closeCardSortModal"
  >
    <p class="helper-text subtle-text">
      Drag and drop the cards below to update their display order.
    </p>
    <ul class="card-sort-list" role="list">
      <li
        v-for="(entry, index) in cardSortModal.order"
        :key="entry.id"
        class="card-sort-item"
        :class="{
          'is-active': cardSortDragState.activeIndex === index,
          'is-over': cardSortDragState.overIndex === index
        }"
        draggable="true"
        :aria-grabbed="cardSortDragState.activeIndex === index ? 'true' : 'false'"
        @dragstart="(event) => handleCardSortDragStart(index, event)"
        @dragenter.prevent="handleCardSortDragEnter(index)"
        @dragover.prevent
        @dragleave="handleCardSortDragLeave(index)"
        @dragend="handleCardSortDragEnd"
        @drop.prevent="handleCardSortDragEnd"
      >
        <span class="card-sort-handle" aria-hidden="true">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <circle cx="6" cy="5" r="1.5" />
            <circle cx="6" cy="10" r="1.5" />
            <circle cx="6" cy="15" r="1.5" />
            <circle cx="14" cy="5" r="1.5" />
            <circle cx="14" cy="10" r="1.5" />
            <circle cx="14" cy="15" r="1.5" />
          </svg>
        </span>
        <span class="card-sort-index">{{ index + 1 }}</span>
        <span class="card-sort-name">{{ entry.card_name }}</span>
        <span class="sr-only">Drag to reorder</span>
      </li>
    </ul>
    <p v-if="cardSortModal.error" class="helper-text error-text">{{ cardSortModal.error }}</p>
    <template #footer>
      <button class="primary-button secondary" type="button" @click="closeCardSortModal">
        Cancel
      </button>
      <button
        class="primary-button"
        type="button"
        :disabled="cardSortModal.saving"
        @click="submitCardSortOrder"
      >
        {{ cardSortModal.saving ? 'Saving…' : 'Save order' }}
      </button>
    </template>
  </BaseModal>

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
      <label class="checkbox-option">
        <input v-model="editCardModal.form.is_cancelled" type="checkbox" />
        <span>Cancel card</span>
      </label>
      <div class="modal-actions">
        <button class="primary-button secondary" type="button" @click="closeEditCardModal">Cancel</button>
        <button class="primary-button" type="submit">Save changes</button>
      </div>
    </form>
  </BaseModal>

  <BaseModal
    :open="exportTemplateModal.open"
    title="Export as template"
    @close="closeExportTemplateModal"
  >
    <form @submit.prevent="submitExportTemplate">
      <p class="helper-text subtle-text">
        Copy this card's benefits into a reusable template. History entries are excluded.
      </p>
      <div class="field-group">
        <input
          v-model="exportTemplateModal.form.card_type"
          type="text"
          placeholder="Template card name"
          required
        />
        <input
          v-model="exportTemplateModal.form.company_name"
          type="text"
          placeholder="Company name"
          required
        />
      </div>
      <div class="field-group">
        <input
          v-model="exportTemplateModal.form.annual_fee"
          type="number"
          min="0"
          step="0.01"
          placeholder="Annual fee"
          required
        />
        <input
          v-model="exportTemplateModal.form.slug"
          type="text"
          placeholder="Slug (optional)"
        />
      </div>
      <label class="checkbox-option">
        <input v-model="exportTemplateModal.form.override_existing" type="checkbox" />
        <span>Override an existing template</span>
      </label>
      <div v-if="exportTemplateModal.form.override_existing" class="field-group">
        <select v-model="exportTemplateModal.form.override_slug" required>
          <option value="" disabled>Select a template to replace</option>
          <option v-for="card in preconfiguredCards" :key="card.slug" :value="card.slug">
            {{ card.card_type }} ({{ card.slug }})
          </option>
        </select>
      </div>
      <p v-if="exportTemplateModal.error" class="helper-text error-text">
        {{ exportTemplateModal.error }}
      </p>
      <p v-else-if="exportTemplateModal.success" class="helper-text success-text">
        {{ exportTemplateModal.success }}
      </p>
      <div class="modal-actions">
        <button class="primary-button secondary" type="button" @click="closeExportTemplateModal">
          Cancel
        </button>
        <button class="primary-button" type="submit" :disabled="exportTemplateModal.loading">
          {{ exportTemplateModal.loading ? 'Saving…' : 'Save template' }}
        </button>
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
    :z-index="1200"
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
      <label
        v-if="redemptionModal.benefit?.type === 'cumulative'"
        class="checkbox-option redemption-complete-toggle"
      >
        <input v-model="redemptionModal.markComplete" type="checkbox" />
        <span>Mark benefit complete for this cycle</span>
      </label>
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
    :z-index="1100"
    @close="closeHistoryModal"
  >
    <div v-if="historyModal.loading" class="history-loading">Loading history...</div>
    <template v-else>
      <h3 class="history-section-title">History</h3>
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
      <article
        v-for="window in benefitWindowsModal.windows"
        :key="window.label"
        :class="['window-card', { 'window-card--redeemed': window.redeemed }]"
      >
        <div class="window-card__header">
          <div class="window-card__info">
            <h3 class="window-title">{{ window.label }}</h3>
            <p class="window-range">{{ formatCycleRange(window.start, window.end) }}</p>
          </div>
          <div class="window-card__actions">
            <button
              class="icon-button ghost"
              type="button"
              title="Edit window redemptions"
              @click="handleEditWindowRedemptions(window)"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  d="M15.58 2.42a1.5 1.5 0 0 0-2.12 0l-9 9V17h5.59l9-9a1.5 1.5 0 0 0 0-2.12zM7 15H5v-2l6.88-6.88 2 2z"
                />
              </svg>
              <span class="sr-only">Edit window redemptions</span>
            </button>
            <button
              class="icon-button danger"
              type="button"
              title="Delete window"
              @click="handleDeleteWindow(window)"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  d="M7 3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1h3.5a.5.5 0 0 1 0 1h-.8l-.62 11a2 2 0 0 1-2 1.9H6.92a2 2 0 0 1-2-1.9L4.3 5H3.5a.5.5 0 0 1 0-1H7zm1 1h4V3H8zM6.3 5l.6 10.8a1 1 0 0 0 1 1h4.2a1 1 0 0 0 1-1L13.7 5z"
                />
              </svg>
              <span class="sr-only">Delete window</span>
            </button>
          </div>
        </div>
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
        <div class="window-card__footer">
          <button class="primary-button small" type="button" @click="handleRedeemWindow(window)">
            Redeem
          </button>
        </div>
      </article>
    </div>
    <div v-if="benefitWindowsModal.deletedWindows.length" class="window-deleted">
      <h3 class="window-deleted__title">Deleted windows</h3>
      <ul class="window-deleted__list">
        <li
          v-for="exclusion in benefitWindowsModal.deletedWindows"
          :key="exclusion.id"
          class="window-deleted__item"
        >
          <span class="window-deleted__label">
            {{
              exclusion.window_label ||
                formatCycleRange(exclusion.window_start, exclusion.window_end)
            }}
          </span>
          <button class="link-button" type="button" @click="handleRestoreWindow(exclusion)">
            Restore
          </button>
        </li>
      </ul>
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
        <div v-for="benefit in adminModal.form.benefits" :key="benefit.id" class="admin-benefit-card">
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
          <div
            v-if="supportsAlignmentOverride(benefit.frequency)"
            class="field-group admin-benefit-alignment"
          >
            <select v-model="benefit.window_tracking_mode">
              <option value="">Match card cycle</option>
              <option value="calendar">Calendar year</option>
              <option value="anniversary">Align with AF year</option>
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
          <label class="checkbox-option admin-benefit-exclude">
            <input v-model="benefit.exclude_from_benefits_page" type="checkbox" />
            <span>Hide from benefits overview</span>
          </label>
          <label class="checkbox-option admin-benefit-exclude">
            <input v-model="benefit.exclude_from_notifications" type="checkbox" />
            <span>Exclude from notifications</span>
          </label>
          <p class="helper-text">{{ benefitTypeDescriptions[benefit.type] }}</p>
          <div class="admin-benefit-card__footer">
            <button
              class="icon-button danger admin-benefit-card__remove"
              type="button"
              title="Remove benefit"
              @click="removeAdminBenefit(benefit.id)"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  d="M5.5 5.5a.75.75 0 0 1 1.06 0L10 8.94l3.44-3.44a.75.75 0 1 1 1.06 1.06L11.06 10l3.44 3.44a.75.75 0 0 1-1.06 1.06L10 11.06l-3.44 3.44a.75.75 0 0 1-1.06-1.06L8.94 10 5.5 6.56a.75.75 0 0 1 0-1.06z"
                />
              </svg>
              <span class="sr-only">Remove benefit</span>
            </button>
          </div>
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

  <BaseModal
    :open="notificationHistoryModal.open"
    title="Notification history"
    @close="closeNotificationHistory"
  >
    <div v-if="notificationHistoryModal.loading" class="history-loading">Loading history...</div>
    <p v-else-if="notificationHistoryModal.error" class="helper-text error-text">
      {{ notificationHistoryModal.error }}
    </p>
    <div v-else class="notification-history-content">
      <div class="notification-history-toolbar">
        <form class="notification-history-search" @submit.prevent="applyNotificationHistorySearch">
          <input
            v-model="notificationHistoryModal.search"
            type="search"
            placeholder="Search notifications"
            :disabled="notificationHistoryModal.loading"
          />
          <button class="primary-button secondary" type="submit" :disabled="notificationHistoryModal.loading">
            Search
          </button>
          <button
            v-if="notificationHistoryModal.search"
            class="link-button"
            type="button"
            :disabled="notificationHistoryModal.loading"
            @click="clearNotificationHistorySearch"
          >
            Clear
          </button>
        </form>
        <button
          class="link-button"
          type="button"
          :disabled="notificationHistoryModal.loading"
          @click="toggleNotificationHistorySort"
        >
          Sort:
          {{ notificationHistoryModal.sortDirection === 'desc' ? 'Newest first' : 'Oldest first' }}
        </button>
      </div>
      <div v-if="notificationHistoryModal.entries.length" class="notification-history-table-wrapper">
        <table class="notification-history-table">
          <thead>
            <tr>
              <th scope="col">Sent at</th>
              <th scope="col">Type</th>
              <th scope="col">Title</th>
              <th scope="col">Target</th>
              <th scope="col">Status</th>
              <th scope="col">Reason</th>
              <th scope="col">Details</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in notificationHistoryModal.entries" :key="entry.id">
              <td>{{ formatNotificationTimestamp(entry.created_at) || '–' }}</td>
              <td>{{ formatNotificationEventType(entry.event_type) || '–' }}</td>
              <td>{{ entry.title || '–' }}</td>
              <td>{{ entry.target || '–' }}</td>
              <td>
                <span :class="['status-pill', entry.sent ? 'success' : 'error']">
                  {{ entry.sent ? 'Delivered' : 'Not sent' }}
                </span>
              </td>
              <td>{{ entry.reason || '–' }}</td>
              <td>{{ entry.response_message || '–' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="empty-state">
        {{
          notificationHistoryModal.search
            ? 'No notifications match the current search.'
            : 'No notifications have been recorded yet.'
        }}
      </p>
    </div>
    <template #footer>
      <button class="primary-button secondary" type="button" @click="closeNotificationHistory">
        Close
      </button>
    </template>
  </BaseModal>

  <BaseModal
    :open="confirmDialog.open"
    :title="confirmDialog.title"
    @close="handleConfirmDialogClose"
  >
    <p>{{ confirmDialog.message }}</p>
    <template #footer>
      <button class="primary-button secondary" type="button" @click="confirmDialogCancel">
        {{ confirmDialog.cancelLabel }}
      </button>
      <button class="primary-button" type="button" @click="confirmDialogConfirm">
        {{ confirmDialog.confirmLabel }}
      </button>
    </template>
  </BaseModal>
</template>

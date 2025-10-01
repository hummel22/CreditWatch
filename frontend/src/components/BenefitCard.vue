<script setup>
import { computed } from 'vue'

import { parseDate } from '../utils/dates'

const props = defineProps({
  benefit: {
    type: Object,
    required: true
  },
  cardContext: {
    type: Object,
    default: null
  },
  showEdit: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits([
  'toggle',
  'delete',
  'add-redemption',
  'view-history',
  'edit',
  'view-windows'
])

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const isCurrentWindowDeleted = computed(() =>
  Boolean(props.benefit.current_window_deleted)
)

const displayName = computed(() => {
  const rawName = typeof props.benefit.name === 'string' ? props.benefit.name : ''
  const cardName = props.cardContext?.card_name
  if (!rawName || typeof cardName !== 'string') {
    return rawName
  }
  const trimmedCardName = cardName.trim()
  if (!trimmedCardName) {
    return rawName
  }
  const pattern = new RegExp(`\\s*\\(${escapeRegExp(trimmedCardName)}\\)\\s*$`)
  return rawName.replace(pattern, '').trim()
})

const typeLabel = computed(() => {
  const type = props.benefit.type || 'standard'
  return type.charAt(0).toUpperCase() + type.slice(1)
})

const statusTag = computed(() => {
  if (isCurrentWindowDeleted.value) {
    return { label: 'Window deleted', tone: 'warning' }
  }
  const type = props.benefit.type
  if (type === 'standard') {
    return props.benefit.is_used
      ? { label: 'Utilized', tone: 'success' }
      : { label: 'Available', tone: 'warning' }
  }
  if (type === 'incremental') {
    const used = Number(props.benefit.current_window_total ?? 0)
    const target = Number(
      props.benefit.current_window_value ?? props.benefit.value ?? 0
    )
    if (used >= target && target > 0) {
      return { label: 'Completed', tone: 'success' }
    }
    if (used > 0) {
      return { label: 'In progress', tone: 'info' }
    }
    return { label: 'Not started', tone: 'warning' }
  }
  if (type === 'cumulative' && props.benefit.is_used) {
    return { label: 'Complete', tone: 'success' }
  }
  return { label: 'Tracking', tone: 'info' }
})

const frequencyLabel = computed(() => {
  const frequency = props.benefit.frequency
  if (!frequency) {
    return ''
  }
  return frequency.charAt(0).toUpperCase() + frequency.slice(1)
})

const currentWindowLabel = computed(() => props.benefit.current_window_label || '')

function resolveCalendarExpiration(benefit, cardContext) {
  const frequency = benefit?.frequency
  const trackingMode =
    benefit?.window_tracking_mode || cardContext?.year_tracking_mode || 'calendar'
  if (trackingMode !== 'calendar') {
    return null
  }
  const baseDate = parseDate(benefit?.expiration_date)
  if (!(baseDate instanceof Date)) {
    return null
  }
  if (baseDate.getDate() !== 1) {
    return null
  }
  const month = baseDate.getMonth()
  const shouldAdjust =
    frequency === 'monthly' ||
    (frequency === 'quarterly' && month % 3 === 0) ||
    (frequency === 'semiannual' && month % 6 === 0) ||
    (frequency === 'yearly' && month === 0)
  if (!shouldAdjust) {
    return null
  }
  const adjusted = new Date(baseDate)
  adjusted.setDate(adjusted.getDate() - 1)
  return adjusted
}

const expirationLabel = computed(() => {
  if (!props.benefit.expiration_date) {
    return 'No expiration set'
  }
  const adjusted = resolveCalendarExpiration(props.benefit, props.cardContext)
  const displayDate = adjusted ?? parseDate(props.benefit.expiration_date)
  if (!(displayDate instanceof Date)) {
    return 'No expiration set'
  }
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  }).format(displayDate)
})

const missedWindowValue = computed(() => {
  if (!['standard', 'incremental'].includes(props.benefit.type)) {
    return 0
  }
  const raw = Number(props.benefit.missed_window_value ?? 0)
  if (!Number.isFinite(raw) || raw <= 0) {
    return 0
  }
  return raw
})

const incrementalProgress = computed(() => {
  if (props.benefit.type !== 'incremental') {
    return null
  }
  const used = Number(props.benefit.cycle_redemption_total ?? 0)
  const target = Number(
    props.benefit.cycle_target_value ?? props.benefit.value ?? 0
  )
  const expired = missedWindowValue.value
  const usedPercent = target > 0 ? Math.min((used / target) * 100, 100) : used > 0 ? 100 : 0
  const expiredPercent = target > 0
    ? Math.min((expired / target) * 100, Math.max(100 - usedPercent, 0))
    : 0
  const remaining = Math.max(target - used - expired, 0)
  const remainingPercent = target > 0
    ? Math.max(100 - usedPercent - expiredPercent, 0)
    : 0
  const accessibleParts = [`Used $${used.toFixed(2)} of $${target.toFixed(2)}`]
  if (remaining > 0) {
    accessibleParts.push(`Remaining $${remaining.toFixed(2)}`)
  }
  if (expired > 0) {
    accessibleParts.push(`Expired $${expired.toFixed(2)}`)
  }
  return {
    used,
    target,
    remaining,
    usedPercent,
    remainingPercent,
    expiredPercent,
    expired,
    accessibleLabel: accessibleParts.join(' · ')
  }
})

const redemptionSummary = computed(() => {
  if (props.benefit.type === 'incremental') {
    return ''
  }
  if (props.benefit.type === 'standard') {
    return ''
  }
  if (props.benefit.type === 'cumulative') {
    return ''
  }
  const value =
    props.benefit.current_window_value != null
      ? Number(props.benefit.current_window_value)
      : Number(props.benefit.value ?? 0)
  return value > 0 ? `Value $${value.toFixed(2)}` : ''
})

const showHistoryButton = computed(
  () => props.benefit.type !== 'standard' || props.benefit.redemption_count > 0
)

const isRecurringBenefit = computed(() =>
  ['monthly', 'quarterly', 'semiannual'].includes(props.benefit.frequency)
)

const currentWindowValue = computed(() => {
  if (props.benefit.current_window_value != null) {
    return Number(props.benefit.current_window_value)
  }
  if (props.benefit.value != null) {
    return Number(props.benefit.value)
  }
  return null
})

const windowValueLabel = computed(() => {
  const value = currentWindowValue.value
  return value != null ? value.toFixed(2) : '0.00'
})

const annualRedeemed = computed(() => Number(props.benefit.cycle_redemption_total ?? 0))

const standardUsage = computed(() => {
  if (props.benefit.type !== 'standard') {
    return null
  }

  const rawTarget =
    props.benefit.cycle_target_value ??
    props.benefit.value ??
    currentWindowValue.value ??
    props.benefit.current_window_value ??
    0
  const target = Number(rawTarget)
  if (!Number.isFinite(target) || target <= 0) {
    return null
  }

  const cycleUsed = Number(props.benefit.cycle_redemption_total ?? 0)
  const expired = Math.min(missedWindowValue.value, target)
  let usedAmount = Math.min(cycleUsed, target)
  if (props.benefit.is_used) {
    usedAmount = Math.max(usedAmount, target - expired)
  }
  const remaining = Math.max(target - usedAmount - expired, 0)
  const usedPercent = target > 0 ? Math.min((usedAmount / target) * 100, 100) : 0
  const expiredPercent =
    target > 0 ? Math.min((expired / target) * 100, Math.max(100 - usedPercent, 0)) : 0
  const remainingPercent = Math.max(100 - usedPercent - expiredPercent, 0)
  const accessibleParts = [`Used $${usedAmount.toFixed(2)} of $${target.toFixed(2)}`]
  accessibleParts.push(`Remaining $${remaining.toFixed(2)}`)
  if (expired > 0) {
    accessibleParts.push(`Expired $${expired.toFixed(2)}`)
  }
  return {
    target,
    used: usedAmount,
    expired,
    remaining,
    usedPercent,
    expiredPercent,
    remainingPercent,
    accessibleLabel: accessibleParts.join(' · ')
  }
})

const windowUsage = computed(() => {
  if (props.benefit.type === 'cumulative') {
    return null
  }
  if (isCurrentWindowDeleted.value) {
    return { remaining: 0, used: 0 }
  }
  if (props.benefit.type === 'standard' && standardUsage.value) {
    return {
      remaining: Math.max(Number(standardUsage.value.remaining ?? 0), 0),
      used: Math.max(Number(standardUsage.value.used ?? 0), 0)
    }
  }
  const baseTarget =
    currentWindowValue.value ??
    Number(
      props.benefit.type === 'incremental'
        ? props.benefit.cycle_target_value ?? props.benefit.value ?? 0
        : props.benefit.value ?? 0
    )
  const target = Number.isFinite(baseTarget) ? Math.max(Number(baseTarget), 0) : null
  const rawUsed =
    props.benefit.type === 'incremental'
      ? Number(
          props.benefit.current_window_total ?? props.benefit.cycle_redemption_total ?? 0
        )
      : Number(props.benefit.current_window_total ?? 0)
  const used = Number.isFinite(rawUsed) ? Math.max(rawUsed, 0) : 0
  if (target === null) {
    return { remaining: 0, used }
  }
  const remaining = Math.max(target - used, 0)
  return { remaining, used }
})

const remainingValueLabel = computed(() => {
  if (props.benefit.type === 'cumulative') {
    if (props.benefit.expected_value != null) {
      return Number(props.benefit.expected_value).toFixed(2)
    }
    return Number(props.benefit.cycle_redemption_total ?? 0).toFixed(2)
  }
  const usage = windowUsage.value
  if (!usage) {
    return windowValueLabel.value
  }
  const remaining = Number(usage.remaining ?? 0)
  return Number.isFinite(remaining) ? remaining.toFixed(2) : windowValueLabel.value
})

const usedValueLabel = computed(() => {
  if (props.benefit.type === 'cumulative') {
    return null
  }
  const usage = windowUsage.value
  if (!usage) {
    return null
  }
  const used = Number(usage.used ?? 0)
  return Number.isFinite(used) ? used.toFixed(2) : '0.00'
})

const showUsedValue = computed(() => {
  if (props.benefit.type === 'cumulative') {
    return false
  }
  return windowUsage.value !== null
})
</script>

<template>
  <article
    class="benefit-card"
    :class="{ used: benefit.is_used, 'window-deleted': isCurrentWindowDeleted }"
  >
    <header class="benefit-header">
      <div class="benefit-header__body">
        <div class="benefit-name">{{ displayName }}</div>
        <div class="benefit-meta">
          <div class="benefit-meta-line">
            <span class="benefit-type">{{ typeLabel }}</span>
            <span v-if="frequencyLabel" class="benefit-frequency">{{ frequencyLabel }}</span>
          </div>
          <span v-if="currentWindowLabel" class="benefit-window">{{ currentWindowLabel }}</span>
        </div>
      </div>
      <div class="benefit-header__aside">
        <div class="benefit-status">
          <div class="tag" :class="statusTag.tone">
            <span>{{ statusTag.label }}</span>
          </div>
          <span class="benefit-year-total">
            Total: <strong class="benefit-amount">${{ annualRedeemed.toFixed(2) }}</strong>
          </span>
        </div>
        <div class="benefit-icons">
          <button
            v-if="isRecurringBenefit"
            class="icon-button ghost"
            type="button"
            @click="emit('view-windows', benefit)"
            title="View recurring history"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M4 16h2V9H4v7zm5 0h2V4H9v12zm5 0h2v-5h-2v5z" />
            </svg>
            <span class="sr-only">View recurring history</span>
          </button>
          <button
            v-if="showEdit"
            class="icon-button ghost"
            type="button"
            @click="emit('edit', benefit)"
            title="Edit benefit"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M15.58 2.42a1.5 1.5 0 0 0-2.12 0l-9 9V17h5.59l9-9a1.5 1.5 0 0 0 0-2.12zM7 15H5v-2l6.88-6.88 2 2z" />
            </svg>
            <span class="sr-only">Edit benefit</span>
          </button>
          <button
            class="icon-button danger"
            type="button"
            @click="emit('delete')"
            title="Remove benefit"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path
                d="M7 3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1h3.5a.5.5 0 0 1 0 1h-.8l-.62 11a2 2 0 0 1-2 1.9H6.92a2 2 0 0 1-2-1.9L4.3 5H3.5a.5.5 0 0 1 0-1H7zm1 1h4V3H8zM6.3 5l.6 10.8a1 1 0 0 0 1 1h4.2a1 1 0 0 0 1-1L13.7 5z"
              />
            </svg>
            <span class="sr-only">Remove benefit</span>
          </button>
        </div>
      </div>
    </header>

    <section class="benefit-body">
      <p v-if="benefit.description">{{ benefit.description }}</p>
      <p class="benefit-expiration">Expires: {{ expirationLabel }}</p>
      <div v-if="incrementalProgress" class="benefit-progress-group">
        <div
          class="benefit-progress-chart"
          role="img"
          :aria-label="incrementalProgress.accessibleLabel"
        >
          <div class="benefit-progress-chart__track">
            <div
              class="benefit-progress-chart__segment benefit-progress-chart__segment--used"
              :style="{ width: `${incrementalProgress.usedPercent}%` }"
              aria-hidden="true"
            ></div>
            <div
              v-if="incrementalProgress.remainingPercent > 0"
              class="benefit-progress-chart__segment benefit-progress-chart__segment--remaining"
              :style="{ width: `${incrementalProgress.remainingPercent}%` }"
              aria-hidden="true"
            ></div>
            <div
              v-if="incrementalProgress.expiredPercent > 0"
              class="benefit-progress-chart__segment benefit-progress-chart__segment--expired"
              :style="{ width: `${incrementalProgress.expiredPercent}%` }"
              aria-hidden="true"
            ></div>
          </div>
        </div>
        <div class="benefit-usage-summary">
          <span class="benefit-usage-summary__title">History</span>
          <div class="benefit-usage-summary__metrics">
            <div class="benefit-usage-summary__metric">
              <span class="benefit-usage-summary__label">Used</span>
              <span class="benefit-usage-summary__value">
                ${{ incrementalProgress.used.toFixed(2) }}
              </span>
            </div>
            <div class="benefit-usage-summary__metric">
              <span class="benefit-usage-summary__label">Remaining</span>
              <span class="benefit-usage-summary__value">
                ${{ incrementalProgress.remaining.toFixed(2) }}
              </span>
            </div>
            <div class="benefit-usage-summary__metric">
              <span class="benefit-usage-summary__label">Expired</span>
              <span class="benefit-usage-summary__value">
                ${{ incrementalProgress.expired.toFixed(2) }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <template v-else>
        <p v-if="redemptionSummary" class="benefit-progress">{{ redemptionSummary }}</p>
        <div v-if="standardUsage" class="benefit-progress-group">
          <div
            class="benefit-progress-chart benefit-progress-chart--standard"
            role="img"
            :aria-label="standardUsage.accessibleLabel"
          >
            <div class="benefit-progress-chart__track">
              <div
                class="benefit-progress-chart__segment benefit-progress-chart__segment--used"
                :style="{ width: `${standardUsage.usedPercent}%` }"
                aria-hidden="true"
              ></div>
              <div
                v-if="standardUsage.remainingPercent > 0"
                class="benefit-progress-chart__segment benefit-progress-chart__segment--remaining"
                :style="{ width: `${standardUsage.remainingPercent}%` }"
                aria-hidden="true"
              ></div>
              <div
                v-if="standardUsage.expiredPercent > 0"
                class="benefit-progress-chart__segment benefit-progress-chart__segment--expired"
                :style="{ width: `${standardUsage.expiredPercent}%` }"
                aria-hidden="true"
              ></div>
            </div>
          </div>
          <div class="benefit-usage-summary">
            <span class="benefit-usage-summary__title">History</span>
            <div class="benefit-usage-summary__metrics">
              <div class="benefit-usage-summary__metric">
                <span class="benefit-usage-summary__label">Used</span>
                <span class="benefit-usage-summary__value">
                  ${{ standardUsage.used.toFixed(2) }}
                </span>
              </div>
              <div class="benefit-usage-summary__metric">
                <span class="benefit-usage-summary__label">Remaining</span>
                <span class="benefit-usage-summary__value">
                  ${{ standardUsage.remaining.toFixed(2) }}
                </span>
              </div>
              <div class="benefit-usage-summary__metric">
                <span class="benefit-usage-summary__label">Expired</span>
                <span class="benefit-usage-summary__value">
                  ${{ standardUsage.expired.toFixed(2) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </section>

    <footer class="benefit-footer">
      <div class="benefit-footer__values">
        <strong v-if="benefit.type !== 'cumulative'" class="benefit-amount">
          ${{ remainingValueLabel }}
        </strong>
        <strong v-else class="benefit-amount">
          <template v-if="benefit.expected_value != null">
            ${{ Number(benefit.expected_value).toFixed(2) }}
          </template>
          <template v-else>
            ${{ benefit.cycle_redemption_total.toFixed(2) }}
          </template>
        </strong>
        <span v-if="showUsedValue" class="benefit-used">
          (${{ usedValueLabel }} used)
        </span>
      </div>
      <div class="benefit-actions">
        <button
          v-if="benefit.type === 'standard' && !benefit.is_used"
          class="primary-button"
          type="button"
          @click="emit('add-redemption', benefit)"
          title="Redeem benefit"
        >
          Redeem
        </button>
        <button
          v-else-if="benefit.type !== 'standard'"
          class="primary-button"
          type="button"
          @click="emit('add-redemption', benefit)"
          title="Redeem benefit"
        >
          Redeem
        </button>
        <button
          v-if="showHistoryButton"
          class="icon-button ghost"
          type="button"
          @click="emit('view-history', benefit)"
          title="View history"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path stroke-linecap="round" d="M4 6h12M4 10h12M4 14h12" />
          </svg>
          <span class="sr-only">View history</span>
        </button>
      </div>
    </footer>
  </article>
</template>

<style scoped>

.benefit-icons {
  display: flex;
  gap: 0.3rem;
  align-items: center;
  justify-content: flex-end;
  flex-shrink: 0;
}

.benefit-icons .icon-button {
  width: 1.6rem;
  height: 1.6rem;
}

.benefit-icons .icon-button svg {
  width: 0.9rem;
  height: 0.9rem;
}

.benefit-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.benefit-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  row-gap: 0.75rem;
}

.benefit-header__body {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex: 1;
  min-width: 0;
}

.benefit-name {
  overflow-wrap: anywhere;
}

.benefit-header__aside {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  align-items: flex-end;
  flex-shrink: 0;
}

.benefit-status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.2rem;
  text-align: right;
  min-width: 0;
}

.benefit-status .tag {
  white-space: nowrap;
}

.benefit-year-total {
  font-size: 0.72rem;
  color: #475569;
  font-weight: 500;
}

.benefit-year-total .benefit-amount {
  font-weight: 600;
}

.benefit-meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.75rem;
  color: #475569;
  min-width: 0;
}

.benefit-meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}

.benefit-expiration {
  font-size: 0.85rem;
  margin: 0;
  color: #94a3b8;
}

.benefit-type {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #0ea5e9;
  font-weight: 600;
  font-size: 0.72rem;
}

.benefit-window {
  font-size: 0.72rem;
  color: #64748b;
  font-weight: 500;
  display: block;
}

.benefit-progress {
  font-size: 0.85rem;
  margin: 0.25rem 0 0;
  color: #0f172a;
}

.benefit-progress-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.6rem;
}

.benefit-progress-chart {
  margin: 0;
}


.benefit-progress-chart__track {
  width: 100%;
  height: 0.55rem;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
  display: flex;
}

.benefit-progress-chart__segment {
  height: 100%;
  flex: 0 0 auto;
  transition: width 0.3s ease;
}


.benefit-progress-chart__segment--used {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
}


.benefit-progress-chart__segment--remaining {
  background: #e2e8f0;
}


.benefit-progress-chart__segment--expired {
  background: #b91c1c;
}

.benefit-usage-summary {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.benefit-usage-summary__title {
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.7rem;
  font-weight: 600;
  color: #94a3b8;
}

.benefit-usage-summary__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  text-align: center;
}

.benefit-usage-summary__metric {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.benefit-usage-summary__label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
}

.benefit-usage-summary__value {
  font-size: 0.8rem;
  font-weight: 400;
  color: #475569;
}

.benefit-usage-summary__status {
  align-self: flex-end;
  font-weight: 600;
  font-size: 0.85rem;
  color: #6366f1;
}

.benefit-footer__values {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.benefit-used {
  color: #059669;
  font-weight: 500;
  font-size: 0.8rem;
}

strong {
  font-weight: 700;
  color: inherit;
}

.benefit-amount {
  color: #334155;
  font-weight: 600;
  font-size: 0.9em;
}
</style>

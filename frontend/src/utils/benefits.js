import { parseDate } from './dates'

function getExpirationTime(benefit) {
  if (!benefit || !benefit.expiration_date) {
    return Number.NEGATIVE_INFINITY
  }
  const parsed = parseDate(benefit.expiration_date)
  if (!(parsed instanceof Date) || Number.isNaN(parsed.getTime())) {
    return Number.NEGATIVE_INFINITY
  }
  return parsed.getTime()
}

export function isBenefitCompleted(benefit) {
  if (!benefit) {
    return false
  }
  if (benefit.type === 'standard') {
    return Boolean(benefit.is_used)
  }
  if (benefit.type === 'incremental') {
    const target = Number(benefit.value ?? 0)
    const used = Number(benefit.cycle_redemption_total ?? 0)
    return target > 0 && used >= target
  }
  if (benefit.type === 'cumulative') {
    const expected = Number(benefit.expected_value ?? 0)
    const used = Number(benefit.cycle_redemption_total ?? 0)
    return expected > 0 && used >= expected
  }
  return false
}

export function compareBenefits(a, b) {
  const completedA = isBenefitCompleted(a)
  const completedB = isBenefitCompleted(b)
  if (completedA !== completedB) {
    return completedA ? 1 : -1
  }
  const timeA = getExpirationTime(a)
  const timeB = getExpirationTime(b)
  if (timeA === timeB) {
    const nameA = a?.name ?? ''
    const nameB = b?.name ?? ''
    return nameA.localeCompare(nameB)
  }
  return timeB - timeA
}

export function sortBenefits(benefits) {
  if (!Array.isArray(benefits)) {
    return []
  }
  return [...benefits].sort(compareBenefits)
}


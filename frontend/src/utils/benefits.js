import { parseDate } from './dates'

function getCurrentWindowDueTime(benefit) {
  if (!benefit) {
    return Number.POSITIVE_INFINITY
  }

  const candidates = [
    benefit.current_window_due_date,
    benefit.current_window_end_date,
    benefit.current_window_end,
    benefit.window_end,
    benefit.expiration_date
  ]

  for (const candidate of candidates) {
    if (!candidate) {
      continue
    }
    const parsed = parseDate(candidate)
    if (parsed instanceof Date && !Number.isNaN(parsed.getTime())) {
      return parsed.getTime()
    }
  }

  return Number.POSITIVE_INFINITY
}

export function isBenefitCompleted(benefit) {
  if (!benefit) {
    return false
  }
  if (benefit.type === 'standard') {
    return Boolean(benefit.is_used)
  }
  if (benefit.type === 'incremental') {
    const targetCandidates = [
      benefit.current_window_value,
      benefit.cycle_target_value,
      benefit.value
    ]
    let target = 0
    for (const candidate of targetCandidates) {
      const parsed = Number(candidate)
      if (Number.isFinite(parsed) && parsed > 0) {
        target = parsed
        break
      }
    }
    const used = Number(
      benefit.current_window_total ?? benefit.cycle_redemption_total ?? 0
    )
    return target > 0 && used >= target
  }
  if (benefit.type === 'cumulative') {
    if (benefit.is_used) {
      return true
    }
    const expected = Number(benefit.expected_value ?? 0)
    const used = Number(benefit.cycle_redemption_total ?? 0)
    return expected > 0 && used >= expected
  }
  return false
}

export function compareBenefits(a, b) {
  const deletedA = Boolean(a?.current_window_deleted)
  const deletedB = Boolean(b?.current_window_deleted)
  if (deletedA !== deletedB) {
    return deletedA ? 1 : -1
  }
  const completedA = isBenefitCompleted(a)
  const completedB = isBenefitCompleted(b)
  if (completedA !== completedB) {
    return completedA ? 1 : -1
  }
  const timeA = getCurrentWindowDueTime(a)
  const timeB = getCurrentWindowDueTime(b)
  if (timeA === timeB) {
    const nameA = a?.name ?? ''
    const nameB = b?.name ?? ''
    return nameA.localeCompare(nameB)
  }
  return timeA - timeB
}

export function sortBenefits(benefits) {
  if (!Array.isArray(benefits)) {
    return []
  }
  return [...benefits].sort(compareBenefits)
}


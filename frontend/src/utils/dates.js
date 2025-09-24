const DAY_IN_MS = 24 * 60 * 60 * 1000

function toDate(value) {
  if (!value) {
    return null
  }
  if (value instanceof Date) {
    return new Date(value.getTime())
  }
  if (typeof value === 'number') {
    return new Date(value)
  }
  const stringValue = String(value)
  if (/^\d{4}-\d{2}-\d{2}$/.test(stringValue)) {
    return new Date(`${stringValue}T00:00:00`)
  }
  return new Date(stringValue)
}

function startOfDay(date) {
  const next = new Date(date.getTime())
  next.setHours(0, 0, 0, 0)
  return next
}

function safeDay(year, month, day) {
  const lastDay = new Date(year, month + 1, 0).getDate()
  return Math.min(day, lastDay)
}

function makeDate(year, month, day) {
  const safe = safeDay(year, month, day)
  return startOfDay(new Date(year, month, safe))
}

export function formatDateInput(date) {
  const instance = startOfDay(toDate(date))
  const offset = instance.getTimezoneOffset() * 60_000
  return new Date(instance.getTime() - offset).toISOString().slice(0, 10)
}

export function parseDate(value) {
  const parsed = toDate(value)
  return parsed ? startOfDay(parsed) : null
}

export function endOfMonth(date) {
  const instance = parseDate(date)
  return makeDate(instance.getFullYear(), instance.getMonth() + 1, 0)
}

export function addMonths(date, count) {
  const instance = parseDate(date)
  const targetMonth = instance.getMonth() + count
  const targetYear = instance.getFullYear() + Math.floor(targetMonth / 12)
  const monthIndex = ((targetMonth % 12) + 12) % 12
  return makeDate(targetYear, monthIndex, instance.getDate())
}

export function computeCardCycle(card, referenceDate = new Date()) {
  const today = startOfDay(referenceDate)
  const mode = card.year_tracking_mode || 'calendar'
  if (mode === 'anniversary') {
    const dueDate = parseDate(card.fee_due_date)
    const dueMonth = dueDate.getMonth()
    const dueDay = dueDate.getDate()
    let cycleEnd = makeDate(today.getFullYear(), dueMonth, dueDay)
    if (cycleEnd <= today) {
      cycleEnd = makeDate(today.getFullYear() + 1, dueMonth, dueDay)
    }
    const cycleStart = makeDate(cycleEnd.getFullYear() - 1, dueMonth, dueDay)
    return {
      mode: 'anniversary',
      start: cycleStart,
      end: cycleEnd,
      label: `${cycleStart.getFullYear()}-${cycleEnd.getFullYear()}`
    }
  }
  const year = today.getFullYear()
  return {
    mode: 'calendar',
    start: makeDate(year, 0, 1),
    end: makeDate(year + 1, 0, 1),
    label: `${year}`
  }
}

export function buildCardCycles(card, earliestDate, referenceDate = new Date()) {
  const earliest = parseDate(earliestDate) || parseDate(card.created_at)
  const cycles = []
  const current = computeCardCycle(card, referenceDate)
  if (card.year_tracking_mode === 'anniversary') {
    const dueDate = parseDate(card.fee_due_date)
    const dueMonth = dueDate.getMonth()
    const dueDay = dueDate.getDate()
    let cycleEnd = makeDate(current.end.getFullYear(), dueMonth, dueDay)
    if (cycleEnd <= current.start) {
      cycleEnd = makeDate(current.end.getFullYear() + 1, dueMonth, dueDay)
    }
    while (true) {
      const cycleStart = makeDate(cycleEnd.getFullYear() - 1, dueMonth, dueDay)
      cycles.push({
        mode: 'anniversary',
        start: cycleStart,
        end: cycleEnd,
        label: `${cycleStart.getFullYear()}-${cycleEnd.getFullYear()}`
      })
      if (cycleStart <= earliest) {
        break
      }
      cycleEnd = cycleStart
    }
    return cycles.reverse()
  }
  const startYear = Math.min(earliest.getFullYear(), current.start.getFullYear())
  const endYear = current.end.getFullYear() - 1
  for (let year = startYear; year <= endYear; year += 1) {
    cycles.push({
      mode: 'calendar',
      start: makeDate(year, 0, 1),
      end: makeDate(year + 1, 0, 1),
      label: `${year}`
    })
  }
  return cycles
}

export function isWithinRange(date, start, end) {
  const value = parseDate(date)
  return value >= start && value < end
}

function formatRangeLabel(start, end) {
  const formatter = new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric'
  })
  const startLabel = formatter.format(start)
  const endLabel = formatter.format(new Date(end.getTime() - DAY_IN_MS))
  if (start.getFullYear() === end.getFullYear()) {
    return `${startLabel} – ${endLabel}`
  }
  return `${startLabel} ${start.getFullYear()} – ${endLabel} ${end.getFullYear()}`
}

export function computeFrequencyWindows(cycle, frequency) {
  const monthsByFrequency = {
    monthly: 1,
    quarterly: 3,
    semiannual: 6
  }
  const monthsPerWindow = monthsByFrequency[frequency]
  if (!monthsPerWindow) {
    return [
      {
        start: cycle.start,
        end: cycle.end,
        label: cycle.label
      }
    ]
  }
  const windows = []
  let cursor = cycle.start
  let index = 1
  while (cursor < cycle.end) {
    const windowEnd = addMonths(cursor, monthsPerWindow)
    windows.push({
      start: cursor,
      end: windowEnd < cycle.end ? windowEnd : cycle.end,
      label: `${frequency === 'monthly' ? 'Month' : frequency === 'quarterly' ? 'Quarter' : 'Half'} ${index} · ${formatRangeLabel(cursor, windowEnd < cycle.end ? windowEnd : cycle.end)}`
    })
    cursor = windowEnd
    index += 1
  }
  return windows
}

export function computeCalendarAlignedWindow(frequency, referenceDate = new Date()) {
  const base = parseDate(referenceDate) || startOfDay(new Date())
  const year = base.getFullYear()
  const month = base.getMonth()
  if (frequency === 'monthly') {
    const start = makeDate(year, month, 1)
    return { start, end: addMonths(start, 1) }
  }
  if (frequency === 'quarterly') {
    const quarter = Math.floor(month / 3)
    const start = makeDate(year, quarter * 3, 1)
    return { start, end: addMonths(start, 3) }
  }
  if (frequency === 'semiannual') {
    const startMonth = month < 6 ? 0 : 6
    const start = makeDate(year, startMonth, 1)
    return { start, end: addMonths(start, 6) }
  }
  return null
}

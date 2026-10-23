const DATE_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatDate(value, withTime = false) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return (withTime ? DATE_TIME_FORMATTER : DATE_FORMATTER).format(date)
}

export function formatPercent(value, digits = 0) {
  const number = Number(value) || 0
  return `${(number * 100).toFixed(digits)}%`
}

export function formatDuration(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0)
  const minutes = Math.floor(safeSeconds / 60)
  const remainder = Math.floor(safeSeconds % 60)
  return `${minutes}分${String(remainder).padStart(2, '0')}秒`
}

export function getJoinDays(createdAt) {
  if (!createdAt) return 0
  const start = new Date(createdAt).getTime()
  if (Number.isNaN(start)) return 0
  return Math.max(1, Math.ceil((Date.now() - start) / 86_400_000))
}

export function toIsoDate(value) {
  const date = new Date(value)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function buildDateRange(days) {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - days + 1)
  return { from: toIsoDate(start), to: toIsoDate(end) }
}

export function getInitial(value) {
  return String(value || '学')
    .trim()
    .slice(0, 1)
    .toUpperCase()
}

export function formatPointsPercent(value, digits = 0) {
  const number = Math.max(0, Number(value) || 0)
  return `${number.toFixed(digits)}%`
}

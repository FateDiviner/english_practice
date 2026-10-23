export function getErrorMessage(error, fallback = '操作未完成，请稍后再试') {
  if (!error) return fallback
  if (typeof error === 'string') return error
  return error.message || fallback
}

export function hasBusinessCode(error, code) {
  return Number(error?.code) === Number(code)
}

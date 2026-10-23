import request from './request'

export function getStatsOverview() {
  return request.get('/stats/overview')
}

export function getStatsDaily({ from, to }) {
  return request.get('/stats/daily', { params: { from, to } })
}

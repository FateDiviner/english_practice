import request from './request'

export function listWrongWords({ page = 1, pageSize = 20, resolved = false } = {}) {
  return request.get('/wrong-words', {
    params: { page, page_size: pageSize, resolved },
  })
}

export function removeWrongWord(wordId) {
  return request.delete(`/wrong-words/${wordId}`)
}

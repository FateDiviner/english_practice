import request from './request'

export function getWordAudio(wordId) {
  return request.get(`/words/${wordId}/audio`)
}

export function getWordTtsAudio(wordId, accent = 'us') {
  return request.get(`/words/${wordId}/audio/file`, {
    params: { accent },
    responseType: 'blob',
    timeout: 30_000,
  })
}

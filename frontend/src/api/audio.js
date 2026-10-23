import request from './request'

export function getWordAudio(wordId) {
  return request.get(`/words/${wordId}/audio`)
}

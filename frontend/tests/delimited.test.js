import assert from 'node:assert/strict'
import test from 'node:test'

import { suggestMapping, validateImportRows } from '../src/utils/delimited.js'

test('detects common English and Chinese headers', () => {
  const mapping = suggestMapping(['单词', 'UK', '释义', '词性'])

  assert.equal(mapping.spelling, '0')
  assert.equal(mapping.phonetic_uk, '1')
  assert.equal(mapping.meaning_cn, '2')
  assert.equal(mapping.part_of_speech, '3')
})

test('reports empty and duplicate spellings before import', () => {
  const errors = validateImportRows(
    ['spelling', 'meaning_cn'],
    [
      ['apple', '苹果'],
      ['', '空词'],
      ['Apple', '重复词'],
    ],
    { spelling: '0', meaning_cn: '1' },
  )

  assert.deepEqual(errors, [
    { row: 3, reason: '拼写为空' },
    { row: 4, reason: '与第 2 行拼写重复' },
  ])
})

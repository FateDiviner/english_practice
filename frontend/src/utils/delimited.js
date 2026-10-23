export const IMPORT_FIELDS = [
  { key: 'spelling', label: '拼写', required: true, aliases: ['spelling', 'word', '单词', '拼写'] },
  { key: 'phonetic_uk', label: '英式音标', aliases: ['phonetic_uk', 'uk', '英式音标'] },
  { key: 'phonetic_us', label: '美式音标', aliases: ['phonetic_us', 'us', '美式音标'] },
  { key: 'meaning_cn', label: '中文释义', aliases: ['meaning_cn', 'meaning', '释义', '中文释义'] },
  { key: 'part_of_speech', label: '词性', aliases: ['part_of_speech', 'pos', '词性'] },
  { key: 'example_en', label: '英文例句', aliases: ['example_en', 'example', '例句', '英文例句'] },
  { key: 'example_cn', label: '例句译文', aliases: ['example_cn', 'translation', '例句译文'] },
  { key: 'audio_url', label: '音频地址', aliases: ['audio_url', 'audio', '音频', '音频地址'] },
  { key: 'sort_order', label: '排序', aliases: ['sort_order', 'order', '排序'] },
]

function detectDelimiter(firstLine) {
  const counts = { ',': 0, '\t': 0, ';': 0 }
  let isQuoted = false
  for (const character of firstLine) {
    if (character === '"') isQuoted = !isQuoted
    if (!isQuoted && character in counts) counts[character] += 1
  }
  return Object.entries(counts).sort((left, right) => right[1] - left[1])[0][0]
}

export function parseDelimited(text) {
  const normalized = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n')
  const firstLine = normalized.split('\n', 1)[0] || ''
  const delimiter = detectDelimiter(firstLine)
  const rows = []
  let row = []
  let field = ''
  let isQuoted = false

  for (let index = 0; index < normalized.length; index += 1) {
    const character = normalized[index]
    const nextCharacter = normalized[index + 1]
    if (character === '"' && isQuoted && nextCharacter === '"') {
      field += '"'
      index += 1
    } else if (character === '"') {
      isQuoted = !isQuoted
    } else if (character === delimiter && !isQuoted) {
      row.push(field.trim())
      field = ''
    } else if (character === '\n' && !isQuoted) {
      row.push(field.trim())
      if (row.some((value) => value !== '')) rows.push(row)
      row = []
      field = ''
    } else {
      field += character
    }
  }
  row.push(field.trim())
  if (row.some((value) => value !== '')) rows.push(row)
  return rows
}

export function suggestMapping(headers) {
  const mapping = {}
  for (const field of IMPORT_FIELDS) {
    const index = headers.findIndex((header) =>
      field.aliases.includes(String(header).trim().toLowerCase()),
    )
    if (index >= 0) mapping[field.key] = String(index)
  }
  return mapping
}

export function validateImportRows(headers, rows, mapping) {
  const spellingIndex = Number(mapping.spelling)
  const errors = []
  const seen = new Map()
  rows.forEach((row, index) => {
    const rowNumber = index + 2
    const spelling = String(row[spellingIndex] || '').trim()
    if (!spelling) {
      errors.push({ row: rowNumber, reason: '拼写为空' })
      return
    }
    const normalized = spelling.toLowerCase()
    if (seen.has(normalized)) {
      errors.push({ row: rowNumber, reason: `与第 ${seen.get(normalized)} 行拼写重复` })
    } else {
      seen.set(normalized, rowNumber)
    }
    if (row.length > headers.length) {
      errors.push({ row: rowNumber, reason: '该行列数多于表头' })
    }
  })
  return errors
}

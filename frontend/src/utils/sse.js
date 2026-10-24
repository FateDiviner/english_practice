const EVENT_FIELD = 'event'
const DATA_FIELD = 'data'

function normalizeFrame(frame) {
  return frame.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
}

export function parseSseFrame(frame) {
  const lines = normalizeFrame(frame).split('\n')
  let event = 'message'
  const dataLines = []

  for (const line of lines) {
    if (!line || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)

    if (field === EVENT_FIELD) {
      event = value
    } else if (field === DATA_FIELD) {
      dataLines.push(value)
    }
  }

  if (!dataLines.length) return null
  const raw = dataLines.join('\n')
  let data = raw
  try {
    data = JSON.parse(raw)
  } catch {
    // 非 JSON 数据保留原始文本，交给调用方判断。
  }
  return { event, data, raw }
}

export function createSseParser(onEvent) {
  let buffer = ''

  function dispatch(frame) {
    const parsed = parseSseFrame(frame)
    if (parsed) onEvent(parsed)
  }

  return {
    push(chunk) {
      buffer = normalizeFrame(buffer + chunk)
      let index = buffer.indexOf('\n\n')
      while (index !== -1) {
        dispatch(buffer.slice(0, index))
        buffer = buffer.slice(index + 2)
        index = buffer.indexOf('\n\n')
      }
    },
    flush() {
      if (buffer.trim()) dispatch(buffer)
      buffer = ''
    },
  }
}

export async function consumeSseResponse(response, onEvent) {
  const parser = createSseParser(onEvent)
  if (!response.body) {
    parser.push(await response.text())
    parser.flush()
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      parser.push(decoder.decode(value, { stream: true }))
    }
    parser.push(decoder.decode())
    parser.flush()
  } finally {
    reader.releaseLock()
  }
}

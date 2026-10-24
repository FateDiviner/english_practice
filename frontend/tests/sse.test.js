import assert from 'node:assert/strict'
import test from 'node:test'

import { createSseParser, parseSseFrame } from '../src/utils/sse.js'

test('parses a single event frame', () => {
  const parsed = parseSseFrame('event: meta\ndata: {"intent":"GENERAL"}')

  assert.equal(parsed.event, 'meta')
  assert.deepEqual(parsed.data, { intent: 'GENERAL' })
})

test('joins multiple data lines and ignores comments and unknown fields', () => {
  const parsed = parseSseFrame(': keep-alive\nid: 7\ndata: {"content":\ndata: "hi"}')

  assert.equal(parsed.event, 'message')
  assert.deepEqual(parsed.data, { content: 'hi' })
})

test('keeps non-JSON payload as raw text', () => {
  const parsed = parseSseFrame('event: note\ndata: plain text')

  assert.equal(parsed.data, 'plain text')
  assert.equal(parsed.raw, 'plain text')
})

test('buffers frames split across chunks and handles CRLF', () => {
  const events = []
  const parser = createSseParser((item) => events.push(item))

  parser.push('event: delta\r\ndata: {"content":"你')
  parser.push('好"}\r\n\r\nevent: done\ndata: {"finish_reason":"stop"}\n\n')

  assert.deepEqual(
    events.map((item) => item.event),
    ['delta', 'done'],
  )
  assert.equal(events[0].data.content, '你好')
  assert.equal(events[1].data.finish_reason, 'stop')
})

test('handles a CRLF pair split across chunks', () => {
  const events = []
  const parser = createSseParser((item) => events.push(item))

  parser.push('event: delta\r')
  parser.push('\ndata: {"content":"a"}\r\n\r\n')

  assert.equal(events.length, 1)
  assert.equal(events[0].data.content, 'a')
})

test('flushes a trailing frame without a blank line', () => {
  const events = []
  const parser = createSseParser((item) => events.push(item))

  parser.push('event: done\ndata: {"finish_reason":"stop"}')
  assert.equal(events.length, 0)

  parser.flush()
  assert.equal(events[0].event, 'done')
})

test('skips frames without data', () => {
  const events = []
  const parser = createSseParser((item) => events.push(item))

  parser.push('event: ping\n\n')
  parser.flush()

  assert.deepEqual(events, [])
})

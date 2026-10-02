import { describe, expect, it } from 'vitest'

import { createSseParser } from '@/api/sse'

function collect() {
  const events = []
  return { events, parser: createSseParser((e) => events.push(e)) }
}

const encode = (text) => new TextEncoder().encode(text)

describe('createSseParser', () => {
  it('parses complete events', () => {
    const { events, parser } = collect()

    parser.push(
      encode('data: {"type":"start","message_id":1}\n\ndata: {"type":"delta","text":"안녕"}\n\n'),
    )

    expect(events).toEqual([
      { type: 'start', message_id: 1 },
      { type: 'delta', text: '안녕' },
    ])
  })

  it('handles events split across chunks', () => {
    const { events, parser } = collect()

    parser.push(encode('data: {"type":"del'))
    expect(events).toEqual([])
    parser.push(encode('ta","text":"a"}\n'))
    parser.push(encode('\ndata: {"type":"done","sources":[]}\n\n'))

    expect(events.map((e) => e.type)).toEqual(['delta', 'done'])
  })

  it('handles multi-byte characters split between chunks', () => {
    const { events, parser } = collect()
    const bytes = encode('data: {"type":"delta","text":"가격"}\n\n')

    parser.push(bytes.slice(0, 30)) // cuts inside a UTF-8 sequence
    parser.push(bytes.slice(30))

    expect(events).toEqual([{ type: 'delta', text: '가격' }])
  })

  it('flushes a final event without a trailing blank line', () => {
    const { events, parser } = collect()

    parser.push(encode('data: {"type":"done","sources":[]}'))
    parser.end()

    expect(events).toEqual([{ type: 'done', sources: [] }])
  })
})
